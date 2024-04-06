from backtesting import Strategy
from backtesting import Backtest


def backtest(df, strategy_parameters):
    dftest = df[:]

    def SIGNAL():
        return dftest.TotalSignal

    class MyStrat(Strategy):
        mysize = 0.03
        slcoef = strategy_parameters["slcoef"]
        TPSLRatio = strategy_parameters["tpslRatio"]

        def init(self):
            super().init()
            self.signal1 = self.I(SIGNAL)

        def next(self):
            super().next()
            slatr = self.slcoef * self.data.ATR[-1]
            TPSLRatio = self.TPSLRatio

            for trade in self.trades:
                if trade.is_long and self.data.RSI[-1] >= 80:
                    trade.close()
                elif trade.is_short and self.data.RSI[-1] <= 20:
                    trade.close()

            if self.signal1 == 2 and len(self.trades) == 0:
                sl1 = self.data.Close[-1] - slatr
                tp1 = self.data.Close[-1] + slatr * TPSLRatio
                self.buy(sl=sl1, tp=tp1, size=self.mysize)

            elif self.signal1 == 1 and len(self.trades) == 0:
                sl1 = self.data.Close[-1] + slatr
                tp1 = self.data.Close[-1] - slatr * TPSLRatio
                self.sell(sl=sl1, tp=tp1, size=self.mysize)

    bt = Backtest(dftest, MyStrat, cash=100000, margin=1 / 500)
    bt.run()

    stats, heatmap = bt.optimize(
        slcoef=[i / 10 for i in range(10, 26)],
        TPSLRatio=[i / 10 for i in range(10, 26)],
        maximize="Return [%]",
        max_tries=300,
        random_state=0,
        return_heatmap=True,
    )

    return bt, stats, heatmap
