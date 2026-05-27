"""
╔══════════════════════════════════════════════════════════════════╗
║         TraderBot v1 — GUI  (with Backtest Tab)                 ║
║  pip install PyQt5   →   python gui.py                          ║
╚══════════════════════════════════════════════════════════════════╝
"""
from chart_widget import CandleChartWidget
from core import chart_watcher as cw
from core.backtest_engine import run_backtest
from core.order_manager import place_level_orders, send_orders, cancel_all_tb_orders
from core.line_drawer import draw_level_lines, clear_level_lines, get_pip_size, write_commands, STYLE_DASH, CLR_ABOVE_1, CLR_ABOVE_2, CLR_ABOVE_3, CLR_BELOW_1, CLR_BELOW_2, CLR_BELOW_3
from config import (
    MT5_LOGIN, MT5_PASSWORD, MT5_SERVER,
    WATCH_SYMBOL, SCAN_INTERVAL_SEC,
    AUTO_OBJECT_PREFIXES, PIP_STEP, BOT_LINE_PREFIX,
    LOT_SIZE, TP_RR_RATIO, MAGIC_NUMBER,
)
import sys
import os
import threading
from datetime import datetime
from typing import Optional

import MetaTrader5 as mt5
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QGroupBox, QTextEdit, QFrame,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QDoubleSpinBox, QSpinBox, QComboBox, QSplitter, QSizePolicy,
    QProgressBar, QCheckBox, QSlider, QScrollArea, QFormLayout, QGridLayout,
    QLineEdit,
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt5.QtGui import QColor, QTextCursor, QFont

os.makedirs("logs", exist_ok=True)

# ── Palette ──────────────────────────────────────────────────────
C = {
    "bg": "#0D1117", "panel": "#161B22", "card": "#1C2333", "input": "#141D2E",
    "border": "#2A3550", "border_hi": "#4A6090",
    "txt": "#E8EDF5", "txt2": "#8B9BB4", "txt3": "#4A5568",
    "gold": "#F5A623", "green": "#00D97E", "green_dk": "#003D22",
    "red": "#FF4560", "red_dk": "#3D0015", "orange": "#FF8C00",
    "cyan": "#00BCD4", "blue": "#2979FF", "purple": "#B388FF",
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
    status = pyqtSignal(str)
    log_line = pyqtSignal(str, str)
    bt_done = pyqtSignal()


class WatcherWorker(threading.Thread):
    def __init__(self, sig: Sig, pip_step: float, symbol: str = WATCH_SYMBOL,
                 tp_pips: float = 0.0, spawn_on: str = "L2 and L3",
                 lot_size: float = 0.01):
        super().__init__(daemon=True)
        self.sig = sig
        self.pip_step = pip_step
        self.symbol = symbol
        self._stop = threading.Event()
        self.prev_names: set = set()
        self.drawn:     dict = {}
        self.follow_enabled: bool = True
        self.tp_pips = tp_pips
        self.spawn_on = spawn_on
        self.lot_size = lot_size
        self.orders_placed: set = set()
        self._last_direction: str = '—'  # 'BUY', 'SELL', or '—'
        # Phase 3: track pending orders by ticket → {level, gen, src, direction, entry}
        self.pending_tracker: dict = {}   # ticket → order_info
        self.spawn_rounds:    int = 0    # how many Phase 3 spawns happened

    def stop(self):  self._stop.set()

    def log(self, msg, lvl="INFO"):
        self.sig.log_line.emit(
            f"{datetime.now().strftime('%H:%M:%S')}  {msg}", lvl)

    @staticmethod
    def _obj_prefix(name: str) -> str:
        import hashlib
        h = hashlib.md5(name.encode()).hexdigest()[:6].upper()
        return f"TB_{h}_"

    def _draw_hline_levels(self, name, price, pip_size):
        """Draw only: gold source + green L3 buy + red L3 sell. Clean chart."""
        prefix = self._obj_prefix(name)
        step = self.pip_step * pip_size
        l3_buy = round(price + step * 3, 5)
        l3_sell = round(price - step * 3, 5)
        cmds = [
            f"DELETE_PREFIX|{prefix}",
            f"DRAW_HLINE|{prefix}SRC|{price:.5f}|16744995|2|0",   # gold solid
            # green dashed
            f"DRAW_HLINE|{prefix}L3B|{l3_buy:.5f}|56702|1|1",
            f"DRAW_HLINE|{prefix}L3S|{l3_sell:.5f}|16728160|1|1",  # red dashed
        ]
        write_commands(cmds, symbol=self.symbol)
        return step

    def _draw_rect_levels(self, name, top, bottom, pip_size):
        """Rectangle center = source. Draw source + L3 lines only."""
        prefix = self._obj_prefix(name)
        step = self.pip_step * pip_size
        center = round((top + bottom) / 2, 5)
        l3_buy = round(center + step * 3, 5)
        l3_sell = round(center - step * 3, 5)
        cmds = [
            f"DELETE_PREFIX|{prefix}",
            f"DRAW_HLINE|{prefix}SRC|{center:.5f}|16744995|2|0",
            f"DRAW_HLINE|{prefix}L3B|{l3_buy:.5f}|56702|1|1",
            f"DRAW_HLINE|{prefix}L3S|{l3_sell:.5f}|16728160|1|1",
        ]
        write_commands(cmds, symbol=self.symbol)
        return step

    def _delete_obj_levels(self, name):
        write_commands(
            [f"DELETE_PREFIX|{self._obj_prefix(name)}"], symbol=self.symbol)

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
                self.log(
                    f"   #{o.ticket} {t:10s} entry={o.price_open:.5f} sl={o.sl:.5f} tp={o.tp:.5f} | {comment}")
        # Active positions
        positions = mt.positions_get(symbol=self.symbol)
        bot_pos = [p for p in (positions or []) if p.magic == MAGIC_NUMBER]
        if bot_pos:
            self.log(f"📊 Active positions ({len(bot_pos)}):")
            for p in sorted(bot_pos, key=lambda x: x.price_open):
                t = "BUY " if p.type == 0 else "SELL"
                pnl = p.profit
                self.log(
                    f"   #{p.ticket} {t} entry={p.price_open:.5f} sl={p.sl:.5f} tp={p.tp:.5f} | PnL={pnl:+.2f}")
        if not bot_orders and not bot_pos:
            self.log("   (no bot orders or positions)")
        self.log(
            f"   Rounds spawned: {self.spawn_rounds}/9 | Tracked pending: {len(self.pending_tracker)}")
        self.log(sep)

    def _place_orders_for_source(self, source_price: float, pip_size: float,
                                 generation: int = 0):
        """Place 6 pending orders and track tickets for Phase 3 monitoring."""
        from core.order_manager import place_level_orders
        try:
            results = place_level_orders(source_price, pip_size,
                                         self.pip_step, self.symbol, generation,
                                         tp_pips=self.tp_pips,
                                         lot_size=self.lot_size)
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
                self.log(
                    f"📋  G{generation}: {ok}/6 placed @ {source_price:.5f} | step={step:.5f}")
                # Show summary: levels above and below
                for r in results:
                    o = r["order"]
                    side = "🟢" if o["type"] == "BUY_STOP" else "🔴"
                    self.log(
                        f"   {side} G{generation}-L{o['level']} {o['type']:10s} entry={o['entry']:.5f} sl={o['sl']:.5f} tp={o['tp']:.5f}")
            else:
                reasons = set(r.get('reason', '?') for r in failed)
                self.log(
                    f"⚠️  G{generation}: {ok}/6 placed | failed: {', '.join(reasons)}", "WARN")
                for r in results:
                    o = r["order"]
                    side = "🟢" if o["type"] == "BUY_STOP" else "🔴"
                    status = "✅" if r["ok"] else f"❌({r.get('reason', '?')[:20]})"
                    self.log(
                        f"   {side} {status} {o['type']:10s} entry={o['entry']:.5f} sl={o['sl']:.5f}")
                if "Market closed" in reasons:
                    self.log(
                        f"💡  Market closed — orders will activate when market opens")
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

        # Log all activations first
        for ticket, info in list(triggered.items()):
            level = info["level"]
            gen = info["generation"]
            entry = info["entry"]
            sl = info["sl"]
            tp = info["tp"]
            direction = info["direction"]
            side = "🟢 BUY" if "BUY" in direction else "🔴 SELL"
            self.log(
                f"⚡  {side} G{gen}-L{level} ACTIVATED | entry={entry:.5f} sl={sl:.5f} tp={tp:.5f} | ticket=#{ticket}", "NEW")

            # Mark l3_activated for pullback
            if level == 3:
                src_reg = getattr(self, "_source_registry", {})
                for reg_v in src_reg.values():
                    if abs(reg_v.get("src", 0) - info.get("source", entry)) < 0.000001:
                        reg_v["l3_activated"] = True
                        self.log(
                            f"   ✅ L3 hit — pullback re-entry now allowed for source {reg_v['src']:.5f}")

            del self.pending_tracker[ticket]

        # Spawn at most ONE new round per scan — pick highest eligible level
        # This prevents cascade explosions when price jumps through multiple levels at once
        import time as _spawn_time
        last_spawn_t = getattr(self, "_last_spawn_time", 0)
        if _spawn_time.time() - last_spawn_t < 2.0:
            return  # cooldown: max one spawn per 2 seconds

        spawn_lvls = []
        if "L2" in self.spawn_on:
            spawn_lvls.append(2)
        if "L3" in self.spawn_on:
            spawn_lvls.append(3)

        # Sort by level descending (prefer L3 over L2) then by gen ascending (prefer lower gen)
        candidates = sorted(
            triggered.items(),
            key=lambda kv: (-kv[1]["level"], kv[1]["generation"])
        )

        for ticket, info in candidates:
            level = info["level"]
            gen = info["generation"]
            entry = info["entry"]
            direction = info["direction"]

            if level not in spawn_lvls:
                continue
            if self.spawn_rounds >= 9:
                self.log(f"⛔  Max 9 rounds reached — no more spawning")
                break

            spawn_key = f"{entry:.5f}_G{gen+1}_{direction[:4]}"
            if not hasattr(self, "spawned_keys"):
                self.spawned_keys = set()
            if spawn_key in self.spawned_keys:
                self.log(
                    f"ℹ️  Already spawned from {entry:.5f} {direction[:4]} — skipping")
                continue

            self.spawned_keys.add(spawn_key)
            self.spawn_rounds += 1
            self._last_spawn_time = _spawn_time.time()
            new_gen = gen + 1
            self.log(
                f"🔄  Phase 3 round {self.spawn_rounds}/9 — "
                f"G{gen}-L{level} {direction} @ {entry:.5f} → "
                f"new source G{new_gen} @ {entry:.5f}", "NEW")
            spawn_name = f"TB_SPAWN_G{new_gen}_R{self.spawn_rounds}"
            self._draw_hline_levels(spawn_name, entry, pip)
            self._place_orders_for_source(entry, pip, generation=new_gen)
            self._log_position_map(_mt5)
            break  # Only ONE spawn per scan cycle

    def run(self):
        if not cw.connect_mt5():
            self.log(
                "❌  MT5 connection failed — is MT5 running? Check login/server in config.py", "ERROR")
            self.sig.status.emit("❌  MT5 connection failed")
            return
        pip = get_pip_size(self.symbol)

        # Log minimum stop distance so user knows if pip_step is too small
        import MetaTrader5 as _mt5
        _mt5.symbol_select(self.symbol, True)
        _info = _mt5.symbol_info(self.symbol)
        if _info:
            min_dist = _info.trade_stops_level * _info.point
            min_pips = min_dist / pip if pip > 0 else 0
            self.log(
                f"✅  Connected | {self.symbol} | pip={pip:.5f} | step={self.pip_step} pips | TP={self.tp_pips:.0f}pips | spawn={self.spawn_on}")
            self.log(
                f"📐  Min stop distance: {min_dist:.5f} = {min_pips:.1f} pips  (pip_step must be > {min_pips:.1f})")
            if self.pip_step * pip <= min_dist:
                self.log(
                    f"⚠️  pip_step={self.pip_step} is too small! L1 SL will fail. Increase to >{min_pips:.0f} pips.", "WARN")
        else:
            self.log(
                f"✅  Connected | {self.symbol} | pip={pip:.5f} | step={self.pip_step} pips")

        self.sig.status.emit("🟢  Running")

        # source_registry: name → {"src": float, "triggered": bool, "gen": int}
        # Orders are placed ONLY when price touches the source line
        source_registry = {}
        self._source_registry = source_registry  # share with _check_phase3_activations
        self.source_registry = source_registry  # expose to GUI

        while not self._stop.is_set():
          try:
            path = cw.find_objects_file(self.symbol)
            if path and path != getattr(self, "_last_path", None):
                self._last_path = path
                self.log(f"📂  Reading EA file: {path}")
                # Check if file symbol matches bot symbol
                try:
                    with open(path, encoding="utf-8", errors="ignore") as _ff:
                        first = _ff.read(100)
                    for _line in first.splitlines():
                        if _line.startswith("SYMBOL:"):
                            file_sym = _line.split(":", 1)[1].strip()
                            if file_sym != self.symbol:
                                self.log(
                                    f"⚠️  File symbol is '{file_sym}' but bot is set to '{self.symbol}'. "
                                    f"Change bot symbol to '{file_sym}' or attach EA to the {self.symbol} chart.", "WARN")
                            break
                except Exception:
                    pass
            if not path:
                self.sig.status.emit("⏳  Waiting for EA…")
                self._stop.wait(min(SCAN_INTERVAL_SEC, 1))
                continue

            # Check file age — skip processing if EA has stopped writing
            import os as _os
            import time as _time
            try:
                _file_age = _time.time() - _os.path.getmtime(path)
            except Exception:
                _file_age = 0

            if _file_age > 15:
                warn_interval = 30  # warn every 30s not every scan
                if not getattr(self, "_ea_stale_warned", False) or int(_file_age) % warn_interval < 1:
                    self._ea_stale_warned = True
                    self.log(
                        f"⚠️  EA file is {_file_age:.0f}s old — EA not running. "
                        f"In MT5: Navigator (Ctrl+N) → Expert Advisors → "
                        f"drag ObjectExporter onto the {self.symbol} chart.", "WARN")
                self.sig.status.emit(
                    f"⚠️  EA stopped ({_file_age:.0f}s) — add EA to chart")
                self._stop.wait(min(SCAN_INTERVAL_SEC, 1))
                continue
            else:
                if getattr(self, "_ea_stale_warned", False):
                    self.log("✅  EA is writing again — resuming", "INFO")
                self._ea_stale_warned = False

            parsed = cw.parse_objects_file(path)
            if len(parsed) == 4:
                trader, auto, ea_sym, candle = parsed
            elif len(parsed) == 3:
                trader, auto, ea_sym, candle = parsed[0], parsed[1], parsed[2], {
                }
            else:
                trader, auto, ea_sym, candle = parsed[0], parsed[1], None, {}

            if ea_sym:
                self.sig.log_line.emit(f"__EA_SYM__{ea_sym}", "EA")

            if ea_sym and ea_sym != self.symbol:
                if ea_sym != getattr(self, "_last_ea_warn", None):
                    self._last_ea_warn = ea_sym
                    self.log(
                        f"⚠️  EA is on {ea_sym} chart — not {self.symbol}. Move EA or change symbol.", "WARN")
                self._stop.wait(min(SCAN_INTERVAL_SEC, 1))
                continue

            self.sig.new_objects.emit(trader, auto)
            # Debug: log trader objects every 10 scans to track price changes
            if not hasattr(self, '_dbg_count'):
                self._dbg_count = 0
            self._dbg_count += 1
            # Log candle state every 30s so user can monitor without spam
            if self._dbg_count % 30 == 0:
                import os as _os
                import time as _time
                bid = candle.get("BID", 0)
                ch = candle.get("CANDLE_H", 0)
                cl = candle.get("CANDLE_L", 0)
                # Show file age so we know if EA is updating it
                file_age = ""
                if path:
                    try:
                        mtime = _os.path.getmtime(path)
                        age = int(_time.time() - mtime)
                        file_age = f" | file_age={age}s"
                    except:
                        pass
                waiting = [f"[{k[:15]}]={v['src']:.5f}" for k,
                           v in source_registry.items() if not v.get("triggered")]
                # Also show ALL trader object prices to detect moves
                all_objs = " | ".join(
                    f"{o.name[:20]}={o.price1:.5f}" for o in trader if o.is_hline)
                if waiting:
                    obj_prices = " | ".join(
                        f"{o.name[:15]}={o.price1:.5f}" for o in trader if o.is_hline and "TB_" not in o.name)
                    self.log(
                        f"⏳  Watching: {', '.join(waiting)} | bid={bid:.5f} H={ch:.5f} L={cl:.5f}{file_age}")
                # Object prices shown inline with waiting log (removed separate spam line)
            self.sig.log_line.emit(f"__CANDLE__{repr(candle)}", "RF")
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
                        self.log(
                            f"⏭  [{n[:25]}] @ {obj.price1:.5f} skipped (current={current_price:.5f}, ratio={ratio:.2f})")
                        continue

                if obj.is_hline:
                    src = obj.price1
                    self._draw_hline_levels(n, src, pip)
                    self.drawn[n] = src
                    # Record the CURRENT candle time — only check touch on FUTURE candles
                    cur_candle_t = candle.get("CANDLE_T", 0)
                    source_registry[n] = {"src": src, "triggered": False, "gen": 0,
                                          "registered_at_candle": cur_candle_t, "last_prev_t": 0}
                    self.log(
                        f"🆕  HLINE [{n[:25]}] @ {src:.5f} | 3+3 levels drawn | waiting for NEXT candle to touch line")

                elif obj.is_rectangle:
                    if not obj.rect_valid:
                        self.drawn[n] = "INVALID"
                        self.log(
                            f"⚠️  [{n[:25]}] rectangle has zero height — skipping")
                        continue
                    center = round((obj.rect_top + obj.rect_bottom) / 2, 5)
                    self._draw_hline_levels(n, center, pip)
                    self.drawn[n] = center
                    source_registry[n] = {
                        "src": center, "triggered": False, "gen": 0, "last_prev_t": 0}
                    self.log(
                        f"🆕  RECT [{n[:25]}] center={center:.5f} (h={obj.rect_height:.5f}) | 3+3 levels drawn | waiting for touch")

            # ── CHECK PREVIOUS CLOSED CANDLE TOUCHES SOURCE LINES ──
            # Use the LAST CLOSED candle (PREV_*) not the forming one.
            # This prevents same-candle buy+sell activation.
            cur_candle_t = candle.get("CANDLE_T", 0)
            cur_h = candle.get("CANDLE_H", current_price)
            cur_l = candle.get("CANDLE_L", current_price)
            cur_c = candle.get("CANDLE_C", current_price)
            cur_o = candle.get("CANDLE_O", current_price)
            prev_h = candle.get("PREV_H", 0.0)
            prev_l = candle.get("PREV_L", 0.0)
            prev_c = candle.get("PREV_C", 0.0)
            prev_o = candle.get("PREV_O", 0.0)

            for n, reg in list(source_registry.items()):
                if reg["triggered"]:
                    # Pullback re-entry rules:
                    # 1. L3 must have been activated first
                    # 2. Price must have moved AWAY from the line (a candle that did NOT touch it)
                    # 3. Then price RETURNS and a new candle touches it again
                    # This prevents firing every minute on M1
                    if not reg.get("l3_activated", False):
                        continue

                    src = reg["src"]
                    prev_t_now = candle.get("PREV_T", 0)

                    # Track whether price was away from the line
                    if prev_h > 0 and prev_l > 0:
                        if prev_l > src or prev_h < src:
                            # This candle did NOT touch the line — price was away
                            reg["price_was_away"] = True
                        elif reg.get("price_was_away", False):
                            # Price was away AND now it's back — genuine pullback
                            last_rb = reg.get("last_pullback_t", 0)
                            if prev_t_now > last_rb:
                                reg["last_pullback_t"] = prev_t_now
                                reg["price_was_away"] = False  # reset
                                side = "from above" if prev_o > src else "from below"
                                self.log(
                                    f"🔁  Pullback to source [{n[:20]}] @ {src:.5f} {side} | "
                                    f"placing fresh G0 round", "NEW")
                                self._place_orders_for_source(
                                    src, pip, generation=0)
                    continue

                src = reg["src"]
                registered_at = reg.get("registered_at_candle", 0)

                # Touch detection: check BOTH current forming candle AND previous closed candle.
                # Use whichever shows a touch, but skip the candle the line was drawn on.
                touched = False
                touch_h, touch_l, touch_c, touch_o = 0, 0, 0, 0

                # Check current forming candle (faster response, same-candle guard)
                if cur_candle_t != registered_at and cur_h > 0:
                    if cur_l <= src <= cur_h:
                        touched = True
                        touch_h, touch_l, touch_c, touch_o = cur_h, cur_l, cur_c, cur_o

                # Check previous closed candle if current didn't touch
                if not touched and prev_h > 0:
                    prev_t_val = candle.get("PREV_T", 0)
                    last_checked = reg.get("last_prev_t", 0)
                    # Only check if this is a new prev candle AND it's after registration
                    if prev_t_val > last_checked and prev_t_val > registered_at:
                        reg["last_prev_t"] = prev_t_val
                        if prev_l <= src <= prev_h:
                            touched = True
                            touch_h, touch_l, touch_c, touch_o = prev_h, prev_l, prev_c, prev_o

                if touched:
                    reg["triggered"] = True
                    reg["last_touch_t"] = candle.get(
                        "PREV_T", 0)  # record when touch happened
                    reg["last_pullback_t"] = candle.get(
                        "PREV_T", 0)  # prevent immediate pullback
                    side = "from above" if touch_o > src else "from below"
                    direction = "BUY" if touch_c > src else "SELL"
                    self._last_direction = direction
                    dir_icon = "🟢" if direction == "BUY" else "🔴"
                    self.log(
                        f"🎯  [{n[:20]}] touched @ {src:.5f} {side} | "
                        f"C={touch_c:.5f} → {dir_icon} {direction} bias | placing orders", "NEW")
                    self._place_orders_for_source(
                        src, pip, generation=reg["gen"])
                    reg["cancel_opposite"] = direction

            # ── CANCEL OPPOSITE-SIDE ORDERS (directional filter) ──────
            for n, reg in list(source_registry.items()):
                if "cancel_opposite" not in reg:
                    continue
                direction = reg.pop("cancel_opposite")
                import MetaTrader5 as _mt5c
                pending = _mt5c.orders_get(symbol=self.symbol) or []
                cancelled = 0
                for o in pending:
                    if o.magic != MAGIC_NUMBER:
                        continue
                    is_buy_stop = o.type == 2  # ORDER_TYPE_BUY_STOP
                    is_sell_stop = o.type == 4  # ORDER_TYPE_SELL_STOP
                    # If BUY bias → cancel sell-stops. If SELL bias → cancel buy-stops.
                    should_cancel = (direction == "BUY" and is_sell_stop) or (
                        direction == "SELL" and is_buy_stop)
                    if should_cancel:
                        res = _mt5c.order_send({
                            "action": _mt5c.TRADE_ACTION_REMOVE,
                            "order":  o.ticket,
                        })
                        if res and res.retcode == _mt5c.TRADE_RETCODE_DONE:
                            cancelled += 1
                if cancelled > 0:
                    dir_icon = "🟢" if direction == "BUY" else "🔴"
                    self.log(
                        f"🗑️  {dir_icon} {direction} bias: cancelled {cancelled} opposite-side orders")

            # ── PHASE 3: CHECK ACTIVATIONS ───────────────────────────
            self._check_phase3_activations(pip)

            # ── RISK-FREE SL CHECK ────────────────────────────────
            self.sig.log_line.emit("__CHECK_RF__", "RF")

            # ── FOLLOW MOVED OBJECTS ───────────────────────────────
            if self.follow_enabled:
                for obj in trader:
                    n = obj.name
                    if n not in self.drawn or self.drawn[n] in ("INVALID", "WRONG_SYMBOL"):
                        continue
                    stored = self.drawn[n]
                    if obj.is_hline and isinstance(stored, float):
                        diff = abs(obj.price1 - stored)
                        if diff > 0.000001:  # reduced threshold from 0.00001
                            new_src = obj.price1
                            self.log(
                                f"↕️  [{n[:25]}] moved {stored:.5f}→{new_src:.5f} — redrawing levels")
                            self._draw_hline_levels(n, new_src, pip)
                            self.drawn[n] = new_src
                            if n in source_registry:
                                source_registry[n]["src"] = new_src
                                # reset touch
                                source_registry[n]["triggered"] = False
                                # wait for next candle after move
                                source_registry[n]["registered_at_candle"] = cur_candle_t
                        # Debug: log current vs stored every 5s
                        # (uncomment to debug): self.log(f"DBG [{n[:15]}] stored={stored:.5f} cur={obj.price1:.5f} diff={diff:.6f}")

            self.prev_names = self.prev_names | cur
            self._stop.wait(min(SCAN_INTERVAL_SEC, 1))

          except Exception as _e:
            import traceback as _tb
            self.log(f"💥 Watcher error: {type(_e).__name__}: {_e}", "ERROR")
            for _line in _tb.format_exc().strip().splitlines():
                self.log(f"   {_line}", "ERROR")
            self._stop.wait(min(SCAN_INTERVAL_SEC, 1))

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
        self._sig = Sig()
        self._sig.new_objects.connect(self._on_objects)
        self._sig.status.connect(self._on_status)
        self._sig.log_line.connect(self._on_log)
        self._sig.bt_done.connect(self._display_bt_result)
        self._trader_objects = []
        self._pip_step = PIP_STEP
        self._bt_running = False  # guard against double-run
        self._session_events = []  # list of session event dicts
        self._session_start = datetime.now()
        self._build_ui()
        QTimer.singleShot(100, self._init_mt5_price)
        self._pt = QTimer()
        self._pt.timeout.connect(self._refresh_price)
        self._pt.start(1000)

    # ─────────────────────────────── UI BUILD ────────────────────

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        vl = QVBoxLayout(root)
        vl.setSpacing(6)
        vl.setContentsMargins(10, 10, 10, 10)
        vl.addWidget(self._header())
        spl = QSplitter(Qt.Horizontal)
        spl.addWidget(self._left_panel())
        spl.addWidget(self._right_panel())
        spl.setSizes([370, 730])
        vl.addWidget(spl, 1)
        vl.addWidget(self._status_bar())

    def _header(self):
        w = QFrame()
        w.setStyleSheet(
            f"background:{C['panel']};border:1px solid {C['border']};border-radius:6px;")
        hl = QHBoxLayout(w)
        hl.setContentsMargins(14, 8, 14, 8)
        t = QLabel(
            "📈  TraderBot  <span style='color:#4A5568;font-size:10px;'>v1.0</span>")
        t.setStyleSheet(f"color:{C['gold']};font-size:16px;font-weight:bold;")
        hl.addWidget(t)
        hl.addStretch()
        self.lbl_price = QLabel("Price: —")
        self.lbl_price.setStyleSheet(
            f"color:{C['cyan']};font-family:Consolas;font-size:14px;font-weight:bold;")
        hl.addWidget(self.lbl_price)
        hl.addWidget(self._vline())
        self.lbl_sym = QLabel(WATCH_SYMBOL)
        self.lbl_sym.setStyleSheet(f"color:{C['txt2']};font-size:12px;")
        hl.addWidget(self.lbl_sym)
        hl.addWidget(self._vline())
        self.lbl_ea_chart = QLabel("EA: —")
        self.lbl_ea_chart.setStyleSheet(f"color:{C['txt3']};font-size:10px;")
        self.lbl_ea_chart.setToolTip(
            "Which chart the ObjectExporter EA is currently on")
        hl.addWidget(self.lbl_ea_chart)
        hl.addWidget(self._vline())
        self.lbl_status = QLabel("⚫  Stopped")
        self.lbl_status.setStyleSheet(f"color:{C['txt2']};font-size:11px;")
        hl.addWidget(self.lbl_status)
        hl.addWidget(self._vline())
        # Strategy phase indicator
        self.lbl_phase = QLabel("Phase: —")
        self.lbl_phase.setStyleSheet(
            f"color:{C['txt3']};font-size:10px;font-family:Consolas;")
        hl.addWidget(self.lbl_phase)
        return w

    def _left_panel(self):
        w = QWidget()
        vl = QVBoxLayout(w)
        vl.setSpacing(8)
        vl.setContentsMargins(0, 0, 4, 0)

        # ── Controls ─────────────────────────────────────────────
        grp = QGroupBox("⚙️  Bot Control")
        cl = QVBoxLayout(grp)
        cl.setSpacing(4)

        def _lbl(text, tooltip=""):
            l = QLabel(text)
            l.setStyleSheet(
                f"color:{C['txt2']};font-size:11px;min-width:90px;")
            if tooltip:
                l.setToolTip(tooltip)
            return l

        def _row(label, widget, tooltip=""):
            hl = QHBoxLayout()
            hl.setSpacing(8)
            hl.addWidget(_lbl(label, tooltip))
            widget.setFixedWidth(160)
            hl.addWidget(widget)
            hl.addStretch()
            cl.addLayout(hl)

        # Symbol
        self.sym_combo = QComboBox()
        self.sym_combo.setEditable(True)
        self.sym_combo.addItems(["XAUUSD_i", "EURUSD_i", "GBPUSD_i",
                                 "XAUUSD", "EURUSD", "GBPUSD", "NAS100", "US30", "BTCUSD"])
        self.sym_combo.setCurrentText("EURUSD")
        self.sym_combo.currentTextChanged.connect(self._on_symbol_changed)
        _row("🎯 Symbol:", self.sym_combo, "The symbol to watch on MT5")

        # Pip step
        self.spin_pip = QDoubleSpinBox()
        self.spin_pip.setRange(0.1, 500.0)
        self.spin_pip.setSingleStep(1.0)
        self.spin_pip.setValue(PIP_STEP)
        self.spin_pip.setDecimals(1)
        _row("📏 Pip step:", self.spin_pip,
             "Distance between each level (L1/L2/L3) in pips")

        # TP pips with checkbox
        tp_row = QHBoxLayout()
        tp_row.setSpacing(8)
        self.chk_tp = QCheckBox()
        self.chk_tp.setChecked(False)
        self.chk_tp.setToolTip(
            "Enable fixed TP. Unchecked = no TP set (orders run until SL or manual close)")
        self.chk_tp.setStyleSheet(f"color:{C['txt2']};")
        tp_row.addWidget(_lbl("🎯 TP pips:"))
        tp_row.addWidget(self.chk_tp)
        self.spin_tp = QDoubleSpinBox()
        self.spin_tp.setRange(1, 1000.0)
        self.spin_tp.setSingleStep(5.0)
        self.spin_tp.setValue(50)
        self.spin_tp.setDecimals(1)
        self.spin_tp.setEnabled(False)
        self.chk_tp.toggled.connect(self.spin_tp.setEnabled)
        tp_row.addWidget(self.spin_tp)
        tp_row.addStretch()
        cl.addLayout(tp_row)

        # Lot size
        self.spin_lot = QDoubleSpinBox()
        self.spin_lot.setRange(0.01, 100.0)
        self.spin_lot.setSingleStep(0.01)
        self.spin_lot.setValue(LOT_SIZE)
        self.spin_lot.setDecimals(2)
        _row("📦 Lot size:", self.spin_lot, "Lot size per order")

        # Spawn level
        self.combo_spawn = QComboBox()
        self.combo_spawn.addItems(["L2 only", "L3 only", "L2 and L3"])
        self.combo_spawn.setCurrentText("L2 and L3")
        _row("🔄 Spawn on:", self.combo_spawn,
             "Which activated level spawns a new cascading round")

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color:{C['border']};")
        cl.addWidget(sep)

        # Start / Stop buttons
        self.btn_start = QPushButton("▶  Start Watcher")
        self.btn_start.setObjectName("btn_start")
        self.btn_start.setMinimumHeight(36)
        self.btn_start.clicked.connect(self._start)
        cl.addWidget(self.btn_start)

        self.btn_stop = QPushButton("■  Stop Watcher")
        self.btn_stop.setObjectName("btn_stop")
        self.btn_stop.setMinimumHeight(36)
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop)
        cl.addWidget(self.btn_stop)

        self.chk_follow = QCheckBox("🔗  Follow object when moved")
        self.chk_follow.setChecked(True)
        self.chk_follow.setStyleSheet(
            f"color:{C['txt2']};font-size:10px;padding:2px 0;")
        self.chk_follow.setToolTip(
            "Level lines redraw if you drag the drawn object")
        cl.addWidget(self.chk_follow)
        vl.addWidget(grp)

        # ── Strategy summary ─────────────────────────────────────
        grp_strat = QGroupBox("📊  Strategy State")
        sv = QGridLayout(grp_strat)
        sv.setSpacing(4)
        sv.setContentsMargins(8, 6, 8, 6)

        def _stat_label(text, color):
            l = QLabel(text)
            l.setStyleSheet(
                f"color:{color};font-family:Consolas;font-size:11px;font-weight:bold;")
            return l

        def _stat_key(text):
            l = QLabel(text)
            l.setStyleSheet(f"color:{C['txt3']};font-size:10px;")
            return l

        self.lbl_source_price = _stat_label("—", C['gold'])
        self.lbl_rounds_info = _stat_label("0 / 9", C['cyan'])
        self.lbl_waiting = _stat_label("Draw a line on chart", C['txt3'])
        self.lbl_direction = _stat_label("—", C['txt2'])

        sv.addWidget(_stat_key("Source:"),    0, 0)
        sv.addWidget(self.lbl_source_price,   0, 1)
        sv.addWidget(_stat_key("Rounds:"),    1, 0)
        sv.addWidget(self.lbl_rounds_info,    1, 1)
        sv.addWidget(_stat_key("Direction:"), 2, 0)
        sv.addWidget(self.lbl_direction,      2, 1)
        sv.addWidget(_stat_key("Status:"),    3, 0)
        sv.addWidget(self.lbl_waiting,        3, 1)
        sv.setColumnStretch(1, 1)
        vl.addWidget(grp_strat)

        # ── Orders ───────────────────────────────────────────────
        grp2 = QGroupBox("Live Orders")
        ol = QVBoxLayout(grp2)
        self.btn_place = QPushButton("🎯  Place Buy/Sell Stops")
        self.btn_place.setObjectName("btn_orders")
        self.btn_place.setMinimumHeight(34)
        self.btn_place.setEnabled(False)
        self.btn_place.clicked.connect(self._place_orders)
        ol.addWidget(self.btn_place)
        self.btn_cancel = QPushButton("🗑️  Cancel All Bot Orders")
        self.btn_cancel.setObjectName("btn_cancel")
        self.btn_cancel.clicked.connect(self._cancel_orders)
        ol.addWidget(self.btn_cancel)

        # ── Risk-Free section ─────────────────────────────────────
        grp_rf = QGroupBox("🛡️  Risk-Free Mode")
        rf_layout = QVBoxLayout(grp_rf)
        rf_layout.setSpacing(6)

        # Row 1: side selector
        rf_row1 = QHBoxLayout()
        rf_row1.addWidget(QLabel("Keep side:"))
        self.combo_rf_side = QComboBox()
        self.combo_rf_side.addItems(["BUY (keep buys)", "SELL (keep sells)"])
        rf_row1.addWidget(self.combo_rf_side)
        rf_layout.addLayout(rf_row1)

        # Row 2: SL price input + update button
        rf_row2 = QHBoxLayout()
        rf_row2.addWidget(QLabel("Exit price:"))
        self.edit_rf_price = QLineEdit()
        self.edit_rf_price.setPlaceholderText("e.g. 1.16420")
        self.edit_rf_price.setToolTip(
            "Price at which all kept positions close.\n"
            "Leave blank to use average entry of kept positions.\n"
            "Can be changed while RF is active using Update SL.")
        self.edit_rf_price.setFixedWidth(95)
        rf_row2.addWidget(self.edit_rf_price)
        self.btn_rf_update = QPushButton("📍 Update SL")
        self.btn_rf_update.setMinimumHeight(24)
        self.btn_rf_update.setEnabled(False)
        self.btn_rf_update.setToolTip(
            "Move the SL exit price while RF is active")
        self.btn_rf_update.clicked.connect(self._update_rf_sl)
        rf_row2.addWidget(self.btn_rf_update)
        rf_row2.addStretch()
        rf_layout.addLayout(rf_row2)

        # Row 3: Activate button
        self.btn_rf = QPushButton("🛡️  Activate Risk-Free")
        self.btn_rf.setObjectName("btn_start")
        self.btn_rf.setMinimumHeight(32)
        self.btn_rf.clicked.connect(self._activate_risk_free)
        rf_layout.addWidget(self.btn_rf)

        self.lbl_rf_status = QLabel("Not active")
        self.lbl_rf_status.setStyleSheet(f"color:{C['txt3']};font-size:10px;")
        rf_layout.addWidget(self.lbl_rf_status)

        ol.addWidget(grp_rf)
        vl.addWidget(grp2)

        # ── Levels table ─────────────────────────────────────────
        grp3 = QGroupBox("Detected Levels")
        ll = QVBoxLayout(grp3)
        self.lvl_tbl = QTableWidget(0, 3)
        self.lvl_tbl.setHorizontalHeaderLabels(["Level", "Price", "Dist"])
        self.lvl_tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.lvl_tbl.setAlternatingRowColors(True)
        self.lvl_tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        self.lvl_tbl.verticalHeader().setVisible(False)
        ll.addWidget(self.lvl_tbl)
        vl.addWidget(grp3, 1)
        return w

    def _right_panel(self):
        w = QWidget()
        vl = QVBoxLayout(w)
        vl.setSpacing(0)
        vl.setContentsMargins(4, 0, 0, 0)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._tab_log(),       "📋  Log")
        self.tabs.addTab(self._tab_orders(),    "📊  Orders")
        self.tabs.addTab(self._tab_scoreboard(), "🏆  Scoreboard")
        self.tabs.addTab(self._tab_backtest(),  "🔬  Backtest")
        self.tabs.addTab(self._tab_report(),    "📁  Session Report")
        vl.addWidget(self.tabs)
        return w

    def _tab_log(self):
        w = QWidget()
        vl = QVBoxLayout(w)
        vl.setContentsMargins(4, 4, 4, 4)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setLineWrapMode(QTextEdit.NoWrap)
        vl.addWidget(self.log_view)
        btn = QPushButton("Clear")
        btn.setFixedHeight(24)
        btn.clicked.connect(self.log_view.clear)
        vl.addWidget(btn)
        return w

    def _tab_orders(self):
        w = QWidget()
        vl = QVBoxLayout(w)
        vl.setContentsMargins(6, 6, 6, 6)
        vl.setSpacing(6)

        # ── Summary bar ───────────────────────────────────────────
        sum_row = QHBoxLayout()
        sum_row.setSpacing(8)

        def _mini_card(key, label, color):
            f = QFrame()
            f.setStyleSheet(
                f"background:{C['card']};border:1px solid {C['border']};border-radius:6px;")
            fv = QVBoxLayout(f)
            fv.setContentsMargins(8, 4, 8, 4)
            fv.setSpacing(0)
            lt = QLabel(label)
            lt.setStyleSheet(
                f"color:{C['txt3']};font-size:8px;font-weight:bold;")
            lt.setAlignment(Qt.AlignCenter)
            lv = QLabel("—")
            lv.setStyleSheet(
                f"color:{color};font-size:15px;font-weight:bold;font-family:Consolas;")
            lv.setAlignment(Qt.AlignCenter)
            fv.addWidget(lt)
            fv.addWidget(lv)
            self._ord_summary[key] = lv
            return f

        self._ord_summary = {}
        sum_row.addWidget(_mini_card("pending",  "PENDING",   C['cyan']))
        sum_row.addWidget(_mini_card("active",   "ACTIVE",    C['gold']))
        sum_row.addWidget(_mini_card("buy_pos",  "BUY POS",   C['green']))
        sum_row.addWidget(_mini_card("sell_pos", "SELL POS",  C['red']))
        sum_row.addWidget(_mini_card("total_pnl", "OPEN P&L",  C['purple']))
        sum_row.addWidget(_mini_card("rounds",   "ROUNDS",    C['txt2']))
        vl.addLayout(sum_row)

        # ── Pending orders table ──────────────────────────────────
        grp_pending = QGroupBox("🔵  Pending Orders")
        pv = QVBoxLayout(grp_pending)
        self.ord_pending = QTableWidget(0, 7)
        self.ord_pending.setHorizontalHeaderLabels(
            ["Gen", "Lvl", "Type", "Entry", "SL", "TP", "Pips SL"])
        self.ord_pending.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.ord_pending.setAlternatingRowColors(True)
        self.ord_pending.setEditTriggers(QTableWidget.NoEditTriggers)
        self.ord_pending.verticalHeader().setVisible(False)
        self.ord_pending.setMaximumHeight(220)
        pv.addWidget(self.ord_pending)
        vl.addWidget(grp_pending)

        # ── Active positions table ────────────────────────────────
        grp_active = QGroupBox("📊  Active Positions")
        av = QVBoxLayout(grp_active)
        self.ord_active = QTableWidget(0, 7)
        self.ord_active.setHorizontalHeaderLabels(
            ["Gen", "Lvl", "Type", "Entry", "SL", "TP", "P&L"])
        self.ord_active.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.ord_active.setAlternatingRowColors(True)
        self.ord_active.setEditTriggers(QTableWidget.NoEditTriggers)
        self.ord_active.verticalHeader().setVisible(False)
        av.addWidget(self.ord_active)
        vl.addWidget(grp_active, 1)

        # ── Refresh button ────────────────────────────────────────
        btn_ref = QPushButton("🔄  Refresh")
        btn_ref.setFixedHeight(26)
        btn_ref.clicked.connect(self._refresh_orders_tab)
        vl.addWidget(btn_ref)

        # Auto-refresh every 2s
        self._ord_timer = QTimer()
        self._ord_timer.timeout.connect(self._refresh_orders_tab)
        self._ord_timer.start(2000)

        return w

    def _tab_scoreboard(self):
        w = QWidget()
        vl = QVBoxLayout(w)
        vl.setContentsMargins(8, 8, 8, 8)
        vl.setSpacing(8)

        # ── Summary cards row ─────────────────────────────────────
        cards_row = QHBoxLayout()
        cards_row.setSpacing(6)

        def _card(key, label, color):
            card = QFrame()
            card.setStyleSheet(
                f"background:{C['card']};border:1px solid {C['border']};border-radius:8px;")
            cv = QVBoxLayout(card)
            cv.setContentsMargins(12, 8, 12, 8)
            cv.setSpacing(2)
            lt = QLabel(label)
            lt.setStyleSheet(
                f"color:{C['txt3']};font-size:9px;font-weight:bold;letter-spacing:1px;")
            lt.setAlignment(Qt.AlignCenter)
            lv = QLabel("—")
            lv.setStyleSheet(
                f"color:{color};font-size:20px;font-weight:bold;font-family:Consolas;")
            lv.setAlignment(Qt.AlignCenter)
            cv.addWidget(lt)
            cv.addWidget(lv)
            self._sb_cards[key] = lv
            return card

        self._sb_cards = {}
        cards_row.addWidget(_card("start_bal",  "START BALANCE", C['txt2']))
        cards_row.addWidget(_card("cur_bal",    "CURRENT BAL",   C['cyan']))
        cards_row.addWidget(_card("pnl",        "TOTAL P&L",     C['gold']))
        cards_row.addWidget(_card("wins",       "WINS",          C['green']))
        cards_row.addWidget(_card("losses",     "LOSSES",        C['red']))
        cards_row.addWidget(_card("ratio",      "WIN RATE",      C['purple']))
        vl.addLayout(cards_row)

        # ── Closed positions table ────────────────────────────────
        grp_hist = QGroupBox("Closed Positions")
        hl = QVBoxLayout(grp_hist)
        self.sb_history = QTableWidget(0, 7)
        self.sb_history.setHorizontalHeaderLabels(
            ["Ticket", "Type", "Entry", "Close", "Pips", "Profit", "Time"])
        self.sb_history.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.sb_history.setAlternatingRowColors(True)
        self.sb_history.setEditTriggers(QTableWidget.NoEditTriggers)
        self.sb_history.verticalHeader().setVisible(False)
        hl.addWidget(self.sb_history)
        vl.addWidget(grp_hist, 1)

        # ── Refresh button ────────────────────────────────────────
        btn_refresh = QPushButton("🔄  Refresh Scoreboard")
        btn_refresh.setObjectName("btn_bt")
        btn_refresh.clicked.connect(self._refresh_scoreboard)
        vl.addWidget(btn_refresh)

        # Auto-refresh every 5 seconds
        self._sb_timer = QTimer()
        self._sb_timer.timeout.connect(self._refresh_scoreboard)
        self._sb_timer.start(5000)

        return w

    def _refresh_scoreboard(self):
        """Pull closed deals from MT5 and update scoreboard."""
        try:
            import MetaTrader5 as _mt5
            if not _mt5.initialize():
                return
            _mt5.login(MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER)

            acc = _mt5.account_info()
            if not acc:
                return

            cur_bal = acc.balance
            equity = acc.equity

            # Start balance — store once
            if not hasattr(self, "_start_balance"):
                self._start_balance = cur_bal

            start_bal = self._start_balance
            pnl = cur_bal - start_bal

            # Get closed deals (history) for this magic number
            from datetime import datetime, timezone, timedelta
            since = datetime.now(timezone.utc) - timedelta(days=30)
            deals = _mt5.history_deals_get(since, datetime.now(timezone.utc))

            bot_deals = []
            if deals:
                for d in deals:
                    if d.magic == MAGIC_NUMBER and d.entry == 1:  # entry=1 means close/out deal
                        bot_deals.append(d)

            wins = sum(1 for d in bot_deals if d.profit > 0)
            losses = sum(1 for d in bot_deals if d.profit < 0)
            total = wins + losses
            ratio = f"{wins/total*100:.0f}%" if total > 0 else "—"

            # Update cards
            self._sb_cards["start_bal"].setText(f"${start_bal:.2f}")
            self._sb_cards["cur_bal"].setText(f"${cur_bal:.2f}")
            pnl_color = C['green'] if pnl >= 0 else C['red']
            self._sb_cards["pnl"].setText(f"{'+'if pnl >= 0 else ''}{pnl:.2f}")
            self._sb_cards["pnl"].setStyleSheet(
                f"color:{pnl_color};font-size:20px;font-weight:bold;font-family:Consolas;")
            self._sb_cards["wins"].setText(str(wins))
            self._sb_cards["losses"].setText(str(losses))
            self._sb_cards["ratio"].setText(ratio)

            # Fill history table (most recent first)
            self.sb_history.setRowCount(0)
            sym = self.sym_combo.currentText().strip() or WATCH_SYMBOL
            for d in sorted(bot_deals, key=lambda x: x.time, reverse=True):
                pip = get_pip_size(sym)
                row = self.sb_history.rowCount()
                self.sb_history.insertRow(row)
                t = "BUY" if d.type == 0 else "SELL"
                pips_val = d.profit / \
                    (LOT_SIZE * pip * 100000) if pip > 0 else 0
                clr = QColor(C['green'] if d.profit > 0 else C['red'])
                close_time = datetime.fromtimestamp(
                    d.time).strftime("%m-%d %H:%M")
                vals = [str(d.deal), t, f"{d.price:.5f}",
                        f"{d.price:.5f}", f"{pips_val:+.1f}",
                        f"{d.profit:+.2f}", close_time]
                for c, v in enumerate(vals):
                    it = QTableWidgetItem(v)
                    it.setForeground(clr)
                    self.sb_history.setItem(row, c, it)

        except Exception as e:
            pass  # Scoreboard refresh errors are non-critical

    def _tab_backtest(self):
        w = QWidget()
        vl = QVBoxLayout(w)
        vl.setContentsMargins(8, 8, 8, 8)
        vl.setSpacing(6)

        # ── Settings ──────────────────────────────────────────────
        grp_set = QGroupBox("Settings")
        sl = QHBoxLayout(grp_set)
        sl.setSpacing(10)
        sl.addWidget(QLabel("Symbol:"))
        self.bt_symbol = QComboBox()
        self.bt_symbol.setEditable(True)
        self.bt_symbol.addItems(
            [WATCH_SYMBOL, "EURUSD", "GBPUSD", "US30", "NAS100", "XAUUSD"])
        self.bt_symbol.setCurrentText(WATCH_SYMBOL)
        self.bt_symbol.setFixedWidth(110)
        sl.addWidget(self.bt_symbol)
        sl.addWidget(QLabel("TF:"))
        self.bt_tf = QComboBox()
        self.bt_tf.addItems(["M1", "M5", "M15", "H1", "H4"])
        self.bt_tf.setCurrentText("M5")
        sl.addWidget(self.bt_tf)
        sl.addWidget(QLabel("Days:"))
        self.bt_days = QSpinBox()
        self.bt_days.setRange(1, 30)
        self.bt_days.setValue(5)
        sl.addWidget(self.bt_days)
        sl.addWidget(QLabel("RR:"))
        self.bt_rr = QDoubleSpinBox()
        self.bt_rr.setRange(0.5, 10.0)
        self.bt_rr.setValue(TP_RR_RATIO)
        self.bt_rr.setSingleStep(0.5)
        self.bt_rr.setDecimals(1)
        sl.addWidget(self.bt_rr)
        sl.addStretch()
        self.btn_bt = QPushButton("▶  Run")
        self.btn_bt.setObjectName("btn_bt")
        self.btn_bt.setMinimumHeight(30)
        self.btn_bt.clicked.connect(self._run_backtest)
        sl.addWidget(self.btn_bt)
        vl.addWidget(grp_set)

        # ── Summary cards ─────────────────────────────────────────
        grp_sum = QGroupBox("Summary")
        hs = QHBoxLayout(grp_sum)
        self._bt_cards = {}
        for key, label, color in [
            ("candles", "Candles", C['txt2']
             ), ("triggered", "Triggered", C['cyan']),
            ("wins", "Wins", C['green']), ("losses", "Losses", C['red']),
            ("winrate", "Win%", C['gold']), ("pips", "Pips", C['purple']),
        ]:
            card = QFrame()
            card.setStyleSheet(
                f"background:{C['card']};border:1px solid {C['border']};border-radius:6px;")
            cv = QVBoxLayout(card)
            cv.setContentsMargins(8, 4, 8, 4)
            cv.setSpacing(1)
            lt = QLabel(label)
            lt.setStyleSheet(
                f"color:{C['txt3']};font-size:9px;font-weight:bold;")
            lv = QLabel("—")
            lv.setStyleSheet(
                f"color:{color};font-size:16px;font-weight:bold;font-family:Consolas;")
            lv.setAlignment(Qt.AlignCenter)
            cv.addWidget(lt)
            cv.addWidget(lv)
            self._bt_cards[key] = lv
            hs.addWidget(card)
        vl.addWidget(grp_sum)

        # ── Progress / loading ────────────────────────────────────
        self.bt_progress = QProgressBar()
        self.bt_progress.setVisible(False)
        self.bt_progress.setFixedHeight(6)
        self.bt_progress.setTextVisible(False)
        vl.addWidget(self.bt_progress)

        # ── Candle chart ──────────────────────────────────────────
        self.bt_chart = CandleChartWidget()
        vl.addWidget(self.bt_chart, 2)

        # ── Candle replay player ──────────────────────────────────
        grp_replay = QGroupBox("Playback & Orders")
        rl = QVBoxLayout(grp_replay)
        rl.setSpacing(4)

        # Bar info row
        bar_info_row = QHBoxLayout()
        self.bt_bar_lbl = QLabel("Bar: — / —")
        self.bt_bar_lbl.setStyleSheet(
            f"color:{C['cyan']};font-family:Consolas;font-size:11px;")
        bar_info_row.addWidget(self.bt_bar_lbl)
        bar_info_row.addStretch()
        self.bt_price_lbl = QLabel("O:— H:— L:— C:—")
        self.bt_price_lbl.setStyleSheet(
            f"color:{C['txt2']};font-family:Consolas;font-size:11px;")
        bar_info_row.addWidget(self.bt_price_lbl)
        rl.addLayout(bar_info_row)

        # Slider
        self.bt_slider = QSlider(Qt.Horizontal)
        self.bt_slider.setMinimum(0)
        self.bt_slider.setMaximum(0)
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
        self.btn_bt_first = QPushButton("⏮")
        self.btn_bt_first.setFixedWidth(36)
        self.btn_bt_first.clicked.connect(lambda: self.bt_slider.setValue(0))
        self.btn_bt_prev = QPushButton("◀")
        self.btn_bt_prev.setFixedWidth(36)
        self.btn_bt_prev.clicked.connect(
            lambda: self.bt_slider.setValue(max(0, self.bt_slider.value()-1)))
        self.btn_bt_play = QPushButton("▶ Play")
        self.btn_bt_play.setFixedWidth(72)
        self.btn_bt_play.setCheckable(True)
        self.btn_bt_play.clicked.connect(self._bt_play_toggle)
        self.btn_bt_next = QPushButton("▶")
        self.btn_bt_next.setFixedWidth(36)
        self.btn_bt_next.clicked.connect(lambda: self.bt_slider.setValue(
            min(self.bt_slider.maximum(), self.bt_slider.value()+1)))
        self.btn_bt_last = QPushButton("⏭")
        self.btn_bt_last.setFixedWidth(36)
        self.btn_bt_last.clicked.connect(
            lambda: self.bt_slider.setValue(self.bt_slider.maximum()))
        self.bt_speed = QComboBox()
        self.bt_speed.addItems(["0.5×", "1×", "2×", "5×", "10×"])
        self.bt_speed.setCurrentText("1×")
        self.bt_speed.setFixedWidth(60)
        for b in [self.btn_bt_first, self.btn_bt_prev, self.btn_bt_play,
                  self.btn_bt_next, self.btn_bt_last]:
            ctrl_row.addWidget(b)
        ctrl_row.addWidget(QLabel("Speed:"))
        ctrl_row.addWidget(self.bt_speed)
        ctrl_row.addStretch()
        rl.addLayout(ctrl_row)

        # Order state grid — shows each order's state at current bar
        self.bt_order_grid = QTableWidget(0, 6)
        self.bt_order_grid.setHorizontalHeaderLabels(
            ["Gen", "Lvl", "Type", "Entry", "SL/TP", "State"])
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
        w.setStyleSheet(
            f"background:{C['panel']};border:1px solid {C['border']};border-radius:4px;")
        hl = QHBoxLayout(w)
        hl.setContentsMargins(10, 4, 10, 4)
        self.lbl_obj_count = QLabel("Objects: —")
        self.lbl_obj_count.setStyleSheet(f"color:{C['txt2']};font-size:10px;")
        hl.addWidget(self.lbl_obj_count)
        hl.addStretch()
        self.lbl_auto = QLabel("Auto-hidden: —")
        self.lbl_auto.setStyleSheet(f"color:{C['txt3']};font-size:10px;")
        hl.addWidget(self.lbl_auto)
        return w

    def _vline(self):
        f = QFrame()
        f.setFrameShape(QFrame.VLine)
        return f

    # ─────────────────────────────── SLOTS ───────────────────────

    def _init_mt5_price(self):
        try:
            if not mt5.initialize():
                self._on_log(
                    f"{datetime.now().strftime('%H:%M:%S')}  ⚠️  MT5 not running — open MetaTrader 5 first", "WARN")
                return
            ok = mt5.login(MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER)
            if not ok:
                err = mt5.last_error()
                self._on_log(
                    f"{datetime.now().strftime('%H:%M:%S')}  ⚠️  MT5 login failed: {err} | Check config.py credentials", "WARN")
                return
            # Symbol combos pre-populated with common symbols
        except Exception:
            pass

    def _start(self):
        self._pip_step = self.spin_pip.value()
        self.spin_pip.setEnabled(False)
        active_sym = self.sym_combo.currentText().strip() or WATCH_SYMBOL
        self._tp_pips = self.spin_tp.value()
        self._spawn_lvls = self.combo_spawn.currentText()
        self._lot_size = self.spin_lot.value()
        self._worker = WatcherWorker(self._sig, self._pip_step, symbol=active_sym,
                                     tp_pips=self._tp_pips, spawn_on=self._spawn_lvls,
                                     lot_size=self._lot_size)
        self._worker.follow_enabled = self.chk_follow.isChecked()
        self._worker.start()
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.chk_follow.stateChanged.connect(self._toggle_follow)
        self._on_log(
            f"{datetime.now().strftime('%H:%M:%S')}  ▶ Watcher started | symbol={active_sym} | pip_step={self._pip_step}", "INFO")
        self._on_log(
            f"{datetime.now().strftime('%H:%M:%S')}  💡 Make sure ObjectExporter EA is on the {active_sym} chart in MT5", "INFO")

    def _toggle_follow(self, state):
        if self._worker:
            self._worker.follow_enabled = bool(state)
            status = "enabled" if state else "locked"
            self._on_log(
                f"{datetime.now().strftime('%H:%M:%S')}  🔗 Follow object: {status}", "INFO")

    def _on_symbol_changed(self, sym: str):
        sym = sym.strip()
        if not sym:
            return
        # Update header label
        self.lbl_sym.setText(sym)
        # Sync backtest symbol combo
        if hasattr(self, "bt_symbol"):
            self.bt_symbol.setCurrentText(sym)
        self._on_log(
            f"{datetime.now().strftime('%H:%M:%S')}  🔄 Symbol changed to {sym}", "INFO")

    def _stop(self):
        if self._worker:
            self._worker.stop()
            self._worker = None
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_place.setEnabled(False)
        self.spin_pip.setEnabled(True)

    def _place_orders(self):
        if not self.btn_place.isEnabled():
            return  # guard against spurious calls
        pip = get_pip_size(
            self.sym_combo.currentText().strip() or WATCH_SYMBOL)
        all_orders = []

        hlines = [o for o in self._trader_objects if o.is_hline]
        rects = [o for o in self._trader_objects if o.is_rectangle]

        if hlines:
            # Hline: 3 buy-stops above, 3 sell-stops below
            _sym = self.sym_combo.currentText().strip() or WATCH_SYMBOL
            orders = place_level_orders(
                hlines[0].price1, pip, self._pip_step, _sym)
            all_orders.extend(orders)

        elif rects:
            # Rectangle: buy-stops above TOP edge, sell-stops below BOTTOM edge
            rect = next((r for r in rects if r.rect_valid), None)
            if rect is None:
                self._on_log(
                    f"{datetime.now().strftime('%H:%M:%S')}  ⚠️  Rectangle not fully drawn yet", "WARN")
                return
            step = self._pip_step * pip
            top = rect.rect_top
            bottom = rect.rect_bottom
            above = [top + step * i for i in range(1, 4)]
            below = [bottom - step * i for i in range(1, 4)]
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
            self._on_log(
                f"{datetime.now().strftime('%H:%M:%S')}  ⚠️  No line or rectangle detected", "WARN")
            return

        self.btn_place.setEnabled(False)
        self._populate_ord_table(all_orders)
        results = send_orders(
            all_orders, self.sym_combo.currentText().strip() or WATCH_SYMBOL)
        ok = sum(1 for r in results if r["ok"])
        failed = [r for r in results if not r["ok"]]
        ts = datetime.now().strftime('%H:%M:%S')
        if ok == len(results):
            self._on_log(f"{ts}  ✅ All {ok} orders placed successfully", "NEW")
        elif ok > 0:
            self._on_log(
                f"{ts}  ⚠️  {ok}/{len(results)} placed — {failed[0].get('reason', 'unknown')}", "WARN")
        else:
            reason = failed[0].get(
                'reason', 'unknown') if failed else 'unknown'
            self._on_log(
                f"{ts}  ❌ 0/{len(results)} placed — {reason}", "ERROR")
            if "Market closed" in reason:
                self._on_log(
                    f"{ts}  💡 Use the Backtest tab to test while market is closed", "INFO")
        self.btn_place.setEnabled(True)
        self.tabs.setCurrentIndex(1)

    def _refresh_orders_tab(self):
        """Pull live pending + active orders from MT5 and update the Orders tab."""
        try:
            import MetaTrader5 as _mt5
            if not _mt5.initialize():
                return
            sym = self.sym_combo.currentText().strip() or WATCH_SYMBOL
            pip = get_pip_size(sym)

            # ── Pending orders ────────────────────────────────────
            pending = _mt5.orders_get(symbol=sym) or []
            bot_pending = [o for o in pending if o.magic == MAGIC_NUMBER]

            self.ord_pending.setRowCount(0)
            for o in sorted(bot_pending, key=lambda x: x.price_open):
                cmt = getattr(o, 'comment', '')
                # Parse Gen/Lvl from comment e.g. TB_G0L1B
                gen_str = "?"
                lvl_str = "?"
                import re
                m = re.search(r'G(\d+)L(\d+)', cmt)
                if m:
                    gen_str, lvl_str = m.group(1), m.group(2)
                is_buy = o.type == 2  # ORDER_TYPE_BUY_STOP = 2
                t_str = "BUY_STOP" if is_buy else "SELL_STOP"
                clr = QColor(C['green'] if is_buy else C['red'])
                sl_pips = abs(o.price_open - o.sl) / pip if pip > 0 else 0
                row = self.ord_pending.rowCount()
                self.ord_pending.insertRow(row)
                gen_colors = [C['gold'], C['cyan'],
                              C['purple'], C['orange'], C['orange']]
                try:
                    gc = QColor(gen_colors[int(gen_str)])
                except:
                    gc = QColor(C['txt2'])
                vals = [f"G{gen_str}", f"L{lvl_str}", t_str,
                        f"{o.price_open:.5f}", f"{o.sl:.5f}",
                        f"{o.tp:.5f}" if o.tp > 0 else "—",
                        f"{sl_pips:.1f}"]
                for c, v in enumerate(vals):
                    it = QTableWidgetItem(v)
                    it.setForeground(gc if c == 0 else clr)
                    # Highlight L1 rows slightly
                    if lvl_str == "1":
                        it.setBackground(
                            QColor("#1A2520" if is_buy else "#251A1A"))
                    self.ord_pending.setItem(row, c, it)

            # ── Active positions ──────────────────────────────────
            positions = _mt5.positions_get(symbol=sym) or []
            bot_pos = [p for p in positions if p.magic == MAGIC_NUMBER]

            self.ord_active.setRowCount(0)
            total_pnl = 0.0
            buy_count = sell_count = 0
            for p in sorted(bot_pos, key=lambda x: x.price_open):
                cmt = getattr(p, 'comment', '')
                gen_str = lvl_str = "?"
                import re
                m = re.search(r'G(\d+)L(\d+)', cmt)
                if m:
                    gen_str, lvl_str = m.group(1), m.group(2)
                is_buy = p.type == 0
                t_str = "BUY" if is_buy else "SELL"
                if is_buy:
                    buy_count += 1
                else:
                    sell_count += 1
                total_pnl += p.profit
                pnl_clr = QColor(C['green'] if p.profit >= 0 else C['red'])
                row_clr = QColor(C['green'] if is_buy else C['red'])
                row = self.ord_active.rowCount()
                self.ord_active.insertRow(row)
                vals = [f"G{gen_str}", f"L{lvl_str}", t_str,
                        f"{p.price_open:.5f}", f"{p.sl:.5f}",
                        f"{p.tp:.5f}" if p.tp > 0 else "—",
                        f"{p.profit:+.2f}"]
                for c, v in enumerate(vals):
                    it = QTableWidgetItem(v)
                    it.setForeground(pnl_clr if c == 6 else row_clr)
                    if c == 0:
                        gen_colors = [C['gold'], C['cyan'],
                                      C['purple'], C['orange'], C['orange']]
                        try:
                            it.setForeground(QColor(gen_colors[int(gen_str)]))
                        except:
                            pass
                    self.ord_active.setItem(row, c, it)

            # ── Summary cards ─────────────────────────────────────
            if hasattr(self, '_ord_summary'):
                self._ord_summary["pending"].setText(str(len(bot_pending)))
                self._ord_summary["active"].setText(str(len(bot_pos)))
                self._ord_summary["buy_pos"].setText(str(buy_count))
                self._ord_summary["sell_pos"].setText(str(sell_count))
                pnl_color = C['green'] if total_pnl >= 0 else C['red']
                self._ord_summary["total_pnl"].setText(f"{total_pnl:+.2f}")
                self._ord_summary["total_pnl"].setStyleSheet(
                    f"color:{pnl_color};font-size:15px;font-weight:bold;font-family:Consolas;")
                rounds = getattr(self._worker, 'spawn_rounds',
                                 0) if self._worker else 0
                self._ord_summary["rounds"].setText(str(rounds))

            # ── Tab title with count ──────────────────────────────
            total = len(bot_pending) + len(bot_pos)
            self.tabs.setTabText(
                1, f"📊  Orders ({total})" if total else "📊  Orders")
            # Update group box titles with counts
            self.ord_pending.parent().parent().setTitle(
                f"🔵  Pending Orders ({len(bot_pending)})")
            self.ord_active.parent().parent().setTitle(
                f"📊  Active Positions ({len(bot_pos)}) | P&L: {total_pnl:+.2f}")

        except Exception as e:
            pass  # Non-critical refresh failure

    def _activate_risk_free(self):
        """
        Risk-Free mode:
        1. Determine which side to KEEP (BUY or SELL)
        2. Close all positions on the OPPOSITE side
        3. Cancel ALL pending orders
        4. Draw a horizontal line on chart labeled "TB_RF_SL"
        5. Every scan cycle: if price touches that line → close all kept positions
        """
        import MetaTrader5 as _mt5
        sym = self.sym_combo.currentText().strip() or WATCH_SYMBOL
        keep_side = "BUY" if "BUY" in self.combo_rf_side.currentText() else "SELL"
        close_side = "SELL" if keep_side == "BUY" else "BUY"

        positions = _mt5.positions_get(symbol=sym) or []
        bot_pos = [p for p in positions if p.magic == MAGIC_NUMBER]

        keep_pos = [p for p in bot_pos if (
            p.type == 0) == (keep_side == "BUY")]
        close_pos = [p for p in bot_pos if (
            p.type == 0) != (keep_side == "BUY")]

        if not keep_pos:
            self._on_log(
                f"{datetime.now().strftime('%H:%M:%S')}  ⚠️  No {keep_side} positions to protect", "WARN")
            return

        # Close opposite side
        closed = 0
        for p in close_pos:
            close_type = _mt5.ORDER_TYPE_SELL if p.type == 0 else _mt5.ORDER_TYPE_BUY
            tick = _mt5.symbol_info_tick(sym)
            price = tick.bid if close_type == _mt5.ORDER_TYPE_SELL else tick.ask
            req = {
                "action":       _mt5.TRADE_ACTION_DEAL,
                "symbol":       sym,
                "volume":       p.volume,
                "type":         close_type,
                "position":     p.ticket,
                "price":        price,
                "deviation":    20,
                "magic":        MAGIC_NUMBER,
                "comment":      "TB_RF_CLOSE",
                "type_time":    _mt5.ORDER_TIME_GTC,
                "type_filling": _mt5.ORDER_FILLING_RETURN,
            }
            res = _mt5.order_send(req)
            if res and res.retcode == _mt5.TRADE_RETCODE_DONE:
                closed += 1

        # Cancel all pending
        pending = _mt5.orders_get(symbol=sym) or []
        cancelled = 0
        for o in pending:
            if o.magic == MAGIC_NUMBER:
                res = _mt5.order_send(
                    {"action": _mt5.TRADE_ACTION_REMOVE, "order": o.ticket})
                if res and res.retcode == _mt5.TRADE_RETCODE_DONE:
                    cancelled += 1

        # Use user-specified exit price or fall back to average entry
        try:
            rf_price_text = self.edit_rf_price.text().strip()
            sl_price = float(rf_price_text) if rf_price_text else 0.0
        except ValueError:
            sl_price = 0.0
        if sl_price <= 0:
            sl_price = round(
                sum(p.price_open for p in keep_pos) / len(keep_pos), 5)
            self.edit_rf_price.setText(f"{sl_price:.5f}")
        write_commands(
            [f"DRAW_HLINE|TB_RF_SL|{sl_price:.5f}|{0xFFD700}|2|0"], symbol=sym)
        avg_entry = sl_price

        # Store RF state for watcher to monitor
        self._rf_active = True
        self._rf_keep_side = keep_side
        self._rf_sym = sym
        self._rf_tickets = [p.ticket for p in keep_pos]

        n_keep = len(keep_pos)
        ts = datetime.now().strftime("%H:%M:%S")
        self._on_log(
            f"{ts}  🛡️  Risk-Free ACTIVE — keeping {n_keep} {keep_side} positions | "
            f"closed {closed} {close_side} | cancelled {cancelled} pending | "
            f"Gold SL line drawn @ {avg_entry:.5f} — DRAG IT in MT5 to set exit price", "NEW")
        self.lbl_rf_status.setText(
            f"🛡️ Active: {n_keep} {keep_side} | exit @ {avg_entry:.5f}")
        self.lbl_rf_status.setStyleSheet(
            f"color:{C['gold']};font-size:10px;font-weight:bold;")
        self.btn_rf_update.setEnabled(True)
        self.btn_rf.setText("🛡️ RF Active")
        self.btn_rf.setEnabled(False)

    def _update_rf_sl(self):
        """Update the RF SL exit price from the input field."""
        if not getattr(self, "_rf_active", False):
            return
        try:
            new_price = float(self.edit_rf_price.text().strip())
        except ValueError:
            self._on_log(
                f"{datetime.now().strftime('%H:%M:%S')}  ⚠️  Invalid price — enter a number like 1.16420", "WARN")
            return
        sym = self._rf_sym
        write_commands(
            [f"DRAW_HLINE|TB_RF_SL|{new_price:.5f}|{0xFFD700}|2|0"], symbol=sym)
        self._on_log(
            f"{datetime.now().strftime('%H:%M:%S')}  📍  RF exit price updated → {new_price:.5f}", "NEW")
        self.lbl_rf_status.setText(
            f"🛡️ Active: {self._rf_keep_side} | exit @ {new_price:.5f}")

    def _check_rf_sl(self, candle: dict):
        """Called each scan cycle when RF mode is active. Closes all kept positions if SL line is touched."""
        if not getattr(self, "_rf_active", False):
            return
        import MetaTrader5 as _mt5
        sym = self._rf_sym
        prev_h = candle.get("PREV_H", 0.0)
        prev_l = candle.get("PREV_L", 0.0)

        # Find RF SL line price from MT5 objects
        # Parse it from the file or get from objects
        # Use BID as fallback
        tick = _mt5.symbol_info_tick(sym)
        if not tick:
            return

        # Find TB_RF_SL — it's a bot-drawn line, visible in the EA export
        # Check self._trader_objects (latest trader objects from watcher)
        rf_price = None
        for obj in self._trader_objects:
            if obj.name == "TB_RF_SL" and obj.is_hline:
                rf_price = obj.price1
                break
        # Update status label with current RF line position
        if rf_price is not None:
            self.lbl_rf_status.setText(
                f"Active: {self._rf_keep_side} | SL line @ {rf_price:.5f} (drag in MT5 to adjust)")

        if rf_price is None:
            return

        # Check if previous closed candle touched the RF SL line
        if prev_l <= rf_price <= prev_h:
            # Close all kept positions
            positions = _mt5.positions_get(symbol=sym) or []
            closed = 0
            for p in positions:
                if p.magic == MAGIC_NUMBER:
                    keep = self._rf_keep_side
                    if (p.type == 0) == (keep == "BUY"):
                        close_type = _mt5.ORDER_TYPE_SELL if p.type == 0 else _mt5.ORDER_TYPE_BUY
                        tick2 = _mt5.symbol_info_tick(sym)
                        price = tick2.bid if close_type == _mt5.ORDER_TYPE_SELL else tick2.ask
                        req = {
                            "action": _mt5.TRADE_ACTION_DEAL, "symbol": sym,
                            "volume": p.volume, "type": close_type,
                            "position": p.ticket, "price": price,
                            "deviation": 20, "magic": MAGIC_NUMBER,
                            "comment": "TB_RF_EXIT",
                            "type_time": _mt5.ORDER_TIME_GTC,
                            "type_filling": _mt5.ORDER_FILLING_RETURN,
                        }
                        res = _mt5.order_send(req)
                        if res and res.retcode == _mt5.TRADE_RETCODE_DONE:
                            closed += 1

            ts = datetime.now().strftime("%H:%M:%S")
            self._on_log(
                f"{ts}  🛡️  Risk-Free SL hit @ {rf_price:.5f} | "
                f"closed {closed} {self._rf_keep_side} positions with profit", "NEW")
            self._rf_active = False
            self.lbl_rf_status.setText("✅ Triggered — all positions closed")
            self.lbl_rf_status.setStyleSheet(
                f"color:{C['cyan']};font-size:10px;")
            self.btn_rf_update.setEnabled(False)
            self.btn_rf.setText("🛡️  Activate Risk-Free")
            self.btn_rf.setEnabled(True)
            write_commands(["DELETE|TB_RF_SL"], symbol=sym)

    def _cancel_orders(self):
        if getattr(self, "_cancelling", False):
            return
        self._cancelling = True
        try:
            sym = self.sym_combo.currentText().strip() or WATCH_SYMBOL
            n = cancel_all_tb_orders(sym)
            write_commands(["DELETE_PREFIX|TB_"], symbol=sym)
            self._on_log(
                f"{datetime.now().strftime('%H:%M:%S')}  🗑️  Cancelled {n} bot orders + cleared all level lines", "WARN")
            if hasattr(self, 'ord_pending'):
                self.ord_pending.setRowCount(0)
            if hasattr(self, 'ord_active'):
                self.ord_active.setRowCount(0)
        finally:
            self._cancelling = False

    def _tab_report(self):
        w = QWidget()
        vl = QVBoxLayout(w)
        vl.setContentsMargins(6, 6, 6, 6)
        vl.setSpacing(6)

        # ── Summary cards ──────────────────────────────────────────
        grp_sum = QGroupBox("Session Summary")
        hs = QHBoxLayout(grp_sum)
        self._rpt_cards = {}
        for key, label, color in [
            ("duration",  "Duration",    C["txt2"]),
            ("total_pos", "Positions",   C["cyan"]),
            ("wins",      "Wins ✅",     C["green"]),
            ("losses",    "Losses ❌",   C["red"]),
            ("rf_exits",  "Risk-Free 🛡", C["gold"]),
            ("pnl",       "Total P&L",   C["purple"]),
            ("best",      "Best P&L",    C["green"]),
            ("worst",     "Worst P&L",   C["red"]),
        ]:
            card = QFrame()
            card.setStyleSheet(
                f"background:{C['card']};border:1px solid {C['border']};border-radius:6px;")
            cv = QVBoxLayout(card)
            cv.setContentsMargins(8, 4, 8, 4)
            cv.setSpacing(1)
            lt = QLabel(label)
            lt.setStyleSheet(
                f"color:{C['txt3']};font-size:8px;font-weight:bold;")
            lt.setAlignment(Qt.AlignCenter)
            lv = QLabel("—")
            lv.setStyleSheet(
                f"color:{color};font-size:13px;font-weight:bold;font-family:Consolas;")
            lv.setAlignment(Qt.AlignCenter)
            cv.addWidget(lt)
            cv.addWidget(lv)
            self._rpt_cards[key] = lv
            hs.addWidget(card)
        vl.addWidget(grp_sum)

        # ── Event table ────────────────────────────────────────────
        grp_tbl = QGroupBox("Position Events")
        tl = QVBoxLayout(grp_tbl)
        self.rpt_table = QTableWidget(0, 10)
        self.rpt_table.setHorizontalHeaderLabels([
            "Time", "Symbol", "Type", "Entry", "Close",
            "SL", "TP", "P&L $", "P&L Pips", "Close Reason"
        ])
        self.rpt_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.rpt_table.setAlternatingRowColors(True)
        self.rpt_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.rpt_table.verticalHeader().setVisible(False)
        self.rpt_table.setSortingEnabled(True)
        tl.addWidget(self.rpt_table)
        vl.addWidget(grp_tbl, 1)

        # ── Buttons ────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_refresh = QPushButton("🔄  Refresh Now")
        btn_refresh.setMinimumHeight(30)
        btn_refresh.clicked.connect(self._refresh_report)
        btn_row.addWidget(btn_refresh)

        btn_csv = QPushButton("💾  Export CSV")
        btn_csv.setMinimumHeight(30)
        btn_csv.clicked.connect(self._export_report_csv)
        btn_row.addWidget(btn_csv)

        btn_txt = QPushButton("📄  Export TXT Report")
        btn_txt.setMinimumHeight(30)
        btn_txt.clicked.connect(self._export_report_txt)
        btn_row.addWidget(btn_txt)

        btn_row.addStretch()
        self.lbl_rpt_status = QLabel("Click Refresh to load")
        self.lbl_rpt_status.setStyleSheet(f"color:{C['txt3']};font-size:10px;")
        btn_row.addWidget(self.lbl_rpt_status)
        vl.addLayout(btn_row)

        # Auto-refresh timer every 30s
        self._rpt_timer = QTimer()
        self._rpt_timer.timeout.connect(self._refresh_report)
        self._rpt_timer.start(30000)

        return w

    def _refresh_report(self):
        """Pull all closed positions + open positions from MT5 and build report."""
        import MetaTrader5 as _mt5
        try:
            if not _mt5.initialize():
                return
            sym = self.sym_combo.currentText().strip()

            # Get all closed deals from a wide window (last 7 days)
            import time as _t
            t_to = datetime.now()
            t_from = self._session_start
            deals = _mt5.history_deals_get(t_from, t_to) or []

            # Filter to bot magic number and entry/exit deal types
            bot_deals = [d for d in deals
                         if d.magic == MAGIC_NUMBER and d.entry in (0, 1)]

            # Group by position_id → pair open+close
            pos_map = {}
            for d in bot_deals:
                pid = d.position_id
                if pid not in pos_map:
                    pos_map[pid] = {"open": None, "close": None}
                if d.entry == 0:
                    pos_map[pid]["open"] = d
                else:
                    pos_map[pid]["close"] = d

            # Also get currently open positions
            open_pos = [p for p in (_mt5.positions_get(symbol=sym) or [])
                        if p.magic == MAGIC_NUMBER]

            events = []
            total_pnl = 0.0
            wins = losses = rf_exits = 0
            best_pnl = float("-inf")
            worst_pnl = float("inf")

            for pid, pair in pos_map.items():
                o = pair["open"]
                c = pair["close"]
                if o is None:
                    continue
                pnl = c.profit if c else 0.0
                pips = round((c.price - o.price) / 0.0001, 1) if c else 0.0
                if "BUY" in str(o.type):
                    pips = -pips  # invert for sells
                reason = "Open"
                if c:
                    reason = ("Risk-Free" if "RF" in (c.comment or "")
                              else "SL" if c.price == o.sl
                              else "TP" if c.price == o.tp
                              else "Manual")
                    total_pnl += pnl
                    if pnl > 0:
                        wins += 1
                    else:
                        losses += 1
                    if "Risk-Free" in reason:
                        rf_exits += 1
                    best_pnl = max(best_pnl, pnl)
                    worst_pnl = min(worst_pnl, pnl)

                events.append({
                    "time":   datetime.fromtimestamp(o.time).strftime("%H:%M:%S"),
                    "symbol": o.symbol,
                    "type":   "BUY" if o.type == 0 else "SELL",
                    "entry":  f"{o.price:.5f}",
                    "close":  f"{c.price:.5f}" if c else "—",
                    "sl":     f"{o.sl:.5f}" if o.sl else "—",
                    "tp":     f"{o.tp:.5f}" if o.tp else "—",
                    "pnl":    f"{pnl:+.2f}" if c else "—",
                    "pips":   f"{pips:+.1f}" if c else "—",
                    "reason": reason,
                    "_pnl_v": pnl,
                })

            # Add still-open positions
            for p in open_pos:
                tick = _mt5.symbol_info_tick(p.symbol)
                cur = (tick.bid + tick.ask) / 2 if tick else 0
                float_pnl = p.profit
                events.append({
                    "time":   datetime.fromtimestamp(p.time).strftime("%H:%M:%S"),
                    "symbol": p.symbol,
                    "type":   "BUY" if p.type == 0 else "SELL",
                    "entry":  f"{p.price_open:.5f}",
                    "close":  f"{cur:.5f} (open)",
                    "sl":     f"{p.sl:.5f}" if p.sl else "—",
                    "tp":     f"{p.tp:.5f}" if p.tp else "—",
                    "pnl":    f"{float_pnl:+.2f}",
                    "pips":   "—",
                    "reason": "🟢 Open",
                    "_pnl_v": float_pnl,
                })

            # Update table
            self.rpt_table.setRowCount(len(events))
            for row, ev in enumerate(events):
                cols = ["time", "symbol", "type", "entry",
                        "close", "sl", "tp", "pnl", "pips", "reason"]
                for col, key in enumerate(cols):
                    it = QTableWidgetItem(ev[key])
                    pv = ev["_pnl_v"]
                    if key == "pnl":
                        it.setForeground(
                            QColor(C["green"] if pv > 0 else C["red"] if pv < 0 else C["txt2"]))
                    elif key == "type":
                        it.setForeground(
                            QColor(C["green"] if ev["type"] == "BUY" else C["red"]))
                    elif key == "reason":
                        clr = (C["gold"] if "Risk" in ev["reason"]
                               else C["red"] if ev["reason"] == "SL"
                               else C["green"] if ev["reason"] == "TP"
                               else C["cyan"] if "Open" in ev["reason"]
                               else C["txt2"])
                        it.setForeground(QColor(clr))
                    self.rpt_table.setItem(row, col, it)

            # Update summary cards
            dur = datetime.now() - self._session_start
            h, m = divmod(int(dur.total_seconds()), 3600)
            m //= 60
            self._rpt_cards["duration"].setText(f"{h}h {m}m")
            self._rpt_cards["total_pos"].setText(str(len(events)))
            self._rpt_cards["wins"].setText(str(wins))
            self._rpt_cards["losses"].setText(str(losses))
            self._rpt_cards["rf_exits"].setText(str(rf_exits))
            pnl_str = f"{total_pnl:+.2f}"
            self._rpt_cards["pnl"].setText(pnl_str)
            self._rpt_cards["pnl"].setStyleSheet(
                f"color:{C['green'] if total_pnl >= 0 else C['red']};font-size:13px;font-weight:bold;font-family:Consolas;")
            self._rpt_cards["best"].setText(
                f"{best_pnl:+.2f}" if best_pnl != float('-inf') else "—")
            self._rpt_cards["worst"].setText(
                f"{worst_pnl:+.2f}" if worst_pnl != float('inf') else "—")

            self._session_events = events
            n_closed = sum(1 for e in events if e["reason"] != "🟢 Open")
            self.lbl_rpt_status.setText(
                f"Last refresh: {datetime.now().strftime('%H:%M:%S')} | "
                f"{n_closed} closed, {len(open_pos)} open")

        except Exception as ex:
            import traceback
            self.lbl_rpt_status.setText(f"Error: {ex}")

    def _export_report_csv(self):
        """Export session events to CSV file."""
        from PyQt5.QtWidgets import QFileDialog
        fname, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "CSV Files (*.csv)")
        if not fname:
            return
        try:
            import csv
            with open(fname, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=[
                    "time", "symbol", "type", "entry", "close", "sl", "tp", "pnl", "pips", "reason"])
                w.writeheader()
                for ev in self._session_events:
                    row = {k: ev[k] for k in ["time", "symbol", "type",
                                              "entry", "close", "sl", "tp", "pnl", "pips", "reason"]}
                    w.writerow(row)
            self.lbl_rpt_status.setText(f"✅  CSV exported: {fname}")
        except Exception as ex:
            self.lbl_rpt_status.setText(f"❌  Export failed: {ex}")

    def _export_report_txt(self):
        """Export a human-readable text report."""
        from PyQt5.QtWidgets import QFileDialog
        fname, _ = QFileDialog.getSaveFileName(
            self, "Export Report", f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "Text Files (*.txt)")
        if not fname:
            return
        try:
            sym = self.sym_combo.currentText().strip()
            dur = datetime.now() - self._session_start
            h, m = divmod(int(dur.total_seconds()), 3600)
            m //= 60
            events = self._session_events
            closed = [e for e in events if e["reason"] != "🟢 Open"]
            opens = [e for e in events if e["reason"] == "🟢 Open"]
            wins = [e for e in closed if float(
                e["pnl"].replace("—", "0") or 0) > 0]
            losses = [e for e in closed if float(
                e["pnl"].replace("—", "0") or 0) <= 0]
            total_pnl = sum(float(e["pnl"].replace("—", "0") or 0)
                            for e in closed)
            wr = len(wins) / len(closed) * 100 if closed else 0

            lines = [
                "=" * 60,
                f"  TRADERBOT SESSION REPORT",
                f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "=" * 60,
                f"  Symbol:      {sym}",
                f"  Session:     {self._session_start.strftime('%H:%M:%S')} → {datetime.now().strftime('%H:%M:%S')}  ({h}h {m}m)",
                f"  Positions:   {len(events)} total ({len(closed)} closed, {len(opens)} open)",
                f"  Win Rate:    {wr:.1f}%  ({len(wins)}W / {len(losses)}L)",
                f"  Total P&L:   ${total_pnl:+.2f}",
                "=" * 60,
                "",
                f"{'Time':<10} {'Type':<5} {'Entry':<10} {'Close':<16} {'P&L':>8} {'Reason':<14} {'SL':<10} {'TP':<10}",
                "-" * 90,
            ]
            for ev in events:
                lines.append(
                    f"{ev['time']:<10} {ev['type']:<5} {ev['entry']:<10} "
                    f"{ev['close']:<16} {ev['pnl']:>8} {ev['reason']:<14} "
                    f"{ev['sl']:<10} {ev['tp']:<10}"
                )
            lines += [
                "",
                "=" * 60,
                f"  Best position:  ${max((float(e['pnl'].replace('—', '0') or 0) for e in closed), default=0):+.2f}",
                f"  Worst position: ${min((float(e['pnl'].replace('—', '0') or 0) for e in closed), default=0):+.2f}",
                f"  Risk-Free exits: {sum(1 for e in closed if 'Risk' in e['reason'])}",
                "=" * 60,
            ]
            with open(fname, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            self.lbl_rpt_status.setText(f"✅  Report exported: {fname}")
        except Exception as ex:
            self.lbl_rpt_status.setText(f"❌  Export failed: {ex}")

    def _run_backtest(self):
        if self._bt_running:
            return  # already running
        hlines = [o for o in self._trader_objects if o.is_hline]
        rects = [o for o in self._trader_objects if o.is_rectangle and o.rect_valid]
        if not hlines and not rects:
            self._on_log(
                f"{datetime.now().strftime('%H:%M:%S')}  ⚠️  Draw a line or rectangle on your chart first", "WARN")
            return

        # Warn if pip step might be below broker minimum
        sym_for_check = self.bt_symbol.currentText().strip() or WATCH_SYMBOL
        ts = datetime.now().strftime('%H:%M:%S')
        self._on_log(f"{ts}  🔬 Running backtest on {sym_for_check}...", "BT")
        self._bt_running = True
        self.btn_bt.setEnabled(False)
        self.btn_bt.setText("Loading…")
        self.bt_progress.setVisible(True)
        self.bt_progress.setRange(0, 0)
        self._bt_play_timer.stop()
        self.btn_bt_play.setChecked(False)
        self.btn_bt_play.setText("▶ Play")

        bt_sym = self.bt_symbol.currentText().strip(
        ) or self.sym_combo.currentText().strip() or WATCH_SYMBOL
        pip = get_pip_size(bt_sym)
        pip_step = self._pip_step
        tf = self.bt_tf.currentText()
        days = self.bt_days.value()
        rr = self.bt_rr.value()

        use_hline = bool(hlines)
        if use_hline:
            src = hlines[0].price1
            rect_top = rect_bot = None
        else:
            rect = rects[0]
            src = rect.price1
            rect_top = rect.rect_top
            rect_bot = rect.rect_bottom

        # Capture all values for the thread closure
        _sym = bt_sym
        _tf = tf
        _src = src
        _step = pip_step
        _rr = rr
        _days = days
        _hline = use_hline
        _rtop = rect_top
        _rbot = rect_bot

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
        new_place = has_object and self._worker is not None
        if self.btn_place.isEnabled() != new_place:
            self.btn_place.setEnabled(new_place)
        if not self.btn_bt.isEnabled() and not self._bt_running:
            self.btn_bt.setEnabled(True)
        self._populate_lvl_table(trader)
        # Update strategy state labels
        self._update_strategy_state(trader)

    def _update_strategy_state(self, trader):
        hlines = [o for o in trader if o.is_hline]
        rects = [o for o in trader if o.is_rectangle and o.rect_valid]
        rounds = getattr(self._worker, 'spawn_rounds',
                         0) if self._worker else 0
        pending_count = len(
            getattr(self._worker, 'pending_tracker', {})) if self._worker else 0

        if hlines or rects:
            obj = hlines[0] if hlines else rects[0]
            src = obj.price1 if obj.is_hline else round(
                (obj.rect_top+obj.rect_bottom)/2, 5)
            self.lbl_source_price.setText(f"{src:.5f}")
            direction = getattr(self._worker, '_last_direction',
                                '—') if self._worker else '—'
            if direction == 'BUY':
                self.lbl_direction.setText("🟢 BUY bias")
                self.lbl_direction.setStyleSheet(
                    f"color:{C['green']};font-family:Consolas;font-size:11px;font-weight:bold;")
            elif direction == 'SELL':
                self.lbl_direction.setText("🔴 SELL bias")
                self.lbl_direction.setStyleSheet(
                    f"color:{C['red']};font-family:Consolas;font-size:11px;font-weight:bold;")
            else:
                self.lbl_direction.setText("— waiting")
                self.lbl_direction.setStyleSheet(
                    f"color:{C['txt3']};font-family:Consolas;font-size:11px;")
            triggered = any(
                v.get("triggered", False)
                for v in (getattr(self._worker, 'source_registry', {}) or {}).values()
            ) if self._worker and hasattr(self._worker, 'source_registry') else False
            if triggered:
                self.lbl_waiting.setText(f"✅ Active — {pending_count} pending")
                self.lbl_waiting.setStyleSheet(
                    f"color:{C['green']};font-family:Consolas;font-size:11px;font-weight:bold;")
            else:
                self.lbl_waiting.setText("⏳ Waiting for touch")
                self.lbl_waiting.setStyleSheet(
                    f"color:{C['orange']};font-family:Consolas;font-size:11px;")
        else:
            self.lbl_source_price.setText("—")
            self.lbl_direction.setText("—")
            self.lbl_direction.setStyleSheet(
                f"color:{C['txt3']};font-family:Consolas;font-size:11px;")
            self.lbl_waiting.setText("Draw a line on chart")
            self.lbl_waiting.setStyleSheet(
                f"color:{C['txt3']};font-family:Consolas;font-size:11px;")

        self.lbl_rounds_info.setText(f"Rounds: {rounds}/9")
        color = C['red'] if rounds >= 7 else C['gold'] if rounds >= 4 else C['cyan']
        self.lbl_rounds_info.setStyleSheet(
            f"color:{color};font-family:Consolas;font-size:11px;")
        self.lbl_phase.setText(f"G{rounds} | Pending: {pending_count}")

    def _on_status(self, msg):
        self.lbl_status.setText(msg)
        color = C['green'] if "Running" in msg else C['red'] if "failed" in msg else C['txt2']
        self.lbl_status.setStyleSheet(f"color:{color};font-size:11px;")

    def _on_log(self, msg, level="INFO"):
        if msg == "__BT_RESULT__":
            return
        if msg == "__REFRESH_ORDERS__":
            self._refresh_orders_tab()
            return
        if msg.startswith("__CANDLE__"):
            try:
                self._last_candle = eval(msg[9:])
            except:
                pass
            return
        if msg == "__CHECK_RF__":
            self._check_rf_sl(getattr(self, "_last_candle", {}))
            return
        if msg.startswith("__EA_SYM__"):
            ea_sym = msg[10:]
            self.lbl_ea_chart.setText(f"EA: {ea_sym}")
            active_sym = self.sym_combo.currentText().strip()
            if ea_sym != active_sym:
                self.lbl_ea_chart.setStyleSheet(
                    f"color:{C['orange']};font-size:10px;font-weight:bold;")
                self.lbl_ea_chart.setToolTip(
                    f"⚠️ EA is on {ea_sym} but you want {active_sym}. Drag ObjectExporter to {active_sym} chart.")
            else:
                self.lbl_ea_chart.setStyleSheet(
                    f"color:{C['green']};font-size:10px;")
                self.lbl_ea_chart.setToolTip(
                    f"EA is on the correct chart: {ea_sym}")
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
            sym = self.sym_combo.currentText().strip() if hasattr(
                self, 'sym_combo') else WATCH_SYMBOL
            tick = mt5.symbol_info_tick(sym)
            if tick:
                p = (tick.bid + tick.ask) / 2
                self.lbl_price.setText(f"Price: {p:.5f}")
        except Exception:
            pass

    def _populate_lvl_table(self, trader):
        sym = self.sym_combo.currentText().strip() if hasattr(
            self, 'sym_combo') else WATCH_SYMBOL
        pip = get_pip_size(sym)
        step = self._pip_step * pip
        self.lvl_tbl.setRowCount(0)
        try:
            tick = mt5.symbol_info_tick(sym)
            cur = (tick.bid + tick.ask) / 2 if tick else 0
        except:
            cur = 0

        hlines = [o for o in trader if o.is_hline]
        rects = [o for o in trader if o.is_rectangle]
        rows = []

        if hlines:
            src = hlines[0].price1
            for i in range(3, 0, -1):
                rows.append((f"🟠 Above {i}", src + step*i, C['orange']))
            rows.append(("── YOUR LINE", src, C['gold']))
            for i in range(1, 4):
                rows.append((f"🟢 Below {i}", src - step*i, C['green']))

        elif rects:
            rect = next((r for r in rects if r.rect_valid), None)
            if rect is None:
                return
            top = rect.rect_top
            bot = rect.rect_bottom
            for i in range(3, 0, -1):
                rows.append((f"🟠 Above {i}", top + step*i, C['orange']))
            rows.append((f"── TOP  {top:.5f}", top, C['gold']))
            rows.append(
                (f"── ZONE ({'%.5f' % (top - bot)})", (top+bot)/2, C['txt3']))
            rows.append((f"── BOT  {bot:.5f}", bot, C['gold']))
            for i in range(1, 4):
                rows.append((f"🟢 Below {i}", bot - step*i, C['green']))

        if not rows:
            return
        self.lvl_tbl.setRowCount(len(rows))
        for r, (lbl, price, clr) in enumerate(rows):
            dist = f"{'+' if price-cur >= 0 else ''}{price-cur:.2f}" if cur else "—"
            for c, v in enumerate([lbl, f"{price:.5f}", dist]):
                it = QTableWidgetItem(v)
                it.setForeground(QColor(clr))
                self.lvl_tbl.setItem(r, c, it)

    def _populate_ord_table(self, orders):
        self.ord_pending.setRowCount(len(orders))
        for r, o in enumerate(orders):
            clr = QColor(C['green'] if o["type"] == "BUY_STOP" else C['red'])
            for c, v in enumerate([f"L{o['level']}", o["type"],
                                   f"{o['entry']:.5f}", f"{o['sl']:.5f}", f"{o['tp']:.5f}"]):
                it = QTableWidgetItem(v)
                it.setForeground(clr)
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
            err = getattr(self, '_run_err',
                          None) or 'Unknown error — check log'
            self._on_log(
                f"{datetime.now().strftime('%H:%M:%S')}  ❌ Backtest failed: {err}", "ERROR")
            return
        r = self._bt_result
        if r.candles_used == 0:
            self._on_log(
                f"{datetime.now().strftime('%H:%M:%S')}  ❌ No candles returned — check symbol name and MT5 connection", "ERROR")
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
        self._on_log(
            f"{ts}  🔬 {r.candles_used} bars | W:{len(r.wins)} L:{len(r.losses)} | {pp:+.1f} pips", "BT")

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
            dir_clr = QColor(C['green'] if direction ==
                             "BUY_STOP" else C['red'])
            emoji = {"PENDING": "⏳", "TRIGGERED": "🔵", "TP": "✅",
                     "SL": "❌", "OPEN": "🔵"}.get(state, "?")
            entry_touched = (direction == "BUY_STOP" and bar_high >= o["entry"]) or (
                direction == "SELL_STOP" and bar_low <= o["entry"])
            sl_tp_str = f"SL {o['sl']:.5f} / TP {o['tp']:.5f}"
            gen_colors = ["#F5A623", "#00BCD4",
                          "#B388FF", "#FF8C00", "#00FF88"]
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
        self._stop()
        e.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = GUI()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
