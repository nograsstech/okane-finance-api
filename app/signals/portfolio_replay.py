"""Deterministic portfolio replay for stored signal actions."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pandas as pd
import yfinance as yf

from app.db.postgres import AsyncSessionLocal
from app.db.repository import BacktestStatRepository, TradeActionRepository
from app.signals.dto import PortfolioReplayRequestDTO

_INTERVAL_FALLBACKS = ("5m", "15m", "1h", "1d")
_CLOSE_ACTIONS = {"close", "closed", "exit", "flatten", "close_long", "close_short"}
_INTERVAL_DURATIONS = {
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
    "1d": timedelta(days=1),
}


async def portfolio_replay(params: PortfolioReplayRequestDTO) -> dict[str, Any]:
    """Load enabled strategy actions, then run the CPU-bound replay off-loop."""
    async with AsyncSessionLocal() as session:
        strategies = await BacktestStatRepository(session).get_enabled_for_portfolio_replay()
        start = datetime.combine(params.start_date, datetime.min.time())
        end_exclusive = datetime.combine(params.end_date, datetime.min.time()) + timedelta(days=1)
        actions = await TradeActionRepository(session).get_for_portfolio_replay(
            [strategy.id for strategy in strategies],
            start,
            end_exclusive,
        )
    return await asyncio.to_thread(run_portfolio_replay, strategies, actions, params)


def _as_naive_utc(value: Any) -> datetime:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert(UTC).tz_localize(None)
    return timestamp.to_pydatetime()


def _value(obj: Any, name: str, default: Any = None) -> Any:
    return getattr(obj, name, default)


def fetch_adjusted_ohlc(
    ticker: str,
    start: datetime,
    end_exclusive: datetime,
) -> tuple[pd.DataFrame, str, list[str]]:
    """Fetch adjusted OHLC at the finest available interval, falling back safely."""
    warnings: list[str] = []
    for interval in _INTERVAL_FALLBACKS:
        try:
            frame = yf.download(
                tickers=ticker,
                interval=interval,
                start=start,
                end=end_exclusive,
                auto_adjust=True,
                multi_level_index=False,
                progress=False,
                timeout=20,
            )
            if frame is not None and not frame.empty:
                frame = frame.rename(
                    columns={column: str(column).title() for column in frame.columns}
                )
                required = {"Open", "High", "Low", "Close"}
                if required.issubset(frame.columns):
                    frame = frame.sort_index().dropna(subset=list(required))
                    if not frame.empty:
                        if interval != _INTERVAL_FALLBACKS[0]:
                            warnings.append(
                                f"{ticker}: 5m data unavailable; replayed with {interval} bars"
                            )
                        return frame, interval, warnings
        except Exception as exc:  # pragma: no cover - provider failures vary
            warnings.append(f"{ticker}: {interval} market data failed ({exc})")
    raise ValueError(f"No adjusted OHLC data available for {ticker}")


def _dedupe_actions(actions: list[Any]) -> tuple[list[Any], int]:
    seen: set[tuple[Any, ...]] = set()
    unique: list[Any] = []
    for action in actions:
        key = (
            _value(action, "backtest_id"),
            _as_naive_utc(_value(action, "datetime")),
            str(_value(action, "trade_action", "")).strip().lower(),
            _value(action, "entry_price"),
            _value(action, "price"),
            _value(action, "sl"),
            _value(action, "tp"),
            _value(action, "size"),
        )
        if key not in seen:
            seen.add(key)
            unique.append(action)
    unique.sort(key=lambda action: _as_naive_utc(_value(action, "datetime")))
    return unique, len(actions) - len(unique)


def _bar_frame(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    normalized.index = pd.DatetimeIndex([_as_naive_utc(value) for value in normalized.index])
    return normalized.sort_index()


def _valid_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if pd.notna(number) else None


def _trade_result(
    strategy: Any,
    position: SimpleNamespace,
    exit_at: datetime,
    exit_price: float,
    reason: str,
    risk_per_trade: float,
    cost: float,
) -> dict[str, Any]:
    price_move = exit_price - position.entry_price
    if position.direction == "short":
        price_move *= -1
    risk_units = abs(position.entry_price - position.stop_loss)
    r_multiple = price_move / risk_units
    pnl = r_multiple * risk_per_trade - cost
    messages = {
        "sl": "Stop loss hit",
        "tp": "Take profit hit",
        "close": "Closed by stored signal",
        "mark_to_market": "Open position marked to the last available close",
    }
    return {
        "backtest_id": int(strategy.id),
        "ticker": str(strategy.ticker),
        "strategy": str(strategy.strategy),
        "datetime": position.entry_at,
        "action": position.action,
        "direction": position.direction,
        "entry_price": position.entry_price,
        "exit_price": exit_price,
        "stop_loss": position.stop_loss,
        "take_profit": position.take_profit,
        "risk_units": risk_units,
        "r_multiple": r_multiple,
        "pnl": pnl,
        "cost": cost,
        "status": "marked" if reason == "mark_to_market" else reason,
        "exit_datetime": exit_at,
        "message": messages[reason],
    }


def _replay_strategy(
    strategy: Any,
    actions: list[Any],
    frame: pd.DataFrame,
    risk_per_trade: float,
    cost_per_trade: float,
    bar_interval: str = "5m",
) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    trades: list[dict[str, Any]] = []
    positions: list[SimpleNamespace] = []
    bars = _bar_frame(frame)
    bar_duration = _INTERVAL_DURATIONS.get(bar_interval, timedelta(0))
    use_completion_time = bar_interval != "5m" and bar_duration > timedelta(0)
    last_scanned: datetime | None = None

    def scan_until(until: datetime) -> None:
        nonlocal last_scanned
        remaining: list[SimpleNamespace] = []
        for position in positions:
            lower_bound = max(last_scanned or position.entry_at, position.entry_at)
            exited = False
            for bar_start, bar in bars.iterrows():
                bar_at = bar_start + bar_duration if use_completion_time else bar_start
                starts_after_entry = not use_completion_time or bar_start >= position.entry_at
                if not (starts_after_entry and lower_bound < bar_at <= until):
                    continue
                is_long = position.direction == "long"
                sl_hit = (
                    float(bar["Low"]) <= position.stop_loss
                    if is_long
                    else float(bar["High"]) >= position.stop_loss
                )
                tp_hit = False
                if position.take_profit is not None:
                    tp_hit = (
                        float(bar["High"]) >= position.take_profit
                        if is_long
                        else float(bar["Low"]) <= position.take_profit
                    )
                if sl_hit or tp_hit:
                    reason = "sl" if sl_hit else "tp"
                    exit_price = position.stop_loss if sl_hit else position.take_profit
                    trades.append(
                        _trade_result(
                            strategy,
                            position,
                            bar_at,
                            exit_price,
                            reason,
                            risk_per_trade,
                            cost_per_trade,
                        )
                    )
                    exited = True
                    break
            if not exited:
                remaining.append(position)
        positions[:] = remaining
        last_scanned = until

    for action in actions:
        action_at = _as_naive_utc(_value(action, "datetime"))
        scan_until(action_at)
        action_name = str(_value(action, "trade_action", "")).strip().lower()
        if action_name in _CLOSE_ACTIONS or action_name.startswith("close"):
            if positions:
                exit_price = _valid_number(_value(action, "price"))
                if exit_price is None:
                    if use_completion_time:
                        prior = bars[(bars.index + bar_duration) <= action_at]
                    else:
                        prior = bars[bars.index <= action_at]
                    if prior.empty:
                        warnings.append(
                            f"{strategy.ticker}/{strategy.strategy}: close at "
                            f"{action_at.isoformat()} had no price"
                        )
                        continue
                    exit_price = float(prior.iloc[-1]["Close"])
                for position in positions:
                    trades.append(
                        _trade_result(
                            strategy,
                            position,
                            action_at,
                            exit_price,
                            "close",
                            risk_per_trade,
                            cost_per_trade,
                        )
                    )
                positions.clear()
            continue
        if action_name not in {"buy", "sell"}:
            warnings.append(
                f"{strategy.ticker}/{strategy.strategy}: ignored unknown action {action_name!r}"
            )
            continue
        entry_price = _valid_number(_value(action, "entry_price"))
        if entry_price is None:
            entry_price = _valid_number(_value(action, "price"))
        stop_loss = _valid_number(_value(action, "sl"))
        take_profit = _valid_number(_value(action, "tp"))
        direction = "long" if action_name == "buy" else "short"
        valid_stop = (
            entry_price is not None
            and stop_loss is not None
            and (
                (direction == "long" and stop_loss < entry_price)
                or (direction == "short" and stop_loss > entry_price)
            )
        )
        if not valid_stop:
            warnings.append(
                f"{strategy.ticker}/{strategy.strategy}: ignored {action_name} at "
                f"{action_at.isoformat()} because entry/SL risk was invalid"
            )
            continue
        if take_profit is not None and (
            (direction == "long" and take_profit <= entry_price)
            or (direction == "short" and take_profit >= entry_price)
        ):
            warnings.append(
                f"{strategy.ticker}/{strategy.strategy}: ignored invalid take profit at "
                f"{action_at.isoformat()}"
            )
            take_profit = None
        positions.append(
            SimpleNamespace(
                action=action_name,
                direction=direction,
                entry_at=action_at,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )
        )

    if positions:
        final_bar_at = bars.index[-1].to_pydatetime()
        if use_completion_time:
            final_bar_at += bar_duration
        scan_until(final_bar_at)
    for position in positions:
        if use_completion_time:
            last_bar = bars[(bars.index + bar_duration) > position.entry_at].tail(1)
        else:
            last_bar = bars[bars.index >= position.entry_at].tail(1)
        if last_bar.empty:
            warnings.append(
                f"{strategy.ticker}/{strategy.strategy}: open position had no close "
                "for mark-to-market"
            )
        else:
            exit_at = last_bar.index[-1].to_pydatetime()
            if use_completion_time:
                exit_at += bar_duration
            trades.append(
                _trade_result(
                    strategy,
                    position,
                    exit_at,
                    float(last_bar.iloc[-1]["Close"]),
                    "mark_to_market",
                    risk_per_trade,
                    0,
                )
            )
    return trades, warnings


def _summary(trades: list[dict[str, Any]], starting_equity: float) -> dict[str, Any]:
    realized = sum(trade["pnl"] for trade in trades if trade["status"] != "marked")
    unrealized = sum(trade["pnl"] for trade in trades if trade["status"] == "marked")
    net_pnl = realized + unrealized
    closed = [trade for trade in trades if trade["status"] != "marked"]
    wins = sum(trade["pnl"] > 0 for trade in closed)
    losses = sum(trade["pnl"] < 0 for trade in closed)
    equity = starting_equity
    peak = equity
    max_drawdown = 0.0
    for trade in sorted(trades, key=lambda item: item["exit_datetime"]):
        equity += trade["pnl"]
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)
    return {
        "starting_equity": starting_equity,
        "ending_equity": starting_equity + net_pnl,
        "net_pnl": net_pnl,
        "return_percentage": net_pnl / starting_equity * 100,
        "realized_pnl": realized,
        "unrealized_pnl": unrealized,
        "total_costs": sum(trade["cost"] for trade in trades),
        "max_drawdown": max_drawdown,
        "max_drawdown_percentage": max_drawdown / peak * 100 if peak else 0.0,
        "total_trades": len(trades),
        "closed_trades": len(closed),
        "open_trades": len(trades) - len(closed),
        "wins": wins,
        "losses": losses,
        "win_rate": wins / len(closed) * 100 if closed else None,
    }


def _strategy_result(strategy: Any, trades: list[dict[str, Any]]) -> dict[str, Any]:
    closed = [trade for trade in trades if trade["status"] != "marked"]
    wins = sum(trade["pnl"] > 0 for trade in closed)
    return {
        "backtest_id": int(strategy.id),
        "ticker": str(strategy.ticker),
        "strategy": str(strategy.strategy),
        "trades": len(trades),
        "closed_trades": len(closed),
        "open_trades": len(trades) - len(closed),
        "wins": wins,
        "net_pnl": sum(trade["pnl"] for trade in trades),
        "win_rate": wins / len(closed) * 100 if closed else None,
        "average_r": (
            sum(trade["r_multiple"] for trade in trades) / len(trades) if trades else None
        ),
    }


def run_portfolio_replay(
    strategies: list[Any],
    actions: list[Any],
    params: PortfolioReplayRequestDTO,
) -> dict[str, Any]:
    """Replay all enabled-strategy actions and build the API response envelope."""
    start = datetime.combine(params.start_date, datetime.min.time())
    end_exclusive = datetime.combine(params.end_date, datetime.min.time()) + timedelta(days=1)
    actions, duplicate_count = _dedupe_actions(actions)
    warnings = [f"Removed {duplicate_count} exact duplicate action(s)"] if duplicate_count else []
    actions_by_strategy: dict[int, list[Any]] = defaultdict(list)
    for action in actions:
        actions_by_strategy[int(_value(action, "backtest_id"))].append(action)

    frames: dict[str, pd.DataFrame] = {}
    intervals: dict[str, str] = {}
    failed_tickers: set[str] = set()
    all_trades: list[dict[str, Any]] = []
    strategy_results: list[dict[str, Any]] = []
    for strategy in strategies:
        strategy_actions = actions_by_strategy.get(int(strategy.id), [])
        if not strategy_actions:
            continue
        ticker = str(strategy.ticker)
        if ticker not in frames and ticker not in failed_tickers:
            try:
                frames[ticker], intervals[ticker], fetch_warnings = fetch_adjusted_ohlc(
                    ticker, start, end_exclusive
                )
                warnings.extend(fetch_warnings)
            except ValueError as exc:
                failed_tickers.add(ticker)
                warnings.append(str(exc))
        if ticker in failed_tickers:
            continue
        strategy_trades, strategy_warnings = _replay_strategy(
            strategy,
            strategy_actions,
            frames[ticker],
            params.risk_per_trade,
            params.cost_per_trade,
            intervals[ticker],
        )
        all_trades.extend(strategy_trades)
        warnings.extend(strategy_warnings)
        strategy_results.append(_strategy_result(strategy, strategy_trades))

    all_trades.sort(key=lambda trade: (trade["exit_datetime"], trade["backtest_id"]))
    equity = params.starting_equity
    equity_curve = [{"datetime": start, "equity": equity, "pnl": 0.0}]
    pnl_by_time: dict[datetime, float] = defaultdict(float)
    for trade in all_trades:
        pnl_by_time[trade["exit_datetime"]] += trade["pnl"]
    for at, pnl in sorted(pnl_by_time.items()):
        equity += pnl
        equity_curve.append({"datetime": at, "equity": equity, "pnl": pnl})

    return {
        "status": 200,
        "message": "Portfolio replay results",
        "data": {
            "start_date": params.start_date,
            "end_date": params.end_date,
            "summary": _summary(all_trades, params.starting_equity),
            "enabled_strategy_count": len(strategies),
            "strategy_count_with_actions": len(actions_by_strategy),
            "equity_curve": equity_curve,
            "strategies": strategy_results,
            "trades": all_trades,
            "warnings": warnings,
        },
    }
