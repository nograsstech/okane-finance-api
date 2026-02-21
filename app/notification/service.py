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

def send_discord_notification(message: str) -> None:
    """
    Sends a message to a Discord channel.

    Args:
        message (str): The message to send.

    Returns:
        None
    """
    try:
        print("Sending Discord notification...", message)
        url = os.environ.get("DISCORD_WEBHOOK_URL")
        headers = {
            "Content-Type": "application/json",
        }
        data = {"content": message}
        requests.post(url, headers=headers, data=json.dumps(data))
        logging.info(f"Discord notification sent successfully.\nMessage: {message}")
    except Exception as e:
        print(f"Failed to send Discord notification. Error: {e}")
        raise HTTPException(
            status_code=400, detail=f"Failed to send Discord notification. Error: {e}"
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
    message_text = ""
    
    print(f"Sending trade action notification for {ticker} on {interval}...")
    print(f"Trade actions: {trade_actions}")

    for action in trade_actions:
        strategy_performance_url = f"{os.environ['OKANE_SIGNALS_URL']}/strategy/{action.backtest_id}"
        backtest_results_url = f"{os.environ['OKANE_SIGNALS_URL']}/strategy/{action.backtest_id}/backtest"
        
        if action.trade_action == "buy":
            content = f"🟢 BUY signal\n\n🧠 Strategy: {strategy} \n📈 Symbol: {ticker}\n⏰ Interval: {interval} \n⏱️Time: {action.datetime} (GMT) \n\nEntry: {str(action.entry_price)[0:7]} \nSize: {action.size} \nStop loss: {str(action.sl)[0:7]} \nTake Profit: {str(action.tp)[0:7]} \n\nStrategy: {strategy_performance_url} \nBacktest: {backtest_results_url}\n---\n"
            messages.append(
                {
                    "type": "text",
                    "text": content,
                }
            )
            message_text = message_text + content + "\n\n"
        elif action.trade_action == "sell":
            content = f"🔴 SELL signal\n\n🧠 Strategy: {strategy} \n📈 Symbol: {ticker}\n⏳ Interval: {interval} \n⏱️Time: {action.datetime} (GMT) \n\nEntry: {str(action.entry_price)[0:7]} \nSize: {action.size} \nStop loss: {str(action.sl)[0:7]} \nTake Profit: {str(action.tp)[0:7]} \n\nStrategy: {strategy_performance_url} \nBacktest: {backtest_results_url}\n---\n"
            messages.append(
                {
                    "type": "text",
                    "text": content,
                }
            )
            message_text = message_text + content + "\n\n"
        elif action.trade_action == "close":
            content = f"🟡 CLOSE signal\n\n🧠 Strategy: {strategy} \n📈 Symbol: {ticker}\n⏳ Interval: {interval} \n⏱️Time: {action.datetime} (GMT) \n\nEntry: {str(action.entry_price)[0:7]} \nSize: {action.size} \nClose Price: {str(action.price)[0:7]} \n\nStrategy: {strategy_performance_url} \nBacktest: {backtest_results_url}\n---\n"
            messages.append(
                {
                    "type": "text",
                    "text": content,
                }
            )
            message_text = message_text + content + "\n\n"

    send_discord_notification(message_text)
    return {
        "status": HTTP_200_OK,
        "message": "Trade actions sent successfully",
        "data": {
            "ticker": ticker,
            "interval": interval,
            "trade_actions": trade_actions,
        },
    }