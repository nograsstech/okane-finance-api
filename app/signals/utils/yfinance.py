from __future__ import annotations

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

type DateInput = str | datetime

_YFINANCE_DOWNLOAD_TIMEOUT_SECONDS = 20
_MARKET_TIMEZONE = ZoneInfo("Asia/Singapore")


def get_dates(period_days: int) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Return the inclusive Singapore-market date range used by legacy callers."""
    today = pd.Timestamp(datetime.now(_MARKET_TIMEZONE))
    start_date = today - pd.Timedelta(days=period_days - 1)
    return today, start_date


def _period_days(period: str) -> int:
    if not period.endswith("d"):
        raise ValueError('period must use the "{number}d" format')

    try:
        days = int(period[:-1])
    except ValueError as exc:
        raise ValueError('period must use the "{number}d" format') from exc

    if days < 1:
        raise ValueError("period must be at least 1 day")
    return days


def get_yfinance_data(
    ticker: str,
    interval: str,
    period: str | None = None,
    start: DateInput | None = None,
    end: DateInput | None = None,
) -> pd.DataFrame:
    """Fetch and normalize OHLCV data from yfinance.

    Explicit dates take precedence. When neither date is supplied, the function
    retains the existing period-based date calculation used by strategy jobs.
    """
    resolved_start = start
    resolved_end = end
    if start is None and end is None:
        if period is None:
            raise ValueError("period is required when start and end are not provided")
        resolved_end, resolved_start = get_dates(_period_days(period))

    downloaded = yf.download(
        tickers=ticker,
        interval=interval,
        start=resolved_start,
        end=resolved_end,
        multi_level_index=False,
        auto_adjust=True,
        timeout=_YFINANCE_DOWNLOAD_TIMEOUT_SECONDS,
    )

    frame = pd.DataFrame(downloaded).reset_index()
    frame = frame.rename(columns={"Datetime": "Gmt time", "Date": "Gmt time"})
    frame["Gmt time"] = pd.to_datetime(frame["Gmt time"])
    frame.set_index("Gmt time", inplace=True)
    return frame[frame["High"] != frame["Low"]]


async def get_yfinance_data_async(
    ticker: str,
    interval: str,
    period: str | None = None,
    start: DateInput | None = None,
    end: DateInput | None = None,
) -> pd.DataFrame:
    """Run the blocking yfinance download outside the event loop."""
    return await asyncio.to_thread(get_yfinance_data, ticker, interval, period, start, end)


# Compatibility aliases for existing internal imports. New code uses snake_case.
getYFinanceData = get_yfinance_data
getYFinanceDataAsync = get_yfinance_data_async
