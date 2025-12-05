# MT5 Trading Bot

A professional Python-based automated trading bot for MetaTrader 5 with multiple strategies, risk management, and comprehensive logging.

## Features

- **Multiple Trading Strategies**
  - Moving Average Crossover
  - RSI (Relative Strength Index)
  - Bollinger Bands
  - MACD (Moving Average Convergence Divergence)
  - Extensible framework for custom strategies

- **Risk Management**
  - Position sizing based on account risk
  - Maximum daily loss limits
  - Maximum concurrent positions
  - Stop loss and take profit automation
  - Trailing stop support
  - Risk/reward ratio calculation

- **Professional Logging**
  - Rotating log files
  - Separate trade logs
  - Daily performance summaries
  - Console and file output

- **Robust Architecture**
  - Modular design
  - Error handling
  - Graceful shutdown
  - Configuration via YAML and environment variables

## Requirements

- Python 3.8+
- MetaTrader 5 terminal installed
- MT5 trading account (demo or live)

## Installation

1. Clone or download this repository

2. Install required packages:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file from the example:
```bash
cp .env.example .env
```

4. Edit `.env` with your MT5 credentials:
```
MT5_LOGIN=your_account_number
MT5_PASSWORD=your_password
MT5_SERVER=your_broker_server
```

## Configuration

Edit `config.yaml` to customize:

- **Trading parameters**: symbol, timeframe, lot size
- **Risk management**: max risk per trade, daily loss limits, stop loss/take profit
- **Strategy selection**: choose and configure your trading strategy
- **Logging**: log level, file rotation settings

### Strategy Configuration

The bot comes with 4 built-in strategies:

#### Moving Average Crossover
```yaml
strategy:
  type: "moving_average_crossover"
  parameters:
    fast_period: 20
    slow_period: 50
    signal_period: 9
```

#### RSI Strategy
```yaml
strategy:
  type: "rsi"
  parameters:
    rsi_period: 14
    oversold: 30
    overbought: 70
```

#### Bollinger Bands Strategy
```yaml
strategy:
  type: "bollinger_bands"
  parameters:
    period: 20
    std_dev: 2
```

#### MACD Strategy
```yaml
strategy:
  type: "macd"
  parameters:
    fast_period: 12
    slow_period: 26
    signal_period: 9
```

## Usage

### Running the Bot

Start the trading bot:
```bash
python trading_bot.py
```

Use a custom config file:
```bash
python trading_bot.py --config my_config.yaml
```

### Checking Status

View current bot status without starting it:
```bash
python trading_bot.py --status
```

This displays:
- Account balance, equity, and profit
- Open positions and their P&L
- Daily trading statistics

### Stopping the Bot

Press `Ctrl+C` for graceful shutdown. The bot will:
- Log final daily summary
- Optionally close all positions (configurable)
- Disconnect from MT5

## Project Structure

```
mt5bot/
├── trading_bot.py          # Main bot runner
├── mt5_connector.py        # MT5 API wrapper
├── strategy_base.py        # Base strategy class
├── strategies.py           # Strategy implementations
├── risk_manager.py         # Risk management
├── trade_executor.py       # Order execution
├── logger_config.py        # Logging setup
├── config.yaml             # Configuration
├── .env                    # Environment variables (create from .env.example)
├── requirements.txt        # Python dependencies
└── logs/                   # Log files (auto-created)
    ├── trading_bot.log     # Main log
    └── trades.log          # Trade-specific log
```

## Creating Custom Strategies

To create your own strategy:

1. Create a new class inheriting from `TradingStrategy` in [strategies.py](strategies.py)

2. Implement required methods:
```python
from strategy_base import TradingStrategy, SignalType
import pandas as pd

class MyCustomStrategy(TradingStrategy):
    def __init__(self, parameters: dict):
        super().__init__("MyCustomStrategy", parameters)
        # Initialize your parameters

    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        # Add your technical indicators to the dataframe
        df = data.copy()
        # ... calculate indicators ...
        return df

    def generate_signal(self, data: pd.DataFrame) -> SignalType:
        # Return 'BUY', 'SELL', 'HOLD', or 'CLOSE'
        # ... your logic ...
        return 'HOLD'
```

3. Register your strategy in [trading_bot.py](trading_bot.py:76):
```python
elif strategy_type == 'my_custom':
    self.strategy = MyCustomStrategy(strategy_params)
```

4. Update [config.yaml](config.yaml) to use your strategy:
```yaml
strategy:
  type: "my_custom"
  parameters:
    # your parameters
```

## Risk Management

The bot includes comprehensive risk management:

- **Position Sizing**: Automatically calculated based on:
  - Account balance
  - Risk percentage (default 2% per trade)
  - Stop loss distance
  - Symbol specifications

- **Risk Limits**:
  - Maximum positions: Limits concurrent trades
  - Daily loss limit: Stops trading if daily loss exceeds threshold
  - Margin level check: Ensures sufficient margin before trading

- **Trade Validation**:
  - Validates lot sizes against broker limits
  - Checks volume steps
  - Ensures stop loss and take profit are set

## Logging

The bot maintains two log files:

- `logs/trading_bot.log`: All bot activities, errors, and debug info
- `logs/trades.log`: Trade-specific log with entry/exit details and daily summaries

Log files automatically rotate when they reach 10MB, keeping 5 backup files.

## Safety Features

- **No Destructive Actions**: Bot will not modify existing positions not created by it (uses magic number)
- **Graceful Shutdown**: Properly closes MT5 connection on exit
- **Error Handling**: Comprehensive error handling and logging
- **Demo Account Testing**: Test thoroughly on demo account first!

## Important Notes

⚠️ **Trading involves risk. This bot is provided for educational purposes.**

- Always test on a demo account first
- Monitor the bot regularly
- Start with small position sizes
- Understand the strategy you're using
- Review logs regularly for issues
- Keep your MT5 terminal running while the bot is active

## Troubleshooting

### Bot won't connect to MT5
- Ensure MT5 terminal is installed and running
- Check your credentials in `.env`
- Verify the server name is correct
- Check if MT5 terminal shows "Connected" status

### No trades being executed
- Check the logs for errors
- Verify your account has sufficient balance
- Ensure the symbol is available in Market Watch
- Check if risk limits are being hit

### Import errors
- Make sure all requirements are installed: `pip install -r requirements.txt`
- Ensure you're using Python 3.8 or higher

### Symbol not found
- Add the symbol to Market Watch in MT5 terminal
- Check the symbol name spelling in config

## License

This project is open source and available for educational purposes.

## Disclaimer

This software is provided "as is" without warranty of any kind. Trading financial instruments carries a high level of risk and may not be suitable for all investors. You should carefully consider your investment objectives, level of experience, and risk appetite before trading. Past performance is not indicative of future results.
