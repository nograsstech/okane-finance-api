from backtesting import Strategy, Backtest
import multiprocessing as mp
if mp.get_start_method(allow_none=True) != 'fork':
    mp.set_start_method('fork', force=True)
import numpy as np

# Module-level data container (will be set before backtest runs)
_dftest = None
_strategy_parameters = None


def SIGNAL(df, grid_distance, grid_range):
    """
    Generates a signal based on a grid strategy.
    A signal of 1 is generated when the price crosses a grid line.
    Ensures only one signal per candle, even if multiple grid lines are crossed.
    """
    def generate_grid(midprice, grid_distance, grid_range):
        return np.arange(midprice - grid_range, midprice + grid_range, grid_distance)

    midprice = df.iloc[0].Close
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
    """Grid trading strategy that buys and sells at grid levels."""
    mysize = 0.1
    grid_distance = 25
    grid_range = 1000
    trades_actions = []
    current_grid_level = None
    grid = None
    stop_loss_levels = 3

    def init(self):
        super().init()
        self.signal1 = self.I(SIGNAL, _dftest, self.grid_distance, self.grid_range)
        self.current_grid_level = self.data.Close[0]
        self.update_grid()

    def update_grid(self):
        self.grid = np.arange(self.current_grid_level - self.grid_range,
                             self.current_grid_level + self.grid_range,
                             self.grid_distance)

    def next(self):
        super().next()
        current_price = self.data.Close[-1]

        if self.signal1[-1] == 1:
            open_buy_trade = True
            open_sell_trade = True

            for trade in self.trades:
                if trade.is_long and trade.tp >= current_price:
                    open_buy_trade = False
                elif not trade.is_long and trade.tp <= current_price:
                    open_sell_trade = False

            if open_buy_trade:
                sl_buy = current_price - self.grid_distance * self.stop_loss_levels
                self.buy(tp=current_price + self.grid_distance, sl=sl_buy, size=self.mysize)

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
                sl_sell = current_price + self.grid_distance * self.stop_loss_levels
                self.sell(tp=current_price - self.grid_distance, sl=sl_sell, size=self.mysize)

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
        for trade in list(self.trades):
            if trade.is_long and current_price >= trade.tp and trade.pl > 0:
                trade.close()
                self.current_grid_level = trade.tp
                self.update_grid()
                sl_new_sell = self.current_grid_level + self.grid_distance * self.stop_loss_levels
                sl_new_buy = self.current_grid_level - self.grid_distance * self.stop_loss_levels

                self.sell(tp=self.current_grid_level - self.grid_distance, sl=sl_new_sell, size=self.mysize)
                self.trades_actions.append({
                    "datetime": self.data.index[-1].strftime('%Y-%m-%d %H:%M:%S.%f'),
                    "trade_action": "sell",
                    "entry_price": self.data.Close[-1],
                    "price": current_price,
                    "sl": sl_new_sell,
                    "tp": self.current_grid_level - self.grid_distance,
                    "size": self.mysize,
                })

                self.buy(tp=self.current_grid_level + self.grid_distance, sl=sl_new_buy, size=self.mysize)
                self.trades_actions.append({
                    "datetime": self.data.index[-1].strftime('%Y-%m-%d %H:%M:%S.%f'),
                    "trade_action": "buy",
                    "entry_price": self.data.Close[-1],
                    "price": current_price,
                    "sl": sl_new_buy,
                    "tp": self.current_grid_level + self.grid_distance,
                    "size": self.mysize,
                })

                print(f"Long trade closed profitably at {trade.tp}. New grid level: {self.current_grid_level}.")
                return

            elif not trade.is_long and current_price <= trade.tp and trade.pl > 0:
                trade.close()
                self.current_grid_level = trade.tp
                self.update_grid()
                sl_new_sell = self.current_grid_level + self.grid_distance * self.stop_loss_levels
                sl_new_buy = self.current_grid_level - self.grid_distance * self.stop_loss_levels

                self.sell(tp=self.current_grid_level - self.grid_distance, sl=sl_new_sell, size=self.mysize)
                self.trades_actions.append({
                    "datetime": self.data.index[-1].strftime('%Y-%m-%d %H:%M:%S.%f'),
                    "trade_action": "sell",
                    "entry_price": self.data.Close[-1],
                    "price": current_price,
                    "sl": sl_new_sell,
                    "tp": self.current_grid_level - self.grid_distance,
                    "size": self.mysize,
                })

                self.buy(tp=self.current_grid_level + self.grid_distance, sl=sl_new_buy, size=self.mysize)
                self.trades_actions.append({
                    "datetime": self.data.index[-1].strftime('%Y-%m-%d %H:%M:%S.%f'),
                    "trade_action": "buy",
                    "entry_price": self.data.Close[-1],
                    "price": current_price,
                    "sl": sl_new_buy,
                    "tp": self.current_grid_level + self.grid_distance,
                    "size": self.mysize,
                })

                print(f"Short trade closed profitably at {trade.tp}. New grid level: {self.current_grid_level}.")
                return


def backtest(df, strategy_parameters=None, skip_optimization=False, best_params=None):
    """
    Run backtest for the grid trading strategy.

    Args:
        df: DataFrame with OHLCV data
        strategy_parameters: Dict of strategy parameters (not used, kept for compatibility)
        skip_optimization: If True, use best_params instead of optimizing
        best_params: Pre-optimized parameters dict

    Returns:
        Tuple of (backtest_object, stats, trades_actions, strategy_parameters)
    """
    global _dftest, _strategy_parameters

    # Validate input data
    if df is None or df.empty:
        print("grid_trading backtest: df is None or empty")
        return None, None, [], {}

    if best_params is None:
        best_params = {"grid_distance": 30}

    dftest = df.copy()
    _dftest = dftest
    _strategy_parameters = strategy_parameters or {}

    # Backtest settings
    cash = 100000
    margin = 1/100
    commission = 0.000

    # Set initial class attributes
    GridTradingStrategy.trades_actions = []

    if not skip_optimization:
        print("Optimizing grid_trading...")
        bt_temp = Backtest(dftest, GridTradingStrategy, cash=cash, hedging=True,
                          margin=margin, commission=commission, finalize_trades=True)

        stats, heatmap = bt_temp.optimize(
            grid_distance=[i for i in range(10, 50, 5)],
            grid_range=[1000],
            maximize='Max. Drawdown [%]',
            max_tries=500,
            random_state=0,
            return_heatmap=True
        )

        # Convert multiindex series to dataframe
        heatmap_df = heatmap.unstack()

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
        grid_distance = 25
        best_params['grid_distance'] = grid_distance

    # Set grid parameters
    GridTradingStrategy.grid_distance = grid_distance
    GridTradingStrategy.grid_range = 1000

    # Run the backtest with the final parameters
    bt_best = Backtest(dftest, GridTradingStrategy, cash=cash, hedging=True,
                      margin=margin, commission=commission, finalize_trades=True)
    stats = bt_best.run(grid_distance=grid_distance)

    strategy_parameters = {
        "best": True,
        "grid_distance": grid_distance
    }
    print("Final strategy parameters:", strategy_parameters)

    trades_actions = bt_best._strategy.trades_actions
    print(stats)

    return bt_best, stats, trades_actions, strategy_parameters
