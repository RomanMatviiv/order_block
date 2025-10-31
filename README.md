# Order Block Detection System

A Python-based trading tool for detecting order blocks in cryptocurrency markets. The system supports both historical analysis with chart generation and live monitoring with Telegram notifications.

## Features

- **Multi-Symbol Support**: Configure multiple trading pairs to monitor simultaneously
- **Multi-Timeframe Analysis**: Run detection on 15m and 30m timeframes (configurable)
- **Historical Analysis**: Fetch historical data and generate charts showing detected order blocks
- **Live Monitoring**: Real-time detection with parallel workers for each symbol/timeframe combination
- **Telegram Notifications**: Instant alerts when new order blocks are detected
- **Deduplication**: Smart tracking to avoid sending duplicate notifications

## Installation

1. Clone the repository:
```bash
git clone https://github.com/RomanMatviiv/order_block.git
cd order_block
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables for Telegram notifications (optional):
```bash
export TELEGRAM_BOT_TOKEN="your_bot_token_here"
export TELEGRAM_CHAT_ID="your_chat_id_here"
```

## Configuration

Edit `src/config.py` to customize the symbols and timeframes to monitor:

```python
# List of symbols to process
SYMBOLS = [
    "BTC/USDT",
    "ETH/USDT",
    # Add more symbols here
]

# Timeframes to run the detector for
TIMEFRAMES = ["15m", "30m"]

# Live polling interval in seconds
POLL_INTERVAL_SEC = 30
```

### Adding New Symbols

To add new trading pairs, simply add them to the `SYMBOLS` list in `src/config.py`:

```python
SYMBOLS = [
    "BTC/USDT",
    "ETH/USDT",
    "BNB/USDT",
    "SOL/USDT",
    "ADA/USDT",
]
```

## Usage

### Historical Analysis

Run historical order block detection and generate charts:

```bash
python run_history.py
```

This will:
- Fetch 2 days of historical data for each configured symbol and timeframe
- Detect bullish and bearish order blocks
- Generate and save charts to the `charts/` directory
- Charts are named: `{symbol}_{timeframe}_order_blocks.png`

Example output:
```
============================================================
Order Block Historical Analysis
============================================================
Symbols: ['BTC/USDT', 'ETH/USDT']
Timeframes: ['15m', '30m']

Processing BTC/USDT on 15m...
  Fetched 192 candles
  Detected 5 bullish and 3 bearish order blocks
  Chart saved to: charts/BTC_USDT_15m_order_blocks.png

Processing BTC/USDT on 30m...
  Fetched 96 candles
  Detected 3 bullish and 2 bearish order blocks
  Chart saved to: charts/BTC_USDT_30m_order_blocks.png
...
============================================================
Historical analysis complete!
============================================================
```

### Live Monitoring

Run live order block detection with Telegram notifications:

```bash
python run_live.py
```

This will:
- Start a separate worker thread for each symbol/timeframe combination
- Poll Binance every 30 seconds (configurable via `POLL_INTERVAL_SEC`)
- Detect new order blocks in real-time
- Send Telegram notifications for each new detection
- Keep track of notified blocks to avoid duplicates

Example output:
```
============================================================
Order Block Live Monitoring
============================================================
Symbols: ['BTC/USDT', 'ETH/USDT']
Timeframes: ['15m', '30m']
Poll Interval: 30 seconds

Started 4 worker threads
Monitoring for order blocks... Press Ctrl+C to stop
============================================================

[BTC/USDT 15m] Worker started
[BTC/USDT 30m] Worker started
[ETH/USDT 15m] Worker started
[ETH/USDT 30m] Worker started

[BTC/USDT 15m] New bullish order block detected at index 150
Telegram notification sent successfully

[ETH/USDT 30m] New bearish order block detected at index 85
Telegram notification sent successfully
```

### Telegram Notification Format

Notifications include:
- Symbol name (e.g., BTC/USDT)
- Timeframe (e.g., 15m)
- Block type (BULLISH or BEARISH)
- Price levels (low and high)
- Candle index

Example notification:
```
🟢 BULLISH Order Block Detected

Symbol: BTC/USDT
Timeframe: 15m
Block Low: 42150.50
Block High: 42350.75
Candle Index: 150

Buy zone identified
```

## Project Structure

```
order_block/
├── src/
│   ├── __init__.py
│   ├── config.py              # Configuration (symbols, timeframes, polling)
│   ├── data_fetcher.py        # Binance data fetching via ccxt
│   ├── detection.py           # Order block detection algorithm
│   ├── generate_entry_signals.py  # Entry signal generation
│   ├── plotter.py             # Chart generation with matplotlib
│   └── notifier.py            # Telegram notification handling
├── charts/                    # Generated charts directory
├── run_history.py             # Historical analysis script
├── run_live.py                # Live monitoring script
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```

## Order Block Detection Logic

The system identifies order blocks using the following criteria:

**Bullish Order Block:**
- A down candle (close < open) followed by a strong upward move
- The next candle's range is at least 1.5x the current candle's range
- Represents a potential support zone where buyers stepped in

**Bearish Order Block:**
- An up candle (close > open) followed by a strong downward move
- The next candle's range is at least 1.5x the current candle's range
- Represents a potential resistance zone where sellers stepped in

## Requirements

- Python 3.7+
- ccxt (for Binance API integration)
- pandas (for data manipulation)
- matplotlib (for chart generation)
- requests (for Telegram API)
- numpy (for numerical operations)

## Troubleshooting

### Telegram Notifications Not Working

Make sure you have set the environment variables:
```bash
echo $TELEGRAM_BOT_TOKEN
echo $TELEGRAM_CHAT_ID
```

If not set, the system will print warnings but continue to operate without sending notifications.

### Charts Not Generated

Ensure the `charts/` directory exists and has write permissions. The system creates it automatically if it doesn't exist.

### Connection Errors

If you encounter connection errors to Binance:
- Check your internet connection
- Verify that Binance is not blocked in your region
- The ccxt library has built-in rate limiting to avoid API bans

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
