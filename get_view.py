import asyncio
from sqlalchemy import text
from app.db.postgres import AsyncSessionLocal

async def main():
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("SELECT pg_get_viewdef('unique_strategies', true);"))
            for row in result:
                print(row[0])
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    asyncio.run(main())
