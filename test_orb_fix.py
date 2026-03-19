"""
Quick test to verify ORB signal generation fix.
Run this to check if signals are being generated properly.
"""

import sys
import pandas as pd
import importlib

# Import ORB signals using importlib due to numeric module name
orb_signals_module = importlib.import_module("app.signals.strategies.5_min_orb.five_min_orb_signals")
five_min_orb_signals = orb_signals_module.five_min_orb_signals

# Create sample data for EUR/USD 5m interval
# This simulates a proper OR breakout scenario
dates = pd.date_range(start='2025-03-18 07:00:00', end='2025-03-18 16:00:00', freq='5min', tz='UTC')
df = pd.DataFrame({
    'Open': [1.0850] * len(dates),
    'High': [1.0860] * len(dates),
    'Low': [1.0840] * len(dates),
    'Close': [1.0855] * len(dates),
}, index=dates)

# Simulate a proper OR breakout
# The OR candle (08:05-08:10) has a small range
df.loc['2025-03-18 08:05:00', 'Open'] = 1.0850
df.loc['2025-03-18 08:05:00', 'High'] = 1.0860  # OR High
df.loc['2025-03-18 08:05:00', 'Low'] = 1.0840   # OR Low
df.loc['2025-03-18 08:05:00', 'Close'] = 1.0855

# Next candle (08:10-08:15) breaks out above OR with strong close
df.loc['2025-03-18 08:10:00', 'Open'] = 1.0856
df.loc['2025-03-18 08:10:00', 'High'] = 1.0872
df.loc['2025-03-18 08:10:00', 'Low'] = 1.0855
df.loc['2025-03-18 08:10:00', 'Close'] = 1.0870  # Strong close, minimal wick

print("Input DataFrame shape:", df.shape)
print("Date range:", df.index[0], "to", df.index[-1])
print()

# Test with London session
result = five_min_orb_signals(df, parameters={'ticker': 'EUR/USD', 'session': 'london'})

print("\n=== RESULTS ===")
print("Output DataFrame shape:", result.shape)
print("Non-zero signals:", (result['TotalSignal'] != 0).sum())
print("Signals distribution:")
print(result['TotalSignal'].value_counts())
print()

# Check if OR values were set
has_or_values = (result['OR_High'].notna()).sum()
print(f"Candles with OR values: {has_or_values}")

# Check for session labels
has_session = (result['OR_Session'].notna()).sum()
print(f"Candles with session labels: {has_session}")

# Check if any signals were generated
if (result['TotalSignal'] != 0).any():
    print("\n✓ SUCCESS: Signals were generated!")
    signal_times = result[result['TotalSignal'] != 0].index
    print(f"Signal times: {signal_times}")
else:
    print("\n✗ FAIL: No signals generated")
    print("\nDebug info:")
    print(f"  OR_High is null: {(result['OR_High'].isna()).all()}")
    print(f"  OR_Low is null: {(result['OR_Low'].isna()).all()}")
    print(f"  OR_Size_Pips is null: {(result['OR_Size_Pips'].isna()).all()}")

sys.exit(0 if (result['TotalSignal'] != 0).any() else 1)
