# Quick Start Guide

Get your MT5 trading bot up and running in 5 minutes!

## Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

## Step 2: Configure Your Account

1. Copy the environment template:
```bash
cp .env.example .env
```

2. Edit `.env` with your MT5 account details:
```
MT5_LOGIN=12345678
MT5_PASSWORD=YourPassword
MT5_SERVER=YourBroker-Demo

SYMBOL=EURUSD
TIMEFRAME=H1
LOT_SIZE=0.01
MAGIC_NUMBER=123456

MAX_RISK_PER_TRADE=0.02
MAX_DAILY_LOSS=0.05
MAX_POSITIONS=3
```

## Step 3: Choose Your Strategy

Open `config.yaml` and select a strategy. Default is Moving Average Crossover:

```yaml
strategy:
  type: "moving_average_crossover"  # Options: moving_average_crossover, rsi, bollinger_bands, macd
  parameters:
    fast_period: 20
    slow_period: 50
    signal_period: 9
```

## Step 4: Test Connection

Check if everything is working:

```bash
python trading_bot.py --status
```

You should see your account information displayed.

## Step 5: Run the Bot

Start trading (recommended: start with demo account):

```bash
python trading_bot.py
```

Press `Ctrl+C` to stop.

## What Happens Now?

The bot will:
1. Connect to your MT5 account
2. Monitor the market for trading signals
3. Execute trades when conditions are met
4. Manage positions with stop loss and take profit
5. Log all activities to `logs/` folder

## Monitor Your Bot

- Watch the console for real-time updates
- Check `logs/trading_bot.log` for detailed information
- Review `logs/trades.log` for trade history
- Run `python trading_bot.py --status` anytime to check status

## Safety Tips

✅ **DO:**
- Start with a demo account
- Use small position sizes
- Monitor regularly
- Review logs daily
- Test strategies thoroughly

❌ **DON'T:**
- Use live account without testing
- Risk more than you can afford to lose
- Leave bot unattended for extended periods
- Ignore error messages
- Trade without understanding the strategy

## Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Customize risk parameters in `config.yaml`
- Try different strategies
- Create your own custom strategy
- Review and optimize based on logs

## Need Help?

Common issues and solutions:

**"Failed to connect to MT5"**
- Ensure MT5 terminal is running
- Check credentials in `.env`
- Verify server name

**"No data received"**
- Add symbol to Market Watch in MT5
- Check internet connection
- Verify timeframe is valid

**"Cannot open trade: Maximum positions reached"**
- Increase `MAX_POSITIONS` in `.env` or
- Wait for existing positions to close

Happy trading! 🚀
