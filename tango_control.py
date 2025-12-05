#!/usr/bin/env python3
"""
Tango Strategy Control Script
Helper script to manually control Tango strategy positions
"""

import os
import sys
import yaml
import argparse
from dotenv import load_dotenv

from mt5_connector import MT5Connector
from strategies import TangoStrategy
from tango_executor import TangoExecutor
from logger_config import setup_logging
import logging


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Tango Strategy Control')
    parser.add_argument('--config', default='config.yaml', help='Configuration file path')

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Open initial position
    open_parser = subparsers.add_parser('open', help='Open initial position')
    open_parser.add_argument('direction', choices=['BUY', 'SELL'], help='Position direction')

    # Close all positions
    subparsers.add_parser('close-all', help='Close all Tango positions')

    # Show status
    subparsers.add_parser('status', help='Show current Tango positions')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Load environment and config
    load_dotenv()

    with open(args.config, 'r') as f:
        config = yaml.safe_load(f)

    # Setup logging
    setup_logging(config['logging'])
    logger = logging.getLogger(__name__)

    # Get MT5 credentials
    login = int(os.getenv('MT5_LOGIN', 0))
    password = os.getenv('MT5_PASSWORD', '')
    server = os.getenv('MT5_SERVER', '')

    if not all([login, password, server]):
        logger.error("MT5 credentials not found in .env file")
        return

    # Connect to MT5
    connector = MT5Connector(login, password, server)

    if not connector.connect():
        logger.error("Failed to connect to MT5")
        return

    logger.info("Connected to MT5")

    # Get trading parameters
    symbol = os.getenv('SYMBOL', config['trading']['symbol'])
    lot_size = float(os.getenv('LOT_SIZE', config['trading']['lot_size']))
    magic_number = int(os.getenv('MAGIC_NUMBER', config['trading']['magic_number']))

    # Initialize Tango strategy and executor
    strategy_params = config['strategy']['parameters'].copy()
    strategy = TangoStrategy(strategy_params)

    executor = TangoExecutor(
        connector,
        strategy,
        symbol,
        magic_number,
        lot_size
    )

    try:
        if args.command == 'open':
            # Open initial position
            logger.info(f"Opening initial {args.direction} position...")
            result = executor.open_initial_position(args.direction)

            if result:
                print(f"\n✓ Initial {args.direction} position opened successfully!")
                print(f"Symbol: {symbol}")
                print(f"Lot Size: {lot_size}")
                print(f"Magic Number: {magic_number}")
                print("\nThe bot will now monitor this position and:")
                print("  • Open 2 opposite positions when it reaches -$10 loss")
                print("  • Set breakeven SL when profit reaches +$20")
                print("  • Trail SL by $20 for every additional $20 profit")
            else:
                print(f"\n✗ Failed to open position")

        elif args.command == 'close-all':
            # Close all positions
            logger.info("Closing all Tango positions...")
            result = executor.close_all_positions()

            if result:
                print("\n✓ All positions closed successfully!")
            else:
                print("\n✗ Failed to close some positions")

        elif args.command == 'status':
            # Show status
            summary = executor.get_position_summary()

            print("\n=== Tango Strategy Status ===")
            print(f"Symbol: {symbol}")
            print(f"Magic Number: {magic_number}")
            print(f"\nOpen Positions: {summary['count']}")
            print(f"Total P&L: ${summary['total_profit']:.2f}")
            print(f"Losing Positions: {summary['losing_positions']}")
            print(f"Winning Positions: {summary['winning_positions']}")
            print(f"Hedged Positions: {summary['hedged_count']}")

            if summary['positions']:
                print("\n=== Position Details ===")
                for pos in summary['positions']:
                    print(f"\nTicket: {pos['ticket']}")
                    print(f"  Type: {pos['type']}")
                    print(f"  Volume: {pos['volume']}")
                    print(f"  Entry: {pos['price_open']:.5f}")
                    print(f"  Current: {pos['price_current']:.5f}")
                    print(f"  P&L: ${pos['profit']:.2f}")
                    print(f"  SL: {pos.get('sl', 0.0):.5f}")
                    print(f"  Comment: {pos.get('comment', 'N/A')}")

    finally:
        # Disconnect
        connector.disconnect()
        logger.info("Disconnected from MT5")


if __name__ == '__main__':
    main()
