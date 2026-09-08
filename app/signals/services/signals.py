from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import HTTPException
from starlette.status import HTTP_200_OK

from app.signals.dto import SignalResponseDTO
from app.signals.strategies.calculate import calculate_signals
from app.signals.utils.signals import get_all_signals, get_latest_signal
from app.signals.utils.yfinance import get_yfinance_data_async


def _parse_parameters(parameters: str | None) -> dict[str, Any]:
    if parameters is None:
        return {}
    try:
        parsed = json.loads(parameters)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to parse parameters. Error: {exc}",
        ) from exc
    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=400,
            detail="Failed to parse parameters. Expected an object",
        )
    return parsed


async def get_signals(
    ticker: str,
    interval: str,
    period: str | None,
    strategy: str | None,
    parameters: str | None,
    start: str | None = None,
    end: str | None = None,
) -> SignalResponseDTO:
    """Fetch market data and calculate the requested strategy signals."""
    parsed_parameters = _parse_parameters(parameters)
    try:
        frame = await get_yfinance_data_async(ticker, interval, period, start, end)
        daily_frame = None
        if strategy == "macd_1":
            daily_frame = await get_yfinance_data_async(ticker, "1d", period, start, end)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to calculate signals. Error: {exc}",
        ) from exc

    try:
        signals_frame = await asyncio.to_thread(
            calculate_signals,
            frame,
            daily_frame,
            strategy,
            parsed_parameters,
        )
        if signals_frame is None or signals_frame.empty:
            raise ValueError("strategy produced no signal data")
        return SignalResponseDTO.model_validate(
            {
                "status": HTTP_200_OK,
                "message": "Signals",
                "data": {
                    "ticker": ticker,
                    "period": period,
                    "interval": interval,
                    "strategy": strategy,
                    "signals": {
                        "latest_signal": get_latest_signal(signals_frame),
                        "all_signals": get_all_signals(signals_frame),
                    },
                },
            }
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to get signals. Error: {exc}",
        ) from exc
