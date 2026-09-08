import asyncio

from fastapi import APIRouter, HTTPException

from app.executors import BACKTEST_EXECUTOR

router = APIRouter()


def _executor_probe() -> None:
    pass


@router.get("/health", include_in_schema=False)
async def healthcheck() -> dict[str, str]:
    try:
        loop = asyncio.get_running_loop()
        await asyncio.wait_for(
            loop.run_in_executor(BACKTEST_EXECUTOR, _executor_probe),
            timeout=2.0,
        )
    except TimeoutError as exc:
        raise HTTPException(status_code=503, detail="Backtest executor unavailable") from exc
    return {"status": "ok"}
