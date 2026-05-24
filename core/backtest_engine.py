"""
backtest_engine.py — TraderBot v1
Ultra-minimal simulation. Bar loop does ZERO allocation.
Snapshots store only OHLC + timestamp.
Order state is reconstructed at render time from the final order list.
"""
import sys, os as _os
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import logging
import MetaTrader5 as mt5
import pandas as pd
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional, List

_log = logging.getLogger("backtest")

TF_MAP = {
    "M1":  mt5.TIMEFRAME_M1,
    "M5":  mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "H1":  mt5.TIMEFRAME_H1,
    "H4":  mt5.TIMEFRAME_H4,
    "D1":  mt5.TIMEFRAME_D1,
}


@dataclass
class BTOrder:
    id:          int
    level:       int
    generation:  int
    source:      float
    direction:   str
    entry:       float
    sl:          float
    tp:          float
    state:       str   = "PENDING"
    trigger_bar: int   = -1
    close_bar:   int   = -1
    close_price: float = 0.0
    pnl_pips:    float = 0.0
    spawned:     bool  = False
    added_at_bar: int  = 0    # which bar this order was added


@dataclass
class SourceLine:
    price:          float
    generation:     int
    above:          List[float]
    below:          List[float]
    spawned_at_bar: int = -1


@dataclass
class BarSnapshot:
    """Stores only OHLC. Order state reconstructed on demand."""
    bar_idx:  int
    bar_time: datetime
    open:     float
    high:     float
    low:      float
    close:    float


@dataclass
class BTResult:
    symbol:       str
    timeframe:    str
    source_price: float
    pip_step:     float
    pip_size:     float
    start_date:   datetime
    end_date:     datetime
    candles_used: int
    rect_top:     Optional[float] = None
    rect_bottom:  Optional[float] = None
    use_hline:    bool            = True
    orders:       list = field(default_factory=list)
    sources:      list = field(default_factory=list)
    snapshots:    list = field(default_factory=list)

    @property
    def triggered(self):  return [o for o in self.orders if o.state != "PENDING"]
    @property
    def wins(self):       return [o for o in self.orders if o.state == "TP"]
    @property
    def losses(self):     return [o for o in self.orders if o.state == "SL"]
    @property
    def total_pips(self): return sum(o.pnl_pips for o in self.triggered)
    @property
    def winrate(self):
        t = len(self.triggered)
        return len(self.wins) / t * 100 if t else 0.0

    def orders_at_bar(self, snap: BarSnapshot) -> list:
        """
        Return orders that existed at this bar, with their state AT that bar.
        State logic:
          - Order existed if added_at_bar <= snap.bar_idx
          - State = PENDING if trigger_bar == -1 or trigger_bar > bar_idx
          - State = TRIGGERED if trigger_bar <= bar_idx and close_bar > bar_idx
          - State = final state if close_bar <= bar_idx
        """
        b = snap.bar_idx
        result = []
        for o in self.orders:
            if o.added_at_bar > b:
                continue  # not spawned yet

            if o.trigger_bar == -1 or o.trigger_bar > b:
                state = "PENDING"
            elif o.close_bar == -1 or o.close_bar > b:
                state = "TRIGGERED"
            else:
                state = o.state  # SL or TP

            result.append({
                "id":          o.id,
                "level":       o.level,
                "generation":  o.generation,
                "source":      o.source,
                "direction":   o.direction,
                "entry":       o.entry,
                "sl":          o.sl,
                "tp":          o.tp,
                "state":       state,
                "trigger_bar": o.trigger_bar,
                "close_bar":   o.close_bar,
                "close_price": o.close_price if state in ("SL","TP") else 0.0,
                "pnl_pips":    o.pnl_pips    if state in ("SL","TP") else 0.0,
            })
        return result

    def sources_at_bar(self, snap: BarSnapshot) -> list:
        return [s for s in self.sources if s.spawned_at_bar <= snap.bar_idx]


def get_pip_size_for_symbol(symbol: str) -> float:
    if not mt5.initialize():
        return 0.0001
    mt5.symbol_select(symbol, True)
    info = mt5.symbol_info(symbol)
    if info is None:
        s = symbol.upper()
        if "JPY" in s: return 0.01
        if "XAU" in s: return 0.10
        if any(x in s for x in ["US30","NAS","DAX","SPX","UK100"]): return 1.0
        return 0.0001
    if info.digits <= 1: return 1.0
    return info.point * 10


def fetch_candles(symbol, tf_str, start, end):
    if not mt5.initialize():
        _log.error("mt5.initialize() failed")
        return None
    mt5.symbol_select(symbol, True)
    info = mt5.symbol_info(symbol)
    _log.info("symbol_info: %s", info.name if info else "None")
    tf = TF_MAP.get(tf_str, mt5.TIMEFRAME_M5)
    rates = mt5.copy_rates_range(symbol, tf, start, end)
    _log.info("copy_rates_range: %s rows",
              len(rates) if rates is not None else "None")
    if rates is None or len(rates) == 0:
        return None
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df.set_index("time", inplace=True)
    return df


def _make_source(price, step, generation, spawned_at_bar=0):
    return SourceLine(
        price=price, generation=generation,
        above=[round(price + step * i, 5) for i in range(1, 4)],
        below=[round(price - step * i, 5) for i in range(1, 4)],
        spawned_at_bar=spawned_at_bar,
    )


def _build_orders(src, pip_size, tp_rr, id_offset, added_at_bar=0):
    orders = []
    for i in range(3):
        dist = src.above[i] - src.below[i]
        orders.append(BTOrder(
            id=id_offset + i*2, level=i+1,
            generation=src.generation, source=src.price,
            direction="BUY_STOP",
            entry=src.above[i], sl=src.below[i],
            tp=round(src.above[i] + dist * tp_rr, 5),
            added_at_bar=added_at_bar,
        ))
        orders.append(BTOrder(
            id=id_offset + i*2+1, level=i+1,
            generation=src.generation, source=src.price,
            direction="SELL_STOP",
            entry=src.below[i], sl=src.above[i],
            tp=round(src.below[i] - dist * tp_rr, 5),
            added_at_bar=added_at_bar,
        ))
    return orders


def run_backtest(symbol, timeframe, source_price, pip_step, pip_size,
                 tp_rr, lookback_days=5, use_hline=True,
                 rect_top=None, rect_bottom=None):

    end   = datetime.now(timezone.utc)
    start = end - timedelta(days=lookback_days)
    _log.info("run_backtest: %s %s %dd src=%.5f pip=%.6f step=%.1f",
              symbol, timeframe, lookback_days, source_price, pip_size, pip_step)

    df = fetch_candles(symbol, timeframe, start, end)

    result = BTResult(
        symbol=symbol, timeframe=timeframe,
        source_price=source_price, pip_step=pip_step, pip_size=pip_size,
        start_date=start, end_date=end,
        candles_used=len(df) if df is not None else 0,
        rect_top=rect_top, rect_bottom=rect_bottom, use_hline=use_hline,
    )

    if df is None or len(df) < 5:
        _log.error("Not enough candles: %s", result.candles_used)
        return result

    step = pip_step * pip_size
    _log.info("step=%.6f  building initial orders...", step)

    if use_hline:
        init_src = _make_source(source_price, step, 0, spawned_at_bar=0)
    else:
        init_src = SourceLine(
            price=source_price, generation=0, spawned_at_bar=0,
            above=[round(rect_top    + step * i, 5) for i in range(1, 4)],
            below=[round(rect_bottom - step * i, 5) for i in range(1, 4)],
        )

    all_orders  = _build_orders(init_src, pip_size, tp_rr,
                                 id_offset=1, added_at_bar=0)
    all_sources = [init_src]
    next_id     = len(all_orders) + 1

    # Use raw numpy arrays — fastest possible iteration
    highs  = df["high"].values
    lows   = df["low"].values
    opens  = df["open"].values
    closes = df["close"].values
    # Convert timestamps once upfront
    times  = [t.to_pydatetime() for t in df.index]

    n_bars = len(highs)
    _log.info("Simulating %d bars with %d initial orders...", n_bars, len(all_orders))

    snapshots = []

    for bar_idx in range(n_bars):
        h = float(highs[bar_idx])
        l = float(lows[bar_idx])

        # Iterate only current orders — append after loop
        new_orders  = []
        new_sources = []

        for order in all_orders:
            if order.state == "PENDING":
                if ((order.direction == "BUY_STOP"  and h >= order.entry) or
                        (order.direction == "SELL_STOP" and l <= order.entry)):
                    order.state       = "TRIGGERED"
                    order.trigger_bar = bar_idx
                    # Phase 3: L2/L3 spawns new source — max 2 generations, max 30 orders
                    if (order.level in (2, 3) and not order.spawned
                            and order.generation < 2
                            and len(all_orders) + len(new_orders) < 30):
                        order.spawned = True
                        ns = _make_source(order.entry, step,
                                          order.generation + 1,
                                          spawned_at_bar=bar_idx)
                        new_sources.append(ns)
                        new_orders.extend(
                            _build_orders(ns, pip_size, tp_rr,
                                          next_id, added_at_bar=bar_idx))
                        next_id += 6

            elif order.state == "TRIGGERED":
                if order.direction == "BUY_STOP":
                    if l <= order.sl:
                        order.state = "SL"; order.close_bar = bar_idx
                        order.close_price = order.sl
                        order.pnl_pips = -(order.entry - order.sl) / pip_size
                    elif h >= order.tp:
                        order.state = "TP"; order.close_bar = bar_idx
                        order.close_price = order.tp
                        order.pnl_pips = (order.tp - order.entry) / pip_size
                else:
                    if h >= order.sl:
                        order.state = "SL"; order.close_bar = bar_idx
                        order.close_price = order.sl
                        order.pnl_pips = -(order.sl - order.entry) / pip_size
                    elif l <= order.tp:
                        order.state = "TP"; order.close_bar = bar_idx
                        order.close_price = order.tp
                        order.pnl_pips = (order.entry - order.tp) / pip_size

        if new_orders:
            all_orders.extend(new_orders)
        if new_sources:
            all_sources.extend(new_sources)

        # ZERO allocation snapshot — just OHLC + time
        snapshots.append(BarSnapshot(
            bar_idx  = bar_idx,
            bar_time = times[bar_idx],
            open     = float(opens[bar_idx]),
            high     = h,
            low      = l,
            close    = float(closes[bar_idx]),
        ))

    for order in all_orders:
        if order.state == "TRIGGERED":
            order.state = "OPEN"
            order.close_bar = -1  # still open

    _log.info("Done: %d bars %d orders W:%d L:%d pips:%.1f",
              n_bars, len(all_orders),
              sum(1 for o in all_orders if o.state == "TP"),
              sum(1 for o in all_orders if o.state == "SL"),
              sum(o.pnl_pips for o in all_orders))

    result.orders    = all_orders
    result.sources   = all_sources
    result.snapshots = snapshots
    return result