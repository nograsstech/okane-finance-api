from backtesting import Strategy
from backtesting import Backtest
import multiprocessing as mp
import numpy as np
import pandas as pd

if mp.get_start_method(allow_none=True) != 'fork':
    mp.set_start_method('fork', force=True)

def backtest(df, strategy_parameters, size = 0.01, skip_optimization=False, best_params=None):
    dftest = df.copy()
    
    # Pre-calculate volatility to avoid errors in backtesting
    # Calculate daily returns
    dftest['returns'] = dftest.Close.pct_change()
    # Calculate rolling volatility (annualized)
    vol_window = strategy_parameters.get('vol_lookback', 20)
    dftest['volatility'] = dftest['returns'].rolling(window=vol_window).std() * np.sqrt(252) * 100
    # Forward fill to handle NaN values
    dftest['volatility'] = dftest['volatility'].fillna(method='ffill').fillna(15.0)  # Default to 15% if no data
    
    # Trading parameters
    margin = 1/100
    cash = 100000
    base_lot_size = size
    
    def SIGNAL():
        return dftest.TotalSignal
    
    def VOLATILITY():
        return dftest.volatility

    class EnhancedStrategy(Strategy):
        # Strategy parameters with default values - increased defaults for wider stops
        slcoef = strategy_parameters.get("slcoef", 3.0)           # ATR multiplier for stop loss - increased from 2.0
        TPSLRatio = strategy_parameters.get("tpslRatio", 2.5)     # Take profit to stop loss ratio - increased from 2.0
        trailing_sl = strategy_parameters.get("trailing_sl", 2.0)  # Trailing stop ATR multiplier - increased from 1.5
        max_positions = strategy_parameters.get("max_positions", 1)  # Maximum concurrent positions
        max_risk_pct = strategy_parameters.get("max_risk_pct", 1.0)  # Maximum risk per trade (%)
        min_atr_value = strategy_parameters.get("min_atr_value", 0.0001)  # Minimum ATR value to prevent tiny stops
        trades_actions = []
        mysize = base_lot_size  # Match variable name from MyStrat for compatibility

        def init(self):
            super().init()
            self.signal = self.I(SIGNAL)    
            # Use pre-calculated volatility from dataframe
            self.volatility = self.I(VOLATILITY)
            
            # Keep track of our trailing stops
            self.trailing_stops = {}
            
        def next(self):
            super().next()
            
            # Skip if we have no price data
            if not len(self.data.Close):
                return
                
            # Calculate ATR-based stop distances with minimum value
            atr = max(self.data.ATR[-1], self.min_atr_value)
            sl_distance = self.slcoef * atr  # Wider stop loss distance
            tp_distance = sl_distance * self.TPSLRatio  # Wider take profit
            
            # Update trailing stops for open trades
            for trade in list(self.trades):
                trade_id = id(trade)
                
                # Compute dynamic position size based on volatility
                current_volatility = self.volatility[-1]
                base_volatility = 15.0  # Base volatility level
                vol_factor = min(max(base_volatility / current_volatility, 0.5), 2.0)
                
                # Initialize trailing stop if needed
                if trade_id not in self.trailing_stops:
                    if trade.is_long:
                        self.trailing_stops[trade_id] = trade.entry_price - sl_distance
                    else:
                        self.trailing_stops[trade_id] = trade.entry_price + sl_distance
                
                # Update trailing stop - only if profitable
                # For long trades, only trail if price has moved in our favor significantly
                if trade.is_long:
                    # Calculate potential trail level
                    trail_level = self.data.Close[-1] - (self.trailing_sl * atr)
                    
                    # Only update trailing stop if price has moved sufficiently above entry
                    # and the new trail level is above the current trail level
                    if (self.data.Close[-1] > trade.entry_price * 1.005) and (trail_level > self.trailing_stops[trade_id]):
                        self.trailing_stops[trade_id] = trail_level
                    
                    # Check if price hit trailing stop
                    if self.data.Low[-1] < self.trailing_stops[trade_id]:
                        trade.close()
                        if strategy_parameters.get('best', False):
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
                        
                # Short trade trailing stop handling - only if profitable
                else:  
                    # Calculate potential trail level
                    trail_level = self.data.Close[-1] + (self.trailing_sl * atr)
                    
                    # Only update trailing stop if price has moved sufficiently below entry
                    # and the new trail level is below the current trail level
                    if (self.data.Close[-1] < trade.entry_price * 0.995) and (trail_level < self.trailing_stops[trade_id]):
                        self.trailing_stops[trade_id] = trail_level
                    
                    # Check if price hit trailing stop
                    if self.data.High[-1] > self.trailing_stops[trade_id]:
                        trade.close()
                        if strategy_parameters.get('best', False):
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
                
                # RSI-based exit signals (matching MyStrat logic) but with more extreme values
                # to allow trades more room to breathe
                if trade.is_long and self.data.RSI[-1] >= 85:  # Increased from 80
                    trade.close()
                    if strategy_parameters.get('best', False):
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
                
                elif trade.is_short and self.data.RSI[-1] <= 15:  # Decreased from 20
                    trade.close()
                    if strategy_parameters.get('best', False):
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
            # Normalize for volatility
            current_volatility = max(self.volatility[-1], 1.0)  # Avoid division by zero
            vol_factor = min(max(15.0 / current_volatility, 0.5), 2.0)  # Target 15% annualized vol
            
            # Risk-based position sizing
            account_value = self.equity
            risk_amount = account_value * (self.max_risk_pct / 100)
            
            # Signal 2 = Buy signal (long)
            if self.signal == 2 and len([t for t in self.trades if t.is_long]) == 0:
                sl_price = current_price - sl_distance
                tp_price = current_price + tp_distance
                
                # Sanity check for stop loss distance
                if current_price - sl_price < (current_price * 0.001):  # Minimum 0.1% distance
                    sl_price = current_price * 0.999  # Enforce minimum distance
                
                # Calculate position size based on stop loss distance and risk
                dollar_risk_per_unit = abs(current_price - sl_price)
                if dollar_risk_per_unit > 0:
                    pos_size = (risk_amount / dollar_risk_per_unit) * vol_factor
                    pos_size = min(pos_size, base_lot_size * 2.0)  # Cap position size
                    pos_size = max(pos_size, base_lot_size * 0.5)  # Minimum position size
                else:
                    pos_size = base_lot_size
                
                self.buy(sl=sl_price, tp=tp_price, size=pos_size)
                
                if strategy_parameters.get('best', False):
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
                if sl_price - current_price < (current_price * 0.001):  # Minimum 0.1% distance
                    sl_price = current_price * 1.001  # Enforce minimum distance
                
                # Calculate position size based on stop loss distance and risk
                dollar_risk_per_unit = abs(current_price - sl_price)
                if dollar_risk_per_unit > 0:
                    pos_size = (risk_amount / dollar_risk_per_unit) * vol_factor
                    pos_size = min(pos_size, base_lot_size * 2.0)  # Cap position size
                    pos_size = max(pos_size, base_lot_size * 0.5)  # Minimum position size
                else:
                    pos_size = base_lot_size
                
                self.sell(sl=sl_price, tp=tp_price, size=pos_size)
                
                if strategy_parameters.get('best', False):
                    self.trades_actions.append({
                        "datetime": self.data.index[-1].strftime('%Y-%m-%d %H:%M:%S.%f'),
                        "trade_action": "sell",
                        "entry_price": current_price,
                        "price": current_price,
                        "sl": sl_price,
                        "tp": tp_price,
                        "size": pos_size,
                    })
    
    # Optimization logic with wider parameter ranges
    if not skip_optimization and best_params is None:
        print("Optimizing with wider stop-loss and take-profit parameters...")
        bt = Backtest(dftest, EnhancedStrategy, cash=cash, margin=margin)

        # Define optimization parameters with expanded ranges
        stats, heatmap = bt.optimize(
            # Expanded range for slcoef to allow wider stops
            slcoef=[2.0, 4.0, 8.0, 12.0, 16.0, 20.0],  # Much wider range
            # Wider range for TPSLRatio
            TPSLRatio=[1.5, 2.0, 2.5, 3.0, 3.5, 4.0],  # Extended upper limit
            # Wider range for trailing stops
            trailing_sl=[1.5, 2.0, 2.5, 3.0, 3.5],  # Extended upper limit
            max_positions=[1, 2],
            max_risk_pct=[0.5, 1.0, 1.5, 2.0],  # Added higher risk option
            # Added minimum ATR value to prevent tiny stops
            min_atr_value=[0.0001, 0.0005, 0.001],
            # Changed optimization metric to focus on overall performance
            # "Win Rate [%]" can sometimes lead to many small wins but big losses
            maximize="Sharpe Ratio",  # Better balance of risk/reward
            max_tries=300,
            random_state=0,
            return_heatmap=True,
        )
        
        # Convert multiindex series to dataframe
        heatmap_df = heatmap.unstack()
        
        # Find maximum value and its location
        try:
            # Fill NaN values to avoid issues finding the maximum
            heatmap_df = heatmap_df.fillna(-999)
            max_value = heatmap_df.max().max()
            
            # Find the optimal parameters
            best_params = {}
            # Direct match for params from optimization results
            best_opt_params = bt._optimizer.best_params
            for param, value in best_opt_params.items():
                best_params[param] = value
                
            print(f"Best parameters found: {best_params}")
        except Exception as e:
            print(f"Error finding optimum parameters: {e}")
            # Fallback with wider default parameters
            best_params = {
                'slcoef': 4.0,            # Increased from previous 2.5
                'TPSLRatio': 3.0,         # Increased from previous 2.0
                'trailing_sl': 2.5,       # Increased from previous 1.5
                'max_positions': 1,
                'max_risk_pct': 1.0,
                'min_atr_value': 0.0005   # Added minimum ATR value
            }
            print(f"Using fallback parameters: {best_params}")
    elif best_params is None:
        # Default parameters if neither optimization nor best_params provided
        # Using wider defaults than before
        best_params = {
            'slcoef': 4.0,            # Increased from previous 2.5
            'TPSLRatio': 3.0,         # Increased from previous 2.0
            'trailing_sl': 2.5,       # Increased from previous 1.5
            'max_positions': 1,
            'max_risk_pct': 1.0,
            'min_atr_value': 0.0005   # Added minimum ATR value
        }
        print("Using default parameters with wider stops:", best_params)
    else:
        print("Optimization is skipped and best params provided:", best_params)
    
    # Set final strategy parameters for best run
    strategy_parameters = {
        "best": True
    }
    
    # Add all best parameters to the strategy_parameters dict
    for key, value in best_params.items():
        strategy_parameters[key] = value
    
    print(f"Running with parameters: {strategy_parameters}")
    
    # Run final backtest with best parameters
    bt_best = Backtest(dftest, EnhancedStrategy, cash=cash, margin=margin)
    stats = bt_best.run(**{k: v for k, v in best_params.items() if k in 
                         ['slcoef', 'TPSLRatio', 'trailing_sl', 'max_positions', 
                          'max_risk_pct', 'min_atr_value']})
    trades_actions = bt_best._strategy.trades_actions
    
    # Return results in same format as MyStrat
    return bt_best, stats, trades_actions, strategy_parameters  