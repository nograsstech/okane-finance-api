from backtesting import Strategy
from backtesting import Backtest

def backtest(df, strategy_parameters):
    dftest = df[:]
    
    # TODO: make these variables parameters instead
    # trades_actions = None
    margin = 1/500
    cash = 100000
    lot_size = 0.03

    def SIGNAL():
        return dftest.TotalSignal

    class MyStrat(Strategy):
        mysize = lot_size
        slcoef = strategy_parameters["slcoef"]
        TPSLRatio = strategy_parameters["tpslRatio"]
        trades_actions = []

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
                    # record trade action
                    if (strategy_parameters['best']):
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
                    # record trade action
                    if (strategy_parameters['best']):
                        self.trades_actions.append({
                            "datetime": self.data.index[-1].strftime('%Y-%m-%d %H:%M:%S.%f'),
                            "trade_action": "close",
                            "entry_price": trade.entry_price,
                            "price": self.data.Close[-1],
                            "sl": None,
                            "tp": None,
                            "size": self.mysize,
                        })

            if self.signal1 == 2 and len(self.trades) == 0:
                sl1 = self.data.Close[-1] - slatr
                tp1 = self.data.Close[-1] + slatr * TPSLRatio
                self.buy(sl=sl1, tp=tp1, size=self.mysize)
                # record trade action
                if (strategy_parameters['best']):
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
                # record trade action
                if (strategy_parameters['best']):
                    self.trades_actions.append({
                        "datetime": self.data.index[-1].strftime('%Y-%m-%d %H:%M:%S.%f'),
                        "trade_action": "sell",
                        "entry_price": self.data.Close[-1],
                        "price": self.data.Close[-1],
                        "sl": sl1,
                        "tp": tp1,
                        "size": self.mysize,
                    })
    
    bt = Backtest(dftest, MyStrat, cash=cash, margin=margin)

    stats, heatmap = bt.optimize(
        slcoef=[i / 10 for i in range(10, 26)],
        TPSLRatio=[i / 10 for i in range(10, 26)],
        maximize="Return [%]",
        max_tries=300,
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
        "tpslRatio": best_params[1]
    }
    
    print(strategy_parameters)
    
    MyStrat.slcoef = strategy_parameters["slcoef"]
    MyStrat.TPSLRatio = strategy_parameters["slcoef"]
    
    bt_best = Backtest(dftest, MyStrat, cash=cash, margin=margin)
    bt_best.run()
    trades_actions = bt_best._strategy.trades_actions
    
    # TODO: Save the backtest result to Supabase using the refID.
    
    return bt, stats, heatmap, trades_actions
