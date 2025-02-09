import zlib
import yfinance as yf
from fastapi import APIRouter, Depends, BackgroundTasks
from fastapi import FastAPI, HTTPException
from app.base.utils.mongodb import connect_mongodb, COLLECTIONS
from starlette.status import HTTP_200_OK
from app.lib.utils.pako import pako_deflate
from app.signals.utils.yfinance import getYFinanceData, getYFinanceDataAsync
from app.signals.utils.signals import get_latest_signal, get_all_signals
from app.signals.strategies.calculate import calculate_signals, calculate_signals_async

# from app.signals.strategies.ema_bollinger_backtest import backtest
from app.signals.strategies.perform_backtest import perform_backtest
from utils.supabase_client import supabase
from app.notification.service import send_trade_action_notification
from app.signals.dto import SignalRequestDTO
from concurrent.futures import ThreadPoolExecutor
from typing import List
import json
import os
import logging
import asyncio
from datetime import datetime, timezone, timedelta
import urllib.parse
import base64

executor = ThreadPoolExecutor(max_workers=5)


def run_in_executor(func, *args, **kwargs):
    def wrapper():
        return func(*args, **kwargs)

    loop = asyncio.new_event_loop()
    return asyncio.ensure_future(loop.run_in_executor(executor, wrapper))


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
    
    try:
        # Fetch data from Yahoo Finance
        df = None
        df1d = None
        try:
            df = await getYFinanceDataAsync(ticker, interval, period, start, end)
            
            # Special adjustments for different strategies
            if (strategy == "macd_1"):
                df1d = getYFinanceData(ticker, "1d", period, start, end)
                
            # ...
            
            
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Failed to calculate signals. Error: {e}"
            )

        # Calculate signals
        signals_df = None
        try:
            signals_df = await calculate_signals_async(df, df1d, strategy, parameters)
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Failed to calculate signals. Error: {e}"
            )
        current_signal = signals_df.iloc[-1]
        current_signal = json.loads(current_signal.to_json())

        # Get the latest signal
        latest_signal = get_latest_signal(signals_df)

        # All Signals
        all_signals = get_all_signals(signals_df)

        return {
            "status": HTTP_200_OK,
            "message": "Signals",
            "data": {
                "ticker": ticker,
                "period": period,
                "interval": interval,
                "strategy": strategy,
                "signals": {
                    "latest_signal": latest_signal,
                    "all_signals": all_signals,
                },
            },
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to get signals. Error: {e}")
        


def get_backtest_result(
    ticker,
    interval,
    period,
    strategy,
    parameters,
    start=None,
    end=None,
    strategy_id=None,
    backtest_process_uuid=None,
    notifications_on=False,
    skip_optimization=False,
    best_params=None,
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
        strategy_id (str, optional): The ID of the strategy. Defaults to None.
        backtest_process_uuid (str, optional): The UUID of the backtest process. Defaults to None.

    Returns:
        dict: A dictionary containing the backtest results.

    Raises:
        Exception: If there is an error fetching data from Yahoo Finance or calculating signals.

    """
    print(f"\n--- BACKTEST BEGINS --\n--- Start backtest for {ticker} ---\n")
    print(f"Interval: {interval}")
    print(f"Period: {period}")
    print(f"Strategy: {strategy}")
    print(f"Parameters: {json.dumps(parameters, indent=4)}")
    if start:
        print(f"Start Date: {start}")
    if end:
        print(f"End Date: {end}")
        
    
    df = None
    df1d = None
    try:
        df = getYFinanceData(ticker, interval, period, start, end)
        if (strategy == "macd_1"):
            df1d = getYFinanceData(ticker, "1d", period, start, end)
    except Exception as e:
        print(e)
        raise HTTPException(
            status_code=400, detail=f"Failed to calculate signals. Error: {e}"
        )

    try:
        print("Parameters: ", parameters)
        if parameters is not None:
            parameters_dict = json.loads(parameters)
    except Exception as e:
        print(e)
        raise HTTPException(
            status_code=400, detail=f"Failed to parse parameters. Error: {e}"
        )

    print(f"\n--- Calculating signals ---\n")
    signals_df = None
    try:
        signals_df = calculate_signals(df, df1d, strategy, parameters_dict)
    except Exception as e:
        print("calculate_signals: ERROR: ", e)
        raise HTTPException(
            status_code=400, detail=f"Failed to calculate signals. Error: {e}"
        )
        
    size = 0.03
    if (ticker == "BTC-USD"):
        size = 0.01  

    bt, stats, trade_actions, strategy_parameters = perform_backtest(
        signals_df,
        strategy,
        {
            "best": False,
            "size": size,
            "slcoef": 2.2,
            "tpslRatio": 2.0,
            "max_longs": parameters_dict.get("max_longs", 1),
            "max_shorts": parameters_dict.get("max_shorts", 1),
        },
        skip_optimization,
        best_params,
    )

    print(f"\n--- Creating backtest result HTML ---\n")
    bt.plot(open_browser=False, filename="backtest.html")
    # Read the HTML content
    with open("backtest.html", "r") as file:
        html_content = file.read()
        # delete the html file
        file.close()
        os.remove("backtest.html")
    logging.info("get_backtest_result finished")

    print("Original trade actions")
    print(len(trade_actions))

    # add the backtest_id
    for trade_action in trade_actions:
        trade_action["backtest_id"] = strategy_id
        
    print(f"\n--- Saving Trade Actions ---\n")
    try:
        latest_trade_action = None
        if strategy_id != None:
            latest_trade_action = (
                supabase.table("trade_actions")
                .select("*")
                .eq("backtest_id", strategy_id)
                .order("datetime", desc=True)
                .limit(1)
                .execute()
            )
            print("----Latest Trade Action----")
            print(latest_trade_action)

            print("----New Trade Actions----")
            if len(latest_trade_action.data) > 0:
                # filter only records where the datetime is newer than latest_trade_action.data[0]['datetime']
                trade_actions = [
                    trade_action
                    for trade_action in trade_actions
                    if trade_action["datetime"]
                    > latest_trade_action.data[0]["datetime"]
                ]
            else:
                trade_actions = trade_actions[-1:]
        else:
            trade_actions = trade_actions[-1:]

        print(len(trade_actions))
    except Exception as e:
        logging.error(
            f"Failed to get the latest trade action from the database. Error: {e}"
        )

    ### Saving data to the database ###
    print ("\n--- Saving data to DB ---\n")
    # Save backtest stats to the database
    backtest_stats = {
        "ticker": ticker,
        "max_drawdown_percentage": round(float(stats["Max. Drawdown [%]"]), 3),
        "start_time": stats["Start"].strftime("%Y-%m-%d %H:%M:%S.%f"),
        "end_time": stats["End"].strftime("%Y-%m-%d %H:%M:%S.%f"),
        "duration": str(stats["Duration"]),
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
        "max_drawdown_duration": str(stats["Max. Drawdown Duration"]),
        "average_drawdown_duration": str(stats["Avg. Drawdown Duration"]),
        "trade_count": stats["# Trades"],
        "win_rate": round(float(stats["Win Rate [%]"]), 3),
        "best_trade": round(float(stats["Best Trade [%]"]), 3),
        "worst_trade": round(float(stats["Worst Trade [%]"]), 3),
        "avg_trade": round(float(stats["Avg. Trade [%]"]), 3),
        "max_trade_duration": str(stats["Max. Trade Duration"]),
        "average_trade_duration": str(stats["Avg. Trade Duration"]),
        "profit_factor": round(float(stats["Profit Factor"]), 3),
        "html": html_content,
        "strategy": strategy,
        "period": period,
        "interval": interval,
        "ref_id": backtest_process_uuid,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
        "last_optimized_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
        "tpsl_ratio": round(float(strategy_parameters.get("tpslRatio", None)), 3) if strategy_parameters.get("tpslRatio") not in [None, ""] else None,
        "sl_coef": round(float(strategy_parameters.get("slcoef", None)), 3) if strategy_parameters.get("slcoef") not in [None, ""] else None,
        "tp_coef": round(float(strategy_parameters.get("TPcoef", None)), 3) if strategy_parameters.get("TPcoef") not in [None, ""] else None,
    }
    
    # Defalt the HTML content to save bandwidth and storage
    try:
        # Convert to bytes
        html_bytes = html_content.encode('utf-8')
        # Compress with zlib (default DEFLATE format)
        compressed_data = zlib.compress(html_bytes, level=9)
        # Encode in base64 for transmission
        backtest_stats["html"] = base64.b64encode(compressed_data).decode('utf-8')
    except Exception as e: 
        logging.error("Failed to deflate the HTML content", e)
        
    # Enable notification if sharpe_ratio is positive and return_percentage is positive
    if backtest_stats["sharpe_ratio"] > 0 and backtest_stats["return_percentage"] > 0:
        backtest_stats["notifications_on"] = True
        notifications_on = True
    else: 
        backtest_stats["notifications_on"] = False
        notifications_on = False
    
    if strategy_id != None:
        backtest_stats["id"] = strategy_id

    updated_backtest_stats = None
    try:
        logging.info(f"Saving backtest stats to the database. Ticker: {ticker}")
        if strategy_id != None:
            updated_backtest_stats = (
                supabase.table("backtest_stats").upsert(backtest_stats, returning='minimal').execute()
            )
        else:
            updated_backtest_stats = (
                supabase.table("backtest_stats").insert([backtest_stats], returning='minimal').execute()
            )
    except Exception as e:
        logging.error(f"Failed to save backtest stats to the database. Error: {e}")

    # Add backtest_id to trade_actions
    # add the backtest_id
    try:
        if updated_backtest_stats and updated_backtest_stats.data:
            for trade_action in trade_actions:
                print("\n\n")
                print(trade_action, "\n\n")
                # Add the backtest_stat id (foreign key) to the trade action
                if updated_backtest_stats.data[0]["id"] is not None:
                    trade_action["backtest_id"] = updated_backtest_stats.data[0]["id"]
        else:
            logging.error("updated_backtest_stats or updated_backtest_stats.data is empty")

    except Exception as e:
        logging.error(f"Failed to add backtest_id to trade_actions. Error: {e}")

    # Save trade actions to the database
    print(f"\n--- Saving trade actions to DB ---\n")
    try:
        logging.info(f"Saving trade actions to the database. Ticker: {ticker}")
        print("--- Inserting Trade Actions to DB")
        print(trade_actions)
        if (len(trade_actions) > 0):
            trade_actions = supabase.table("trade_actions").insert(trade_actions).execute()
            print(f"Trade actions saved to the database.")
    except Exception as e:
        logging.error(f"Failed to save trade actions to the database. Error: {e}")

    # Send notifications for new trade actions
    print(f"\n--- Sending trade action notifications ---\n")
    if notifications_on & hasattr(trade_actions, 'data'):
        print("Sending trade action notification to LINE group...")
        print(trade_actions)
        try:
            send_trade_action_notification(
                strategy=strategy,
                ticker=ticker,
                interval=interval,
                trade_actions=trade_actions,
            )
        except Exception as e:
            logging.error(f"Failed to send LINE notification. Error: {e}")

    print(f"\n--- COMPLETE ---\n")
    
    # Return the response. No longer need to send the HTML payload since it will be saved to DB.
    # Just return the id of those records
    return {
        "status": HTTP_200_OK,
        "message": "Backtest results",
        "data": backtest_process_uuid,
    }


def strategy_notification_job():
    """
    Send a notification for the specified strategies.

    Args:
        strategy_id_list (List[SignalRequestDTO]): A list of strategy IDs for which to send notifications.

    Returns:
        None

    -- Supabase AI is experimental and may produce incorrect answers
    -- Always verify the output before executing

    """
    # Perform the inner query
    query = supabase.table("unique_strategies").select("*")
    response = query.execute()

    print("--------------------------------------")
    print("Preparing to run backtests and send signal notification if available. \nSignal for: ", response.data)
    print("--------------------------------------")
    logging.info(response.data)

    for strategy in response.data:
        logging.info(
            f"Updating strategy backtest. Ticker: {strategy['ticker']}, Strategy: {strategy['strategy']}, Period: {strategy['period']}, Interval: {strategy['interval']}"
        )
        
        # Check the strategy["last_optimized_at"] and compare it with the current time. If the difference is greater than 5 days, re-optimize.
        singapore_tz = timezone(timedelta(hours=8))
        last_optimized_at = datetime.strptime(strategy["last_optimized_at"], "%Y-%m-%dT%H:%M:%S.%f%z")
        current_time = datetime.now(singapore_tz)
        time_difference = (current_time - last_optimized_at).days
        print("Skip optimization: ", time_difference < 3)

        # Send a notification for the strategy
        try:
            get_backtest_result(
                ticker=strategy["ticker"],
                interval=strategy["interval"],
                period=strategy["period"],
                strategy=strategy["strategy"],
                parameters='{"max_longs": 2, "max_shorts": 2}', # temporary
                start=None,
                end=None,
                strategy_id=strategy["id"],
                notifications_on=strategy["notifications_on"],
                skip_optimization=time_difference < 3, # Reoptimize every 3 days
                best_params={
                    "tpslRatio": strategy['tpsl_ratio'],
                    "slcoef": strategy['sl_coef'],
                    "TPcoef": strategy['tp_coef']
                },
            )
        except Exception as e:
            logging.error(f"Failed to send notification for strategy. Error: {e}")
