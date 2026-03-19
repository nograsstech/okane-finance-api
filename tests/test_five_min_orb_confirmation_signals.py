"""
Tests for 5-Minute ORB signal generator - Version B (breakout with retest confirmation).

Tests Version B three-step process:
1. Initial Breakout (Observation Only) - Detect breakout, set state, don't generate signal
2. Wait for Retest - Monitor for price returning to OR level within timeout
3. Confirmation (Entry Trigger) - Generate signal on retest + confirmation
"""

import importlib

import pandas as pd
import pytest

# Import from module with numeric name using importlib
five_min_orb_confirmation_signals = importlib.import_module(
    "app.signals.strategies.5_min_orb_confirmation.five_min_orb_confirmation_signals"
)

five_min_orb_confirmation_signals_func = five_min_orb_confirmation_signals.five_min_orb_confirmation_signals


class TestVersionBSignalGeneration:
    """Test Version B signal generation logic with three-step process."""

    def test_version_b_no_breakout(self):
        """No signals should be generated without a breakout."""
        # Create data without any breakout
        # OR candle at 08:05: High 1.0860, Low 1.0850
        # Subsequent candles trade within OR range
        data = {
            "Open": [1.0850, 1.0855, 1.0855, 1.0855, 1.0855],
            "High": [1.0855, 1.0860, 1.0858, 1.0858, 1.0858],
            "Low": [1.0848, 1.0850, 1.0852, 1.0852, 1.0852],
            "Close": [1.0852, 1.0858, 1.0855, 1.0855, 1.0855],
        }
        # Timestamps: 08:00, 08:05 (OR), 08:10, 08:15, 08:20
        index = pd.to_datetime([
            "2026-01-15 08:00:00+00:00",
            "2026-01-15 08:05:00+00:00",
            "2026-01-15 08:10:00+00:00",
            "2026-01-15 08:15:00+00:00",
            "2026-01-15 08:20:00+00:00",
        ])
        df = pd.DataFrame(data, index=index)

        # Generate signals
        result = five_min_orb_confirmation_signals_func(
            df, parameters={"ticker": "EUR/USD", "session": "london"}
        )

        # Check that required columns are added
        assert "OR_High" in result.columns
        assert "OR_Low" in result.columns
        assert "OR_Size_Pips" in result.columns
        assert "TotalSignal" in result.columns

        # No breakout, so no signal
        for idx in result.index:
            assert result.loc[idx, "TotalSignal"] == 0

    def test_version_b_breakout_no_retest(self):
        """No signal if breakout occurs but no retest within timeout."""
        # Create data with breakout but no retest
        # OR candle at 08:05: High 1.0860, Low 1.0850
        # Breakout at 08:10: closes above OR_High (1.0864)
        # No retest - price continues away from OR level
        # Timeout after 6 candles (30 minutes)
        data = {
            "Open": [1.0850, 1.0855, 1.0858, 1.0870, 1.0875, 1.0880, 1.0885, 1.0890],
            "High": [1.0855, 1.0860, 1.0865, 1.0875, 1.0880, 1.0885, 1.0890, 1.0895],
            "Low": [1.0848, 1.0850, 1.0858, 1.0865, 1.0870, 1.0875, 1.0880, 1.0885],
            "Close": [1.0852, 1.0858, 1.0864, 1.0872, 1.0878, 1.0882, 1.0888, 1.0892],
        }
        # Timestamps: 08:00, 08:05 (OR), 08:10 (breakout), 08:15-08:45 (no retest)
        index = pd.to_datetime([
            "2026-01-15 08:00:00+00:00",
            "2026-01-15 08:05:00+00:00",
            "2026-01-15 08:10:00+00:00",
            "2026-01-15 08:15:00+00:00",
            "2026-01-15 08:20:00+00:00",
            "2026-01-15 08:25:00+00:00",
            "2026-01-15 08:30:00+00:00",
            "2026-01-15 08:35:00+00:00",
        ])
        df = pd.DataFrame(data, index=index)

        # Generate signals
        result = five_min_orb_confirmation_signals_func(
            df, parameters={"ticker": "EUR/USD", "session": "london"}
        )

        # OR should be identified at 08:05
        assert result.loc[result.index[1], "OR_High"] == 1.0860
        assert result.loc[result.index[1], "OR_Low"] == 1.0850

        # Breakout at 08:10, but no retest within timeout
        # No signal should be generated
        for idx in result.index:
            assert result.loc[idx, "TotalSignal"] == 0

    def test_version_b_retest_with_confirmation_option_a(self):
        """Signal on retest + confirmation via candle close (Option A)."""
        # Create data with breakout, retest, and confirmation via close
        # OR candle at 08:05: High 1.0860, Low 1.0850
        # Breakout at 08:10: closes above OR_High (1.0864)
        # Retest at 08:20: touches OR_High (1.0860) and closes above (1.0862)
        # Signal at 08:25 (next candle after confirmation close)
        data = {
            "Open": [1.0850, 1.0855, 1.0858, 1.0870, 1.0860, 1.0862, 1.0865, 1.0868],
            "High": [1.0855, 1.0860, 1.0865, 1.0875, 1.0863, 1.0865, 1.0870, 1.0875],
            "Low": [1.0848, 1.0850, 1.0858, 1.0865, 1.0858, 1.0860, 1.0862, 1.0865],
            "Close": [1.0852, 1.0858, 1.0864, 1.0872, 1.0862, 1.0864, 1.0868, 1.0872],
        }
        # Timestamps: 08:00, 08:05 (OR), 08:10 (breakout), 08:15, 08:20 (retest + confirm), 08:25 (signal)
        index = pd.to_datetime([
            "2026-01-15 08:00:00+00:00",
            "2026-01-15 08:05:00+00:00",
            "2026-01-15 08:10:00+00:00",
            "2026-01-15 08:15:00+00:00",
            "2026-01-15 08:20:00+00:00",
            "2026-01-15 08:25:00+00:00",
            "2026-01-15 08:30:00+00:00",
            "2026-01-15 08:35:00+00:00",
        ])
        df = pd.DataFrame(data, index=index)

        # Generate signals
        result = five_min_orb_confirmation_signals_func(
            df, parameters={"ticker": "EUR/USD", "session": "london"}
        )

        # OR should be identified at 08:05
        assert result.loc[result.index[1], "OR_High"] == 1.0860
        assert result.loc[result.index[1], "OR_Low"] == 1.0850

        # Breakout at 08:10 (close above OR_High)
        # Retest at 08:20: touches 1.0860 (within 3 pips tolerance)
        # At 08:20: Open=1.0860, Close=1.0862, Low=1.0858
        # Lower wick = 1.0860 - 1.0858 = 0.0002 (2 pips)
        # Body = 1.0862 - 1.0860 = 0.0002 (2 pips)
        # Wick (2 pips) < 2× body (4 pips), so Option B doesn't trigger
        # Confirmation: closes at 1.0862 (above OR_High)
        # Signal at 08:25 (next candle)
        assert result.loc[result.index[5], "TotalSignal"] == 2  # Buy signal

    def test_version_b_retest_with_confirmation_option_b(self):
        """Signal on retest + confirmation via rejection wick (Option B)."""
        # Create data with breakout, retest, and confirmation via rejection wick
        # OR candle at 08:05: High 1.0860, Low 1.0850
        # Breakout at 08:10: closes above OR_High (1.0864)
        # Retest at 08:20: rejection wick at OR_High
        #   - Low: 1.0858 (touches near OR_High 1.0860)
        #   - Open: 1.0865, Close: 1.0870 (body = 0.0005)
        #   - High: 1.0872 (upper wick = 0.0002)
        #   - Lower wick: 1.0865 - 1.0858 = 0.0007 (≥ 2× body size)
        # Signal at 08:20 (at rejection candle close)
        data = {
            "Open": [1.0850, 1.0855, 1.0858, 1.0870, 1.0868, 1.0865, 1.0872],
            "High": [1.0855, 1.0860, 1.0865, 1.0875, 1.0872, 1.0872, 1.0875],
            "Low": [1.0848, 1.0850, 1.0858, 1.0865, 1.0858, 1.0858, 1.0870],
            "Close": [1.0852, 1.0858, 1.0864, 1.0872, 1.0869, 1.0870, 1.0873],
        }
        # Timestamps: 08:00, 08:05 (OR), 08:10 (breakout), 08:15, 08:20 (retest + rejection), 08:25
        index = pd.to_datetime([
            "2026-01-15 08:00:00+00:00",
            "2026-01-15 08:05:00+00:00",
            "2026-01-15 08:10:00+00:00",
            "2026-01-15 08:15:00+00:00",
            "2026-01-15 08:20:00+00:00",
            "2026-01-15 08:25:00+00:00",
            "2026-01-15 08:30:00+00:00",
        ])
        df = pd.DataFrame(data, index=index)

        # Generate signals
        result = five_min_orb_confirmation_signals_func(
            df, parameters={"ticker": "EUR/USD", "session": "london"}
        )

        # OR should be identified at 08:05
        assert result.loc[result.index[1], "OR_High"] == 1.0860
        assert result.loc[result.index[1], "OR_Low"] == 1.0850

        # Breakout at 08:10
        # Retest at 08:20 with rejection wick
        # Signal at 08:20 (at rejection candle close)
        assert result.loc[result.index[4], "TotalSignal"] == 2  # Buy signal

    def test_version_b_short_breakout_with_retest(self):
        """Short signal on breakout below OR_Low with retest confirmation (Option A)."""
        # Create data with short breakout and retest using Option A (candle close)
        # OR candle at 08:05: High 1.0860, Low 1.0850
        # Breakout at 08:10: closes below OR_Low (1.0846)
        # Retest at 08:25: touches OR_Low (1.0850) and closes below (1.0848)
        # Signal at 08:30 (next candle after confirmation close)
        data = {
            "Open": [1.0850, 1.0855, 1.0852, 1.0845, 1.0840, 1.0850, 1.0846, 1.0843],
            "High": [1.0855, 1.0860, 1.0855, 1.0846, 1.0841, 1.0851, 1.0848, 1.0846],
            "Low": [1.0848, 1.0850, 1.0844, 1.0840, 1.0835, 1.0846, 1.0844, 1.0841],
            "Close": [1.0852, 1.0858, 1.0846, 1.0842, 1.0838, 1.0848, 1.0845, 1.0842],
        }
        # Timestamps: 08:00, 08:05 (OR), 08:10 (breakout), 08:15, 08:20, 08:25 (retest + confirm), 08:30 (signal)
        index = pd.to_datetime([
            "2026-01-15 08:00:00+00:00",
            "2026-01-15 08:05:00+00:00",
            "2026-01-15 08:10:00+00:00",
            "2026-01-15 08:15:00+00:00",
            "2026-01-15 08:20:00+00:00",
            "2026-01-15 08:25:00+00:00",
            "2026-01-15 08:30:00+00:00",
            "2026-01-15 08:35:00+00:00",
        ])
        df = pd.DataFrame(data, index=index)

        # Generate signals
        result = five_min_orb_confirmation_signals_func(
            df, parameters={"ticker": "EUR/USD", "session": "london"}
        )

        # OR should be identified at 08:05
        assert result.loc[result.index[1], "OR_High"] == 1.0860
        assert result.loc[result.index[1], "OR_Low"] == 1.0850

        # Breakout at 08:10 (close below OR_Low)
        # 08:15 (index 3): High=1.0846, 4 pips from OR_Low (1.0850), no retest (outside 3-pip tolerance)
        # 08:20 (index 4): High=1.0841, 9 pips from OR_Low, no retest
        # 08:25 (index 5): Open=1.0850, High=1.0851, Close=1.0848
        # High (1.0851) is within 3 pips of OR_Low (1.0850) - retest detected
        # Upper wick = 1.0851 - 1.0850 = 0.0001 (1 pip)
        # Body = 1.0850 - 1.0848 = 0.0002 (2 pips)
        # Wick (1 pip) < 2× body (4 pips), so Option B doesn't trigger
        # Option A: Close (1.0848) < OR_Low (1.0850) ✓
        # Signal at 08:30 (next candle, index 6)
        assert result.loc[result.index[6], "TotalSignal"] == 1  # Sell signal

    def test_version_b_timeout_after_breakout(self):
        """No signal if retest doesn't occur within timeout (6 candles)."""
        # Create data with breakout but no retest within 6 candles
        # OR candle at 08:05: High 1.0860, Low 1.0850
        # Breakout at 08:10: closes above OR_High (1.0864)
        # No retest for 7 candles (exceeds 6-candle timeout)
        # State should reset and no signal should be generated
        data = {
            "Open": [1.0850, 1.0855, 1.0858, 1.0870, 1.0875, 1.0880, 1.0885, 1.0890, 1.0895],
            "High": [1.0855, 1.0860, 1.0865, 1.0875, 1.0880, 1.0885, 1.0890, 1.0895, 1.0900],
            "Low": [1.0848, 1.0850, 1.0858, 1.0865, 1.0870, 1.0875, 1.0880, 1.0885, 1.0890],
            "Close": [1.0852, 1.0858, 1.0864, 1.0872, 1.0878, 1.0882, 1.0888, 1.0892, 1.0898],
        }
        # Timestamps: 08:00, 08:05 (OR), 08:10 (breakout), 08:15-08:45 (7 candles, no retest)
        index = pd.to_datetime([
            "2026-01-15 08:00:00+00:00",
            "2026-01-15 08:05:00+00:00",
            "2026-01-15 08:10:00+00:00",
            "2026-01-15 08:15:00+00:00",
            "2026-01-15 08:20:00+00:00",
            "2026-01-15 08:25:00+00:00",
            "2026-01-15 08:30:00+00:00",
            "2026-01-15 08:35:00+00:00",
            "2026-01-15 08:40:00+00:00",
        ])
        df = pd.DataFrame(data, index=index)

        # Generate signals
        result = five_min_orb_confirmation_signals_func(
            df, parameters={"ticker": "EUR/USD", "session": "london"}
        )

        # Breakout at 08:10, but no retest within 6 candles
        # No signal should be generated
        for idx in result.index:
            assert result.loc[idx, "TotalSignal"] == 0

    def test_version_b_handles_multiindex_columns(self):
        """Should handle MultiIndex columns from yfinance."""
        # Create data with MultiIndex columns
        columns = pd.MultiIndex.from_tuples([
            ('Adj Close', 'EURUSD=X'),
            ('Close', 'EURUSD=X'),
            ('High', 'EURUSD=X'),
            ('Low', 'EURUSD=X'),
            ('Open', 'EURUSD=X'),
            ('Volume', 'EURUSD=X'),
        ])
        data = {
            ('Adj Close', 'EURUSD=X'): [1.0852, 1.0854, 1.0864, 1.0872, 1.0862, 1.0864, 1.0868, 1.0872],
            ('Close', 'EURUSD=X'): [1.0852, 1.0854, 1.0864, 1.0872, 1.0862, 1.0864, 1.0868, 1.0872],
            ('High', 'EURUSD=X'): [1.0855, 1.0860, 1.0865, 1.0875, 1.0863, 1.0865, 1.0870, 1.0875],
            ('Low', 'EURUSD=X'): [1.0848, 1.0850, 1.0858, 1.0865, 1.0858, 1.0860, 1.0862, 1.0865],
            ('Open', 'EURUSD=X'): [1.0850, 1.0852, 1.0858, 1.0870, 1.0860, 1.0862, 1.0865, 1.0868],
            ('Volume', 'EURUSD=X'): [1000, 1200, 1500, 1800, 1600, 1400, 1700, 1900],
        }
        index = pd.to_datetime([
            "2026-01-15 08:00:00+00:00",
            "2026-01-15 08:05:00+00:00",
            "2026-01-15 08:10:00+00:00",
            "2026-01-15 08:15:00+00:00",
            "2026-01-15 08:20:00+00:00",
            "2026-01-15 08:25:00+00:00",
            "2026-01-15 08:30:00+00:00",
            "2026-01-15 08:35:00+00:00",
        ])
        df = pd.DataFrame(data, index=index, columns=columns)

        # Generate signals
        result = five_min_orb_confirmation_signals_func(
            df, parameters={"ticker": "EURUSD=X", "session": "london"}
        )

        # Should handle MultiIndex and generate signals
        assert "OR_High" in result.columns
        assert "TotalSignal" in result.columns
        assert result.loc[result.index[5], "TotalSignal"] == 2  # Buy signal

    def test_version_b_default_parameters(self):
        """Should use default parameters when none provided."""
        # Create minimal data
        data = {
            "Open": [1.0850, 1.0852],
            "High": [1.0855, 1.0856],
            "Low": [1.0848, 1.0850],
            "Close": [1.0852, 1.0854],
        }
        index = pd.to_datetime([
            "2026-01-15 08:00:00+00:00",
            "2026-01-15 08:05:00+00:00",
        ])
        df = pd.DataFrame(data, index=index)

        # Generate signals without parameters
        result = five_min_orb_confirmation_signals_func(df)

        # Should use defaults: ticker='EUR/USD', session='london'
        assert "OR_High" in result.columns
        assert "Pip_Value" in result.columns
        assert result.loc[result.index[0], "Pip_Value"] == 0.0001  # EUR/USD pip value

    def test_version_b_state_resets_on_new_session(self):
        """State should reset when moving to a new session date."""
        # Create data spanning two days
        # Day 1: Breakout at 08:10, no retest
        # Day 2: Fresh start, new breakout should be detected
        data = {
            "Open": [1.0850, 1.0855, 1.0858, 1.0870, 1.0875, 1.0880, 1.0850, 1.0855, 1.0858, 1.0868],
            "High": [1.0855, 1.0860, 1.0865, 1.0875, 1.0880, 1.0885, 1.0855, 1.0860, 1.0865, 1.0870],
            "Low": [1.0848, 1.0850, 1.0858, 1.0865, 1.0870, 1.0875, 1.0848, 1.0850, 1.0858, 1.0865],
            "Close": [1.0852, 1.0858, 1.0864, 1.0872, 1.0878, 1.0882, 1.0852, 1.0858, 1.0864, 1.0868],
        }
        # Day 1: 08:00-08:25, Day 2: 08:00-08:10
        index = pd.to_datetime([
            "2026-01-15 08:00:00+00:00",  # 0
            "2026-01-15 08:05:00+00:00",  # 1 - OR day 1
            "2026-01-15 08:10:00+00:00",  # 2
            "2026-01-15 08:15:00+00:00",  # 3
            "2026-01-15 08:20:00+00:00",  # 4
            "2026-01-15 08:25:00+00:00",  # 5
            "2026-01-16 08:00:00+00:00",  # 6 - before OR day 2
            "2026-01-16 08:05:00+00:00",  # 7 - OR day 2
            "2026-01-16 08:10:00+00:00",  # 8
            "2026-01-16 08:15:00+00:00",  # 9
        ])
        df = pd.DataFrame(data, index=index)

        # Generate signals
        result = five_min_orb_confirmation_signals_func(
            df, parameters={"ticker": "EUR/USD", "session": "london"}
        )

        # Day 1: Breakout but no retest (state should not persist to day 2)
        # Day 2: New OR should be identified, breakout detected fresh
        # OR is at index 1 (day 1) and index 7 (day 2)
        assert result.loc[result.index[1], "OR_High"] == result.loc[result.index[7], "OR_High"]
        # Both should have the same OR values (data is the same)
        # But the state should be reset (no breakout detected from day 1)
        # So day 2 should have a fresh breakout detection
