"""
session_report.py — Session Report logic (data fetch + export)
Separated from gui.py to keep it clean and independently testable.
"""
import csv
from datetime import datetime
import MetaTrader5 as mt5

from config import MAGIC_NUMBER, MT5_LOGIN, MT5_PASSWORD, MT5_SERVER


def fetch_session_events(symbol: str, session_start: datetime) -> dict:
    """
    Fetch all closed + open bot positions since session_start.
    Returns a dict with: events[], wins, losses, rf_exits, total_pnl, best_pnl, worst_pnl
    """
    # Initialize with credentials — safe to call even if already initialized
    mt5.initialize(login=MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER)

    t_from = session_start
    t_to = datetime.now()

    # All deals in the session window
    deals = mt5.history_deals_get(t_from, t_to) or []

    # Only bot orders, only entry (0=open) and exit (1=close) types
    bot_deals = [d for d in deals
                 if d.magic == MAGIC_NUMBER and d.entry in (0, 1)]

    # Group by position_id → {open: deal, close: deal}
    pos_map: dict = {}
    for d in bot_deals:
        pid = d.position_id
        if pid not in pos_map:
            pos_map[pid] = {"open": None, "close": None}
        if d.entry == 0:
            pos_map[pid]["open"] = d
        elif d.entry == 1:
            # Keep the latest close deal (in case of partial closes)
            if pos_map[pid]["close"] is None or d.time > pos_map[pid]["close"].time:
                pos_map[pid]["close"] = d

    # Currently open positions for this symbol
    open_pos = [p for p in (mt5.positions_get(symbol=symbol) or [])
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

        # Pip calculation — use symbol point * 10 for forex
        sym_info = mt5.symbol_info(o.symbol)
        pip_size = sym_info.point * 10 if sym_info else 0.0001
        if c and pip_size > 0:
            raw_diff = c.price - o.price
            pips = round(raw_diff / pip_size, 1)
            # Invert for SELL positions
            if o.type == 1:  # DEAL_TYPE_SELL = 1
                pips = -pips
        else:
            pips = 0.0

        # Determine close reason — get SL/TP from history orders (deals have no sl/tp)
        entry_sl = 0.0
        entry_tp = 0.0
        try:
            orders = mt5.history_orders_get(position=pid)
            if orders:
                entry_sl = orders[0].sl or 0.0
                entry_tp = orders[0].tp or 0.0
        except Exception:
            pass

        reason = "Open"
        if c:
            cmt = (c.comment or "").upper()
            if "RF" in cmt or "RISK" in cmt:
                reason = "Risk-Free 🛡"
            elif "RESET" in cmt or "AUTOCLOSE" in cmt:
                reason = "Auto-Close 🤖"
            elif "PULLBACK" in cmt:
                reason = "Pullback Close"
            elif entry_sl and abs(c.price - entry_sl) < pip_size * 2:
                reason = "SL ❌"
            elif entry_tp and abs(c.price - entry_tp) < pip_size * 2:
                reason = "TP ✅"
            else:
                reason = "Manual"

            total_pnl += pnl
            if pnl > 0:
                wins += 1
            else:
                losses += 1
            if "Risk" in reason:
                rf_exits += 1
            best_pnl = max(best_pnl, pnl)
            worst_pnl = min(worst_pnl, pnl)

        # Parse gen/level from comment if available
        import re
        gen_lvl = ""
        m = re.search(r'G(\d+)L(\d+)', o.comment or "")
        if m:
            gen_lvl = f"G{m.group(1)}-L{m.group(2)}"

        events.append({
            "time":    datetime.fromtimestamp(o.time).strftime("%m-%d %H:%M:%S"),
            "symbol":  o.symbol,
            "gen_lvl": gen_lvl,
            "type":    "BUY" if o.type == 0 else "SELL",
            "entry":   f"{o.price:.5f}",
            "close":   f"{c.price:.5f}" if c else "—",
            "sl":      f"{entry_sl:.5f}" if entry_sl else "—",
            "tp":      f"{entry_tp:.5f}" if entry_tp else "—",
            "pnl":     f"{pnl:+.2f}" if c else "—",
            "pips":    f"{pips:+.1f}" if c else "—",
            "reason":  reason,
            "_pnl_v":  pnl,
            "_closed": c is not None,
        })

    # Add still-open positions
    for p in open_pos:
        tick = mt5.symbol_info_tick(p.symbol)
        cur = (tick.bid + tick.ask) / 2 if tick else 0.0
        import re
        m = re.search(r'G(\d+)L(\d+)', p.comment or "")
        gen_lvl = f"G{m.group(1)}-L{m.group(2)}" if m else ""
        events.append({
            "time":    datetime.fromtimestamp(p.time).strftime("%m-%d %H:%M:%S"),
            "symbol":  p.symbol,
            "gen_lvl": gen_lvl,
            "type":    "BUY" if p.type == 0 else "SELL",
            "entry":   f"{p.price_open:.5f}",
            "close":   f"{cur:.5f} ↻",
            "sl":      f"{p.sl:.5f}" if p.sl else "—",
            "tp":      f"{p.tp:.5f}" if p.tp else "—",
            "pnl":     f"{p.profit:+.2f}",
            "pips":    "—",
            "reason":  "🟢 Open",
            "_pnl_v":  p.profit,
            "_closed": False,
        })

    # Sort: closed by time, open positions at top
    events.sort(key=lambda e: (e["_closed"], e["time"]))

    return {
        "events":    events,
        "wins":      wins,
        "losses":    losses,
        "rf_exits":  rf_exits,
        "total_pnl": total_pnl,
        "best_pnl":  best_pnl if best_pnl != float("-inf") else 0.0,
        "worst_pnl": worst_pnl if worst_pnl != float("inf") else 0.0,
        "open_count": len(open_pos),
    }


def export_csv(events: list, filepath: str):
    """Write events list to a CSV file."""
    cols = ["time", "symbol", "gen_lvl", "type", "entry",
            "close", "sl", "tp", "pnl", "pips", "reason"]
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(events)


def export_txt(events: list, session_start: datetime, symbol: str, filepath: str):
    """Write a human-readable text report."""
    closed = [e for e in events if e["_closed"]]
    opens = [e for e in events if not e["_closed"]]
    wins = [e for e in closed if e["_pnl_v"] > 0]
    losses = [e for e in closed if e["_pnl_v"] <= 0]
    total_pnl = sum(e["_pnl_v"] for e in closed)
    wr = len(wins) / len(closed) * 100 if closed else 0

    dur = datetime.now() - session_start
    h, rem = divmod(int(dur.total_seconds()), 3600)
    m = rem // 60

    SEP = "=" * 64
    lines = [
        SEP,
        "  TRADERBOT SESSION REPORT",
        f"  Generated : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        SEP,
        f"  Symbol    : {symbol}",
        f"  Session   : {session_start.strftime('%H:%M:%S')} → "
        f"{datetime.now().strftime('%H:%M:%S')}  ({h}h {m}m)",
        f"  Positions : {len(events)} total  "
        f"({len(closed)} closed, {len(opens)} open)",
        f"  Win Rate  : {wr:.1f}%  ({len(wins)}W / {len(losses)}L)",
        f"  Total P&L : ${total_pnl:+.2f}",
        SEP,
        "",
        f"{'Time':<17} {'G/L':<8} {'Type':<5} {'Entry':<10} {'Close':<14} "
        f"{'P&L':>7} {'Pips':>7}  {'Reason'}",
        "-" * 80,
    ]
    for ev in events:
        lines.append(
            f"{ev['time']:<17} {ev['gen_lvl']:<8} {ev['type']:<5} "
            f"{ev['entry']:<10} {ev['close']:<14} "
            f"{ev['pnl']:>7} {ev['pips']:>7}  {ev['reason']}"
        )
    lines += [
        "",
        SEP,
        f"  Best trade  : ${max((e['_pnl_v'] for e in closed), default=0):+.2f}",
        f"  Worst trade : ${min((e['_pnl_v'] for e in closed), default=0):+.2f}",
        f"  Risk-Free exits: {sum(1 for e in closed if 'Risk' in e['reason'])}",
        f"  Bot-Reset exits: {sum(1 for e in closed if 'Reset' in e['reason'])}",
        SEP,
    ]
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
