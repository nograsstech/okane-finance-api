"""
DTO builders for API responses.

Provides helper functions for building data transfer objects from backtest results.
Extracted from service.py for better separation of concerns.
"""
import math


def safe_float(value, default=0.0, decimals=3):
    """
    Safely convert a value to float, handling NaN and None values.

    Args:
        value: The value to convert
        default: Default value if conversion fails or result is NaN/Inf
        decimals: Number of decimal places to round to

    Returns:
        float: The converted and rounded value, or default if conversion fails
    """
    try:
        float_val = float(value)
        if math.isnan(float_val) or math.isinf(float_val):
            return default
        return round(float_val, decimals)
    except (TypeError, ValueError):
        return default


def build_backtest_stats_dto(stats, html_content: str, ticker: str, strategy: str,
                             period: str, interval: str, strategy_parameters: dict) -> dict:
    """
    Build backtest stats DTO from backtesting.py stats object.

    Args:
        stats: Backtest statistics dictionary from backtesting.py
        html_content: HTML content for the backtest plot
        ticker: Trading symbol
        strategy: Strategy name
        period: Time period
        interval: Time interval
        strategy_parameters: Strategy parameters used

    Returns:
        dict: Formatted backtest statistics for API response
    """
    return {
        "ticker": ticker,
        "max_drawdown_percentage": safe_float(stats["Max. Drawdown [%]"]),
        "start_time": stats["Start"].strftime("%Y-%m-%d %H:%M:%S.%f"),
        "end_time": stats["End"].strftime("%Y-%m-%d %H:%M:%S.%f"),
        "duration": str(stats["Duration"]),
        "exposure_time_percentage": safe_float(stats["Exposure Time [%]"]),
        "final_equity": safe_float(stats["Equity Final [$]"]),
        "peak_equity": safe_float(stats["Equity Peak [$]"]),
        "return_percentage": safe_float(stats["Return [%]"]),
        "buy_and_hold_return": safe_float(stats["Buy & Hold Return [%]"]),
        "return_annualized": safe_float(stats["Return (Ann.) [%]"]),
        "volatility_annualized": safe_float(stats["Volatility (Ann.) [%]"]),
        "sharpe_ratio": safe_float(stats["Sharpe Ratio"]),
        "sortino_ratio": safe_float(stats["Sortino Ratio"]),
        "calmar_ratio": safe_float(stats["Calmar Ratio"]),
        "average_drawdown_percentage": safe_float(stats["Avg. Drawdown [%]"]),
        "max_drawdown_duration": str(stats["Max. Drawdown Duration"]),
        "average_drawdown_duration": str(stats["Avg. Drawdown Duration"]),
        "trade_count": stats["# Trades"],
        "win_rate": safe_float(stats["Win Rate [%]"]),
        "best_trade": safe_float(stats["Best Trade [%]"]),
        "worst_trade": safe_float(stats["Worst Trade [%]"]),
        "avg_trade": safe_float(stats["Avg. Trade [%]"]),
        "max_trade_duration": str(stats["Max. Trade Duration"]),
        "average_trade_duration": str(stats["Avg. Trade Duration"]),
        "profit_factor": safe_float(stats["Profit Factor"]),
        "html": html_content,
        "strategy": strategy,
        "period": period,
        "interval": interval,
        "tpslRatio": strategy_parameters.get("tpslRatio", 0.0),
        "sl_coef": strategy_parameters.get("slcoef", 0.0),
    }
