"""
Test ORB signal generation with both London and NY sessions.
This verifies the multi-session fix works correctly.
"""

import sys
import pandas as pd
import importlib

# Import ORB signals using importlib due to numeric module name
orb_signals_module = importlib.import_module("app.signals.strategies.5_min_orb.five_min_orb_signals")
five_min_orb_signals = orb_signals_module.five_min_orb_signals

# Create sample data covering both London and NY sessions
dates = pd.date_range(start='2025-03-18 07:00:00', end='2025-03-18 17:00:00', freq='5min', tz='UTC')
df = pd.DataFrame({
    'Open': [1.0850] * len(dates),
    'High': [1.0860] * len(dates),
    'Low': [1.0840] * len(dates),
    'Close': [1.0855] * len(dates),
}, index=dates)

# London OR breakout (08:05 UTC)
df.loc['2025-03-18 08:05:00', 'Open'] = 1.0850
df.loc['2025-03-18 08:05:00', 'High'] = 1.0860
df.loc['2025-03-18 08:05:00', 'Low'] = 1.0840
df.loc['2025-03-18 08:05:00', 'Close'] = 1.0855

df.loc['2025-03-18 08:10:00', 'Open'] = 1.0856
df.loc['2025-03-18 08:10:00', 'High'] = 1.0872
df.loc['2025-03-18 08:10:00', 'Low'] = 1.0855
df.loc['2025-03-18 08:10:00', 'Close'] = 1.0870  # London breakout

# NY OR breakout (13:35 UTC = 09:35 NY time)
# Create a larger OR to avoid chase threshold filter
df.loc['2025-03-18 13:35:00', 'Open'] = 1.0870
df.loc['2025-03-18 13:35:00', 'High'] = 1.0890  # Larger OR
df.loc['2025-03-18 13:35:00', 'Low'] = 1.0865
df.loc['2025-03-18 13:35:00', 'Close'] = 1.0875

# Small breakout to pass chase threshold (25 pips OR, can move up to 12.5 pips)
df.loc['2025-03-18 13:40:00', 'Open'] = 1.0876
df.loc['2025-03-18 13:40:00', 'High'] = 1.0900
df.loc['2025-03-18 13:40:00', 'Low'] = 1.0875
df.loc['2025-03-18 13:40:00', 'Close'] = 1.0898  # NY breakout (0.8 pips from OR high)

print("Testing with BOTH London and NY sessions")
print("=" * 60)

result = five_min_orb_signals(df, parameters={'ticker': 'EUR/USD', 'session': 'both'})

print("\n=== RESULTS ===")
print(f"Non-zero signals: {(result['TotalSignal'] != 0).sum()}")
print(f"Signals distribution:\n{result['TotalSignal'].value_counts()}")
print()

# Check which sessions the signals belong to
signal_candles = result[result['TotalSignal'] != 0]
if len(signal_candles) > 0:
    print("✓ SUCCESS: Signals were generated!")
    print(f"\nSignal details:")
    for idx, row in signal_candles.iterrows():
        print(f"  Time: {idx} | Signal: {row['TotalSignal']} ({'BUY' if row['TotalSignal'] == 2 else 'SELL'}) | Session: {row['OR_Session']}")

    # Verify we have signals for both sessions
    sessions_with_signals = signal_candles['OR_Session'].unique()
    print(f"\nSessions with signals: {list(sessions_with_signals)}")

    if len(sessions_with_signals) == 2:
        print("✓ PASS: Both London and NY sessions generated signals!")
        sys.exit(0)
    else:
        print(f"✗ FAIL: Expected signals from both sessions, got: {sessions_with_signals}")
        sys.exit(1)
else:
    print("✗ FAIL: No signals generated")
    sys.exit(1)
