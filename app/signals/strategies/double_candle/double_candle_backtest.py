"""
Backtest wrapper for the double candle strategy.

Strategy: Buy on 2 consecutive green candles, sell on 2 consecutive red candles.
Position sizing: Dynamic based on ATR volatility.
"""
from backtesting import Strategy
from backtesting import Backtest
import multiprocessing as mp

if mp.get_start_method(allow_none=True) != 'fork':
    mp.set_start_method('fork', force=True)

# Module-level data container (will be set before backtest runs)
_dftest = None
_strategy_parameters = None


def SIGNAL():
    """Return the TotalSignal column from the test DataFrame."""
    return _dftest.TotalSignal


def POSITION_SIZE():
    """Return the dynamic position size from the test DataFrame."""
    return _dftest.position_size


class DoubleCandleStrat(Strategy):
    """
    Double Candle Strategy - trades based on consecutive candle patterns.

    Entry Rules:
    - Buy (Long): When 2 consecutive green candles appear
    - Sell (Short): When 2 consecutive red candles appear

    Exit Rules:
    - Stop Loss: Based on ATR * slcoef
    - Take Profit: Stop Loss * TPSLRatio

    Position Sizing (conservative for real-world usage):
    - Dynamic based on ATR volatility percentage
    - Lower volatility = larger position (up to 2%)
    - Higher volatility = smaller position (down to 0.5%)
    - Base size: 1% of account
    """
    base_size = 0.01
    slcoef = 1.5
    TPSLRatio = 2.0
    trades_actions = []

    def init(self):
        super().init()
        self.signal1 = self.I(SIGNAL)
        self.position_sizes = self.I(POSITION_SIZE)

    def next(self):
        super().next()

        # Get current ATR value and position size
        slatr = self.slcoef * self.data.volatility_atr[-1]
        TPSLRatio = self.TPSLRatio

        # Use dynamic position size if available, otherwise base size
        current_size = getattr(self, 'mysize', self.base_size)

        # Entry conditions based on TotalSignal
        # Only enter if no open positions (simple single-position strategy)
        if self.signal1 == 2 and len(self.trades) == 0:
            # Buy signal - 2 consecutive green candles
            sl1 = self.data.Close[-1] - slatr
            tp1 = self.data.Close[-1] + slatr * TPSLRatio

            # Use dynamic position size from indicator, or base size
            current_size = self.position_sizes[-1] if hasattr(self, 'position_sizes') else self.base_size

            self.buy(sl=sl1, tp=tp1, size=current_size)

            # Record trade action
            if _strategy_parameters and _strategy_parameters.get('best', False):
                self.trades_actions.append({
                    "datetime": self.data.index[-1].strftime('%Y-%m-%d %H:%M:%S.%f'),
                    "trade_action": "buy",
                    "entry_price": self.data.Close[-1],
                    "price": self.data.Close[-1],
                    "sl": sl1,
                    "tp": tp1,
                    "size": current_size,
                })

        elif self.signal1 == 1 and len(self.trades) == 0:
            # Sell signal - 2 consecutive red candles
            sl1 = self.data.Close[-1] + slatr
            tp1 = self.data.Close[-1] - slatr * TPSLRatio

            # Use dynamic position size from indicator, or base size
            current_size = self.position_sizes[-1] if hasattr(self, 'position_sizes') else self.base_size

            self.sell(sl=sl1, tp=tp1, size=current_size)

            # Record trade action
            if _strategy_parameters and _strategy_parameters.get('best', False):
                self.trades_actions.append({
                    "datetime": self.data.index[-1].strftime('%Y-%m-%d %H:%M:%S.%f'),
                    "trade_action": "sell",
                    "entry_price": self.data.Close[-1],
                    "price": self.data.Close[-1],
                    "sl": sl1,
                    "tp": tp1,
                    "size": current_size,
                })


def backtest(df, strategy_parameters, size=0.01, skip_optimization=False, best_params=None):
    """
    Run backtest for the double candle strategy.

    Args:
        df: DataFrame with OHLCV data and TotalSignal column
        strategy_parameters: Dict of strategy parameters
        size: Base position size (will be overridden by dynamic sizing)
        skip_optimization: If True, use best_params instead of optimizing
        best_params: Pre-optimized parameters dict

    Returns:
        Tuple of (backtest_object, stats, trades_actions, strategy_parameters)
    """
    global _dftest, _strategy_parameters

    # Validate input data
    if df is None or df.empty:
        print("double_candle backtest: df is None or empty")
        return None, None, [], {}

    dftest = df.copy()
    _dftest = dftest
    _strategy_parameters = strategy_parameters

    # Default backtest parameters
    margin = 1/500
    cash = 100000
    lot_size = size

    # Set initial class attributes from parameters
    DoubleCandleStrat.base_size = lot_size
    DoubleCandleStrat.slcoef = strategy_parameters.get("slcoef", 1.5)
    DoubleCandleStrat.TPSLRatio = strategy_parameters.get("tpslRatio", 2.0)
    DoubleCandleStrat.trades_actions = []

    # Do optimization if skip_optimization is False
    if not skip_optimization:
        print("Optimizing double_candle...")
        bt = Backtest(dftest, DoubleCandleStrat, cash=cash, margin=margin, finalize_trades=True)

        stats, heatmap = bt.optimize(
            slcoef=[i / 10 for i in range(10, 31, 2)],  # 1.0 to 3.0
            TPSLRatio=[i / 10 for i in range(15, 31, 2)],  # 1.5 to 3.0
            maximize="Win Rate [%]",
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
            'tpslRatio': optimized_params[1],
            'slcoef': optimized_params[0]
        }

        print(best_params)
    else:
        # Use provided best_params or defaults
        if best_params is None:
            best_params = {
                'tpslRatio': 2.0,
                'slcoef': 1.5
            }
        print("Optimization is skipped, using params:", best_params)

    strategy_parameters = {
        "best": True,
        "tpslRatio": best_params['tpslRatio'],
        "slcoef": best_params['slcoef']
    }

    print(strategy_parameters)

    DoubleCandleStrat.slcoef = strategy_parameters["slcoef"]
    DoubleCandleStrat.TPSLRatio = strategy_parameters["tpslRatio"]

    # Update the global _strategy_parameters with the final values
    _strategy_parameters = strategy_parameters

    bt_best = Backtest(dftest, DoubleCandleStrat, cash=cash, margin=margin, finalize_trades=True)
    stats = bt_best.run()
    trades_actions = bt_best._strategy.trades_actions

    return bt_best, stats, trades_actions, strategy_parameters
