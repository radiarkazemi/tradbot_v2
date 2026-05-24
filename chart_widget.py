"""
chart_widget.py — TraderBot v1
Candlestick chart with zoom, pan, level lines, order markers,
and Phase 3 multi-generation source lines.
"""
from PyQt5.QtWidgets import QWidget, QSizePolicy
from PyQt5.QtCore    import Qt, QPoint
from PyQt5.QtGui     import (QPainter, QPen, QBrush, QColor,
                              QFont, QPainterPath, QWheelEvent)

# ── Palette ───────────────────────────────────────────────────────
BG        = QColor("#0D1117")
GRID      = QColor("#1A2235")
AXIS_TXT  = QColor("#4A5568")
BULL_BODY = QColor("#00D97E")
BEAR_BODY = QColor("#FF4560")
BULL_WICK = QColor("#00A060")
BEAR_WICK = QColor("#CC3040")

# Source line colours per generation
GEN_LINE_C = [
    QColor("#F5A623"),   # gen 0 — gold (original)
    QColor("#00BCD4"),   # gen 1 — cyan
    QColor("#B388FF"),   # gen 2 — purple
    QColor("#FF8C00"),   # gen 3 — orange
    QColor("#00FF88"),   # gen 4 — lime
]

ABOVE_C = [QColor("#FF8C00"), QColor("#CC6000"), QColor("#994800")]
BELOW_C = [QColor("#00D97E"), QColor("#009960"), QColor("#006640")]

STATE_C = {
    "PENDING":   QColor("#2A3550"),
    "TRIGGERED": QColor("#00BCD4"),
    "TP":        QColor("#00D97E"),
    "SL":        QColor("#FF4560"),
    "OPEN":      QColor("#2979FF"),
}

# Per-generation above/below colours (lighter for later gens)
GEN_ABOVE = [
    [QColor("#FF8C00"), QColor("#CC6000"), QColor("#994800")],
    [QColor("#00BCD4"), QColor("#0090A0"), QColor("#006070")],
    [QColor("#B388FF"), QColor("#8060CC"), QColor("#604099")],
]
GEN_BELOW = [
    [QColor("#00D97E"), QColor("#009960"), QColor("#006640")],
    [QColor("#FFD700"), QColor("#CCA800"), QColor("#997A00")],
    [QColor("#FF6090"), QColor("#CC4060"), QColor("#992030")],
]


def _gen_above(gen, i):
    if gen < len(GEN_ABOVE): return GEN_ABOVE[gen][i]
    return QColor("#888888")

def _gen_below(gen, i):
    if gen < len(GEN_BELOW): return GEN_BELOW[gen][i]
    return QColor("#666666")

def _gen_src(gen):
    return GEN_LINE_C[min(gen, len(GEN_LINE_C)-1)]


class CandleChartWidget(QWidget):
    """
    Candlestick chart with:
      - Zoom (mouse wheel)
      - Pan (click + drag)
      - Multi-generation source lines (Phase 3)
      - Order entry triangles, TP/SL crosses
      - Crosshair + price label
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumHeight(300)
        self.setMouseTracking(True)

        self._snapshots   = []
        self._bt_result   = None
        self._current_bar = 0

        # Zoom / pan state
        self._visible_bars = 80    # how many bars visible
        self._pan_offset   = 0     # bars offset from right edge (panning)
        self._dragging     = False
        self._drag_start_x = 0
        self._drag_start_offset = 0

        # Crosshair
        self._mx = -1
        self._my = -1

        # Layout
        self._pad = (18, 32, 4, 78)   # top, bottom, left, right

    # ── Public API ────────────────────────────────────────────────

    def set_data(self, snapshots, bt_result):
        self._snapshots  = snapshots
        self._bt_result  = bt_result
        self._pan_offset = 0
        self.update()

    # Keep set_snapshots as alias
    def set_snapshots(self, snapshots, bt_result=None):
        self._snapshots  = snapshots
        self._bt_result  = bt_result
        self._pan_offset = 0
        self.update()

    def set_bar(self, bar_idx: int):
        self._current_bar = bar_idx
        # Auto-scroll: keep current bar visible
        end_visible = len(self._snapshots) - self._pan_offset
        start_visible = max(0, end_visible - self._visible_bars)
        if bar_idx < start_visible or bar_idx >= end_visible:
            self._pan_offset = max(0, len(self._snapshots) - bar_idx - 1)
        self.update()

    # ── Mouse ─────────────────────────────────────────────────────

    def wheelEvent(self, e: QWheelEvent):
        delta = e.angleDelta().y()
        factor = 0.85 if delta > 0 else 1.18
        self._visible_bars = max(10, min(500, int(self._visible_bars * factor)))
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_start_x = e.x()
            self._drag_start_offset = self._pan_offset

    def mouseReleaseEvent(self, e):
        self._dragging = False

    def mouseMoveEvent(self, e):
        self._mx = e.x(); self._my = e.y()
        if self._dragging and self._snapshots:
            W = self.width()
            pt, pb, pl, pr = self._pad
            cw = W - pl - pr
            bar_w = cw / max(self._visible_bars, 1)
            dx_bars = int((self._drag_start_x - e.x()) / bar_w)
            self._pan_offset = max(0, min(
                len(self._snapshots) - 1,
                self._drag_start_offset + dx_bars
            ))
        self.update()

    def leaveEvent(self, e):
        self._mx = -1; self._my = -1; self.update()

    # ── Paint ──────────────────────────────────────────────────────

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), BG)

        if not self._snapshots:
            p.setPen(QColor("#4A5568"))
            p.setFont(QFont("Segoe UI", 11))
            p.drawText(self.rect(), Qt.AlignCenter,
                       "Run backtest to see chart\n(wheel to zoom, drag to pan)")
            return

        W, H = self.width(), self.height()
        pt, pb, pl, pr = self._pad
        cw = W - pl - pr
        ch = H - pt - pb

        # Visible window
        total = len(self._snapshots)
        end_bar   = min(self._current_bar + 1, total - self._pan_offset)
        start_bar = max(0, end_bar - self._visible_bars)
        visible   = self._snapshots[start_bar:end_bar]
        n = len(visible)
        if n == 0:
            return

        # Price range from visible candles + source lines from bt_result
        prices = []
        for s in visible:
            prices += [s.high, s.low]
        if self._bt_result:
            for src in self._bt_result.sources:
                prices.append(src.price)
                prices += src.above + src.below
        if not prices:
            return
        lo = min(prices) * 0.9997
        hi = max(prices) * 1.0003
        rng = (hi - lo) or 1.0

        bar_slot = cw / max(n, 1)
        body_w   = max(1, int(bar_slot * 0.65))

        def py(price):
            return pt + int(ch * (1.0 - (price - lo) / rng))

        def bx(i):
            return int(pl + i * bar_slot + bar_slot / 2)

        # ── Grid ─────────────────────────────────────────────────
        p.setFont(QFont("Consolas", 7))
        steps = 8
        for i in range(steps + 1):
            yy = pt + int(ch * i / steps)
            p.setPen(QPen(GRID, 1))
            p.drawLine(pl, yy, pl + cw, yy)
            price_at = hi - rng * i / steps
            p.setPen(QPen(AXIS_TXT, 1))
            p.drawText(pl + cw + 3, yy + 4, f"{price_at:.2f}")

        # ── Source lines + level lines ────────────────────────────
        if visible and self._bt_result:
            cur_sources = self._bt_result.sources_at_bar(visible[-1])
            for src in cur_sources:
                gen = src.generation
                src_clr = _gen_src(gen)

                # Source line (solid, thicker for gen 0)
                width = 2 if gen == 0 else 1
                self._hline(p, py(src.price), pl, cw,
                            src_clr, Qt.SolidLine, width,
                            f"G{gen} {src.price:.2f}", pl + cw + 3)

                # Level lines
                for i in range(3):
                    self._hline(p, py(src.above[i]), pl, cw,
                                _gen_above(gen, i), Qt.DashLine, 1,
                                f"A{i+1}" if gen == 0 else "")
                    self._hline(p, py(src.below[i]), pl, cw,
                                _gen_below(gen, i), Qt.DashLine, 1,
                                f"B{i+1}" if gen == 0 else "")

        # ── Candles ───────────────────────────────────────────────
        for i, snap in enumerate(visible):
            x      = bx(i)
            bull   = snap.close >= snap.open
            body_c = BULL_BODY if bull else BEAR_BODY
            wick_c = BULL_WICK if bull else BEAR_WICK
            top_y  = py(max(snap.open, snap.close))
            bot_y  = py(min(snap.open, snap.close))
            hi_y   = py(snap.high)
            lo_y   = py(snap.low)
            bh     = max(1, bot_y - top_y)
            hw     = body_w // 2

            # Wick
            p.setPen(QPen(wick_c, 1))
            p.drawLine(x, hi_y, x, lo_y)

            # Body
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(body_c))
            p.drawRect(x - hw, top_y, body_w, bh)

        # ── Order markers ─────────────────────────────────────────
        if self._bt_result:
            abs_start = start_bar
            for i, snap in enumerate(visible):
                abs_idx = abs_start + i
                x = bx(i)
                orders_at = self._bt_result.orders_at_bar(snap)
                for o in orders_at:
                    if o["trigger_bar"] == abs_idx:
                        up = o["direction"] == "BUY_STOP"
                        gen_clr = _gen_src(o["generation"])
                        self._triangle(p, x, py(o["entry"]), up, gen_clr, 7)
                    if o["close_bar"] == abs_idx and o["state"] in ("TP", "SL"):
                        self._cross(p, x, py(o["close_price"]), STATE_C[o["state"]])

        # ── Active SL/TP dashes at current bar ───────────────────
        if 0 <= self._current_bar < total and self._bt_result:
            cur = self._snapshots[self._current_bar]
            orders_cur = self._bt_result.orders_at_bar(cur)
            for o in orders_cur:
                if o["state"] == "PENDING":
                    self._hline(p, py(o["entry"]), pl, cw,
                                STATE_C["PENDING"], Qt.DotLine, 1)
                elif o["state"] in ("TRIGGERED", "OPEN"):
                    self._hline(p, py(o["sl"]), pl, cw,
                                STATE_C["SL"], Qt.DashDotLine, 1)
                    self._hline(p, py(o["tp"]), pl, cw,
                                STATE_C["TP"], Qt.DashDotLine, 1)

        # ── Crosshair ─────────────────────────────────────────────
        if pl < self._mx < pl + cw and pt < self._my < pt + ch:
            p.setPen(QPen(QColor("#2A3A55"), 1, Qt.DotLine))
            p.drawLine(self._mx, pt, self._mx, pt + ch)
            p.drawLine(pl, self._my, pl + cw, self._my)
            price_at_mouse = lo + (1.0 - (self._my - pt) / ch) * rng
            lbl = f"{price_at_mouse:.2f}"
            fm = p.fontMetrics()
            tw = fm.width(lbl) + 6
            p.fillRect(pl + cw + 1, self._my - 7, tw, 14, QColor("#1C2333"))
            p.setPen(QColor("#E8EDF5"))
            p.setFont(QFont("Consolas", 8))
            p.drawText(pl + cw + 4, self._my + 4, lbl)

        # ── Zoom/bar count label ──────────────────────────────────
        p.setPen(QColor("#2A3550"))
        p.setFont(QFont("Consolas", 8))
        p.drawText(pl + 4, pt + 12,
                   f"{n} bars  |  scroll to zoom  |  drag to pan")

    # ── Drawing helpers ───────────────────────────────────────────

    def _hline(self, p, y, x0, w, color, style=Qt.SolidLine,
               width=1, label="", label_x=0):
        if y < self._pad[0] or y > self.height() - self._pad[1]:
            return
        p.setPen(QPen(color, width, style))
        p.drawLine(x0, y, x0 + w, y)
        if label and label_x:
            p.setFont(QFont("Consolas", 7))
            p.setPen(QPen(color, 1))
            p.drawText(label_x, y + 4, label)

    def _triangle(self, p, cx, cy, up, color, size=7):
        p.setBrush(QBrush(color))
        p.setPen(QPen(color, 1))
        path = QPainterPath()
        if up:
            path.moveTo(cx, cy - size)
            path.lineTo(cx - size, cy + size // 2)
            path.lineTo(cx + size, cy + size // 2)
        else:
            path.moveTo(cx, cy + size)
            path.lineTo(cx - size, cy - size // 2)
            path.lineTo(cx + size, cy - size // 2)
        path.closeSubpath()
        p.drawPath(path)

    def _cross(self, p, cx, cy, color, s=5):
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(color, 2))
        p.drawLine(cx - s, cy - s, cx + s, cy + s)
        p.drawLine(cx + s, cy - s, cx - s, cy + s)