from backtesting import Strategy, Backtest
import multiprocessing as mp
if mp.get_start_method(allow_none=True) != 'fork':
    mp.set_start_method('fork', force=True)
import numpy as np

# Module-level data container (will be set before backtest runs)
_df_for_signal = None

def SIGNAL(df, grid_distance, grid_range):
    """
    Generates a signal based on a grid strategy. A signal of 1 is generated when the price crosses a grid line.
    Ensures only one signal per candle, even if multiple grid lines are crossed in one candle.
    """
    def generate_grid(midprice, grid_distance, grid_range):
        return np.arange(midprice - grid_range, midprice + grid_range, grid_distance)

    midprice = df.iloc[0].Close  # Use the initial close price as the midprice.
    grid = generate_grid(midprice=midprice, grid_distance=grid_distance, grid_range=grid_range)

    signal = np.zeros(len(df), dtype=int)
    for i, row in df.iterrows():
        signal_generated_this_candle = False
        for p in grid:
            if row.Low <= p <= row.High:
                if not signal_generated_this_candle:
                    signal[df.index.get_loc(i)] = 1
                    signal_generated_this_candle = True
                    break
    return signal

class GridTradingStrategy(Strategy):
    mysize = 0.1
    grid_distance = 25
    grid_range = 1000
    trades_actions = []
    current_grid_level = None
    grid = None
    stop_loss_levels = 3 # Stop loss at 3 grid levels

    def init(self):
        super().init()
        self.signal1 = self.I(SIGNAL, _df_for_signal, self.grid_distance, self.grid_range)
        self.current_grid_level = self.data.Close[0] # Initial grid level is the first close price
        self.update_grid()

    def update_grid(self):
        self.grid = np.arange(self.current_grid_level - self.grid_range, self.current_grid_level + self.grid_range, self.grid_distance)

    def next(self):
        super().next()
        current_price = self.data.Close[-1]

        if self.signal1[-1] == 1: # Signal to check and potentially open trades at grid level
            open_buy_trade = True
            open_sell_trade = True

            for trade in self.trades:
                if trade.is_long and trade.tp >= current_price: # Existing long trade targeting this level or higher
                    open_buy_trade = False
                elif not trade.is_long and trade.tp <= current_price: # Existing short trade targeting this level or lower
                    open_sell_trade = False

            if open_buy_trade:
                sl_buy = current_price - self.grid_distance * self.stop_loss_levels # SL for buy order
                self.buy(tp=current_price + self.grid_distance, sl=sl_buy, size=self.mysize)  # Open buy at current level with SL (TP is full grid distance)
                self.trades_actions.append({
                    "datetime": self.data.index[-1].strftime('%Y-%m-%d %H:%M:%S.%f'),
                    "trade_action": "buy",
                    "entry_price": self.data.Close[-1],
                    "price": current_price,
                    "sl": sl_buy,
                    "tp": current_price + self.grid_distance,
                    "size": self.mysize,
                })
                print(f"New BUY trade opened at level: {current_price} with SL: {sl_buy}, TP: {current_price + self.grid_distance}")
            if open_sell_trade:
                sl_sell = current_price + self.grid_distance * self.stop_loss_levels # SL for sell order
                self.sell(tp=current_price - self.grid_distance, sl=sl_sell, size=self.mysize) # Open sell at current level with SL (TP is full grid distance)
                self.trades_actions.append({
                    "datetime": self.data.index[-1].strftime('%Y-%m-%d %H:%M:%S.%f'),
                    "trade_action": "sell",
                    "entry_price": self.data.Close[-1],
                    "price": current_price,
                    "sl": sl_sell,
                    "tp": current_price - self.grid_distance,
                    "size": self.mysize,
                })
                print(f"New SELL trade opened at level: {current_price} with SL: {sl_sell}, TP: {current_price - self.grid_distance}")


        # Check and close profitable trades
        for trade in list(self.trades): # Iterate over a copy to allow removal during iteration
            if trade.is_long and current_price >= trade.tp and trade.pl > 0: # Profitable long trade reached TP
                trade.close()
                self.current_grid_level = trade.tp # New grid level from TP of closed trade
                self.update_grid() # Update grid
                sl_new_sell = self.current_grid_level + self.grid_distance * self.stop_loss_levels # SL for new sell
                sl_new_buy = self.current_grid_level - self.grid_distance * self.stop_loss_levels # SL for new buy

                self.sell(tp=self.current_grid_level - self.grid_distance, sl=sl_new_sell, size=self.mysize) # Open new sell at new grid level with SL (TP is full grid distance)
                self.trades_actions.append({
                    "datetime": self.data.index[-1].strftime('%Y-%m-%d %H:%M:%S.%f'),
                    "trade_action": "sell",
                    "entry_price": self.data.Close[-1],
                    "price": current_price,
                    "sl": sl_new_sell,
                    "tp": self.current_grid_level - self.grid_distance,
                    "size": self.mysize,
                })

                self.buy(tp=self.current_grid_level + self.grid_distance, sl=sl_new_buy, size=self.mysize)  # Open new buy at new grid level with SL (TP is full grid distance)
                self.trades_actions.append({
                    "datetime": self.data.index[-1].strftime('%Y-%m-%d %H:%M:%S.%f'),
                    "trade_action": "buy",
                    "entry_price": self.data.Close[-1],
                    "price": current_price,
                    "sl": sl_new_buy,
                    "tp": self.current_grid_level + self.grid_distance,
                    "size": self.mysize,
                })

                print(f"Long trade closed profitably at {trade.tp}. New grid level: {self.current_grid_level}. Opened new pair with SLs: Sell SL={sl_new_sell}, Buy SL={sl_new_buy}, TPs: Sell TP={self.current_grid_level - self.grid_distance}, Buy TP={self.current_grid_level + self.grid_distance}")
                return # Exit after one profitable close and new pair open to avoid closing multiple in one candle

            elif not trade.is_long and current_price <= trade.tp and trade.pl > 0: # Profitable short trade reached TP
                trade.close()
                self.current_grid_level = trade.tp # New grid level from TP of closed trade
                self.update_grid() # Update grid
                sl_new_sell = self.current_grid_level + self.grid_distance * self.stop_loss_levels # SL for new sell
                sl_new_buy = self.current_grid_level - self.grid_distance * self.stop_loss_levels # SL for new buy

                self.sell(tp=self.current_grid_level - self.grid_distance, sl=sl_new_sell, size=self.mysize) # Open new sell at new grid level with SL (TP is full grid distance)
                self.trades_actions.append({
                    "datetime": self.data.index[-1].strftime('%Y-%m-%d %H:%M:%S.%f'),
                    "trade_action": "sell",
                    "entry_price": self.data.Close[-1],
                    "price": current_price,
                    "sl": sl_new_sell,
                    "tp": self.current_grid_level - self.grid_distance,
                    "size": self.mysize,
                })

                self.buy(tp=self.current_grid_level + self.grid_distance, sl=sl_new_buy, size=self.mysize)  # Open new buy at new grid level with SL (TP is full grid distance)
                self.trades_actions.append({
                    "datetime": self.data.index[-1].strftime('%Y-%m-%d %H:%M:%S.%f'),
                    "trade_action": "buy",
                    "entry_price": self.data.Close[-1],
                    "price": current_price,
                    "sl": sl_new_buy,
                    "tp": self.current_grid_level + self.grid_distance,
                    "size": self.mysize,
                })
                print(f"Short trade closed profitably at {trade.tp}. New grid level: {self.current_grid_level}. Opened new pair with SLs: Sell SL={sl_new_sell}, Buy SL={sl_new_buy}, TPs: Sell TP={self.current_grid_level - self.grid_distance}, Buy TP={self.current_grid_level + self.grid_distance}")
                return # Exit after one profitable close and new pair open

def backtest(df, strategy_parameters=None, skip_optimization=False, best_params={ "grid_distance": 30 }):
    global _df_for_signal

    print("Starting grid trading backtest...")
    dftest = df[:]
    _df_for_signal = dftest

    # Backtest settings
    cash = 100000
    margin = 1/100
    commission = 0.000

    # Reset class attributes
    GridTradingStrategy.trades_actions = []
    GridTradingStrategy.mysize = 0.1

    if (not skip_optimization):
        print("Optimizing...")
        bt_temp = Backtest(dftest, GridTradingStrategy, cash=cash, hedging=True, margin=margin, commission=commission)
        # We need to run once to initialize any class attributes if needed, but optimize will handle it.
        stats, heatmap = bt_temp.optimize(
                            grid_distance=[i for i in range(10, 50, 5)],
                            grid_range=[1000],
                            maximize='Max. Drawdown [%]', max_tries=500,
                            random_state=0,
                            return_heatmap=True)
        # Convert multiindex series to dataframe
        heatmap_df = heatmap.unstack()
        # find the one best parameters from heatmap_df

        # Find the maximum value over the entire DataFrame
        max_value = heatmap_df.max().max()

       # Find the index of the maximum value
        optimized_params = (heatmap_df == max_value).stack().idxmax()

        best_params = {}
        best_params['grid_distance'] = optimized_params[0]

        print("Optimized best params:", best_params)
    else:
        print("Optimization is skipped and best params provided", best_params)

    # Ensure grid_distance is in best_params
    grid_distance = best_params.get('grid_distance')
    if grid_distance is None:
        grid_distance = 25 # Default value
        best_params['grid_distance'] = grid_distance

    # Run the backtest with the final parameters
    bt_best = Backtest(dftest, GridTradingStrategy, cash=cash, hedging=True, margin=margin, commission=commission)
    stats = bt_best.run(grid_distance=grid_distance)

    strategy_parameters = {
        "best": True,
        "grid_distance": grid_distance
    }
    print("Final strategy parameters:", strategy_parameters)

    trades_actions = bt_best._strategy.trades_actions
    print(stats)

    return bt_best, stats, trades_actions, strategy_parameters
