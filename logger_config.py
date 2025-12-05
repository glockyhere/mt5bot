"""
Logging Configuration
Sets up structured logging for the trading bot
"""

import logging
import logging.handlers
import os
from datetime import datetime
from typing import Dict


def setup_logging(config: Dict) -> logging.Logger:
    """
    Configure logging for the trading bot

    Args:
        config: Logging configuration dictionary

    Returns:
        Configured logger instance
    """
    # Create logs directory if it doesn't exist
    log_file = config.get('file', 'logs/trading_bot.log')
    log_dir = os.path.dirname(log_file)

    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Get logging level
    level_str = config.get('level', 'INFO')
    level = getattr(logging, level_str.upper(), logging.INFO)

    # Create logger
    logger = logging.getLogger()
    logger.setLevel(level)

    # Remove existing handlers
    logger.handlers = []

    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )

    # File handler with rotation
    max_bytes = config.get('max_bytes', 10485760)  # 10MB
    backup_count = config.get('backup_count', 5)

    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(detailed_formatter)
    logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(simple_formatter)
    logger.addHandler(console_handler)

    # Create a separate handler for trade logs
    trade_log_file = os.path.join(log_dir, 'trades.log')
    trade_handler = logging.handlers.RotatingFileHandler(
        trade_log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    trade_handler.setLevel(logging.INFO)
    trade_handler.setFormatter(detailed_formatter)

    # Create trade logger
    trade_logger = logging.getLogger('trade_logger')
    trade_logger.setLevel(logging.INFO)
    trade_logger.addHandler(trade_handler)
    trade_logger.propagate = False

    logger.info("Logging configured successfully")

    return logger


def log_trade(signal: str, symbol: str, volume: float, price: float,
              sl: float, tp: float, ticket: int = None):
    """
    Log trade information

    Args:
        signal: Trade signal (BUY/SELL)
        symbol: Trading symbol
        volume: Position size
        price: Entry price
        sl: Stop loss
        tp: Take profit
        ticket: Order ticket number
    """
    trade_logger = logging.getLogger('trade_logger')

    msg = (
        f"TRADE: {signal} | Symbol: {symbol} | Volume: {volume} | "
        f"Price: {price:.5f} | SL: {sl:.5f} | TP: {tp:.5f}"
    )

    if ticket:
        msg += f" | Ticket: {ticket}"

    trade_logger.info(msg)


def log_position_closed(ticket: int, symbol: str, profit: float, close_price: float):
    """
    Log position close information

    Args:
        ticket: Position ticket
        symbol: Trading symbol
        profit: Profit/loss
        close_price: Close price
    """
    trade_logger = logging.getLogger('trade_logger')

    msg = (
        f"CLOSED: Ticket: {ticket} | Symbol: {symbol} | "
        f"Close Price: {close_price:.5f} | Profit: {profit:.2f}"
    )

    trade_logger.info(msg)


def log_daily_summary(stats: Dict):
    """
    Log daily trading summary

    Args:
        stats: Daily statistics dictionary
    """
    trade_logger = logging.getLogger('trade_logger')

    msg = (
        f"\n{'='*60}\n"
        f"DAILY SUMMARY - {stats['date']}\n"
        f"{'='*60}\n"
        f"Total Trades: {stats['total_trades']}\n"
        f"Winning Trades: {stats['winning_trades']}\n"
        f"Losing Trades: {stats['losing_trades']}\n"
        f"Win Rate: {stats['win_rate']*100:.2f}%\n"
        f"Total Profit: {stats['total_profit']:.2f}\n"
        f"Average Win: {stats['average_win']:.2f}\n"
        f"Average Loss: {stats['average_loss']:.2f}\n"
        f"{'='*60}"
    )

    trade_logger.info(msg)
