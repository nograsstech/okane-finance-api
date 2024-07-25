from .ema_bollinger_backtest import backtest as ema_bollinger_backtest
from .ema_bollinger_1_low_risk_backtest import backtest as ema_bollinger_1_low_risk_backtest
from .macd_1_backtest import backtest as macd_1_backtest
from fastapi import HTTPException

def perform_backtest(df, strategy, parameters, skip_optimization=False, best_params=None):
    print(strategy)
    try:
        if strategy == "ema_bollinger":
            return ema_bollinger_backtest(df, parameters, parameters['size'], skip_optimization, best_params)
        if strategy == "ema_bollinger_1_low_risk":
            return ema_bollinger_1_low_risk_backtest(df, parameters, parameters['size'], skip_optimization, best_params)
        elif strategy == "macd_1":
            return macd_1_backtest(df, parameters, parameters['size'], skip_optimization, best_params)
        else:
            raise HTTPException(status_code=404, detail="Not found")
    except Exception as e:
        print("ERROR__________________")
        print(e)
        return None


async def perform_backtest_async(df, strategy, parameters):
    print(strategy)
    if strategy == "ema_bollinger":
        return ema_bollinger_backtest(df, parameters, parameters['size'])
    if strategy == "ema_bollinger_1_low_risk":
        return ema_bollinger_1_low_risk_backtest(df, parameters, parameters['size'])
    elif strategy == "macd_1":
        return macd_1_backtest(df, parameters, parameters['size'])
    else:
        raise HTTPException(status_code=404, detail="Not found")
