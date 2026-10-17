import os
from concurrent.futures import ThreadPoolExecutor

# Each backtest holds several DataFrames plus rendered HTML, so the pool size is the main
# lever on peak memory. Default is small for 2-vCPU hosts; raise it with BACKTEST_MAX_WORKERS.
BACKTEST_EXECUTOR = ThreadPoolExecutor(
    max_workers=max(1, int(os.environ.get("BACKTEST_MAX_WORKERS", "2"))),
    thread_name_prefix="backtest",
)
