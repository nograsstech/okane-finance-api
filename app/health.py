import asyncio

from fastapi import APIRouter, HTTPException

router = APIRouter()


def _executor_probe() -> None:
    pass


@router.get("/health", include_in_schema=False)
async def healthcheck() -> dict[str, str]:
    try:
        await asyncio.wait_for(asyncio.to_thread(_executor_probe), timeout=2.0)
    except TimeoutError as exc:
        raise HTTPException(status_code=503, detail="Worker executor unavailable") from exc
    return {"status": "ok"}
