from __future__ import annotations

import base64
import html
import logging
import math
import tempfile
import zlib
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from app.signals.dto import BacktestStats

logger = logging.getLogger(__name__)


class BacktestPlot(Protocol):
    def plot(self, *, filename: str, **kwargs: Any) -> Any: ...


def safe_float(value: Any, default: float = 0.0, decimals: int = 3) -> float:
    """Convert a dynamic backtesting.py statistic to a finite rounded float."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(number) or math.isinf(number):
        return default
    return round(number, decimals)


def compress_html(content: str) -> str:
    compressed = zlib.compress(content.encode("utf-8"), level=9)
    return base64.b64encode(compressed).decode("utf-8")


def render_backtest_html(backtest: BacktestPlot, stats: Mapping[str, Any]) -> str:
    """Render a plot into a unique temporary file and return its HTML."""
    with tempfile.TemporaryDirectory(prefix="okane-backtest-") as directory:
        output = Path(directory) / "backtest.html"
        try:
            backtest.plot(open_browser=False, filename=str(output), superimpose=False)
        except Exception as first_error:
            logger.warning("Backtest plot with superimpose disabled failed: %s", first_error)
            try:
                backtest.plot(open_browser=False, filename=str(output))
            except Exception as second_error:
                logger.error("Backtest plot generation failed: %s", second_error)
                return (
                    "<html><head><title>Backtest Results</title></head><body>"
                    f"<h1>Backtest Results</h1><pre>{html.escape(str(stats))}</pre>"
                    f"<p>Plot generation failed: {html.escape(str(second_error))}</p>"
                    "</body></html>"
                )
        return output.read_text(encoding="utf-8")


def build_backtest_stats(
    *,
    ticker: str,
    stats: Mapping[str, Any],
    html_content: str,
    tpsl_ratio: Any = None,
    sl_coef: Any = None,
) -> BacktestStats:
    """Map backtesting.py's dynamic series into the stable API schema."""
    return BacktestStats(
        ticker=ticker,
        max_drawdown_percentage=safe_float(stats["Max. Drawdown [%]"]),
        start_time=stats["Start"].strftime("%Y-%m-%d %H:%M:%S.%f"),
        end_time=stats["End"].strftime("%Y-%m-%d %H:%M:%S.%f"),
        duration=str(stats["Duration"]),
        exposure_time_percentage=safe_float(stats["Exposure Time [%]"]),
        final_equity=safe_float(stats["Equity Final [$]"]),
        peak_equity=safe_float(stats["Equity Peak [$]"]),
        return_percentage=safe_float(stats["Return [%]"]),
        buy_and_hold_return=safe_float(stats["Buy & Hold Return [%]"]),
        return_annualized=safe_float(stats["Return (Ann.) [%]"]),
        volatility_annualized=safe_float(stats["Volatility (Ann.) [%]"]),
        sharpe_ratio=safe_float(stats["Sharpe Ratio"]),
        sortino_ratio=safe_float(stats["Sortino Ratio"]),
        calmar_ratio=safe_float(stats["Calmar Ratio"]),
        average_drawdown_percentage=safe_float(stats["Avg. Drawdown [%]"]),
        max_drawdown_duration=str(stats["Max. Drawdown Duration"]),
        average_drawdown_duration=str(stats["Avg. Drawdown Duration"]),
        trade_count=int(stats["# Trades"]),
        win_rate=safe_float(stats["Win Rate [%]"]),
        best_trade=safe_float(stats["Best Trade [%]"]),
        worst_trade=safe_float(stats["Worst Trade [%]"]),
        avg_trade=safe_float(stats["Avg. Trade [%]"]),
        max_trade_duration=str(stats["Max. Trade Duration"]),
        average_trade_duration=str(stats["Avg. Trade Duration"]),
        profit_factor=safe_float(stats["Profit Factor"]),
        html=compress_html(html_content),
        tpslRatio=safe_float(tpsl_ratio),
        sl_coef=safe_float(sl_coef),
    )


def build_persistence_payload(
    *,
    public_stats: BacktestStats,
    strategy: str,
    period: str | None,
    interval: str,
    reference: str | None,
    tpsl_ratio: Any = None,
    sl_coef: Any = None,
    tp_coef: Any = None,
) -> dict[str, Any]:
    """Convert public backtest stats to the existing database column names."""
    payload = public_stats.model_dump()
    payload.pop("tpslRatio")
    payload.update(
        strategy=strategy,
        period=period,
        interval=interval,
        ref_id=reference,
        updated_at=datetime.now(UTC),
        last_optimized_at=datetime.now(UTC),
        tpsl_ratio=safe_float(tpsl_ratio) if tpsl_ratio not in (None, "") else None,
        sl_coef=safe_float(sl_coef) if sl_coef not in (None, "") else None,
        tp_coef=safe_float(tp_coef) if tp_coef not in (None, "") else None,
    )
    return payload
