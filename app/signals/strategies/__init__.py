from multiprocessing.dummy import Pool as ThreadPool

import backtesting

# backtesting.py defaults to forking optimizer workers on Linux. Use its supported
# pool override so optimization cannot inherit locked uvicorn and asyncio state.
backtesting.Pool = ThreadPool
