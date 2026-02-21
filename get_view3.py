import asyncio
from sqlalchemy import text
from app.db.postgres import AsyncSessionLocal

async def main():
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("SELECT id FROM unique_strategies LIMIT 1;"))
        for row in result:
            print("unique_strategies.id type:", type(row[0]), "val:", row[0])

asyncio.run(main())
