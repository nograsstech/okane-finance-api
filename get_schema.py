import asyncio
from sqlalchemy import text
from app.db.postgres import AsyncSessionLocal

async def main():
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'backtest_stats';"))
            print("backtest_stats:")
            for row in result:
                print(f"  {row[0]}: {row[1]}")
            
            result = await session.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'trade_actions';"))
            print("trade_actions:")
            for row in result:
                print(f"  {row[0]}: {row[1]}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    asyncio.run(main())
