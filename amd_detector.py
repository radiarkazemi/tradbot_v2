"""
amd_detector.py — AMD Zone Detector
Accumulation · Manipulation · Distribution fractal time analysis.

Standard rules:
  Quarter : Q1=A  Q2=M  Q3=D  (Q4=continuation/new A)
  Month   : within quarter — M1=A  M2=M  M3=D
  Week    : within month  — W1+W2=A  W3=M  W4=D
  Day     : Asian 00-08=A  London 08-14=M  NY 14-22=D  (NO overlap)
  4H      : 4H1+4H2=A  4H3+4H4=M  4H5+4H6=D  (per calendar day)
  1H      : 1H1=A  1H2=M  1H3+1H4=D  (within each 4H block)
  5M      : 5M1-4=A  5M5-8=M  5M9-12=D  (within each 1H)

Usage:
  python amd_detector.py --symbol EURUSD --gmt 2
  python amd_detector.py --symbol EURUSD --gmt 2 --tf DAY
  python amd_detector.py --symbol EURUSD --clear
"""

from core.line_drawer import write_commands
import calendar
from datetime import datetime, timedelta, timezone
import numpy as np
import MetaTrader5 as mt5
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


AMD_PREFIX = "AMD_"

# ── Colors in MT5 BGR format ─────────────────────────────────────
CLR_A_BORDER = 0xFF6600   # Blue
CLR_A_FILL = 0x993300
CLR_M_BORDER = 0x0000DD   # Red
CLR_M_FILL = 0x000066
CLR_D_BORDER = 0x00CC00   # Green
CLR_D_FILL = 0x005500

ZONE_ICON = {"A": "🟦", "M": "🟥", "D": "🟩"}
_logs = []


# ─────────────────────────────────────────────────────────────────
#  UTILITIES
# ─────────────────────────────────────────────────────────────────

def _utc_now():
    return int(datetime.now(timezone.utc).timestamp())


def _utc_dt(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def _ts(year, month=1, day=1, hour=0, minute=0):
    return int(datetime(year, month, day, hour, minute,
                        tzinfo=timezone.utc).timestamp())


def _ft(ts):
    return _utc_dt(ts).strftime("%m-%d %H:%M")


def log(msg, level="INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    icons = {"INFO": "   ", "ZONE": "   ", "SKIP": "⏭  ",
             "WARN": "⚠️ ", "OK": "✅ ", "ERR": "❌ ", "HEAD": "───"}
    line = f"{ts} {icons.get(level, '   ')} {msg}"
    print(line)
    _logs.append(line)


def log_zone(name, t1, t2, zh, zl, ztype, ctype, closed, skip=False):
    icon = ZONE_ICON.get(ctype, "⬜")
    status = "closed" if closed else "ACTIVE"
    rc = f" → {ztype}→{ctype}✓" if (ctype != ztype and closed) else ""
    if skip:
        log(f"⏭  [{name:<24}] {ztype} | {_ft(t1)} → {_ft(t2)} | no data", "SKIP")
    else:
        log(f"{icon} [{name:<24}] {ctype} {status} | "
            f"{_ft(t1)} → {_ft(t2)} | "
            f"H={zh:.5f} L={zl:.5f} Δ={zh-zl:.5f}{rc}")


# ─────────────────────────────────────────────────────────────────
#  DATA
# ─────────────────────────────────────────────────────────────────

def _rates(symbol, tf, count):
    names = {mt5.TIMEFRAME_M5: "M5", mt5.TIMEFRAME_M15: "M15",
             mt5.TIMEFRAME_H1: "H1", mt5.TIMEFRAME_H4: "H4",
             mt5.TIMEFRAME_D1: "D1"}
    r = mt5.copy_rates_from_pos(symbol, tf, 0, count)
    if r is None or len(r) == 0:
        log(f"No {names.get(tf, tf)} data", "WARN")
        return None
    log(f"Loaded {len(r):4d} {names.get(tf, tf)} | "
        f"{_ft(int(r['time'][0]))} → {_ft(int(r['time'][-1]))}")
    return r


def _atr(rates, period=14):
    if rates is None or len(rates) < period + 1:
        return 0.0
    trs = [max(rates['high'][i]-rates['low'][i],
               abs(rates['high'][i]-rates['close'][i-1]),
               abs(rates['low'][i] - rates['close'][i-1]))
           for i in range(1, period+1)]
    return float(np.mean(trs))


def _hl(rates, t1, t2):
    """H/L of bars with open time in [t1, t2). Returns (None,None) if empty."""
    if rates is None:
        return None, None
    mask = (rates['time'] >= t1) & (rates['time'] < t2)
    b = rates[mask]
    if len(b) == 0:
        return None, None
    return float(np.max(b['high'])), float(np.min(b['low']))


def _last_end(rates, bar_sec):
    if rates is None or len(rates) == 0:
        return 0
    return int(rates['time'][-1]) + bar_sec


def _confirm(rates, t1, t2, expected, atr):
    if rates is None or atr <= 0:
        return expected
    mask = (rates['time'] >= t1) & (rates['time'] < t2)
    b = rates[mask]
    if len(b) < 2:
        return expected
    span = float(np.max(b['high'])) - float(np.min(b['low']))
    rng = b['high'] - b['low']
    body = np.abs(b['close'] - b['open'])
    ar = float(np.mean(rng))
    br = float(np.mean(body)) / ar if ar > 0 else 0
    move = abs(float(b['close'][-1]) - float(b['open'][0]))
    ret = move < atr * 0.3
    tight = span < atr * 0.5
    strong = move > atr * 1.5
    wicky = br < 0.40
    bs = br > 0.60
    if tight and ret:
        return "A"
    if wicky and ret and span > atr*0.6:
        return "M"
    if strong and not ret and bs:
        return "D"
    return expected


def _clr(z):
    return {"A": (CLR_A_BORDER, CLR_A_FILL),
            "M": (CLR_M_BORDER, CLR_M_FILL),
            "D": (CLR_D_BORDER, CLR_D_FILL)}[z]


# ─────────────────────────────────────────────────────────────────
#  COMMAND BUILDERS
# ─────────────────────────────────────────────────────────────────

def _rect(name, t1, zh, t2, zl, border, fill, width, style):
    return (f"DRAW_RECT|{AMD_PREFIX}{name}|"
            f"{t1}|{zh:.5f}|{t2}|{zl:.5f}|"
            f"{border}|{fill}|{width}|{style}|1")


def _text(name, t, p, txt, color):
    return f"DRAW_TEXT|{AMD_PREFIX}{name}|{t}|{p:.5f}|{txt}|{color}|8"


def _emit(cmds, name, t1, t2, rates, ztype, label, tf_lbl,
          closed, atr=0, fine_rates=None):
    """
    Draw one AMD zone from t1 to min(t2, last_bar_end).
    Uses fine_rates for H/L if provided, else rates.
    """
    hl_src = fine_rates if fine_rates is not None else rates
    le = _last_end(rates, 0)   # last bar open time (we clamp below)

    # Clamp t2 to last available bar end
    bar_sec = {mt5.TIMEFRAME_D1: 86400, mt5.TIMEFRAME_H4: 14400,
               mt5.TIMEFRAME_H1: 3600,  mt5.TIMEFRAME_M5: 300}.get(0, 3600)
    t2_draw = t2  # will be clamped by caller

    zh, zl = _hl(hl_src, t1, t2)
    ctype = _confirm(rates, t1, t2, ztype, atr) if closed else ztype

    if zh is None:
        log_zone(name, t1, t2, zh, zl, ztype, ctype, closed, skip=True)
        return

    log_zone(name, t1, t2_draw, zh, zl, ztype, ctype, closed)
    border, fill = _clr(ctype)
    width = 1 if closed else 2
    style = 0 if closed else 1

    if closed and ctype != ztype:
        marker = f"{ztype}→{ctype}✓"
    elif closed:
        marker = f"{ztype}·"
    else:
        marker = f"{ztype}…"

    cmds.append(_rect(f"{name}_r", t1, zh, t2_draw, zl,
                      border, fill, width, style))
    cmds.append(_text(f"{name}_t", t1, zh,
                      f"[{tf_lbl}] {marker} {label}", border))


def _emit2(cmds, name, t1, t2, t2_draw, rates_hl,
           rates_conf, ztype, label, tf_lbl, closed, atr=0):
    """Emit with explicit t2_draw and separate rates for HL vs confirmation."""
    zh, zl = _hl(rates_hl, t1, t2)
    ctype = _confirm(rates_conf, t1, t2, ztype, atr) if closed else ztype
    if zh is None:
        log_zone(name, t1, t2, zh, zl, ztype, ctype, closed, skip=True)
        return
    log_zone(name, t1, t2_draw, zh, zl, ztype, ctype, closed)
    border, fill = _clr(ctype)
    if closed and ctype != ztype:
        marker = f"{ztype}→{ctype}✓"
    elif closed:
        marker = f"{ztype}·"
    else:
        marker = f"{ztype}…"
    cmds.append(_rect(f"{name}_r", t1, zh, t2_draw, zl,
                      border, fill, 1 if closed else 2, 0 if closed else 1))
    cmds.append(_text(f"{name}_t", t1, zh,
                      f"[{tf_lbl}] {marker} {label}", border))


# ─────────────────────────────────────────────────────────────────
#  ZONE GENERATORS — strictly 3 zones per period, no overlap
# ─────────────────────────────────────────────────────────────────

def gen_quarterly(symbol, now_utc, cmds):
    """3 zones: Q1=A  Q2=M  Q3=D"""
    log("Quarterly  (Q1=A  Q2=M  Q3=D)", "HEAD")
    rates = _rates(symbol, mt5.TIMEFRAME_D1, 500)
    if rates is None:
        return
    atr = _atr(rates, 20)
    le = _last_end(rates, 86400)
    year = _utc_dt(now_utc).year

    for s, e, lbl, ztype in [
        (_ts(year, 1, 1), _ts(year, 4, 1),   "Q1", "A"),
        (_ts(year, 4, 1), _ts(year, 7, 1),   "Q2", "M"),
        (_ts(year, 7, 1), _ts(year, 10, 1),  "Q3", "D"),
        (_ts(year, 10, 1), _ts(year+1, 1, 1), "Q4", "A"),
    ]:
        if s >= le:
            continue
        t2d = min(e, le)
        closed = now_utc >= e
        _emit2(cmds, f"Q_{lbl}", s, e, t2d, rates, rates,
               ztype, lbl, "QTR", closed, atr)


def gen_monthly(symbol, now_utc, cmds, months_back=4):
    """3 zones per quarter: M1=A  M2=M  M3=D"""
    log("Monthly    (M1=A  M2=M  M3=D within quarter)", "HEAD")
    rates = _rates(symbol, mt5.TIMEFRAME_D1, 500)
    if rates is None:
        return
    atr = _atr(rates, 14)
    le = _last_end(rates, 86400)

    dt = _utc_dt(now_utc)
    for i in range(months_back):
        month = dt.month - i
        year = dt.year
        while month <= 0:
            month += 12
            year -= 1
        nm, ny = (month+1, year) if month < 12 else (1, year+1)
        t1 = _ts(year, month, 1)
        t2 = _ts(ny, nm, 1)
        if t1 >= le:
            continue
        t2d = min(t2, le)
        qpos = (month-1) % 3           # 0=A 1=M 2=D
        ztype = ["A", "M", "D"][qpos]
        lbl = datetime(year, month, 1).strftime("%b %Y")
        closed = now_utc >= t2
        _emit2(cmds, f"MO_{year}_{month:02d}", t1, t2, t2d,
               rates, rates, ztype, lbl, "MON", closed, atr)


def gen_weekly(symbol, now_utc, cmds, weeks_back=8):
    """
    Within each month: W1+W2=A  W3=M  W4=D
    Each zone covers exactly the weeks assigned to it.
    """
    log("Weekly     (W1+W2=A  W3=M  W4=D)", "HEAD")
    rates = _rates(symbol, mt5.TIMEFRAME_D1, 500)
    if rates is None:
        return
    atr = _atr(rates, 14)
    le = _last_end(rates, 86400)

    dt = _utc_dt(now_utc)
    # Process current and previous months
    for mi in range(3):
        month = dt.month - mi
        year = dt.year
        while month <= 0:
            month += 12
            year -= 1

        # Get all Mondays in this month
        _, ndays = calendar.monthrange(year, month)
        days = [datetime(year, month, d, tzinfo=timezone.utc)
                for d in range(1, ndays+1)
                if datetime(year, month, d, tzinfo=timezone.utc).weekday() == 0]
        if not days:
            continue

        # Week boundaries: each week starts Monday, ends next Monday
        week_starts = [int(d.timestamp()) for d in days]
        nm, ny = (month+1, year) if month < 12 else (1, year+1)
        month_end = _ts(ny, nm, 1)

        # Assign weeks to AMD: weeks 0,1 → A | week 2 → M | week 3+ → D
        def week_end(i):
            return week_starts[i+1] if i+1 < len(week_starts) else month_end

        zones = []
        # A = week 0 start → week 2 start
        if len(week_starts) >= 1:
            a_s = week_starts[0]
            a_e = week_starts[2] if len(week_starts) > 2 else month_end
            zones.append((a_s, a_e, "A", f"W1+2"))
        # M = week 2 start → week 3 start
        if len(week_starts) >= 3:
            m_s = week_starts[2]
            m_e = week_starts[3] if len(week_starts) > 3 else month_end
            zones.append((m_s, m_e, "M", f"W3"))
        # D = week 3 start → month end
        if len(week_starts) >= 4:
            d_s = week_starts[3]
            zones.append((d_s, month_end, "D", f"W4"))

        for t1, t2, ztype, lbl in zones:
            if t1 >= le:
                continue
            t2d = min(t2, le)
            closed = now_utc >= t2
            mn = datetime(year, month, 1).strftime("%b")
            _emit2(cmds, f"WK_{year}_{month:02d}_{ztype}", t1, t2, t2d,
                   rates, rates, ztype, f"{mn} {lbl}", "WK", closed, atr)


def gen_daily_sessions(symbol, now_utc, cmds, gmt_offset=0, days_back=7):
    """
    Exactly 3 non-overlapping sessions per day:
      Asian  : 00:00 - 08:00 broker time = A
      London : 08:00 - 14:00 broker time = M  (no NY overlap)
      NY     : 14:00 - 22:00 broker time = D
    """
    log("Sessions   (Asian 00-08=A  London 08-14=M  NY 14-22=D)", "HEAD")
    rates = _rates(symbol, mt5.TIMEFRAME_H1, days_back*24+48)
    if rates is None:
        return
    atr = _atr(rates, 14)
    le = _last_end(rates, 3600)

    # Sessions in broker hours (0-24), convert to UTC by subtracting gmt_offset
    gmt_s = gmt_offset * 3600
    sessions = [
        (0*3600 - gmt_s,  8*3600 - gmt_s, "Asian",  "A"),
        (8*3600 - gmt_s, 14*3600 - gmt_s, "London", "M"),
        (14*3600 - gmt_s, 22*3600 - gmt_s, "NY",     "D"),
    ]

    for d in range(days_back):
        day_dt = _utc_dt(now_utc) - timedelta(days=d)
        if day_dt.weekday() >= 5:
            continue
        day_base = _ts(day_dt.year, day_dt.month, day_dt.day)
        ds = day_dt.strftime("%Y%m%d")

        for s_off, e_off, ses, ztype in sessions:
            t1 = day_base + s_off
            t2 = day_base + e_off
            if t1 >= le:
                continue
            t2d = min(t2, le)
            closed = now_utc >= t2
            _emit2(cmds, f"D_{ds}_{ses}", t1, t2, t2d,
                   rates, rates, ztype, ses, "SES", closed, atr)


def gen_4h_zones(symbol, now_utc, cmds, gmt_offset=0, days_back=7):
    """
    Per calendar day (broker time): 6 x 4H candles.
    4H1+4H2 (00-08) = A
    4H3+4H4 (08-16) = M
    4H5+4H6 (16-24) = D
    Exactly 3 zones per day.
    """
    log("4H zones   (4H1+2=A  4H3+4=M  4H5+6=D per day)", "HEAD")
    rates_4h = _rates(symbol, mt5.TIMEFRAME_H4, days_back*6+6)
    rates_1h = _rates(symbol, mt5.TIMEFRAME_H1, days_back*24+24)
    if rates_4h is None:
        return
    atr = _atr(rates_4h, 14)
    le = _last_end(rates_4h, 4*3600)
    gmt_s = gmt_offset * 3600

    for d in range(days_back):
        day_dt = _utc_dt(now_utc) - timedelta(days=d)
        if day_dt.weekday() >= 5:
            continue
        day_base = _ts(day_dt.year, day_dt.month, day_dt.day)
        ds = day_dt.strftime("%Y%m%d")

        # 3 zones, each covering 8 hours (2 x 4H candles)
        for h_s, h_e, ztype, lbl in [
            (0*3600 - gmt_s,  8*3600 - gmt_s, "A", "4H1+2"),
            (8*3600 - gmt_s, 16*3600 - gmt_s, "M", "4H3+4"),
            (16*3600 - gmt_s, 24*3600 - gmt_s, "D", "4H5+6"),
        ]:
            t1 = day_base + h_s
            t2 = day_base + h_e
            if t1 >= le:
                continue
            t2d = min(t2, le)
            closed = now_utc >= t2
            fine = rates_1h if rates_1h is not None else rates_4h
            zh, zl = _hl(fine, t1, t2)
            ctype = _confirm(rates_4h, t1, t2, ztype, atr) if closed else ztype
            if zh is None:
                log_zone(f"4H_{ds}_{ztype}", t1, t2, zh, zl,
                         ztype, ctype, closed, skip=True)
                continue
            log_zone(f"4H_{ds}_{ztype}", t1, t2d, zh, zl,
                     ztype, ctype, closed)
            border, fill = _clr(ctype)
            if closed and ctype != ztype:
                marker = f"{ztype}→{ctype}✓"
            elif closed:
                marker = f"{ztype}·"
            else:
                marker = f"{ztype}…"
            cmds.append(_rect(f"4H_{ds}_{ztype}_r", t1, zh, t2d, zl,
                              border, fill, 1 if closed else 2,
                              0 if closed else 1))
            cmds.append(_text(f"4H_{ds}_{ztype}_t", t1, zh,
                              f"[4H] {marker} {lbl}", border))


def gen_1h_zones(symbol, now_utc, cmds, gmt_offset=0, days_back=5):
    """
    Per 4H block: 4 x 1H candles.
    1H1=A  1H2=M  1H3+1H4=D
    Exactly 3 zones per 4H block = 18 zones per day.
    """
    log("1H zones   (1H1=A  1H2=M  1H3+4=D per 4H block)", "HEAD")
    rates_1h = _rates(symbol, mt5.TIMEFRAME_H1, days_back*24+24)
    rates_15 = _rates(symbol, mt5.TIMEFRAME_M15, days_back*24*4+4)
    if rates_1h is None:
        return
    atr = _atr(rates_1h, 14)
    le = _last_end(rates_1h, 3600)
    gmt_s = gmt_offset * 3600

    for d in range(days_back):
        day_dt = _utc_dt(now_utc) - timedelta(days=d)
        if day_dt.weekday() >= 5:
            continue
        day_base = _ts(day_dt.year, day_dt.month, day_dt.day)
        ds = day_dt.strftime("%Y%m%d")

        # 6 blocks of 4H in a day
        for block in range(6):
            block_s = day_base + block*4*3600 - gmt_s
            block_e = block_s + 4*3600
            if block_s >= le:
                continue

            # 3 zones within this 4H block
            for h_off_s, h_off_e, ztype, lbl in [
                (0*3600, 1*3600, "A", "1H1"),
                (1*3600, 2*3600, "M", "1H2"),
                (2*3600, 4*3600, "D", "1H3+4"),
            ]:
                t1 = block_s + h_off_s
                t2 = block_s + h_off_e
                if t1 >= le:
                    continue
                t2d = min(t2, le)
                closed = now_utc >= t2
                fine = rates_15 if rates_15 is not None else rates_1h
                zh, zl = _hl(fine, t1, t2)
                ctype = _confirm(rates_1h, t1, t2, ztype,
                                 atr) if closed else ztype
                if zh is None:
                    log_zone(f"1H_{ds}_B{block}_{ztype}", t1, t2,
                             zh, zl, ztype, ctype, closed, skip=True)
                    continue
                log_zone(f"1H_{ds}_B{block}_{ztype}", t1, t2d,
                         zh, zl, ztype, ctype, closed)
                border, fill = _clr(ctype)
                if closed and ctype != ztype:
                    marker = f"{ztype}→{ctype}✓"
                elif closed:
                    marker = f"{ztype}·"
                else:
                    marker = f"{ztype}…"
                cmds.append(_rect(f"1H_{ds}_B{block}_{ztype}_r",
                                  t1, zh, t2d, zl,
                                  border, fill, 1 if closed else 2,
                                  0 if closed else 1))
                cmds.append(_text(f"1H_{ds}_B{block}_{ztype}_t", t1, zh,
                                  f"[1H] {marker} {lbl}", border))


def gen_5m_zones(symbol, now_utc, cmds, gmt_offset=0, days_back=2):
    """
    Per 1H block: 12 x 5M candles.
    5M1-4=A (0-20min)  5M5-8=M (20-40min)  5M9-12=D (40-60min)
    Exactly 3 zones per 1H = 72 zones per day.
    """
    log("5M zones   (5M1-4=A  5M5-8=M  5M9-12=D per 1H)", "HEAD")
    rates = _rates(symbol, mt5.TIMEFRAME_M5, days_back*24*12+24)
    if rates is None:
        return
    atr = _atr(rates, 14)
    le = _last_end(rates, 5*60)
    gmt_s = gmt_offset * 3600

    for d in range(days_back):
        day_dt = _utc_dt(now_utc) - timedelta(days=d)
        if day_dt.weekday() >= 5:
            continue
        day_base = _ts(day_dt.year, day_dt.month, day_dt.day)
        ds = day_dt.strftime("%Y%m%d")

        # 24 1H blocks in a day
        for hour in range(24):
            hour_s = day_base + hour*3600 - gmt_s
            if hour_s >= le:
                continue

            # 3 zones within this 1H
            for m_s, m_e, ztype, lbl in [
                (0*60, 20*60, "A", "5M1-4"),
                (20*60, 40*60, "M", "5M5-8"),
                (40*60, 60*60, "D", "5M9-12"),
            ]:
                t1 = hour_s + m_s
                t2 = hour_s + m_e
                if t1 >= le:
                    continue
                t2d = min(t2, le)
                closed = now_utc >= t2
                zh, zl = _hl(rates, t1, t2)
                ctype = _confirm(rates, t1, t2, ztype,
                                 atr) if closed else ztype
                if zh is None:
                    log_zone(f"5M_{ds}_H{hour:02d}_{ztype}", t1, t2,
                             zh, zl, ztype, ctype, closed, skip=True)
                    continue
                log_zone(f"5M_{ds}_H{hour:02d}_{ztype}", t1, t2d,
                         zh, zl, ztype, ctype, closed)
                border, fill = _clr(ctype)
                if closed and ctype != ztype:
                    marker = f"{ztype}→{ctype}✓"
                elif closed:
                    marker = f"{ztype}·"
                else:
                    marker = f"{ztype}…"
                cmds.append(_rect(f"5M_{ds}_H{hour:02d}_{ztype}_r",
                                  t1, zh, t2d, zl,
                                  border, fill, 1 if closed else 2,
                                  0 if closed else 1))
                cmds.append(_text(f"5M_{ds}_H{hour:02d}_{ztype}_t", t1, zh,
                                  f"[5M] {marker} {lbl}", border))


# ─────────────────────────────────────────────────────────────────
#  SUMMARY
# ─────────────────────────────────────────────────────────────────

def _summary(cmds):
    na = sum(1 for l in _logs if "🟦" in l)
    nm = sum(1 for l in _logs if "🟥" in l)
    nd = sum(1 for l in _logs if "🟩" in l)
    ns = sum(1 for l in _logs if "⏭" in l)
    nac = sum(1 for l in _logs if "ACTIVE" in l)
    ncl = sum(1 for l in _logs if "closed" in l)
    nr = sum(1 for l in _logs if "→" in l and "✓" in l)
    nz = sum(1 for c in cmds if c.startswith("DRAW_RECT"))
    log("=" * 60)
    log(f"Total zones : {nz}  (A={na} M={nm} D={nd})")
    log(f"  Closed    : {ncl}  |  Active: {nac}  |  Skipped: {ns}")
    log(f"  Reclassified by price behavior: {nr}")
    log(f"  Commands  : {len(cmds)}")


# ─────────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────────

def run_amd_detector(symbol="EURUSD", gmt_offset=0,
                     timeframe="ALL", clear_first=True):
    if not mt5.initialize():
        log("MT5 not initialized", "ERR")
        return False
    mt5.symbol_select(symbol, True)
    if mt5.symbol_info(symbol) is None:
        log(f"Symbol {symbol} not found", "ERR")
        return False

    now_utc = _utc_now()
    log("=" * 60)
    log(f"AMD Detector | {symbol} | GMT{gmt_offset:+d} | levels={timeframe}")
    log(f"UTC now    : {_utc_dt(now_utc).strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"Broker now : {_utc_dt(now_utc + gmt_offset*3600).strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 60)

    cmds = []
    if clear_first:
        cmds.append(f"DELETE_PREFIX|{AMD_PREFIX}")
        log("Clearing previous AMD zones")

    tf = timeframe.upper()
    if tf in ("ALL", "QTR"):
        gen_quarterly(symbol, now_utc, cmds)
    if tf in ("ALL", "MON"):
        gen_monthly(symbol, now_utc, cmds)
    if tf in ("ALL", "WK"):
        gen_weekly(symbol, now_utc, cmds)
    if tf in ("ALL", "DAY"):
        gen_daily_sessions(symbol, now_utc, cmds, gmt_offset)
    if tf in ("ALL", "4H"):
        gen_4h_zones(symbol, now_utc, cmds, gmt_offset)
    if tf in ("ALL", "1H"):
        gen_1h_zones(symbol, now_utc, cmds, gmt_offset)
    if tf in ("ALL", "5M"):
        gen_5m_zones(symbol, now_utc, cmds, gmt_offset)

    _summary(cmds)
    write_commands(cmds, symbol=symbol)
    log(f"✅ Done — AMD zones drawn on {symbol}", "OK")

    lp = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "amd_detector.log")
    with open(lp, "w", encoding="utf-8") as f:
        f.write("\n".join(_logs))
    log(f"Log → {lp}")
    return True


def clear_amd_zones(symbol="EURUSD"):
    if not mt5.initialize():
        return
    write_commands([f"DELETE_PREFIX|{AMD_PREFIX}"], symbol=symbol)
    log(f"AMD zones cleared from {symbol}")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="AMD Zone Detector")
    p.add_argument("--symbol",  default="EURUSD")
    p.add_argument("--gmt",     default=0, type=int)
    p.add_argument("--tf",      default="ALL",
                   choices=["ALL", "QTR", "MON", "WK", "DAY", "4H", "1H", "5M"])
    p.add_argument("--clear",   action="store_true")
    args = p.parse_args()
    if args.clear:
        clear_amd_zones(args.symbol)
    else:
        run_amd_detector(symbol=args.symbol,
                         gmt_offset=args.gmt,
                         timeframe=args.tf)
