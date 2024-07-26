from typing import List
from fastapi import HTTPException
from app.signals.dto import TradeAction
from starlette.status import HTTP_200_OK
import requests
import json
import os
import logging


def send_line_notification(messages: List[str]) -> None:
    """
    Sends a message to a LINE group.

    Args:
        message (str): The message to send.

    Returns:
        None
    """
    try:
        url = "https://api.line.me/v2/bot/message/broadcast"
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + os.environ.get("LINE_SECRET"),
        }
        data = {"messages": messages}
        requests.post(url, headers=headers, data=json.dumps(data))
        logging.info(f"LINE notification sent successfully.\nMessages: {messages}")
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Failed to send LINE notification. Error: {e}"
        )


def send_trade_action_notification(
    strategy: str, ticker: str, interval: str, trade_actions
):
    """
    Sends a trade action notification to a LINE group.

    Args:
        trade_actions (TradeActions): The trade actions to send.

    Returns:
        None
    """
    messages = []
    
    print(f"Sending trade action notification for {ticker} on {interval}...")
    print(f"Trade actions: {trade_actions.data}")

    for action in trade_actions.data:
        strategy_performance_url = f"{os.environ['OKANE_SIGNALS_URL']}/strategy/{action['backtest_id']}"
        backtest_results_url = f"{os.environ['OKANE_SIGNALS_URL']}/strategy/{action['backtest_id']}/backtest"
        
        if action['trade_action'] == "buy":
            messages.append(
                {
                    "type": "text",
                    "text": f"🟢 BUY signal\n\n🧠 Strategy: {strategy} \n📈 Symbol: {ticker}\n⏰ Interval: {interval} \n⏱️Time: {action['datetime']} (GMT) \n\n--- \nEntry: {str(action['entry_price'])[0:7]} \nSize: {action['size']} \nStop loss: {str(action['sl'])[0:7]} \nTake Profit: {str(action['tp'])[0:7]} \n\nStrategy: {strategy_performance_url} \n\nBacktest: {backtest_results_url}",
                }
            )
        elif action['trade_action'] == "sell":
            messages.append(
                {
                    "type": "text",
                    "text": f"🔴 SELL signal\n\n🧠 Strategy: {strategy} \n📈 Symbol: {ticker}\n⏳ Interval: {interval} \n⏱️Time: {action['datetime']} (GMT) \n\n--- \nEntry: {str(action['entry_price'])[0:7]} \nSize: {action['size']} \nStop loss: {str(action['sl'])[0:7]} \nTake Profit: {str(action['tp'])[0:7]} \n\nStrategy: {strategy_performance_url} \n\nBacktest: {backtest_results_url}",
                }
            )
        elif action['trade_action'] == "close":
            messages.append(
                {
                    "type": "text",
                    "text": f"🟡 CLOSE signal\n\n🧠 Strategy: {strategy} \n📈 Symbol: {ticker}\n⏳ Interval: {interval} \n⏱️Time: {action['datetime']} (GMT) \n\n--- \nEntry: {str(action['entry_price'])[0:7]} \nSize: {action['size']} \nClose Price: {str(action['price'])[0:7]} \n\nStrategy: {strategy_performance_url} \n\nBacktest: {backtest_results_url}",
                }
            )

    send_line_notification(messages)
    return {
        "status": HTTP_200_OK,
        "message": "Trade actions sent successfully",
        "data": {
            "ticker": ticker,
            "interval": interval,
            "trade_actions": trade_actions,
        },
    }
