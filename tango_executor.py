"""
Tango Strategy Trade Executor
Specialized executor for the Tango hedging strategy
"""

import logging
from typing import Optional, Dict, List
from mt5_connector import MT5Connector
from risk_manager import RiskManager
from strategies import TangoStrategy


class TangoExecutor:
    """Executes and manages trades for Tango strategy"""

    def __init__(self, connector: MT5Connector, strategy: TangoStrategy,
                 symbol: str, magic_number: int, lot_size: float):
        """
        Initialize Tango executor

        Args:
            connector: MT5 connector instance
            strategy: TangoStrategy instance
            symbol: Trading symbol
            magic_number: Magic number for identifying bot's orders
            lot_size: Lot size for new positions
        """
        self.connector = connector
        self.strategy = strategy
        self.symbol = symbol
        self.magic_number = magic_number
        self.lot_size = lot_size
        self.logger = logging.getLogger(__name__)

    def manage_tango_positions(self) -> bool:
        """
        Main Tango strategy logic:
        1. Check positions for $10 loss trigger -> open 2 opposite positions
        2. Check positions for $20 profit -> set breakeven/trailing SL
        3. Enforce max 3 positions limit

        Returns:
            bool: True if management successful
        """
        try:
            # Get current positions
            positions = self.connector.get_positions(symbol=self.symbol)
            positions = [p for p in positions if p['magic'] == self.magic_number]

            if not positions:
                self.logger.debug("No positions to manage")
                return True

            # Get symbol info for current prices
            symbol_info = self.connector.get_symbol_info(self.symbol)
            if symbol_info is None:
                self.logger.error("Failed to get symbol info")
                return False

            # Process each position
            for position in positions:
                # Check for hedge trigger (position at $10 loss)
                if self.strategy.should_hedge_position(position):
                    self._execute_hedge(position, symbol_info)

                # Check for trailing stop updates
                self._update_trailing_stop(position, symbol_info)

            # Clean up closed positions from hedged tracking
            self._cleanup_closed_positions(positions)

            return True

        except Exception as e:
            self.logger.error(f"Error managing Tango positions: {e}", exc_info=True)
            return False

    def _execute_hedge(self, losing_position: Dict, symbol_info: Dict) -> bool:
        """
        Execute hedge: open 2 opposite positions when loss trigger hit

        Args:
            losing_position: Position that triggered the hedge
            symbol_info: Symbol information

        Returns:
            bool: True if hedge executed successfully
        """
        # Check max positions limit
        current_positions = self.connector.get_positions(symbol=self.symbol)
        current_positions = [p for p in current_positions if p['magic'] == self.magic_number]

        if len(current_positions) >= self.strategy.max_positions:
            self.logger.warning(f"Cannot hedge: Already at max positions ({self.strategy.max_positions})")
            return False

        # Determine opposite direction
        losing_type = losing_position['type']
        opposite_type = 'SELL' if losing_type == 'BUY' else 'BUY'

        # Calculate how many positions we can open (max 2, but limited by max_positions)
        available_slots = self.strategy.max_positions - len(current_positions)
        positions_to_open = min(2, available_slots)

        if positions_to_open == 0:
            self.logger.warning("Cannot hedge: No available position slots")
            return False

        self.logger.info(
            f"Triggering hedge for position {losing_position['ticket']} "
            f"(${losing_position['profit']:.2f} loss). "
            f"Opening {positions_to_open} {opposite_type} position(s)"
        )

        # Open opposite positions (no SL/TP initially)
        success_count = 0
        for i in range(positions_to_open):
            if opposite_type == 'BUY':
                entry_price = symbol_info['ask']
            else:
                entry_price = symbol_info['bid']

            comment = f"Tango_Hedge_{losing_position['ticket']}_{i+1}"

            result = self.connector.send_order(
                symbol=self.symbol,
                order_type=opposite_type,
                volume=self.lot_size,
                price=entry_price,
                sl=0.0,  # No stop loss initially
                tp=0.0,  # No take profit
                magic=self.magic_number,
                comment=comment
            )

            if result:
                self.logger.info(f"Hedge position {i+1} opened: {result}")
                success_count += 1
            else:
                self.logger.error(f"Failed to open hedge position {i+1}")

        # Mark the losing position as hedged
        if success_count > 0:
            self.strategy.mark_position_hedged(losing_position['ticket'])
            return True

        return False

    def _update_trailing_stop(self, position: Dict, symbol_info: Dict) -> bool:
        """
        Update trailing stop based on profit level

        Args:
            position: Position to update
            symbol_info: Symbol information

        Returns:
            bool: True if update successful
        """
        # Determine current price
        if position['type'] == 'BUY':
            current_price = symbol_info['bid']
        else:
            current_price = symbol_info['ask']

        # Calculate new trailing stop
        new_sl = self.strategy.calculate_trailing_stop(position, current_price)

        if new_sl == 0.0:
            # No update needed
            return True

        # Update stop loss
        current_sl = position.get('sl', 0.0)

        self.logger.info(
            f"Updating trailing SL for position {position['ticket']}: "
            f"${position['profit']:.2f} profit, "
            f"SL {current_sl:.5f} -> {new_sl:.5f}"
        )

        result = self.connector.modify_position(
            ticket=position['ticket'],
            sl=new_sl,
            tp=position.get('tp', 0.0)
        )

        if result:
            self.logger.info(f"Trailing stop updated successfully")
            return True
        else:
            self.logger.error(f"Failed to update trailing stop")
            return False

    def _cleanup_closed_positions(self, open_positions: List[Dict]):
        """
        Remove closed positions from hedged tracking

        Args:
            open_positions: List of currently open positions
        """
        open_tickets = {p['ticket'] for p in open_positions}

        # Remove any hedged position tickets that are no longer open
        for ticket in list(self.strategy.hedged_positions):
            if ticket not in open_tickets:
                self.strategy.remove_hedged_position(ticket)

    def open_initial_position(self, order_type: str) -> bool:
        """
        Open initial position to start the Tango strategy

        Args:
            order_type: 'BUY' or 'SELL'

        Returns:
            bool: True if position opened successfully
        """
        # Check max positions
        current_positions = self.connector.get_positions(symbol=self.symbol)
        current_positions = [p for p in current_positions if p['magic'] == self.magic_number]

        if len(current_positions) >= self.strategy.max_positions:
            self.logger.warning(f"Cannot open position: Already at max positions")
            return False

        # Get symbol info
        symbol_info = self.connector.get_symbol_info(self.symbol)
        if symbol_info is None:
            self.logger.error("Failed to get symbol info")
            return False

        # Get entry price
        if order_type == 'BUY':
            entry_price = symbol_info['ask']
        else:
            entry_price = symbol_info['bid']

        # Open position (no SL/TP)
        comment = f"Tango_Initial"

        result = self.connector.send_order(
            symbol=self.symbol,
            order_type=order_type,
            volume=self.lot_size,
            price=entry_price,
            sl=0.0,  # No stop loss initially
            tp=0.0,  # No take profit
            magic=self.magic_number,
            comment=comment
        )

        if result:
            self.logger.info(f"Initial {order_type} position opened: {result}")
            return True
        else:
            self.logger.error("Failed to open initial position")
            return False

    def close_all_positions(self) -> bool:
        """
        Close all Tango positions

        Returns:
            bool: True if all positions closed successfully
        """
        positions = self.connector.get_positions(symbol=self.symbol)
        positions = [p for p in positions if p['magic'] == self.magic_number]

        if not positions:
            self.logger.info("No positions to close")
            return True

        success = True
        for position in positions:
            result = self.connector.close_position(position['ticket'])

            if result:
                self.logger.info(f"Closed position {position['ticket']}")
                self.strategy.remove_hedged_position(position['ticket'])
            else:
                self.logger.error(f"Failed to close position {position['ticket']}")
                success = False

        return success

    def get_position_summary(self) -> Dict:
        """
        Get summary of current Tango positions

        Returns:
            Dictionary with position summary
        """
        positions = self.connector.get_positions(symbol=self.symbol)
        positions = [p for p in positions if p['magic'] == self.magic_number]

        if not positions:
            return {
                'count': 0,
                'total_profit': 0.0,
                'losing_positions': 0,
                'winning_positions': 0,
                'hedged_count': len(self.strategy.hedged_positions),
                'positions': []
            }

        total_profit = sum(p['profit'] for p in positions)
        losing_count = sum(1 for p in positions if p['profit'] < 0)
        winning_count = sum(1 for p in positions if p['profit'] > 0)

        return {
            'count': len(positions),
            'total_profit': total_profit,
            'losing_positions': losing_count,
            'winning_positions': winning_count,
            'hedged_count': len(self.strategy.hedged_positions),
            'positions': positions
        }
