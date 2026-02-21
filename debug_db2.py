import asyncio
from app.db.postgres import AsyncSessionLocal
from app.db.repository import BacktestStatRepository

async def test():
    async with AsyncSessionLocal() as session:
        repo = BacktestStatRepository(session)
        # We don't need a real db if it's a compile error, but it helps.
        data = {
            "html": "",
            "period": "1y",
        }
        try:
            print("trying upsert...")
            data["id"] = "a6bf2a31-6b99-4a94-b2b9-e4d0dabc1234"
            await repo.upsert(data)
            print("upsert success")
        except Exception as e:
            print("UPSERT ERROR:", getattr(e, "message", str(e)))

asyncio.run(test())
