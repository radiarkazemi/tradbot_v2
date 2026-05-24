"""
install_ea.py — Copies mt5/ObjectExporter.mq5 to the correct MT5 Experts folder.
Run once, then compile in MetaEditor (F7).
"""
import os, shutil
import MetaTrader5 as mt5

print("\n" + "="*60)
print("  TraderBot v1 — EA Installer")
print("="*60)

if not mt5.initialize():
    print("❌ MT5 not running. Open MT5 first.")
    exit(1)

info = mt5.terminal_info()
mt5.shutdown()

if not info or not info.data_path:
    print("❌ Could not get MT5 data path.")
    exit(1)

experts_folder = os.path.join(info.data_path, "MQL5", "Experts")
print(f"\n📁 Experts folder:\n   {experts_folder}")

script_dir = os.path.dirname(os.path.abspath(__file__))
src = os.path.join(script_dir, "mt5", "ObjectExporter.mq5")

if not os.path.exists(src):
    print(f"\n❌ mt5/ObjectExporter.mq5 not found next to this script.")
    exit(1)

dst = os.path.join(experts_folder, "ObjectExporter.mq5")
shutil.copy2(src, dst)
print(f"\n✅ Copied to:\n   {dst}")

print(f"""
NEXT STEPS:
  1. Press F4 in MT5 to open MetaEditor
  2. Open ObjectExporter.mq5 from the Experts folder above
  3. Press F7 to compile  (should say "0 errors")
  4. Back in MT5 Navigator → right-click Expert Advisors → Refresh
  5. Drag ObjectExporter onto your chart → click OK
  6. Make sure Algo Trading button is GREEN in toolbar
  7. Run:  python gui.py
""")