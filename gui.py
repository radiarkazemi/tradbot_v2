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
    QProgressBar, QCheckBox, QSlider, QScrollArea, QFormLayout, QGridLayout,
    QLineEdit,
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


from watcher import WatcherWorker
import session_report as sr

# ── Main Window ──────────────────────────────────────────────────
class GUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TraderBot v1")
        self.setMinimumSize(820, 600)
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
        self._session_events = []  # list of session event dicts
        self._session_start = datetime.now()
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
        spl.setSizes([360, 740])
        spl.setCollapsible(0, False)
        spl.setCollapsible(1, False)
        # Left panel: minimum 280px, can grow
        spl.widget(0).setMinimumWidth(280)
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
        hl.addWidget(self._vline())
        # Strategy phase indicator
        self.lbl_phase = QLabel("Phase: —")
        self.lbl_phase.setStyleSheet(f"color:{C['txt3']};font-size:10px;font-family:Consolas;")
        hl.addWidget(self.lbl_phase)
        return w

    def _left_panel(self):
        # Wrap in scroll area so left panel works at any window height
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
            "QScrollBar:vertical { width: 6px; background: transparent; }"
            "QScrollBar::handle:vertical { background: #2A3550; border-radius: 3px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }")
        w = QWidget(); vl = QVBoxLayout(w); vl.setSpacing(8); vl.setContentsMargins(0,0,4,0)

        # ── Controls ─────────────────────────────────────────────
        grp = QGroupBox("⚙️  Bot Control"); cl = QVBoxLayout(grp); cl.setSpacing(4)

        def _lbl(text, tooltip=""):
            l = QLabel(text)
            l.setStyleSheet(f"color:{C['txt2']};font-size:11px;")
            l.setWordWrap(False)
            if tooltip: l.setToolTip(tooltip)
            return l

        def _row(label, widget, tooltip=""):
            hl = QHBoxLayout(); hl.setSpacing(8)
            lw = _lbl(label, tooltip)
            lw.setFixedWidth(90)
            hl.addWidget(lw)
            widget.setMinimumWidth(100)
            widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            hl.addWidget(widget)
            cl.addLayout(hl)

        # Symbol
        self.sym_combo = QComboBox(); self.sym_combo.setEditable(True)
        self.sym_combo.addItems(["XAUUSD_i","EURUSD_i","GBPUSD_i",
                                  "XAUUSD","EURUSD","GBPUSD","NAS100","US30","BTCUSD"])
        self.sym_combo.setCurrentText("EURUSD")
        self.sym_combo.currentTextChanged.connect(self._on_symbol_changed)
        _row("🎯 Symbol:", self.sym_combo, "The symbol to watch on MT5")

        # Pip step
        self.spin_pip = QDoubleSpinBox()
        self.spin_pip.setRange(0.1, 500.0); self.spin_pip.setSingleStep(1.0)
        self.spin_pip.setValue(PIP_STEP); self.spin_pip.setDecimals(1)
        _row("📏 Pip step:", self.spin_pip, "Distance between each level (L1/L2/L3) in pips")

        # TP pips with checkbox
        tp_row = QHBoxLayout(); tp_row.setSpacing(8)
        lbl_tp = _lbl("🎯 TP pips:")
        lbl_tp.setFixedWidth(90)
        tp_row.addWidget(lbl_tp)
        self.chk_tp = QCheckBox()
        self.chk_tp.setChecked(False)
        self.chk_tp.setToolTip("Enable fixed TP. Unchecked = no TP set (orders run until SL or manual close)")
        self.chk_tp.setStyleSheet(f"color:{C['txt2']};")
        tp_row.addWidget(self.chk_tp)
        self.spin_tp = QDoubleSpinBox()
        self.spin_tp.setRange(1, 1000.0); self.spin_tp.setSingleStep(5.0)
        self.spin_tp.setValue(50); self.spin_tp.setDecimals(1)
        self.spin_tp.setEnabled(False)
        self.spin_tp.setMinimumWidth(70)
        self.spin_tp.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.chk_tp.toggled.connect(self.spin_tp.setEnabled)
        tp_row.addWidget(self.spin_tp)
        cl.addLayout(tp_row)

        # Lot size
        self.spin_lot = QDoubleSpinBox()
        self.spin_lot.setRange(0.01, 100.0); self.spin_lot.setSingleStep(0.01)
        self.spin_lot.setValue(LOT_SIZE); self.spin_lot.setDecimals(2)
        _row("📦 Lot size:", self.spin_lot, "Lot size per order")

        # Spawn level
        self.combo_spawn = QComboBox()
        self.combo_spawn.addItems(["L2 only", "L3 only", "L2 and L3"])
        self.combo_spawn.setCurrentText("L2 and L3")
        _row("🔄 Spawn on:", self.combo_spawn,
             "Which activated level spawns a new cascading round")

        # Separator
        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color:{C['border']};"); cl.addWidget(sep)

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

        # Manual trigger button — places orders on current source line immediately
        self.btn_manual = QPushButton("🖐  Manual Trigger")
        self.btn_manual.setMinimumHeight(30)
        self.btn_manual.setEnabled(False)
        self.btn_manual.setToolTip(
            "Manually place orders on all watched source lines right now.\n"
            "Useful for testing or when you want to force entry\n"
            "without waiting for the candle to touch the line.")
        self.btn_manual.setStyleSheet(
            f"QPushButton {{ background:{C['bg']};color:{C['gold']};"
            f"border:1px solid {C['gold']};border-radius:4px;font-size:11px; }}"
            f"QPushButton:hover {{ background:{C['gold']};color:#000; }}"
            f"QPushButton:disabled {{ color:{C['txt3']};border-color:{C['border']}; }}")
        self.btn_manual.clicked.connect(self._manual_trigger)
        cl.addWidget(self.btn_manual)

        self.chk_follow = QCheckBox("🔗  Follow object when moved")
        self.chk_follow.setChecked(True)
        self.chk_follow.setStyleSheet(f"color:{C['txt2']};font-size:10px;padding:2px 0;")
        self.chk_follow.setToolTip("Level lines redraw if you drag the drawn object")
        cl.addWidget(self.chk_follow)
        vl.addWidget(grp)

        # ── Strategy summary ─────────────────────────────────────
        grp_strat = QGroupBox("📊  Strategy State")
        sv = QGridLayout(grp_strat); sv.setSpacing(4); sv.setContentsMargins(8,6,8,6)

        def _stat_label(text, color):
            l = QLabel(text)
            l.setStyleSheet(f"color:{color};font-family:Consolas;font-size:11px;font-weight:bold;")
            return l

        def _stat_key(text):
            l = QLabel(text)
            l.setStyleSheet(f"color:{C['txt3']};font-size:10px;")
            return l

        self.lbl_source_price = _stat_label("—", C['gold'])
        self.lbl_rounds_info  = _stat_label("0 / 9", C['cyan'])
        self.lbl_waiting      = _stat_label("Draw a line on chart", C['txt3'])
        self.lbl_direction    = _stat_label("—", C['txt2'])

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

        # ── Peak P&L Dashboard + Auto-Close ──────────────────────
        grp_peak = QGroupBox("📈  Peak P&L Tracker & Auto-Close")
        grp_peak.setStyleSheet(
            f"QGroupBox {{ background:{C['card']};border:1px solid {C['border_hi']};"
            f"border-radius:6px;margin-top:14px;padding:8px 6px 6px 6px;"
            f"font-size:10px;font-weight:bold;color:{C['gold']}; }}"
            f"QGroupBox::title {{ subcontrol-origin:margin;left:10px;padding:0 4px; }}")
        pv = QVBoxLayout(grp_peak); pv.setSpacing(5); pv.setContentsMargins(8,6,8,6)

        # Big P&L numbers row
        pnl_row = QHBoxLayout(); pnl_row.setSpacing(6)

        def _big_card(key, label, color):
            f = QFrame()
            f.setStyleSheet(
                f"background:{C['bg']};border:1px solid {C['border']};"
                f"border-radius:5px;")
            fv = QVBoxLayout(f); fv.setContentsMargins(6,4,6,4); fv.setSpacing(1)
            lt = QLabel(label)
            lt.setStyleSheet(f"color:{C['txt3']};font-size:8px;font-weight:bold;letter-spacing:1px;")
            lt.setAlignment(Qt.AlignCenter)
            lv = QLabel("—")
            lv.setStyleSheet(f"color:{color};font-size:17px;font-weight:bold;font-family:Consolas;")
            lv.setAlignment(Qt.AlignCenter)
            fv.addWidget(lt); fv.addWidget(lv)
            self._peak_cards[key] = lv
            return f

        self._peak_cards = {}
        pnl_row.addWidget(_big_card("current",  "NOW",       C['cyan']))
        pnl_row.addWidget(_big_card("peak",     "PEAK",      C['green']))
        pnl_row.addWidget(_big_card("drawdown", "FROM PEAK", C['red']))
        pv.addLayout(pnl_row)

        # Velocity card — shows P&L speed
        vel_row = QHBoxLayout(); vel_row.setSpacing(6)
        pnl_row.addWidget(_big_card("velocity", "$/MIN",     C['gold']))
        pv.addLayout(vel_row)

        # ── Auto-close rules (separator) ─────────────────────────
        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color:{C['border_hi']};")
        pv.addWidget(sep)

        ac_title = QLabel("⚡ Auto-Close Rules")
        ac_title.setStyleSheet(
            f"color:{C['gold']};font-size:10px;font-weight:bold;letter-spacing:1px;")
        pv.addWidget(ac_title)

        def _ac_row(label, spin_min, spin_max, spin_default, suffix, tip, chk_default=False):
            row = QHBoxLayout(); row.setSpacing(6)
            chk = QCheckBox()
            chk.setChecked(chk_default)
            chk.setStyleSheet(f"color:{C['txt2']};")
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color:{C['txt2']};font-size:10px;")
            lbl.setWordWrap(True)
            lbl.setToolTip(tip)
            spin = QDoubleSpinBox()
            spin.setRange(spin_min, spin_max)
            spin.setValue(spin_default)
            spin.setDecimals(1)
            spin.setSuffix(suffix)
            spin.setMinimumWidth(75)
            spin.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            spin.setToolTip(tip)
            spin.setEnabled(chk_default)
            chk.toggled.connect(spin.setEnabled)
            row.addWidget(chk)
            row.addWidget(lbl)
            row.addWidget(spin)
            pv.addLayout(row)
            return chk, spin

        # Rule 1: Minimum profit target (blocks ALL auto-close below this)
        r1_row = QHBoxLayout(); r1_row.setSpacing(6)
        self.chk_min_profit = QCheckBox()
        self.chk_min_profit.setChecked(True)
        self.chk_min_profit.setStyleSheet(f"color:{C['txt2']};")
        lbl_mp = QLabel("Min profit to close:")
        lbl_mp.setStyleSheet(f"color:{C['txt2']};font-size:10px;")
        lbl_mp.setToolTip(
            "Auto-close will NEVER fire unless total P&L is above this.\n"
            "Click '⟳ Calc' to auto-calculate based on your symbol + lot size.\n"
            "Formula: lot × pip_value × 50 pips (approx 1 good cascade)")
        self.spin_min_profit = QDoubleSpinBox()
        self.spin_min_profit.setRange(0, 10000)
        self.spin_min_profit.setValue(70.0)
        self.spin_min_profit.setDecimals(1)
        self.spin_min_profit.setSuffix(" $")
        self.spin_min_profit.setMinimumWidth(70)
        self.spin_min_profit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.spin_min_profit.setEnabled(True)
        self.chk_min_profit.toggled.connect(self.spin_min_profit.setEnabled)
        btn_calc = QPushButton("⟳")
        btn_calc.setFixedSize(24, 24)
        btn_calc.setToolTip("Auto-calculate min profit for current symbol + lot size")
        btn_calc.setStyleSheet(
            f"background:{C['border']};color:{C['gold']};border:1px solid {C['gold']};"
            f"border-radius:3px;font-size:11px;font-weight:bold;padding:0;")
        btn_calc.clicked.connect(self._calc_min_profit)
        r1_row.addWidget(self.chk_min_profit)
        r1_row.addWidget(lbl_mp)
        r1_row.addWidget(self.spin_min_profit)
        r1_row.addWidget(btn_calc)
        pv.addLayout(r1_row)

        # Rule 2: Velocity close (blowoff top detection)
        self.chk_velocity, self.spin_velocity = _ac_row(
            "Velocity close ($/min):",
            1, 1000, 20.0, " $/m",
            "Close when P&L gains this much in 60 seconds.\n"
            "Catches the blowoff top — a fast spike followed by reversal.\n"
            "Example: 20 = close when you gain $20 in under 60 seconds.\n"
            "Has a 30s countdown you can cancel.",
            True)

        # Rule 3: Drawdown close (reversal protection)
        self.chk_drawdown, self.spin_drawdown = _ac_row(
            "Drawdown close ($):",
            1, 1000, 25.0, " $",
            "Close when P&L drops this much from its session peak.\n"
            "Protects from holding through a full reversal.\n"
            "Example: 25 = if peak was $110, close if P&L falls to $85.\n"
            "Only fires if you're still above the minimum profit target.",
            True)

        # Rule 4: Rounds complete close
        self.chk_rounds_close, self.spin_rounds_wait = _ac_row(
            "Close after round 9/9 +",
            1, 60, 10.0, " min",
            "After all 9 rounds complete, start a countdown.\n"
            "If no new high is made within this time, close everything.\n"
            "Prevents holding dead positions after the cascade exhausts.",
            True)

        # Alert-only threshold (existing feature, kept)
        alert_row = QHBoxLayout(); alert_row.setSpacing(6)
        lbl_al = QLabel("🔔 Alert only at:")
        lbl_al.setStyleSheet(f"color:{C['txt2']};font-size:10px;")
        alert_row.addWidget(lbl_al)
        self.spin_alert = QDoubleSpinBox()
        self.spin_alert.setRange(1, 10000); self.spin_alert.setValue(50)
        self.spin_alert.setDecimals(1); self.spin_alert.setSuffix(" $")
        self.spin_alert.setMinimumWidth(75)
        self.spin_alert.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.spin_alert.setToolTip("Sound + flash alert only. Does NOT auto-close.")
        alert_row.addWidget(self.spin_alert)
        self.chk_alert = QCheckBox("on")
        self.chk_alert.setChecked(True)
        self.chk_alert.setStyleSheet(f"color:{C['txt2']};font-size:10px;")
        alert_row.addWidget(self.chk_alert)
        alert_row.addStretch()
        pv.addLayout(alert_row)

        # Countdown banner (hidden until auto-close fires)
        self.lbl_autoclose_banner = QLabel("")
        self.lbl_autoclose_banner.setStyleSheet(
            f"color:{C['red']};font-size:12px;font-weight:bold;"
            f"background:{C['red_dk']};border:1px solid {C['red']};"
            f"border-radius:4px;padding:4px;")
        self.lbl_autoclose_banner.setAlignment(Qt.AlignCenter)
        self.lbl_autoclose_banner.setWordWrap(True)
        self.lbl_autoclose_banner.hide()
        pv.addWidget(self.lbl_autoclose_banner)

        # Cancel auto-close countdown button
        self.btn_cancel_autoclose = QPushButton("✋  Cancel Auto-Close")
        self.btn_cancel_autoclose.setStyleSheet(
            f"QPushButton {{ background:{C['orange']};color:#000;"
            f"font-weight:bold;border-radius:4px;font-size:11px; }}"
            f"QPushButton:hover {{ background:#FFB300; }}")
        self.btn_cancel_autoclose.hide()
        self.btn_cancel_autoclose.clicked.connect(self._cancel_autoclose)
        pv.addWidget(self.btn_cancel_autoclose)

        # Status line
        self.lbl_peak_status = QLabel("Start watcher to begin tracking")
        self.lbl_peak_status.setStyleSheet(
            f"color:{C['txt3']};font-size:9px;font-family:Consolas;")
        self.lbl_peak_status.setWordWrap(True)
        pv.addWidget(self.lbl_peak_status)

        # Close All & Reset button
        self.btn_close_reset = QPushButton("🏁  Close All Positions & Reset")
        self.btn_close_reset.setMinimumHeight(38)
        self.btn_close_reset.setStyleSheet(
            f"QPushButton {{ background:#1A0A2A;color:{C['purple']};"
            f"border:2px solid {C['purple']};border-radius:5px;"
            f"font-weight:bold;font-size:13px; }}"
            f"QPushButton:hover {{ background:{C['purple']};color:#fff; }}"
            f"QPushButton:pressed {{ background:#0A0015; }}")
        self.btn_close_reset.setToolTip(
            "Close ALL open positions + cancel ALL pending orders\n"
            "then reset the bot state. Use at the peak.")
        self.btn_close_reset.clicked.connect(self._close_all_and_reset)
        pv.addWidget(self.btn_close_reset)

        vl.addWidget(grp_peak)

        # Internal peak tracking state
        self._session_peak_pnl     = 0.0
        self._session_peak_alerted = False
        self._alert_was_above      = False
        self._pnl_history          = []   # [(timestamp, pnl), ...] rolling 90s window
        self._autoclose_countdown  = 0    # seconds remaining in countdown
        self._autoclose_reason     = ""
        self._rounds9_time         = None  # when spawn_rounds first hit 9
        self._rounds9_peak_at_9    = 0.0
        self._peak_timer = QTimer()
        self._peak_timer.timeout.connect(self._refresh_peak_pnl)
        self._peak_timer.start(1000)  # update every second

        # ── Orders ───────────────────────────────────────────────
        grp2 = QGroupBox("Live Orders"); ol = QVBoxLayout(grp2)
        self.btn_place = QPushButton("🎯  Place Buy/Sell Stops")
        self.btn_place.setObjectName("btn_orders"); self.btn_place.setMinimumHeight(34)
        self.btn_place.setEnabled(False); self.btn_place.clicked.connect(self._place_orders)
        ol.addWidget(self.btn_place)
        self.btn_cancel = QPushButton("🗑️  Cancel All Bot Orders")
        self.btn_cancel.setObjectName("btn_cancel"); self.btn_cancel.clicked.connect(self._cancel_orders)
        ol.addWidget(self.btn_cancel)

        # ── Risk-Free section ─────────────────────────────────────
        grp_rf = QGroupBox("🛡️  Risk-Free Mode")
        rf_layout = QVBoxLayout(grp_rf); rf_layout.setSpacing(6)

        # Row 1: side selector
        rf_row1 = QHBoxLayout(); rf_row1.setSpacing(6)
        lbl_ks = QLabel("Keep side:")
        lbl_ks.setStyleSheet(f"color:{C['txt2']};font-size:11px;")
        rf_row1.addWidget(lbl_ks)
        self.combo_rf_side = QComboBox()
        self.combo_rf_side.addItems(["BUY (keep buys)", "SELL (keep sells)"])
        self.combo_rf_side.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.combo_rf_side.currentTextChanged.connect(self._refresh_rf_advisor)
        rf_row1.addWidget(self.combo_rf_side)
        rf_layout.addLayout(rf_row1)

        # ── RF Advisor panel ──────────────────────────────────────
        adv_frame = QFrame()
        adv_frame.setStyleSheet(
            f"background:{C['card']};border:1px solid {C['border']};border-radius:5px;")
        adv_layout = QVBoxLayout(adv_frame)
        adv_layout.setContentsMargins(8, 6, 8, 6); adv_layout.setSpacing(4)

        adv_title = QLabel("📊 Suggested SL levels:")
        adv_title.setStyleSheet(f"color:{C['txt3']};font-size:9px;font-weight:bold;")
        adv_layout.addWidget(adv_title)

        # Three suggestion rows: Conservative / Balanced / Aggressive
        self._rf_suggestions = {}
        for key, label, color, tip in [
            ("safe",  "🟢 Conservative (all in profit):",    C["green"],
             "SL just below the SMALLEST (most exposed) position\n"
             "Every kept position is profitable at this SL price"),
            ("mid",   "🟡 Balanced (avg entry):",            C["gold"],
             "SL at average entry price of all kept positions\n"
             "Half the positions in profit, half at break-even zone"),
            ("bold",  "🔴 Aggressive (best pos safe only):", C["red"],
             "SL just below the BEST (most profitable) position's entry\n"
             "Only the most profitable position is guaranteed safe"),
        ]:
            row = QHBoxLayout(); row.setSpacing(6)
            lbl_key = QLabel(label)
            lbl_key.setStyleSheet(f"color:{C['txt3']};font-size:9px;")
            lbl_key.setWordWrap(True)
            lbl_key.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            lbl_key.setToolTip(tip)
            lbl_val = QLabel("—")
            lbl_val.setStyleSheet(
                f"color:{color};font-family:Consolas;font-size:11px;font-weight:bold;")
            btn_use = QPushButton("Use")
            btn_use.setFixedSize(36, 20)
            btn_use.setStyleSheet(
                f"background:{C['border']};color:{C['txt2']};font-size:9px;"
                f"border:1px solid {C['border_hi']};border-radius:3px;padding:0;")
            btn_use.clicked.connect(lambda _, k=key: self._rf_use_suggestion(k))
            row.addWidget(lbl_key); row.addWidget(lbl_val); row.addWidget(btn_use)
            adv_layout.addLayout(row)
            self._rf_suggestions[key] = {"label": lbl_val, "value": None}

        # Positions summary line
        self.lbl_rf_pos_summary = QLabel("Click 🔄 to load positions")
        self.lbl_rf_pos_summary.setStyleSheet(f"color:{C['txt3']};font-size:9px;")
        self.lbl_rf_pos_summary.setWordWrap(True)
        adv_layout.addWidget(self.lbl_rf_pos_summary)

        btn_adv_refresh = QPushButton("🔄 Refresh")
        btn_adv_refresh.setFixedHeight(22)
        btn_adv_refresh.clicked.connect(self._refresh_rf_advisor)
        adv_layout.addWidget(btn_adv_refresh)
        rf_layout.addWidget(adv_frame)

        # Row 2: exit price label + input
        rf_row2a = QHBoxLayout(); rf_row2a.setSpacing(6)
        lbl_ep = QLabel("Exit price:")
        lbl_ep.setStyleSheet(f"color:{C['txt2']};font-size:11px;")
        rf_row2a.addWidget(lbl_ep)
        self.edit_rf_price = QLineEdit()
        self.edit_rf_price.setPlaceholderText("e.g. 1.16420")
        self.edit_rf_price.setToolTip(
            "Price at which all kept positions close.\n"
            "Leave blank to use average entry of kept positions.\n"
            "Can be changed while RF is active using Update SL.")
        self.edit_rf_price.setMinimumWidth(70)
        self.edit_rf_price.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        rf_row2a.addWidget(self.edit_rf_price)
        rf_layout.addLayout(rf_row2a)
        # Row 2b: update SL button (full width)
        self.btn_rf_update = QPushButton("📍 Update SL Price")
        self.btn_rf_update.setMinimumHeight(26)
        self.btn_rf_update.setEnabled(False)
        self.btn_rf_update.setToolTip("Move the SL exit price while RF is active")
        self.btn_rf_update.clicked.connect(self._update_rf_sl)
        rf_layout.addWidget(self.btn_rf_update)

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
        grp3 = QGroupBox("Detected Levels"); ll = QVBoxLayout(grp3)
        self.lvl_tbl = QTableWidget(0, 3)
        self.lvl_tbl.setHorizontalHeaderLabels(["Level","Price","Dist"])
        self.lvl_tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.lvl_tbl.setAlternatingRowColors(True)
        self.lvl_tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        self.lvl_tbl.verticalHeader().setVisible(False)
        ll.addWidget(self.lvl_tbl)
        vl.addWidget(grp3, 1)
        scroll.setWidget(w)
        return scroll

    def _right_panel(self):
        w = QWidget(); vl = QVBoxLayout(w); vl.setSpacing(0); vl.setContentsMargins(4,0,0,0)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._tab_log(),       "📋  Log")
        self.tabs.addTab(self._tab_orders(),    "📊  Orders")
        self.tabs.addTab(self._tab_scoreboard(),"🏆  Scoreboard")
        self.tabs.addTab(self._tab_backtest(),  "🔬  Backtest")
        self.tabs.addTab(self._tab_report(),    "📁  Session Report")
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
        w = QWidget(); vl = QVBoxLayout(w); vl.setContentsMargins(6,6,6,6); vl.setSpacing(6)

        # ── Summary bar ───────────────────────────────────────────
        sum_row = QHBoxLayout(); sum_row.setSpacing(8)

        def _mini_card(key, label, color):
            f = QFrame()
            f.setStyleSheet(f"background:{C['card']};border:1px solid {C['border']};border-radius:6px;")
            fv = QVBoxLayout(f); fv.setContentsMargins(8,4,8,4); fv.setSpacing(0)
            lt = QLabel(label); lt.setStyleSheet(f"color:{C['txt3']};font-size:8px;font-weight:bold;")
            lt.setAlignment(Qt.AlignCenter)
            lv = QLabel("—"); lv.setStyleSheet(f"color:{color};font-size:15px;font-weight:bold;font-family:Consolas;")
            lv.setAlignment(Qt.AlignCenter)
            fv.addWidget(lt); fv.addWidget(lv)
            self._ord_summary[key] = lv
            return f

        self._ord_summary = {}
        sum_row.addWidget(_mini_card("pending",  "PENDING",   C['cyan']))
        sum_row.addWidget(_mini_card("active",   "ACTIVE",    C['gold']))
        sum_row.addWidget(_mini_card("buy_pos",  "BUY POS",   C['green']))
        sum_row.addWidget(_mini_card("sell_pos", "SELL POS",  C['red']))
        sum_row.addWidget(_mini_card("total_pnl","OPEN P&L",  C['purple']))
        sum_row.addWidget(_mini_card("rounds",   "ROUNDS",    C['txt2']))
        vl.addLayout(sum_row)

        # ── Pending orders table ──────────────────────────────────
        grp_pending = QGroupBox("🔵  Pending Orders")
        pv = QVBoxLayout(grp_pending)
        self.ord_pending = QTableWidget(0, 7)
        self.ord_pending.setHorizontalHeaderLabels(
            ["Gen","Lvl","Type","Entry","SL","TP","Pips SL"])
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
            ["Gen","Lvl","Type","Entry","SL","TP","P&L"])
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
        w = QWidget(); vl = QVBoxLayout(w); vl.setContentsMargins(8,8,8,8); vl.setSpacing(8)

        # ── Summary cards row ─────────────────────────────────────
        cards_row = QHBoxLayout(); cards_row.setSpacing(6)

        def _card(key, label, color):
            card = QFrame()
            card.setStyleSheet(f"background:{C['card']};border:1px solid {C['border']};border-radius:8px;")
            cv = QVBoxLayout(card); cv.setContentsMargins(12,8,12,8); cv.setSpacing(2)
            lt = QLabel(label); lt.setStyleSheet(f"color:{C['txt3']};font-size:9px;font-weight:bold;letter-spacing:1px;")
            lt.setAlignment(Qt.AlignCenter)
            lv = QLabel("—"); lv.setStyleSheet(f"color:{color};font-size:20px;font-weight:bold;font-family:Consolas;")
            lv.setAlignment(Qt.AlignCenter)
            cv.addWidget(lt); cv.addWidget(lv)
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
            ["Ticket","Type","Entry","Close","Pips","Profit","Time"])
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
            if not _mt5.initialize(): return
            _mt5.login(MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER)

            acc = _mt5.account_info()
            if not acc: return

            cur_bal = acc.balance
            equity  = acc.equity

            # Start balance — store once
            if not hasattr(self, "_start_balance"):
                self._start_balance = cur_bal

            start_bal = self._start_balance
            pnl       = cur_bal - start_bal

            # Get closed deals (history) for this magic number
            from datetime import datetime, timezone, timedelta
            since = datetime.now(timezone.utc) - timedelta(days=30)
            deals = _mt5.history_deals_get(since, datetime.now(timezone.utc))

            bot_deals = []
            if deals:
                for d in deals:
                    if d.magic == MAGIC_NUMBER and d.entry == 1:  # entry=1 means close/out deal
                        bot_deals.append(d)

            wins   = sum(1 for d in bot_deals if d.profit > 0)
            losses = sum(1 for d in bot_deals if d.profit < 0)
            total  = wins + losses
            ratio  = f"{wins/total*100:.0f}%" if total > 0 else "—"

            # Update cards
            self._sb_cards["start_bal"].setText(f"${start_bal:.2f}")
            self._sb_cards["cur_bal"].setText(f"${cur_bal:.2f}")
            pnl_color = C['green'] if pnl >= 0 else C['red']
            self._sb_cards["pnl"].setText(f"{'+'if pnl>=0 else ''}{pnl:.2f}")
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
                pips_val = d.profit / (LOT_SIZE * pip * 100000) if pip > 0 else 0
                clr = QColor(C['green'] if d.profit > 0 else C['red'])
                close_time = datetime.fromtimestamp(d.time).strftime("%m-%d %H:%M")
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
            if not mt5.initialize():
                self._on_log(f"{datetime.now().strftime('%H:%M:%S')}  ⚠️  MT5 not running — open MetaTrader 5 first", "WARN")
                return
            ok = mt5.login(MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER)
            if not ok:
                err = mt5.last_error()
                self._on_log(f"{datetime.now().strftime('%H:%M:%S')}  ⚠️  MT5 login failed: {err} | Check config.py credentials", "WARN")
                return
            # Symbol combos pre-populated with common symbols
        except Exception:
            pass

    def _start(self):
        self._pip_step = self.spin_pip.value()
        self.spin_pip.setEnabled(False)
        active_sym   = self.sym_combo.currentText().strip() or WATCH_SYMBOL
        self._tp_pips    = self.spin_tp.value()
        self._spawn_lvls = self.combo_spawn.currentText()
        self._lot_size   = self.spin_lot.value()
        self._worker = WatcherWorker(self._sig, self._pip_step, symbol=active_sym,
                                      tp_pips=self._tp_pips, spawn_on=self._spawn_lvls,
                                      lot_size=self._lot_size)
        self._worker.follow_enabled = self.chk_follow.isChecked()
        self._worker.start()
        self.btn_start.setEnabled(False); self.btn_stop.setEnabled(True)
        self.btn_manual.setEnabled(True)
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
        self.btn_manual.setEnabled(False)
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

    def _refresh_orders_tab(self):
        """Pull live pending + active orders from MT5 and update the Orders tab."""
        try:
            import MetaTrader5 as _mt5
            if not _mt5.initialize(): return
            sym = self.sym_combo.currentText().strip() or WATCH_SYMBOL
            pip = get_pip_size(sym)

            # ── Pending orders ────────────────────────────────────
            pending = _mt5.orders_get(symbol=sym) or []
            bot_pending = [o for o in pending if o.magic == MAGIC_NUMBER]

            self.ord_pending.setRowCount(0)
            for o in sorted(bot_pending, key=lambda x: x.price_open):
                cmt  = getattr(o, 'comment', '')
                # Parse Gen/Lvl from comment e.g. TB_G0L1B
                gen_str = "?"
                lvl_str = "?"
                import re
                m = re.search(r'G(\d+)L(\d+)', cmt)
                if m: gen_str, lvl_str = m.group(1), m.group(2)
                is_buy = o.type == 2  # ORDER_TYPE_BUY_STOP = 2
                t_str  = "BUY_STOP" if is_buy else "SELL_STOP"
                clr    = QColor(C['green'] if is_buy else C['red'])
                sl_pips = abs(o.price_open - o.sl) / pip if pip > 0 else 0
                row = self.ord_pending.rowCount()
                self.ord_pending.insertRow(row)
                gen_colors = [C['gold'], C['cyan'], C['purple'], C['orange'], C['orange']]
                try: gc = QColor(gen_colors[int(gen_str)])
                except: gc = QColor(C['txt2'])
                vals = [f"G{gen_str}", f"L{lvl_str}", t_str,
                        f"{o.price_open:.5f}", f"{o.sl:.5f}",
                        f"{o.tp:.5f}" if o.tp > 0 else "—",
                        f"{sl_pips:.1f}"]
                for c, v in enumerate(vals):
                    it = QTableWidgetItem(v)
                    it.setForeground(gc if c == 0 else clr)
                    # Highlight L1 rows slightly
                    if lvl_str == "1":
                        it.setBackground(QColor("#1A2520" if is_buy else "#251A1A"))
                    self.ord_pending.setItem(row, c, it)

            # ── Active positions ──────────────────────────────────
            positions = _mt5.positions_get(symbol=sym) or []
            bot_pos   = [p for p in positions if p.magic == MAGIC_NUMBER]

            self.ord_active.setRowCount(0)
            total_pnl = 0.0
            buy_count = sell_count = 0
            for p in sorted(bot_pos, key=lambda x: x.price_open):
                cmt = getattr(p, 'comment', '')
                gen_str = lvl_str = "?"
                import re
                m = re.search(r'G(\d+)L(\d+)', cmt)
                if m: gen_str, lvl_str = m.group(1), m.group(2)
                is_buy = p.type == 0
                t_str  = "BUY" if is_buy else "SELL"
                if is_buy: buy_count  += 1
                else:      sell_count += 1
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
                        gen_colors = [C['gold'], C['cyan'], C['purple'], C['orange'], C['orange']]
                        try: it.setForeground(QColor(gen_colors[int(gen_str)]))
                        except: pass
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
                rounds = getattr(self._worker, 'spawn_rounds', 0) if self._worker else 0
                self._ord_summary["rounds"].setText(str(rounds))

            # ── Tab title with count ──────────────────────────────
            total = len(bot_pending) + len(bot_pos)
            self.tabs.setTabText(1, f"📊  Orders ({total})" if total else "📊  Orders")
            # Update group box titles with counts
            self.ord_pending.parent().parent().setTitle(
                f"🔵  Pending Orders ({len(bot_pending)})")
            self.ord_active.parent().parent().setTitle(
                f"📊  Active Positions ({len(bot_pos)}) | P&L: {total_pnl:+.2f}")

        except Exception as e:
            pass  # Non-critical refresh failure

    def _refresh_rf_advisor(self):
        """Calculate and display the 3 suggested SL levels based on live positions."""
        try:
            import MetaTrader5 as _mt5
            sym       = self.sym_combo.currentText().strip() or WATCH_SYMBOL
            pip       = get_pip_size(sym)
            keep_side = "BUY" if "BUY" in self.combo_rf_side.currentText() else "SELL"

            positions = _mt5.positions_get(symbol=sym) or []
            keep_pos  = [p for p in positions
                         if p.magic == MAGIC_NUMBER and
                         ((p.type == 0) == (keep_side == "BUY"))]

            # Reset
            for k in self._rf_suggestions:
                self._rf_suggestions[k]["label"].setText("—")
                self._rf_suggestions[k]["value"] = None

            if not keep_pos:
                self.lbl_rf_pos_summary.setText(
                    f"No {keep_side} positions found — start watcher and place orders first")
                return

            entries = sorted([p.price_open for p in keep_pos],
                             reverse=(keep_side == "BUY"))
            # For BUY: sorted descending → entries[0] = best (highest entry if price went up)
            # For SELL: sorted ascending → entries[0] = best (lowest entry if price went down)
            # Actually sort by current profit
            keep_pos_sorted = sorted(keep_pos, key=lambda p: p.profit, reverse=True)

            best_entry  = keep_pos_sorted[0].price_open   # most profitable position
            worst_entry = keep_pos_sorted[-1].price_open  # least profitable position
            avg_entry   = sum(p.price_open for p in keep_pos) / len(keep_pos)
            total_pnl   = sum(p.profit for p in keep_pos)

            # Buffer: 1 pip below entry for BUY (protects from spread noise)
            buf = pip * 1.0

            if keep_side == "BUY":
                # Conservative: SL below worst (smallest profit) entry — ALL positions safe
                safe_price = round(worst_entry - buf, 5)
                # Balanced: SL at average entry
                mid_price  = round(avg_entry - buf, 5)
                # Aggressive: SL just below BEST entry only
                bold_price = round(best_entry - buf, 5)
            else:  # SELL
                safe_price = round(worst_entry + buf, 5)
                mid_price  = round(avg_entry  + buf, 5)
                bold_price = round(best_entry + buf, 5)

            # Update suggestion labels and store values
            self._rf_suggestions["safe"]["label"].setText(f"{safe_price:.5f}")
            self._rf_suggestions["safe"]["value"] = safe_price
            self._rf_suggestions["mid"]["label"].setText(f"{mid_price:.5f}")
            self._rf_suggestions["mid"]["value"] = mid_price
            self._rf_suggestions["bold"]["label"].setText(f"{bold_price:.5f}")
            self._rf_suggestions["bold"]["value"] = bold_price

            # Summary: show each position's entry and current P&L
            lines = [f"  {keep_side} positions ({len(keep_pos)}) | Total P&L: {total_pnl:+.2f}"]
            for i, p in enumerate(keep_pos_sorted):
                rank = "★" if i == 0 else ("▼" if i == len(keep_pos_sorted)-1 else "·")
                lines.append(f"  {rank} #{p.ticket} entry={p.price_open:.5f} "
                              f"P&L={p.profit:+.2f}")
            self.lbl_rf_pos_summary.setText("\n".join(lines))

        except Exception as e:
            self.lbl_rf_pos_summary.setText(f"Error: {e}")

    def _rf_use_suggestion(self, key: str):
        """Copy a suggested SL price into the exit price field."""
        val = self._rf_suggestions.get(key, {}).get("value")
        if val is not None:
            self.edit_rf_price.setText(f"{val:.5f}")

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

        keep_pos  = [p for p in bot_pos if (p.type == 0) == (keep_side == "BUY")]
        close_pos = [p for p in bot_pos if (p.type == 0) != (keep_side == "BUY")]

        if not keep_pos:
            self._on_log(f"{datetime.now().strftime('%H:%M:%S')}  ⚠️  No {keep_side} positions to protect", "WARN")
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
                res = _mt5.order_send({"action": _mt5.TRADE_ACTION_REMOVE, "order": o.ticket})
                if res and res.retcode == _mt5.TRADE_RETCODE_DONE:
                    cancelled += 1

        # Use user-specified exit price or fall back to average entry
        try:
            rf_price_text = self.edit_rf_price.text().strip()
            sl_price = float(rf_price_text) if rf_price_text else 0.0
        except ValueError:
            sl_price = 0.0
        if sl_price <= 0:
            sl_price = round(sum(p.price_open for p in keep_pos) / len(keep_pos), 5)
            self.edit_rf_price.setText(f"{sl_price:.5f}")
        write_commands([f"DRAW_HLINE|TB_RF_SL|{sl_price:.5f}|{0xFFD700}|2|0"], symbol=sym)
        avg_entry = sl_price

        # Store RF state for watcher to monitor
        self._rf_active    = True
        self._rf_keep_side = keep_side
        self._rf_sym       = sym
        self._rf_price     = sl_price   # stored price — not from EA objects
        self._rf_tickets   = [p.ticket for p in keep_pos]

        n_keep = len(keep_pos)
        ts = datetime.now().strftime("%H:%M:%S")
        self._on_log(
            f"{ts}  🛡️  Risk-Free ACTIVE — keeping {n_keep} {keep_side} positions | "
            f"closed {closed} {close_side} | cancelled {cancelled} pending | "
            f"Gold SL line drawn @ {avg_entry:.5f} — DRAG IT in MT5 to set exit price", "NEW")
        self.lbl_rf_status.setText(
            f"🛡️ Active: {n_keep} {keep_side} | exit @ {avg_entry:.5f}")
        self.lbl_rf_status.setStyleSheet(f"color:{C['gold']};font-size:10px;font-weight:bold;")
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
            self._on_log(f"{datetime.now().strftime('%H:%M:%S')}  ⚠️  Invalid price — enter a number like 1.16420", "WARN")
            return
        sym = self._rf_sym
        write_commands([f"DRAW_HLINE|TB_RF_SL|{new_price:.5f}|{0xFFD700}|2|0"], symbol=sym)
        self._rf_price = new_price  # update stored price
        self._on_log(
            f"{datetime.now().strftime('%H:%M:%S')}  📍  RF exit price updated → {new_price:.5f}", "NEW")
        self.lbl_rf_status.setText(
            f"🛡️ Active: {self._rf_keep_side} | exit @ {new_price:.5f}")

    def _check_rf_sl(self, candle: dict):
        """Called each scan cycle when RF mode is active. Closes all kept positions if SL line is touched."""
        if not getattr(self, "_rf_active", False):
            return
        import MetaTrader5 as _mt5
        sym    = self._rf_sym
        prev_h = candle.get("PREV_H", 0.0)
        prev_l = candle.get("PREV_L", 0.0)
        cur_h  = candle.get("CANDLE_H", 0.0)
        cur_l  = candle.get("CANDLE_L", 0.0)

        # Use the stored RF price — either from user input or updated via "Update SL" button
        # Don't rely on EA objects list (bot-drawn lines aren't in EA export)
        rf_price = getattr(self, "_rf_price", None)
        if rf_price is None:
            return

        self.lbl_rf_status.setText(
            f"🛡️ Active: {self._rf_keep_side} | exit @ {rf_price:.5f}")

        # Touch: either previous closed candle or current forming candle crossed RF line
        prev_touched = prev_h > 0 and prev_l <= rf_price <= prev_h
        cur_touched  = cur_h  > 0 and cur_l  <= rf_price <= cur_h

        if not (prev_touched or cur_touched):
            return

        # Close all kept positions at market
        positions = _mt5.positions_get(symbol=sym) or []
        closed = 0
        for p in positions:
            if p.magic != MAGIC_NUMBER:
                continue
            is_keep = (p.type == 0) == (self._rf_keep_side == "BUY")
            if not is_keep:
                continue
            close_type = _mt5.ORDER_TYPE_SELL if p.type == 0 else _mt5.ORDER_TYPE_BUY
            tick = _mt5.symbol_info_tick(sym)
            if not tick:
                continue
            price = tick.bid if close_type == _mt5.ORDER_TYPE_SELL else tick.ask
            for filling in (_mt5.ORDER_FILLING_FOK, _mt5.ORDER_FILLING_IOC,
                            _mt5.ORDER_FILLING_RETURN):
                req = {
                    "action":       _mt5.TRADE_ACTION_DEAL,
                    "symbol":       sym,
                    "volume":       p.volume,
                    "type":         close_type,
                    "position":     p.ticket,
                    "price":        price,
                    "deviation":    50,
                    "magic":        MAGIC_NUMBER,
                    "comment":      "TB_RF_EXIT",
                    "type_time":    _mt5.ORDER_TIME_GTC,
                    "type_filling": filling,
                }
                res = _mt5.order_send(req)
                if res and res.retcode == _mt5.TRADE_RETCODE_DONE:
                    closed += 1
                    break

        ts = datetime.now().strftime("%H:%M:%S")
        self._on_log(
            f"{ts}  🛡️  RF SL hit @ {rf_price:.5f} | "
            f"closed {closed}/{len([p for p in positions if p.magic == MAGIC_NUMBER])} "
            f"{self._rf_keep_side} positions", "NEW")
        self._rf_active = False
        self._rf_price  = None
        self.lbl_rf_status.setText("✅ RF triggered — positions closed")
        self.lbl_rf_status.setStyleSheet(f"color:{C['cyan']};font-size:10px;")
        self.btn_rf_update.setEnabled(False)
        self.btn_rf.setText("🛡️  Activate Risk-Free")
        self.btn_rf.setEnabled(True)
        write_commands(["DELETE|TB_RF_SL"], symbol=sym)

    def _refresh_peak_pnl(self):
        """Update the peak P&L dashboard every second and evaluate auto-close rules."""
        try:
            import MetaTrader5 as _mt5
            import time as _time
            sym     = self.sym_combo.currentText().strip() or WATCH_SYMBOL
            positions = _mt5.positions_get(symbol=sym) or []
            bot_pos   = [p for p in positions if p.magic == MAGIC_NUMBER]
            n_pos     = len(bot_pos)
            current_pnl = sum(p.profit for p in bot_pos)
            now         = _time.time()
            rounds      = getattr(self._worker, 'spawn_rounds', 0) if self._worker else 0

            # ── Update peak ──────────────────────────────────────
            if current_pnl > self._session_peak_pnl:
                self._session_peak_pnl = current_pnl
                self._alert_was_above  = False
                if self._autoclose_countdown > 0:
                    # New high while counting down — cancel countdown
                    self._autoclose_countdown = 0
                    self._autoclose_reason    = ""
                    self.lbl_autoclose_banner.hide()
                    self.btn_cancel_autoclose.hide()

            drawdown     = self._session_peak_pnl - current_pnl
            drawdown_pct = (drawdown / self._session_peak_pnl * 100
                            if self._session_peak_pnl > 0 else 0)

            # ── P&L history for velocity calc ────────────────────
            self._pnl_history.append((now, current_pnl))
            # Keep only last 90 seconds
            self._pnl_history = [(t, v) for t, v in self._pnl_history if now - t <= 90]

            # Velocity: gain over last 60 seconds
            velocity_60s = 0.0
            hist_60 = [(t, v) for t, v in self._pnl_history if now - t <= 60]
            if len(hist_60) >= 2:
                velocity_60s = hist_60[-1][1] - hist_60[0][1]

            # ── Track rounds 9/9 completion time ─────────────────
            if rounds >= 9 and self._rounds9_time is None:
                self._rounds9_time     = now
                self._rounds9_peak_at_9 = current_pnl
                self._on_log(
                    f"{datetime.now().strftime('%H:%M:%S')}  ⚠️  ALL 9 ROUNDS COMPLETE — "
                    f"cascade exhausted | watching for reversal", "WARN")

            # ── Update display cards ──────────────────────────────
            cur_color = C['green'] if current_pnl >= 0 else C['red']
            self._peak_cards["current"].setText(f"{current_pnl:+.2f}")
            self._peak_cards["current"].setStyleSheet(
                f"color:{cur_color};font-size:17px;font-weight:bold;font-family:Consolas;")

            self._peak_cards["peak"].setText(f"{self._session_peak_pnl:+.2f}")
            self._peak_cards["peak"].setStyleSheet(
                f"color:{C['green'] if self._session_peak_pnl > 0 else C['txt3']};"
                f"font-size:17px;font-weight:bold;font-family:Consolas;")

            if drawdown > 0.01:
                dd_color = C['red'] if drawdown_pct > 20 else C['orange']
                self._peak_cards["drawdown"].setText(f"-{drawdown:.2f} ({drawdown_pct:.0f}%)")
                self._peak_cards["drawdown"].setStyleSheet(
                    f"color:{dd_color};font-size:14px;font-weight:bold;font-family:Consolas;")
            else:
                self._peak_cards["drawdown"].setText("0.00")
                self._peak_cards["drawdown"].setStyleSheet(
                    f"color:{C['txt3']};font-size:17px;font-weight:bold;font-family:Consolas;")

            vel_color = C['green'] if velocity_60s > 0 else C['red'] if velocity_60s < -2 else C['txt3']
            self._peak_cards["velocity"].setText(f"{velocity_60s:+.2f}")
            self._peak_cards["velocity"].setStyleSheet(
                f"color:{vel_color};font-size:17px;font-weight:bold;font-family:Consolas;")

            self.lbl_peak_status.setText(
                f"{n_pos} open | Rounds: {rounds}/9 | "
                f"Peak: {self._session_peak_pnl:+.2f} | "
                f"{'⚠️ POST-9/9' if rounds >= 9 else 'running'}")

            # ── Alert-only check ──────────────────────────────────
            if self.chk_alert.isChecked() and n_pos > 0:
                if current_pnl >= self.spin_alert.value() and not self._alert_was_above:
                    self._alert_was_above = True
                    self._fire_pnl_alert(current_pnl)
                elif current_pnl < self.spin_alert.value() * 0.9:
                    self._alert_was_above = False

            # ── Countdown tick ────────────────────────────────────
            if self._autoclose_countdown > 0:
                self._autoclose_countdown -= 1
                self.lbl_autoclose_banner.setText(
                    f"⚡ AUTO-CLOSE in {self._autoclose_countdown}s\n"
                    f"Reason: {self._autoclose_reason}\n"
                    f"P&L now: ${current_pnl:+.2f} | Peak: ${self._session_peak_pnl:+.2f}")
                if self._autoclose_countdown <= 0:
                    self.lbl_autoclose_banner.hide()
                    self.btn_cancel_autoclose.hide()
                    self._execute_autoclose(f"Auto-close: {self._autoclose_reason}")
                return  # don't re-evaluate rules while counting down

            # ── Auto-close rule evaluation ────────────────────────
            # Gate: only evaluate if there are open positions and countdown not active
            if n_pos == 0 or self._autoclose_countdown > 0:
                self._update_close_button_style(drawdown_pct)
                return

            min_profit = self.spin_min_profit.value() if self.chk_min_profit.isChecked() else 0.0

            # Rule 1 — Velocity close (blowoff top)
            if (self.chk_velocity.isChecked() and
                    velocity_60s >= self.spin_velocity.value() and
                    current_pnl >= min_profit):
                self._arm_autoclose(
                    f"VELOCITY: +${velocity_60s:.2f} in 60s (blowoff top)",
                    countdown=30)
                return

            # Rule 2 — Drawdown close (reversal)
            if (self.chk_drawdown.isChecked() and
                    drawdown >= self.spin_drawdown.value() and
                    current_pnl >= min_profit):
                self._arm_autoclose(
                    f"DRAWDOWN: -${drawdown:.2f} from peak ${self._session_peak_pnl:.2f}",
                    countdown=15)
                return

            # Rule 3 — Rounds 9/9 timeout
            if (self.chk_rounds_close.isChecked() and
                    rounds >= 9 and self._rounds9_time is not None and
                    current_pnl >= min_profit):
                mins_since_9 = (now - self._rounds9_time) / 60.0
                wait_mins    = self.spin_rounds_wait.value()
                # Only close if peak hasn't improved since round 9 completed
                if (mins_since_9 >= wait_mins and
                        current_pnl <= self._rounds9_peak_at_9):
                    self._arm_autoclose(
                        f"ROUNDS 9/9 DONE: no new high in {mins_since_9:.0f}min",
                        countdown=20)
                    return

            self._update_close_button_style(drawdown_pct)

        except Exception:
            pass

    def _arm_autoclose(self, reason: str, countdown: int):
        """Start the auto-close countdown."""
        import winsound
        self._autoclose_countdown = countdown
        self._autoclose_reason    = reason
        ts = datetime.now().strftime('%H:%M:%S')
        self._on_log(
            f"{ts}  ⚡  AUTO-CLOSE ARMED — {reason} | "
            f"closing in {countdown}s (click ✋ to cancel)", "NEW")
        self.lbl_autoclose_banner.show()
        self.btn_cancel_autoclose.show()
        try: winsound.MessageBeep(winsound.MB_ICONHAND)
        except Exception: pass

    def _calc_min_profit(self):
        """
        Auto-calculate the minimum profit threshold for the current symbol + lot size.

        Logic:
        - Get symbol's tick value (profit per 1 pip move for 1 lot)
        - Multiply by lot size
        - Multiply by 50 pips (a full cascade L1+L2+L3 run covers ~45 pips total)
        - That's what ONE good round is worth — use as the floor

        EURUSD 0.05 lot: $0.50/pip × 0.05 × 50 = $1.25... wait, that's per position.
        For the full cascade (9 rounds × 3 positions avg) = ~15 positions at 0.05 lot:
        15 × $0.50/pip × 0.05 lot × 10 pips avg gain = $37.50
        So minimum = lot × pip_value_per_lot × 150 pips equivalent
        """
        import MetaTrader5 as _mt5
        try:
            sym  = self.sym_combo.currentText().strip() or WATCH_SYMBOL
            lot  = self.spin_lot.value() if hasattr(self, 'spin_lot') else 0.05
            info = _mt5.symbol_info(sym)
            if not info:
                self._on_log(
                    f"{datetime.now().strftime('%H:%M:%S')}  ⚠️  Symbol info not available", "WARN")
                return

            # tick_value = profit in account currency per 1 tick (smallest move) for 1 lot
            tick_val  = info.trade_tick_value   # e.g. EURUSD = $1 per 0.00001 per lot
            tick_size = info.trade_tick_size    # e.g. 0.00001
            point     = info.point

            # pip_value_per_lot = profit per 1 pip per 1 lot
            # For EURUSD: $10/pip/lot. For XAUUSD: ~$10/pip/lot at standard
            pip_size = point * 10 if 'JPY' not in sym.upper() else point * 100
            pip_value_per_lot = (tick_val / tick_size) * pip_size

            # Per lot at user's lot size
            pip_value = pip_value_per_lot * lot

            # Min profit = value of a full successful cascade
            # Assume 6 positions avg profit of 30 pips each (conservative)
            min_profit = round(pip_value * 6 * 30, 1)

            # Clamp: never below $10, never above $500
            min_profit = max(10.0, min(500.0, min_profit))

            self.spin_min_profit.setValue(min_profit)
            self._on_log(
                f"{datetime.now().strftime('%H:%M:%S')}  ⟳  Min profit calculated: "
                f"${min_profit:.1f} | "
                f"({sym} | lot={lot} | pip_val=${pip_value:.3f}/pip)", "INFO")

        except Exception as e:
            self._on_log(
                f"{datetime.now().strftime('%H:%M:%S')}  ⚠️  Calc failed: {e}", "WARN")

    def _cancel_autoclose(self):
        """Cancel the auto-close countdown."""
        self._autoclose_countdown = 0
        self._autoclose_reason    = ""
        self.lbl_autoclose_banner.hide()
        self.btn_cancel_autoclose.hide()
        self._on_log(
            f"{datetime.now().strftime('%H:%M:%S')}  ✋  Auto-close CANCELLED by user", "WARN")

    def _execute_autoclose(self, reason: str):
        """Execute auto-close — same as Close All & Reset but automatic."""
        import MetaTrader5 as _mt5
        sym = self.sym_combo.currentText().strip() or WATCH_SYMBOL
        positions = _mt5.positions_get(symbol=sym) or []
        bot_pos   = [p for p in positions if p.magic == MAGIC_NUMBER]
        pending   = _mt5.orders_get(symbol=sym) or []
        bot_pend  = [o for o in pending if o.magic == MAGIC_NUMBER]
        total_pnl = sum(p.profit for p in bot_pos)

        closed = cancelled = 0
        for p in bot_pos:
            close_type = _mt5.ORDER_TYPE_SELL if p.type == 0 else _mt5.ORDER_TYPE_BUY
            tick = _mt5.symbol_info_tick(sym)
            price = tick.bid if close_type == _mt5.ORDER_TYPE_SELL else tick.ask
            for filling in (_mt5.ORDER_FILLING_FOK, _mt5.ORDER_FILLING_IOC,
                            _mt5.ORDER_FILLING_RETURN):
                req = {
                    "action": _mt5.TRADE_ACTION_DEAL, "symbol": sym,
                    "volume": p.volume, "type": close_type, "position": p.ticket,
                    "price": price, "deviation": 50, "magic": MAGIC_NUMBER,
                    "comment": "TB_AUTOCLOSE", "type_time": _mt5.ORDER_TIME_GTC,
                    "type_filling": filling,
                }
                res = _mt5.order_send(req)
                if res and res.retcode == _mt5.TRADE_RETCODE_DONE:
                    closed += 1; break

        for o in bot_pend:
            res = _mt5.order_send({"action": _mt5.TRADE_ACTION_REMOVE, "order": o.ticket})
            if res and res.retcode == _mt5.TRADE_RETCODE_DONE:
                cancelled += 1

        write_commands(["DELETE_PREFIX|TB_"], symbol=sym)

        # Reset watcher state
        if self._worker:
            self._worker.spawn_rounds    = 0
            self._worker.spawned_keys    = set()
            self._worker.pending_tracker = {}
            self._worker.drawn           = {}
            self._worker.prev_names      = set()
            self._worker.orders_placed   = set()
            self._worker.source_registry = {}
            self._worker._source_registry = {}

        last_peak = self._session_peak_pnl
        self._session_peak_pnl  = 0.0
        self._alert_was_above   = False
        self._pnl_history       = []
        self._rounds9_time      = None
        self._rounds9_peak_at_9 = 0.0
        for key in self._peak_cards:
            self._peak_cards[key].setText("—")
        self.lbl_peak_status.setText("Reset — draw new line to start")
        self.lbl_autoclose_banner.hide()
        self.btn_cancel_autoclose.hide()

        ts = datetime.now().strftime('%H:%M:%S')
        self._on_log(
            f"{ts}  ⚡  AUTO-CLOSE EXECUTED | {reason} | "
            f"closed {closed} positions | locked ~${total_pnl:+.2f} | "
            f"session peak was ${last_peak:+.2f}", "NEW")

    def _update_close_button_style(self, drawdown_pct: float):
        """Update the close button color based on drawdown severity."""
        if drawdown_pct > 30 and self._session_peak_pnl > 5:
            self.btn_close_reset.setStyleSheet(
                f"QPushButton {{ background:{C['red_dk']};color:{C['red']};"
                f"border:2px solid {C['red']};border-radius:5px;"
                f"font-weight:bold;font-size:13px; }}"
                f"QPushButton:hover {{ background:{C['red']};color:#fff; }}")
        else:
            self.btn_close_reset.setStyleSheet(
                f"QPushButton {{ background:#1A0A2A;color:{C['purple']};"
                f"border:2px solid {C['purple']};border-radius:5px;"
                f"font-weight:bold;font-size:13px; }}"
                f"QPushButton:hover {{ background:{C['purple']};color:#fff; }}")

    def _fire_pnl_alert(self, pnl: float):
        """Flash GUI and play sound when P&L target is reached."""
        import winsound
        ts = datetime.now().strftime('%H:%M:%S')
        self._on_log(
            f"{ts}  🔔  P&L ALERT — ${pnl:+.2f} crossed target "
            f"${self.spin_alert.value():.1f} — consider closing!", "NEW")
        # Flash the peak panel gold
        try:
            self.btn_close_reset.setStyleSheet(
                f"QPushButton {{ background:{C['gold']};color:#000;"
                f"border:2px solid {C['gold']};border-radius:5px;"
                f"font-weight:bold;font-size:13px; }}"
                f"QPushButton:hover {{ background:{C['gold']};color:#000; }}")
            # Simple beep — works on Windows
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except Exception:
            pass  # Non-Windows fallback — just the log message

    def _close_all_and_reset(self):
        """
        One-click: close ALL open positions + cancel ALL pending orders
        + reset watcher state (rounds, source registry, peak tracker).
        """
        from PyQt5.QtWidgets import QMessageBox
        import MetaTrader5 as _mt5

        sym = self.sym_combo.currentText().strip() or WATCH_SYMBOL

        # Get current totals for confirmation dialog
        positions = _mt5.positions_get(symbol=sym) or []
        bot_pos   = [p for p in positions if p.magic == MAGIC_NUMBER]
        pending   = _mt5.orders_get(symbol=sym) or []
        bot_pend  = [o for o in pending if o.magic == MAGIC_NUMBER]
        total_pnl = sum(p.profit for p in bot_pos)

        # Confirm
        msg = (f"Close ALL {len(bot_pos)} open positions "
               f"(P&L: {total_pnl:+.2f}) and cancel {len(bot_pend)} pending orders?\n\n"
               f"Peak this session: ${self._session_peak_pnl:+.2f}\n"
               f"You will receive: ~${total_pnl:+.2f}\n\n"
               f"Bot state will be fully reset — you can draw a new line immediately.")
        reply = QMessageBox.question(
            self, "🏁 Close All & Reset", msg,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return

        ts = datetime.now().strftime('%H:%M:%S')
        closed = cancelled = 0

        # Close all open positions at market — try each filling mode
        for p in bot_pos:
            close_type = _mt5.ORDER_TYPE_SELL if p.type == 0 else _mt5.ORDER_TYPE_BUY
            tick = _mt5.symbol_info_tick(sym)
            price = tick.bid if close_type == _mt5.ORDER_TYPE_SELL else tick.ask
            for filling in (_mt5.ORDER_FILLING_FOK, _mt5.ORDER_FILLING_IOC,
                            _mt5.ORDER_FILLING_RETURN):
                req = {
                    "action":       _mt5.TRADE_ACTION_DEAL,
                    "symbol":       sym,
                    "volume":       p.volume,
                    "type":         close_type,
                    "position":     p.ticket,
                    "price":        price,
                    "deviation":    50,
                    "magic":        MAGIC_NUMBER,
                    "comment":      "TB_CLOSE_RESET",
                    "type_time":    _mt5.ORDER_TIME_GTC,
                    "type_filling": filling,
                }
                res = _mt5.order_send(req)
                if res and res.retcode == _mt5.TRADE_RETCODE_DONE:
                    closed += 1
                    break

        # Cancel all pending
        for o in bot_pend:
            res = _mt5.order_send({
                "action": _mt5.TRADE_ACTION_REMOVE,
                "order":  o.ticket,
            })
            if res and res.retcode == _mt5.TRADE_RETCODE_DONE:
                cancelled += 1

        # Clear bot lines from MT5 chart
        write_commands(["DELETE_PREFIX|TB_"], symbol=sym)

        # Reset watcher state
        if self._worker:
            self._worker.spawn_rounds    = 0
            self._worker.spawned_keys    = set()
            self._worker.pending_tracker = {}
            self._worker.drawn           = {}
            self._worker.prev_names      = set()
            self._worker.orders_placed   = set()
            self._worker.source_registry = {}
            self._worker._source_registry = {}
            self._worker._last_direction = "—"

        # Reset peak tracker (keep session_peak for reference, reset for next trade)
        last_peak = self._session_peak_pnl
        self._session_peak_pnl     = 0.0
        self._session_peak_alerted = False

        # Reset peak cards
        for key in self._peak_cards:
            self._peak_cards[key].setText("—")
        self.lbl_peak_status.setText("Reset complete — draw a new line to start")

        self._on_log(
            f"{ts}  🏁  CLOSED {closed} positions | Cancelled {cancelled} pending | "
            f"Locked: ~${total_pnl:+.2f} | Session peak was: ${last_peak:+.2f}", "NEW")
        self._on_log(
            f"{ts}  ✅  Bot state reset — draw a new line on the chart to begin next trade", "INFO")

    def _manual_trigger(self):
        """Force-place orders on all watched source lines immediately."""
        if not self._worker:
            return
        w = self._worker
        sym = w.symbol
        pip = get_pip_size(sym)
        triggered = 0
        for n, reg in list(w.source_registry.items()):
            if reg.get("triggered"):
                self._on_log(
                    f"{datetime.now().strftime('%H:%M:%S')}  🖐  Manual trigger: "
                    f"[{n[:20]}] already triggered — placing fresh G0 round", "NEW")
            else:
                reg["triggered"] = True
                self._on_log(
                    f"{datetime.now().strftime('%H:%M:%S')}  🖐  Manual trigger: "
                    f"[{n[:20]}] @ {reg['src']:.5f} → placing orders now", "NEW")
            w._place_orders_for_source(reg["src"], pip, generation=0)
            triggered += 1
        if triggered == 0:
            self._on_log(
                f"{datetime.now().strftime('%H:%M:%S')}  ⚠️  Manual trigger: "
                f"no source lines found — draw a line on the chart first", "WARN")

    def _cancel_orders(self):
        if getattr(self, "_cancelling", False):
            return
        self._cancelling = True
        try:
            sym = self.sym_combo.currentText().strip() or WATCH_SYMBOL
            n = cancel_all_tb_orders(sym)
            write_commands(["DELETE_PREFIX|TB_"], symbol=sym)
            self._on_log(f"{datetime.now().strftime('%H:%M:%S')}  🗑️  Cancelled {n} bot orders + cleared all level lines", "WARN")
            if hasattr(self, 'ord_pending'): self.ord_pending.setRowCount(0)
            if hasattr(self, 'ord_active'):  self.ord_active.setRowCount(0)
        finally:
            self._cancelling = False

    def _tab_report(self):
        w = QWidget(); vl = QVBoxLayout(w); vl.setContentsMargins(6,6,6,6); vl.setSpacing(6)

        # ── Summary cards ──────────────────────────────────────────
        grp_sum = QGroupBox("Session Summary"); hs = QHBoxLayout(grp_sum)
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
            card.setStyleSheet(f"background:{C['card']};border:1px solid {C['border']};border-radius:6px;")
            cv = QVBoxLayout(card); cv.setContentsMargins(8,4,8,4); cv.setSpacing(1)
            lt = QLabel(label); lt.setStyleSheet(f"color:{C['txt3']};font-size:8px;font-weight:bold;")
            lt.setAlignment(Qt.AlignCenter)
            lv = QLabel("—"); lv.setStyleSheet(f"color:{color};font-size:13px;font-weight:bold;font-family:Consolas;")
            lv.setAlignment(Qt.AlignCenter)
            cv.addWidget(lt); cv.addWidget(lv)
            self._rpt_cards[key] = lv
            hs.addWidget(card)
        vl.addWidget(grp_sum)

        # ── Event table ────────────────────────────────────────────
        grp_tbl = QGroupBox("Position Events")
        tl = QVBoxLayout(grp_tbl)
        self.rpt_table = QTableWidget(0, 11)
        self.rpt_table.setHorizontalHeaderLabels([
            "Time", "Symbol", "G/L", "Type", "Entry", "Close",
            "SL", "TP", "P&L $", "P&L Pips", "Reason"
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
        """Fetch session data via session_report module and update the Report tab."""
        sym = self.sym_combo.currentText().strip() or WATCH_SYMBOL
        try:
            self.lbl_rpt_status.setText("Refreshing…")
            data = sr.fetch_session_events(sym, self._session_start)
            events   = data["events"]
            wins     = data["wins"]
            losses   = data["losses"]
            rf_exits = data["rf_exits"]
            total_pnl= data["total_pnl"]
            open_cnt = data["open_count"]

            # ── Fill table ────────────────────────────────────────
            cols = ["time","symbol","gen_lvl","type","entry","close",
                    "sl","tp","pnl","pips","reason"]
            self.rpt_table.setRowCount(len(events))
            for row, ev in enumerate(events):
                for col, key in enumerate(cols):
                    it = QTableWidgetItem(ev.get(key, ""))
                    pv = ev["_pnl_v"]
                    if key == "pnl":
                        clr = C["green"] if pv > 0 else C["red"] if pv < 0 else C["txt2"]
                        it.setForeground(QColor(clr))
                    elif key == "type":
                        it.setForeground(QColor(C["green"] if ev["type"] == "BUY" else C["red"]))
                    elif key == "gen_lvl":
                        it.setForeground(QColor(C["gold"]))
                    elif key == "reason":
                        clr = (C["gold"]   if "Risk"   in ev["reason"]
                               else C["purple"] if "Reset"  in ev["reason"]
                               else C["red"]    if "SL"     in ev["reason"]
                               else C["green"]  if "TP"     in ev["reason"]
                               else C["cyan"]   if "Open"   in ev["reason"]
                               else C["txt2"])
                        it.setForeground(QColor(clr))
                    self.rpt_table.setItem(row, col, it)

            # ── Summary cards ─────────────────────────────────────
            dur = datetime.now() - self._session_start
            h, rem = divmod(int(dur.total_seconds()), 3600); m = rem // 60
            self._rpt_cards["duration"].setText(f"{h}h {m}m")
            self._rpt_cards["total_pos"].setText(str(len(events)))
            self._rpt_cards["wins"].setText(str(wins))
            self._rpt_cards["losses"].setText(str(losses))
            self._rpt_cards["rf_exits"].setText(str(rf_exits))
            self._rpt_cards["pnl"].setText(f"{total_pnl:+.2f}")
            self._rpt_cards["pnl"].setStyleSheet(
                f"color:{C['green'] if total_pnl >= 0 else C['red']};"
                f"font-size:13px;font-weight:bold;font-family:Consolas;")
            self._rpt_cards["best"].setText(f"{data['best_pnl']:+.2f}")
            self._rpt_cards["worst"].setText(f"{data['worst_pnl']:+.2f}")

            self._session_events = events
            n_closed = sum(1 for e in events if e["_closed"])
            self.lbl_rpt_status.setText(
                f"Refreshed {datetime.now().strftime('%H:%M:%S')} | "
                f"{n_closed} closed · {open_cnt} open · "
                f"W:{wins} L:{losses}")

        except Exception as ex:
            import traceback; traceback.print_exc()
            self.lbl_rpt_status.setText(f"Error: {ex}")

    def _export_report_csv(self):
        from PyQt5.QtWidgets import QFileDialog
        fname, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "CSV Files (*.csv)")
        if not fname: return
        try:
            sr.export_csv(self._session_events, fname)
            self.lbl_rpt_status.setText(f"✅  CSV saved: {fname}")
        except Exception as ex:
            self.lbl_rpt_status.setText(f"❌  {ex}")

    def _export_report_txt(self):
        from PyQt5.QtWidgets import QFileDialog
        fname, _ = QFileDialog.getSaveFileName(
            self, "Export Report", f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "Text Files (*.txt)")
        if not fname: return
        try:
            sym = self.sym_combo.currentText().strip() or WATCH_SYMBOL
            sr.export_txt(self._session_events, self._session_start, sym, fname)
            self.lbl_rpt_status.setText(f"✅  Report saved: {fname}")
        except Exception as ex:
            self.lbl_rpt_status.setText(f"❌  {ex}")

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
        rects  = [o for o in trader if o.is_rectangle and o.rect_valid]
        rounds = getattr(self._worker, 'spawn_rounds', 0) if self._worker else 0
        pending_count = len(getattr(self._worker, 'pending_tracker', {})) if self._worker else 0

        if hlines or rects:
            obj = hlines[0] if hlines else rects[0]
            src = obj.price1 if obj.is_hline else round((obj.rect_top+obj.rect_bottom)/2,5)
            self.lbl_source_price.setText(f"{src:.5f}")
            direction = getattr(self._worker, '_last_direction', '—') if self._worker else '—'
            if direction == 'BUY':
                self.lbl_direction.setText("🟢 BUY bias")
                self.lbl_direction.setStyleSheet(f"color:{C['green']};font-family:Consolas;font-size:11px;font-weight:bold;")
            elif direction == 'SELL':
                self.lbl_direction.setText("🔴 SELL bias")
                self.lbl_direction.setStyleSheet(f"color:{C['red']};font-family:Consolas;font-size:11px;font-weight:bold;")
            else:
                self.lbl_direction.setText("— waiting")
                self.lbl_direction.setStyleSheet(f"color:{C['txt3']};font-family:Consolas;font-size:11px;")
            triggered = any(
                v.get("triggered", False)
                for v in (getattr(self._worker, 'source_registry', {}) or {}).values()
            ) if self._worker and hasattr(self._worker, 'source_registry') else False
            if triggered:
                self.lbl_waiting.setText(f"✅ Active — {pending_count} pending")
                self.lbl_waiting.setStyleSheet(f"color:{C['green']};font-family:Consolas;font-size:11px;font-weight:bold;")
            else:
                self.lbl_waiting.setText("⏳ Waiting for touch")
                self.lbl_waiting.setStyleSheet(f"color:{C['orange']};font-family:Consolas;font-size:11px;")
        else:
            self.lbl_source_price.setText("—")
            self.lbl_direction.setText("—")
            self.lbl_direction.setStyleSheet(f"color:{C['txt3']};font-family:Consolas;font-size:11px;")
            self.lbl_waiting.setText("Draw a line on chart")
            self.lbl_waiting.setStyleSheet(f"color:{C['txt3']};font-family:Consolas;font-size:11px;")

        self.lbl_rounds_info.setText(f"Rounds: {rounds}/9")
        color = C['red'] if rounds >= 7 else C['gold'] if rounds >= 4 else C['cyan']
        self.lbl_rounds_info.setStyleSheet(f"color:{color};font-family:Consolas;font-size:11px;")
        self.lbl_phase.setText(f"G{rounds} | Pending: {pending_count}")

    def _on_status(self, msg):
        self.lbl_status.setText(msg)
        color = C['green'] if "Running" in msg else C['red'] if "failed" in msg else C['txt2']
        self.lbl_status.setStyleSheet(f"color:{color};font-size:11px;")

    def _on_log(self, msg, level="INFO"):
        if msg == "__BT_RESULT__": return
        if msg == "__REFRESH_ORDERS__":
            self._refresh_orders_tab()
            return
        if msg.startswith("__CANDLE__"):
            try: self._last_candle = eval(msg[9:])
            except: pass
            return
        if msg == "__CHECK_RF__":
            self._check_rf_sl(getattr(self, "_last_candle", {}))
            return
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
        self.ord_pending.setRowCount(len(orders))
        for r, o in enumerate(orders):
            clr = QColor(C['green'] if o["type"] == "BUY_STOP" else C['red'])
            for c, v in enumerate([f"L{o['level']}", o["type"],
                                    f"{o['entry']:.5f}", f"{o['sl']:.5f}", f"{o['tp']:.5f}"]):
                it = QTableWidgetItem(v); it.setForeground(clr)
                self.ord_pending.setItem(r, c, it)

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