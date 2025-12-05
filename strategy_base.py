"""
Base Strategy Class
All trading strategies should inherit from this class
"""

from abc import ABC, abstractmethod
import pandas as pd
from typing import Optional, Dict, Literal
import logging


SignalType = Literal['BUY', 'SELL', 'HOLD', 'CLOSE']


class TradingStrategy(ABC):
    """Abstract base class for trading strategies"""

    def __init__(self, name: str, parameters: Optional[Dict] = None):
        """
        Initialize strategy

        Args:
            name: Strategy name
            parameters: Strategy parameters dictionary
        """
        self.name = name
        self.parameters = parameters or {}
        self.logger = logging.getLogger(f"{__name__}.{name}")

    @abstractmethod
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate technical indicators

        Args:
            data: DataFrame with OHLCV data

        Returns:
            DataFrame with added indicator columns
        """
        pass

    @abstractmethod
    def generate_signal(self, data: pd.DataFrame) -> SignalType:
        """
        Generate trading signal based on indicators

        Args:
            data: DataFrame with OHLCV and indicator data

        Returns:
            Signal: 'BUY', 'SELL', 'HOLD', or 'CLOSE'
        """
        pass

    def on_bar(self, data: pd.DataFrame) -> SignalType:
        """
        Called when new bar is formed

        Args:
            data: DataFrame with OHLCV data

        Returns:
            Trading signal
        """
        # Calculate indicators
        data_with_indicators = self.calculate_indicators(data)

        # Generate signal
        signal = self.generate_signal(data_with_indicators)

        self.logger.debug(f"Signal generated: {signal}")

        return signal

    def get_stop_loss(self, signal: SignalType, current_price: float) -> float:
        """
        Calculate stop loss price

        Args:
            signal: Trading signal
            current_price: Current market price

        Returns:
            Stop loss price
        """
        sl_pips = self.parameters.get('stop_loss_pips', 50)
        point_value = self.parameters.get('point_value', 0.0001)

        if signal == 'BUY':
            return current_price - (sl_pips * point_value)
        elif signal == 'SELL':
            return current_price + (sl_pips * point_value)
        else:
            return 0.0

    def get_take_profit(self, signal: SignalType, current_price: float) -> float:
        """
        Calculate take profit price

        Args:
            signal: Trading signal
            current_price: Current market price

        Returns:
            Take profit price
        """
        tp_pips = self.parameters.get('take_profit_pips', 100)
        point_value = self.parameters.get('point_value', 0.0001)

        if signal == 'BUY':
            return current_price + (tp_pips * point_value)
        elif signal == 'SELL':
            return current_price - (tp_pips * point_value)
        else:
            return 0.0
