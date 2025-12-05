# Tango Trading Strategy

## Overview

The Tango strategy is a P&L-based hedging strategy that automatically manages positions based on profit and loss thresholds rather than technical indicators.

## Strategy Rules

1. **Loss Trigger**: When a position reaches **$10 loss**, the bot automatically opens **2 opposite positions** to hedge
2. **No Initial TP/SL**: Positions are opened without Take Profit or Stop Loss initially
3. **Breakeven Protection**: When a position reaches **+$20 profit**, the bot sets a Stop Loss at the entry price (breakeven)
4. **Trailing Stop**: For every additional **$20 profit**, the Stop Loss trails by **$20**
5. **Position Limit**: Maximum **3 positions** at once (typically 1 losing + 2 profitable opposite positions)

## How It Works

### Example Scenario

1. **Start**: You open a BUY position at 2000.00
2. **Loss Trigger**: Price drops and position shows -$10 loss
   - Bot automatically opens 2 SELL positions
   - Now you have: 1 BUY (losing) + 2 SELL (opposite)
3. **Profit Management**: If one SELL position reaches +$20 profit
   - Bot sets SL at entry price (breakeven)
4. **Trailing**: If SELL position reaches +$40 profit
   - Bot moves SL to +$20 above entry (locks in $20 profit)
5. **Continuation**: If SELL position reaches +$60 profit
   - Bot moves SL to +$40 above entry (locks in $40 profit)
   - Pattern continues for every $20 increment

## Configuration

The Tango strategy is configured in `config.yaml`:

```yaml
strategy:
  type: "tango"
  parameters:
    loss_trigger: 10.0        # Dollar loss to trigger hedge
    profit_breakeven: 20.0    # Profit threshold to set breakeven SL
    profit_trail_step: 20.0   # Trail SL by this amount for each $20 profit
    max_positions: 3          # Maximum 3 positions (1 losing + 2 profitable)
    point_value: 0.01         # For XAUUSD (Gold)
    contract_size: 100        # Standard for XAUUSD
```

### Parameter Descriptions

- **loss_trigger**: Dollar amount that triggers opening opposite positions (default: $10)
- **profit_breakeven**: Profit level to set breakeven stop loss (default: $20)
- **profit_trail_step**: Dollar increment for trailing stop (default: $20)
- **max_positions**: Maximum concurrent positions (default: 3)
- **point_value**: Price movement value for the symbol (0.01 for XAUUSD)
- **contract_size**: Contract size for the symbol (100 for XAUUSD)

## Usage

### 1. Running the Bot

Start the bot normally:

```bash
python trading_bot.py
```

The bot will monitor any open positions and apply Tango rules automatically.

### 2. Opening Initial Position

You need to manually open the first position. Use the control script:

```bash
# Open a BUY position
python tango_control.py open BUY

# Open a SELL position
python tango_control.py open SELL
```

### 3. Monitoring Positions

Check current status:

```bash
python tango_control.py status
```

This shows:
- Number of open positions
- Total P&L
- Losing vs winning positions
- Hedged position count
- Details of each position

### 4. Closing All Positions

To manually close all Tango positions:

```bash
python tango_control.py close-all
```

## Risk Considerations

### Advantages
- Automatic hedging protects against significant losses
- Trailing stops lock in profits automatically
- No reliance on technical indicators or market timing
- Simple, rule-based approach

### Risks
- Requires sufficient margin for multiple positions
- Can result in multiple small losses if market whipsaws
- Not guaranteed to profit in all market conditions
- Maximum 3 positions limits hedging in extreme scenarios

### Recommendations
1. **Start Small**: Use small lot sizes (0.01 - 0.1) when testing
2. **Monitor Closely**: Watch the first few hedge triggers
3. **Adequate Margin**: Ensure you have enough margin for 3 positions
4. **Volatile Markets**: Strategy works best in trending markets, be cautious in choppy conditions
5. **Adjust Parameters**: You can customize loss_trigger and profit thresholds based on your risk tolerance

## Files Modified/Created

- `strategies.py` - Added `TangoStrategy` class
- `tango_executor.py` - New file with Tango-specific execution logic
- `trading_bot.py` - Modified to support Tango strategy
- `config.yaml` - Updated to use Tango strategy
- `tango_control.py` - Helper script for manual position control

## Troubleshooting

### Bot doesn't open hedge positions
- Check that max_positions (3) hasn't been reached
- Verify margin is sufficient for new positions
- Check logs for error messages

### Trailing stop not updating
- Verify profit has reached $20 threshold
- Check that profit increments are full $20 steps
- Review symbol point_value and contract_size settings

### Connection issues
- Verify .env file has correct MT5 credentials
- Check MT5 terminal is running
- Ensure symbol (XAUUSD) is available in your broker

## Support

For issues or questions:
1. Check the logs in `logs/trading_bot.log`
2. Verify configuration in `config.yaml`
3. Test with small lot sizes first
