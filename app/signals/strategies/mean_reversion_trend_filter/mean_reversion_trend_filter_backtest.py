"""
Backtest wrapper for the Mean Reversion + Trend Filter strategy.

Strategy: Trades pullbacks to EMA 50 in the direction of the 4H trend (price vs EMA 200).
Entries triggered by candle patterns (engulfing, hammer/shooting star).
Exits based on ATR-sized stops and targets.
"""
from backtesting import Strategy
from backtesting import Backtest
import multiprocessing as mp
import pandas as pd

if mp.get_start_method(allow_none=True) != 'fork':
    mp.set_start_method('fork', force=True)

# Module-level data container (will be set before backtest runs)
_dftest = None
_strategy_parameters = None


def SIGNAL():
    """Return the TotalSignal column from the test DataFrame."""
    return _dftest.TotalSignal


def resample_to_1h(df: pd.DataFrame) -> pd.DataFrame:
    """
    Resample input data to 1H timeframe if needed.
    The strategy is designed for 1H data but can work with resampled data.

    Args:
        df: DataFrame with OHLCV data (any timeframe)

    Returns:
        1H resampled DataFrame
    """
    # Check if we need to resample (look at index frequency or data span)
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)

    # Calculate the median time difference between candles
    if len(df) > 1:
        time_diffs = df.index.to_series().diff().dropna()
        median_diff = time_diffs.median()

        # If median diff is less than 1 hour, resample to 1H
        if median_diff < pd.Timedelta(hours=1):
            return df.resample('1h').agg({
                'Open': 'first',
                'High': 'max',
                'Low': 'min',
                'Close': 'last',
                'Volume': 'sum'
            }).dropna()

    return df


class MeanReversionTrendFilterStrat(Strategy):
    """
    Mean Reversion + Trend Filter Strategy

    Trades pullbacks to the 50 EMA in the direction of the higher timeframe trend.

    Entry Rules (Long):
    - Entry timeframe price > EMA 100 (PRIMARY trend filter - fastest reaction)
    - 4H price > EMA 100 OR 4H not in strong downtrend (secondary confirmation)
    - Entry timeframe NOT showing downtrend momentum (not far below EMA 50, EMA 50 not falling)
    - No recent 4H trend change (20 bar cooldown after EMA 100 cross)
    - Price within 1.0×ATR of 50 EMA (pullback zone)
    - RSI between 30-50 (oversold zone)
    - Price >= VWAP
    - Bullish engulfing/hammer pattern (strong) OR 2 consecutive bullish candles (standard)
    - ATR not in top 5% (avoid extreme volatility spikes)

    Entry Rules (Short):
    - Entry timeframe price < EMA 100 (PRIMARY trend filter - fastest reaction)
    - 4H price < EMA 100 OR 4H not in strong uptrend (secondary confirmation)
    - Entry timeframe NOT showing uptrend momentum (not far above EMA 50, EMA 50 not rising)
    - No recent 4H trend change (20 bar cooldown after EMA 100 cross)
    - Price within 1.0×ATR of 50 EMA (pullback zone)
    - RSI between 50-70 (overbought zone)
    - Price <= VWAP
    - Bearish engulfing/shooting star pattern (strong) OR 2 consecutive bearish candles (standard)
    - ATR not in top 5% (avoid extreme volatility spikes)

    Exit Rules:
    - Stop Loss: slcoef × ATR from entry (default 4.0× ATR)
    - Take Profit: slcoef × tpratio × ATR from entry (default 3.5 ratio = 14× ATR)
    - Early Exit: RSI >= 70 for longs, RSI <= 30 for shorts
    - Cooldown: 5 bars before re-entry after exit
    """
    mysize = 0.01  # 1% of account
    slcoef = 4.0  # Stop loss coefficient (4.0 × ATR)
    tpratio = 3.5  # Take profit ratio (SL × 3.5)
    trades_actions = []
    cooldown_period = 5  # bars to wait after exit before new entry

    def init(self):
        super().init()
        self.signal1 = self.I(SIGNAL)
        self.bars_since_exit = 100  # Initialize high to allow first trade

    def next(self):
        super().next()

        # Track cooldown counter
        had_trades = len(self.trades) > 0
        if had_trades:
            self.bars_since_exit = 0
        else:
            self.bars_since_exit += 1

        # Early exit based on RSI (exit early if mean reversion complete)
        for trade in self.trades:
            if trade.is_long and self.data.RSI[-1] >= 70:
                trade.close()
            elif trade.is_short and self.data.RSI[-1] <= 30:
                trade.close()

        # Get current ATR value for SL/TP calculation
        slatr = self.slcoef * self.data.ATR[-1]

        # Entry conditions based on TotalSignal
        # Check cooldown period before allowing new entry
        if self.signal1 == 2 and len(self.trades) == 0 and self.bars_since_exit >= self.cooldown_period:
            # Buy signal - long setup
            sl1 = self.data.Close[-1] - slatr
            tp1 = self.data.Close[-1] + (slatr * self.tpratio)

            self.buy(sl=sl1, tp=tp1, size=self.mysize)
            self.bars_since_exit = 0  # Reset after entry

            # Record trade action
            if _strategy_parameters and _strategy_parameters.get('best', False):
                self.trades_actions.append({
                    "datetime": self.data.index[-1].strftime('%Y-%m-%d %H:%M:%S.%f'),
                    "trade_action": "buy",
                    "entry_price": self.data.Close[-1],
                    "price": self.data.Close[-1],
                    "sl": sl1,
                    "tp": tp1,
                    "size": self.mysize,
                })

        elif self.signal1 == 1 and len(self.trades) == 0 and self.bars_since_exit >= self.cooldown_period:
            # Sell signal - short setup
            sl1 = self.data.Close[-1] + slatr
            tp1 = self.data.Close[-1] - (slatr * self.tpratio)

            self.sell(sl=sl1, tp=tp1, size=self.mysize)
            self.bars_since_exit = 0  # Reset after entry

            # Record trade action
            if _strategy_parameters and _strategy_parameters.get('best', False):
                self.trades_actions.append({
                    "datetime": self.data.index[-1].strftime('%Y-%m-%d %H:%M:%S.%f'),
                    "trade_action": "sell",
                    "entry_price": self.data.Close[-1],
                    "price": self.data.Close[-1],
                    "sl": sl1,
                    "tp": tp1,
                    "size": self.mysize,
                })


def backtest(df, strategy_parameters, size=0.01, skip_optimization=False, best_params=None):
    """
    Run backtest for the mean reversion + trend filter strategy.

    This function matches the standard signature used by all strategy backtests.

    Args:
        df: DataFrame with OHLCV data and TotalSignal column (signals already calculated)
        strategy_parameters: Dict of strategy parameters
        size: Position size (default 0.01 = 1%)
        skip_optimization: If True, use best_params instead of optimizing
        best_params: Pre-optimized parameters dict with 'slcoef' and 'tpratio'

    Returns:
        Tuple of (backtest_object, stats, trades_actions, strategy_parameters)
    """
    global _dftest, _strategy_parameters

    # Validate input data
    if df is None or df.empty:
        print("mean_reversion_trend_filter backtest: df is None or empty")
        return None, None, [], {}

    dftest = df.copy()
    _dftest = dftest
    _strategy_parameters = strategy_parameters

    # Default backtest parameters
    margin = 1/500
    cash = 100000
    lot_size = size

    # Set initial class attributes from parameters
    MeanReversionTrendFilterStrat.mysize = lot_size
    MeanReversionTrendFilterStrat.slcoef = strategy_parameters.get("slcoef", 4.0)
    MeanReversionTrendFilterStrat.tpratio = strategy_parameters.get("tpratio", 3.5)
    MeanReversionTrendFilterStrat.trades_actions = []

    # Do optimization if skip_optimization is False
    if not skip_optimization:
        print("Optimizing mean_reversion_trend_filter...")
        bt = Backtest(dftest, MeanReversionTrendFilterStrat, cash=cash, margin=margin, finalize_trades=True)

        stats, heatmap = bt.optimize(
            slcoef=[i / 10 for i in range(30, 71, 3)],  # 3.0 to 7.0
            tpratio=[i / 10 for i in range(25, 51, 3)],  # 2.5 to 5.0
            maximize="Sharpe Ratio",
            max_tries=300,
            random_state=0,
            return_heatmap=True,
        )

        # Convert multiindex series to dataframe
        heatmap_df = heatmap.unstack()

        # Find the maximum value over the entire DataFrame
        max_value = heatmap_df.max().max()

        # Find the index of the maximum value
        optimized_params = (heatmap_df == max_value).stack().idxmax()

        best_params = {
            'slcoef': optimized_params[0],
            'tpratio': optimized_params[1]
        }

        print(best_params)
    else:
        # Use provided best_params or defaults
        if best_params is None:
            best_params = {
                'slcoef': 4.0,
                'tpratio': 3.5
            }
        print("Optimization is skipped, using params:", best_params)

    strategy_parameters = {
        "best": True,
        "slcoef": best_params['slcoef'],
        "tpratio": best_params['tpratio']
    }

    print(strategy_parameters)

    MeanReversionTrendFilterStrat.slcoef = strategy_parameters["slcoef"]
    MeanReversionTrendFilterStrat.tpratio = strategy_parameters["tpratio"]

    # Update the global _strategy_parameters with the final values
    _strategy_parameters = strategy_parameters

    bt_best = Backtest(dftest, MeanReversionTrendFilterStrat, cash=cash, margin=margin, finalize_trades=True)
    stats = bt_best.run()
    trades_actions = bt_best._strategy.trades_actions

    return bt_best, stats, trades_actions, strategy_parameters
