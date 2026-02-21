# PR Title
feat: Migrate Database Layer to Async SQLAlchemy and Motor

# Description

This PR introduces a major refactor of the database layer, migrating away from the synchronous Supabase Python client to a fully asynchronous architecture using native SQLAlchemy alongside the Motor async client for MongoDB.

## Key Changes
- **Postgres Migration:** Configured `psycopg3` natively and added new async Session management (`AsyncSessionLocal`) in `app/db/postgres.py`.
- **SQLAlchemy ORM Models:** Implemented declarative models (`app/db/models.py`) reflecting the existing Supabase tables: `backtest_stats`, `trade_actions`, and `unique_strategies`.
- **Repository Pattern:** Added `app/db/repository.py` to decouple business logic from direct database operations.
- **MongoDB Singleton:** Refactored `app/base/utils/mongodb.py` to export a module-level `AsyncIOMotorClient` singleton, avoiding the high cost of recreating the client on every request.
- **Background Tasks Refactor:** Replaced the custom ThreadPoolExecutor in `app/signals/router.py` with FastAPI's native `BackgroundTasks` injected directly into the route handlers.
- **Async Execution:** Converted synchronous data retrieval and operations within `app/signals/service.py` and other services to utilize `await`.
- **Unit Tests:** Added full unit test suites for the MongoDB singleton and the new Postgres repositories leveraging Pytest and an in-memory database workflow.
