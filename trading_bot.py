"""
Main Trading Bot
Orchestrates all components and runs the trading loop
"""

import time
import signal
import sys
import os
from datetime import datetime, timedelta
from typing import Optional
import yaml

from mt5_connector import MT5Connector
from risk_manager import RiskManager
from trade_executor import TradeExecutor
from tango_executor import TangoExecutor
from strategies import MovingAverageCrossover, RSIStrategy, BollingerBandsStrategy, MACDStrategy, TangoStrategy
from strategy_base import TradingStrategy
from logger_config import setup_logging, log_trade, log_position_closed, log_daily_summary
import logging


class TradingBot:
    """Main trading bot class"""

    def __init__(self, config_file: str = 'config.yaml'):
        """
        Initialize trading bot

        Args:
            config_file: Path to configuration file
        """
        # Load configuration
        with open(config_file, 'r') as f:
            self.config = yaml.safe_load(f)

        # Setup logging
        setup_logging(self.config['logging'])
        self.logger = logging.getLogger(__name__)

        # Initialize components
        self.running = False
        self.connector: Optional[MT5Connector] = None
        self.risk_manager: Optional[RiskManager] = None
        self.executor: Optional[TradeExecutor] = None
        self.tango_executor: Optional[TangoExecutor] = None
        self.strategy: Optional[TradingStrategy] = None
        self.is_tango_strategy = False

        # Trading parameters
        self.symbol = self.config['trading']['symbol']
        self.timeframe = self.config['trading']['timeframe']
        self.lot_size = self.config['trading']['lot_size']
        self.magic_number = self.config['trading']['magic_number']

        # Bot state
        self.last_bar_time = None
        self.last_daily_summary = datetime.now().date()

        self.logger.info("Trading bot initialized")

    def connect(self) -> bool:
        """
        Connect to MT5 and initialize components

        Returns:
            bool: True if connection successful
        """
        # Get MT5 credentials from config
        mt5_config = self.config.get('mt5', {})
        login = mt5_config.get('login', 0)
        password = mt5_config.get('password', '')
        server = mt5_config.get('server', '')

        if not all([login, password, server]):
            self.logger.error("MT5 credentials not found in config.yaml")
            self.logger.error("Please configure mt5 section in config.yaml with login, password, and server")
            return False

        # Initialize MT5 connector
        self.connector = MT5Connector(login, password, server)

        if not self.connector.connect():
            self.logger.error("Failed to connect to MT5")
            return False

        # Initialize risk manager
        self.risk_manager = RiskManager(self.config['risk_management'])

        # Initialize strategy
        strategy_type = self.config['strategy']['type']
        strategy_params = self.config['strategy']['parameters'].copy()

        # Add risk parameters to strategy
        strategy_params.update({
            'stop_loss_pips': self.config['risk_management']['stop_loss_pips'],
            'take_profit_pips': self.config['risk_management']['take_profit_pips']
        })

        if strategy_type == 'moving_average_crossover':
            self.strategy = MovingAverageCrossover(strategy_params)
        elif strategy_type == 'rsi':
            self.strategy = RSIStrategy(strategy_params)
        elif strategy_type == 'bollinger_bands':
            self.strategy = BollingerBandsStrategy(strategy_params)
        elif strategy_type == 'macd':
            self.strategy = MACDStrategy(strategy_params)
        elif strategy_type == 'tango':
            self.strategy = TangoStrategy(strategy_params)
            self.is_tango_strategy = True
        else:
            self.logger.error(f"Unknown strategy type: {strategy_type}")
            return False

        # Initialize executor based on strategy type
        if self.is_tango_strategy:
            # Use specialized Tango executor
            self.tango_executor = TangoExecutor(
                self.connector,
                self.strategy,
                self.symbol,
                self.magic_number,
                self.lot_size
            )
            self.logger.info("Tango strategy executor initialized")
        else:
            # Use standard trade executor
            self.executor = TradeExecutor(
                self.connector,
                self.risk_manager,
                self.symbol,
                self.magic_number,
                self.lot_size
            )

        self.logger.info(f"Strategy initialized: {self.strategy.name}")
        self.logger.info(f"Trading {self.symbol} on {self.timeframe} timeframe")

        return True

    def run(self):
        """Run the trading bot main loop"""
        if not self.connect():
            self.logger.error("Failed to initialize bot")
            return

        self.running = True

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        self.logger.info("Trading bot started")
        self.logger.info("Press Ctrl+C to stop")

        try:
            while self.running:
                self._trading_loop()
                time.sleep(1)  # Sleep for 1 second between iterations

        except Exception as e:
            self.logger.error(f"Error in main loop: {e}", exc_info=True)

        finally:
            self.shutdown()

    def _trading_loop(self):
        """Execute one iteration of the trading loop"""
        try:
            if self.is_tango_strategy:
                # Tango strategy uses position-based management
                self.tango_executor.manage_tango_positions()
            else:
                # Standard strategy uses indicator-based signals
                # Get latest bars
                bars = self.connector.get_bars(self.symbol, self.timeframe, count=200)

                if bars is None or len(bars) == 0:
                    self.logger.warning("No data received")
                    return

                # Check if new bar formed
                latest_bar_time = bars.iloc[-1]['time']

                if self.last_bar_time is None or latest_bar_time > self.last_bar_time:
                    self.last_bar_time = latest_bar_time
                    self.logger.debug(f"New bar formed at {latest_bar_time}")

                    # Generate signal
                    signal = self.strategy.on_bar(bars)

                    if signal != 'HOLD':
                        self.logger.info(f"Signal generated: {signal}")

                        # Get current price
                        symbol_info = self.connector.get_symbol_info(self.symbol)
                        if symbol_info:
                            current_price = symbol_info['bid']

                            # Execute signal
                            self.executor.execute_signal(signal, current_price)

                # Manage existing positions
                self.executor.manage_positions()

            # Log daily summary
            self._check_daily_summary()

        except Exception as e:
            self.logger.error(f"Error in trading loop: {e}", exc_info=True)

    def _check_daily_summary(self):
        """Check and log daily summary if day changed"""
        today = datetime.now().date()

        if today > self.last_daily_summary:
            # Get yesterday's stats
            stats = self.risk_manager.get_daily_statistics()
            log_daily_summary(stats)

            self.last_daily_summary = today

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info("Shutdown signal received")
        self.running = False

    def shutdown(self):
        """Shutdown the bot gracefully"""
        self.logger.info("Shutting down bot...")

        # Log final daily summary
        if self.risk_manager:
            stats = self.risk_manager.get_daily_statistics()
            log_daily_summary(stats)

        # Close all positions (optional - comment out if you want to keep them open)
        if self.is_tango_strategy and self.tango_executor:
            # self.tango_executor.close_all_positions()
            pass
        elif self.executor:
            # self.executor.close_all_positions()
            pass

        # Disconnect from MT5
        if self.connector:
            self.connector.disconnect()

        self.logger.info("Bot shutdown complete")

    def get_status(self) -> dict:
        """
        Get current bot status

        Returns:
            Dictionary with bot status information
        """
        if not self.connector or not self.connector.connected:
            return {'status': 'disconnected'}

        account_info = self.connector.get_account_info()

        if self.is_tango_strategy:
            position_summary = self.tango_executor.get_position_summary()
        else:
            position_summary = self.executor.get_position_summary()

        daily_stats = self.risk_manager.get_daily_statistics()

        return {
            'status': 'running' if self.running else 'stopped',
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'strategy': self.strategy.name,
            'account': {
                'balance': account_info['balance'],
                'equity': account_info['equity'],
                'profit': account_info['profit'],
                'margin_level': account_info['margin_level']
            },
            'positions': position_summary,
            'daily_stats': daily_stats
        }


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='MT5 Trading Bot')
    parser.add_argument('--config', default='config.yaml', help='Configuration file path')
    parser.add_argument('--status', action='store_true', help='Show bot status and exit')

    args = parser.parse_args()

    bot = TradingBot(args.config)

    if args.status:
        # Just show status
        if bot.connect():
            status = bot.get_status()
            print("\n=== Bot Status ===")
            print(f"Status: {status['status']}")
            print(f"Symbol: {status['symbol']}")
            print(f"Timeframe: {status['timeframe']}")
            print(f"Strategy: {status['strategy']}")
            print(f"\n=== Account ===")
            print(f"Balance: {status['account']['balance']:.2f}")
            print(f"Equity: {status['account']['equity']:.2f}")
            print(f"Profit: {status['account']['profit']:.2f}")
            print(f"Margin Level: {status['account']['margin_level']:.2f}%")
            print(f"\n=== Positions ===")
            print(f"Open Positions: {status['positions']['count']}")
            print(f"Total Profit: {status['positions']['total_profit']:.2f}")
            print(f"\n=== Daily Stats ===")
            print(f"Total Trades: {status['daily_stats']['total_trades']}")
            print(f"Win Rate: {status['daily_stats']['win_rate']*100:.2f}%")
            print(f"Total Profit: {status['daily_stats']['total_profit']:.2f}")
            bot.shutdown()
    else:
        # Run the bot
        bot.run()


if __name__ == '__main__':
    main()
