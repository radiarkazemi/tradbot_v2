# TraderBot v1

A trader-interactive MT5 bot. The trader draws objects on the MetaTrader 5 chart; the bot detects them, draws level lines around them, places pending orders, and can backtest the setup against historical data.

---

## Architecture

```
trader_bot_v2/
│
├── core/                         ← Business logic (no UI, no MT5 UI)
│   ├── __init__.py
│   ├── chart_watcher.py          ← Reads trader_objects.txt, detects drawn objects
│   ├── line_drawer.py            ← Writes trader_commands.txt → EA draws lines
│   ├── order_manager.py          ← Places / cancels MT5 pending orders
│   └── backtest_engine.py        ← Simulates orders on historical candle data
│
├── mt5/                          ← MQL5 files (install into MT5)
│   └── ObjectExporter.mq5        ← EA: exports chart objects + executes draw commands
│
├── gui.py                        ← PyQt5 desktop GUI (entry point)
├── config.py                     ← All settings (credentials, pip step, lot size)
├── requirements.txt
├── .gitignore
└── README.md
```

### Data Flow

```
Trader draws line
      │
      ▼
ObjectExporter.mq5 (EA on chart)
      │  writes every 2s
      ▼
trader_objects.txt  ────────────►  chart_watcher.py  ──►  GUI (live display)
                                          │
                                          ▼
                                   line_drawer.py
                                          │  writes commands
                                          ▼
                                   trader_commands.txt
                                          │
                                          ▼
                                   ObjectExporter.mq5
                                   (reads & draws lines)
                                          │
                                          ▼
                                    MT5 Chart  ◄── 6 level lines appear
```

---

## Quick Start

### 1. Prerequisites
- MetaTrader 5 (Windows)
- Python 3.11+
- Demo or live MT5 account

### 2. Install
```bash
pip install -r requirements.txt
```

### 3. Configure
Edit `config.py`:
```python
MT5_LOGIN    = 123456789
MT5_PASSWORD = "yourpassword"
MT5_SERVER   = "Broker-Demo"
WATCH_SYMBOL = "XAUUSD_i"
PIP_STEP     = 1.5        # distance between level lines in pips
LOT_SIZE     = 0.01
TP_RR_RATIO  = 2.0        # take profit = SL distance × 2
```

### 4. Install the MT5 EA
- Copy `mt5/ObjectExporter.mq5` to MT5 → `MQL5/Experts/`
- Open MetaEditor → compile (F7)
- Drag `ObjectExporter` onto your chart
- Enable Algo Trading (green button in toolbar)

### 5. Run
```bash
python gui.py
```

---

## Module Reference

| File | Responsibility |
|---|---|
| `config.py` | All settings — credentials, pip step, lot size, magic number |
| `core/chart_watcher.py` | Parses `trader_objects.txt`, filters auto-drawn objects, detects new/removed/moved lines |
| `core/line_drawer.py` | Writes draw commands to `trader_commands.txt`; knows pip size per symbol |
| `core/order_manager.py` | Calculates buy-stop/sell-stop levels with mirrored SLs; sends orders to MT5 |
| `core/backtest_engine.py` | Fetches historical candles from MT5; simulates order triggers bar by bar |
| `mt5/ObjectExporter.mq5` | MQL5 EA: exports all chart objects to file; reads and executes draw commands |
| `gui.py` | PyQt5 GUI: watcher control, live levels table, orders tab, backtest tab |

---

## Order Logic

When the trader draws a horizontal line at price `P`, the bot places:

```
Above 3  (+3 × step)  →  BUY STOP   │  SL = Below 3  │  TP = entry + (SL dist × RR)
Above 2  (+2 × step)  →  BUY STOP   │  SL = Below 2
Above 1  (+1 × step)  →  BUY STOP   │  SL = Below 1
─────────────────── P (trader line) ───────────────────
Below 1  (-1 × step)  →  SELL STOP  │  SL = Above 1
Below 2  (-2 × step)  →  SELL STOP  │  SL = Above 2
Below 3  (-3 × step)  →  SELL STOP  │  SL = Above 3  │  TP = entry - (SL dist × RR)
```

SLs are **mirrored** across the source line — e.g. the buy-stop at Above 1 has its SL at Below 1, so the risk is always the full spread between the two levels.

---

## Roadmap

| Phase | Status | Description |
|---|---|---|
| 1 | ✅ Done | Detect trader-drawn horizontal lines and rectangles |
| 2 | ✅ Done | Auto-draw 3+3 level lines around the trader's line |
| 3 | ✅ Done | Place buy-stop / sell-stop orders with mirrored SLs |
| 4 | ✅ Done | Backtest orders on historical MT5 data |
| 5 | 🔜 Next | Interactive confirmation — bot asks trader before placing |
| 6 | 🔜 Later | Strategy selector (breakout, reversal, scalp modes) |
| 7 | 🔜 Later | Live P&L tracking and position management |