"""
Risk Manager for position sizing, stop-loss, and take-profit calculations.
"""
from typing import Optional, Dict


class RiskManager:
    """
    Handles position sizing and risk management for trading strategies.

    Uses ATR (Average True Range) based position sizing with configurable
    risk-reward ratios and per-trade risk percentage.
    """

    def __init__(self, atr_multiplier: float, risk_reward_ratio: float, risk_per_trade: float):
        """
        Initialize the Risk Manager.

        Args:
            atr_multiplier: Multiplier for ATR to calculate stop-loss distance
            risk_reward_ratio: Ratio of take-profit to stop-loss (e.g., 2.0 means TP is 2x SL)
            risk_per_trade: Percentage of equity to risk per trade (e.g., 0.02 = 2%)
        """
        self.atr_multiplier = atr_multiplier
        self.risk_reward_ratio = risk_reward_ratio
        self.risk_per_trade = risk_per_trade

    def evaluate(self, equity: float, price: float, atr: float, direction: str) -> Optional[Dict]:
        """
        Calculate position size, stop-loss, and take-profit for a trade.

        Args:
            equity: Current account equity
            price: Current entry price
            atr: Average True Range value
            direction: "long" or "short"

        Returns:
            Dictionary with keys:
                - size: Position size (fraction of equity, 0-1)
                - sl: Stop-loss price
                - tp: Take-profit price
            Returns None if parameters are invalid.
        """
        if atr <= 0 or price <= 0 or equity <= 0:
            return None

        # Calculate stop-loss distance using ATR
        sl_distance = atr * self.atr_multiplier

        # Calculate position size based on risk per trade
        # Risk amount = sl_distance * position_value_in_currency
        # position_size = (equity * risk_per_trade) / sl_distance
        risk_amount = equity * self.risk_per_trade
        position_value = risk_amount / sl_distance
        size = position_value / price

        # Ensure size is reasonable (between 0 and 1)
        size = max(0.0, min(1.0, size))

        # Calculate stop-loss and take-profit levels
        if direction == "long":
            sl = price - sl_distance
            tp = price + (sl_distance * self.risk_reward_ratio)
        elif direction == "short":
            sl = price + sl_distance
            tp = price - (sl_distance * self.risk_reward_ratio)
        else:
            return None

        return {
            "size": size,
            "sl": sl,
            "tp": tp,
        }
