"""
Risk Management Module
Handles position sizing, risk limits, and trade validation
"""

import logging
from typing import Dict, Optional, List
from datetime import datetime, timedelta


class RiskManager:
    """Manages trading risk and position sizing"""

    def __init__(self, config: Dict):
        """
        Initialize risk manager

        Args:
            config: Risk management configuration
        """
        self.max_risk_per_trade = config.get('max_risk_per_trade', 0.02)
        self.max_daily_loss = config.get('max_daily_loss', 0.05)
        self.max_positions = config.get('max_positions', 3)
        self.stop_loss_pips = config.get('stop_loss_pips', 50)
        self.take_profit_pips = config.get('take_profit_pips', 100)
        self.trailing_stop = config.get('trailing_stop', False)
        self.trailing_stop_pips = config.get('trailing_stop_pips', 30)

        self.daily_trades = []
        self.daily_profit = 0.0
        self.last_reset_date = datetime.now().date()

        self.logger = logging.getLogger(__name__)

    def reset_daily_stats(self):
        """Reset daily statistics"""
        today = datetime.now().date()
        if today > self.last_reset_date:
            self.daily_trades = []
            self.daily_profit = 0.0
            self.last_reset_date = today
            self.logger.info("Daily statistics reset")

    def calculate_position_size(self, account_balance: float, entry_price: float,
                                stop_loss_price: float, symbol_info: Dict) -> float:
        """
        Calculate position size based on risk parameters

        Args:
            account_balance: Current account balance
            entry_price: Planned entry price
            stop_loss_price: Stop loss price
            symbol_info: Symbol information dictionary

        Returns:
            Recommended lot size
        """
        # Maximum risk amount in account currency
        max_risk_amount = account_balance * self.max_risk_per_trade

        # Calculate pips at risk
        point_value = symbol_info.get('point', 0.0001)
        pips_at_risk = abs(entry_price - stop_loss_price) / point_value

        # Calculate lot size
        contract_size = symbol_info.get('trade_contract_size', 100000)
        value_per_pip = contract_size * point_value

        if pips_at_risk == 0:
            self.logger.warning("Pips at risk is zero, cannot calculate position size")
            return 0.0

        lot_size = max_risk_amount / (pips_at_risk * value_per_pip)

        # Round to symbol's volume step
        volume_min = symbol_info.get('volume_min', 0.01)
        volume_max = symbol_info.get('volume_max', 100.0)
        volume_step = symbol_info.get('volume_step', 0.01)

        # Round down to nearest step
        lot_size = round(lot_size / volume_step) * volume_step

        # Ensure within limits
        lot_size = max(volume_min, min(lot_size, volume_max))

        self.logger.info(f"Calculated position size: {lot_size} lots (Risk: {self.max_risk_per_trade * 100}%)")

        return lot_size

    def can_open_trade(self, account_info: Dict, current_positions: List[Dict]) -> tuple[bool, str]:
        """
        Check if new trade can be opened based on risk rules

        Args:
            account_info: Account information dictionary
            current_positions: List of current open positions

        Returns:
            Tuple of (can_trade: bool, reason: str)
        """
        self.reset_daily_stats()

        # Check maximum positions
        if len(current_positions) >= self.max_positions:
            return False, f"Maximum positions reached ({self.max_positions})"

        # Check daily loss limit
        account_balance = account_info.get('balance', 0)
        max_daily_loss_amount = account_balance * self.max_daily_loss

        if self.daily_profit < -max_daily_loss_amount:
            return False, f"Daily loss limit reached ({self.max_daily_loss * 100}%)"

        # Check account equity
        equity = account_info.get('equity', 0)
        if equity <= 0:
            return False, "No equity available"

        # Check margin
        margin_level = account_info.get('margin_level', 0)
        if margin_level > 0 and margin_level < 150:  # 150% margin level minimum
            return False, f"Insufficient margin (Level: {margin_level:.2f}%)"

        return True, "OK"

    def update_daily_profit(self, profit: float):
        """
        Update daily profit tracking

        Args:
            profit: Profit/loss amount to add
        """
        self.reset_daily_stats()
        self.daily_profit += profit

        self.daily_trades.append({
            'timestamp': datetime.now(),
            'profit': profit
        })

        self.logger.info(f"Daily profit updated: {self.daily_profit:.2f} ({len(self.daily_trades)} trades)")

    def should_close_position(self, position: Dict, current_price: float) -> tuple[bool, str]:
        """
        Determine if position should be closed based on risk rules

        Args:
            position: Position dictionary
            current_price: Current market price

        Returns:
            Tuple of (should_close: bool, reason: str)
        """
        # Check daily loss limit
        self.reset_daily_stats()

        account_balance = position.get('balance', 0)
        if account_balance > 0:
            max_daily_loss_amount = account_balance * self.max_daily_loss

            if self.daily_profit < -max_daily_loss_amount:
                return True, "Daily loss limit reached"

        # Check trailing stop
        if self.trailing_stop:
            position_type = position.get('type', '').upper()
            price_open = position.get('price_open', 0)
            current_sl = position.get('sl', 0)

            point_value = 0.0001  # Should be from symbol info
            trailing_distance = self.trailing_stop_pips * point_value

            if position_type == 'BUY':
                # Calculate new trailing stop
                new_sl = current_price - trailing_distance

                # If price moved favorably enough, update stop
                if new_sl > current_sl and new_sl > price_open:
                    return False, f"Update trailing stop to {new_sl:.5f}"

            elif position_type == 'SELL':
                # Calculate new trailing stop
                new_sl = current_price + trailing_distance

                # If price moved favorably enough, update stop
                if (current_sl == 0 or new_sl < current_sl) and new_sl < price_open:
                    return False, f"Update trailing stop to {new_sl:.5f}"

        return False, "OK"

    def validate_trade_parameters(self, symbol_info: Dict, volume: float,
                                  sl: float, tp: float) -> tuple[bool, str]:
        """
        Validate trade parameters

        Args:
            symbol_info: Symbol information
            volume: Lot size
            sl: Stop loss price
            tp: Take profit price

        Returns:
            Tuple of (is_valid: bool, reason: str)
        """
        # Check volume limits
        volume_min = symbol_info.get('volume_min', 0.01)
        volume_max = symbol_info.get('volume_max', 100.0)
        volume_step = symbol_info.get('volume_step', 0.01)

        if volume < volume_min:
            return False, f"Volume too small (min: {volume_min})"

        if volume > volume_max:
            return False, f"Volume too large (max: {volume_max})"

        # Check if volume is a valid step
        remainder = (volume - volume_min) % volume_step
        if remainder > 0.0001:  # Small tolerance for floating point
            return False, f"Invalid volume step (step: {volume_step})"

        # Check SL and TP are set (if required by risk rules)
        if sl == 0:
            self.logger.warning("No stop loss set")

        if tp == 0:
            self.logger.warning("No take profit set")

        return True, "OK"

    def get_risk_reward_ratio(self, entry_price: float, sl: float, tp: float) -> float:
        """
        Calculate risk/reward ratio

        Args:
            entry_price: Entry price
            sl: Stop loss price
            tp: Take profit price

        Returns:
            Risk/reward ratio
        """
        if sl == 0 or tp == 0:
            return 0.0

        risk = abs(entry_price - sl)
        reward = abs(tp - entry_price)

        if risk == 0:
            return 0.0

        return reward / risk

    def get_daily_statistics(self) -> Dict:
        """
        Get daily trading statistics

        Returns:
            Dictionary with daily stats
        """
        self.reset_daily_stats()

        winning_trades = [t for t in self.daily_trades if t['profit'] > 0]
        losing_trades = [t for t in self.daily_trades if t['profit'] < 0]

        return {
            'date': self.last_reset_date.isoformat(),
            'total_trades': len(self.daily_trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': len(winning_trades) / len(self.daily_trades) if self.daily_trades else 0,
            'total_profit': self.daily_profit,
            'average_win': sum(t['profit'] for t in winning_trades) / len(winning_trades) if winning_trades else 0,
            'average_loss': sum(t['profit'] for t in losing_trades) / len(losing_trades) if losing_trades else 0
        }
