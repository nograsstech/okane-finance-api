import yfinance as yf
from app.base.utils.mongodb import connect_mongodb, COLLECTIONS
from starlette.status import HTTP_200_OK
from app.signals.utils.yfinance import getYFinanceData
from app.signals.strategies.calculate import calculate_signals
from app.signals.strategies.ema_bollinger_backtest import backtest
import json
import os


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
        return {
            "status": 400,
            "message": f"Failed to fetch data from Yahoo Finance. Error: {e}",
        }
        
    signals_df = None
    try:
        signals_df = await calculate_signals(df, strategy, parameters)
    except Exception as e:
        return {
            "status": 400,
            "message": f"Failed to calculate signals. Error: {e}",
        }
        
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


async def get_backtest_result(
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
    df = None
    try:
        df = getYFinanceData(ticker, interval, period, start, end);
    except Exception as e:
        return {
            "status": 400,
            "message": f"Failed to fetch data from Yahoo Finance. Error: {e}",
        }
        
    signals_df = None
    try:
        signals_df = await calculate_signals(df, strategy, parameters)
    except Exception as e:
        return {
            "status": 400,
            "message": f"Failed to calculate signals. Error: {e}",
        }
    
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

    return {
        "status": HTTP_200_OK,
        "message": "Backtest results",
        "data": {
            "ticker": ticker,
            "stats": {
                "max_drawdown_percentage": stats["Max. Drawdown [%]"],
                "start": stats["Start"],
                "end": stats["End"],
                "duration": stats["Duration"],
                "duration": stats["Duration"],
                "exposure_time_percentage": stats["Exposure Time [%]"],
                "final_equity": stats["Equity Final [$]"],
                "peak_equity": stats["Equity Peak [$]"],
                "return": stats["Return [%]"],
                "buy_and_hold_return": stats["Buy & Hold Return [%]"],
                "return_annualizecd": stats["Return (Ann.) [%]"],
                "volatility_annualized": stats["Volatility (Ann.) [%]"],
                "sharpe_ratio": stats["Sharpe Ratio"],
                "sortino_ratio": stats["Sortino Ratio"],
                "calmar_ratio": stats["Calmar Ratio"],
                "max_drawdown_percentage": stats["Max. Drawdown [%]"],
                "average_drawdown_percentage": stats["Avg. Drawdown [%]"],
                "max_drawdown_duration": stats["Max. Drawdown Duration"],
                "average_drawdown_duration": stats["Avg. Drawdown Duration"],
                "trade_count": stats["# Trades"],
                "win_rate": stats["Win Rate [%]"],
                "best_trade": stats["Best Trade [%]"],
                "worst_trade": stats["Worst Trade [%]"],
                "avg_trade": stats["Avg. Trade [%]"],
                "max_trade_duration": stats["Max. Trade Duration"],
                "average_trade_duration": stats["Avg. Trade Duration"],
                "profit_factor": stats["Profit Factor"],
            },
            "html": html_content
        },
    }
    

        
    
        
    