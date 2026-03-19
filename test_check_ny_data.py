"""
Check if NY test data is being set correctly.
"""

import pandas as pd

# Create the same date range as the test
dates = pd.date_range(start='2025-03-18 07:00:00', end='2025-03-18 17:00:00', freq='5min', tz='UTC')
df = pd.DataFrame({
    'Open': [1.0850] * len(dates),
    'High': [1.0860] * len(dates),
    'Low': [1.0840] * len(dates),
    'Close': [1.0855] * len(dates),
}, index=dates)

# Try to set the NY OR breakout values
print("Setting NY OR at 13:35...")
try:
    df.loc['2025-03-18 13:35:00', 'Open'] = 1.0870
    df.loc['2025-03-18 13:35:00', 'High'] = 1.0880
    df.loc['2025-03-18 13:35:00', 'Low'] = 1.0865
    df.loc['2025-03-18 13:35:00', 'Close'] = 1.0875
    print("✓ NY OR set successfully")

    # Check if it was actually set
    ny_or = df.loc['2025-03-18 13:35:00']
    print(f"NY OR values: Open={ny_or['Open']}, High={ny_or['High']}, Low={ny_or['Low']}, Close={ny_or['Close']}")

    # Calculate OR size
    or_size_pips = (ny_or['High'] - ny_or['Low']) / 0.0001
    print(f"OR size: {or_size_pips} pips")

    # Calculate the breakout candle values
    df.loc['2025-03-18 13:40:00', 'Open'] = 1.0876
    df.loc['2025-03-18 13:40:00', 'High'] = 1.0892
    df.loc['2025-03-18 13:40:00', 'Low'] = 1.0875
    df.loc['2025-03-18 13:40:00', 'Close'] = 1.0890
    print("✓ NY breakout candle set successfully")

    # Check if it was actually set
    ny_bo = df.loc['2025-03-18 13:40:00']
    print(f"NY breakout values: Open={ny_bo['Open']}, High={ny_bo['High']}, Low={ny_bo['Low']}, Close={ny_bo['Close']}")

    # Check if close is above OR high
    print(f"Breakout check: Close ({ny_bo['Close']}) > OR_High ({ny_or['High']})? {ny_bo['Close'] > ny_or['High']}")

    # Calculate wick and body
    body = abs(ny_bo['Close'] - ny_bo['Open'])
    upper_wick = ny_bo['High'] - ny_bo['Close']
    lower_wick = ny_bo['Open'] - ny_bo['Low']
    print(f"Body: {body}, Upper wick: {upper_wick}, Lower wick: {lower_wick}")
    print(f"Wick filter: Upper wick ({upper_wick}) > Body ({body})? {upper_wick > body}")

except KeyError as e:
    print(f"✗ KeyError: {e}")
    print("\nAvailable timestamps around that time:")
    nearby = df.loc[(df.index >= '2025-03-18 13:30:00') & (df.index <= '2025-03-18 13:50:00')]
    print(nearby.index.tolist())
