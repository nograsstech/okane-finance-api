"""
Predefined Trade Strategy for backtest replay.

This strategy executes trades that were previously stored in the database,
allowing for replay of backtests with fresh historical price data.
"""

import multiprocessing as mp

import pandas as pd
from backtesting import Backtest, Strategy

if mp.get_start_method(allow_none=True) != 'fork':
    mp.set_start_method('fork', force=True)


def backtest(df, trade_schedule, cash=100000, margin=1/500):
    """
    Run a backtest with predefined trades.

    Args:
        df: DataFrame with OHLC data and datetime index
        trade_schedule: List of dicts with keys:
            - datetime: str (format: '%Y-%m-%d %H:%M:%S.%f' or '%Y-%m-%d %H:%M:%S')
            - trade_action: str ('buy', 'sell', 'close')
            - entry_price: float
            - price: float
            - sl: float | None
            - tp: float | None
            - size: float
        cash: Initial cash
        margin: Margin requirement

    Returns:
        (bt, stats, trade_actions, strategy_parameters)
    """
    dftest = df[:]

    # Ensure DataFrame index is timezone-naive
    if dftest.index.tz is not None:
        dftest.index = dftest.index.tz_localize(None)

    print(f"[REPLAY] DataFrame shape: {dftest.shape}")
    print(f"[REPLAY] DataFrame index range: {dftest.index.min()} to {dftest.index.max()}")
    print(f"[REPLAY] DataFrame index tzinfo: {dftest.index.tz}")
    print(f"[REPLAY] Trade schedule count: {len(trade_schedule)}")

    # Parse trade schedule datetimes and convert to pandas Timestamps
    # Ensure they are timezone-naive to match yfinance data
    parsed_schedule = []
    for trade in trade_schedule:
        dt_str = trade['datetime']
        try:
            dt = pd.to_datetime(dt_str, format='%Y-%m-%d %H:%M:%S.%f')
        except ValueError:
            dt = pd.to_datetime(dt_str, format='%Y-%m-%d %H:%M:%S')

        # Remove timezone info to match yfinance data (which is tz-naive)
        if dt.tz is not None:
            dt = dt.tz_localize(None)

        parsed_schedule.append({
            'datetime': dt,
            'trade_action': trade['trade_action'].lower(),
            'entry_price': trade['entry_price'],
            'price': trade['price'],
            'sl': trade.get('sl'),
            'tp': trade.get('tp'),
            'size': trade['size'],
        })

    # Sort by datetime
    parsed_schedule.sort(key=lambda x: x['datetime'])
    print(f"[REPLAY] Parsed {len(parsed_schedule)} trades")
    if parsed_schedule:
        print(f"[REPLAY] First trade: {parsed_schedule[0]['datetime']} (tz: {parsed_schedule[0]['datetime'].tz}) - {parsed_schedule[0]['trade_action']}")
        print(f"[REPLAY] Last trade: {parsed_schedule[-1]['datetime']} (tz: {parsed_schedule[-1]['datetime'].tz}) - {parsed_schedule[-1]['trade_action']}")

    class PredefinedTradeStrategy(Strategy):
        trades_actions = []
        executed_trades = set()

        def init(self):
            super().init()
            self.trade_schedule = parsed_schedule
            # Track which trades have been executed
            self.executed_trade_indices = set()

        def next(self):
            super().next()

            current_dt = self.data.index[-1]

            # Find trades that should be executed at or before this bar
            # Use a time window to account for timing differences
            for i, trade in enumerate(self.trade_schedule):
                if i in self.executed_trade_indices:
                    continue

                trade_dt = trade['datetime']

                # Check if this trade should be executed now
                # Execute if the trade datetime is within the time window of current bar
                # or if we've passed the trade time
                time_diff = (current_dt - trade_dt).total_seconds()

                # Execute if we're close to the trade time (within 2 intervals) or passed it
                # This handles cases where yfinance data doesn't have exact time matches
                if time_diff >= 0:
                    action = trade['trade_action']

                    if action == 'buy':
                        sl = trade['sl']
                        tp = trade['tp']
                        size = trade['size']

                        # Only buy if we don't have an open position
                        if len(self.trades) == 0:
                            # Try to execute with TP/SL, fall back to without if validation fails
                            try:
                                self.buy(sl=sl, tp=tp, size=size)
                                print(f"[REPLAY] BUY at {current_dt} - price: {self.data.Close[-1]:.5f}, size: {size}, SL: {sl}, TP: {tp}")
                            except ValueError as e:
                                if "require" in str(e).lower() or "tp" in str(e).lower() or "sl" in str(e).lower():
                                    print(f"[REPLAY] BUY at {current_dt} - Invalid TP/SL, executing without: {e}")
                                    self.buy(size=size)
                                else:
                                    raise

                            self.trades_actions.append({
                                "datetime": current_dt.strftime('%Y-%m-%d %H:%M:%S.%f'),
                                "trade_action": "buy",
                                "entry_price": self.data.Close[-1],
                                "price": self.data.Close[-1],
                                "sl": sl,
                                "tp": tp,
                                "size": size,
                            })

                    elif action == 'sell':
                        sl = trade['sl']
                        tp = trade['tp']
                        size = trade['size']

                        # Only sell if we don't have an open position
                        if len(self.trades) == 0:
                            # Try to execute with TP/SL, fall back to without if validation fails
                            try:
                                self.sell(sl=sl, tp=tp, size=size)
                                print(f"[REPLAY] SELL at {current_dt} - price: {self.data.Close[-1]:.5f}, size: {size}, SL: {sl}, TP: {tp}")
                            except ValueError as e:
                                if "require" in str(e).lower() or "tp" in str(e).lower() or "sl" in str(e).lower():
                                    print(f"[REPLAY] SELL at {current_dt} - Invalid TP/SL, executing without: {e}")
                                    self.sell(size=size)
                                else:
                                    raise

                            self.trades_actions.append({
                                "datetime": current_dt.strftime('%Y-%m-%d %H:%M:%S.%f'),
                                "trade_action": "sell",
                                "entry_price": self.data.Close[-1],
                                "price": self.data.Close[-1],
                                "sl": sl,
                                "tp": tp,
                                "size": size,
                            })

                    elif action == 'close':
                        # Close all open trades
                        for trade_obj in list(self.trades):
                            trade_obj.close()
                            print(f"[REPLAY] CLOSE at {current_dt} - price: {self.data.Close[-1]:.5f}")

                        self.trades_actions.append({
                            "datetime": current_dt.strftime('%Y-%m-%d %H:%M:%S.%f'),
                            "trade_action": "close",
                            "entry_price": None,
                            "price": self.data.Close[-1],
                            "sl": None,
                            "tp": None,
                            "size": None,
                        })

                    # Mark this trade as executed
                    self.executed_trade_indices.add(i)

    # Run the backtest
    bt = Backtest(dftest, PredefinedTradeStrategy, cash=cash, margin=margin)
    stats = bt.run()
    trades_actions = bt._strategy.trades_actions

    print(f"[REPLAY] Executed {len(trades_actions)} trades")
    print(f"[REPLAY] Trade count in stats: {stats['# Trades']}")

    strategy_parameters = {
        "replay": True,
        "trade_count": len(trade_schedule),
    }

    return bt, stats, trades_actions, strategy_parameters
