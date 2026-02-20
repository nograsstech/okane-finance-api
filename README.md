# okane-finance-api

Okane Finance API — signals, AI, and financial data platform built with FastAPI.

---

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.14+ | [python.org](https://www.python.org/) or `pyenv install 3.14` |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |

---

## Local Development

### 1. Create & activate the virtual environment

```zsh
# uv reads .python-version (3.14) and creates .venv automatically
uv sync
source .venv/bin/activate
```

### 2. Install dependencies (including dev tools)

```zsh
uv sync --dev
```

> **Note:** The `pandas_ta` dependency is a local vendor wheel (`vendor/pandas_ta-0.3.14b0-py3-none-any.whl`). uv resolves it automatically via `pyproject.toml`.

### 3. Run the development server

```zsh
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

The API will be available at: `http://127.0.0.1:8000`

---

## Package Management

This project uses **[uv](https://github.com/astral-sh/uv)** for fast, reproducible dependency management.

```zsh
# Add a new runtime dependency
uv add <package>

# Add a dev-only dependency
uv add --dev <package>

# Remove a dependency
uv remove <package>

# Sync environment to match lock file exactly
uv sync --frozen
```

The `uv.lock` file is **committed to the repository** to guarantee reproducible builds across environments and CI.

---

## Typing & Validation

This project uses **[Pydantic v2](https://docs.pydantic.dev/)** as its primary data validation and typing library. All request/response schemas and config models are defined with Pydantic.

```python
from pydantic import BaseModel
from pydantic_settings import BaseSettings

class SignalResponse(BaseModel):
    symbol: str
    action: str
    confidence: float
```

---

## Docker

### Build

```zsh
docker build -t okane-finance-api .
```

The Dockerfile uses a **2-stage build**:
1. **Builder** — installs all dependencies with uv into a `.venv`
2. **Runtime** — copies the `.venv` into a lean image, runs as a non-root `appuser`

### Run

```zsh
docker run -p 8000:8000 --env-file .env okane-finance-api
```

### Health check

```zsh
curl http://localhost:8000/
```

---

## Project Structure

```
okane-finance-api/
├── app/
│   ├── main.py          # FastAPI entry point
│   ├── signals/         # Trading signal logic
│   ├── ai/              # AI/LLM integrations
│   ├── news/            # News feed endpoints
│   ├── ticker/          # Ticker data endpoints
│   ├── notification/    # Push notification service
│   ├── auth/            # Authentication
│   └── base/            # Shared models & interfaces
├── public/              # Static files
├── vendor/              # Local wheel packages (pandas_ta)
├── pyproject.toml       # ← single source of truth for deps
├── uv.lock              # ← committed lock file
├── .python-version      # ← pins Python 3.14
└── Dockerfile           # ← 2-stage production build
```