from concurrent.futures import ThreadPoolExecutor

BACKTEST_EXECUTOR = ThreadPoolExecutor(max_workers=5, thread_name_prefix="backtest")
