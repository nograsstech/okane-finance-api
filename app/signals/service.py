"""Compatibility imports for the split signal service modules.

Routers and external callers may continue importing ``app.signals.service``.
New code should import the focused module under ``app.signals.services``.
"""

from app.executors import BACKTEST_EXECUTOR
from app.signals.services.backtests import get_backtest_result
from app.signals.services.replay import replay_backtest
from app.signals.services.results import safe_float
from app.signals.services.signals import get_signals
from app.signals.services.strategy_jobs import (
    get_strategies,
    strategy_notification_job,
)

__all__ = [
    "BACKTEST_EXECUTOR",
    "get_backtest_result",
    "get_signals",
    "get_strategies",
    "replay_backtest",
    "safe_float",
    "strategy_notification_job",
]
