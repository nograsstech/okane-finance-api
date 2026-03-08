from backtesting import Strategy
from backtesting import Backtest
import multiprocessing as mp

if mp.get_start_method(allow_none=True) != "fork":
    mp.set_start_method("fork", force=True)

# Module-level data container (will be set before backtest runs)
_dftest = None
_strategy_parameters = None


def SIGNAL():
    """Return the TotalSignal column from the test DataFrame."""
    return _dftest.TotalSignal


class MACDStrat(Strategy):
    """MACD strategy with RSI exit conditions."""
    trades_actions = []
    initsize = 0.03
    mysize = 0.03
    latestEntry = 0
    lastHigh = 0
    slcoef = 2.3
    TPSLRatio = 2.5

    def init(self):
        super().init()
        self.signal1 = self.I(SIGNAL)

    def next(self):
        super().next()
        slatr = self.slcoef * self.data.ATR[-1]
        TPSLRatio = self.TPSLRatio

        # if the current equity is higher than lastHigh, then update lastHigh
        if self.equity > self.lastHigh:
            self.lastHigh = self.equity

        # close the position if the amount lost exceeds 2% of the account balance
        if self.position.pl < -1 * self.equity * 0.02:
            self.position.close()
            if _strategy_parameters and _strategy_parameters.get('best', False):
                self.trades_actions.append({
                    "datetime": self.data.index[-1].strftime("%Y-%m-%d %H:%M:%S.%f"),
                    "trade_action": "close",
                    "entry_price": self.data.Close[-1],
                    "price": self.data.Close[-1],
                    "sl": None,
                    "tp": None,
                    "size": self.mysize,
                })

        if len(self.trades) > 0:
            for trade in self.trades:
                if trade.is_long and self.data.RSI[-1] >= 90:
                    trade.close()
                    if _strategy_parameters and _strategy_parameters.get('best', False):
                        self.trades_actions.append({
                            "datetime": self.data.index[-1].strftime("%Y-%m-%d %H:%M:%S.%f"),
                            "trade_action": "close",
                            "entry_price": trade.entry_price,
                            "price": self.data.Close[-1],
                            "sl": None,
                            "tp": None,
                            "size": self.mysize,
                        })
                elif trade.is_short and self.data.RSI[-1] <= 10:
                    trade.close()
                    if _strategy_parameters and _strategy_parameters.get('best', False):
                        self.trades_actions.append({
                            "datetime": self.data.index[-1].strftime("%Y-%m-%d %H:%M:%S.%f"),
                            "trade_action": "close",
                            "entry_price": trade.entry_price,
                            "price": self.data.Close[-1],
                            "sl": None,
                            "tp": None,
                            "size": self.mysize,
                        })

        if self.signal1 == 2 and len(self.trades) < _strategy_parameters.get("max_longs", 1):
            sl1 = self.data.Close[-1] - slatr
            tp1 = self.data.Close[-1] + slatr * TPSLRatio
            self.buy(sl=sl1, tp=tp1, size=self.mysize)
            self.latestEntry = self.data.Close[-1]
            if _strategy_parameters and _strategy_parameters.get('best', False):
                self.trades_actions.append({
                    "datetime": self.data.index[-1].strftime("%Y-%m-%d %H:%M:%S.%f"),
                    "trade_action": "buy",
                    "entry_price": self.data.Close[-1],
                    "price": self.data.Close[-1],
                    "sl": sl1,
                    "tp": tp1,
                    "size": self.mysize,
                })

        elif self.signal1 == 1 and len(self.trades) < _strategy_parameters.get("max_shorts", 1):
            sl1 = self.data.Close[-1] + slatr
            tp1 = self.data.Close[-1] - slatr * TPSLRatio
            self.sell(sl=sl1, tp=tp1, size=self.mysize)
            self.latestEntry = self.data.Close[-1]
            if _strategy_parameters and _strategy_parameters.get('best', False):
                self.trades_actions.append({
                    "datetime": self.data.index[-1].strftime("%Y-%m-%d %H:%M:%S.%f"),
                    "trade_action": "sell",
                    "entry_price": self.data.Close[-1],
                    "price": self.data.Close[-1],
                    "sl": sl1,
                    "tp": tp1,
                    "size": self.mysize,
                })


def backtest(df, strategy_parameters, size=0.03, skip_optimization=False, best_params=None):
    """
    Run backtest for the MACD strategy.

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
        print("macd_1 backtest: df is None or empty")
        return None, None, [], {}

    dftest = df.copy()
    _dftest = dftest
    _strategy_parameters = strategy_parameters

    # Default backtest parameters
    margin = 1 / 100
    cash = 100000
    lot_size = size

    # Set initial class attributes from parameters
    MACDStrat.initsize = lot_size
    MACDStrat.mysize = lot_size
    MACDStrat.slcoef = strategy_parameters.get("slcoef", 2.3)
    MACDStrat.TPSLRatio = strategy_parameters.get("tpslRatio", 2.5)
    MACDStrat.trades_actions = []

    # Do optimization if skip_optimization is False
    if not skip_optimization:
        print("Optimizing macd_1...")
        bt = Backtest(dftest, MACDStrat, cash=cash, margin=margin, finalize_trades=True)

        stats, heatmap = bt.optimize(
            slcoef=[i / 10 for i in range(10, 25)],
            TPSLRatio=[i / 10 for i in range(15, 30)],
            maximize="Win Rate [%]",
            max_tries=500,
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
                'tpslRatio': 2.5,
                'slcoef': 2.3
            }
        print("Optimization is skipped, using params:", best_params)

    strategy_parameters = {
        "best": True,
        "tpslRatio": best_params['tpslRatio'],
        "slcoef": best_params['slcoef']
    }

    print(strategy_parameters)

    MACDStrat.slcoef = strategy_parameters["slcoef"]
    MACDStrat.TPSLRatio = strategy_parameters["tpslRatio"]

    # Update the global _strategy_parameters with the final values
    _strategy_parameters = strategy_parameters

    bt_best = Backtest(dftest, MACDStrat, cash=cash, margin=margin, finalize_trades=True)
    stats = bt_best.run()
    trades_actions = bt_best._strategy.trades_actions

    return bt_best, stats, trades_actions, strategy_parameters
