from backtesting import Strategy, Backtest
import pandas_ta as ta
import pandas as pd
import multiprocessing as mp
if mp.get_start_method(allow_none=True) != 'fork':
    mp.set_start_method('fork', force=True)

class QuantFVGStrategy(Strategy):
    # Optimization parameters
    tp_sl_ratio = 2.0
    fvg_min_size_atr_multiplier = 0.5
    fvg_candle_range_atr_multiplier = 1.5
    sl_atr_multiplier = 1.0
    fvg_expiry_bars = 10
    log_trades = False
    mysize = 0.03

    def init(self):
        self.ema200 = self.I(lambda x: ta.ema(pd.Series(x), length=200), self.data.Close)
        self.atr = self.I(lambda high, low, close: ta.atr(high=pd.Series(high), low=pd.Series(low), close=pd.Series(close), length=14),
                          self.data.High, self.data.Low, self.data.Close)
        self.active_fvg = None
        self.trades_actions = []

    def next(self):
        if self.position:
            return

        current_bar_index = len(self.data.Close) - 1
        current_atr = self.atr[-1]
        price = self.data.Close[-1]

        if self.active_fvg:
            if current_bar_index >= self.active_fvg['expiry']:
                self.active_fvg = None
            if self.active_fvg and self.active_fvg['type'] == 'bearish' and price > self.active_fvg['top']:
                self.active_fvg = None
            if self.active_fvg and self.active_fvg['type'] == 'bullish' and price < self.active_fvg['bottom']:
                self.active_fvg = None

            if self.active_fvg:
                if self.active_fvg['type'] == 'bearish':
                    if self.data.High[-1] > self.active_fvg['bottom']:
                        entry_price = self.data.Close[-1]
                        sl = self.active_fvg['sl']
                        tp = entry_price - self.tp_sl_ratio * (sl - entry_price)
                        self.sell(sl=sl, tp=tp, size=self.mysize)
                        if self.log_trades:
                            self.trades_actions.append({
                                "datetime": self.data.index[-1].strftime('%Y-%m-%d %H:%M:%S.%f'),
                                "trade_action": "sell",
                                "entry_price": entry_price,
                                "price": self.data.Close[-1],
                                "sl": sl,
                                "tp": tp,
                                "size": self.mysize,
                            })
                        self.active_fvg = None
                        return
                elif self.active_fvg['type'] == 'bullish':
                    if self.data.Low[-1] < self.active_fvg['top']:
                        entry_price = self.data.Close[-1]
                        sl = self.active_fvg['sl']
                        tp = entry_price + self.tp_sl_ratio * (entry_price - sl)
                        self.buy(sl=sl, tp=tp, size=self.mysize)
                        if self.log_trades:
                            self.trades_actions.append({
                                "datetime": self.data.index[-1].strftime('%Y-%m-%d %H:%M:%S.%f'),
                                "trade_action": "buy",
                                "entry_price": entry_price,
                                "price": self.data.Close[-1],
                                "sl": sl,
                                "tp": tp,
                                "size": self.mysize,
                            })
                        self.active_fvg = None
                        return
            if self.active_fvg:
                return

        if not self.active_fvg:
            if len(self.data.Close) < 20:
                return

            if price < self.ema200[-1]:
                if self.data.Low[-3] > self.data.High[-1]:
                    fvg_top = self.data.Low[-3]
                    fvg_bottom = self.data.High[-1]
                    fvg_size = fvg_top - fvg_bottom
                    fvg_candle_range = self.data.High[-2] - self.data.Low[-2]

                    if (fvg_size > self.fvg_min_size_atr_multiplier * current_atr and
                        fvg_candle_range > self.fvg_candle_range_atr_multiplier * current_atr):
                        sl = self.data.High[-2] + self.sl_atr_multiplier * current_atr
                        self.active_fvg = {'type': 'bearish', 'top': fvg_top, 'bottom': fvg_bottom, 'sl': sl, 'expiry': current_bar_index + self.fvg_expiry_bars}
                        return

            if price > self.ema200[-1]:
                if self.data.High[-3] < self.data.Low[-1]:
                    fvg_bottom = self.data.High[-3]
                    fvg_top = self.data.Low[-1]
                    fvg_size = fvg_top - fvg_bottom
                    fvg_candle_range = self.data.High[-2] - self.data.Low[-2]

                    if (fvg_size > self.fvg_min_size_atr_multiplier * current_atr and
                        fvg_candle_range > self.fvg_candle_range_atr_multiplier * current_atr):
                        sl = self.data.Low[-2] - self.sl_atr_multiplier * current_atr
                        self.active_fvg = {'type': 'bullish', 'top': fvg_top, 'bottom': fvg_bottom, 'sl': sl, 'expiry': current_bar_index + self.fvg_expiry_bars}
                        return

def backtest(df, strategy_parameters, size=0.03, skip_optimization=False, best_params=None):
    dftest = df[:]
    margin = 1/500
    cash = 100000

    QuantFVGStrategy.tp_sl_ratio = strategy_parameters.get('tp_sl_ratio', QuantFVGStrategy.tp_sl_ratio)
    QuantFVGStrategy.fvg_min_size_atr_multiplier = strategy_parameters.get('fvg_min_size_atr_multiplier', QuantFVGStrategy.fvg_min_size_atr_multiplier)
    QuantFVGStrategy.fvg_candle_range_atr_multiplier = strategy_parameters.get('fvg_candle_range_atr_multiplier', QuantFVGStrategy.fvg_candle_range_atr_multiplier)
    QuantFVGStrategy.sl_atr_multiplier = strategy_parameters.get('sl_atr_multiplier', QuantFVGStrategy.sl_atr_multiplier)
    QuantFVGStrategy.fvg_expiry_bars = strategy_parameters.get('fvg_expiry_bars', QuantFVGStrategy.fvg_expiry_bars)

    if not skip_optimization:
        print("Optimizing FVG Confirmation Strategy...")
        QuantFVGStrategy.log_trades = False
        bt = Backtest(dftest, QuantFVGStrategy, cash=cash, margin=margin)
        
        stats, heatmap = bt.optimize(
            tp_sl_ratio=[1.25, 1.5, 2.0, 2.5],
            maximize='Win Rate [%]',
            return_heatmap=True,
        )
        
        if stats is not None and '_strategy' in stats:
            best_params = {
                'tp_sl_ratio': stats['_strategy'].tp_sl_ratio
            }
        else:
            best_params = {
                'tp_sl_ratio': QuantFVGStrategy.tp_sl_ratio
            }
        print("Best params from optimization:", best_params)

    else:
        print("Skipping optimization for FVG Confirmation Strategy.")
        if not best_params:
            best_params = {
                'tp_sl_ratio': strategy_parameters.get('tp_sl_ratio', QuantFVGStrategy.tp_sl_ratio)
            }
    
    QuantFVGStrategy.tp_sl_ratio = best_params['tp_sl_ratio']
    QuantFVGStrategy.log_trades = True
    QuantFVGStrategy.mysize = size
    
    bt_best = Backtest(dftest, QuantFVGStrategy, cash=cash, margin=margin)
    stats = bt_best.run()
    
    trades_actions = []
    if hasattr(bt_best._strategy, 'trades_actions'):
        trades_actions = bt_best._strategy.trades_actions

    strategy_parameters = {
        "best": True,
        "tpslRatio": best_params['tp_sl_ratio']
    }
    
    print("Final strategy parameters used:", strategy_parameters)

    return bt_best, stats, trades_actions, strategy_parameters