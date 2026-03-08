from backtesting import Strategy
from backtesting import Backtest
import multiprocessing as mp
import numpy as np
import pandas as pd

if mp.get_start_method(allow_none=True) != 'fork':
    mp.set_start_method('fork', force=True)

# Module-level data container (will be set before backtest runs)
_dftest = None
_strategy_parameters = None


def SIGNAL():
    """Return the TotalSignal column from the test DataFrame."""
    return _dftest.TotalSignal


def VOLATILITY():
    """Return the volatility column from the test DataFrame."""
    return _dftest.volatility


class SuperSafeStrategy(Strategy):
    """Enhanced strategy with trailing stops, dynamic position sizing, and RSI exits."""
    # Strategy parameters with default values
    slcoef = 3.0
    TPSLRatio = 2.5
    trailing_sl = 2.0
    max_positions = 1
    max_risk_pct = 1.0
    min_atr_value = 0.0001
    trades_actions = []
    mysize = 0.01
    base_lot_size = 0.01

    def init(self):
        super().init()
        self.signal = self.I(SIGNAL)
        self.volatility = self.I(VOLATILITY)
        self.trailing_stops = {}

    def next(self):
        super().next()

        # Skip if we have no price data
        if not len(self.data.Close):
            return

        # Calculate ATR-based stop distances with minimum value
        atr = max(self.data.ATR[-1], self.min_atr_value)
        sl_distance = self.slcoef * atr
        tp_distance = sl_distance * self.TPSLRatio

        # Update trailing stops for open trades
        for trade in list(self.trades):
            trade_id = id(trade)

            # Initialize trailing stop if needed
            if trade_id not in self.trailing_stops:
                if trade.is_long:
                    self.trailing_stops[trade_id] = trade.entry_price - sl_distance
                else:
                    self.trailing_stops[trade_id] = trade.entry_price + sl_distance

            # Update trailing stop - only if profitable
            if trade.is_long:
                trail_level = self.data.Close[-1] - (self.trailing_sl * atr)

                if (self.data.Close[-1] > trade.entry_price * 1.005) and (trail_level > self.trailing_stops[trade_id]):
                    self.trailing_stops[trade_id] = trail_level

                # Check if price hit trailing stop
                if self.data.Low[-1] < self.trailing_stops[trade_id]:
                    trade.close()
                    if _strategy_parameters and _strategy_parameters.get('best', False):
                        self.trades_actions.append({
                            "datetime": self.data.index[-1].strftime('%Y-%m-%d %H:%M:%S.%f'),
                            "trade_action": "close_trail_sl",
                            "entry_price": trade.entry_price,
                            "price": self.trailing_stops[trade_id],
                            "sl": self.trailing_stops[trade_id],
                            "tp": None,
                            "size": trade.size,
                        })
                    del self.trailing_stops[trade_id]

            else:
                trail_level = self.data.Close[-1] + (self.trailing_sl * atr)

                if (self.data.Close[-1] < trade.entry_price * 0.995) and (trail_level < self.trailing_stops[trade_id]):
                    self.trailing_stops[trade_id] = trail_level

                # Check if price hit trailing stop
                if self.data.High[-1] > self.trailing_stops[trade_id]:
                    trade.close()
                    if _strategy_parameters and _strategy_parameters.get('best', False):
                        self.trades_actions.append({
                            "datetime": self.data.index[-1].strftime('%Y-%m-%d %H:%M:%S.%f'),
                            "trade_action": "close_trail_sl",
                            "entry_price": trade.entry_price,
                            "price": self.trailing_stops[trade_id],
                            "sl": self.trailing_stops[trade_id],
                            "tp": None,
                            "size": trade.size,
                        })
                    del self.trailing_stops[trade_id]

            # RSI-based exit signals
            if trade.is_long and self.data.RSI[-1] >= 85:
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
                if trade_id in self.trailing_stops:
                    del self.trailing_stops[trade_id]

            elif trade.is_short and self.data.RSI[-1] <= 15:
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
                if trade_id in self.trailing_stops:
                    del self.trailing_stops[trade_id]

        # Check if we can open new positions
        if len(self.trades) >= self.max_positions:
            return

        # Entry signals
        current_price = self.data.Close[-1]

        # Calculate position size based on risk percentage and ATR
        current_volatility = max(self.volatility[-1], 1.0)
        vol_factor = min(max(15.0 / current_volatility, 0.5), 2.0)

        account_value = self.equity
        risk_amount = account_value * (self.max_risk_pct / 100)

        # Signal 2 = Buy signal (long)
        if self.signal == 2 and len([t for t in self.trades if t.is_long]) == 0:
            sl_price = current_price - sl_distance
            tp_price = current_price + tp_distance

            # Sanity check for stop loss distance
            if current_price - sl_price < (current_price * 0.001):
                sl_price = current_price * 0.999

            # Calculate position size
            dollar_risk_per_unit = abs(current_price - sl_price)
            if dollar_risk_per_unit > 0:
                pos_size = (risk_amount / dollar_risk_per_unit) * vol_factor
                pos_size = min(pos_size, self.base_lot_size * 2.0)
                pos_size = max(pos_size, self.base_lot_size * 0.5)
            else:
                pos_size = self.base_lot_size

            self.buy(sl=sl_price, tp=tp_price, size=pos_size)

            if _strategy_parameters and _strategy_parameters.get('best', False):
                self.trades_actions.append({
                    "datetime": self.data.index[-1].strftime('%Y-%m-%d %H:%M:%S.%f'),
                    "trade_action": "buy",
                    "entry_price": current_price,
                    "price": current_price,
                    "sl": sl_price,
                    "tp": tp_price,
                    "size": pos_size,
                })

        # Signal 1 = Sell signal (short)
        elif self.signal == 1 and len([t for t in self.trades if t.is_short]) == 0:
            sl_price = current_price + sl_distance
            tp_price = current_price - tp_distance

            # Sanity check for stop loss distance
            if sl_price - current_price < (current_price * 0.001):
                sl_price = current_price * 1.001

            # Calculate position size
            dollar_risk_per_unit = abs(current_price - sl_price)
            if dollar_risk_per_unit > 0:
                pos_size = (risk_amount / dollar_risk_per_unit) * vol_factor
                pos_size = min(pos_size, self.base_lot_size * 2.0)
                pos_size = max(pos_size, self.base_lot_size * 0.5)
            else:
                pos_size = self.base_lot_size

            self.sell(sl=sl_price, tp=tp_price, size=pos_size)

            if _strategy_parameters and _strategy_parameters.get('best', False):
                self.trades_actions.append({
                    "datetime": self.data.index[-1].strftime('%Y-%m-%d %H:%M:%S.%f'),
                    "trade_action": "sell",
                    "entry_price": current_price,
                    "price": current_price,
                    "sl": sl_price,
                    "tp": tp_price,
                    "size": pos_size,
                })


def backtest(df, strategy_parameters, size=0.01, skip_optimization=False, best_params=None):
    """
    Run backtest for the super safe strategy.

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
        print("super_safe_strategy backtest: df is None or empty")
        return None, None, [], {}

    dftest = df.copy()

    # Pre-calculate volatility
    dftest['returns'] = dftest.Close.pct_change()
    vol_window = strategy_parameters.get('vol_lookback', 20)
    dftest['volatility'] = dftest['returns'].rolling(window=vol_window).std() * np.sqrt(252) * 100
    dftest['volatility'] = dftest['volatility'].fillna(method='ffill').fillna(15.0)

    _dftest = dftest
    _strategy_parameters = strategy_parameters

    # Default backtest parameters
    margin = 1/100
    cash = 100000
    base_lot_size = size

    # Set initial class attributes from parameters
    SuperSafeStrategy.slcoef = strategy_parameters.get("slcoef", 3.0)
    SuperSafeStrategy.TPSLRatio = strategy_parameters.get("tpslRatio", 2.5)
    SuperSafeStrategy.trailing_sl = strategy_parameters.get("trailing_sl", 2.0)
    SuperSafeStrategy.max_positions = strategy_parameters.get("max_positions", 1)
    SuperSafeStrategy.max_risk_pct = strategy_parameters.get("max_risk_pct", 1.0)
    SuperSafeStrategy.min_atr_value = strategy_parameters.get("min_atr_value", 0.0001)
    SuperSafeStrategy.trades_actions = []
    SuperSafeStrategy.mysize = base_lot_size
    SuperSafeStrategy.base_lot_size = base_lot_size

    # Optimization logic
    if not skip_optimization and best_params is None:
        print("Optimizing super_safe_strategy...")
        bt = Backtest(dftest, SuperSafeStrategy, cash=cash, margin=margin, finalize_trades=True)

        stats, heatmap = bt.optimize(
            slcoef=[2.0, 4.0, 8.0, 12.0, 16.0, 20.0],
            TPSLRatio=[1.5, 2.0, 2.5, 3.0, 3.5, 4.0],
            trailing_sl=[1.5, 2.0, 2.5, 3.0, 3.5],
            max_positions=[1, 2],
            max_risk_pct=[0.5, 1.0, 1.5, 2.0],
            min_atr_value=[0.0001, 0.0005, 0.001],
            maximize="Sharpe Ratio",
            max_tries=300,
            random_state=0,
            return_heatmap=True,
        )

        # Find best parameters
        try:
            heatmap_df = heatmap.unstack()
            heatmap_df = heatmap_df.fillna(-999)
            max_value = heatmap_df.max().max()

            best_params = {}
            best_opt_params = bt._optimizer.best_params
            for param, value in best_opt_params.items():
                best_params[param] = value

            print(f"Best parameters found: {best_params}")
        except Exception as e:
            print(f"Error finding optimum parameters: {e}")
            best_params = {
                'slcoef': 4.0,
                'TPSLRatio': 3.0,
                'trailing_sl': 2.5,
                'max_positions': 1,
                'max_risk_pct': 1.0,
                'min_atr_value': 0.0005
            }
            print(f"Using fallback parameters: {best_params}")
    elif best_params is None:
        best_params = {
            'slcoef': 4.0,
            'TPSLRatio': 3.0,
            'trailing_sl': 2.5,
            'max_positions': 1,
            'max_risk_pct': 1.0,
            'min_atr_value': 0.0005
        }
        print("Using default parameters:", best_params)
    else:
        print("Optimization is skipped and best params provided:", best_params)

    # Set final strategy parameters
    strategy_parameters = {"best": True}
    for key, value in best_params.items():
        strategy_parameters[key] = value

    print(f"Running with parameters: {strategy_parameters}")

    # Update strategy parameters
    SuperSafeStrategy.slcoef = strategy_parameters.get("slcoef", 3.0)
    SuperSafeStrategy.TPSLRatio = strategy_parameters.get("TPSLRatio", 2.5)
    SuperSafeStrategy.trailing_sl = strategy_parameters.get("trailing_sl", 2.0)
    SuperSafeStrategy.max_positions = strategy_parameters.get("max_positions", 1)
    SuperSafeStrategy.max_risk_pct = strategy_parameters.get("max_risk_pct", 1.0)
    SuperSafeStrategy.min_atr_value = strategy_parameters.get("min_atr_value", 0.0001)

    # Update global
    _strategy_parameters = strategy_parameters

    # Run final backtest
    bt_best = Backtest(dftest, SuperSafeStrategy, cash=cash, margin=margin, finalize_trades=True)
    stats = bt_best.run()
    trades_actions = bt_best._strategy.trades_actions

    return bt_best, stats, trades_actions, strategy_parameters
