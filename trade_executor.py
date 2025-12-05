"""
Trade Execution Module
Handles order execution and position management
"""

import logging
from typing import Optional, Dict, List
from mt5_connector import MT5Connector
from risk_manager import RiskManager
from strategy_base import SignalType


class TradeExecutor:
    """Executes trades and manages positions"""

    def __init__(self, connector: MT5Connector, risk_manager: RiskManager,
                 symbol: str, magic_number: int, lot_size: Optional[float] = None):
        """
        Initialize trade executor

        Args:
            connector: MT5 connector instance
            risk_manager: Risk manager instance
            symbol: Trading symbol
            magic_number: Magic number for identifying bot's orders
            lot_size: Fixed lot size (if None, will use risk-based sizing)
        """
        self.connector = connector
        self.risk_manager = risk_manager
        self.symbol = symbol
        self.magic_number = magic_number
        self.fixed_lot_size = lot_size
        self.logger = logging.getLogger(__name__)

    def execute_signal(self, signal: SignalType, current_price: float) -> bool:
        """
        Execute trading signal

        Args:
            signal: Trading signal ('BUY', 'SELL', 'HOLD', 'CLOSE')
            current_price: Current market price

        Returns:
            bool: True if action was taken successfully
        """
        if signal == 'HOLD':
            return True

        # Get current positions
        positions = self.connector.get_positions(symbol=self.symbol)
        positions = [p for p in positions if p['magic'] == self.magic_number]

        # Handle CLOSE signal
        if signal == 'CLOSE':
            return self._close_all_positions(positions)

        # Get account info
        account_info = self.connector.get_account_info()
        if account_info is None:
            self.logger.error("Failed to get account info")
            return False

        # Check if we already have a position in the same direction
        if self._has_position_in_direction(positions, signal):
            self.logger.info(f"Already have a {signal} position, skipping")
            return True

        # Check if we can open a new trade
        can_trade, reason = self.risk_manager.can_open_trade(account_info, positions)
        if not can_trade:
            self.logger.warning(f"Cannot open trade: {reason}")
            return False

        # Get symbol info
        symbol_info = self.connector.get_symbol_info(self.symbol)
        if symbol_info is None:
            self.logger.error(f"Failed to get symbol info for {self.symbol}")
            return False

        # Calculate stop loss and take profit
        if signal == 'BUY':
            entry_price = symbol_info['ask']
        else:
            entry_price = symbol_info['bid']

        sl = self._calculate_stop_loss(signal, entry_price, symbol_info)
        tp = self._calculate_take_profit(signal, entry_price, symbol_info)

        # Calculate position size
        if self.fixed_lot_size:
            volume = self.fixed_lot_size
        else:
            volume = self.risk_manager.calculate_position_size(
                account_info['balance'], entry_price, sl, symbol_info
            )

        if volume == 0:
            self.logger.error("Invalid position size calculated")
            return False

        # Validate trade parameters
        is_valid, validation_msg = self.risk_manager.validate_trade_parameters(
            symbol_info, volume, sl, tp
        )
        if not is_valid:
            self.logger.error(f"Trade validation failed: {validation_msg}")
            return False

        # Calculate risk/reward
        rr_ratio = self.risk_manager.get_risk_reward_ratio(entry_price, sl, tp)
        self.logger.info(f"Risk/Reward ratio: {rr_ratio:.2f}")

        # Execute order
        order_type = 'BUY' if signal == 'BUY' else 'SELL'
        comment = f"Bot_{self.magic_number}_{order_type}"

        result = self.connector.send_order(
            symbol=self.symbol,
            order_type=order_type,
            volume=volume,
            price=entry_price,
            sl=sl,
            tp=tp,
            magic=self.magic_number,
            comment=comment
        )

        if result:
            self.logger.info(f"Order executed successfully: {result}")
            return True
        else:
            self.logger.error("Failed to execute order")
            return False

    def manage_positions(self) -> bool:
        """
        Manage existing positions (trailing stops, etc.)

        Returns:
            bool: True if management was successful
        """
        positions = self.connector.get_positions(symbol=self.symbol)
        positions = [p for p in positions if p['magic'] == self.magic_number]

        if not positions:
            return True

        # Get current price
        symbol_info = self.connector.get_symbol_info(self.symbol)
        if symbol_info is None:
            self.logger.error("Failed to get symbol info")
            return False

        for position in positions:
            # Determine current price based on position type
            if position['type'] == 'BUY':
                current_price = symbol_info['bid']
            else:
                current_price = symbol_info['ask']

            # Check if position should be closed
            should_close, reason = self.risk_manager.should_close_position(
                position, current_price
            )

            if should_close:
                self.logger.info(f"Closing position {position['ticket']}: {reason}")
                success = self.connector.close_position(position['ticket'])

                if success:
                    # Update daily profit tracking
                    self.risk_manager.update_daily_profit(position['profit'])
                else:
                    self.logger.error(f"Failed to close position {position['ticket']}")

        return True

    def close_all_positions(self) -> bool:
        """
        Close all positions for this symbol and magic number

        Returns:
            bool: True if all positions closed successfully
        """
        positions = self.connector.get_positions(symbol=self.symbol)
        positions = [p for p in positions if p['magic'] == self.magic_number]

        return self._close_all_positions(positions)

    def _close_all_positions(self, positions: List[Dict]) -> bool:
        """Close all given positions"""
        if not positions:
            self.logger.info("No positions to close")
            return True

        success = True
        for position in positions:
            result = self.connector.close_position(position['ticket'])

            if result:
                self.logger.info(f"Closed position {position['ticket']}")
                # Update daily profit tracking
                self.risk_manager.update_daily_profit(position['profit'])
            else:
                self.logger.error(f"Failed to close position {position['ticket']}")
                success = False

        return success

    def _has_position_in_direction(self, positions: List[Dict], signal: SignalType) -> bool:
        """Check if there's already a position in the signal direction"""
        for position in positions:
            if position['type'] == signal:
                return True
        return False

    def _calculate_stop_loss(self, signal: SignalType, entry_price: float,
                            symbol_info: Dict) -> float:
        """Calculate stop loss price"""
        point = symbol_info['point']
        sl_pips = self.risk_manager.stop_loss_pips

        if signal == 'BUY':
            return entry_price - (sl_pips * point * 10)  # *10 for pips vs points
        elif signal == 'SELL':
            return entry_price + (sl_pips * point * 10)
        else:
            return 0.0

    def _calculate_take_profit(self, signal: SignalType, entry_price: float,
                               symbol_info: Dict) -> float:
        """Calculate take profit price"""
        point = symbol_info['point']
        tp_pips = self.risk_manager.take_profit_pips

        if signal == 'BUY':
            return entry_price + (tp_pips * point * 10)  # *10 for pips vs points
        elif signal == 'SELL':
            return entry_price - (tp_pips * point * 10)
        else:
            return 0.0

    def get_position_summary(self) -> Dict:
        """
        Get summary of current positions

        Returns:
            Dictionary with position summary
        """
        positions = self.connector.get_positions(symbol=self.symbol)
        positions = [p for p in positions if p['magic'] == self.magic_number]

        if not positions:
            return {
                'count': 0,
                'total_profit': 0.0,
                'positions': []
            }

        total_profit = sum(p['profit'] for p in positions)

        return {
            'count': len(positions),
            'total_profit': total_profit,
            'positions': positions
        }
