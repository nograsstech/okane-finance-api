import yfinance as yf
from fastapi import APIRouter, Depends, BackgroundTasks
from fastapi import FastAPI, HTTPException
from app.base.utils.mongodb import connect_mongodb, COLLECTIONS
from starlette.status import HTTP_200_OK
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
import datetime

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
    df = None
    df1d = None
    try:
        df = await getYFinanceDataAsync(ticker, interval, period, start, end)
        if (strategy == "macd_1"):
            df1d = getYFinanceData(ticker, "1d", period, start, end)
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Failed to calculate signals. Error: {e}"
        )

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
    logging.info("get_backtest_result started")
    df = None
    df1d = None
    try:
        df = getYFinanceData(ticker, interval, period, start, end)
        if (strategy == "macd_1"):
            df1d = getYFinanceData(ticker, "1d", period, start, end)
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Failed to calculate signals. Error: {e}"
        )

    parameters_dict = json.loads(parameters)

    signals_df = None
    try:
        signals_df = calculate_signals(df, df1d, strategy, parameters_dict)
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Failed to calculate signals. Error: {e}"
        )

    bt, stats, heatmap, trade_actions = perform_backtest(
        signals_df,
        strategy,
        {
            "best": False,
            "size": 0.03,
            "slcoef": 2.2,
            "tpslRatio": 2.0,
            "max_longs": parameters_dict.get("max_longs", 1),
            "max_shorts": parameters_dict.get("max_shorts", 1),
        },
    )

    # Get the
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
        "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
    }
    if strategy_id != None:
        backtest_stats["id"] = strategy_id

    updated_backtest_stats = None
    try:
        logging.info(f"Saving backtest stats to the database. Ticker: {ticker}")
        if strategy_id != None:
            updated_backtest_stats = (
                supabase.table("backtest_stats").upsert(backtest_stats).execute()
            )
        else:
            updated_backtest_stats = (
                supabase.table("backtest_stats").insert([backtest_stats]).execute()
            )
    except Exception as e:
        logging.error(f"Failed to save backtest stats to the database. Error: {e}")

    # Add backtest_id to trade_actions
    # add the backtest_id
    try:
        for trade_action in trade_actions:
            # Add the backtest_stat id (foreign key) to the trade action
            if (
                updated_backtest_stats != None
                and updated_backtest_stats.data[0]["id"] != None
            ):
                trade_action["backtest_id"] = updated_backtest_stats.data[0]["id"]

    except Exception as e:
        logging.error(f"Failed to add backtest_id to trade_actions. Error: {e}")

    # Save trade actions to the database
    try:
        logging.info(f"Saving trade actions to the database. Ticker: {ticker}")
        print("--- Inserting Trade Actions to DB")
        print(trade_actions)
        trade_actions = supabase.table("trade_actions").insert(trade_actions).execute()
        logging.info(f"Trade actions saved to the database.")
    except Exception as e:
        logging.error(f"Failed to save trade actions to the database. Error: {e}")

    # Send notifications for new trade actions
    if notifications_on:
        logging.info("Sending trade action notification to LINE group...")
        logging.info(trade_actions)
        try:
            send_trade_action_notification(
                strategy=strategy,
                ticker=ticker,
                interval=interval,
                trade_actions=trade_actions,
            )
        except Exception as e:
            logging.error(f"Failed to send LINE notification. Error: {e}")

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

    logging.info(response.data)

    for strategy in response.data:
        logging.info(
            f"Updating strategy backtest. Ticker: {strategy['ticker']}, Strategy: {strategy['strategy']}, Period: {strategy['period']}, Interval: {strategy['interval']}"
        )
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
            )
        except Exception as e:
            logging.error(f"Failed to send notification for strategy. Error: {e}")
