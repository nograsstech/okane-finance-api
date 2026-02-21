import asyncio
from app.db.postgres import AsyncSessionLocal
from app.db.repository import BacktestStatRepository

async def test():
    async with AsyncSessionLocal() as session:
        repo = BacktestStatRepository(session)
        # We don't need a real db if it's a compile error, but it helps.
        data = {
            "ticker": "BTC",
            "max_drawdown_percentage": 1.0,
            "start_time": "2022-01-01",
            "end_time": "2022-01-02",
            "duration": "1 days, 0:00:00",
            "exposure_time_percentage": 50.0,
            "final_equity": 100000.0,
            "peak_equity": 100000.0,
            "return_percentage": 0.0,
            "buy_and_hold_return": 0.0,
            "return_annualized": 0.0,
            "volatility_annualized": 0.0,
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
            "calmar_ratio": 0.0,
            "average_drawdown_percentage": 0.0,
            "max_drawdown_duration": "",
            "average_drawdown_duration": "",
            "trade_count": 1,
            "win_rate": 0.0,
            "best_trade": 0.0,
            "worst_trade": 0.0,
            "avg_trade": 0.0,
            "max_trade_duration": "",
            "average_trade_duration": "",
            "profit_factor": 0.0,
            "html": "",
            "strategy": "ema_bollinger",
            "period": "1y",
            "interval": "1d",
            "ref_id": "test",
            "updated_at": "2022",
            "last_optimized_at": "2022",
            "tpsl_ratio": 1.5,
            "sl_coef": 4.8,
            "tp_coef": None,
            "notifications_on": False,
        }
        try:
            print("trying insert...")
            await repo.insert(data)
            print("insert success")
        except Exception as e:
            print("INSERT ERROR")
            print(repr(e))
            print(str(e))
        
        try:
            print("trying upsert...")
            data["id"] = "a6bf2a31-6b99-4a94-b2b9-e4d0dabc1234"
            await repo.upsert(data)
            print("upsert success")
        except Exception as e:
            print("UPSERT ERROR")
            print(repr(e))
            print(str(e))

asyncio.run(test())
