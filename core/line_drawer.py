"""
line_drawer.py — Sends draw commands to MT5 via trader_commands.txt
The ObjectExporter EA reads this file and draws the lines on the chart.
"""
import sys, os as _os
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import os
import time
import MetaTrader5 as mt5
from typing import Optional

# ── MT5 color constants (BGR hex integers) ────────────────────────
# These are standard MQL5 color values
CLR_GOLD        = 0x00D7FF    # gold/yellow  — trader's own line
CLR_ABOVE_1     = 0x0080FF    # orange       — closest above
CLR_ABOVE_2     = 0x0050CC    # darker orange
CLR_ABOVE_3     = 0x003099    # darkest orange
CLR_BELOW_1     = 0x80FF00    # lime green   — closest below
CLR_BELOW_2     = 0x50CC00    # darker green
CLR_BELOW_3     = 0x309900    # darkest green

STYLE_SOLID = 0
STYLE_DASH  = 1
STYLE_DOT   = 2


def get_command_file_path(symbol: str = None) -> str:
    """Returns symbol-specific command file path."""
    appdata = os.environ.get("APPDATA", "")
    fname = f"trader_commands_{symbol}.txt" if symbol else "trader_commands.txt"
    return os.path.join(
        appdata, "MetaQuotes", "Terminal", "Common", "Files", fname
    )


def write_commands(commands: list, symbol: str = None):
    """Write command lines to file. Retries on PermissionError (EA may be reading)."""
    import time as _time
    path = get_command_file_path(symbol)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    for attempt in range(5):
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(commands) + "\n")
            return
        except PermissionError:
            _time.sleep(0.05)  # wait 50ms and retry


def get_pip_size(symbol: str) -> float:
    """Return pip size for any MT5 symbol. Selects symbol first so it works
    even if not in Market Watch."""
    mt5.symbol_select(symbol, True)
    info = mt5.symbol_info(symbol)
    if info is None:
        sym = symbol.upper()
        if "JPY" in sym:  return 0.01
        if "XAU" in sym:  return 0.10
        if "XAG" in sym:  return 0.01
        if any(x in sym for x in ["US30","NAS","DAX","FTSE","SPX","US500"]): return 1.0
        return 0.0001
    digits = info.digits
    point  = info.point
    if digits == 0: return 1.0
    if digits == 1: return 1.0
    return point * 10


def draw_level_lines(symbol: str, source_name: str, source_price: float,
                     pip_step: float = 1.5, prefix: str = "TB_"):
    """
    Draw 3 lines above and 3 lines below the trader's line.
    Each line is pip_step pips apart.
    Deletes any previous TB_ lines first.

    Colors:
      Above: orange shades  (closest → darkest)
      Below: green shades   (closest → darkest)
    """
    pip = get_pip_size(symbol)
    step = pip_step * pip

    above_colors = [CLR_ABOVE_1, CLR_ABOVE_2, CLR_ABOVE_3]
    below_colors = [CLR_BELOW_1, CLR_BELOW_2, CLR_BELOW_3]

    commands = []

    # Delete all previous TB_ lines first
    commands.append(f"DELETE_PREFIX|{prefix}")

    # Draw 3 lines ABOVE
    for i in range(1, 4):
        name  = f"{prefix}ABOVE_{i}_{source_name[:20]}"
        price = source_price + (step * i)
        clr   = above_colors[i - 1]
        # DRAW_HLINE|name|price|color|width|style
        commands.append(f"DRAW_HLINE|{name}|{price:.5f}|{clr}|1|{STYLE_DASH}")

    # Draw 3 lines BELOW
    for i in range(1, 4):
        name  = f"{prefix}BELOW_{i}_{source_name[:20]}"
        price = source_price - (step * i)
        clr   = below_colors[i - 1]
        commands.append(f"DRAW_HLINE|{name}|{price:.5f}|{clr}|1|{STYLE_DASH}")

    write_commands(commands)
    return step, commands


def clear_level_lines(prefix: str = "TB_"):
    """Remove all bot-drawn level lines from the chart."""
    write_commands([f"DELETE_PREFIX|{prefix}"])