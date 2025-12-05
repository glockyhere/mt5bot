"""
Example Backtest Script
Demonstrates how to test strategies on historical data
"""

import pandas as pd
from strategies import MovingAverageCrossover, RSIStrategy, BollingerBandsStrategy, MACDStrategy
from mt5_connector import MT5Connector
import os
from dotenv import load_dotenv


def simple_backtest(strategy, data: pd.DataFrame):
    """
    Simple backtest of a strategy on historical data

    Args:
        strategy: Trading strategy instance
        data: DataFrame with OHLCV data

    Returns:
        Dictionary with backtest results
    """
    trades = []
    position = None
    balance = 10000  # Starting balance

    for i in range(len(data)):
        if i < 100:  # Need enough data for indicators
            continue

        # Get data up to current bar
        current_data = data.iloc[:i+1]

        # Generate signal
        signal = strategy.on_bar(current_data)
        current_price = data.iloc[i]['close']
        timestamp = data.iloc[i]['time']

        # Execute trades
        if signal == 'BUY' and position is None:
            position = {
                'type': 'BUY',
                'entry_price': current_price,
                'entry_time': timestamp,
                'size': 0.01  # 0.01 lot
            }
            print(f"[{timestamp}] BUY at {current_price:.5f}")

        elif signal == 'SELL' and position is None:
            position = {
                'type': 'SELL',
                'entry_price': current_price,
                'entry_time': timestamp,
                'size': 0.01
            }
            print(f"[{timestamp}] SELL at {current_price:.5f}")

        elif position is not None:
            # Check if we should close
            if (position['type'] == 'BUY' and signal == 'SELL') or \
               (position['type'] == 'SELL' and signal == 'BUY'):

                # Calculate profit
                if position['type'] == 'BUY':
                    profit = (current_price - position['entry_price']) * 100000 * position['size']
                else:
                    profit = (position['entry_price'] - current_price) * 100000 * position['size']

                balance += profit

                trade = {
                    'type': position['type'],
                    'entry_price': position['entry_price'],
                    'entry_time': position['entry_time'],
                    'exit_price': current_price,
                    'exit_time': timestamp,
                    'profit': profit
                }
                trades.append(trade)

                print(f"[{timestamp}] CLOSE at {current_price:.5f} | Profit: ${profit:.2f}")

                position = None

    # Calculate statistics
    if not trades:
        print("\nNo trades executed!")
        return None

    winning_trades = [t for t in trades if t['profit'] > 0]
    losing_trades = [t for t in trades if t['profit'] < 0]

    total_profit = sum(t['profit'] for t in trades)
    win_rate = len(winning_trades) / len(trades) * 100

    results = {
        'total_trades': len(trades),
        'winning_trades': len(winning_trades),
        'losing_trades': len(losing_trades),
        'win_rate': win_rate,
        'total_profit': total_profit,
        'final_balance': balance,
        'return_pct': (balance - 10000) / 10000 * 100,
        'avg_win': sum(t['profit'] for t in winning_trades) / len(winning_trades) if winning_trades else 0,
        'avg_loss': sum(t['profit'] for t in losing_trades) / len(losing_trades) if losing_trades else 0
    }

    return results


def main():
    """Run backtest example"""
    print("=" * 60)
    print("MT5 Trading Bot - Backtest Example")
    print("=" * 60)

    # Load environment variables
    load_dotenv()

    # Connect to MT5
    login = int(os.getenv('MT5_LOGIN', 0))
    password = os.getenv('MT5_PASSWORD', '')
    server = os.getenv('MT5_SERVER', '')

    if not all([login, password, server]):
        print("Error: MT5 credentials not found in .env file")
        return

    connector = MT5Connector(login, password, server)

    if not connector.connect():
        print("Error: Failed to connect to MT5")
        return

    print(f"\nConnected to MT5")

    # Get historical data
    symbol = 'EURUSD'
    timeframe = 'H1'
    bars = 5000

    print(f"Fetching {bars} bars of {symbol} {timeframe} data...")
    data = connector.get_bars(symbol, timeframe, bars)

    if data is None:
        print("Error: Failed to get historical data")
        connector.disconnect()
        return

    print(f"Received {len(data)} bars")

    # Test strategies
    strategies = [
        ('Moving Average Crossover', MovingAverageCrossover({
            'fast_period': 20,
            'slow_period': 50,
            'signal_period': 9
        })),
        ('RSI Strategy', RSIStrategy({
            'rsi_period': 14,
            'oversold': 30,
            'overbought': 70
        })),
        ('Bollinger Bands', BollingerBandsStrategy({
            'period': 20,
            'std_dev': 2
        })),
        ('MACD Strategy', MACDStrategy({
            'fast_period': 12,
            'slow_period': 26,
            'signal_period': 9
        }))
    ]

    print("\n" + "=" * 60)
    print("BACKTEST RESULTS")
    print("=" * 60)

    for name, strategy in strategies:
        print(f"\n{name}")
        print("-" * 60)

        results = simple_backtest(strategy, data)

        if results:
            print(f"\nTotal Trades: {results['total_trades']}")
            print(f"Win Rate: {results['win_rate']:.2f}%")
            print(f"Total Profit: ${results['total_profit']:.2f}")
            print(f"Return: {results['return_pct']:.2f}%")
            print(f"Final Balance: ${results['final_balance']:.2f}")
            print(f"Average Win: ${results['avg_win']:.2f}")
            print(f"Average Loss: ${results['avg_loss']:.2f}")

    # Disconnect
    connector.disconnect()
    print("\n" + "=" * 60)
    print("Backtest complete!")
    print("=" * 60)


if __name__ == '__main__':
    main()
