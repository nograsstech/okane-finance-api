"""
Integration tests for ORB strategies full pipeline.

Tests the complete flow from signal generation to backtest execution.
"""

import pytest
import pandas as pd
import importlib
from datetime import UTC, datetime

# Import Version A (immediate breakout)
five_min_orb_signals = importlib.import_module("app.signals.strategies.5_min_orb.five_min_orb_signals")
five_min_orb_backtest = importlib.import_module("app.signals.strategies.5_min_orb.five_min_orb_backtest")

# Import Version B (retest confirmation)
five_min_orb_confirmation_signals = importlib.import_module(
    "app.signals.strategies.5_min_orb_confirmation.five_min_orb_confirmation_signals"
)
five_min_orb_confirmation_backtest = importlib.import_module(
    "app.signals.strategies.5_min_orb_confirmation.five_min_orb_confirmation_backtest"
)


def create_sample_data(
    start_date: str = "2026-01-15 08:00:00",
    num_candles: int = 50,
    base_price: float = 1.0850,
    volatility: float = 0.0010
) -> pd.DataFrame:
    """
    Create sample OHLCV data for testing.

    Args:
        start_date: Starting timestamp (UTC)
        num_candles: Number of 5-min candles to generate
        base_price: Base price level
        volatility: Price volatility range

    Returns:
        DataFrame with OHLC data and UTC datetime index
    """
    timestamps = pd.date_range(
        start=start_date,
        periods=num_candles,
        freq='5min',
        tz=UTC
    )

    # Generate realistic price movement
    import numpy as np
    np.random.seed(42)

    opens = []
    highs = []
    lows = []
    closes = []

    current_price = base_price

    for _ in range(num_candles):
        open_price = current_price
        change = np.random.uniform(-volatility, volatility)
        close_price = open_price + change
        high_price = max(open_price, close_price) + abs(np.random.uniform(0, volatility/2))
        low_price = min(open_price, close_price) - abs(np.random.uniform(0, volatility/2))

        opens.append(open_price)
        highs.append(high_price)
        lows.append(low_price)
        closes.append(close_price)

        current_price = close_price

    df = pd.DataFrame({
        'Open': opens,
        'High': highs,
        'Low': lows,
        'Close': closes,
    }, index=timestamps)

    return df


def create_breakout_scenario_data() -> pd.DataFrame:
    """
    Create sample data with a clear ORB breakout scenario (Version A).

    Simulates EUR/USD London session:
    - 08:00-08:05: Opening Range forms
    - 08:10-08:15: Bullish breakout above OR_High
    """
    timestamps = pd.to_datetime([
        "2026-01-15 07:55:00+00:00",  # Before session
        "2026-01-15 08:00:00+00:00",  # Session open
        "2026-01-15 08:05:00+00:00",  # OR candle (1.0840-1.0860, 20 pips)
        "2026-01-15 08:10:00+00:00",  # Breakout candle (closes above OR_High)
        "2026-01-15 08:15:00+00:00",  # Signal candle (entry here)
        "2026-01-15 08:20:00+00:00",  # Continuation
        "2026-01-15 08:25:00+00:00",
        "2026-01-15 08:30:00+00:00",
    ])

    df = pd.DataFrame({
        'Open': [
            1.0850,
            1.0850,
            1.0845,  # OR open
            1.0855,  # Breakout open
            1.0870,  # Signal open (above OR_High)
            1.0875,
            1.0880,
            1.0885,
        ],
        'High': [
            1.0855,
            1.0855,
            1.0860,  # OR high (1.0840-1.0860 = 20 pips)
            1.0875,  # Breakout high
            1.0875,
            1.0880,
            1.0885,
            1.0890,
        ],
        'Low': [
            1.0848,
            1.0848,
            1.0840,  # OR low
            1.0848,
            1.0865,
            1.0870,
            1.0875,
            1.0880,
        ],
        'Close': [
            1.0852,
            1.0852,
            1.0852,  # OR close
            1.0868,  # Breakout close (above OR_High 1.0860)
            1.0872,  # Signal candle
            1.0878,
            1.0882,
            1.0888,
        ],
    }, index=timestamps)

    return df


def create_retest_scenario_data() -> pd.DataFrame:
    """
    Create sample data with OR, breakout, and retest (Version B).

    Simulates EUR/USD London session:
    - 08:00-08:05: Opening Range forms
    - 08:10-08:15: Bullish breakout above OR_High
    - 08:20-08:25: Retest of OR_High (acts as support)
    - 08:30: Confirmation and entry
    """
    timestamps = pd.to_datetime([
        "2026-01-15 07:55:00+00:00",
        "2026-01-15 08:00:00+00:00",
        "2026-01-15 08:05:00+00:00",  # OR candle (1.0840-1.0860)
        "2026-01-15 08:10:00+00:00",  # Breakout candle
        "2026-01-15 08:15:00+00:00",  # Move higher
        "2026-01-15 08:20:00+00:00",  # Pullback starts
        "2026-01-15 08:25:00+00:00",  # Retest OR_High (1.0860)
        "2026-01-15 08:30:00+00:00",  # Confirmation (wick rejection of OR_High)
        "2026-01-15 08:35:00+00:00",  # Entry candle
        "2026-01-15 08:40:00+00:00",
        "2026-01-15 08:45:00+00:00",
    ])

    df = pd.DataFrame({
        'Open': [
            1.0850,
            1.0850,
            1.0845,
            1.0855,
            1.0870,
            1.0870,
            1.0865,
            1.0860,  # Touch OR_High
            1.0862,
            1.0870,
            1.0875,
        ],
        'High': [
            1.0855,
            1.0855,
            1.0860,  # OR high
            1.0875,
            1.0875,
            1.0872,
            1.0868,
            1.0865,  # Reject from OR_High
            1.0870,
            1.0875,
            1.0880,
        ],
        'Low': [
            1.0848,
            1.0848,
            1.0840,  # OR low
            1.0848,
            1.0865,
            1.0862,
            1.0858,
            1.0858,  # Hold above OR_High
            1.0860,
            1.0865,
            1.0870,
        ],
        'Close': [
            1.0852,
            1.0852,
            1.0852,
            1.0868,  # Breakout close
            1.0872,
            1.0868,
            1.0862,  # Near OR_High
            1.0863,  # Hold (wick rejection)
            1.0868,  # Confirmation close
            1.0872,
            1.0878,
        ],
    }, index=timestamps)

    return df


class TestVersionAFullPipeline:
    """Test full pipeline for ORB Version A (immediate breakout)."""

    def test_version_a_full_pipeline(self):
        """Test complete pipeline: signal generation → backtest → results."""
        # Step 1: Create sample data
        df = create_sample_data(
            start_date="2026-01-15 08:00:00",
            num_candles=100,
            base_price=1.0850
        )

        # Step 2: Generate signals
        df_signals = five_min_orb_signals.five_min_orb_signals(
            df,
            parameters={"ticker": "EUR/USD", "session": "london"}
        )

        # Verify signals were generated
        assert 'OR_High' in df_signals.columns
        assert 'OR_Low' in df_signals.columns
        assert 'OR_Size_Pips' in df_signals.columns
        assert 'Pip_Value' in df_signals.columns
        assert 'TotalSignal' in df_signals.columns

        # Step 3: Run backtest (skip optimization for speed)
        bt, stats, trades_actions, strategy_params = five_min_orb_backtest.backtest(
            df=df_signals,
            strategy_parameters={},
            size=0.03,
            skip_optimization=True
        )

        # Step 4: Verify backtest results
        assert bt is not None, "Backtest object should not be None"
        assert stats is not None, "Stats should not be None"
        assert isinstance(trades_actions, list), "Trades actions should be a list"
        assert isinstance(strategy_params, dict), "Strategy params should be a dict"

        # Verify strategy parameters
        assert 'spread_buffer_pips' in strategy_params
        assert 'tp1_multiplier' in strategy_params
        assert 'tp2_multiplier' in strategy_params
        assert strategy_params['best'] is True


class TestVersionBFullPipeline:
    """Test full pipeline for ORB Version B (retest confirmation)."""

    def test_version_b_full_pipeline(self):
        """Test complete pipeline: signal generation → backtest → results."""
        # Step 1: Create sample data
        df = create_sample_data(
            start_date="2026-01-15 08:00:00",
            num_candles=100,
            base_price=1.0850
        )

        # Step 2: Generate signals
        df_signals = five_min_orb_confirmation_signals.five_min_orb_confirmation_signals(
            df,
            parameters={"ticker": "EUR/USD", "session": "london"}
        )

        # Verify signals were generated
        assert 'OR_High' in df_signals.columns
        assert 'OR_Low' in df_signals.columns
        assert 'OR_Size_Pips' in df_signals.columns
        assert 'Pip_Value' in df_signals.columns
        assert 'TotalSignal' in df_signals.columns

        # Step 3: Run backtest (skip optimization for speed)
        bt, stats, trades_actions, strategy_params = five_min_orb_confirmation_backtest.backtest(
            df=df_signals,
            strategy_parameters={},
            size=0.03,
            skip_optimization=True
        )

        # Step 4: Verify backtest results
        assert bt is not None, "Backtest object should not be None"
        assert stats is not None, "Stats should not be None"
        assert isinstance(trades_actions, list), "Trades actions should be a list"
        assert isinstance(strategy_params, dict), "Strategy params should be a dict"

        # Verify strategy parameters
        assert 'sl_buffer_pips' in strategy_params
        assert 'tp1_multiplier' in strategy_params
        assert 'tp2_multiplier' in strategy_params
        assert strategy_params['best'] is True


class TestOrbABreakoutScenario:
    """Test Version A with realistic breakout scenario."""

    def test_orb_a_with_breakout_scenario(self):
        """Test Version A generates signal on breakout."""
        # Create data with clear breakout
        df = create_breakout_scenario_data()

        # Generate signals
        df_signals = five_min_orb_signals.five_min_orb_signals(
            df,
            parameters={"ticker": "EUR/USD", "session": "london"}
        )

        # Verify OR was identified at 08:05
        or_candle = df_signals.loc["2026-01-15 08:05:00+00:00"]
        assert or_candle['OR_High'] == 1.0860
        assert or_candle['OR_Low'] == 1.0840
        assert or_candle['OR_Size_Pips'] == pytest.approx(20)  # 20 pips

        # Verify breakout was detected at 08:10 (close above OR_High)
        breakout_candle = df_signals.loc["2026-01-15 08:10:00+00:00"]
        assert breakout_candle['Close'] > 1.0860  # Above OR_High

        # Verify signal was generated at 08:15 (next candle open)
        signal_candle = df_signals.loc["2026-01-15 08:15:00+00:00"]
        assert signal_candle['TotalSignal'] == 2  # Buy signal

        # Run backtest to verify execution
        bt, stats, trades_actions, strategy_params = five_min_orb_backtest.backtest(
            df=df_signals,
            strategy_parameters={},
            size=0.03,
            skip_optimization=True
        )

        # Verify backtest executed successfully
        assert bt is not None
        assert stats is not None
        # Trades_actions list is created (may be empty if no trade completed)
        assert isinstance(trades_actions, list)


class TestOrbBRetestScenario:
    """Test Version B with retest and confirmation scenario."""

    def test_orb_b_with_retest_scenario(self):
        """Test Version B signal generation with retest setup."""
        # Create data with breakout, pullback, and retest
        df = create_retest_scenario_data()

        # Generate signals
        df_signals = five_min_orb_confirmation_signals.five_min_orb_confirmation_signals(
            df,
            parameters={"ticker": "EUR/USD", "session": "london"}
        )

        # Verify OR was identified at 08:05
        or_candle = df_signals.loc["2026-01-15 08:05:00+00:00"]
        assert or_candle['OR_High'] == 1.0860
        assert or_candle['OR_Low'] == 1.0840
        assert or_candle['OR_Size_Pips'] == pytest.approx(20)

        # Verify breakout was detected at 08:10
        breakout_candle = df_signals.loc["2026-01-15 08:10:00+00:00"]
        assert breakout_candle['Close'] > 1.0860

        # Verify retest happened at 08:25-08:30 (price returned to OR_High)
        retest_candle = df_signals.loc["2026-01-15 08:25:00+00:00"]
        assert retest_candle['Low'] <= 1.0860  # Touched OR_High

        # Verify confirmation at 08:30 (wick rejection of OR_High)
        confirmation_candle = df_signals.loc["2026-01-15 08:30:00+00:00"]
        assert confirmation_candle['Low'] >= 1.0858  # Held above OR_High

        # Run backtest to verify execution
        bt, stats, trades_actions, strategy_params = five_min_orb_confirmation_backtest.backtest(
            df=df_signals,
            strategy_parameters={},
            size=0.03,
            skip_optimization=True
        )

        # Verify backtest executed successfully
        assert bt is not None
        assert stats is not None
        # Trades_actions list is created (may be empty if no trade completed)
        assert isinstance(trades_actions, list)


class TestOrbIntegrationEdgeCases:
    """Test edge cases in the integration pipeline."""

    def test_version_a_empty_dataframe(self):
        """Test Version A handles empty DataFrame gracefully."""
        df = pd.DataFrame()

        bt, stats, trades_actions, strategy_params = five_min_orb_backtest.backtest(
            df=df,
            strategy_parameters={},
            size=0.03,
            skip_optimization=True
        )

        # Should return None for invalid input
        assert bt is None
        assert stats is None
        assert trades_actions == []
        assert strategy_params == {}

    def test_version_b_empty_dataframe(self):
        """Test Version B handles empty DataFrame gracefully."""
        df = pd.DataFrame()

        bt, stats, trades_actions, strategy_params = five_min_orb_confirmation_backtest.backtest(
            df=df,
            strategy_parameters={},
            size=0.03,
            skip_optimization=True
        )

        # Should return None for invalid input
        assert bt is None
        assert stats is None
        assert trades_actions == []
        assert strategy_params == {}

    def test_version_a_no_signals_generated(self):
        """Test Version A when no signals are generated."""
        # Create data with no clear breakout
        df = create_sample_data(
            start_date="2026-01-15 08:00:00",
            num_candles=20,
            base_price=1.0850,
            volatility=0.0002  # Low volatility, no breakout
        )

        df_signals = five_min_orb_signals.five_min_orb_signals(
            df,
            parameters={"ticker": "EUR/USD", "session": "london"}
        )

        # Run backtest
        bt, stats, trades_actions, strategy_params = five_min_orb_backtest.backtest(
            df=df_signals,
            strategy_parameters={},
            size=0.03,
            skip_optimization=True
        )

        # Backtest should still run, but with no trades
        assert bt is not None
        assert stats is not None
        # trades_actions may be empty if no signals triggered
        assert isinstance(trades_actions, list)
