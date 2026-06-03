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
import sys, os as _os
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import logging
import MetaTrader5 as mt5
from config import LOT_SIZE, TP_RR_RATIO, MAGIC_NUMBER

log = logging.getLogger("orders")


# ── Helpers ───────────────────────────────────────────────────────

def _filling_mode(symbol: str) -> int:
    info = mt5.symbol_info(symbol)
    if info is None:
        return mt5.ORDER_FILLING_RETURN
    m = info.filling_mode
    if m & 4: return mt5.ORDER_FILLING_RETURN
    if m & 2: return mt5.ORDER_FILLING_IOC
    if m & 1: return mt5.ORDER_FILLING_FOK
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
                       comment_prefix: str = "TB",
                       tp_pips: float = 0.0) -> list:
    """
    Build 6 order dicts for a source line.
    tp_pips > 0: all 3 buy positions share TP = L3_buy_entry + tp_pips,
                 all 3 sell positions share TP = L3_sell_entry - tp_pips.
    tp_pips = 0: use TP_RR_RATIO per position.
    """
    step = pip_step * pip_size
    above = [_round_price(source_price + step * i, symbol) for i in range(1, 4)]
    below = [_round_price(source_price - step * i, symbol) for i in range(1, 4)]

    # Fixed TP: same TP price for all 3 positions in the round
    fixed_tp_buy = fixed_tp_sell = None
    if tp_pips > 0:
        tp_dist = tp_pips * pip_size
        fixed_tp_buy  = _round_price(above[2] + tp_dist, symbol)  # L3 entry + tp_pips
        fixed_tp_sell = _round_price(below[2] - tp_dist, symbol)  # L3 entry - tp_pips
        log.info("Fixed TP: BUY_TP=%.5f SELL_TP=%.5f (%g pips from L3)",
                 fixed_tp_buy, fixed_tp_sell, tp_pips)

    orders = []
    for i in range(3):
        lvl = i + 1
        ea  = above[i]
        es  = below[i]

        sl_buy  = _adjust_sl(ea, es, symbol, True)
        sl_sell = _adjust_sl(es, ea, symbol, False)
        dist_b  = ea - sl_buy
        dist_s  = sl_sell - es

        if fixed_tp_buy is not None:
            tp_buy  = _adjust_tp(ea, fixed_tp_buy,  symbol, True)
            tp_sell = _adjust_tp(es, fixed_tp_sell, symbol, False)
        else:
            tp_buy  = _adjust_tp(ea, _round_price(ea + dist_b * TP_RR_RATIO, symbol), symbol, True)
            tp_sell = _adjust_tp(es, _round_price(es - dist_s * TP_RR_RATIO, symbol), symbol, False)

        orders.append({
            "level": lvl, "generation": generation, "source": source_price,
            "type": "BUY_STOP", "entry": ea, "sl": sl_buy, "tp": tp_buy,
            "sl_pips": round(dist_b / pip_size, 1),
        })
        orders.append({
            "level": lvl, "generation": generation, "source": source_price,
            "type": "SELL_STOP", "entry": es, "sl": sl_sell, "tp": tp_sell,
            "sl_pips": round(dist_s / pip_size, 1),
        })
    return orders


def send_orders(orders: list, symbol: str, lot_size: float = None) -> list:
    """Send order dicts to MT5. Returns results list."""
    import time as _t
    from config import MT5_LOGIN, MT5_PASSWORD, MT5_SERVER

    # Ensure MT5 is initialized with credentials — retry up to 3 times
    initialized = False
    for _attempt in range(3):
        if mt5.initialize(login=MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER):
            initialized = True
            break
        _t.sleep(0.5)
    if not initialized:
        log.error("MT5 initialize failed after 3 attempts in send_orders thread")
        return [{"order": o, "ticket": None, "ok": False,
                 "retcode": -1, "reason": "MT5 not initialized"} for o in orders]
    mt5.symbol_select(symbol, True)

    filling = _filling_mode(symbol)
    results = []
    vol = lot_size if lot_size and lot_size > 0 else LOT_SIZE

    # Get current price once for all orders in this batch
    tick = mt5.symbol_info_tick(symbol)
    current_price = (tick.bid + tick.ask) / 2 if tick else 0.0

    for o in orders:
        is_buy = o["type"] == "BUY_STOP"
        order_type = mt5.ORDER_TYPE_BUY_STOP if is_buy else mt5.ORDER_TYPE_SELL_STOP
        gen = o.get("generation", 0)
        lvl = o["level"]

        # Safety checks before placing pending order:
        if current_price > 0:
            min_dist = _min_stop_distance(symbol)
            entry    = o["entry"]

            # 1. Entry must be on correct side of current price
            if is_buy and current_price >= entry:
                log.warning("⏭  %s G%d-L%d SKIPPED — price %.5f already above entry %.5f",
                            o["type"], gen, lvl, current_price, entry)
                results.append({"order": o, "ticket": None, "ok": False,
                                "retcode": 0, "reason": "Price already past entry"})
                continue
            if not is_buy and current_price <= entry:
                log.warning("⏭  %s G%d-L%d SKIPPED — price %.5f already below entry %.5f",
                            o["type"], gen, lvl, current_price, entry)
                results.append({"order": o, "ticket": None, "ok": False,
                                "retcode": 0, "reason": "Price already past entry"})
                continue

            # 2. Entry must be far enough from current price (min stop distance)
            dist_to_current = abs(entry - current_price)
            if min_dist > 0 and dist_to_current < min_dist:
                log.warning("⏭  %s G%d-L%d SKIPPED — entry %.5f too close to price %.5f (min=%.5f)",
                            o["type"], gen, lvl, entry, current_price, min_dist)
                results.append({"order": o, "ticket": None, "ok": False,
                                "retcode": 0, "reason": f"Entry too close to price (min {min_dist:.5f})"})
                continue

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