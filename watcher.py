"""
watcher.py — WatcherWorker thread
Runs in background: reads EA file, detects line touches, places orders, manages Phase 3 cascades.
"""
import threading
from datetime import datetime
import MetaTrader5 as mt5

from config import (
    WATCH_SYMBOL, SCAN_INTERVAL_SEC, MAGIC_NUMBER, PIP_STEP, LOT_SIZE,
)
from core.line_drawer  import get_pip_size, write_commands
from core.order_manager import place_level_orders, cancel_all_tb_orders
from core import chart_watcher as cw


class WatcherWorker(threading.Thread):
    def __init__(self, sig, pip_step: float, symbol: str = WATCH_SYMBOL,
                 tp_pips: float = 0.0, spawn_on: str = "L2 and L3",
                 lot_size: float = LOT_SIZE):
        super().__init__(daemon=True)
        self.sig            = sig
        self.pip_step       = pip_step
        self.symbol         = symbol
        self.tp_pips        = tp_pips
        self.spawn_on       = spawn_on
        self.lot_size       = lot_size
        self._stop          = threading.Event()
        self.prev_names     = set()
        self.drawn          = {}
        self.follow_enabled = True
        self.orders_placed  = set()
        self._last_direction = "—"
        # Phase 3
        self.pending_tracker = {}   # ticket → order_info
        self.spawn_rounds    = 0
        self.spawned_keys    = set()
        self._last_prev_t    = 0    # shared with _check_phase3_activations
        # exposed to GUI
        self.source_registry = {}   # set in run()

    def stop(self): self._stop.set()

    def log(self, msg, lvl="INFO"):
        self.sig.log_line.emit(f"{datetime.now().strftime('%H:%M:%S')}  {msg}", lvl)

    # ── Chart drawing ─────────────────────────────────────────────

    @staticmethod
    def _obj_prefix(name: str) -> str:
        import hashlib
        return f"TB_{hashlib.md5(name.encode()).hexdigest()[:6].upper()}_"

    def _draw_hline_levels(self, name, price, pip_size):
        prefix  = self._obj_prefix(name)
        step    = self.pip_step * pip_size
        l3_buy  = round(price + step * 3, 5)
        l3_sell = round(price - step * 3, 5)
        write_commands([
            f"DELETE_PREFIX|{prefix}",
            f"DRAW_HLINE|{prefix}SRC|{price:.5f}|16744995|2|0",
            f"DRAW_HLINE|{prefix}L3B|{l3_buy:.5f}|56702|1|1",
            f"DRAW_HLINE|{prefix}L3S|{l3_sell:.5f}|16728160|1|1",
        ], symbol=self.symbol)
        return step

    # ── Order placement ───────────────────────────────────────────

    def _place_orders_for_source(self, source_price: float, pip_size: float, generation: int = 0):
        try:
            results = place_level_orders(
                source_price, pip_size, self.pip_step, self.symbol,
                generation, tp_pips=self.tp_pips, lot_size=self.lot_size)
            ok     = sum(1 for r in results if r["ok"])
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
                self.log(f"📋  G{generation}: {ok}/6 placed @ {source_price:.5f} | step={step:.5f}")
                for r in results:
                    o = r["order"]
                    icon = "🟢" if o["type"] == "BUY_STOP" else "🔴"
                    self.log(f"   {icon} G{generation}-L{o['level']} {o['type']:10s}"
                             f" entry={o['entry']:.5f} sl={o['sl']:.5f} tp={o['tp']:.5f}")
            else:
                reasons = set(r.get("reason", "?") for r in failed)
                self.log(f"⚠️  G{generation}: {ok}/6 placed | failed: {', '.join(reasons)}", "WARN")
                for r in results:
                    o = r["order"]
                    icon   = "🟢" if o["type"] == "BUY_STOP" else "🔴"
                    status = "✅" if r["ok"] else f"❌({r.get('reason','?')[:20]})"
                    self.log(f"   {icon} {status} {o['type']:10s} entry={o['entry']:.5f} sl={o['sl']:.5f}")
        except Exception as e:
            self.log(f"💥  Order error: {type(e).__name__}: {e}", "ERROR")

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

        # Log every activation
        for ticket, info in list(triggered.items()):
            gen, level = info["generation"], info["level"]
            entry, sl, tp = info["entry"], info["sl"], info["tp"]
            direction = info["direction"]
            icon = "🟢 BUY" if "BUY" in direction else "🔴 SELL"
            self.log(f"⚡  {icon} G{gen}-L{level} ACTIVATED | "
                     f"entry={entry:.5f} sl={sl:.5f} tp={tp:.5f} | ticket=#{ticket}", "NEW")

            # Arm pullback when L3 hits
            if level == 3:
                for reg in self.source_registry.values():
                    if abs(reg.get("src", 0) - info.get("source", entry)) < 0.000001:
                        reg["l3_activated"]          = True
                        reg["l3_activated_candle_t"] = self._last_prev_t
                        reg["_last_candle_counted"]  = self._last_prev_t
                        reg["candles_since_l3"]      = 0
                        reg["price_was_away"]        = False
                        self.log(f"   ✅ L3 hit — pullback armed (needs 2+ candles away from source)")

            del self.pending_tracker[ticket]

        # Spawn: max one per scan, cooldown 2s
        last_spawn = getattr(self, "_last_spawn_time", 0)
        if _t.time() - last_spawn < 2.0:
            return

        spawn_lvls = []
        if "L2" in self.spawn_on: spawn_lvls.append(2)
        if "L3" in self.spawn_on: spawn_lvls.append(3)

        candidates = sorted(triggered.items(),
                            key=lambda kv: (-kv[1]["level"], kv[1]["generation"]))

        for ticket, info in candidates:
            level, gen   = info["level"], info["generation"]
            entry, direction = info["entry"], info["direction"]

            if level not in spawn_lvls: continue
            if self.spawn_rounds >= 9:
                self.log("⛔  Max 9 rounds reached — no more spawning"); break

            spawn_key = f"{entry:.5f}_G{gen+1}_{direction[:4]}"
            if spawn_key in self.spawned_keys:
                self.log(f"ℹ️  Already spawned from {entry:.5f} {direction[:4]} — skipping")
                continue

            self.spawned_keys.add(spawn_key)
            self.spawn_rounds += 1
            self._last_spawn_time = _t.time()
            new_gen = gen + 1
            self.log(f"🔄  Phase 3 round {self.spawn_rounds}/9 — "
                     f"G{gen}-L{level} {direction} @ {entry:.5f} → "
                     f"new source G{new_gen} @ {entry:.5f}", "NEW")
            self._draw_hline_levels(f"TB_SPAWN_G{new_gen}_R{self.spawn_rounds}", entry, pip)
            self._place_orders_for_source(entry, pip, generation=new_gen)
            self._log_position_map()
            break  # one spawn per cycle

    def _log_position_map(self):
        sep = "─" * 55
        self.log(sep)
        orders = mt5.orders_get(symbol=self.symbol)
        bot_orders = [o for o in (orders or []) if o.magic == MAGIC_NUMBER]
        if bot_orders:
            self.log(f"📋 Pending orders ({len(bot_orders)}):")
            for o in sorted(bot_orders, key=lambda x: x.price_open):
                t = "BUY_STOP" if o.type == 2 else "SELL_STOP"
                self.log(f"   #{o.ticket} {t:10s} entry={o.price_open:.5f} "
                         f"sl={o.sl:.5f} tp={o.tp:.5f} | {getattr(o,'comment','')}")
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
        """Check and fire pullback re-entry for a triggered source."""
        if not reg.get("l3_activated", False):
            return
        src       = reg["src"]
        prev_t    = candle.get("PREV_T", 0)
        prev_h    = candle.get("PREV_H", 0.0)
        prev_l    = candle.get("PREV_L", 0.0)
        prev_o    = candle.get("PREV_O", 0.0)
        l3_t      = reg.get("l3_activated_candle_t", 0)
        cnt       = reg.get("candles_since_l3", 0)

        # Count new candles since L3 (only count each PREV_T once, and only after L3)
        if prev_t > reg.get("_last_candle_counted", 0) and prev_t > l3_t:
            reg["_last_candle_counted"] = prev_t
            cnt += 1
            reg["candles_since_l3"] = cnt

        if cnt < 2:
            return  # wait for at least 2 full candles after L3

        if prev_h <= 0 or prev_l <= 0:
            return

        # Track whether price moved away from the line
        if prev_l > src or prev_h < src:
            reg["price_was_away"] = True
        elif reg.get("price_was_away", False):
            last_rb = reg.get("last_pullback_t", 0)
            if prev_t > last_rb:
                reg["last_pullback_t"]   = prev_t
                reg["price_was_away"]    = False
                reg["candles_since_l3"]  = 0
                side = "from above" if prev_o > src else "from below"

                # Cancel only G0 pending orders before placing fresh round
                pending = mt5.orders_get(symbol=self.symbol) or []
                cancelled = 0
                for o in pending:
                    cmt = getattr(o, "comment", "")
                    if o.magic == MAGIC_NUMBER and "_G0L" in str(cmt):
                        r = mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket})
                        if r and r.retcode == 10009:
                            cancelled += 1
                if cancelled:
                    self.log(f"🗑️  Cancelled {cancelled} G0 pending orders before pullback")

                self.log(f"🔁  Pullback [{n[:20]}] @ {src:.5f} {side} | placing fresh G0 round", "NEW")
                self._place_orders_for_source(src, pip, generation=0)

    # ── Main loop ─────────────────────────────────────────────────

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
            self.log(f"📐  Min stop distance: {min_dist:.5f} = {min_pips:.1f} pips")
        else:
            self.log(f"✅  Connected | {self.symbol} | pip={pip:.5f}")

        self.sig.status.emit("🟢  Running")
        source_registry = {}
        self.source_registry = source_registry

        import os as _os, time as _time

        while not self._stop.is_set():
            try:
                path = cw.find_objects_file(self.symbol)

                # Log new file path once
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
                                    self.log(f"⚠️  File symbol '{file_sym}' ≠ bot symbol '{self.symbol}'", "WARN")
                                break
                    except Exception:
                        pass

                if not path:
                    self.sig.status.emit("⏳  Waiting for EA…")
                    self._stop.wait(min(SCAN_INTERVAL_SEC, 1)); continue

                # Stale file check
                try: file_age = _time.time() - _os.path.getmtime(path)
                except: file_age = 0
                if file_age > 15:
                    if not getattr(self, "_stale_warned", False) or int(file_age) % 30 < 1:
                        self._stale_warned = True
                        self.log(f"⚠️  EA file {file_age:.0f}s old — EA not running on {self.symbol} chart", "WARN")
                    self.sig.status.emit(f"⚠️  EA stopped ({file_age:.0f}s)")
                    self._stop.wait(min(SCAN_INTERVAL_SEC, 1)); continue
                else:
                    if getattr(self, "_stale_warned", False):
                        self.log("✅  EA writing again — resuming")
                    self._stale_warned = False

                # Parse file
                parsed = cw.parse_objects_file(path)
                if len(parsed) == 4:
                    trader, auto, ea_sym, candle = parsed
                elif len(parsed) == 3:
                    trader, auto, ea_sym, candle = parsed[0], parsed[1], parsed[2], {}
                else:
                    trader, auto, ea_sym, candle = parsed[0], parsed[1], None, {}

                if ea_sym:
                    self.sig.log_line.emit(f"__EA_SYM__{ea_sym}", "EA")

                if ea_sym and ea_sym != self.symbol:
                    if ea_sym != getattr(self, "_last_ea_warn", None):
                        self._last_ea_warn = ea_sym
                        self.log(f"⚠️  EA on '{ea_sym}' chart — not '{self.symbol}'", "WARN")
                    self._stop.wait(min(SCAN_INTERVAL_SEC, 1)); continue

                self.sig.new_objects.emit(trader, auto)

                # Periodic status log (every 30 scans)
                self._dbg_count = getattr(self, "_dbg_count", 0) + 1
                if self._dbg_count % 30 == 0:
                    waiting = [f"[{k[:15]}]={v['src']:.5f}"
                               for k, v in source_registry.items() if not v.get("triggered")]
                    if waiting:
                        bid = candle.get("BID", 0)
                        ch  = candle.get("CANDLE_H", 0)
                        cl  = candle.get("CANDLE_L", 0)
                        try:
                            age = int(_time.time() - _os.path.getmtime(path))
                            age_s = f" | file_age={age}s"
                        except: age_s = ""
                        self.log(f"⏳  Watching: {', '.join(waiting)} | bid={bid:.5f} H={ch:.5f} L={cl:.5f}{age_s}")

                # Send candle data to GUI (for RF check)
                self.sig.log_line.emit(f"__CANDLE__{repr(candle)}", "RF")

                cur = {o.name for o in trader}
                tick = mt5.symbol_info_tick(self.symbol)
                current_price = (tick.bid + tick.ask) / 2 if tick else 0.0

                # ── Candle data ──────────────────────────────────
                cur_candle_t = candle.get("CANDLE_T", 0)
                cur_h  = candle.get("CANDLE_H", current_price)
                cur_l  = candle.get("CANDLE_L", current_price)
                cur_c  = candle.get("CANDLE_C", current_price)
                cur_o  = candle.get("CANDLE_O", current_price)
                prev_h = candle.get("PREV_H", 0.0)
                prev_l = candle.get("PREV_L", 0.0)
                prev_c = candle.get("PREV_C", 0.0)
                prev_o = candle.get("PREV_O", 0.0)
                self._last_prev_t = candle.get("PREV_T", 0)

                # ── Detect new objects ───────────────────────────
                for n in cur - self.prev_names:
                    if n in self.drawn:
                        continue
                    obj = next(o for o in trader if o.name == n)

                    # Skip wrong-symbol artifacts
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
                        source_registry[n] = {
                            "src": src, "triggered": False, "gen": 0,
                            "registered_at_candle": cur_candle_t, "last_prev_t": 0,
                        }
                        self.log(f"🆕  HLINE [{n[:25]}] @ {src:.5f} | 3+3 levels drawn | "
                                 f"waiting for NEXT candle to touch line")

                    elif obj.is_rectangle:
                        if not obj.rect_valid:
                            self.drawn[n] = "INVALID"
                            self.log(f"⚠️  [{n[:25]}] rectangle has zero height — skipping")
                            continue
                        center = round((obj.rect_top + obj.rect_bottom) / 2, 5)
                        self._draw_hline_levels(n, center, pip)
                        self.drawn[n] = center
                        source_registry[n] = {
                            "src": center, "triggered": False, "gen": 0,
                            "registered_at_candle": cur_candle_t, "last_prev_t": 0,
                        }
                        self.log(f"🆕  RECT [{n[:25]}] center={center:.5f} | waiting for touch")

                # ── Touch detection & pullback ───────────────────
                for n, reg in list(source_registry.items()):
                    if reg["triggered"]:
                        self._check_pullback(n, reg, candle, pip)
                        continue

                    src           = reg["src"]
                    registered_at = reg.get("registered_at_candle", 0)
                    touched       = False
                    touch_h = touch_l = touch_c = touch_o = 0.0

                    # Current forming candle (skip same candle as registration)
                    if cur_candle_t != registered_at and cur_h > 0:
                        if cur_l <= src <= cur_h:
                            touched = True
                            touch_h, touch_l, touch_c, touch_o = cur_h, cur_l, cur_c, cur_o

                    # Previous closed candle
                    if not touched and prev_h > 0:
                        prev_t_val   = candle.get("PREV_T", 0)
                        last_checked = reg.get("last_prev_t", 0)
                        if prev_t_val > last_checked and prev_t_val > registered_at:
                            reg["last_prev_t"] = prev_t_val
                            if prev_l <= src <= prev_h:
                                touched = True
                                touch_h, touch_l, touch_c, touch_o = prev_h, prev_l, prev_c, prev_o

                    if touched:
                        reg["triggered"]      = True
                        reg["last_touch_t"]   = candle.get("PREV_T", 0)
                        reg["last_pullback_t"] = candle.get("PREV_T", 0)
                        side      = "from above" if touch_o > src else "from below"
                        direction = "BUY" if touch_c > src else "SELL"
                        self._last_direction  = direction
                        icon = "🟢" if direction == "BUY" else "🔴"
                        self.log(f"🎯  [{n[:20]}] touched @ {src:.5f} {side} | "
                                 f"C={touch_c:.5f} → {icon} {direction} bias | placing orders", "NEW")
                        self._place_orders_for_source(src, pip, generation=reg["gen"])
                        reg["cancel_opposite"] = direction

                # ── Cancel opposite-side orders ──────────────────
                for n, reg in list(source_registry.items()):
                    if "cancel_opposite" not in reg:
                        continue
                    direction = reg.pop("cancel_opposite")
                    pending = mt5.orders_get(symbol=self.symbol) or []
                    cancelled = 0
                    for o in pending:
                        if o.magic != MAGIC_NUMBER: continue
                        is_buy_stop  = o.type == 2
                        is_sell_stop = o.type == 4
                        should = ((direction == "BUY"  and is_sell_stop) or
                                  (direction == "SELL" and is_buy_stop))
                        if should:
                            r = mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket})
                            if r and r.retcode == mt5.TRADE_RETCODE_DONE:
                                cancelled += 1
                    if cancelled:
                        icon = "🟢" if direction == "BUY" else "🔴"
                        self.log(f"🗑️  {icon} {direction} bias: cancelled {cancelled} opposite-side orders")

                # ── Phase 3 ──────────────────────────────────────
                self._check_phase3_activations(pip)

                # ── Risk-Free SL check (via GUI signal) ──────────
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
                                self.log(f"↕️  [{n[:25]}] moved {stored:.5f}→{new_src:.5f} — redrawing")
                                self._draw_hline_levels(n, new_src, pip)
                                self.drawn[n] = new_src
                                if n in source_registry:
                                    source_registry[n]["src"]                    = new_src
                                    source_registry[n]["triggered"]              = False
                                    source_registry[n]["registered_at_candle"]  = cur_candle_t
                                    source_registry[n]["last_prev_t"]            = 0

                self.prev_names = self.prev_names | cur
                self._stop.wait(min(SCAN_INTERVAL_SEC, 1))

            except Exception as e:
                import traceback as _tb
                self.log(f"💥 Watcher error: {type(e).__name__}: {e}", "ERROR")
                for line in _tb.format_exc().strip().splitlines():
                    self.log(f"   {line}", "ERROR")
                self._stop.wait(min(SCAN_INTERVAL_SEC, 1))

        # Cleanup on stop
        write_commands(["DELETE_PREFIX|TB_"], symbol=self.symbol)
        mt5.shutdown()
        self.sig.status.emit("⚫  Stopped")
        self.log("Bot stopped — all bot lines cleared")