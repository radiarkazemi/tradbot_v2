"""
order_manager.py — TraderBot v1
Places buy-stop and sell-stop orders based on the 6 level lines.

Logic:
  Above line 1 → BUY STOP   | SL = Below line 1
  Above line 2 → BUY STOP   | SL = Below line 2
  Above line 3 → BUY STOP   | SL = Below line 3
  Below line 1 → SELL STOP  | SL = Above line 1
  Below line 2 → SELL STOP  | SL = Above line 2
  Below line 3 → SELL STOP  | SL = Above line 3

TP = configurable (default = 2x the SL distance)
"""
import sys, os as _os
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import logging
import MetaTrader5 as mt5
from config import WATCH_SYMBOL, LOT_SIZE, TP_RR_RATIO, MAGIC_NUMBER

log = logging.getLogger("order_manager")


def _get_filling_mode(symbol: str) -> int:
    sym = mt5.symbol_info(symbol)
    if sym is None:
        return mt5.ORDER_FILLING_RETURN
    m = sym.filling_mode
    if m & 4: return mt5.ORDER_FILLING_RETURN
    if m & 2: return mt5.ORDER_FILLING_IOC
    if m & 1: return mt5.ORDER_FILLING_FOK
    return mt5.ORDER_FILLING_RETURN


def place_level_orders(source_price: float, pip_size: float,
                       pip_step: float, symbol: str = None) -> list:
    """
    Given the trader's line price, calculate all 6 level prices
    and place buy-stop / sell-stop orders with mirrored SLs.
    Returns list of placed order results.
    """
    sym = symbol or WATCH_SYMBOL
    step = pip_step * pip_size

    # Calculate the 6 level prices
    above = [source_price + step * i for i in range(1, 4)]   # [+1, +2, +3]
    below = [source_price - step * i for i in range(1, 4)]   # [-1, -2, -3]

    orders = []

    # above[0] ↔ below[0], above[1] ↔ below[1], above[2] ↔ below[2]
    for i in range(3):
        entry_buy  = above[i]
        sl_buy     = below[i]       # mirror SL across source line
        dist_buy   = entry_buy - sl_buy
        tp_buy     = entry_buy + dist_buy * TP_RR_RATIO

        entry_sell = below[i]
        sl_sell    = above[i]       # mirror SL across source line
        dist_sell  = sl_sell - entry_sell
        tp_sell    = entry_sell - dist_sell * TP_RR_RATIO

        orders.append({
            "level":      i + 1,
            "type":       "BUY_STOP",
            "entry":      round(entry_buy,  5),
            "sl":         round(sl_buy,     5),
            "tp":         round(tp_buy,     5),
            "sl_pips":    round(dist_buy  / pip_size, 1),
        })
        orders.append({
            "level":      i + 1,
            "type":       "SELL_STOP",
            "entry":      round(entry_sell, 5),
            "sl":         round(sl_sell,    5),
            "tp":         round(tp_sell,    5),
            "sl_pips":    round(dist_sell / pip_size, 1),
        })

    return orders


def send_orders(orders: list, symbol: str = None) -> list:
    """Send the calculated orders to MT5."""
    sym = symbol or WATCH_SYMBOL
    filling = _get_filling_mode(sym)
    results = []

    for o in orders:
        order_type = (mt5.ORDER_TYPE_BUY_STOP
                      if o["type"] == "BUY_STOP"
                      else mt5.ORDER_TYPE_SELL_STOP)

        request = {
            "action":       mt5.TRADE_ACTION_PENDING,
            "symbol":       sym,
            "volume":       LOT_SIZE,
            "type":         order_type,
            "price":        o["entry"],
            "sl":           o["sl"],
            "tp":           o["tp"],
            "deviation":    10,
            "magic":        MAGIC_NUMBER,
            "comment":      f"TB_L{o['level']}_{o['type'][:1]}",
            "type_time":    mt5.ORDER_TIME_GTC,
            "type_filling": filling,
        }

        res = mt5.order_send(request)
        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            log.info("✅  %s L%d placed | entry=%.5f sl=%.5f tp=%.5f",
                     o["type"], o["level"], o["entry"], o["sl"], o["tp"])
            results.append({"order": o, "ticket": res.order, "ok": True})
        else:
            code = res.retcode if res else -1
            # Translate common retcodes to human-readable reasons
            reasons = {
                10018: "Market closed",
                10019: "Not enough money",
                10016: "Invalid stops (SL/TP too close to entry)",
                10015: "Invalid SL/TP (check min stop level for symbol)",
                10014: "Invalid volume",
                10013: "Invalid price",
                10006: "Order rejected",
                10004: "Requote",
                10009: "Request completed — check MT5 journal",
            }
            reason = reasons.get(code, f"retcode={code}")
            log.error("❌  %s L%d FAILED | %s | entry=%.5f sl=%.5f tp=%.5f",
                      o["type"], o["level"], reason, o["entry"], o["sl"], o["tp"])
            results.append({"order": o, "ticket": None, "ok": False,
                            "retcode": code, "reason": reason})

    return results


def cancel_all_tb_orders(symbol: str = None) -> int:
    """Cancel all pending orders placed by this bot (magic number match)."""
    sym = symbol or WATCH_SYMBOL
    orders = mt5.orders_get(symbol=sym)
    if not orders:
        return 0
    cancelled = 0
    for o in orders:
        if o.magic == MAGIC_NUMBER:
            res = mt5.order_send({
                "action": mt5.TRADE_ACTION_REMOVE,
                "order":  o.ticket,
            })
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                cancelled += 1
                log.info("🗑️  Cancelled order #%d", o.ticket)
    return cancelled