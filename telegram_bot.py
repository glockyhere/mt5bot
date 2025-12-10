"""
Telegram Trading Bot
Monitors a Telegram group for trading commands and executes trades on MT5
Commands: long <slot_size>, short <slot_size>
"""

import asyncio
import logging
import re
import yaml
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from mt5_connector import MT5Connector
from logger_config import setup_logging

# Trailing stop configuration (in dollars)
# At $10 profit -> SL at $5 | At $20 -> SL at $10 | At $30 -> SL at $20 | etc.
TRAILING_STOP_TRIGGER = 10.0  # First trigger at $10 profit
TRAILING_STOP_STEP = 10.0     # Check every $10 increment

# Position limits
MAX_SAME_DIRECTION = 3    # Max 3 positions in same direction
MAX_TOTAL_POSITIONS = 5   # Max 5 total positions


class TelegramTradingBot:
    """Telegram bot that listens for trade commands"""

    def __init__(self, config_file: str = 'config.yaml'):
        # Load configuration
        with open(config_file, 'r') as f:
            self.config = yaml.safe_load(f)

        # Setup logging
        setup_logging(self.config['logging'])
        self.logger = logging.getLogger(__name__)

        # MT5 settings
        self.symbol = self.config['trading']['symbol']
        self.magic_number = self.config['trading']['magic_number']

        # Telegram settings
        telegram_config = self.config.get('telegram', {})
        self.bot_token = telegram_config.get('bot_token', '')
        self.allowed_chat_ids = telegram_config.get('allowed_chat_ids', [])

        # Initialize components
        self.connector: Optional[MT5Connector] = None
        self.application: Optional[Application] = None
        self.running = False

        # Position tracking for trailing stops
        self.position_tracker = {}

        self.logger.info("Telegram Trading Bot initialized")

    def connect_mt5(self) -> bool:
        """Connect to MT5"""
        mt5_config = self.config.get('mt5', {})
        login = mt5_config.get('login', 0)
        password = mt5_config.get('password', '')
        server = mt5_config.get('server', '')

        if not all([login, password, server]):
            self.logger.error("MT5 credentials not found in config.yaml")
            return False

        self.connector = MT5Connector(login, password, server)

        if not self.connector.connect():
            self.logger.error("Failed to connect to MT5")
            return False

        self.logger.info(f"Connected to MT5, trading {self.symbol}")
        return True

    def is_allowed_chat(self, chat_id: int) -> bool:
        """Check if chat is allowed to send commands"""
        if not self.allowed_chat_ids:
            return True  # Allow all if no restrictions
        return chat_id in self.allowed_chat_ids

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        if not self.is_allowed_chat(update.effective_chat.id):
            return

        keyboard = [
            [
                InlineKeyboardButton("📈 Status", callback_data="status"),
                InlineKeyboardButton("📊 Positions", callback_data="positions"),
            ],
            [
                InlineKeyboardButton("❌ Close All", callback_data="close_all"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "🤖 *MT5 Trading Bot*\n\n"
            "Commands:\n"
            "`long <size>` - Open BUY\n"
            "`short <size>` - Open SELL\n"
            "`close` - Close positions\n\n"
            "Or use the buttons below:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    async def _show_close_menu(self, update: Update):
        """Show positions as buttons to close"""
        positions = self.connector.get_positions(symbol=self.symbol)
        positions = [p for p in positions if p['magic'] == self.magic_number]

        if not positions:
            await update.message.reply_text("📈 No open positions to close")
            return

        keyboard = []
        for pos in positions:
            emoji = "🟢" if pos['profit'] >= 0 else "🔴"
            pnl = f"+${pos['profit']:.2f}" if pos['profit'] >= 0 else f"-${abs(pos['profit']):.2f}"
            label = f"{emoji} {pos['type']} {pos['volume']} | {pnl}"
            keyboard.append([InlineKeyboardButton(label, callback_data=f"close_{pos['ticket']}")])

        keyboard.append([InlineKeyboardButton("❌ Close All", callback_data="close_all")])
        keyboard.append([InlineKeyboardButton("🔙 Cancel", callback_data="cancel")])

        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "Select position to close:",
            reply_markup=reply_markup
        )

    def check_position_limits(self, order_type: str) -> tuple[bool, str]:
        """
        Check if we can open a new position based on limits

        Returns:
            (can_open, reason)
        """
        positions = self.connector.get_positions(symbol=self.symbol)
        positions = [p for p in positions if p['magic'] == self.magic_number]

        total_positions = len(positions)
        same_direction = sum(1 for p in positions if p['type'] == order_type)

        # Check total limit
        if total_positions >= MAX_TOTAL_POSITIONS:
            return False, f"Max total positions reached ({MAX_TOTAL_POSITIONS})"

        # Check same direction limit
        if same_direction >= MAX_SAME_DIRECTION:
            return False, f"Max {order_type} positions reached ({MAX_SAME_DIRECTION})"

        return True, "OK"

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming text messages"""
        if not self.is_allowed_chat(update.effective_chat.id):
            return

        message = update.message.text.strip().lower()
        self.logger.debug(f"Received message: {message}")

        # Parse commands
        # close - show positions to close
        if message == 'close':
            await self._show_close_menu(update)
            return

        # long <size> or short <size>
        match = re.match(r'^(long|short)\s+(\d+\.?\d*)$', message)
        if not match:
            return

        direction = match.group(1)
        lot_size = float(match.group(2))

        self.logger.info(f"Trade command received: {direction} {lot_size}")

        # Execute trade
        order_type = 'BUY' if direction == 'long' else 'SELL'

        # Check position limits
        can_open, reason = self.check_position_limits(order_type)
        if not can_open:
            self.logger.warning(f"Position limit reached: {reason}")
            await update.message.reply_text(f"⚠️ {reason}")
            return

        result = self.connector.send_order(
            symbol=self.symbol,
            order_type=order_type,
            volume=lot_size,
            magic=self.magic_number,
            comment=f"TG_{direction}_{lot_size}"
        )

        if result:
            self.logger.info(f"Order executed: {order_type} {lot_size} @ {result['price']}")
            # Track position for trailing stop
            self.position_tracker[result['ticket']] = {
                'entry_price': result['price'],
                'current_sl_profit': 0,
                'type': order_type
            }
            await update.message.reply_text(
                f"✅ *{order_type}* {lot_size} lots @ {result['price']:.2f}\n"
                f"Ticket: `{result['ticket']}`",
                parse_mode='Markdown'
            )
        else:
            self.logger.error(f"Failed to execute {direction} {lot_size}")
            await update.message.reply_text(f"❌ Failed to execute {direction} {lot_size}")

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline button callbacks"""
        query = update.callback_query
        await query.answer()

        if not self.is_allowed_chat(update.effective_chat.id):
            return

        if query.data == "status":
            await self._send_status(query)
        elif query.data == "positions":
            await self._send_positions(query)
        elif query.data == "close_all":
            await self._close_all_positions(query)
        elif query.data == "cancel":
            await query.edit_message_text("Cancelled")
        elif query.data.startswith("close_"):
            ticket = int(query.data.replace("close_", ""))
            await self._close_single_position(query, ticket)

    async def _send_status(self, query):
        """Send account status"""
        account_info = self.connector.get_account_info()
        if account_info:
            text = (
                f"📊 *Account Status*\n\n"
                f"Balance: `${account_info['balance']:.2f}`\n"
                f"Equity: `${account_info['equity']:.2f}`\n"
                f"Profit: `${account_info['profit']:.2f}`\n"
                f"Margin Level: `{account_info['margin_level']:.1f}%`"
            )
        else:
            text = "❌ Failed to get account info"

        await query.edit_message_text(text, parse_mode='Markdown')

    async def _send_positions(self, query):
        """Send open positions"""
        positions = self.connector.get_positions(symbol=self.symbol)
        positions = [p for p in positions if p['magic'] == self.magic_number]

        if not positions:
            text = "📈 No open positions"
        else:
            text = "📈 *Open Positions*\n\n"
            for pos in positions:
                emoji = "🟢" if pos['profit'] >= 0 else "🔴"
                text += (
                    f"{emoji} {pos['type']} {pos['volume']} @ {pos['price_open']:.2f}\n"
                    f"   P/L: `${pos['profit']:.2f}` | SL: {pos['sl']:.2f}\n\n"
                )

        await query.edit_message_text(text, parse_mode='Markdown')

    async def _close_all_positions(self, query):
        """Close all positions"""
        positions = self.connector.get_positions(symbol=self.symbol)
        positions = [p for p in positions if p['magic'] == self.magic_number]

        if not positions:
            await query.edit_message_text("📈 No positions to close")
            return

        closed = 0
        total_pnl = 0.0
        for pos in positions:
            if self.connector.close_position(pos['ticket']):
                closed += 1
                total_pnl += pos['profit']

        emoji = "🟢" if total_pnl >= 0 else "🔴"
        pnl_str = f"+${total_pnl:.2f}" if total_pnl >= 0 else f"-${abs(total_pnl):.2f}"
        await query.edit_message_text(f"✅ Closed {closed}/{len(positions)} positions\n{emoji} Total P/L: {pnl_str}")

    async def _close_single_position(self, query, ticket: int):
        """Close a single position by ticket"""
        positions = self.connector.get_positions(symbol=self.symbol)
        position = next((p for p in positions if p['ticket'] == ticket), None)

        if not position:
            await query.edit_message_text(f"❌ Position {ticket} not found")
            return

        profit = position['profit']
        if self.connector.close_position(ticket):
            emoji = "🟢" if profit >= 0 else "🔴"
            pnl_str = f"+${profit:.2f}" if profit >= 0 else f"-${abs(profit):.2f}"
            await query.edit_message_text(
                f"✅ Closed {position['type']} {position['volume']} lots\n"
                f"{emoji} P/L: {pnl_str}"
            )
        else:
            await query.edit_message_text(f"❌ Failed to close position {ticket}")

    async def manage_trailing_stops(self, context: ContextTypes.DEFAULT_TYPE):
        """Manage trailing stops for all positions (runs as job)"""
        if not self.connector or not self.connector.connected:
            return

        positions = self.connector.get_positions(symbol=self.symbol)
        positions = [p for p in positions if p['magic'] == self.magic_number]

        for pos in positions:
            ticket = pos['ticket']
            profit = pos['profit']

            # Initialize tracking if not exists
            if ticket not in self.position_tracker:
                self.position_tracker[ticket] = {
                    'entry_price': pos['price_open'],
                    'current_sl_profit': 0,
                    'type': pos['type']
                }

            tracker = self.position_tracker[ticket]

            # Calculate what SL profit level we should have based on current profit
            # At $10 -> SL at $5 | At $20 -> SL at $10 | At $30 -> SL at $20
            if profit >= TRAILING_STOP_TRIGGER:
                thresholds_crossed = int(profit / TRAILING_STOP_STEP)

                if thresholds_crossed == 1:
                    target_sl_profit = 5.0
                else:
                    target_sl_profit = (thresholds_crossed - 1) * 10.0

                # Only update if we need to move SL higher
                if target_sl_profit > tracker['current_sl_profit']:
                    new_sl = self._calculate_stop_price(pos, target_sl_profit)

                    if new_sl > 0:
                        success = self.connector.modify_position(ticket, sl=new_sl)
                        if success:
                            tracker['current_sl_profit'] = target_sl_profit
                            self.logger.info(
                                f"Updated SL for ticket {ticket}: "
                                f"Locking ${target_sl_profit:.0f} profit, Profit: ${profit:.2f}"
                            )

        # Clean up closed positions from tracker
        open_tickets = {p['ticket'] for p in positions}
        closed_tickets = [t for t in self.position_tracker if t not in open_tickets]
        for t in closed_tickets:
            del self.position_tracker[t]

    def _calculate_stop_price(self, position: dict, target_profit: float) -> float:
        """Calculate stop loss price that locks in target_profit dollars"""
        entry_price = position['price_open']
        pos_type = position['type']

        symbol_info = self.connector.get_symbol_info(self.symbol)
        if not symbol_info:
            return 0.0

        volume = position['volume']
        contract_size = symbol_info.get('trade_contract_size', 100)

        price_per_dollar = 1.0 / (volume * contract_size)
        price_distance = target_profit * price_per_dollar

        if pos_type == 'BUY':
            return entry_price + price_distance
        else:
            return entry_price - price_distance

    def run(self):
        """Start the bot"""
        if not self.bot_token:
            self.logger.error("Bot token not found in config.yaml")
            return

        if not self.connect_mt5():
            return

        # Build application
        self.application = Application.builder().token(self.bot_token).build()

        # Add handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self.handle_message
        ))
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))

        # Add job for trailing stop management (every 1 second)
        self.application.job_queue.run_repeating(
            self.manage_trailing_stops,
            interval=1.0,
            first=1.0
        )

        self.logger.info("Bot started - listening for commands...")

        # Run the bot
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

        # Cleanup on exit
        if self.connector:
            self.connector.disconnect()


def main():
    bot = TelegramTradingBot()
    bot.run()


if __name__ == '__main__':
    main()
