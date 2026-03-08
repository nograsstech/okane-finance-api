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


class EMABollingerLowRiskStrat(Strategy):
    """EMA Bollinger Bands low risk strategy with RSI exit conditions."""
    mysize = 0.03
    slcoef = 2.0
    TPSLRatio = 2.0
    trades_actions = []

    def init(self):
        super().init()
        self.signal1 = self.I(SIGNAL)

    def next(self):
        super().next()
        slatr = self.slcoef * self.data.ATR[-1]
        TPSLRatio = self.TPSLRatio

        # Exit conditions based on RSI
        for trade in self.trades:
            if trade.is_long and self.data.RSI[-1] >= 80:
                trade.close()
                if _strategy_parameters and _strategy_parameters.get('best', False):
                    self.trades_actions.append({
                        "datetime": self.data.index[-1].strftime('%Y-%m-%d %H:%M:%S.%f'),
                        "trade_action": "close",
                        "entry_price": trade.entry_price,
                        "price": self.data.Close[-1],
                        "sl": None,
                        "tp": None,
                        "size": self.mysize,
                    })

            elif trade.is_short and self.data.RSI[-1] <= 20:
                trade.close()
                if _strategy_parameters and _strategy_parameters.get('best', False):
                    self.trades_actions.append({
                        "datetime": self.data.index[-1].strftime('%Y-%m-%d %H:%M:%S.%f'),
                        "trade_action": "close",
                        "entry_price": trade.entry_price,
                        "price": self.data.Close[-1],
                        "sl": None,
                        "tp": None,
                        "size": self.mysize,
                    })

        # Entry conditions
        if self.signal1 == 2 and len(self.trades) == 0:
            sl1 = self.data.Close[-1] - slatr
            tp1 = self.data.Close[-1] + slatr * TPSLRatio
            self.buy(sl=sl1, tp=tp1, size=self.mysize)

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

        elif self.signal1 == 1 and len(self.trades) == 0:
            sl1 = self.data.Close[-1] + slatr
            tp1 = self.data.Close[-1] - slatr * TPSLRatio
            self.sell(sl=sl1, tp=tp1, size=self.mysize)

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


def backtest(df, strategy_parameters, size=0.03, skip_optimization=False, best_params=None):
    """
    Run backtest for the EMA Bollinger low risk strategy.

    Args:
        df: DataFrame with OHLCV data and TotalSignal column
        strategy_parameters: Dict of strategy parameters
        size: Position size
        skip_optimization: If True, use best_params instead of optimizing
        best_params: Pre-optimized parameters dict

    Returns:
        Tuple of (backtest_object, stats, trades_actions, strategy_parameters)
    """
    global _dftest, _strategy_parameters

    # Validate input data
    if df is None or df.empty:
        print("ema_bollinger_1_low_risk backtest: df is None or empty")
        return None, None, [], {}

    dftest = df.copy()
    _dftest = dftest
    _strategy_parameters = strategy_parameters

    # Default backtest parameters
    margin = 1/500
    cash = 100000
    lot_size = size

    # Set initial class attributes from parameters
    EMABollingerLowRiskStrat.mysize = lot_size
    EMABollingerLowRiskStrat.slcoef = strategy_parameters.get("slcoef", 2.0)
    EMABollingerLowRiskStrat.TPSLRatio = strategy_parameters.get("tpslRatio", 2.0)
    EMABollingerLowRiskStrat.trades_actions = []

    # Do optimization if skip_optimization is False
    if not skip_optimization:
        print("Optimizing ema_bollinger_1_low_risk...")
        bt = Backtest(dftest, EMABollingerLowRiskStrat, cash=cash, margin=margin, finalize_trades=True)

        stats, heatmap = bt.optimize(
            slcoef=[i / 10 for i in range(10, 41, 2)],
            TPSLRatio=[i / 10 for i in range(10, 31, 2)],
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
            'tpslRatio': optimized_params[1],
            'slcoef': optimized_params[0]
        }

        print(best_params)
    else:
        # Use provided best_params or defaults
        if best_params is None:
            best_params = {
                'tpslRatio': 2.0,
                'slcoef': 2.0
            }
        print("Optimization is skipped, using params:", best_params)

    strategy_parameters = {
        "best": True,
        "tpslRatio": best_params['tpslRatio'],
        "slcoef": best_params['slcoef']
    }

    print(strategy_parameters)

    EMABollingerLowRiskStrat.slcoef = strategy_parameters["slcoef"]
    EMABollingerLowRiskStrat.TPSLRatio = strategy_parameters["tpslRatio"]

    # Update the global _strategy_parameters with the final values
    _strategy_parameters = strategy_parameters

    bt_best = Backtest(dftest, EMABollingerLowRiskStrat, cash=cash, margin=margin, finalize_trades=True)
    stats = bt_best.run()
    trades_actions = bt_best._strategy.trades_actions

    return bt_best, stats, trades_actions, strategy_parameters
