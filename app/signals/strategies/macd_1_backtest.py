from backtesting import Strategy
from backtesting import Backtest
import multiprocessing as mp

if mp.get_start_method(allow_none=True) != "fork":
    mp.set_start_method("fork", force=True)


def backtest(df, strategy_parameters):
    dftest = df[:]

    # TODO: make these variables parameters instead
    # trades_actions = None
    margin = 1 / 100
    cash = 100000
    lot_size = 0.03

    import pandas_ta as ta

    dftest["ATR"] = ta.atr(dftest.High, dftest.Low, dftest.Close, length=24)

    def SIGNAL():
        return dftest.TotalSignal

    class MyStrat(Strategy):
        trades_actions = []
        initsize = lot_size
        mysize = lot_size
        latestEntry = 0
        lastHigh = 0
        slcoef = 2.3  # just initial value, not used
        TPSLRatio = 2.5  # just initial value, not used

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

            # # close the position if the amount lost exceeds 3% of the account balance
            if self.position.pl < -1 * self.equity * 0.02:
                self.position.close()
                self.trades_actions.append(
                    {
                        "datetime": self.data.index[-1].strftime(
                            "%Y-%m-%d %H:%M:%S.%f"
                        ),
                        "trade_action": "close",
                        "entry_price": self.data.Close[-1],
                        "price": self.data.Close[-1],
                        "sl": None,
                        "tp": None,
                        "size": self.mysize,
                    }
                )

            if len(self.trades) > 0:
                for trade in self.trades:
                    if trade.is_long and self.data.RSI[-1] >= 90:
                        trade.close()
                        self.trades_actions.append(
                            {
                                "datetime": self.data.index[-1].strftime(
                                    "%Y-%m-%d %H:%M:%S.%f"
                                ),
                                "trade_action": "close",
                                "entry_price": trade.entry_price,
                                "price": self.data.Close[-1],
                                "sl": None,
                                "tp": None,
                                "size": self.mysize,
                            }
                        )
                    elif trade.is_short and self.data.RSI[-1] <= 10:
                        trade.close()
                        self.trades_actions.append(
                            {
                                "datetime": self.data.index[-1].strftime(
                                    "%Y-%m-%d %H:%M:%S.%f"
                                ),
                                "trade_action": "close",
                                "entry_price": trade.entry_price,
                                "price": self.data.Close[-1],
                                "sl": None,
                                "tp": None,
                                "size": self.mysize,
                            }
                        )

            if self.signal1 == 2 and len(self.trades) < strategy_parameters.get(
                "max_longs", 1
            ):
                sl1 = self.data.Close[-1] - slatr
                tp1 = self.data.Close[-1] + slatr * TPSLRatio
                self.buy(sl=sl1, tp=tp1, size=self.mysize)
                self.latestEntry = self.data.Close[-1]
                self.trades_actions.append(
                    {
                        "datetime": self.data.index[-1].strftime(
                            "%Y-%m-%d %H:%M:%S.%f"
                        ),
                        "trade_action": "buy",
                        "entry_price": self.data.Close[-1],
                        "price": self.data.Close[-1],
                        "sl": sl1,
                        "tp": tp1,
                        "size": self.mysize,
                    }
                )

            elif self.signal1 == 1 and len(self.trades) < strategy_parameters.get(
                "max_shorts", 1
            ):
                sl1 = self.data.Close[-1] + slatr
                tp1 = self.data.Close[-1] - slatr * TPSLRatio
                self.sell(sl=sl1, tp=tp1, size=self.mysize)
                self.latestEntry = self.data.Close[-1]
                self.trades_actions.append(
                    {
                        "datetime": self.data.index[-1].strftime(
                            "%Y-%m-%d %H:%M:%S.%f"
                        ),
                        "trade_action": "sell",
                        "entry_price": self.data.Close[-1],
                        "price": self.data.Close[-1],
                        "sl": sl1,
                        "tp": tp1,
                        "size": self.mysize,
                    }
                )

    bt = Backtest(dftest, MyStrat, cash=cash, margin=margin)

    stats, heatmap = bt.optimize(
        slcoef=[i / 10 for i in range(10, 41)],
        TPSLRatio=[i / 10 for i in range(10, 41)],
        maximize="Return [%]",
        max_tries=500,
        random_state=0,
        return_heatmap=True,
    )

    # Convert multiindex series to dataframe
    heatmap_df = heatmap.unstack()
    # find the one best parameters from heatmap_df
    best_params = heatmap_df.idxmax()

    # Find the maximum value over the entire DataFrame
    max_value = heatmap_df.max().max()

    # Find the index of the maximum value
    best_params = (heatmap_df == max_value).stack().idxmax()

    print(best_params)

    strategy_parameters = {
        "best": True,
        "slcoef": best_params[0],
        "tpslRatio": best_params[1],
    }

    print(strategy_parameters)

    MyStrat.slcoef = strategy_parameters["slcoef"]
    MyStrat.TPSLRatio = strategy_parameters["slcoef"]

    bt_best = Backtest(dftest, MyStrat, cash=cash, margin=margin)
    bt_best.run()
    trades_actions = bt_best._strategy.trades_actions

    # TODO: Save the backtest result to Supabase using the refID.

    return bt, stats, heatmap, trades_actions
