"""
order_manager.py — TraderBot v1  Phase 2+3

ORDER LOGIC:
  Source line at price P, step = pip_step × pip_size

  Initial 6 pending orders (placed immediately when line drawn):
    BUY_STOP  L1/L2/L3  at P+1×step / P+2×step / P+3×step
    SELL_STOP L1/L2/L3  at P-1×step / P-2×step / P-3×step
    SL for each = mirror level across P

  Activation (candle touches main line):
    → Orders become active. No re-placement needed — they're already pending.

  Phase 3 — when L2 or L3 is TRIGGERED (not L1):
    → That level's entry price becomes a NEW source line
    → 6 fresh pending orders placed from the new source
    → Original orders remain active
    → This cascades (L2/L3 of the new source also spawns) but max 2 generations
    → 9 rounds max total spawns (night range)

  Stop distance fix:
    MT5 requires minimum stop distance. We fetch the symbol's STOPLEVEL
    and ensure SL is at least that far from entry.
"""
from config import LOT_SIZE, TP_RR_RATIO, MAGIC_NUMBER
import MetaTrader5 as mt5
import logging
import sys
import os as _os
sys.path.insert(0, _os.path.dirname(
    _os.path.dirname(_os.path.abspath(__file__))))


log = logging.getLogger("orders")


# ── Helpers ───────────────────────────────────────────────────────

def _filling_mode(symbol: str) -> int:
    info = mt5.symbol_info(symbol)
    if info is None:
        return mt5.ORDER_FILLING_RETURN
    m = info.filling_mode
    if m & 4:
        return mt5.ORDER_FILLING_RETURN
    if m & 2:
        return mt5.ORDER_FILLING_IOC
    if m & 1:
        return mt5.ORDER_FILLING_FOK
    return mt5.ORDER_FILLING_RETURN


def _min_stop_distance(symbol: str) -> float:
    """Return the minimum stop distance in price units."""
    info = mt5.symbol_info(symbol)
    if info is None:
        return 0.0
    # stoplevel is in points — add 20% buffer for safety
    min_dist = info.trade_stops_level * info.point * 1.2
    log.debug("Min stop distance for %s: %.5f (stoplevel=%d points)",
              symbol, min_dist, info.trade_stops_level)
    return min_dist


def _round_price(price: float, symbol: str) -> float:
    """Round price to symbol's digit precision."""
    info = mt5.symbol_info(symbol)
    digits = info.digits if info else 5
    return round(price, digits)


def _adjust_sl(entry: float, sl: float, symbol: str, is_buy: bool) -> float:
    """Ensure SL is at least min_stop_distance from entry."""
    min_dist = _min_stop_distance(symbol)
    if min_dist <= 0:
        return sl
    if is_buy:
        # SL must be below entry by at least min_dist
        if entry - sl < min_dist:
            sl = entry - min_dist
    else:
        # SL must be above entry by at least min_dist
        if sl - entry < min_dist:
            sl = entry + min_dist
    return _round_price(sl, symbol)


def _adjust_tp(entry: float, tp: float, symbol: str, is_buy: bool) -> float:
    """Ensure TP is at least min_stop_distance from entry."""
    min_dist = _min_stop_distance(symbol)
    if min_dist <= 0:
        return tp
    if is_buy:
        if tp - entry < min_dist:
            tp = entry + min_dist
    else:
        if entry - tp < min_dist:
            tp = entry - min_dist
    return _round_price(tp, symbol)


def build_level_orders(source_price: float, pip_size: float,
                       pip_step: float, symbol: str,
                       generation: int = 0,
                       comment_prefix: str = "TB") -> list:
    """
    Build 6 order dicts (not yet sent) for a source line.
    Returns list of order parameter dicts.
    """
    step = pip_step * pip_size
    above = [_round_price(source_price + step * i, symbol)
             for i in range(1, 4)]
    below = [_round_price(source_price - step * i, symbol)
             for i in range(1, 4)]

    min_dist = _min_stop_distance(symbol)
    orders = []
    for i in range(3):
        lvl = i + 1
        ea = above[i]
        es = below[i]

        # SL = mirror level. If distance < min_stop, push SL further out.
        # Keep entry fixed — only adjust SL (and TP proportionally).
        sl_buy_raw = es   # mirror: buy SL = below level
        sl_sell_raw = ea   # mirror: sell SL = above level

        sl_buy = _adjust_sl(ea, sl_buy_raw,  symbol, True)
        sl_sell = _adjust_sl(es, sl_sell_raw, symbol, False)

        dist_b = ea - sl_buy
        dist_s = sl_sell - es
        tp_buy = _adjust_tp(ea, _round_price(
            ea + dist_b * TP_RR_RATIO, symbol), symbol, True)
        tp_sell = _adjust_tp(es, _round_price(
            es - dist_s * TP_RR_RATIO, symbol), symbol, False)

        orders.append({
            "level":      lvl,
            "generation": generation,
            "source":     source_price,
            "type":       "BUY_STOP",
            "entry":      ea,
            "sl":         sl_buy,
            "tp":         tp_buy,
            "sl_pips":    round(dist_b / pip_size, 1),
        })
        orders.append({
            "level":      lvl,
            "generation": generation,
            "source":     source_price,
            "type":       "SELL_STOP",
            "entry":      es,
            "sl":         sl_sell,
            "tp":         tp_sell,
            "sl_pips":    round(dist_s / pip_size, 1),
        })
    return orders


def send_orders(orders: list, symbol: str, lot_size: float = None) -> list:
    """Send order dicts to MT5. Returns results list."""
    filling = _filling_mode(symbol)
    results = []
    vol = lot_size if lot_size and lot_size > 0 else LOT_SIZE

    for o in orders:
        is_buy = o["type"] == "BUY_STOP"
        order_type = mt5.ORDER_TYPE_BUY_STOP if is_buy else mt5.ORDER_TYPE_SELL_STOP
        gen = o.get("generation", 0)
        lvl = o["level"]

        request = {
            "action":       mt5.TRADE_ACTION_PENDING,
            "symbol":       symbol,
            "volume":       vol,
            "type":         order_type,
            "price":        o["entry"],
            "sl":           o["sl"],
            "tp":           o["tp"],
            "deviation":    20,
            "magic":        MAGIC_NUMBER,
            "comment":      f"TB_G{gen}L{lvl}{'B' if is_buy else 'S'}",
            "type_time":    mt5.ORDER_TIME_GTC,
            "type_filling": filling,
        }

        res = mt5.order_send(request)
        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            log.info("✅ %s G%d-L%d | entry=%.5f sl=%.5f tp=%.5f (%.1f pips)",
                     o["type"], gen, lvl, o["entry"], o["sl"], o["tp"], o["sl_pips"])
            results.append({"order": o, "ticket": res.order, "ok": True})
        else:
            code = res.retcode if res else -1
            _REASONS = {
                10018: "Market closed",
                10019: "Not enough money",
                10016: "Stops too close to entry",
                10015: "Invalid SL/TP",
                10014: "Invalid volume",
                10013: "Invalid price",
                10006: "Order rejected",
                10004: "Requote",
            }
            reason = _REASONS.get(code, f"retcode={code}")
            log.error("❌ %s G%d-L%d FAILED | %s | entry=%.5f sl=%.5f tp=%.5f",
                      o["type"], gen, lvl, reason, o["entry"], o["sl"], o["tp"])
            results.append({"order": o, "ticket": None, "ok": False,
                            "retcode": code, "reason": reason})

    ok = sum(1 for r in results if r["ok"])
    log.info("Order batch: %d/%d placed", ok, len(results))
    return results


def place_level_orders(source_price: float, pip_size: float,
                       pip_step: float, symbol: str,
                       generation: int = 0,
                       tp_pips: float = 0.0,
                       lot_size: float = None) -> list:
    """Build + send 6 orders for a source line. Returns results."""
    orders = build_level_orders(source_price, pip_size, pip_step,
                                symbol, generation, tp_pips=tp_pips)
    return send_orders(orders, symbol, lot_size=lot_size)


def cancel_all_tb_orders(symbol: str) -> int:
    """Cancel all bot pending orders (magic number match)."""
    orders = mt5.orders_get(symbol=symbol)
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
                log.info("Cancelled order #%d", o.ticket)
            else:
                log.warning("Failed to cancel #%d: %s", o.ticket,
                            res.retcode if res else "no response")
    log.info("Cancelled %d bot orders", cancelled)
    return cancelled


def get_active_positions(symbol: str) -> list:
    """Get all open positions placed by this bot."""
    positions = mt5.positions_get(symbol=symbol)
    if not positions:
        return []
    return [p for p in positions if p.magic == MAGIC_NUMBER]
