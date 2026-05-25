"""
╔══════════════════════════════════════════════════════════════════╗
║         TraderBot v1 — GUI  (with Backtest Tab)                 ║
║  pip install PyQt5   →   python gui.py                          ║
╚══════════════════════════════════════════════════════════════════╝
"""
import sys, os, threading
from datetime import datetime
from typing import Optional

import MetaTrader5 as mt5
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QGroupBox, QTextEdit, QFrame,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QDoubleSpinBox, QSpinBox, QComboBox, QSplitter, QSizePolicy,
    QProgressBar, QCheckBox, QSlider, QScrollArea,
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt5.QtGui import QColor, QTextCursor, QFont

os.makedirs("logs", exist_ok=True)
from config import (
    MT5_LOGIN, MT5_PASSWORD, MT5_SERVER,
    WATCH_SYMBOL, SCAN_INTERVAL_SEC,
    AUTO_OBJECT_PREFIXES, PIP_STEP, BOT_LINE_PREFIX,
    LOT_SIZE, TP_RR_RATIO, MAGIC_NUMBER,
)
from core.line_drawer  import draw_level_lines, clear_level_lines, get_pip_size, write_commands, STYLE_DASH, CLR_ABOVE_1, CLR_ABOVE_2, CLR_ABOVE_3, CLR_BELOW_1, CLR_BELOW_2, CLR_BELOW_3
from core.order_manager import place_level_orders, send_orders, cancel_all_tb_orders
from core.backtest_engine import run_backtest
from core import chart_watcher as cw
from chart_widget import CandleChartWidget

# ── Palette ──────────────────────────────────────────────────────
C = {
    "bg":"#0D1117","panel":"#161B22","card":"#1C2333","input":"#141D2E",
    "border":"#2A3550","border_hi":"#4A6090",
    "txt":"#E8EDF5","txt2":"#8B9BB4","txt3":"#4A5568",
    "gold":"#F5A623","green":"#00D97E","green_dk":"#003D22",
    "red":"#FF4560","red_dk":"#3D0015","orange":"#FF8C00",
    "cyan":"#00BCD4","blue":"#2979FF","purple":"#B388FF",
}

SS = f"""
QWidget      {{ background:{C['bg']};color:{C['txt']};font-family:'Segoe UI';font-size:12px; }}
QMainWindow  {{ background:{C['bg']}; }}
QLabel       {{ background:transparent; }}
QGroupBox    {{ background:{C['card']};border:1px solid {C['border']};border-radius:6px;
                margin-top:14px;padding:8px 6px 6px 6px;
                font-size:10px;font-weight:bold;color:{C['txt2']}; }}
QGroupBox::title {{ subcontrol-origin:margin;left:10px;padding:0 4px; }}
QPushButton  {{ background:{C['card']};color:{C['txt']};border:1px solid {C['border']};
                border-radius:5px;padding:6px 14px; }}
QPushButton:hover   {{ background:{C['border']};border-color:{C['border_hi']}; }}
QPushButton:pressed {{ background:{C['bg']}; }}
QPushButton:disabled{{ color:{C['txt3']};border-color:{C['card']}; }}
QPushButton#btn_start {{ background:{C['green_dk']};color:{C['green']};
    border:1px solid {C['green']};font-weight:bold;font-size:13px; }}
QPushButton#btn_start:hover {{ background:{C['green']};color:#000; }}
QPushButton#btn_stop {{ background:{C['red_dk']};color:{C['red']};
    border:1px solid {C['red']};font-weight:bold;font-size:13px; }}
QPushButton#btn_stop:hover {{ background:{C['red']};color:#fff; }}
QPushButton#btn_orders {{ background:#1A2A0A;color:{C['orange']};
    border:1px solid {C['orange']};font-weight:bold; }}
QPushButton#btn_orders:hover {{ background:{C['orange']};color:#000; }}
QPushButton#btn_cancel {{ background:{C['red_dk']};color:{C['red']};border:1px solid {C['red']}; }}
QPushButton#btn_cancel:hover {{ background:{C['red']};color:#fff; }}
QPushButton#btn_bt {{ background:#0A1A2A;color:{C['cyan']};
    border:1px solid {C['cyan']};font-weight:bold; }}
QPushButton#btn_bt:hover {{ background:{C['cyan']};color:#000; }}
QTextEdit    {{ background:{C['bg']};color:{C['txt']};border:1px solid {C['border']};
                border-radius:4px;font-family:'Consolas';font-size:11px; }}
QTableWidget {{ background:{C['bg']};color:{C['txt']};border:1px solid {C['border']};
                border-radius:4px;gridline-color:{C['border']};
                alternate-background-color:{C['panel']}; }}
QTableWidget::item {{ padding:4px 8px; }}
QTableWidget::item:selected {{ background:{C['border']}; }}
QHeaderView::section {{ background:{C['card']};color:{C['txt2']};padding:5px 8px;
    border:none;border-right:1px solid {C['border']};
    border-bottom:1px solid {C['border']};font-size:10px;font-weight:bold; }}
QTabWidget::pane {{ background:{C['panel']};border:1px solid {C['border']};border-radius:4px; }}
QTabBar::tab {{ background:{C['card']};color:{C['txt2']};padding:6px 18px;
    border:1px solid {C['border']};border-bottom:none;
    border-radius:4px 4px 0 0;margin-right:2px; }}
QTabBar::tab:selected {{ background:{C['panel']};color:{C['gold']};border-bottom:2px solid {C['gold']}; }}
QTabBar::tab:hover:!selected {{ color:{C['txt']}; }}
QDoubleSpinBox,QSpinBox,QComboBox {{ background:{C['input']};color:{C['txt']};
    border:1px solid {C['border']};border-radius:4px;padding:4px 7px;min-height:26px; }}
QDoubleSpinBox::up-button,QDoubleSpinBox::down-button,
QSpinBox::up-button,QSpinBox::down-button {{ background:{C['border']};border:none;width:16px; }}
QComboBox::drop-down {{ border:none;width:20px; }}
QComboBox QAbstractItemView {{ background:{C['card']};color:{C['txt']};
    selection-background-color:{C['border']}; }}
QProgressBar {{ background:{C['bg']};border:1px solid {C['border']};border-radius:4px;
                text-align:center;color:{C['txt']};font-size:10px; }}
QProgressBar::chunk {{ background:{C['cyan']};border-radius:3px; }}
QFrame[frameShape="4"],QFrame[frameShape="5"] {{ color:{C['border']}; }}
QSplitter::handle {{ background:{C['border']}; }}
"""


# ── Watcher signals & worker ──────────────────────────────────────
class Sig(QObject):
    new_objects = pyqtSignal(list, list)
    status      = pyqtSignal(str)
    log_line    = pyqtSignal(str, str)
    bt_done     = pyqtSignal()


class WatcherWorker(threading.Thread):
    def __init__(self, sig: Sig, pip_step: float, symbol: str = WATCH_SYMBOL,
                 tp_pips: float = 0.0, spawn_on: str = "L2 and L3"):
        super().__init__(daemon=True)
        self.sig       = sig
        self.pip_step  = pip_step
        self.symbol    = symbol
        self._stop     = threading.Event()
        self.prev_names: set  = set()
        self.drawn:     dict  = {}
        self.follow_enabled: bool = True
        self.tp_pips      = tp_pips    # 0 = RR ratio, >0 = fixed pip TP from L3
        self.spawn_on     = spawn_on   # "L2 only" / "L3 only" / "L2 and L3"
        self.orders_placed: set  = set()
        # Phase 3: track pending orders by ticket → {level, gen, src, direction, entry}
        self.pending_tracker: dict = {}   # ticket → order_info
        self.spawn_rounds:    int  = 0    # how many Phase 3 spawns happened

    def stop(self):  self._stop.set()

    def log(self, msg, lvl="INFO"):
        self.sig.log_line.emit(f"{datetime.now().strftime('%H:%M:%S')}  {msg}", lvl)

    @staticmethod
    def _obj_prefix(name: str) -> str:
        import hashlib
        h = hashlib.md5(name.encode()).hexdigest()[:6].upper()
        return f"TB_{h}_"

    def _draw_hline_levels(self, name, price, pip_size):
        prefix = self._obj_prefix(name)
        step   = self.pip_step * pip_size
        cmds   = [f"DELETE_PREFIX|{prefix}"]
        for i, clr in enumerate([CLR_ABOVE_1, CLR_ABOVE_2, CLR_ABOVE_3], 1):
            cmds.append(f"DRAW_HLINE|{prefix}A{i}|{price + step*i:.5f}|{clr}|1|{STYLE_DASH}")
        for i, clr in enumerate([CLR_BELOW_1, CLR_BELOW_2, CLR_BELOW_3], 1):
            cmds.append(f"DRAW_HLINE|{prefix}B{i}|{price - step*i:.5f}|{clr}|1|{STYLE_DASH}")
        write_commands(cmds, symbol=self.symbol)
        return step

    def _draw_rect_levels(self, name, top, bottom, pip_size):
        prefix = self._obj_prefix(name)
        step   = self.pip_step * pip_size
        cmds   = [f"DELETE_PREFIX|{prefix}"]
        for i, clr in enumerate([CLR_ABOVE_1, CLR_ABOVE_2, CLR_ABOVE_3], 1):
            cmds.append(f"DRAW_HLINE|{prefix}A{i}|{top    + step*i:.5f}|{clr}|1|{STYLE_DASH}")
        for i, clr in enumerate([CLR_BELOW_1, CLR_BELOW_2, CLR_BELOW_3], 1):
            cmds.append(f"DRAW_HLINE|{prefix}B{i}|{bottom - step*i:.5f}|{clr}|1|{STYLE_DASH}")
        write_commands(cmds, symbol=self.symbol)
        return step

    def _delete_obj_levels(self, name):
        write_commands([f"DELETE_PREFIX|{self._obj_prefix(name)}"], symbol=self.symbol)

    def _log_position_map(self, _mt5=None):
        """Log a clear summary of all active positions and pending orders."""
        import MetaTrader5 as __mt5
        mt = _mt5 or __mt5
        sep = "─" * 55
        self.log(sep)
        # Pending orders
        orders = mt.orders_get(symbol=self.symbol)
        bot_orders = [o for o in (orders or []) if o.magic == MAGIC_NUMBER]
        if bot_orders:
            self.log(f"📋 Pending orders ({len(bot_orders)}):")
            for o in sorted(bot_orders, key=lambda x: x.price_open):
                t = "BUY_STOP" if o.type == 2 else "SELL_STOP"
                comment = getattr(o, 'comment', '')
                self.log(f"   #{o.ticket} {t:10s} entry={o.price_open:.5f} sl={o.sl:.5f} tp={o.tp:.5f} | {comment}")
        # Active positions
        positions = mt.positions_get(symbol=self.symbol)
        bot_pos = [p for p in (positions or []) if p.magic == MAGIC_NUMBER]
        if bot_pos:
            self.log(f"📊 Active positions ({len(bot_pos)}):")
            for p in sorted(bot_pos, key=lambda x: x.price_open):
                t = "BUY " if p.type == 0 else "SELL"
                pnl = p.profit
                self.log(f"   #{p.ticket} {t} entry={p.price_open:.5f} sl={p.sl:.5f} tp={p.tp:.5f} | PnL={pnl:+.2f}")
        if not bot_orders and not bot_pos:
            self.log("   (no bot orders or positions)")
        self.log(f"   Rounds spawned: {self.spawn_rounds}/9 | Tracked pending: {len(self.pending_tracker)}")
        self.log(sep)

    def _place_orders_for_source(self, source_price: float, pip_size: float,
                                  generation: int = 0):
        """Place 6 pending orders and track tickets for Phase 3 monitoring."""
        from core.order_manager import place_level_orders
        try:
            results = place_level_orders(source_price, pip_size,
                                          self.pip_step, self.symbol, generation,
                                          tp_pips=self.tp_pips)
            ok = sum(1 for r in results if r["ok"])
            failed = [r for r in results if not r["ok"]]

            # Track placed orders for Phase 3 activation monitoring
            for r in results:
                if r["ok"] and r.get("ticket"):
                    o = r["order"]
                    self.pending_tracker[r["ticket"]] = {
                        "level":      o["level"],
                        "generation": generation,
                        "source":     source_price,
                        "direction":  o["type"],
                        "entry":      o["entry"],
                        "sl":         o["sl"],
                        "tp":         o["tp"],
                    }

            step = self.pip_step * pip_size
            if ok == len(results):
                self.log(f"📋  G{generation}: {ok}/6 placed @ {source_price:.5f} | step={step:.5f}")
                # Show summary: levels above and below
                for r in results:
                    o = r["order"]
                    side = "🟢" if o["type"] == "BUY_STOP" else "🔴"
                    self.log(f"   {side} G{generation}-L{o['level']} {o['type']:10s} entry={o['entry']:.5f} sl={o['sl']:.5f} tp={o['tp']:.5f}")
            else:
                reasons = set(r.get('reason','?') for r in failed)
                self.log(f"⚠️  G{generation}: {ok}/6 placed | failed: {', '.join(reasons)}", "WARN")
                for r in results:
                    o = r["order"]; side = "🟢" if o["type"] == "BUY_STOP" else "🔴"
                    status = "✅" if r["ok"] else f"❌({r.get('reason','?')[:20]})"
                    self.log(f"   {side} {status} {o['type']:10s} entry={o['entry']:.5f} sl={o['sl']:.5f}")
                if "Market closed" in reasons:
                    self.log(f"💡  Market closed — orders will activate when market opens")
        except Exception as e:
            self.log(f"💥  Order error: {type(e).__name__}: {e}", "ERROR")

    def _check_phase3_activations(self, pip: float):
        """
        Check if any tracked L2/L3 pending orders became active (triggered).
        When L2 or L3 is triggered → spawn new source at that entry price.
        Max 9 rounds total (night range constraint).
        """
        if not self.pending_tracker or self.spawn_rounds >= 9:
            return
        import MetaTrader5 as _mt5
        # Get current pending orders from MT5
        still_pending_tickets = set()
        pending = _mt5.orders_get(symbol=self.symbol)
        if pending:
            for o in pending:
                if o.magic == MAGIC_NUMBER:
                    still_pending_tickets.add(o.ticket)

        # Get open positions to see what got triggered
        positions = _mt5.positions_get(symbol=self.symbol)
        active_tickets = set()
        if positions:
            for p in positions:
                if p.magic == MAGIC_NUMBER:
                    # Find by price matching since ticket changes on activation
                    active_tickets.add(p.ticket)

        # Find tickets that were pending but are now gone (triggered or cancelled)
        triggered = {t: info for t, info in self.pending_tracker.items()
                     if t not in still_pending_tickets}

        for ticket, info in list(triggered.items()):
            level     = info["level"]
            gen       = info["generation"]
            entry     = info["entry"]
            sl        = info["sl"]
            tp        = info["tp"]
            direction = info["direction"]
            side      = "🟢 BUY" if "BUY" in direction else "🔴 SELL"

            self.log(f"⚡  {side} G{gen}-L{level} ACTIVATED | entry={entry:.5f} sl={sl:.5f} tp={tp:.5f} | ticket=#{ticket}", "NEW")

            # Phase 3: L2 and L3 spawn new sources (max 9 rounds, max gen 2)
            # Dynamic spawn level from GUI
            spawn_lvls = []
            if "L2" in self.spawn_on: spawn_lvls.append(2)
            if "L3" in self.spawn_on: spawn_lvls.append(3)
            if level in spawn_lvls and gen < 2 and self.spawn_rounds < 9:
                # Prevent duplicate: check if we already spawned from this exact entry+gen
                spawn_key = f"{entry:.5f}_G{gen+1}"
                if spawn_key in getattr(self, "spawned_keys", set()):
                    self.log(f"ℹ️  Already spawned G{gen+1} @ {entry:.5f} — skipping duplicate")
                else:
                    if not hasattr(self, "spawned_keys"):
                        self.spawned_keys = set()
                    self.spawned_keys.add(spawn_key)
                    self.spawn_rounds += 1
                    new_gen = gen + 1
                    self.log(
                        f"🔄  Phase 3 round {self.spawn_rounds}/9 — "
                        f"G{gen}-L{level} {direction} triggered @ {entry:.5f} → "
                        f"new source G{new_gen} @ {entry:.5f}", "NEW")
                    spawn_name = f"TB_SPAWN_G{new_gen}_R{self.spawn_rounds}"
                    self._draw_hline_levels(spawn_name, entry, pip)
                    self._place_orders_for_source(entry, pip, generation=new_gen)
                    self._log_position_map(_mt5)
            elif level == 1:
                self.log(f"ℹ️  G{gen}-L1 activated — no spawn (L1 does not spawn new source)")
            elif self.spawn_rounds >= 9:
                self.log(f"⛔  Max 9 rounds reached — no more spawning")
            elif gen >= 2:
                self.log(f"ℹ️  G{gen}-L{level} activated — max generation reached (gen 2)")

            del self.pending_tracker[ticket]

    def run(self):
        if not cw.connect_mt5():
            self.sig.status.emit("❌  MT5 connection failed"); return
        pip = get_pip_size(self.symbol)

        # Log minimum stop distance so user knows if pip_step is too small
        import MetaTrader5 as _mt5
        _mt5.symbol_select(self.symbol, True)
        _info = _mt5.symbol_info(self.symbol)
        if _info:
            min_dist = _info.trade_stops_level * _info.point
            min_pips = min_dist / pip if pip > 0 else 0
            self.log(f"✅  Connected | {self.symbol} | pip={pip:.5f} | step={self.pip_step} pips")
            self.log(f"📐  Min stop distance: {min_dist:.5f} = {min_pips:.1f} pips  (pip_step must be > {min_pips:.1f})")
            if self.pip_step * pip <= min_dist:
                self.log(f"⚠️  pip_step={self.pip_step} is too small! L1 SL will fail. Increase to >{min_pips:.0f} pips.", "WARN")
        else:
            self.log(f"✅  Connected | {self.symbol} | pip={pip:.5f} | step={self.pip_step} pips")

        self.sig.status.emit("🟢  Running")

        # source_registry: name → {"src": float, "triggered": bool, "gen": int}
        # Orders are placed ONLY when price touches the source line
        source_registry = {}

        while not self._stop.is_set():
          try:
            path = cw.find_objects_file(self.symbol)
            if not path:
                self.sig.status.emit("⏳  Waiting for EA…")
                self._stop.wait(SCAN_INTERVAL_SEC); continue

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
                    self.log(f"⚠️  EA is on {ea_sym} chart — not {self.symbol}. Move EA or change symbol.", "WARN")
                self._stop.wait(SCAN_INTERVAL_SEC)
                continue

            self.sig.new_objects.emit(trader, auto)
            cur = {o.name for o in trader}

            # Get current price once per scan
            tick = mt5.symbol_info_tick(self.symbol)
            current_price = (tick.bid + tick.ask) / 2 if tick else 0.0

            # ── DETECT NEW OBJECTS ─────────────────────────────────
            for n in cur - self.prev_names:
                if n in self.drawn:
                    continue  # already processed

                obj = next(o for o in trader if o.name == n)

                # Skip wrong-symbol artifacts (price far from current)
                if current_price > 0 and obj.price1 > 0:
                    ratio = obj.price1 / current_price
                    if ratio < 0.5 or ratio > 2.0:
                        self.drawn[n] = "WRONG_SYMBOL"
                        self.log(f"⏭  [{n[:25]}] @ {obj.price1:.5f} skipped (current={current_price:.5f}, ratio={ratio:.2f})")
                        continue

                if obj.is_hline:
                    src = obj.price1
                    self._draw_hline_levels(n, src, pip)
                    self.drawn[n] = src
                    # Record the CURRENT candle time — only check touch on FUTURE candles
                    cur_candle_t = candle.get("CANDLE_T", 0)
                    source_registry[n] = {"src": src, "triggered": False, "gen": 0,
                                          "registered_at_candle": cur_candle_t}
                    self.log(f"🆕  HLINE [{n[:25]}] @ {src:.5f} | 3+3 levels drawn | waiting for NEXT candle to touch line")

                elif obj.is_rectangle:
                    if not obj.rect_valid:
                        self.drawn[n] = "INVALID"
                        self.log(f"⚠️  [{n[:25]}] rectangle has zero height — skipping")
                        continue
                    center = round((obj.rect_top + obj.rect_bottom) / 2, 5)
                    self._draw_hline_levels(n, center, pip)
                    self.drawn[n] = center
                    source_registry[n] = {"src": center, "triggered": False, "gen": 0}
                    self.log(f"🆕  RECT [{n[:25]}] center={center:.5f} (h={obj.rect_height:.5f}) | 3+3 levels drawn | waiting for touch")

            # ── CHECK PREVIOUS CLOSED CANDLE TOUCHES SOURCE LINES ──
            # Use the LAST CLOSED candle (PREV_*) not the forming one.
            # This prevents same-candle buy+sell activation.
            cur_candle_t  = candle.get("CANDLE_T", 0)
            prev_h = candle.get("PREV_H", 0.0)
            prev_l = candle.get("PREV_L", 0.0)
            prev_c = candle.get("PREV_C", 0.0)
            prev_o = candle.get("PREV_O", 0.0)
            prev_t = candle.get("PREV_T", 0)

            for n, reg in list(source_registry.items()):
                if reg["triggered"]:
                    continue
                src = reg["src"]

                # Skip if prev candle hasn't changed since last check
                last_checked = reg.get("last_prev_t", 0)
                if prev_t == last_checked:
                    continue  # Same prev candle — already checked
                reg["last_prev_t"] = prev_t

                # Skip if prev candle is the same as when line was registered
                registered_at = reg.get("registered_at_candle", 0)
                if prev_t <= registered_at:
                    continue  # Line drawn on this or a newer candle — wait

                # Touch = previous closed candle's range includes the source line
                if prev_h > 0 and prev_l > 0 and prev_l <= src <= prev_h:
                    side = "from above" if prev_o > src else "from below"
                    if reg["triggered"]:
                        # Pullback re-entry: price returned to source after a round started
                        # Reset and place orders again (new round on same source)
                        reg["triggered"] = True  # keep as triggered
                        self.log(
                            f"🔁  Pullback to source [{n[:20]}] @ {src:.5f} {side} | "
                            f"placing fresh orders on original source", "NEW")
                        self._place_orders_for_source(src, pip, generation=0)
                    else:
                        reg["triggered"] = True
                        self.log(
                            f"🎯  Candle [{n[:20]}] touched source @ {src:.5f} {side} | "
                            f"H={prev_h:.5f} L={prev_l:.5f} C={prev_c:.5f} → placing orders", "NEW")
                        self._place_orders_for_source(src, pip, generation=reg["gen"])

            # ── PHASE 3: CHECK ACTIVATIONS ───────────────────────────
            self._check_phase3_activations(pip)

            # ── FOLLOW MOVED OBJECTS ───────────────────────────────
            if self.follow_enabled:
                for obj in trader:
                    n = obj.name
                    if n not in self.drawn or self.drawn[n] in ("INVALID", "WRONG_SYMBOL"):
                        continue
                    stored = self.drawn[n]
                    if obj.is_hline and isinstance(stored, float):
                        if abs(obj.price1 - stored) > 0.00001:
                            new_src = obj.price1
                            self.log(f"↕️  [{n[:25]}] moved {stored:.5f}→{new_src:.5f} — redrawing levels")
                            self._draw_hline_levels(n, new_src, pip)
                            self.drawn[n] = new_src
                            if n in source_registry:
                                source_registry[n]["src"] = new_src
                                source_registry[n]["triggered"] = False  # reset touch
                                source_registry[n]["registered_at_candle"] = prev_t  # wait for next candle after move

            self.prev_names = self.prev_names | cur
            self._stop.wait(SCAN_INTERVAL_SEC)

          except Exception as _e:
            import traceback as _tb
            self.log(f"💥 Watcher error: {type(_e).__name__}: {_e}", "ERROR")
            for _line in _tb.format_exc().strip().splitlines():
                self.log(f"   {_line}", "ERROR")
            self._stop.wait(SCAN_INTERVAL_SEC)

        write_commands(["DELETE_PREFIX|TB_"], symbol=self.symbol)
        mt5.shutdown()
        self.sig.status.emit("⚫  Stopped")
        self.log("Bot stopped — all bot lines cleared")


# ── Main Window ──────────────────────────────────────────────────
class GUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TraderBot v1")
        self.setMinimumSize(1100, 720)
        self.setStyleSheet(SS)
        self._worker: Optional[WatcherWorker] = None
        self._sig    = Sig()
        self._sig.new_objects.connect(self._on_objects)
        self._sig.status.connect(self._on_status)
        self._sig.log_line.connect(self._on_log)
        self._sig.bt_done.connect(self._display_bt_result)
        self._trader_objects = []
        self._pip_step = PIP_STEP
        self._bt_running = False  # guard against double-run
        self._build_ui()
        QTimer.singleShot(100, self._init_mt5_price)
        self._pt = QTimer(); self._pt.timeout.connect(self._refresh_price); self._pt.start(1000)

    # ─────────────────────────────── UI BUILD ────────────────────

    def _build_ui(self):
        root = QWidget(); self.setCentralWidget(root)
        vl = QVBoxLayout(root); vl.setSpacing(6); vl.setContentsMargins(10,10,10,10)
        vl.addWidget(self._header())
        spl = QSplitter(Qt.Horizontal)
        spl.addWidget(self._left_panel())
        spl.addWidget(self._right_panel())
        spl.setSizes([370, 730])
        vl.addWidget(spl, 1)
        vl.addWidget(self._status_bar())

    def _header(self):
        w = QFrame()
        w.setStyleSheet(f"background:{C['panel']};border:1px solid {C['border']};border-radius:6px;")
        hl = QHBoxLayout(w); hl.setContentsMargins(14,8,14,8)
        t = QLabel("📈  TraderBot  <span style='color:#4A5568;font-size:10px;'>v1.0</span>")
        t.setStyleSheet(f"color:{C['gold']};font-size:16px;font-weight:bold;")
        hl.addWidget(t); hl.addStretch()
        self.lbl_price = QLabel("Price: —")
        self.lbl_price.setStyleSheet(f"color:{C['cyan']};font-family:Consolas;font-size:14px;font-weight:bold;")
        hl.addWidget(self.lbl_price)
        hl.addWidget(self._vline())
        self.lbl_sym = QLabel(WATCH_SYMBOL)
        self.lbl_sym.setStyleSheet(f"color:{C['txt2']};font-size:12px;")
        hl.addWidget(self.lbl_sym)
        hl.addWidget(self._vline())
        self.lbl_ea_chart = QLabel("EA: —")
        self.lbl_ea_chart.setStyleSheet(f"color:{C['txt3']};font-size:10px;")
        self.lbl_ea_chart.setToolTip("Which chart the ObjectExporter EA is currently on")
        hl.addWidget(self.lbl_ea_chart)
        hl.addWidget(self._vline())
        self.lbl_status = QLabel("⚫  Stopped")
        self.lbl_status.setStyleSheet(f"color:{C['txt2']};font-size:11px;")
        hl.addWidget(self.lbl_status)
        return w

    def _left_panel(self):
        w = QWidget(); vl = QVBoxLayout(w); vl.setSpacing(8); vl.setContentsMargins(0,0,4,0)

        # ── Controls ─────────────────────────────────────────────
        grp = QGroupBox("Bot Control"); cl = QVBoxLayout(grp)
        # Symbol
        hl_sym = QHBoxLayout()
        hl_sym.addWidget(QLabel("Symbol:"))
        self.sym_combo = QComboBox()
        self.sym_combo.setEditable(True)
        self.sym_combo.addItems(["XAUUSD_i", "EURUSD_i", "GBPUSD_i",
                                  "XAUUSD", "EURUSD", "GBPUSD",
                                  "NAS100", "US30", "BTCUSD"])
        self.sym_combo.setCurrentText(WATCH_SYMBOL)
        self.sym_combo.currentTextChanged.connect(self._on_symbol_changed)
        hl_sym.addWidget(self.sym_combo); hl_sym.addStretch(); cl.addLayout(hl_sym)

        # Pip step
        hl_pip = QHBoxLayout()
        hl_pip.addWidget(QLabel("Pip step:"))
        self.spin_pip = QDoubleSpinBox()
        self.spin_pip.setRange(0.1, 200.0); self.spin_pip.setSingleStep(0.5)
        self.spin_pip.setValue(PIP_STEP);   self.spin_pip.setDecimals(1)
        hl_pip.addWidget(self.spin_pip); hl_pip.addStretch(); cl.addLayout(hl_pip)

        # TP pips (0 = use RR ratio, >0 = fixed pip TP from L3)
        hl_tp = QHBoxLayout()
        hl_tp.addWidget(QLabel("TP pips:"))
        self.spin_tp = QDoubleSpinBox()
        self.spin_tp.setRange(0, 500.0); self.spin_tp.setSingleStep(5.0)
        self.spin_tp.setValue(0); self.spin_tp.setDecimals(1)
        self.spin_tp.setToolTip("Fixed TP in pips from L3 for all positions in a round.\n0 = use RR ratio from config")
        hl_tp.addWidget(self.spin_tp); hl_tp.addStretch(); cl.addLayout(hl_tp)

        # Spawn level: which level triggers a new round
        hl_spawn = QHBoxLayout()
        hl_spawn.addWidget(QLabel("Spawn on:"))
        self.combo_spawn = QComboBox()
        self.combo_spawn.addItems(["L2 only", "L3 only", "L2 and L3"])
        self.combo_spawn.setCurrentText("L2 and L3")
        self.combo_spawn.setToolTip("Which activated level triggers a new Phase 3 round")
        hl_spawn.addWidget(self.combo_spawn); hl_spawn.addStretch(); cl.addLayout(hl_spawn)
        self.btn_start = QPushButton("▶  Start Watcher"); self.btn_start.setObjectName("btn_start")
        self.btn_start.setMinimumHeight(38); self.btn_start.clicked.connect(self._start)
        cl.addWidget(self.btn_start)
        self.btn_stop = QPushButton("■  Stop Watcher"); self.btn_stop.setObjectName("btn_stop")
        self.btn_stop.setMinimumHeight(38); self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop); cl.addWidget(self.btn_stop)

        self.chk_follow = QCheckBox("🔗  Follow object when moved")
        self.chk_follow.setChecked(True)
        self.chk_follow.setStyleSheet(f"color:{C['txt2']};font-size:11px;padding:2px 0;")
        self.chk_follow.setToolTip("When checked, level lines redraw automatically if you move the drawn object")
        cl.addWidget(self.chk_follow)
        vl.addWidget(grp)

        # ── Orders ───────────────────────────────────────────────
        grp2 = QGroupBox("Live Orders"); ol = QVBoxLayout(grp2)
        self.btn_place = QPushButton("🎯  Place Buy/Sell Stops")
        self.btn_place.setObjectName("btn_orders"); self.btn_place.setMinimumHeight(34)
        self.btn_place.setEnabled(False); self.btn_place.clicked.connect(self._place_orders)
        ol.addWidget(self.btn_place)
        self.btn_cancel = QPushButton("🗑️  Cancel All Bot Orders")
        self.btn_cancel.setObjectName("btn_cancel"); self.btn_cancel.clicked.connect(self._cancel_orders)
        ol.addWidget(self.btn_cancel)
        vl.addWidget(grp2)

        # ── Levels table ─────────────────────────────────────────
        grp3 = QGroupBox("Detected Levels"); ll = QVBoxLayout(grp3)
        self.lvl_tbl = QTableWidget(0, 3)
        self.lvl_tbl.setHorizontalHeaderLabels(["Level","Price","Dist"])
        self.lvl_tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.lvl_tbl.setAlternatingRowColors(True)
        self.lvl_tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        self.lvl_tbl.verticalHeader().setVisible(False)
        ll.addWidget(self.lvl_tbl)
        vl.addWidget(grp3, 1)
        return w

    def _right_panel(self):
        w = QWidget(); vl = QVBoxLayout(w); vl.setSpacing(0); vl.setContentsMargins(4,0,0,0)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._tab_log(),       "📋  Log")
        self.tabs.addTab(self._tab_orders(),    "📊  Orders")
        self.tabs.addTab(self._tab_backtest(),  "🔬  Backtest")
        vl.addWidget(self.tabs)
        return w

    def _tab_log(self):
        w = QWidget(); vl = QVBoxLayout(w); vl.setContentsMargins(4,4,4,4)
        self.log_view = QTextEdit(); self.log_view.setReadOnly(True)
        self.log_view.setLineWrapMode(QTextEdit.NoWrap)
        vl.addWidget(self.log_view)
        btn = QPushButton("Clear"); btn.setFixedHeight(24); btn.clicked.connect(self.log_view.clear)
        vl.addWidget(btn); return w

    def _tab_orders(self):
        w = QWidget(); vl = QVBoxLayout(w); vl.setContentsMargins(4,4,4,4)
        self.ord_tbl = QTableWidget(0, 5)
        self.ord_tbl.setHorizontalHeaderLabels(["Lvl","Type","Entry","SL","TP"])
        self.ord_tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.ord_tbl.setAlternatingRowColors(True)
        self.ord_tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        self.ord_tbl.verticalHeader().setVisible(False)
        vl.addWidget(self.ord_tbl); return w

    def _tab_backtest(self):
        w = QWidget(); vl = QVBoxLayout(w); vl.setContentsMargins(8,8,8,8); vl.setSpacing(6)

        # ── Settings ──────────────────────────────────────────────
        grp_set = QGroupBox("Settings"); sl = QHBoxLayout(grp_set); sl.setSpacing(10)
        sl.addWidget(QLabel("Symbol:"))
        self.bt_symbol = QComboBox()
        self.bt_symbol.setEditable(True)
        self.bt_symbol.addItems([WATCH_SYMBOL, "EURUSD", "GBPUSD", "US30", "NAS100", "XAUUSD"])
        self.bt_symbol.setCurrentText(WATCH_SYMBOL)
        self.bt_symbol.setFixedWidth(110)
        sl.addWidget(self.bt_symbol)
        sl.addWidget(QLabel("TF:"))
        self.bt_tf = QComboBox(); self.bt_tf.addItems(["M1","M5","M15","H1","H4"])
        self.bt_tf.setCurrentText("M5"); sl.addWidget(self.bt_tf)
        sl.addWidget(QLabel("Days:"))
        self.bt_days = QSpinBox(); self.bt_days.setRange(1,30); self.bt_days.setValue(5)
        sl.addWidget(self.bt_days)
        sl.addWidget(QLabel("RR:"))
        self.bt_rr = QDoubleSpinBox(); self.bt_rr.setRange(0.5,10.0)
        self.bt_rr.setValue(TP_RR_RATIO); self.bt_rr.setSingleStep(0.5); self.bt_rr.setDecimals(1)
        sl.addWidget(self.bt_rr)
        sl.addStretch()
        self.btn_bt = QPushButton("▶  Run"); self.btn_bt.setObjectName("btn_bt")
        self.btn_bt.setMinimumHeight(30); self.btn_bt.clicked.connect(self._run_backtest)
        sl.addWidget(self.btn_bt)
        vl.addWidget(grp_set)

        # ── Summary cards ─────────────────────────────────────────
        grp_sum = QGroupBox("Summary"); hs = QHBoxLayout(grp_sum)
        self._bt_cards = {}
        for key, label, color in [
            ("candles","Candles",C['txt2']),("triggered","Triggered",C['cyan']),
            ("wins","Wins",C['green']),("losses","Losses",C['red']),
            ("winrate","Win%",C['gold']),("pips","Pips",C['purple']),
        ]:
            card = QFrame()
            card.setStyleSheet(f"background:{C['card']};border:1px solid {C['border']};border-radius:6px;")
            cv = QVBoxLayout(card); cv.setContentsMargins(8,4,8,4); cv.setSpacing(1)
            lt = QLabel(label); lt.setStyleSheet(f"color:{C['txt3']};font-size:9px;font-weight:bold;")
            lv = QLabel("—"); lv.setStyleSheet(f"color:{color};font-size:16px;font-weight:bold;font-family:Consolas;")
            lv.setAlignment(Qt.AlignCenter)
            cv.addWidget(lt); cv.addWidget(lv)
            self._bt_cards[key] = lv; hs.addWidget(card)
        vl.addWidget(grp_sum)

        # ── Progress / loading ────────────────────────────────────
        self.bt_progress = QProgressBar(); self.bt_progress.setVisible(False)
        self.bt_progress.setFixedHeight(6); self.bt_progress.setTextVisible(False)
        vl.addWidget(self.bt_progress)

        # ── Candle chart ──────────────────────────────────────────
        self.bt_chart = CandleChartWidget()
        vl.addWidget(self.bt_chart, 2)

        # ── Candle replay player ──────────────────────────────────
        grp_replay = QGroupBox("Playback & Orders")
        rl = QVBoxLayout(grp_replay); rl.setSpacing(4)

        # Bar info row
        bar_info_row = QHBoxLayout()
        self.bt_bar_lbl = QLabel("Bar: — / —")
        self.bt_bar_lbl.setStyleSheet(f"color:{C['cyan']};font-family:Consolas;font-size:11px;")
        bar_info_row.addWidget(self.bt_bar_lbl)
        bar_info_row.addStretch()
        self.bt_price_lbl = QLabel("O:— H:— L:— C:—")
        self.bt_price_lbl.setStyleSheet(f"color:{C['txt2']};font-family:Consolas;font-size:11px;")
        bar_info_row.addWidget(self.bt_price_lbl)
        rl.addLayout(bar_info_row)

        # Slider
        self.bt_slider = QSlider(Qt.Horizontal)
        self.bt_slider.setMinimum(0); self.bt_slider.setMaximum(0)
        self.bt_slider.valueChanged.connect(self._on_bt_slider)
        self.bt_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                background:{C['border']};height:6px;border-radius:3px;
            }}
            QSlider::handle:horizontal {{
                background:{C['cyan']};width:14px;height:14px;
                border-radius:7px;margin:-4px 0;
            }}
            QSlider::sub-page:horizontal {{
                background:{C['cyan']};height:6px;border-radius:3px;
            }}
        """)
        rl.addWidget(self.bt_slider)

        # Playback controls
        ctrl_row = QHBoxLayout()
        self.btn_bt_first = QPushButton("⏮"); self.btn_bt_first.setFixedWidth(36)
        self.btn_bt_first.clicked.connect(lambda: self.bt_slider.setValue(0))
        self.btn_bt_prev  = QPushButton("◀"); self.btn_bt_prev.setFixedWidth(36)
        self.btn_bt_prev.clicked.connect(lambda: self.bt_slider.setValue(max(0, self.bt_slider.value()-1)))
        self.btn_bt_play  = QPushButton("▶ Play"); self.btn_bt_play.setFixedWidth(72)
        self.btn_bt_play.setCheckable(True); self.btn_bt_play.clicked.connect(self._bt_play_toggle)
        self.btn_bt_next  = QPushButton("▶"); self.btn_bt_next.setFixedWidth(36)
        self.btn_bt_next.clicked.connect(lambda: self.bt_slider.setValue(min(self.bt_slider.maximum(), self.bt_slider.value()+1)))
        self.btn_bt_last  = QPushButton("⏭"); self.btn_bt_last.setFixedWidth(36)
        self.btn_bt_last.clicked.connect(lambda: self.bt_slider.setValue(self.bt_slider.maximum()))
        self.bt_speed = QComboBox(); self.bt_speed.addItems(["0.5×","1×","2×","5×","10×"])
        self.bt_speed.setCurrentText("1×"); self.bt_speed.setFixedWidth(60)
        for b in [self.btn_bt_first, self.btn_bt_prev, self.btn_bt_play,
                  self.btn_bt_next, self.btn_bt_last]:
            ctrl_row.addWidget(b)
        ctrl_row.addWidget(QLabel("Speed:")); ctrl_row.addWidget(self.bt_speed)
        ctrl_row.addStretch()
        rl.addLayout(ctrl_row)

        # Order state grid — shows each order's state at current bar
        self.bt_order_grid = QTableWidget(0, 6)
        self.bt_order_grid.setHorizontalHeaderLabels(["Gen","Lvl","Type","Entry","SL/TP","State"])
        self.bt_order_grid.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.bt_order_grid.setAlternatingRowColors(True)
        self.bt_order_grid.setEditTriggers(QTableWidget.NoEditTriggers)
        self.bt_order_grid.verticalHeader().setVisible(False)
        self.bt_order_grid.setFixedHeight(220)
        rl.addWidget(self.bt_order_grid)

        vl.addWidget(grp_replay)

        # ── Auto-play timer ───────────────────────────────────────
        self._bt_play_timer = QTimer()
        self._bt_play_timer.timeout.connect(self._bt_auto_step)
        self._bt_snapshots = []

        return w

    def _status_bar(self):
        w = QFrame()
        w.setStyleSheet(f"background:{C['panel']};border:1px solid {C['border']};border-radius:4px;")
        hl = QHBoxLayout(w); hl.setContentsMargins(10,4,10,4)
        self.lbl_obj_count = QLabel("Objects: —")
        self.lbl_obj_count.setStyleSheet(f"color:{C['txt2']};font-size:10px;")
        hl.addWidget(self.lbl_obj_count); hl.addStretch()
        self.lbl_auto = QLabel("Auto-hidden: —")
        self.lbl_auto.setStyleSheet(f"color:{C['txt3']};font-size:10px;")
        hl.addWidget(self.lbl_auto); return w

    def _vline(self):
        f = QFrame(); f.setFrameShape(QFrame.VLine); return f

    # ─────────────────────────────── SLOTS ───────────────────────

    def _init_mt5_price(self):
        try:
            mt5.initialize()
            mt5.login(MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER)
            # Symbol combos pre-populated with common symbols
        except Exception:
            pass

    def _start(self):
        self._pip_step = self.spin_pip.value()
        self.spin_pip.setEnabled(False)
        active_sym   = self.sym_combo.currentText().strip() or WATCH_SYMBOL
        self._tp_pips   = self.spin_tp.value()
        self._spawn_lvls = self.combo_spawn.currentText()
        self._worker = WatcherWorker(self._sig, self._pip_step, symbol=active_sym,
                                      tp_pips=self._tp_pips, spawn_on=self._spawn_lvls)
        self._worker.follow_enabled = self.chk_follow.isChecked()
        self._worker.start()
        self.btn_start.setEnabled(False); self.btn_stop.setEnabled(True)
        self.chk_follow.stateChanged.connect(self._toggle_follow)
        self._on_log(f"{datetime.now().strftime('%H:%M:%S')}  ▶ Watcher started | symbol={active_sym} | pip_step={self._pip_step}", "INFO")
        self._on_log(f"{datetime.now().strftime('%H:%M:%S')}  💡 Make sure ObjectExporter EA is on the {active_sym} chart in MT5", "INFO")

    def _toggle_follow(self, state):
        if self._worker:
            self._worker.follow_enabled = bool(state)
            status = "enabled" if state else "locked"
            self._on_log(f"{datetime.now().strftime('%H:%M:%S')}  🔗 Follow object: {status}", "INFO")

    def _on_symbol_changed(self, sym: str):
        sym = sym.strip()
        if not sym: return
        # Update header label
        self.lbl_sym.setText(sym)
        # Sync backtest symbol combo
        if hasattr(self, "bt_symbol"):
            self.bt_symbol.setCurrentText(sym)
        self._on_log(f"{datetime.now().strftime('%H:%M:%S')}  🔄 Symbol changed to {sym}", "INFO")

    def _stop(self):
        if self._worker: self._worker.stop(); self._worker = None
        self.btn_start.setEnabled(True); self.btn_stop.setEnabled(False)
        self.btn_place.setEnabled(False); self.spin_pip.setEnabled(True)

    def _place_orders(self):
        if not self.btn_place.isEnabled():
            return  # guard against spurious calls
        pip = get_pip_size(self.sym_combo.currentText().strip() or WATCH_SYMBOL)
        all_orders = []

        hlines = [o for o in self._trader_objects if o.is_hline]
        rects  = [o for o in self._trader_objects if o.is_rectangle]

        if hlines:
            # Hline: 3 buy-stops above, 3 sell-stops below
            _sym = self.sym_combo.currentText().strip() or WATCH_SYMBOL
            orders = place_level_orders(hlines[0].price1, pip, self._pip_step, _sym)
            all_orders.extend(orders)

        elif rects:
            # Rectangle: buy-stops above TOP edge, sell-stops below BOTTOM edge
            rect = next((r for r in rects if r.rect_valid), None)
            if rect is None:
                self._on_log(f"{datetime.now().strftime('%H:%M:%S')}  ⚠️  Rectangle not fully drawn yet", "WARN")
                return
            step = self._pip_step * pip
            top    = rect.rect_top
            bottom = rect.rect_bottom
            above  = [top    + step * i for i in range(1, 4)]
            below  = [bottom - step * i for i in range(1, 4)]
            for i in range(3):
                sl_dist = above[i] - below[i]
                all_orders.append({
                    "level": i+1, "type": "BUY_STOP",
                    "entry": round(above[i], 5),
                    "sl":    round(below[i], 5),
                    "tp":    round(above[i] + sl_dist * TP_RR_RATIO, 5),
                    "sl_pips": round(sl_dist / pip, 1),
                })
                all_orders.append({
                    "level": i+1, "type": "SELL_STOP",
                    "entry": round(below[i], 5),
                    "sl":    round(above[i], 5),
                    "tp":    round(below[i] - sl_dist * TP_RR_RATIO, 5),
                    "sl_pips": round(sl_dist / pip, 1),
                })

        if not all_orders:
            self._on_log(f"{datetime.now().strftime('%H:%M:%S')}  ⚠️  No line or rectangle detected", "WARN")
            return

        self.btn_place.setEnabled(False)
        self._populate_ord_table(all_orders)
        results = send_orders(all_orders, self.sym_combo.currentText().strip() or WATCH_SYMBOL)
        ok      = sum(1 for r in results if r["ok"])
        failed  = [r for r in results if not r["ok"]]
        ts      = datetime.now().strftime('%H:%M:%S')
        if ok == len(results):
            self._on_log(f"{ts}  ✅ All {ok} orders placed successfully", "NEW")
        elif ok > 0:
            self._on_log(f"{ts}  ⚠️  {ok}/{len(results)} placed — {failed[0].get('reason','unknown')}", "WARN")
        else:
            reason = failed[0].get('reason', 'unknown') if failed else 'unknown'
            self._on_log(f"{ts}  ❌ 0/{len(results)} placed — {reason}", "ERROR")
            if "Market closed" in reason:
                self._on_log(f"{ts}  💡 Use the Backtest tab to test while market is closed", "INFO")
        self.btn_place.setEnabled(True)
        self.tabs.setCurrentIndex(1)

    def _cancel_orders(self):
        # Guard against multiple rapid calls
        if getattr(self, "_cancelling", False):
            return
        self._cancelling = True
        try:
            sym = self.sym_combo.currentText().strip() or WATCH_SYMBOL
            n = cancel_all_tb_orders(sym)
            write_commands(["DELETE_PREFIX|TB_"], symbol=sym)
            self._on_log(f"{datetime.now().strftime('%H:%M:%S')}  🗑️  Cancelled {n} bot orders + cleared all level lines", "WARN")
            self.ord_tbl.setRowCount(0)
        finally:
            self._cancelling = False

    def _run_backtest(self):
        if self._bt_running:
            return  # already running
        hlines = [o for o in self._trader_objects if o.is_hline]
        rects  = [o for o in self._trader_objects if o.is_rectangle and o.rect_valid]
        if not hlines and not rects:
            self._on_log(f"{datetime.now().strftime('%H:%M:%S')}  ⚠️  Draw a line or rectangle on your chart first", "WARN")
            return

        # Warn if pip step might be below broker minimum
        sym_for_check = self.bt_symbol.currentText().strip() or WATCH_SYMBOL
        ts = datetime.now().strftime('%H:%M:%S')
        self._on_log(f"{ts}  🔬 Running backtest on {sym_for_check}...", "BT")
        self._bt_running = True
        self.btn_bt.setEnabled(False); self.btn_bt.setText("Loading…")
        self.bt_progress.setVisible(True); self.bt_progress.setRange(0, 0)
        self._bt_play_timer.stop()
        self.btn_bt_play.setChecked(False); self.btn_bt_play.setText("▶ Play")

        bt_sym   = self.bt_symbol.currentText().strip() or self.sym_combo.currentText().strip() or WATCH_SYMBOL
        pip      = get_pip_size(bt_sym)
        pip_step = self._pip_step
        tf       = self.bt_tf.currentText()
        days     = self.bt_days.value()
        rr       = self.bt_rr.value()

        use_hline = bool(hlines)
        if use_hline:
            src = hlines[0].price1
            rect_top = rect_bot = None
        else:
            rect = rects[0]
            src  = rect.price1
            rect_top = rect.rect_top; rect_bot = rect.rect_bottom

        # Capture all values for the thread closure
        _sym      = bt_sym
        _tf       = tf
        _src      = src
        _step     = pip_step
        _rr       = rr
        _days     = days
        _hline    = use_hline
        _rtop     = rect_top
        _rbot     = rect_bot

        def _run():
            import traceback as _tb
            self._run_err = None
            self._bt_result = None
            try:
                from core.backtest_engine import get_pip_size_for_symbol
                _pip = get_pip_size_for_symbol(_sym)
                self._sig.log_line.emit(
                    f"{datetime.now().strftime('%H:%M:%S')}  🔬 BT starting: {_sym} {_tf} {_days}d | pip={_pip:.6f} | src={_src:.5f}", "BT")
                result = run_backtest(
                    symbol=_sym, timeframe=_tf,
                    source_price=_src, pip_step=_step,
                    pip_size=_pip, tp_rr=_rr,
                    lookback_days=_days, use_hline=_hline,
                    rect_top=_rtop, rect_bottom=_rbot,
                )
                self._sig.log_line.emit(
                    f"{datetime.now().strftime('%H:%M:%S')}  🔬 BT done: {result.candles_used} candles", "BT")
                self._bt_result = result
            except Exception as e:
                import traceback as _tb
                self._run_err = f"{type(e).__name__}: {e}"
                full_tb = _tb.format_exc()
                self._sig.log_line.emit(
                    f"{datetime.now().strftime('%H:%M:%S')}  ❌ BT error: {self._run_err}", "ERROR")
                # Log each traceback line separately so it's visible
                for line in full_tb.strip().splitlines():
                    self._sig.log_line.emit(
                        f"    {line}", "ERROR")
            finally:
                self._sig.bt_done.emit()

        threading.Thread(target=_run, daemon=True).start()

    def _on_objects(self, trader, auto):
        self._trader_objects = trader
        self.lbl_obj_count.setText(f"Trader objects: {len(trader)}")
        self.lbl_auto.setText(f"Auto-hidden: {len(auto)}")
        has_object = any(o.is_hline or o.is_rectangle for o in trader)
        # Only update enabled state when it actually changes to avoid spurious Qt signals
        new_place = has_object and self._worker is not None
        if self.btn_place.isEnabled() != new_place:
            self.btn_place.setEnabled(new_place)
        if not self.btn_bt.isEnabled() and not self._bt_running:
            self.btn_bt.setEnabled(True)
        self._populate_lvl_table(trader)

    def _on_status(self, msg):
        self.lbl_status.setText(msg)
        color = C['green'] if "Running" in msg else C['red'] if "failed" in msg else C['txt2']
        self.lbl_status.setStyleSheet(f"color:{color};font-size:11px;")

    def _on_log(self, msg, level="INFO"):
        if msg == "__BT_RESULT__": return
        if msg.startswith("__EA_SYM__"):
            ea_sym = msg[10:]
            self.lbl_ea_chart.setText(f"EA: {ea_sym}")
            active_sym = self.sym_combo.currentText().strip()
            if ea_sym != active_sym:
                self.lbl_ea_chart.setStyleSheet(f"color:{C['orange']};font-size:10px;font-weight:bold;")
                self.lbl_ea_chart.setToolTip(f"⚠️ EA is on {ea_sym} but you want {active_sym}. Drag ObjectExporter to {active_sym} chart.")
            else:
                self.lbl_ea_chart.setStyleSheet(f"color:{C['green']};font-size:10px;")
                self.lbl_ea_chart.setToolTip(f"EA is on the correct chart: {ea_sym}")
            return
        clr = {
            "NEW": C['green'], "WARN": C['orange'],
            "ERROR": C['red'], "INFO": C['txt2'], "BT": C['cyan'],
        }.get(level, C['txt2'])
        self.log_view.moveCursor(QTextCursor.End)
        self.log_view.insertHtml(
            f'<span style="color:{clr};font-family:Consolas;font-size:11px;">{msg}</span><br>')
        self.log_view.moveCursor(QTextCursor.End)

    def _refresh_price(self):
        try:
            sym  = self.sym_combo.currentText().strip() if hasattr(self,'sym_combo') else WATCH_SYMBOL
            tick = mt5.symbol_info_tick(sym)
            if tick:
                p = (tick.bid + tick.ask) / 2
                self.lbl_price.setText(f"Price: {p:.5f}")
        except Exception: pass

    def _populate_lvl_table(self, trader):
        sym  = self.sym_combo.currentText().strip() if hasattr(self,'sym_combo') else WATCH_SYMBOL
        pip  = get_pip_size(sym)
        step = self._pip_step * pip
        self.lvl_tbl.setRowCount(0)
        try:
            tick = mt5.symbol_info_tick(sym)
            cur  = (tick.bid + tick.ask) / 2 if tick else 0
        except: cur = 0

        hlines = [o for o in trader if o.is_hline]
        rects  = [o for o in trader if o.is_rectangle]
        rows   = []

        if hlines:
            src = hlines[0].price1
            for i in range(3, 0, -1):
                rows.append((f"🟠 Above {i}", src + step*i, C['orange']))
            rows.append(("── YOUR LINE", src, C['gold']))
            for i in range(1, 4):
                rows.append((f"🟢 Below {i}", src - step*i, C['green']))

        elif rects:
            rect = next((r for r in rects if r.rect_valid), None)
            if rect is None: return
            top = rect.rect_top; bot = rect.rect_bottom
            for i in range(3, 0, -1):
                rows.append((f"🟠 Above {i}", top + step*i, C['orange']))
            rows.append((f"── TOP  {top:.5f}", top, C['gold']))
            rows.append((f"── ZONE ({'%.5f' % (top - bot)})", (top+bot)/2, C['txt3']))
            rows.append((f"── BOT  {bot:.5f}", bot, C['gold']))
            for i in range(1, 4):
                rows.append((f"🟢 Below {i}", bot - step*i, C['green']))

        if not rows: return
        self.lvl_tbl.setRowCount(len(rows))
        for r, (lbl, price, clr) in enumerate(rows):
            dist  = f"{'+' if price-cur >= 0 else ''}{price-cur:.2f}" if cur else "—"
            for c, v in enumerate([lbl, f"{price:.5f}", dist]):
                it = QTableWidgetItem(v); it.setForeground(QColor(clr))
                self.lvl_tbl.setItem(r, c, it)

    def _populate_ord_table(self, orders):
        self.ord_tbl.setRowCount(len(orders))
        for r, o in enumerate(orders):
            clr = QColor(C['green'] if o["type"] == "BUY_STOP" else C['red'])
            for c, v in enumerate([f"L{o['level']}", o["type"],
                                    f"{o['entry']:.5f}", f"{o['sl']:.5f}", f"{o['tp']:.5f}"]):
                it = QTableWidgetItem(v); it.setForeground(clr)
                self.ord_tbl.setItem(r, c, it)

    def _display_bt_result(self):
        self._bt_running = False
        try:
            self.btn_bt.setEnabled(True)
            self.btn_bt.setText("▶  Run")
            self.bt_progress.setVisible(False)
            self.bt_progress.setRange(0, 1)
        except Exception:
            return
        if not hasattr(self, '_bt_result') or self._bt_result is None:
            err = getattr(self, '_run_err', None) or 'Unknown error — check log'
            self._on_log(f"{datetime.now().strftime('%H:%M:%S')}  ❌ Backtest failed: {err}", "ERROR")
            return
        r = self._bt_result
        if r.candles_used == 0:
            self._on_log(f"{datetime.now().strftime('%H:%M:%S')}  ❌ No candles returned — check symbol name and MT5 connection", "ERROR")
            return

        # Summary cards
        self._bt_cards["candles"].setText(str(r.candles_used))
        self._bt_cards["triggered"].setText(str(len(r.triggered)))
        self._bt_cards["wins"].setText(str(len(r.wins)))
        self._bt_cards["losses"].setText(str(len(r.losses)))
        self._bt_cards["winrate"].setText(f"{r.winrate:.0f}%")
        pp = r.total_pips
        self._bt_cards["pips"].setText(f"{pp:+.1f}")
        self._bt_cards["pips"].setStyleSheet(
            f"color:{C['green'] if pp >= 0 else C['red']};font-size:16px;font-weight:bold;font-family:Consolas;")

        # Pass snapshots to chart (sources + levels embedded in each snapshot)
        self._bt_snapshots = r.snapshots
        self.bt_chart.set_snapshots(r.snapshots, bt_result=r)

        # Setup replay slider
        n = len(r.snapshots)
        self.bt_slider.setMaximum(max(0, n-1))
        self.bt_slider.setValue(0)
        if n > 0:
            self._render_bar(0)

        self.tabs.setCurrentIndex(2)
        ts = datetime.now().strftime('%H:%M:%S')
        self._on_log(f"{ts}  🔬 {r.candles_used} bars | W:{len(r.wins)} L:{len(r.losses)} | {pp:+.1f} pips", "BT")

    def _on_bt_slider(self, value: int):
        if 0 <= value < len(self._bt_snapshots):
            self._render_bar(value)

    def _render_bar(self, idx: int):
        snap = self._bt_snapshots[idx]
        total = len(self._bt_snapshots)
        t = snap.bar_time.strftime("%m-%d %H:%M") if snap.bar_time else "?"
        self.bt_bar_lbl.setText(f"Bar {idx+1}/{total}  [{t}]")
        self.bt_price_lbl.setText(
            f"O:{snap.open:.5f}  H:{snap.high:.5f}  L:{snap.low:.5f}  C:{snap.close:.5f}")
        # Use orders_at_bar to get order dicts at this snapshot
        if hasattr(self, '_bt_result') and self._bt_result:
            orders_now = self._bt_result.orders_at_bar(snap)
        else:
            orders_now = []
        self._render_order_grid(orders_now, snap.high, snap.low)
        self.bt_chart.set_bar(idx)

    def _render_order_grid(self, orders, bar_high, bar_low):
        # orders is now a list of dicts from orders_at_bar()
        self.bt_order_grid.setRowCount(len(orders))
        self.bt_order_grid.setFixedHeight(min(400, 30 + len(orders) * 28))
        for row, o in enumerate(orders):
            state = o["state"]
            direction = o["direction"]
            state_clr = {
                "PENDING":   C['txt3'],
                "TRIGGERED": C['cyan'],
                "TP":        C['green'],
                "SL":        C['red'],
                "OPEN":      C['blue'],
            }.get(state, C['txt2'])
            dir_clr = QColor(C['green'] if direction == "BUY_STOP" else C['red'])
            emoji = {"PENDING":"⏳","TRIGGERED":"🔵","TP":"✅","SL":"❌","OPEN":"🔵"}.get(state,"?")
            entry_touched = (direction == "BUY_STOP"  and bar_high >= o["entry"]) or                             (direction == "SELL_STOP" and bar_low  <= o["entry"])
            sl_tp_str = f"SL {o['sl']:.5f} / TP {o['tp']:.5f}"
            gen_colors = ["#F5A623","#00BCD4","#B388FF","#FF8C00","#00FF88"]
            gen_clr_str = gen_colors[min(o["generation"], len(gen_colors)-1)]
            vals = [f"G{o['generation']}", f"L{o['level']}", direction,
                    f"{o['entry']:.5f}", sl_tp_str, f"{emoji} {state}"]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if c == 5:
                    it.setForeground(QColor(state_clr))
                elif c == 0:
                    it.setForeground(QColor(gen_clr_str))
                else:
                    it.setForeground(dir_clr)
                if entry_touched and state == "PENDING":
                    it.setBackground(QColor("#1A2A0A"))
                self.bt_order_grid.setItem(row, c, it)

    def _bt_play_toggle(self, checked: bool):
        if checked:
            self.btn_bt_play.setText("⏸ Pause")
            speeds = {"0.5×": 2000, "1×": 800, "2×": 400, "5×": 160, "10×": 80}
            interval = speeds.get(self.bt_speed.currentText(), 800)
            self._bt_play_timer.start(interval)
        else:
            self.btn_bt_play.setText("▶ Play")
            self._bt_play_timer.stop()

    def _bt_auto_step(self):
        nxt = self.bt_slider.value() + 1
        if nxt > self.bt_slider.maximum():
            self._bt_play_timer.stop()
            self.btn_bt_play.setChecked(False)
            self.btn_bt_play.setText("▶ Play")
        else:
            self.bt_slider.setValue(nxt)

    def closeEvent(self, e):
        self._stop(); e.accept()


def main():
    app = QApplication(sys.argv); app.setStyle("Fusion")
    win = GUI(); win.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()