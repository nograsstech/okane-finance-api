import asyncio
from sqlalchemy import text
from app.db.postgres import AsyncSessionLocal

async def main():
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'unique_strategies';"))
        print("\nunique_strategies columns:")
        for row in result:
            print(f"  {row[0]}: {row[1]}")
            
        result = await session.execute(text("SELECT definition FROM pg_views WHERE viewname = 'unique_strategies';"))
        for row in result:
            print("\nDef:", row[0])

asyncio.run(main())
