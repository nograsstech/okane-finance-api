from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pandas as pd
import pytest
from pydantic import ValidationError

from app.signals import portfolio_replay as portfolio_replay_module
from app.signals.dto import PortfolioReplayRequestDTO
from app.signals.portfolio_replay import _replay_strategy, run_portfolio_replay


def _strategy(backtest_id: int = 1):
    return SimpleNamespace(id=backtest_id, ticker="TEST", strategy="alpha", interval="5m")


def _action(
    action: str,
    at: str,
    *,
    backtest_id: int = 1,
    entry: float | None = 100,
    price: float | None = 100,
    sl: float | None = 90,
    tp: float | None = 120,
):
    return SimpleNamespace(
        backtest_id=backtest_id,
        datetime=datetime.fromisoformat(at),
        trade_action=action,
        entry_price=entry,
        price=price,
        sl=sl,
        tp=tp,
        size=1,
    )


def _bars(rows: list[tuple[str, float, float, float, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        [(open_, high, low, close) for _, open_, high, low, close in rows],
        index=pd.DatetimeIndex([at for at, *_ in rows]),
        columns=["Open", "High", "Low", "Close"],
    )


def _params(**overrides) -> PortfolioReplayRequestDTO:
    return PortfolioReplayRequestDTO(
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 5),
        starting_equity=10_000,
        risk_per_trade=100,
        cost_per_trade=5,
        **overrides,
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"end_date": date(2023, 12, 31)},
        {"end_date": date.today() + timedelta(days=1)},
        {"end_date": date(2024, 3, 1)},
        {"starting_equity": 0},
        {"risk_per_trade": 0},
        {"cost_per_trade": -1},
    ],
)
def test_request_validation(overrides):
    base = {
        "start_date": date(2024, 1, 1),
        "end_date": date(2024, 1, 5),
        "starting_equity": 10_000,
        "risk_per_trade": 100,
        "cost_per_trade": 0,
    }
    with pytest.raises(ValidationError):
        PortfolioReplayRequestDTO(**(base | overrides))


def test_long_same_bar_uses_conservative_sl_first_and_applies_cost():
    frame = _bars([("2024-01-01 10:00", 100, 125, 85, 110)])
    trades, _ = _replay_strategy(
        _strategy(),
        [_action("buy", "2024-01-01 09:00")],
        frame,
        risk_per_trade=100,
        cost_per_trade=5,
    )

    assert trades[0]["status"] == "sl"
    assert trades[0]["r_multiple"] == -1
    assert trades[0]["pnl"] == -105


def test_short_take_profit():
    frame = _bars([("2024-01-01 10:00", 100, 102, 78, 80)])
    action = _action("sell", "2024-01-01 09:00", sl=110, tp=80)

    trades, _ = _replay_strategy(_strategy(), [action], frame, 100, 0)

    assert trades[0]["status"] == "tp"
    assert trades[0]["direction"] == "short"
    assert trades[0]["r_multiple"] == 2
    assert trades[0]["pnl"] == 200


def test_explicit_close_uses_stored_price():
    frame = _bars([("2024-01-01 10:00", 100, 103, 99, 101)])
    actions = [
        _action("buy", "2024-01-01 09:00"),
        _action("close", "2024-01-01 11:00", entry=None, price=105, sl=None, tp=None),
    ]

    trades, _ = _replay_strategy(_strategy(), actions, frame, 100, 5)

    assert trades[0]["status"] == "close"
    assert trades[0]["exit_price"] == 105
    assert trades[0]["pnl"] == 45


def test_open_position_is_marked_to_last_close():
    frame = _bars([("2024-01-01 10:00", 100, 105, 95, 104)])

    trades, _ = _replay_strategy(_strategy(), [_action("buy", "2024-01-01 09:00")], frame, 100, 5)

    assert trades[0]["status"] == "marked"
    assert trades[0]["exit_price"] == 104
    assert trades[0]["cost"] == 0
    assert trades[0]["pnl"] == 40


def test_daily_entry_inside_bar_is_marked_to_that_bars_close():
    frame = _bars([("2024-01-01 00:00", 100, 125, 85, 104)])

    trades, _ = _replay_strategy(
        _strategy(),
        [_action("buy", "2024-01-01 12:00")],
        frame,
        100,
        0,
        bar_interval="1d",
    )

    assert len(trades) == 1
    assert trades[0]["status"] == "marked"
    assert trades[0]["exit_price"] == 104
    assert trades[0]["exit_datetime"] == datetime(2024, 1, 2)


def test_daily_bar_does_not_override_close_before_bar_completion():
    frame = _bars([("2024-01-01 00:00", 100, 125, 85, 104)])
    actions = [
        _action("buy", "2024-01-01 00:00"),
        _action("close", "2024-01-01 12:00", entry=None, price=105, sl=None, tp=None),
    ]

    trades, _ = _replay_strategy(_strategy(), actions, frame, 100, 0, bar_interval="1d")

    assert len(trades) == 1
    assert trades[0]["status"] == "close"
    assert trades[0]["exit_price"] == 105


def test_close_flattens_multiple_concurrent_positions():
    frame = _bars([("2024-01-01 10:00", 100, 103, 97, 101)])
    actions = [
        _action("buy", "2024-01-01 09:00"),
        _action("buy", "2024-01-01 09:30", entry=102, price=102, sl=92, tp=122),
        _action("close", "2024-01-01 11:00", entry=None, price=105, sl=None, tp=None),
    ]

    trades, _ = _replay_strategy(_strategy(), actions, frame, 100, 0)

    assert len(trades) == 2
    assert {trade["status"] for trade in trades} == {"close"}


def test_full_replay_deduplicates_exact_actions(monkeypatch):
    frame = _bars([("2024-01-01 10:00", 100, 125, 95, 120)])
    action = _action("buy", "2024-01-01 09:00")
    monkeypatch.setattr(
        "app.signals.portfolio_replay.fetch_adjusted_ohlc",
        lambda *_: (frame, "5m", []),
    )

    response = run_portfolio_replay([_strategy()], [action, action], _params())

    assert response["data"]["enabled_strategy_count"] == 1
    assert response["data"]["strategy_count_with_actions"] == 1
    assert response["data"]["summary"]["total_trades"] == 1
    assert response["data"]["summary"]["ending_equity"] == 10_195
    assert response["data"]["warnings"] == ["Removed 1 exact duplicate action(s)"]


@pytest.mark.asyncio
async def test_portfolio_replay_service_returns_a_typed_empty_portfolio(monkeypatch):
    class SessionContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, *_args):
            return None

    class BacktestRepository:
        def __init__(self, _session):
            pass

        async def get_enabled_for_portfolio_replay(self):
            return []

    class TradeRepository:
        def __init__(self, _session):
            pass

        async def get_for_portfolio_replay(self, *_args):
            return []

    monkeypatch.setattr(portfolio_replay_module, "AsyncSessionLocal", SessionContext)
    monkeypatch.setattr(
        portfolio_replay_module,
        "BacktestStatRepository",
        BacktestRepository,
    )
    monkeypatch.setattr(
        portfolio_replay_module,
        "TradeActionRepository",
        TradeRepository,
    )

    response = await portfolio_replay_module.portfolio_replay(_params())

    assert response.status == 200
    assert response.data.enabled_strategy_count == 0
    assert response.data.summary.ending_equity == 10_000
