"""
Debug script to check session window detection for London and NY.
"""

import sys
import pandas as pd
import importlib
from datetime import time

# Import ORB utils using importlib due to numeric module name
orb_utils_module = importlib.import_module("app.signals.strategies.5_min_orb.orb_utils")
convert_utc_to_session_time = orb_utils_module.convert_utc_to_session_time
detect_session_window = orb_utils_module.detect_session_window

# Test specific times
test_times = [
    '2025-03-18 08:00:00+00:00',  # London open
    '2025-03-18 08:05:00+00:00',  # London active
    '2025-03-18 12:00:00+00:00',  # Mid-day
    '2025-03-18 13:30:00+00:00',  # NY open
    '2025-03-18 13:35:00+00:00',  # NY active
    '2025-03-18 14:00:00+00:00',  # Both active?
]

print("Session Window Detection Test")
print("=" * 80)

for time_str in test_times:
    dt = pd.Timestamp(time_str)
    print(f"\nUTC Time: {dt}")

    for session in ['london', 'ny']:
        local_time = convert_utc_to_session_time(dt, session)
        window = detect_session_window(dt, session)
        print(f"  {session:8s}: {local_time.strftime('%H:%M:%S')} local | Window: {window}")
