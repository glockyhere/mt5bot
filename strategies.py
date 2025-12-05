"""
Trading Strategy Implementations
"""

import pandas as pd
import numpy as np
from strategy_base import TradingStrategy, SignalType
from typing import Dict


class MovingAverageCrossover(TradingStrategy):
    """
    Moving Average Crossover Strategy

    Generates BUY signal when fast MA crosses above slow MA
    Generates SELL signal when fast MA crosses below slow MA
    """

    def __init__(self, parameters: Dict):
        """
        Initialize MA Crossover strategy

        Parameters:
            fast_period: Fast moving average period
            slow_period: Slow moving average period
            signal_period: Signal line period (for MACD-like confirmation)
        """
        super().__init__("MovingAverageCrossover", parameters)
        self.fast_period = parameters.get('fast_period', 20)
        self.slow_period = parameters.get('slow_period', 50)
        self.signal_period = parameters.get('signal_period', 9)

    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate moving averages"""
        df = data.copy()

        # Calculate fast and slow moving averages
        df['ma_fast'] = df['close'].rolling(window=self.fast_period).mean()
        df['ma_slow'] = df['close'].rolling(window=self.slow_period).mean()

        # Calculate difference and signal line
        df['ma_diff'] = df['ma_fast'] - df['ma_slow']
        df['ma_signal'] = df['ma_diff'].rolling(window=self.signal_period).mean()

        return df

    def generate_signal(self, data: pd.DataFrame) -> SignalType:
        """Generate trading signal based on MA crossover"""
        if len(data) < self.slow_period + self.signal_period:
            return 'HOLD'

        # Get last two rows to detect crossover
        current = data.iloc[-1]
        previous = data.iloc[-2]

        # Check for NaN values
        if pd.isna(current['ma_fast']) or pd.isna(current['ma_slow']):
            return 'HOLD'

        # Bullish crossover: fast MA crosses above slow MA
        if (previous['ma_fast'] <= previous['ma_slow'] and
            current['ma_fast'] > current['ma_slow'] and
            current['ma_diff'] > current['ma_signal']):
            return 'BUY'

        # Bearish crossover: fast MA crosses below slow MA
        elif (previous['ma_fast'] >= previous['ma_slow'] and
              current['ma_fast'] < current['ma_slow'] and
              current['ma_diff'] < current['ma_signal']):
            return 'SELL'

        return 'HOLD'


class RSIStrategy(TradingStrategy):
    """
    RSI-based Trading Strategy

    Generates BUY signal when RSI crosses above oversold level
    Generates SELL signal when RSI crosses below overbought level
    """

    def __init__(self, parameters: Dict):
        """
        Initialize RSI strategy

        Parameters:
            rsi_period: RSI calculation period
            oversold: Oversold level
            overbought: Overbought level
        """
        super().__init__("RSIStrategy", parameters)
        self.rsi_period = parameters.get('rsi_period', 14)
        self.oversold = parameters.get('oversold', 30)
        self.overbought = parameters.get('overbought', 70)

    def calculate_rsi(self, prices: pd.Series, period: int) -> pd.Series:
        """Calculate RSI indicator"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate RSI"""
        df = data.copy()
        df['rsi'] = self.calculate_rsi(df['close'], self.rsi_period)
        return df

    def generate_signal(self, data: pd.DataFrame) -> SignalType:
        """Generate trading signal based on RSI"""
        if len(data) < self.rsi_period + 1:
            return 'HOLD'

        current = data.iloc[-1]
        previous = data.iloc[-2]

        if pd.isna(current['rsi']):
            return 'HOLD'

        # Buy signal: RSI crosses above oversold level
        if previous['rsi'] <= self.oversold and current['rsi'] > self.oversold:
            return 'BUY'

        # Sell signal: RSI crosses below overbought level
        elif previous['rsi'] >= self.overbought and current['rsi'] < self.overbought:
            return 'SELL'

        return 'HOLD'


class BollingerBandsStrategy(TradingStrategy):
    """
    Bollinger Bands Strategy

    Generates BUY signal when price touches lower band
    Generates SELL signal when price touches upper band
    """

    def __init__(self, parameters: Dict):
        """
        Initialize Bollinger Bands strategy

        Parameters:
            period: Moving average period
            std_dev: Standard deviation multiplier
        """
        super().__init__("BollingerBandsStrategy", parameters)
        self.period = parameters.get('period', 20)
        self.std_dev = parameters.get('std_dev', 2)

    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate Bollinger Bands"""
        df = data.copy()

        df['bb_middle'] = df['close'].rolling(window=self.period).mean()
        df['bb_std'] = df['close'].rolling(window=self.period).std()
        df['bb_upper'] = df['bb_middle'] + (df['bb_std'] * self.std_dev)
        df['bb_lower'] = df['bb_middle'] - (df['bb_std'] * self.std_dev)

        # Calculate bandwidth for volatility
        df['bb_bandwidth'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']

        return df

    def generate_signal(self, data: pd.DataFrame) -> SignalType:
        """Generate trading signal based on Bollinger Bands"""
        if len(data) < self.period + 1:
            return 'HOLD'

        current = data.iloc[-1]
        previous = data.iloc[-2]

        if pd.isna(current['bb_upper']) or pd.isna(current['bb_lower']):
            return 'HOLD'

        # Buy signal: price touches or crosses below lower band and bounces back
        if previous['close'] <= previous['bb_lower'] and current['close'] > current['bb_lower']:
            return 'BUY'

        # Sell signal: price touches or crosses above upper band and falls back
        elif previous['close'] >= previous['bb_upper'] and current['close'] < current['bb_upper']:
            return 'SELL'

        return 'HOLD'


class MACDStrategy(TradingStrategy):
    """
    MACD (Moving Average Convergence Divergence) Strategy

    Generates BUY signal when MACD line crosses above signal line
    Generates SELL signal when MACD line crosses below signal line
    """

    def __init__(self, parameters: Dict):
        """
        Initialize MACD strategy

        Parameters:
            fast_period: Fast EMA period
            slow_period: Slow EMA period
            signal_period: Signal line period
        """
        super().__init__("MACDStrategy", parameters)
        self.fast_period = parameters.get('fast_period', 12)
        self.slow_period = parameters.get('slow_period', 26)
        self.signal_period = parameters.get('signal_period', 9)

    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate MACD"""
        df = data.copy()

        # Calculate EMAs
        df['ema_fast'] = df['close'].ewm(span=self.fast_period, adjust=False).mean()
        df['ema_slow'] = df['close'].ewm(span=self.slow_period, adjust=False).mean()

        # Calculate MACD line and signal line
        df['macd'] = df['ema_fast'] - df['ema_slow']
        df['macd_signal'] = df['macd'].ewm(span=self.signal_period, adjust=False).mean()
        df['macd_histogram'] = df['macd'] - df['macd_signal']

        return df

    def generate_signal(self, data: pd.DataFrame) -> SignalType:
        """Generate trading signal based on MACD"""
        if len(data) < self.slow_period + self.signal_period:
            return 'HOLD'

        current = data.iloc[-1]
        previous = data.iloc[-2]

        if pd.isna(current['macd']) or pd.isna(current['macd_signal']):
            return 'HOLD'

        # Buy signal: MACD crosses above signal line
        if previous['macd'] <= previous['macd_signal'] and current['macd'] > current['macd_signal']:
            return 'BUY'

        # Sell signal: MACD crosses below signal line
        elif previous['macd'] >= previous['macd_signal'] and current['macd'] < current['macd_signal']:
            return 'SELL'

        return 'HOLD'


class TangoStrategy(TradingStrategy):
    """
    Tango Strategy - P&L based hedging strategy

    Rules:
    1. When a position reaches $10 loss, open 2 opposite positions
    2. No TP/SL on new positions initially
    3. When a position reaches +$20 profit, set SL at entry (breakeven)
    4. Every additional $20 profit, trail SL by $20
    5. Maximum 3 positions at once (1 losing + 2 profitable opposite)
    """

    def __init__(self, parameters: Dict):
        """
        Initialize Tango strategy

        Parameters:
            loss_trigger: Dollar amount to trigger hedge (default: 10)
            profit_breakeven: Profit threshold to set breakeven SL (default: 20)
            profit_trail_step: Profit increment for trailing SL (default: 20)
            max_positions: Maximum concurrent positions (default: 3)
        """
        super().__init__("TangoStrategy", parameters)
        self.loss_trigger = parameters.get('loss_trigger', 10.0)
        self.profit_breakeven = parameters.get('profit_breakeven', 20.0)
        self.profit_trail_step = parameters.get('profit_trail_step', 20.0)
        self.max_positions = parameters.get('max_positions', 3)

        # Track which positions have triggered hedges
        self.hedged_positions = set()

    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """No indicators needed for Tango strategy"""
        return data

    def generate_signal(self, data: pd.DataFrame) -> SignalType:
        """
        Tango strategy doesn't generate traditional entry signals.
        Use HOLD - position management happens in manage_tango_positions()
        """
        return 'HOLD'

    def should_hedge_position(self, position: Dict) -> bool:
        """
        Check if position should trigger hedge (2 opposite positions)

        Args:
            position: Position dictionary with profit info

        Returns:
            bool: True if position hit loss trigger and not already hedged
        """
        ticket = position['ticket']
        profit = position['profit']

        # Check if position is at loss trigger and not already hedged
        if profit <= -self.loss_trigger and ticket not in self.hedged_positions:
            return True

        return False

    def calculate_trailing_stop(self, position: Dict, current_price: float) -> float:
        """
        Calculate trailing stop loss based on profit level

        Args:
            position: Position dictionary
            current_price: Current market price

        Returns:
            float: New stop loss price (0 if no change needed)
        """
        profit = position['profit']
        entry_price = position['price_open']
        position_type = position['type']

        # No SL adjustment if profit less than breakeven threshold
        if profit < self.profit_breakeven:
            return 0.0

        # Calculate how many $20 increments above breakeven
        profit_steps = int(profit / self.profit_trail_step)

        if profit_steps < 1:
            return 0.0

        # Calculate SL distance from entry
        # First step: breakeven (0 distance)
        # Each additional step: add $20 protection
        sl_distance_dollars = (profit_steps - 1) * self.profit_trail_step

        # Convert dollar distance to price distance
        volume = position['volume']

        if volume == 0:
            return 0.0

        # Approximate price distance (simplified)
        # For more accuracy, need symbol contract size and point value
        point_value = self.parameters.get('point_value', 0.0001)
        contract_size = self.parameters.get('contract_size', 100000)

        # Calculate how much price movement equals sl_distance_dollars
        price_distance = sl_distance_dollars / (volume * contract_size * (1 / point_value))

        # Calculate new SL
        if position_type == 'BUY':
            new_sl = entry_price + price_distance
        else:  # SELL
            new_sl = entry_price - price_distance

        # Only return if it's better than current SL
        current_sl = position.get('sl', 0.0)

        if position_type == 'BUY':
            if new_sl > current_sl:
                return new_sl
        else:  # SELL
            if current_sl == 0.0 or new_sl < current_sl:
                return new_sl

        return 0.0

    def mark_position_hedged(self, ticket: int):
        """Mark position as hedged to prevent multiple hedge triggers"""
        self.hedged_positions.add(ticket)

    def remove_hedged_position(self, ticket: int):
        """Remove position from hedged tracking (when position closes)"""
        self.hedged_positions.discard(ticket)
