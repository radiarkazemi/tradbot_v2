"""
╔══════════════════════════════════════════════════════════════════╗
║         TraderBot v1 — Configuration                            ║
╚══════════════════════════════════════════════════════════════════╝
"""

# ── MT5 CREDENTIALS ──────────────────────────────────────────────
MT5_LOGIN    = 52858180
MT5_PASSWORD = "@Radiar9841@"
MT5_SERVER   = "Alpari-MT5-Demo"

# ── SYMBOL TO WATCH ──────────────────────────────────────────────
WATCH_SYMBOL = "XAUUSD_i"

# ── SCAN SETTINGS ────────────────────────────────────────────────
SCAN_INTERVAL_SEC = 2

# ── LEVEL LINES ──────────────────────────────────────────────────
PIP_STEP       = 1.5     # distance between each level line in pips
BOT_LINE_PREFIX = "TB_"  # prefix for bot-drawn lines

# ── ORDER SETTINGS ───────────────────────────────────────────────
LOT_SIZE      = 0.01     # lot size per order
TP_RR_RATIO   = 2.0      # TP = SL distance × this ratio (e.g. 2.0 = 1:2 RR)
MAGIC_NUMBER  = 778899   # unique ID for this bot's orders

# ── OBJECT FILTERING ─────────────────────────────────────────────
AUTO_OBJECT_PREFIXES = [
    "PA_",       # GoldBot PA_Overlay indicator
    "CT",        # GoldBot candle-timer label
    "GB_",       # Other GoldBot objects
    "TB_",       # Our own bot-drawn level lines
    "autotrade", # MT5 trade history arrows
]

# ── LOGGING ──────────────────────────────────────────────────────
LOG_LEVEL = "INFO"