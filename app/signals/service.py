import yfinance as yf
from fastapi import FastAPI, HTTPException
from app.base.utils.mongodb import connect_mongodb, COLLECTIONS
from starlette.status import HTTP_200_OK
from app.signals.utils.yfinance import getYFinanceData
from app.signals.strategies.calculate import calculate_signals
from app.signals.strategies.ema_bollinger_backtest import backtest
import json
import os
import logging
logging.basicConfig(level=logging.INFO)

async def get_signals(
    ticker, interval, period, strategy, parameters, start=None, end=None
):
    """
    Retrieves signals for a given ticker using the specified parameters.

    Args:
        ticker (str): The ticker symbol of the stock.
        interval (str): The time interval for the stock data (e.g., '1d' for daily).
        period (str): The time period for the stock data (e.g., '1y' for 1 year).
        strategy (str): The strategy to use for signal calculation.
        parameters (dict): The parameters required for the specified strategy.
        start (str, optional): The start date for the stock data. Defaults to None.
        end (str, optional): The end date for the stock data. Defaults to None.

    Returns:
        dict: A dictionary containing the status, message, and data of the signals.

    Raises:
        Exception: If there is an error fetching data from Yahoo Finance or calculating signals.
    """
    df = None
    try:
        df = getYFinanceData(ticker, interval, period, start, end);
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch data from Yahoo Finance. Error: {e}")
        
    signals_df = None
    try:
        signals_df = await calculate_signals(df, strategy, parameters)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to calculate signals. Error: {e}")
        
    current_signal = signals_df.iloc[-1]
    current_signal = json.loads(current_signal.to_json())
    
    if current_signal == 2:
        return {
            "status": HTTP_200_OK,
            "message": "Buy",
            "data": {"ticker": ticker, "signal": current_signal},
        }
    elif current_signal == 1:
        return {
            "status": HTTP_200_OK,
            "message": "Sell",
            "data": {"ticker": ticker, "signal": current_signal},
        }
    else:
        return {
            "status": HTTP_200_OK,
            "message": "No signals",
            "data": {"ticker": ticker, "signal": current_signal},
        }


def get_backtest_result(
    ticker, interval, period, strategy, parameters, start=None, end=None
):
    """
    Get the backtest result for a given ticker, interval, period, strategy, and parameters.

    Args:
        ticker (str): The ticker symbol of the asset.
        interval (str): The time interval for the data (e.g., '1d' for daily, '1h' for hourly).
        period (str): The period of data to fetch (e.g., '1y' for 1 year, '3mo' for 3 months).
        strategy (str): The name of the strategy to use for backtesting.
        parameters (dict): The parameters specific to the strategy.
        start (str, optional): The start date of the backtest period (YYYY-MM-DD). Defaults to None.
        end (str, optional): The end date of the backtest period (YYYY-MM-DD). Defaults to None.

    Returns:
        dict: A dictionary containing the backtest results.

    Raises:
        Exception: If there is an error fetching data from Yahoo Finance or calculating signals.

    """
    print("I am running the backtest")
    logging.info("get_backtest_result started")
    df = None
    try:
        df = getYFinanceData(ticker, interval, period, start, end);
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to calculate signals. Error: {e}")
        
    signals_df = None
    try:
        signals_df = calculate_signals(df, strategy, parameters)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to calculate signals. Error: {e}")
    
    bt, stats, heatmap = backtest(signals_df, {
        "size": 0.03,
        "slcoef": 2.2,
        "tpslRatio": 2.0
    })
    
    # Get the 
    bt.plot(open_browser=False, filename="backtest.html")
     # Read the HTML content
    with open("backtest.html", "r") as file:
        html_content = file.read()
        # delete the html file
        file.close()
        os.remove("backtest.html")
    logging.info("get_backtest_result finished")
    return {
        "status": HTTP_200_OK,
        "message": "Backtest results",
        "data": {
            "ticker": ticker,
            "max_drawdown_percentage": round(float(stats["Max. Drawdown [%]"]), 3),
            "start_time": stats["Start"],
            "end_time": stats["End"],
            "duration": stats["Duration"],
            "exposure_time_percentage": round(float(stats["Exposure Time [%]"]), 3),
            "final_equity": round(float(stats["Equity Final [$]"]), 3),
            "peak_equity": round(float(stats["Equity Peak [$]"]), 3),
            "return_percentage": round(float(stats["Return [%]"]), 3),
            "buy_and_hold_return": round(float(stats["Buy & Hold Return [%]"]), 3),
            "return_annualized": round(float(stats["Return (Ann.) [%]"]), 3),
            "volatility_annualized": round(float(stats["Volatility (Ann.) [%]"]), 3),
            "sharpe_ratio": round(float(stats["Sharpe Ratio"]), 3),
            "sortino_ratio": round(float(stats["Sortino Ratio"]), 3),
            "calmar_ratio": round(float(stats["Calmar Ratio"]), 3),
            "max_drawdown_percentage": round(float(stats["Max. Drawdown [%]"]), 3),
            "average_drawdown_percentage": round(float(stats["Avg. Drawdown [%]"]), 3),
            "max_drawdown_duration": stats["Max. Drawdown Duration"],
            "average_drawdown_duration": stats["Avg. Drawdown Duration"],
            "trade_count": stats["# Trades"],
            "win_rate": round(float(stats["Win Rate [%]"]), 3),
            "best_trade": round(float(stats["Best Trade [%]"]), 3),
            "worst_trade": round(float(stats["Worst Trade [%]"]), 3),
            "avg_trade": round(float(stats["Avg. Trade [%]"]), 3),
            "max_trade_duration": stats["Max. Trade Duration"],
            "average_trade_duration": stats["Avg. Trade Duration"],
            "profit_factor": round(float(stats["Profit Factor"]), 3),
            "html": html_content
        },
    }
    

        
    
        
    