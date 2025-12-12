"""
Telegram Trading Bot
Monitors a Telegram group for trading commands and executes trades on MT5
Commands: long <slot_size>, short <slot_size>
"""

import asyncio
import logging
import re
import time
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
from telegram.error import BadRequest

from mt5_connector import MT5Connector
from logger_config import setup_logging

# Take profit in dollars
TAKE_PROFIT_DOLLARS = 10.0

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

        # Track live position displays for real-time updates
        # {(chat_id, message_id): {'type': 'positions'|'close', 'last_update': timestamp}}
        self.live_displays = {}

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
            "`b` - BUY (with TP)\n"
            "`s` - SELL (with TP)\n"
            "`bx` - BUY (no TP)\n"
            "`sx` - SELL (no TP)\n"
            "`c` - Close\n\n"
            "Or use the buttons below:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    def _build_close_menu_keyboard(self):
        """Build close menu keyboard with current positions"""
        positions = self.connector.get_positions(symbol=self.symbol)
        positions = [p for p in positions if p['magic'] == self.magic_number]

        if not positions:
            return None, None

        total_pnl = sum(p['profit'] for p in positions)
        total_emoji = "🟢" if total_pnl >= 0 else "🔴"
        total_str = f"+${total_pnl:.2f}" if total_pnl >= 0 else f"-${abs(total_pnl):.2f}"

        keyboard = []
        for pos in positions:
            emoji = "🟢" if pos['profit'] >= 0 else "🔴"
            pnl = f"+${pos['profit']:.2f}" if pos['profit'] >= 0 else f"-${abs(pos['profit']):.2f}"
            label = f"{emoji} {pos['type']} {pos['volume']} | {pnl}"
            keyboard.append([InlineKeyboardButton(label, callback_data=f"close_{pos['ticket']}")])

        keyboard.append([InlineKeyboardButton("❌ Close All", callback_data="close_all")])
        keyboard.append([InlineKeyboardButton("🔙 Cancel", callback_data="cancel")])

        text = f"Select position to close: | {total_emoji} {total_str}"
        return text, InlineKeyboardMarkup(keyboard)

    async def _show_close_menu(self, update: Update):
        """Show positions as buttons to close"""
        text, keyboard = self._build_close_menu_keyboard()

        if not keyboard:
            await update.message.reply_text("📈 No open positions to close")
            return

        msg = await update.message.reply_text(text, reply_markup=keyboard)

        # Track for live updates
        self.live_displays[(msg.chat_id, msg.message_id)] = {
            'type': 'close',
            'last_update': time.time()
        }

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
        if message == 'c':
            await self._show_close_menu(update)
            return

        if message not in ('b', 's', 'bx', 'sx'):
            return

        order_type = 'BUY' if message in ('b', 'bx') else 'SELL'
        no_tp = message in ('bx', 'sx')
        lot_size = self.config['trading'].get('lot_size', 0.1)

        self.logger.info(f"Trade command received: {order_type} {lot_size} (no_tp={no_tp})")

        # Check position limits
        can_open, reason = self.check_position_limits(order_type)
        if not can_open:
            self.logger.warning(f"Position limit reached: {reason}")
            await update.message.reply_text(f"⚠️ {reason}")
            return

        # Calculate TP price (if not no_tp mode)
        tp_price = None if no_tp else self._calculate_tp_price(order_type, lot_size)

        result = self.connector.send_order(
            symbol=self.symbol,
            order_type=order_type,
            volume=lot_size,
            tp=tp_price,
            magic=self.magic_number,
            comment=f"TG_{order_type}"
        )

        if result:
            if no_tp:
                self.logger.info(f"Order executed: {order_type} {lot_size} @ {result['price']} (no TP)")
                await update.message.reply_text(
                    f"✅ *{order_type}* {lot_size} lots @ {result['price']:.2f}\n"
                    f"Ticket: `{result['ticket']}`",
                    parse_mode='Markdown'
                )
            else:
                self.logger.info(f"Order executed: {order_type} {lot_size} @ {result['price']} TP: {tp_price}")
                await update.message.reply_text(
                    f"✅ *{order_type}* {lot_size} lots @ {result['price']:.2f}\n"
                    f"TP: {tp_price:.2f} (${TAKE_PROFIT_DOLLARS})\n"
                    f"Ticket: `{result['ticket']}`",
                    parse_mode='Markdown'
                )
        else:
            self.logger.error(f"Failed to execute {order_type} {lot_size}")
            await update.message.reply_text(f"❌ Failed to execute {order_type} {lot_size}")

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
            # Remove from live tracking
            key = (query.message.chat_id, query.message.message_id)
            if key in self.live_displays:
                del self.live_displays[key]
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

    def _build_positions_text(self):
        """Build positions text"""
        positions = self.connector.get_positions(symbol=self.symbol)
        positions = [p for p in positions if p['magic'] == self.magic_number]

        if not positions:
            return "📈 No open positions", False

        total_pnl = sum(p['profit'] for p in positions)
        total_emoji = "🟢" if total_pnl >= 0 else "🔴"
        total_str = f"+${total_pnl:.2f}" if total_pnl >= 0 else f"-${abs(total_pnl):.2f}"

        text = f"📈 *Open Positions* | {total_emoji} {total_str}\n\n"
        for pos in positions:
            emoji = "🟢" if pos['profit'] >= 0 else "🔴"
            pnl_str = f"+${pos['profit']:.2f}" if pos['profit'] >= 0 else f"-${abs(pos['profit']):.2f}"
            text += (
                f"{emoji} {pos['type']} {pos['volume']} @ {pos['price_open']:.2f}\n"
                f"   P/L: `{pnl_str}` | TP: {pos['tp']:.2f}\n\n"
            )

        return text, True

    async def _send_positions(self, query):
        """Send open positions"""
        text, has_positions = self._build_positions_text()

        await query.edit_message_text(text, parse_mode='Markdown')

        # Track this display for live updates
        if has_positions:
            chat_id = query.message.chat_id
            message_id = query.message.message_id
            self.live_displays[(chat_id, message_id)] = {
                'type': 'positions',
                'last_update': time.time()
            }

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

        # Remove from live tracking
        key = (query.message.chat_id, query.message.message_id)
        if key in self.live_displays:
            del self.live_displays[key]

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

            # Remove from live tracking
            key = (query.message.chat_id, query.message.message_id)
            if key in self.live_displays:
                del self.live_displays[key]

            await query.edit_message_text(
                f"✅ Closed {position['type']} {position['volume']} lots\n"
                f"{emoji} P/L: {pnl_str}"
            )
        else:
            await query.edit_message_text(f"❌ Failed to close position {ticket}")

    async def update_live_displays(self, context: ContextTypes.DEFAULT_TYPE):
        """Update all live position displays (runs as job)"""
        if not self.connector or not self.connector.connected:
            return

        if not self.live_displays:
            return

        # Remove stale displays (older than 5 minutes)
        stale_keys = [
            key for key, data in self.live_displays.items()
            if time.time() - data['last_update'] > 300
        ]
        for key in stale_keys:
            del self.live_displays[key]

        # Update each tracked display
        for (chat_id, message_id), data in list(self.live_displays.items()):
            try:
                if data['type'] == 'positions':
                    text, has_positions = self._build_positions_text()
                    if not has_positions:
                        # No more positions, remove tracking
                        del self.live_displays[(chat_id, message_id)]
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=text,
                        parse_mode='Markdown'
                    )
                elif data['type'] == 'close':
                    text, keyboard = self._build_close_menu_keyboard()
                    if not keyboard:
                        # No more positions
                        await context.bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=message_id,
                            text="📈 No open positions"
                        )
                        del self.live_displays[(chat_id, message_id)]
                    else:
                        await context.bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=message_id,
                            text=text,
                            reply_markup=keyboard
                        )
                data['last_update'] = time.time()
            except BadRequest as e:
                # Message not modified or deleted
                if "not modified" not in str(e).lower():
                    del self.live_displays[(chat_id, message_id)]
            except Exception:
                # Remove from tracking on any error
                del self.live_displays[(chat_id, message_id)]

    def _calculate_tp_price(self, order_type: str, lot_size: float) -> float:
        """Calculate take profit price for target dollar profit"""
        symbol_info = self.connector.get_symbol_info(self.symbol)
        if not symbol_info:
            return 0.0

        contract_size = symbol_info.get('trade_contract_size', 100)
        current_price = symbol_info['ask'] if order_type == 'BUY' else symbol_info['bid']

        # Price movement per dollar = 1 / (volume * contract_size)
        price_per_dollar = 1.0 / (lot_size * contract_size)
        price_distance = TAKE_PROFIT_DOLLARS * price_per_dollar

        if order_type == 'BUY':
            return current_price + price_distance
        else:
            return current_price - price_distance

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

        # Add job for live display updates (every 1 second)
        self.application.job_queue.run_repeating(
            self.update_live_displays,
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
