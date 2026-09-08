import multiprocessing as mp

# backtesting.py creates optimizer workers from request-handling threads. Forking
# there can inherit locked uvicorn and asyncio state, so all strategy imports use spawn.
mp.set_start_method("spawn", force=True)
