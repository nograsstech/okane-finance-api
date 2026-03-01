"""
Strategy registry for auto-discovery and unified access.

Provides a central registry for all trading strategies, enabling
dynamic strategy lookup and eliminating hardcoded strategy lists.
"""

from app.signals.strategies.base import StrategyInterface


class StrategyRegistry:
    """
    Central registry for all trading strategies.

    Uses a class-level dictionary to store strategy instances,
    allowing for singleton-like access across the application.
    """

    _strategies: dict[str, StrategyInterface] = {}

    @classmethod
    def register(cls, strategy: StrategyInterface) -> None:
        """
        Register a strategy instance.

        Args:
            strategy: An instance of a class implementing StrategyInterface

        Raises:
            ValueError: If a strategy with the same name is already registered
        """
        name = strategy.name
        if name in cls._strategies:
            raise ValueError(f"Strategy '{name}' is already registered")
        cls._strategies[name] = strategy

    @classmethod
    def get(cls, name: str) -> StrategyInterface | None:
        """
        Get a strategy by name.

        Args:
            name: The unique strategy identifier

        Returns:
            The strategy instance, or None if not found
        """
        return cls._strategies.get(name)

    @classmethod
    def list_all(cls) -> list[str]:
        """
        List all registered strategy names.

        Returns:
            List of strategy identifiers
        """
        return list(cls._strategies.keys())

    @classmethod
    def clear(cls) -> None:
        """
        Clear all registrations.

        Useful for testing to ensure a clean state between tests.
        """
        cls._strategies.clear()

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """
        Check if a strategy is registered.

        Args:
            name: The strategy identifier to check

        Returns:
            True if the strategy is registered, False otherwise
        """
        return name in cls._strategies
