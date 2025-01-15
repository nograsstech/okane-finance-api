from backtesting import Strategy
from backtesting import Backtest
import multiprocessing as mp
if mp.get_start_method(allow_none=True) != 'fork':
    mp.set_start_method('fork', force=True)

def backtest(df, strategy_parameters, size = 0.03, skip_optimization=False, best_params=None):
    dftest = df[:]
    
    # TODO: make these variables parameters instead
    # trades_actions = None
    margin = 1/100
    cash = 100000
    size = 0.01
    lot_size = size

    def SIGNAL():
        return dftest.TotalSignal

    class CLFControlTpAndSlSeparately_15m(Strategy):
        mysize = 0.03
        slcoef = 3
        TPcoef = 2
        trades_actions = []
        
        def init(self):
            super().init()
            self.signal1 = self.I(SIGNAL)

        def next(self):
            try:
                super().next()
                slatr = self.slcoef*self.data.atr[-1]
                tpatr = self.TPcoef*self.data.atr[-1]
            
                if self.signal1==2 and len(self.trades)==0:
                    sl1 = self.data.Close[-1] - slatr
                    tp1 = self.data.Close[-1] + tpatr
                    self.buy(sl=sl1, tp=tp1, size=self.mysize)
                    
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

                if self.signal1==1 and len(self.trades)==0:
                    sl1 = self.data.Close[-1] + slatr
                    tp1 = self.data.Close[-1] - tpatr
                    self.sell(sl=sl1, tp=tp1, size=self.mysize)
                    
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
            except:
                pass
    
    # Do optimization if skip_optimization is False
    if (not skip_optimization):
        print("Optimizing...")
        bt = Backtest(df, CLFControlTpAndSlSeparately_15m, cash=100000, margin=1/100, commission=0.000) #0.0002
        stats, heatmap = bt.optimize(slcoef=[i/10 for i in range(40, 140, 5)],
                    TPcoef=[i/10 for i in range(40, 100, 5)],
                    maximize='Sharpe Ratio', max_tries=500,
                        random_state=0,
                        return_heatmap=True)
        
        print(stats)
        
        # Convert multiindex series to dataframe
        heatmap_df = heatmap.unstack()
        # find the one best parameters from heatmap_df
        best_params = heatmap_df.idxmax()

        # Find the maximum value over the entire DataFrame
        max_value = heatmap_df.max().max()

        # Find the index of the maximum value
        optimized_params = (heatmap_df == max_value).stack().idxmax()
        
        best_params = {}
        best_params['TPcoef'] = optimized_params[1]
        best_params['slcoef'] = optimized_params[0]

        print(best_params)
    else:
        print("Optimization is skipped and best params provided", best_params)
        
    strategy_parameters = {
        "best": True,
        "TPcoef": best_params['TPcoef'],
        "slcoef": best_params['slcoef'],
        "tpslRatio": best_params['TPcoef'] / best_params['slcoef']
    }
    
    print(strategy_parameters)
    
    CLFControlTpAndSlSeparately_15m.slcoef = strategy_parameters["slcoef"]
    CLFControlTpAndSlSeparately_15m.TPcoef = strategy_parameters["TPcoef"]
    
    bt_best = Backtest(dftest, CLFControlTpAndSlSeparately_15m, cash=cash, margin=margin)
    stats = bt_best.run()
    trades_actions = bt_best._strategy.trades_actions
    
    return bt_best, stats, trades_actions, strategy_parameters
