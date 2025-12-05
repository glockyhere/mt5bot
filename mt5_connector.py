"""
MT5 Connector Module
Handles connection and communication with MetaTrader 5 platform
"""

import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
from typing import Optional, Dict, List
import logging


class MT5Connector:
    """Manages connection and operations with MT5 terminal"""

    def __init__(self, login: int, password: str, server: str):
        """
        Initialize MT5 connector

        Args:
            login: MT5 account number
            password: MT5 account password
            server: MT5 broker server name
        """
        self.login = login
        self.password = password
        self.server = server
        self.connected = False
        self.logger = logging.getLogger(__name__)

    def connect(self) -> bool:
        """
        Establish connection to MT5 terminal

        Returns:
            bool: True if connection successful, False otherwise
        """
        if not mt5.initialize():
            self.logger.error(f"MT5 initialization failed: {mt5.last_error()}")
            return False

        authorized = mt5.login(self.login, password=self.password, server=self.server)

        if authorized:
            self.connected = True
            account_info = mt5.account_info()
            self.logger.info(f"Connected to MT5 account #{self.login}")
            self.logger.info(f"Balance: {account_info.balance}, Equity: {account_info.equity}")
            return True
        else:
            self.logger.error(f"MT5 login failed: {mt5.last_error()}")
            mt5.shutdown()
            return False

    def disconnect(self):
        """Close connection to MT5 terminal"""
        if self.connected:
            mt5.shutdown()
            self.connected = False
            self.logger.info("Disconnected from MT5")

    def get_account_info(self) -> Optional[Dict]:
        """
        Get account information

        Returns:
            Dict with account information or None if failed
        """
        if not self.connected:
            self.logger.error("Not connected to MT5")
            return None

        account_info = mt5.account_info()
        if account_info is None:
            return None

        return {
            'balance': account_info.balance,
            'equity': account_info.equity,
            'margin': account_info.margin,
            'margin_free': account_info.margin_free,
            'margin_level': account_info.margin_level,
            'profit': account_info.profit,
            'leverage': account_info.leverage
        }

    def get_bars(self, symbol: str, timeframe: str, count: int = 100) -> Optional[pd.DataFrame]:
        """
        Get historical price data

        Args:
            symbol: Trading symbol (e.g., 'EURUSD')
            timeframe: Timeframe string (e.g., 'H1', 'M15')
            count: Number of bars to retrieve

        Returns:
            DataFrame with OHLCV data or None if failed
        """
        if not self.connected:
            self.logger.error("Not connected to MT5")
            return None

        # Convert timeframe string to MT5 constant
        timeframe_map = {
            'M1': mt5.TIMEFRAME_M1,
            'M5': mt5.TIMEFRAME_M5,
            'M15': mt5.TIMEFRAME_M15,
            'M30': mt5.TIMEFRAME_M30,
            'H1': mt5.TIMEFRAME_H1,
            'H4': mt5.TIMEFRAME_H4,
            'D1': mt5.TIMEFRAME_D1,
            'W1': mt5.TIMEFRAME_W1,
            'MN1': mt5.TIMEFRAME_MN1
        }

        mt5_timeframe = timeframe_map.get(timeframe)
        if mt5_timeframe is None:
            self.logger.error(f"Invalid timeframe: {timeframe}")
            return None

        rates = mt5.copy_rates_from_pos(symbol, mt5_timeframe, 0, count)

        if rates is None or len(rates) == 0:
            self.logger.error(f"Failed to get bars for {symbol}: {mt5.last_error()}")
            return None

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')

        return df

    def get_symbol_info(self, symbol: str) -> Optional[Dict]:
        """
        Get symbol information

        Args:
            symbol: Trading symbol

        Returns:
            Dict with symbol information or None if failed
        """
        if not self.connected:
            self.logger.error("Not connected to MT5")
            return None

        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            self.logger.error(f"Symbol {symbol} not found")
            return None

        return {
            'bid': symbol_info.bid,
            'ask': symbol_info.ask,
            'spread': symbol_info.spread,
            'point': symbol_info.point,
            'digits': symbol_info.digits,
            'volume_min': symbol_info.volume_min,
            'volume_max': symbol_info.volume_max,
            'volume_step': symbol_info.volume_step,
            'trade_contract_size': symbol_info.trade_contract_size
        }

    def get_positions(self, symbol: Optional[str] = None) -> List[Dict]:
        """
        Get open positions

        Args:
            symbol: Filter by symbol (optional)

        Returns:
            List of position dictionaries
        """
        if not self.connected:
            self.logger.error("Not connected to MT5")
            return []

        if symbol:
            positions = mt5.positions_get(symbol=symbol)
        else:
            positions = mt5.positions_get()

        if positions is None:
            return []

        return [
            {
                'ticket': pos.ticket,
                'symbol': pos.symbol,
                'type': 'BUY' if pos.type == mt5.ORDER_TYPE_BUY else 'SELL',
                'volume': pos.volume,
                'price_open': pos.price_open,
                'sl': pos.sl,
                'tp': pos.tp,
                'profit': pos.profit,
                'magic': pos.magic,
                'comment': pos.comment
            }
            for pos in positions
        ]

    def send_order(self, symbol: str, order_type: str, volume: float,
                   price: Optional[float] = None, sl: float = 0.0, tp: float = 0.0,
                   magic: int = 0, comment: str = "") -> Optional[Dict]:
        """
        Send a trading order

        Args:
            symbol: Trading symbol
            order_type: 'BUY' or 'SELL'
            volume: Lot size
            price: Entry price (None for market order)
            sl: Stop loss price
            tp: Take profit price
            magic: Magic number
            comment: Order comment

        Returns:
            Dict with order result or None if failed
        """
        if not self.connected:
            self.logger.error("Not connected to MT5")
            return None

        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            self.logger.error(f"Symbol {symbol} not found")
            return None

        if not symbol_info.visible:
            if not mt5.symbol_select(symbol, True):
                self.logger.error(f"Failed to select {symbol}")
                return None

        # Determine order type
        if order_type.upper() == 'BUY':
            trade_type = mt5.ORDER_TYPE_BUY
            price = price or mt5.symbol_info_tick(symbol).ask
        elif order_type.upper() == 'SELL':
            trade_type = mt5.ORDER_TYPE_SELL
            price = price or mt5.symbol_info_tick(symbol).bid
        else:
            self.logger.error(f"Invalid order type: {order_type}")
            return None

        # Prepare request
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": trade_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "magic": magic,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        # Send order
        result = mt5.order_send(request)

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            self.logger.error(f"Order failed: {result.comment}")
            return None

        self.logger.info(f"Order successful: {order_type} {volume} {symbol} at {price}")

        return {
            'ticket': result.order,
            'volume': result.volume,
            'price': result.price,
            'bid': result.bid,
            'ask': result.ask,
            'comment': result.comment
        }

    def close_position(self, ticket: int) -> bool:
        """
        Close a position by ticket

        Args:
            ticket: Position ticket number

        Returns:
            bool: True if closed successfully
        """
        if not self.connected:
            self.logger.error("Not connected to MT5")
            return False

        positions = mt5.positions_get(ticket=ticket)
        if positions is None or len(positions) == 0:
            self.logger.error(f"Position {ticket} not found")
            return False

        position = positions[0]

        # Determine close order type (opposite of position type)
        if position.type == mt5.ORDER_TYPE_BUY:
            trade_type = mt5.ORDER_TYPE_SELL
            price = mt5.symbol_info_tick(position.symbol).bid
        else:
            trade_type = mt5.ORDER_TYPE_BUY
            price = mt5.symbol_info_tick(position.symbol).ask

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": position.symbol,
            "volume": position.volume,
            "type": trade_type,
            "position": ticket,
            "price": price,
            "magic": position.magic,
            "comment": "Close position",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            self.logger.error(f"Failed to close position {ticket}: {result.comment}")
            return False

        self.logger.info(f"Position {ticket} closed successfully")
        return True

    def modify_position(self, ticket: int, sl: float = 0.0, tp: float = 0.0) -> bool:
        """
        Modify stop loss and take profit of an existing position

        Args:
            ticket: Position ticket number
            sl: New stop loss price (0 to remove)
            tp: New take profit price (0 to remove)

        Returns:
            bool: True if modified successfully
        """
        if not self.connected:
            self.logger.error("Not connected to MT5")
            return False

        positions = mt5.positions_get(ticket=ticket)
        if positions is None or len(positions) == 0:
            self.logger.error(f"Position {ticket} not found")
            return False

        position = positions[0]

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": position.symbol,
            "position": ticket,
            "sl": sl,
            "tp": tp,
            "magic": position.magic,
            "comment": "Modify SL/TP",
        }

        result = mt5.order_send(request)

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            self.logger.error(f"Failed to modify position {ticket}: {result.comment}")
            return False

        self.logger.info(f"Position {ticket} modified successfully (SL: {sl}, TP: {tp})")
        return True
