import logging
from typing import Any

import pandas as pd
from fastapi import HTTPException

from .clf_bollinger_rsi.clf_bollinger_rsi_backtest import backtest as clf_bollinger_rsi_backtest
from .clf_bollinger_rsi.clf_bollinger_rsi_backtest_15m import (
    backtest as clf_bollinger_rsi_backtest_15m,
)
from .clf_bollinger_rsi.eurjpy_bollinger_rsi_60m_backtest import (
    backtest as eurjpy_bollinger_rsi_60m_backtest,
)
from .double_candle.double_candle_backtest import backtest as double_candle_backtest
from .ema_bollinger.ema_bollinger_backtest import backtest as ema_bollinger_backtest
from .ema_bollinger_1_low_risk.ema_bollinger_1_low_risk_backtest import (
    backtest as ema_bollinger_1_low_risk_backtest,
)
from .five_min_orb.five_min_orb_backtest import backtest as five_min_orb_backtest
from .five_min_orb_confirmation.five_min_orb_confirmation_backtest import (
    backtest as five_min_orb_confirmation_backtest,
)
from .forex_fvg_respected.fvg_confirmation_backtest import backtest as fvg_confirmation_backtest
from .grid_trading.grid_trading_backtest import backtest as grid_trading_backtest
from .macd_1.macd_1_backtest import backtest as macd_1_backtest
from .mean_reversion_trend_filter.mean_reversion_trend_filter_backtest import (
    backtest as mean_reversion_trend_filter_backtest,
)
from .orb_autoresearch.orb_autoresearch_backtest import backtest as orb_autoresearch_backtest
from .super_safe_strategy.super_safe_strategy_backtest import (
    backtest as super_safe_strategy_backtest,
)
from .swing_1.swing_backtest import backtest as swing_1_backtest

logger = logging.getLogger(__name__)


def perform_backtest(
    df: pd.DataFrame,
    strategy: str,
    parameters: dict[str, Any],
    skip_optimization: bool = False,
    best_params: dict[str, Any] | None = None,
) -> tuple[Any, Any, list[dict[str, Any]], dict[str, Any]]:
    try:
        if strategy == "ema_bollinger":
            return ema_bollinger_backtest(
                df, parameters, parameters["size"], skip_optimization, best_params
            )
        if strategy == "ema_bollinger_1_low_risk":
            return ema_bollinger_1_low_risk_backtest(
                df, parameters, parameters["size"], skip_optimization, best_params
            )
        elif strategy == "macd_1":
            return macd_1_backtest(
                df, parameters, parameters["size"], skip_optimization, best_params
            )
        elif strategy == "clf_bollinger_rsi":
            return clf_bollinger_rsi_backtest(
                df, parameters, parameters["size"], skip_optimization, best_params
            )
        elif strategy == "clf_bollinger_rsi_15m":
            return clf_bollinger_rsi_backtest_15m(
                df, parameters, parameters["size"], skip_optimization, best_params
            )
        elif strategy == "eurjpy_bollinger_rsi_60m":
            return eurjpy_bollinger_rsi_60m_backtest(
                df, parameters, parameters["size"], skip_optimization, best_params
            )
        elif strategy == "grid_trading":
            return grid_trading_backtest(df, parameters, skip_optimization, best_params)
        elif strategy == "super_safe_strategy":
            return super_safe_strategy_backtest(
                df, parameters, parameters["size"], skip_optimization, best_params
            )
        elif strategy == "fvg_confirmation":
            return fvg_confirmation_backtest(
                df, parameters, parameters["size"], skip_optimization, best_params
            )
        elif strategy == "swing-1":
            return swing_1_backtest(
                df, parameters, parameters["size"], skip_optimization, best_params
            )
        elif strategy == "double_candle":
            return double_candle_backtest(
                df, parameters, parameters.get("size", 0.01), skip_optimization, best_params
            )
        elif strategy == "mean_reversion_trend_filter":
            return mean_reversion_trend_filter_backtest(
                df, parameters, parameters.get("size", 0.01), skip_optimization, best_params
            )
        elif strategy == "5_min_orb":
            return five_min_orb_backtest(
                df, parameters, parameters.get("size", 0.03), skip_optimization, best_params
            )
        elif strategy == "5_min_orb_confirmation":
            return five_min_orb_confirmation_backtest(
                df, parameters, parameters.get("size", 0.03), skip_optimization, best_params
            )
        elif strategy == "orb_autoresearch":
            return orb_autoresearch_backtest(
                df, parameters, parameters.get("size", 0.03), skip_optimization, best_params
            )
        else:
            raise HTTPException(status_code=404, detail="Not found")
    except Exception as exc:
        logger.error(
            "perform_backtest failed for strategy=%s: %s",
            strategy,
            exc,
            exc_info=True,
        )
        raise
