"""
Notification handling for trade actions.

Handles sending trade action notifications via configured channels (Discord, LINE, etc.).
Extracted from service.py for better separation of concerns.
"""
import logging

from app.notification.service import send_trade_action_notification


def handle_trade_action_notifications(
    strategy: str,
    ticker: str,
    interval: str,
    notifications_on: bool,
    trade_actions: list,
) -> None:
    """
    Send notifications for trade actions if enabled.

    Args:
        strategy: Strategy name
        ticker: Trading symbol
        interval: Time interval
        notifications_on: Whether notifications are enabled
        trade_actions: List of trade action dictionaries to notify about
    """
    if not notifications_on or not trade_actions:
        if not notifications_on:
            print("Notifications disabled for this strategy (notifications_on=False).")
        if not trade_actions:
            print("No trade actions to notify about.")
        return

    print(f"Sending trade action notification for {len(trade_actions)} actions...")
    try:
        send_trade_action_notification(
            strategy=strategy,
            ticker=ticker,
            interval=interval,
            trade_actions=trade_actions,
        )
        print("Trade action notification sent successfully.")
    except ValueError as e:
        logging.error(f"Configuration error for notification: {e}")
        print(f"ERROR: Notification not configured - {e}")
    except Exception as e:
        logging.error(f"Failed to send notification. Error: {e}", exc_info=True)
        print(f"ERROR: Failed to send notification - {e}")
