# MT5 Telegram Trading Bot

A simple trading bot that monitors a Telegram group for trading commands and executes them on MetaTrader 5.

## Features

- Monitors Telegram group for `long <size>` and `short <size>` commands
- Executes trades on MT5 automatically
- Automatic trailing stop management:
  - First stop at $5 from entry when profit reaches $10
  - Trails by $10 increments thereafter

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Create a Telegram Bot

1. Open Telegram and search for `@BotFather`
2. Send `/newbot` and follow the prompts
3. Copy the bot token

### 3. Get Your Chat ID

Add your bot to the group, then send a message. Get the chat ID by visiting:
```
https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
```

### 4. Configure the Bot

Edit `config.yaml`:

```yaml
mt5:
  login: 12345678              # Your MT5 account number
  password: "your_password"    # Your MT5 password
  server: "your_broker_server" # Your broker's server

telegram:
  bot_token: "123456789:ABC..."  # From @BotFather
  allowed_chat_ids:              # Restrict to specific chats
    - -1001234567890             # Group ID
    - 123456789                  # Your user ID

trading:
  symbol: "XAUUSD"
  magic_number: 123456
```

## Running on Windows Server

### 1. Install MT5

Download and install MetaTrader 5 on the Windows server.

### 2. Install Python

Download Python 3.11+ from python.org

### 3. Setup the Bot

```cmd
cd C:\mt5bot
pip install -r requirements.txt
```

### 4. Run the Bot

```cmd
python telegram_bot.py
```

### 5. Run as Background Service

Create a batch file `run_bot.bat`:
```cmd
@echo off
cd C:\mt5bot
python telegram_bot.py
```

Or use Task Scheduler to run on startup.

## Commands

| Command | Action |
|---------|--------|
| `/start` | Show menu with inline buttons |
| `long 0.1` | Open BUY position with 0.1 lots |
| `short 0.5` | Open SELL position with 0.5 lots |

**Inline Buttons:**
- 📈 Status - Show account balance/equity
- 📊 Positions - List open positions
- ❌ Close All - Close all bot positions

## Trailing Stop Logic

| Profit | Stop Loss Locks |
|--------|-----------------|
| $10    | $5              |
| $20    | $10             |
| $30    | $20             |
| $40    | $30             |
| ...    | ...             |

## Files

```
mt5bot/
├── telegram_bot.py     # Main bot
├── mt5_connector.py    # MT5 API wrapper
├── logger_config.py    # Logging setup
├── config.yaml         # Configuration
├── requirements.txt    # Dependencies
└── logs/               # Log files
```

## Disclaimer

Trading involves risk. This bot is provided for educational purposes. Always test on a demo account first.
