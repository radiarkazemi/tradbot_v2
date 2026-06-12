"""
watcher.py — WatcherWorker thread
Runs in background: reads EA file, detects line touches, places orders, manages Phase 3 cascades.

FIXES applied (from session log analysis):
  1. Triple trigger: multiple sources at same price within 1 pip → only first fires
  2. Duplicate G1 orders: spawn_key now includes round number to prevent collision
  3. Pullback fires into fast market: require 2 closed candles AFTER price moved away
  4. P&L alert spam: handled in gui.py with 10% buffer reset
  5. Best entry logic: wait for candle CLOSE confirmation before placing orders
     (optional per source — enabled by default for HLINE, disabled for RECT)
  6. Cancel ALL pending bot orders on pullback (not just G0)
  7. Close opposing positions on pullback
"""
import threading
from datetime import datetime
import MetaTrader5 as mt5

from config import (
    WATCH_SYMBOL, SCAN_INTERVAL_SEC, MAGIC_NUMBER, PIP_STEP, LOT_SIZE,
)
from core.line_drawer import get_pip_size, write_commands
from core.order_manager import place_level_orders, cancel_all_tb_orders
from core import chart_watcher as cw


class WatcherWorker(threading.Thread):
    def __init__(self, sig, pip_step: float, symbol: str = WATCH_SYMBOL,
                 tp_pips: float = 0.0, spawn_on: str = "L2 and L3",
                 lot_size: float = LOT_SIZE, max_positions: int = 6):
        super().__init__(daemon=True)
        self.sig = sig
        self.pip_step = pip_step
        self.symbol = symbol
        self.tp_pips = tp_pips
        self.spawn_on = spawn_on
        self.lot_size = lot_size
        self.max_positions = max_positions   # hard cap on simultaneous positions
        self._stop = threading.Event()
        self.prev_names = set()
        self.drawn = {}
        self.follow_enabled = True
        self.orders_placed = set()
        self._last_direction = "—"
        # Phase 3
        self.pending_tracker = {}
        self.spawn_rounds = 0
        self.spawned_keys = set()
        self._last_prev_t = 0
        # exposed to GUI
        self.source_registry = {}
        # ── ICT / FVG ─────────────────────────────────────────────
        self.candle_buffer: list = []   # rolling M1 candle history
        self.fvg_zones: list = []   # active unfilled FVG zones
        self.ict_use_fvg_tp: bool = True  # use nearest FVG as TP
        self.ict_partial_close: bool = True  # partial close at G1-L3
        self._fvg_logged: set = set()  # zones already signalled (prevents repeat logs)

    def stop(self): self._stop.set()

    def log(self, msg, lvl="INFO"):
        self.sig.log_line.emit(
            f"{datetime.now().strftime('%H:%M:%S')}  {msg}", lvl)

    # ── Chart drawing ─────────────────────────────────────────────

    @staticmethod
    def _obj_prefix(name: str) -> str:
        import hashlib
        return f"TB_{hashlib.md5(name.encode()).hexdigest()[:6].upper()}_"

    def _draw_hline_levels(self, name, price, pip_size):
        prefix = self._obj_prefix(name)
        step = self.pip_step * pip_size
        l3_buy = round(price + step * 3, 5)
        l3_sell = round(price - step * 3, 5)
        write_commands([
            f"DELETE_PREFIX|{prefix}",
            f"DRAW_HLINE|{prefix}SRC|{price:.5f}|16744995|2|0",
            f"DRAW_HLINE|{prefix}L3B|{l3_buy:.5f}|56702|1|1",
            f"DRAW_HLINE|{prefix}L3S|{l3_sell:.5f}|16728160|1|1",
        ], symbol=self.symbol)
        return step

    # ── Order placement ───────────────────────────────────────────

    # ══════════════════════════════════════════════════════════════
    #  ICT — Fair Value Gap Detection & ICT Exits
    # ══════════════════════════════════════════════════════════════

    def _fvg_alignment(self, src: float, direction: str, pip: float) -> dict | None:
        """
        Check if an FVG aligns with the trade direction within TP range.
        Returns the nearest confirming FVG dict or None.
        Used at touch detection to grade entry quality.
        """
        if not self.fvg_zones:
            return None
        is_sell = "SELL" in direction
        tp_range = self.tp_pips * pip * 2   # search within 2× TP distance
        for z in sorted(
                self.fvg_zones,
                key=lambda x: abs(x["mid"] - src)):
            if is_sell and z["type"] == "bearish" and z["mid"] < src:
                if src - z["mid"] <= tp_range:
                    return z
            elif not is_sell and z["type"] == "bullish" and z["mid"] > src:
                if z["mid"] - src <= tp_range:
                    return z
        return None

    def _apply_fvg_tps_on_orders(self):
        """
        After order placement, update TPs on ALL bot pending orders AND
        open positions to the nearest FVG midpoint in the trade direction.
        Pending orders use TRADE_ACTION_MODIFY.
        Open positions use TRADE_ACTION_SLTP.
        """
        if not self.ict_use_fvg_tp or not self.fvg_zones:
            return

        mod_orders = 0
        # ── Pending orders ────────────────────────────────────────
        pending = mt5.orders_get(symbol=self.symbol) or []
        for o in pending:
            if o.magic != MAGIC_NUMBER:
                continue
            direction = "BUY" if o.type == 4 else "SELL"
            ftp = self._fvg_tp(direction, o.price_open, o.tp)
            if ftp == o.tp or ftp <= 0:
                continue
            res = mt5.order_send({
                "action":    mt5.TRADE_ACTION_MODIFY,
                "order":     o.ticket,
                "price":     o.price_open,
                "sl":        o.sl,
                "tp":        ftp,
                "type_time": mt5.ORDER_TIME_GTC,
            })
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                mod_orders += 1

        # ── Open positions ────────────────────────────────────────
        mod_pos = 0
        positions = mt5.positions_get(symbol=self.symbol) or []
        for p in positions:
            if p.magic != MAGIC_NUMBER:
                continue
            direction = "BUY" if p.type == 0 else "SELL"
            ftp = self._fvg_tp(direction, p.price_open, p.tp)
            if ftp == p.tp or ftp <= 0:
                continue
            res = mt5.order_send({
                "action":   mt5.TRADE_ACTION_SLTP,
                "symbol":   self.symbol,
                "position": p.ticket,
                "sl":       p.sl,
                "tp":       ftp,
            })
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                mod_pos += 1

        if mod_orders + mod_pos > 0:
            self.log(
                f"🎯 FVG TP applied: {mod_orders} pending orders + "
                f"{mod_pos} positions → nearest FVG midpoint", "NEW")

    def _check_fvg_fill_exit(self, bid: float):
        """
        Log once when price enters an FVG zone.
        No auto-close — FVGs are visual signals only.
        Uses _fvg_logged set so the same zone never fires twice,
        even after _detect_fvg() rebuilds the zones list.
        """
        if not self.fvg_zones:
            return
        # Only signal if the bot actually has open positions to act on
        positions = mt5.positions_get(symbol=self.symbol) or []
        bot_positions = [p for p in positions if p.magic == MAGIC_NUMBER]
        if not bot_positions:
            return
        for z in self.fvg_zones:
            if not (z["bottom"] <= bid <= z["top"]):
                continue
            key = f"{z['type']}_{z['top']:.5f}_{z['bottom']:.5f}"
            if key in self._fvg_logged:
                continue
            zone_dir = z["type"]
            suggest = "SELL" if zone_dir == "bearish" else "BUY"
            pos_type = 1 if suggest == "SELL" else 0   # MT5 type: 0=BUY, 1=SELL
            positions = mt5.positions_get(symbol=self.symbol) or []
            has_pos = any(
                p.magic == MAGIC_NUMBER and p.type == pos_type
                for p in positions)
            if not has_pos:
                continue   # no relevant positions — skip the log
            self._fvg_logged.add(key)
            self.log(
                f"📐 FVG {zone_dir} entered @ {bid:.5f} "
                f"({z['bottom']:.5f}–{z['top']:.5f} mid={z['mid']:.5f}) "
                f"— consider closing {suggest} positions", "NEW")

    def _load_historical_candles(self, count: int = 120):
        """
        Load the last N closed M1 candles directly from MT5 on startup.
        This fills the candle buffer immediately so FVG detection works
        from the first scan without waiting for live candles to accumulate.
        """
        try:
            rates = mt5.copy_rates_from_pos(
                self.symbol, mt5.TIMEFRAME_M1, 1, count)
            if rates is None or len(rates) == 0:
                self.log(
                    "⚠️  Historical candles unavailable — FVG will build over time", "WARN")
                return
            self.candle_buffer = []
            for r in rates:
                c = {
                    "t":     int(r["time"]),
                    "open":  float(r["open"]),
                    "high":  float(r["high"]),
                    "low":   float(r["low"]),
                    "close": float(r["close"]),
                }
                if c["high"] > 0:
                    self.candle_buffer.append(c)
            self.candle_buffer.sort(key=lambda x: x["t"])
            if len(self.candle_buffer) > 120:
                self.candle_buffer = self.candle_buffer[-120:]
            self.log(
                f"📊  Loaded {len(self.candle_buffer)} M1 candles from MT5 "
                f"— running FVG scan…", "NEW")
            self._detect_fvg()
        except Exception as e:
            self.log(f"⚠️  Historical candle load failed: {e}", "WARN")

    def _update_candle_buffer(self, candle: dict):
        """Add latest closed candle to rolling buffer (called each scan)."""
        prev_t = candle.get("PREV_T", 0)
        if not prev_t:
            return
        if self.candle_buffer and self.candle_buffer[-1]["t"] == prev_t:
            return  # same candle, no update needed
        c = {
            "t":     prev_t,
            "open":  candle.get("PREV_O", 0.0),
            "high":  candle.get("PREV_H", 0.0),
            "low":   candle.get("PREV_L", 0.0),
            "close": candle.get("PREV_C", 0.0),
        }
        if c["high"] <= 0:
            return
        self.candle_buffer.append(c)
        if len(self.candle_buffer) > 120:      # keep 2 hours of M1 data
            self.candle_buffer.pop(0)

    def _detect_fvg(self):
        """
        Scan candle buffer for Fair Value Gaps (3-candle imbalance).

        Bullish FVG : C1.high < C3.low  → gap = (C1.high , C3.low)
        Bearish FVG : C1.low  > C3.high → gap = (C3.high , C1.low)

        Only keeps unfilled gaps (price hasn't re-entered the zone).
        Stores results in self.fvg_zones.
        """
        if len(self.candle_buffer) < 3:
            return

        # current mid-price for fill check
        try:
            tick = mt5.symbol_info_tick(self.symbol)
            cur = (tick.bid + tick.ask) / 2 if tick else 0.0
        except Exception:
            cur = 0.0

        zones = []
        buf = self.candle_buffer[-50:]          # scan last 50 candles only
        for i in range(1, len(buf) - 1):
            c1, c3 = buf[i - 1], buf[i + 1]
            if c1["high"] <= 0 or c3["high"] <= 0:
                continue

            # Bullish FVG
            if c1["high"] < c3["low"]:
                bottom = c1["high"]
                top = c3["low"]
                mid = (top + bottom) / 2
                filled = cur > 0 and bottom <= cur <= top
                if not filled:
                    zones.append({
                        "type": "bullish", "top": top, "bottom": bottom,
                        "mid": mid, "time": c3["t"], "filled": False})

            # Bearish FVG
            elif c1["low"] > c3["high"]:
                top = c1["low"]
                bottom = c3["high"]
                mid = (top + bottom) / 2
                filled = cur > 0 and bottom <= cur <= top
                if not filled:
                    zones.append({
                        "type": "bearish", "top": top, "bottom": bottom,
                        "mid": mid, "time": c3["t"], "filled": False})

        self.fvg_zones = zones

        # Prune _fvg_logged: remove keys for zones no longer detected
        # (they may reappear later as fresh zones and should log again)
        active_keys = {
            f"{z['type']}_{z['top']:.5f}_{z['bottom']:.5f}"
            for z in zones}
        self._fvg_logged &= active_keys   # keep only still-active ones

        # ── Draw FVG zones on MT5 chart ───────────────────────────
        # Clear old FVG drawings, then draw new ones as horizontal lines
        cmds = ["DELETE_PREFIX|TB_FVG_"]
        for i, z in enumerate(zones[:12]):          # max 12 zones on chart
            t = z["type"]
            if t == "bullish":
                c_top = 32768       # dark green top border
                c_mid = 65280       # bright green midpoint
                c_bot = 32768       # dark green bottom border
            else:
                c_top = 8388608     # dark red top border
                c_mid = 16711680    # bright red midpoint
                c_bot = 8388608     # dark red bottom border
            pfx = f"TB_FVG_{t[:4].upper()}_{i}"
            cmds += [
                # dashed top
                f"DRAW_HLINE|{pfx}_T|{z['top']:.5f}|{c_top}|1|1",
                # solid mid (target)
                f"DRAW_HLINE|{pfx}_M|{z['mid']:.5f}|{c_mid}|2|0",
                # dashed bottom
                f"DRAW_HLINE|{pfx}_B|{z['bottom']:.5f}|{c_bot}|1|1",
            ]
        write_commands(cmds, symbol=self.symbol)

        # ── Emit to GUI panel ─────────────────────────────────────
        summary = (
            f"📐 FVG: {sum(1 for z in zones if z['type'] == 'bullish')} bullish  "
            f"{sum(1 for z in zones if z['type'] == 'bearish')} bearish"
        )
        self.sig.log_line.emit(f"__FVG_UPDATE__|{summary}|{zones!r}", "FVG")

    def _fvg_tp(self, direction: str, entry: float, fallback: float) -> float:
        """
        Return nearest FVG midpoint as TP target.
        SELL → nearest bearish FVG below entry.
        BUY  → nearest bullish FVG above entry.
        Falls back to fallback if no suitable FVG exists.
        """
        if not self.ict_use_fvg_tp or not self.fvg_zones:
            return fallback
        is_sell = "SELL" in direction
        candidates = []
        for z in self.fvg_zones:
            if is_sell and z["type"] == "bearish" and z["mid"] < entry:
                candidates.append(z["mid"])
            elif not is_sell and z["type"] == "bullish" and z["mid"] > entry:
                candidates.append(z["mid"])
        if not candidates:
            return fallback
        # nearest: highest bearish below for SELL, lowest bullish above for BUY
        return max(candidates) if is_sell else min(candidates)

    def _apply_fvg_tps(self):
        """
        After a spawn, update all open positions' TP to the nearest FVG target.
        Only updates if FVG TP is more favourable than existing TP.
        """
        if not self.ict_use_fvg_tp:
            return
        positions = mt5.positions_get(symbol=self.symbol) or []
        updated = 0
        for p in positions:
            if p.magic != MAGIC_NUMBER:
                continue
            direction = "BUY" if p.type == 0 else "SELL"
            fvg_tp = self._fvg_tp(direction, p.price_open, p.tp)
            if fvg_tp == p.tp or fvg_tp <= 0:
                continue
            # Only tighten TP if it's closer (more conservative exit)
            if direction == "BUY" and fvg_tp < p.price_open:
                continue
            if direction == "SELL" and fvg_tp > p.price_open:
                continue
            res = mt5.order_send({
                "action":   mt5.TRADE_ACTION_SLTP,
                "symbol":   self.symbol,
                "position": p.ticket,
                "sl":       p.sl,
                "tp":       fvg_tp,
            })
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                updated += 1
        if updated:
            self.log(
                f"🎯 ICT: Updated TP on {updated} positions to nearest FVG", "NEW")

    def _ict_partial_close(self):
        """
        Called when G1-L3 activates.
        Closes 50% of profitable positions (oldest first) and locks gains.
        Moves remaining SLs to breakeven.
        """
        if not self.ict_partial_close:
            return
        positions = mt5.positions_get(symbol=self.symbol) or []
        bot_pos = sorted(
            [p for p in positions if p.magic == MAGIC_NUMBER],
            key=lambda p: p.time)  # oldest first

        profitable = [p for p in bot_pos if p.profit > 0]
        if not profitable:
            self.log("ℹ️  ICT partial close: no profitable positions to close")
            return

        close_n = max(1, len(profitable) // 2)   # 50%
        to_close = profitable[:close_n]
        closed = 0
        locked_pnl = 0.0

        for p in to_close:
            close_type = mt5.ORDER_TYPE_SELL if p.type == 0 else mt5.ORDER_TYPE_BUY
            tick = mt5.symbol_info_tick(self.symbol)
            price = tick.bid if close_type == mt5.ORDER_TYPE_SELL else tick.ask
            for fill in (mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_IOC,
                         mt5.ORDER_FILLING_RETURN):
                req = {
                    "action":       mt5.TRADE_ACTION_DEAL,
                    "symbol":       self.symbol,
                    "volume":       p.volume,
                    "type":         close_type,
                    "position":     p.ticket,
                    "price":        price,
                    "deviation":    30,
                    "magic":        MAGIC_NUMBER,
                    "comment":      "TB_ICT_PARTIAL",
                    "type_time":    mt5.ORDER_TIME_GTC,
                    "type_filling": fill,
                }
                res = mt5.order_send(req)
                if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                    closed += 1
                    locked_pnl += p.profit
                    break

        # Move remaining profitable positions' SL to breakeven
        be_moved = 0
        remaining = [p for p in profitable if p not in to_close]
        for p in remaining:
            res = mt5.order_send({
                "action":   mt5.TRADE_ACTION_SLTP,
                "symbol":   self.symbol,
                "position": p.ticket,
                "sl":       p.price_open,   # breakeven
                "tp":       p.tp,
            })
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                be_moved += 1

        self.log(
            f"💰 ICT G1-L3 partial close: locked ${locked_pnl:.2f} | "
            f"closed {closed}/{len(profitable)} profitable | "
            f"moved {be_moved} SLs to breakeven", "NEW")

    def _place_orders_for_source(self, source_price: float, pip_size: float, generation: int = 0):
        # ── Ensure MT5 is initialized and logged in ───────────────
        # MT5 must be initialized per-thread. The spawn fires inside the
        # same watcher thread but mt5.terminal_info() can still return None
        # if the session was lost. Reinitialize + login if needed.
        try:
            connected = mt5.terminal_info() is not None and mt5.account_info() is not None
        except Exception:
            connected = False
        if not connected:
            from config import MT5_LOGIN, MT5_PASSWORD, MT5_SERVER
            # Try initialize with full credentials first
            ok = mt5.initialize(
                login=MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER)
            if not ok:
                # Fallback: bare initialize then login
                mt5.initialize()
                ok = mt5.login(MT5_LOGIN, password=MT5_PASSWORD,
                               server=MT5_SERVER)
            if not ok:
                self.log(
                    f"💥  MT5 reconnect failed — cannot place G{generation} orders | "
                    f"error: {mt5.last_error()}", "ERROR")
                return
            self.log(f"🔄  MT5 reconnected for G{generation} order placement")

        # ── Max positions guard ───────────────────────────────────
        # Count current open bot positions before placing new orders
        current_positions = mt5.positions_get(symbol=self.symbol) or []
        bot_pos_count = sum(
            1 for p in current_positions if p.magic == MAGIC_NUMBER)
        if bot_pos_count >= self.max_positions:
            self.log(
                f"⛔  Max positions reached ({bot_pos_count}/{self.max_positions}) "
                f"— skipping G{generation} order placement", "WARN")
            return
        try:
            results = place_level_orders(
                source_price, pip_size, self.pip_step, self.symbol,
                generation, tp_pips=self.tp_pips, lot_size=self.lot_size)
            ok = sum(1 for r in results if r["ok"])
            failed = [r for r in results if not r["ok"]]

            for r in results:
                if r["ok"] and r.get("ticket"):
                    o = r["order"]
                    self.pending_tracker[r["ticket"]] = {
                        "level": o["level"], "generation": generation,
                        "source": source_price, "direction": o["type"],
                        "entry": o["entry"], "sl": o["sl"], "tp": o["tp"],
                    }

            step = self.pip_step * pip_size
            if ok == len(results):
                self.log(
                    f"📋  G{generation}: {ok}/6 placed @ {source_price:.5f} | step={step:.5f}")
                for r in results:
                    o = r["order"]
                    icon = "🟢" if o["type"] == "BUY_STOP" else "🔴"
                    self.log(f"   {icon} G{generation}-L{o['level']} {o['type']:10s}"
                             f" entry={o['entry']:.5f} sl={o['sl']:.5f} tp={o['tp']:.5f}")
            else:
                reasons = set(r.get("reason", "?") for r in failed)
                self.log(
                    f"⚠️  G{generation}: {ok}/6 placed | failed: {', '.join(reasons)}", "WARN")
                for r in results:
                    o = r["order"]
                    icon = "🟢" if o["type"] == "BUY_STOP" else "🔴"
                    status = "✅" if r["ok"] else f"❌({r.get('reason', '?')[:20]})"
                    self.log(
                        f"   {icon} {status} {o['type']:10s} entry={o['entry']:.5f} sl={o['sl']:.5f}")
        except Exception as e:
            self.log(f"💥  Order error: {type(e).__name__}: {e}", "ERROR")

    # ── FIX 1: Duplicate source guard ────────────────────────────
    # If multiple sources exist at the same price (within 1 pip),
    # only the first one should trigger. Subsequent ones are blocked
    # for that candle.

    def _already_triggered_at_price(self, price: float, pip: float, current_name: str) -> bool:
        """Return True if another source already triggered at same price this candle."""
        tolerance = pip * 1.0  # 1 pip
        for n, reg in self.source_registry.items():
            if n == current_name:
                continue
            if not reg.get("just_triggered_t"):
                continue
            if abs(reg["src"] - price) <= tolerance:
                return True
        return False

    # ── Phase 3 cascade ───────────────────────────────────────────

    def _check_phase3_activations(self, pip: float):
        """Detect triggered pending orders and spawn new rounds."""
        if not self.pending_tracker or self.spawn_rounds >= 9:
            return
        import time as _t

        still_pending = set()
        pending = mt5.orders_get(symbol=self.symbol)
        if pending:
            for o in pending:
                if o.magic == MAGIC_NUMBER:
                    still_pending.add(o.ticket)

        triggered = {t: info for t, info in self.pending_tracker.items()
                     if t not in still_pending}

        activations_this_scan = []
        for ticket, info in list(triggered.items()):
            gen, level = info["generation"], info["level"]
            entry, sl, tp = info["entry"], info["sl"], info["tp"]
            direction = info["direction"]
            icon = "🟢 BUY" if "BUY" in direction else "🔴 SELL"
            self.log(f"⚡  {icon} G{gen}-L{level} ACTIVATED | "
                     f"entry={entry:.5f} sl={sl:.5f} tp={tp:.5f} | ticket=#{ticket}", "NEW")
            activations_this_scan.append(info)

            # Arm pullback when L3 hits
            if level == 3:
                for reg in self.source_registry.values():
                    if abs(reg.get("src", 0) - info.get("source", entry)) < pip * 0.5:
                        if gen == 0:
                            # G0-L3: arm pullback normally
                            reg["l3_activated"] = True
                            reg["l3_activated_candle_t"] = self._last_prev_t
                            reg["_last_candle_counted"] = self._last_prev_t
                            reg["candles_since_l3"] = 0
                            reg["price_was_away"] = False
                            self.log(
                                f"   ✅ L3 hit — pullback armed (needs 5+ candles away from source)")
                        elif gen == 1:
                            # FIX: G1-L3: re-arm pullback on ORIGINAL main line source
                            # price_was_away=True means next touch fires immediately
                            reg["l3_activated"] = True
                            reg["l3_activated_candle_t"] = self._last_prev_t
                            reg["_last_candle_counted"] = self._last_prev_t
                            reg["candles_since_l3"] = 5   # bypass wait
                            reg["price_was_away"] = True  # already away
                            self.log(
                                f"   ↩️  G1-L3 hit — pullback re-armed on main source @ {reg['src']:.5f}")
                            # ── ICT exits ────────────────────────────────────
                            self._ict_partial_close()   # lock 50% of profits
                            self._apply_fvg_tps()       # snap TPs to FVG zones

            del self.pending_tracker[ticket]

        if len(activations_this_scan) >= 3:
            self.log(f"⚡  {len(activations_this_scan)} levels activated in one scan — "
                     f"breakout candle detected, spawn cooldown enforced", "WARN")

        import time as _t
        last_spawn = getattr(self, "_last_spawn_time", 0)
        if _t.time() - last_spawn < 60.0:
            remaining = int(60 - (_t.time() - last_spawn))
            if not getattr(self, "_spawn_cooldown_logged", False):
                self.log(f"⏱️  Spawn cooldown — next spawn in {remaining}s")
                self._spawn_cooldown_logged = True
            return
        self._spawn_cooldown_logged = False

        spawn_lvls = []
        if "L2" in self.spawn_on:
            spawn_lvls.append(2)
        if "L3" in self.spawn_on:
            spawn_lvls.append(3)

        candidates = sorted(triggered.items(),
                            key=lambda kv: (-kv[1]["level"], kv[1]["generation"]))

        for ticket, info in candidates:
            level, gen = info["level"], info["generation"]
            entry, direction = info["entry"], info["direction"]

            if level not in spawn_lvls:
                continue
            if gen >= 1:
                continue       # only G0 spawns G1 — no deeper cascade
            if self.spawn_rounds >= 9:
                self.log("⛔  Max 9 rounds reached — no more spawning")
                break

            # FIX 2: Include round number in spawn_key to prevent duplicate G1 orders
            spawn_key = f"{entry:.5f}_G{gen+1}_{direction[:4]}_R{self.spawn_rounds + 1}"
            if spawn_key in self.spawned_keys:
                self.log(
                    f"ℹ️  Already spawned from {entry:.5f} {direction[:4]} R{self.spawn_rounds+1} — skipping")
                continue

            self.spawned_keys.add(spawn_key)
            self.spawn_rounds += 1
            self._last_spawn_time = _t.time()
            new_gen = gen + 1
            self.log(f"🔄  Phase 3 round {self.spawn_rounds}/9 — "
                     f"G{gen}-L{level} {direction} @ {entry:.5f} → "
                     f"new source G{new_gen} @ {entry:.5f}", "NEW")
            self._draw_hline_levels(
                f"TB_SPAWN_G{new_gen}_R{self.spawn_rounds}", entry, pip)
            self._place_orders_for_source(entry, pip, generation=new_gen)
            self._apply_fvg_tps_on_orders()   # snap all TPs to FVG
            self._log_position_map()
            break

    def _log_position_map(self):
        sep = "─" * 55
        self.log(sep)
        orders = mt5.orders_get(symbol=self.symbol)
        bot_orders = [o for o in (orders or []) if o.magic == MAGIC_NUMBER]
        if bot_orders:
            self.log(f"📋 Pending orders ({len(bot_orders)}):")
            for o in sorted(bot_orders, key=lambda x: x.price_open):
                t = "BUY_STOP" if o.type == 4 else "SELL_STOP"
                self.log(f"   #{o.ticket} {t:10s} entry={o.price_open:.5f} "
                         f"sl={o.sl:.5f} tp={o.tp:.5f} | {getattr(o, 'comment', '')}")
        positions = mt5.positions_get(symbol=self.symbol)
        bot_pos = [p for p in (positions or []) if p.magic == MAGIC_NUMBER]
        if bot_pos:
            self.log(f"📊 Active positions ({len(bot_pos)}):")
            for p in sorted(bot_pos, key=lambda x: x.price_open):
                t = "BUY " if p.type == 0 else "SELL"
                self.log(f"   #{p.ticket} {t} entry={p.price_open:.5f} "
                         f"sl={p.sl:.5f} tp={p.tp:.5f} | PnL={p.profit:+.2f}")
        if not bot_orders and not bot_pos:
            self.log("   (no bot orders or positions)")
        self.log(f"   Rounds spawned: {self.spawn_rounds}/9 | "
                 f"Tracked pending: {len(self.pending_tracker)}")
        self.log(sep)

    # ── Pullback detection ────────────────────────────────────────

    def _check_pullback(self, n, reg, candle, pip):
        """
        WWW / MMM pullback logic.

        When price returns to the main source line after L3 was hit:
          - Place a fresh G0 set of orders at the source
          - DO NOT cancel any existing orders
          - DO NOT close any existing positions
          - Reset spawn keys so next L3 hit creates G1 again (round +1)

        All existing positions and pending orders from previous rounds
        stay alive — they will ride to TP or SL naturally.
        This is the correct WWW/MMM accumulation pattern.
        """
        if self.spawn_rounds >= 9:
            return
        if not reg.get("l3_activated", False):
            return

        src = reg["src"]
        prev_t = candle.get("PREV_T", 0)
        prev_h = candle.get("PREV_H", 0.0)
        prev_l = candle.get("PREV_L", 0.0)
        prev_o = candle.get("PREV_O", 0.0)
        l3_t = reg.get("l3_activated_candle_t", 0)
        cnt = reg.get("candles_since_l3", 0)

        # Count new M1 candles since L3 activated
        if prev_t > reg.get("_last_candle_counted", 0) and prev_t > l3_t:
            reg["_last_candle_counted"] = prev_t
            cnt += 1
            reg["candles_since_l3"] = cnt

        if cnt < 5:
            return

        if prev_h <= 0 or prev_l <= 0:
            return

        # Track whether price moved at least 2 pips away from source
        if prev_l > src + pip or prev_h < src - pip:
            reg["price_was_away"] = True
            reg["candles_away"] = reg.get("candles_away", 0) + 1
        else:
            candles_away = reg.get("candles_away", 0)
            if reg.get("price_was_away", False) and candles_away >= 2:
                last_rb = reg.get("last_pullback_t", 0)
                if prev_t > last_rb:
                    reg["last_pullback_t"] = prev_t
                    reg["price_was_away"] = False
                    reg["candles_since_l3"] = 0
                    reg["candles_away"] = 0

                    side = "from above" if prev_o > src else "from below"

                    # Reset G1 spawn keys so next G0-L3 spawns G1 again
                    old_count = len(self.spawned_keys)
                    self.spawned_keys = {
                        k for k in self.spawned_keys if "_G1_" not in k}
                    reset = old_count - len(self.spawned_keys)
                    if reset:
                        self.log(
                            f"♻️  Reset {reset} G1 spawn key(s) — "
                            f"next G0-L3 will spawn G1 again")

                    # Place fresh G0 at main line
                    # NOTE: existing orders and positions are NOT touched
                    # They ride to their TP or SL naturally
                    self.log(
                        f"🔁  Pullback [{n[:20]}] @ {src:.5f} {side} — "
                        f"adding fresh G0 (existing positions untouched)", "NEW")
                    self._place_orders_for_source(src, pip, generation=0)
                    self._log_position_map()
            else:
                reg["candles_away"] = 0

    def run(self):
        if not cw.connect_mt5():
            self.log("❌  MT5 connection failed", "ERROR")
            self.sig.status.emit("❌  MT5 connection failed")
            return

        pip = get_pip_size(self.symbol)
        mt5.symbol_select(self.symbol, True)
        info = mt5.symbol_info(self.symbol)
        if info:
            min_dist = info.trade_stops_level * info.point
            min_pips = min_dist / pip if pip > 0 else 0
            self.log(f"✅  Connected | {self.symbol} | pip={pip:.5f} | "
                     f"step={self.pip_step} pips | TP={self.tp_pips:.0f}pips | spawn={self.spawn_on}")
            self.log(
                f"📐  Min stop distance: {min_dist:.5f} = {min_pips:.1f} pips")
        else:
            self.log(f"✅  Connected | {self.symbol} | pip={pip:.5f}")

        self.sig.status.emit("🟢  Running")
        source_registry = {}
        self.source_registry = source_registry

        # Load historical M1 candles for immediate FVG analysis
        self._load_historical_candles(120)

        import os as _os
        import time as _time

        while not self._stop.is_set():
            try:
                path = cw.find_objects_file(self.symbol)

                if path and path != getattr(self, "_last_path", None):
                    self._last_path = path
                    self.log(f"📂  Reading EA file: {path}")
                    try:
                        with open(path, encoding="utf-8", errors="ignore") as f:
                            first = f.read(200)
                        for line in first.splitlines():
                            if line.startswith("SYMBOL:"):
                                file_sym = line.split(":", 1)[1].strip()
                                if file_sym != self.symbol:
                                    self.log(
                                        f"⚠️  File symbol '{file_sym}' ≠ bot symbol '{self.symbol}'", "WARN")
                                break
                    except Exception:
                        pass

                if not path:
                    self.sig.status.emit("⏳  Waiting for EA…")
                    self._stop.wait(min(SCAN_INTERVAL_SEC, 1))
                    continue

                try:
                    file_age = _time.time() - _os.path.getmtime(path)
                except:
                    file_age = 0
                if file_age > 15:
                    if not getattr(self, "_stale_warned", False) or int(file_age) % 30 < 1:
                        self._stale_warned = True
                        self.log(
                            f"⚠️  EA file {file_age:.0f}s old — EA not running on {self.symbol} chart", "WARN")
                    self.sig.status.emit(f"⚠️  EA stopped ({file_age:.0f}s)")
                    self._stop.wait(min(SCAN_INTERVAL_SEC, 1))
                    continue
                else:
                    if getattr(self, "_stale_warned", False):
                        self.log("✅  EA writing again — resuming")
                    self._stale_warned = False

                parsed = cw.parse_objects_file(path)
                if len(parsed) == 4:
                    trader, auto, ea_sym, candle = parsed
                elif len(parsed) == 3:
                    trader, auto, ea_sym, candle = parsed[0], parsed[1], parsed[2], {
                    }
                else:
                    trader, auto, ea_sym, candle = parsed[0], parsed[1], None, {
                    }

                if ea_sym:
                    self.sig.log_line.emit(f"__EA_SYM__{ea_sym}", "EA")

                if ea_sym and ea_sym != self.symbol:
                    if ea_sym != getattr(self, "_last_ea_warn", None):
                        self._last_ea_warn = ea_sym
                        self.log(
                            f"⚠️  EA on '{ea_sym}' chart — not '{self.symbol}'", "WARN")
                    self._stop.wait(min(SCAN_INTERVAL_SEC, 1))
                    continue

                self.sig.new_objects.emit(trader, auto)

                self._dbg_count = getattr(self, "_dbg_count", 0) + 1
                if self._dbg_count % 30 == 0:
                    waiting = [f"[{k[:15]}]={v['src']:.5f}"
                               for k, v in source_registry.items() if not v.get("triggered")]
                    if waiting:
                        bid = candle.get("BID", 0)
                        ch = candle.get("CANDLE_H", 0)
                        cl = candle.get("CANDLE_L", 0)
                        try:
                            age = int(_time.time() - _os.path.getmtime(path))
                            age_s = f" | file_age={age}s"
                        except:
                            age_s = ""
                        self.log(
                            f"⏳  Watching: {', '.join(waiting)} | bid={bid:.5f} H={ch:.5f} L={cl:.5f}{age_s}")

                self.sig.log_line.emit(f"__CANDLE__{repr(candle)}", "RF")

                cur = {o.name for o in trader}
                tick = mt5.symbol_info_tick(self.symbol)
                current_price = (tick.bid + tick.ask) / 2 if tick else 0.0

                cur_candle_t = candle.get("CANDLE_T", 0)
                cur_h = candle.get("CANDLE_H", current_price)
                cur_l = candle.get("CANDLE_L", current_price)
                cur_c = candle.get("CANDLE_C", current_price)
                cur_o = candle.get("CANDLE_O", current_price)
                prev_h = candle.get("PREV_H", 0.0)
                prev_l = candle.get("PREV_L", 0.0)

                # ── ICT: update candle buffer + detect FVGs ───────
                self._update_candle_buffer(candle)
                self._detect_fvg()   # runs every new M1 candle

                # ── ICT: FVG fill exit check ───────────────────────
                bid = candle.get("BID", 0.0)
                if bid > 0:
                    self._check_fvg_fill_exit(bid)
                prev_c = candle.get("PREV_C", 0.0)
                prev_o = candle.get("PREV_O", 0.0)
                self._last_prev_t = candle.get("PREV_T", 0)

                # ── Detect new objects ───────────────────────────
                for n in cur - self.prev_names:
                    if n in self.drawn:
                        continue
                    obj = next(o for o in trader if o.name == n)

                    if current_price > 0 and obj.price1 > 0:
                        ratio = obj.price1 / current_price
                        if ratio < 0.5 or ratio > 2.0:
                            self.drawn[n] = "WRONG_SYMBOL"
                            self.log(f"⏭  [{n[:25]}] @ {obj.price1:.5f} skipped "
                                     f"(ratio={ratio:.2f} vs current={current_price:.5f})")
                            continue

                    if obj.is_hline:
                        src = obj.price1
                        self._draw_hline_levels(n, src, pip)
                        self.drawn[n] = src
                        prev_t_reg = candle.get("PREV_T", 0)
                        source_registry[n] = {
                            "src": src, "triggered": False, "gen": 0,
                            "registered_at_candle": prev_t_reg,
                            "last_prev_t": prev_t_reg,
                        }
                        self.log(f"🆕  HLINE [{n[:25]}] @ {src:.5f} | 3+3 levels drawn | "
                                 f"waiting for NEXT candle to touch line")

                    elif obj.is_rectangle:
                        if not obj.rect_valid:
                            self.drawn[n] = "INVALID"
                            self.log(
                                f"⚠️  [{n[:25]}] rectangle has zero height — skipping")
                            continue
                        center = round((obj.rect_top + obj.rect_bottom) / 2, 5)
                        self._draw_hline_levels(n, center, pip)
                        self.drawn[n] = center
                        prev_t_reg = candle.get("PREV_T", 0)
                        source_registry[n] = {
                            "src": center, "triggered": False, "gen": 0,
                            "registered_at_candle": prev_t_reg,
                            "last_prev_t": prev_t_reg,
                        }
                        self.log(
                            f"🆕  RECT [{n[:25]}] center={center:.5f} | waiting for touch")

                # ── Touch detection & pullback ───────────────────
                for n, reg in list(source_registry.items()):
                    if reg["triggered"]:
                        self._check_pullback(n, reg, candle, pip)
                        continue

                    src = reg["src"]
                    registered_at = reg.get("registered_at_candle", 0)
                    touched = False
                    touch_h = touch_l = touch_c = touch_o = 0.0

                    # FIX 1: Skip if another source at same price already triggered
                    # this candle (prevents triple-fire from 3 rects at same level)
                    if self._already_triggered_at_price(src, pip, n):
                        continue

                    # Check 1: Current forming candle
                    if cur_h > 0 and cur_candle_t != registered_at:
                        if cur_l <= src <= cur_h:
                            touched = True
                            touch_h, touch_l, touch_c, touch_o = cur_h, cur_l, cur_c, cur_o

                    # Check 2: Previous closed candle (fallback)
                    if not touched and prev_h > 0:
                        prev_t_val = candle.get("PREV_T", 0)
                        last_checked = reg.get("last_prev_t", 0)
                        if prev_t_val > last_checked and prev_t_val > registered_at:
                            reg["last_prev_t"] = prev_t_val
                            if prev_l <= src <= prev_h:
                                touched = True
                                touch_h, touch_l, touch_c, touch_o = prev_h, prev_l, prev_c, prev_o

                    if touched:
                        reg["triggered"] = True
                        reg["just_triggered_t"] = cur_candle_t
                        reg["last_touch_t"] = candle.get("PREV_T", 0)
                        reg["last_pullback_t"] = candle.get("PREV_T", 0)
                        # FIX: use APPROACH direction (open side) not close
                        # touch_c can equal src exactly → close-based direction is unreliable
                        # touch_o tells us which side price came FROM:
                        #   open below src → price approached from below → BUY bias
                        #   open above src → price approached from above → SELL bias
                        if touch_o < src:
                            direction = "BUY"
                            side = "from below"
                        elif touch_o > src:
                            direction = "SELL"
                            side = "from above"
                        else:
                            # open exactly at src — fall back to close
                            direction = "BUY" if touch_c >= src else "SELL"
                            side = "from below" if direction == "BUY" else "from above"
                        self._last_direction = direction
                        icon = "🟢" if direction == "BUY" else "🔴"
                        self.log(f"🎯  [{n[:20]}] touched @ {src:.5f} {side} | "
                                 f"C={touch_c:.5f} → {icon} {direction} bias | placing orders", "NEW")
                        # ── ICT entry confirmation ────────────────
                        fvg_conf = self._fvg_alignment(src, direction, pip)
                        if fvg_conf:
                            self.log(
                                f"   ✅ FVG aligned: {fvg_conf['type']} "
                                f"{fvg_conf['bottom']:.5f}–{fvg_conf['top']:.5f}  "
                                f"mid={fvg_conf['mid']:.5f} — HIGH PROB entry", "NEW")
                        else:
                            self.log(
                                f"   ⚠️  No FVG alignment in TP range — "
                                f"lower probability entry", "WARN")
                        self._place_orders_for_source(
                            src, pip, generation=reg["gen"])
                        self._apply_fvg_tps_on_orders()  # snap TPs to FVG

                # ── Phase 3 ──────────────────────────────────────
                self._check_phase3_activations(pip)

                # ── Risk-Free SL check ────────────────────────────
                self.sig.log_line.emit("__CHECK_RF__", "RF")

                # ── Follow moved objects ──────────────────────────
                if self.follow_enabled:
                    for obj in trader:
                        n = obj.name
                        if n not in self.drawn or self.drawn[n] in ("INVALID", "WRONG_SYMBOL"):
                            continue
                        stored = self.drawn[n]
                        if obj.is_hline and isinstance(stored, float):
                            if abs(obj.price1 - stored) > 0.000001:
                                new_src = obj.price1
                                self.log(
                                    f"↕️  [{n[:25]}] moved {stored:.5f}→{new_src:.5f} — redrawing")
                                self._draw_hline_levels(n, new_src, pip)
                                self.drawn[n] = new_src
                                if n in source_registry:
                                    source_registry[n]["src"] = new_src
                                    source_registry[n]["triggered"] = False
                                    source_registry[n]["just_triggered_t"] = 0
                                    prev_t_now = candle.get("PREV_T", 0)
                                    source_registry[n]["registered_at_candle"] = prev_t_now
                                    source_registry[n]["last_prev_t"] = prev_t_now

                self.prev_names = self.prev_names | cur
                self._stop.wait(min(SCAN_INTERVAL_SEC, 1))

            except Exception as e:
                import traceback as _tb
                self.log(f"💥 Watcher error: {type(e).__name__}: {e}", "ERROR")
                for line in _tb.format_exc().strip().splitlines():
                    self.log(f"   {line}", "ERROR")
                self._stop.wait(min(SCAN_INTERVAL_SEC, 1))

        write_commands(["DELETE_PREFIX|TB_"], symbol=self.symbol)
        mt5.shutdown()
        self.sig.status.emit("⚫  Stopped")
        self.log("Bot stopped — all bot lines cleared")
