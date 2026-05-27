"""
╔══════════════════════════════════════════════════════════════════╗
║         TraderBot v1 — Chart Object Watcher (Phase 2)           ║
║                                                                  ║
║  Phase 1: Detect trader-drawn objects                           ║
║  Phase 2: When a line is detected, auto-draw 3 lines above      ║
║           and 3 below it, each 1.5 pips apart, diff colors      ║
╚══════════════════════════════════════════════════════════════════╝
"""
from config import (
    MT5_LOGIN, MT5_PASSWORD, MT5_SERVER,
    WATCH_SYMBOL, SCAN_INTERVAL_SEC, LOG_LEVEL,
    AUTO_OBJECT_PREFIXES, PIP_STEP, BOT_LINE_PREFIX,
)
import MetaTrader5 as mt5
from typing import Optional
from dataclasses import dataclass
from datetime import datetime
import logging
import time
import os
import sys
import os as _os
sys.path.insert(0, _os.path.dirname(
    _os.path.dirname(_os.path.abspath(__file__))))


# Always create logs/ at project root, not cwd
_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
os.makedirs(os.path.join(_ROOT, "logs"), exist_ok=True)

try:
    from core.line_drawer import draw_level_lines, clear_level_lines, get_pip_size
except ModuleNotFoundError:
    from line_drawer import draw_level_lines, clear_level_lines, get_pip_size

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(
            _ROOT, "logs", "chart_watcher.log"), encoding="utf-8"),
    ],
)
log = logging.getLogger("chart_watcher")


@dataclass
class ChartObject:
    name:      str
    obj_type:  str
    type_id:   int
    price1:    float
    price2:    float
    time1:     Optional[datetime]
    time2:     Optional[datetime]
    color:     int = 0

    @property
    def is_hline(self): return self.obj_type == "HLINE"

    @property
    def is_rectangle(
        self): return self.obj_type == "RECTANGLE" or self.type_id == 20

    @property
    def is_trend(self): return self.obj_type == "TREND"

    @property
    def rect_valid(self):
        # price2 must be non-zero and different from price1 to be a valid rectangle
        return (self.is_rectangle
                and self.price2 != 0.0
                and abs(self.price1 - self.price2) > 0.00001)

    @property
    def rect_top(self):
        return max(self.price1, self.price2) if self.rect_valid else None

    @property
    def rect_bottom(self):
        return min(self.price1, self.price2) if self.rect_valid else None

    @property
    def rect_height(self):
        return round(self.rect_top - self.rect_bottom, 5) if self.rect_valid else None


def is_auto_object(name: str) -> bool:
    # Skip empty names or internal MT5 chart objects
    if not name or name.strip() == "":
        return True
    # Skip vertical lines (MT5 internal date markers)
    # Skip objects with no meaningful name
    for prefix in AUTO_OBJECT_PREFIXES:
        if name.startswith(prefix):
            return True
    return False


def get_file_paths(symbol: str = None) -> list:
    """Search ALL possible MT5 data paths — works across different computers."""
    paths = []
    fname_sym = f"trader_objects_{symbol}.txt" if symbol else None
    fname_gen = "trader_objects.txt"

    # 1. Common folder via APPDATA
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        common = os.path.join(appdata, "MetaQuotes",
                              "Terminal", "Common", "Files")
        if fname_sym:
            paths.append(os.path.join(common, fname_sym))
        paths.append(os.path.join(common, fname_gen))

    # 2. MT5 terminal data path (from running instance)
    try:
        info = mt5.terminal_info()
        if info and hasattr(info, "data_path") and info.data_path:
            local = os.path.join(info.data_path, "MQL5", "Files")
            if fname_sym:
                paths.append(os.path.join(local, fname_sym))
            paths.append(os.path.join(local, fname_gen))
    except Exception:
        pass

    # 3. Scan ALL MetaQuotes terminal folders (handles multiple MT5 installations)
    try:
        mq_root = os.path.join(appdata, "MetaQuotes", "Terminal")
        if os.path.isdir(mq_root):
            for terminal_id in os.listdir(mq_root):
                t_path = os.path.join(mq_root, terminal_id)
                if os.path.isdir(t_path):
                    local = os.path.join(t_path, "MQL5", "Files")
                    if fname_sym:
                        paths.append(os.path.join(local, fname_sym))
                    paths.append(os.path.join(local, fname_gen))
    except Exception:
        pass

    # 4. Also check roaming MetaQuotes path (some MT5 versions use different structure)
    try:
        roaming = os.path.join(os.environ.get("USERPROFILE", ""), "AppData",
                               "Roaming", "MetaQuotes", "Terminal")
        if os.path.isdir(roaming):
            for terminal_id in os.listdir(roaming):
                t_path = os.path.join(roaming, terminal_id)
                if os.path.isdir(t_path):
                    local = os.path.join(t_path, "MQL5", "Files")
                    if fname_sym:
                        paths.append(os.path.join(local, fname_sym))
                    paths.append(os.path.join(local, fname_gen))
    except Exception:
        pass

    return paths


def find_objects_file(symbol: str = None) -> Optional[str]:
    """Return the most recently written matching file across all MT5 paths.
    Also searches for files without _i suffix as fallback (broker symbol variants).
    """
    import time as _t

    # Build search list: try exact symbol AND without _i suffix AND with _i suffix
    symbols_to_try = [symbol]
    if symbol:
        if symbol.endswith("_i"):
            symbols_to_try.append(symbol[:-2])  # XAUUSD_i → XAUUSD
        else:
            symbols_to_try.append(symbol + "_i")  # XAUUSD → XAUUSD_i
        symbols_to_try.append(None)  # generic trader_objects.txt

    best_path = None
    best_age = float("inf")

    for sym in symbols_to_try:
        for p in get_file_paths(sym):
            if os.path.exists(p):
                try:
                    age = _t.time() - os.path.getmtime(p)
                    if age < best_age:
                        best_age = age
                        best_path = p
                except Exception:
                    if best_path is None:
                        best_path = p

    return best_path


def parse_objects_file(path: str, filter_symbol: str = None) -> tuple:
    """Returns (trader_objects, auto_objects, file_symbol)."""
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception as e:
        log.warning("Could not read file: %s", e)
        return [], [], None, {}

    # Read file symbol from header
    file_symbol = None
    for line in lines:
        if line.startswith("SYMBOL:"):
            file_symbol = line.strip().split(":", 1)[1]
            break

    def _to_dt(ts_str):
        try:
            v = int(ts_str)
            return datetime.fromtimestamp(v) if v > 0 else None
        except Exception:
            return None

    trader_objects, auto_objects = [], []
    for line in lines:
        line = line.strip()
        if not line.startswith("OBJ"):
            continue
        parts = line.split("|")
        data = {}
        for p in parts[1:]:
            if ":" in p:
                k, v = p.split(":", 1)
                data[k] = v
        try:
            co = ChartObject(
                name=data.get("NAME", "?"),
                obj_type=data.get("TYPE", "OTHER"),
                type_id=int(data.get("TYPEID", 0)),
                price1=float(data.get("PRICE1", 0)),
                price2=float(data.get("PRICE2", 0)),
                time1=_to_dt(data.get("TIME1", "0")),
                time2=_to_dt(data.get("TIME2", "0")),
                color=int(data.get("COLOR", 0)),
            )
            # Also skip VLINEs (type_id=0) — these are MT5 internal date markers
            if is_auto_object(co.name) or co.type_id == 0:
                auto_objects.append(co)
            else:
                trader_objects.append(co)
        except Exception as e:
            log.debug("Skipping line: %s — %s", line[:60], e)

    # Parse candle data from header
    candle = {}
    for line in lines:
        for key in ("CANDLE_O", "CANDLE_H", "CANDLE_L", "CANDLE_C", "BID", "CANDLE_T",
                    "PREV_H", "PREV_L", "PREV_C", "PREV_O", "PREV_T"):
            if line.startswith(key + ":"):
                try:
                    val = line.strip().split(":", 1)[1]
                    candle[key] = int(val) if key in (
                        "CANDLE_T", "PREV_T") else float(val)
                except:
                    pass

    log.debug("Parsed: %d trader objects, %d auto | EA=%s | H=%.5f L=%.5f",
              len(trader_objects), len(auto_objects), file_symbol,
              candle.get("CANDLE_H", 0), candle.get("CANDLE_L", 0))
    return trader_objects, auto_objects, file_symbol, candle


def connect_mt5() -> bool:
    if not mt5.initialize():
        log.error("MT5 initialise failed: %s", mt5.last_error())
        return False
    authorised = mt5.login(MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER)
    if not authorised:
        log.error("MT5 login failed: %s", mt5.last_error())
        mt5.shutdown()
        return False
    acc = mt5.account_info()
    log.info("✅  Connected — %s | %s | Balance: %.2f %s",
             acc.server, acc.name, acc.balance, acc.currency)
    return True


def get_current_price() -> Optional[float]:
    tick = mt5.symbol_info_tick(WATCH_SYMBOL)
    return (tick.bid + tick.ask) / 2 if tick else None


def print_objects(trader_objects: list, auto_count: int,
                  current_price: Optional[float], file_age: float):
    sep = "─" * 64
    print(f"\n{sep}")
    print(f"  🕐  {datetime.now().strftime('%H:%M:%S')}   |   {WATCH_SYMBOL}   |   file: {file_age:.0f}s ago")
    if current_price:
        print(
            f"  📊  Current price: {current_price:.5f}   |   auto-objects hidden: {auto_count}")
    print(sep)

    if not trader_objects:
        print("  (no trader-drawn objects on chart)")
        print(f"  💡  Draw a horizontal line on your MT5 chart")
        print(sep)
        return

    hlines = [o for o in trader_objects if o.is_hline]
    rects = [o for o in trader_objects if o.is_rectangle]
    trends = [o for o in trader_objects if o.is_trend]
    others = [o for o in trader_objects
              if not o.is_hline and not o.is_rectangle and not o.is_trend]

    if hlines:
        pip = get_pip_size(WATCH_SYMBOL)
        step_price = PIP_STEP * pip
        print(
            f"  📏  HORIZONTAL LINES ({len(hlines)})   [level spacing: {PIP_STEP} pips = {step_price:.5f}]")
        for o in hlines:
            dist = ""
            if current_price:
                d = o.price1 - current_price
                dist = f"   ({'+' if d >= 0 else ''}{d:.2f} from price)"
            print(f"      • [{o.name}]   {o.price1:.5f}{dist}")
            print(f"          🟠 above 3: {o.price1 + step_price*3:.5f}")
            print(f"          🟠 above 2: {o.price1 + step_price*2:.5f}")
            print(f"          🟠 above 1: {o.price1 + step_price*1:.5f}")
            print(f"          ──  YOUR LINE ──────────────────")
            print(f"          🟢 below 1: {o.price1 - step_price*1:.5f}")
            print(f"          🟢 below 2: {o.price1 - step_price*2:.5f}")
            print(f"          🟢 below 3: {o.price1 - step_price*3:.5f}")

    if rects:
        print(f"  🟦  RECTANGLES ({len(rects)})")
        for o in rects:
            print(
                f"      • [{o.name}]  top: {o.rect_top:.5f}  bottom: {o.rect_bottom:.5f}  height: {o.rect_height:.5f}")

    if trends:
        print(f"  📉  TREND LINES ({len(trends)})")
        for o in trends:
            print(f"      • [{o.name}]  {o.price1:.5f} → {o.price2:.5f}")

    if others:
        print(f"  📌  OTHER ({len(others)})")
        for o in others:
            print(
                f"      • [{o.name}]  type: {o.obj_type}  price: {o.price1:.5f}")

    print(sep)


def main():
    log.info("=" * 64)
    log.info("  TraderBot v1 — Chart Object Watcher — Phase 2")
    log.info("=" * 64)

    if not connect_mt5():
        return

    pip = get_pip_size(WATCH_SYMBOL)
    log.info("Symbol: %s  |  pip size: %.5f  |  step: %.1f pips = %.5f",
             WATCH_SYMBOL, pip, PIP_STEP, PIP_STEP * pip)
    log.info(
        "Draw a horizontal line on your chart — bot will add 3+3 levels around it.")
    log.info("Press Ctrl+C to stop.")

    prev_trader_names: set = set()
    # Track what we've already drawn levels for (name → price)
    drawn_levels: dict = {}
    warned_missing = False

    try:
        while True:
            path = find_objects_file()

            if path is None:
                if not warned_missing:
                    log.warning(
                        "⚠️  trader_objects.txt not found — is ObjectExporter EA on the chart?")
                    warned_missing = True
                print(
                    f"\n  ⏳  {datetime.now().strftime('%H:%M:%S')}  Waiting for ObjectExporter EA…")
                time.sleep(SCAN_INTERVAL_SEC)
                continue

            warned_missing = False
            file_age = time.time() - os.path.getmtime(path)
            trader_objects, auto_objects = parse_objects_file(path)
            current_price = get_current_price()

            current_names = {o.name for o in trader_objects}
            added = current_names - prev_trader_names
            removed = prev_trader_names - current_names

            # ── Handle NEW objects ────────────────────────────
            for name in added:
                obj = next(o for o in trader_objects if o.name == name)
                log.info("🆕  TRADER drew: [%s]  %s  @ %.5f",
                         name, obj.obj_type, obj.price1)

                if obj.is_hline:
                    step, cmds = draw_level_lines(
                        symbol=WATCH_SYMBOL,
                        source_name=name,
                        source_price=obj.price1,
                        pip_step=PIP_STEP,
                        prefix=BOT_LINE_PREFIX,
                    )
                    drawn_levels[name] = obj.price1
                    log.info(
                        "🎯  Drew 3 levels above + 3 below  [step=%.5f]", step)

                elif obj.is_rectangle:
                    if not obj.rect_valid:
                        log.debug(
                            "Rectangle [%s] not yet fully drawn — skipping", name)
                        continue
                    top = obj.rect_top
                    bottom = obj.rect_bottom
                    pip = get_pip_size(WATCH_SYMBOL)
                    step = PIP_STEP * pip
                    log.info("🟦  Rectangle — top: %.5f  bottom: %.5f  height: %.5f",
                             top, bottom, obj.rect_height)
                    # 3 lines ABOVE the top edge only
                    cmds = [f"DELETE_PREFIX|{BOT_LINE_PREFIX}"]
                    colors_above = [0x0080FF, 0x0050CC, 0x003099]
                    colors_below = [0x80FF00, 0x50CC00, 0x309900]
                    for i, clr in enumerate(colors_above, 1):
                        nm = f"{BOT_LINE_PREFIX}ABOVE_{i}_{name[:20]}"
                        cmds.append(
                            f"DRAW_HLINE|{nm}|{top + step*i:.5f}|{clr}|1|1")
                    # 3 lines BELOW the bottom edge only
                    for i, clr in enumerate(colors_below, 1):
                        nm = f"{BOT_LINE_PREFIX}BELOW_{i}_{name[:20]}"
                        cmds.append(
                            f"DRAW_HLINE|{nm}|{bottom - step*i:.5f}|{clr}|1|1")
                    from line_drawer import write_commands
                    write_commands(cmds)
                    drawn_levels[name] = ("RECT", top, bottom)
                    log.info("🎯  3 above top (%.5f) + 3 below bottom (%.5f)  step=%.5f",
                             top, bottom, step)

            # ── Handle REMOVED objects ────────────────────────
            for name in removed:
                log.info("🗑️   TRADER removed: [%s]", name)
                if name in drawn_levels:
                    clear_level_lines(prefix=BOT_LINE_PREFIX)
                    drawn_levels.clear()
                    log.info("🧹  Cleared bot level lines")

            # ── Check if line was MOVED (price changed) ───────
            for obj in trader_objects:
                if obj.is_hline and obj.name in drawn_levels:
                    if abs(obj.price1 - drawn_levels[obj.name]) > 0.00001:
                        log.info("↕️   LINE MOVED: [%s]  %.5f → %.5f — redrawing levels",
                                 obj.name, drawn_levels[obj.name], obj.price1)
                        step, _ = draw_level_lines(
                            symbol=WATCH_SYMBOL,
                            source_name=obj.name,
                            source_price=obj.price1,
                            pip_step=PIP_STEP,
                            prefix=BOT_LINE_PREFIX,
                        )
                        drawn_levels[obj.name] = obj.price1

            prev_trader_names = current_names
            print_objects(trader_objects, len(
                auto_objects), current_price, file_age)
            time.sleep(SCAN_INTERVAL_SEC)

    except KeyboardInterrupt:
        log.info("Stopped by user.")
        log.info("Clearing bot level lines…")
        clear_level_lines(prefix=BOT_LINE_PREFIX)
    finally:
        mt5.shutdown()
        log.info("MT5 connection closed.")


if __name__ == "__main__":
    main()
