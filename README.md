# Order Block Detection System

A Python-based trading tool for detecting order blocks in cryptocurrency markets. The system supports both historical analysis with chart generation and live monitoring with Telegram notifications.

## Features

- **Binance Futures Support**: Configured to work with USDT-margined perpetual futures
- **Multi-Symbol Support**: Configure multiple trading pairs to monitor simultaneously
- **Multi-Timeframe Analysis**: Run detection on 15m and 30m timeframes (configurable)
- **Historical Analysis**: Fetch historical data and generate charts showing detected order blocks
- **Live Monitoring**: Real-time detection with parallel workers for each symbol/timeframe combination
- **Telegram Notifications**: Instant alerts when new order blocks are detected
- **Deduplication**: Smart tracking to avoid sending duplicate notifications

## Binance Futures API

This system is configured to use **Binance USDT-margined Futures (perpetual contracts)** for both historical and live data:

- **REST API Base URL**: `https://fapi.binance.com`
- **WebSocket Base URL**: `wss://fstream.binance.com`
- **Endpoints Used**:
  - `/fapi/v1/klines` - Historical and real-time kline/candlestick data
  - `/fapi/v1/exchangeInfo` - Symbol validation and trading status

The system automatically:
- Validates symbols against the Binance Futures exchangeInfo endpoint
- Skips symbols that are not available on Binance Futures
- Uses futures-specific WebSocket streams for real-time data

> **Note**: Binance Futures is different from Binance Spot. Make sure your symbols are available on Binance Futures. The system will gracefully skip any symbols that are not supported.

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
# Binance API Configuration
BINANCE_API = 'futures'  # API type (futures for USDT-margined perpetual)
REST_BASE = 'https://fapi.binance.com'  # Futures REST API base URL
WS_BASE = 'wss://fstream.binance.com'  # Futures WebSocket base URL

# List of symbols to process
SYMBOLS = [
    "LINKUSDT",
    "ADAUSDT",
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
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "SOLUSDT",
    "ADAUSDT",
]
```

**Important**: 
- Use the Binance Futures symbol format (e.g., `BTCUSDT`, not `BTC/USDT`)
- Ensure the symbol exists on Binance Futures (the system will skip unsupported symbols automatically)
- Some symbols on Binance Spot may not be available on Binance Futures

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

The system offers two methods for live monitoring:

#### 1. WebSocket-Based Monitoring (Recommended)

Real-time monitoring using Binance Futures WebSocket streams:

```bash
python run_live_ws.py
```

**NEW: Historical Preloading**

The WebSocket mode now automatically preloads historical klines on startup to enable immediate detection. You can control whether historical blocks trigger Telegram notifications:

```bash
# Default: Mark historical blocks as seen without notifications (prevents spam)
python run_live_ws.py

# Send Telegram notifications for historical blocks found on startup
python run_live_ws.py --send-historical
```

This will:
- **Validate symbols** against Binance Futures exchangeInfo endpoint
- **Skip unsupported symbols** gracefully (e.g., symbols only on Spot)
- **Preload historical klines** (up to 500 bars per symbol/timeframe) via Futures REST API
- **Run detection immediately** on historical data to populate buffers
- Connect to Binance Futures WebSocket (`wss://fstream.binance.com`) for real-time kline updates
- Process only closed klines (no incomplete candle data)
- Maintain a rolling buffer of recent candles per symbol/timeframe
- Detect new order blocks immediately when candles close
- Send Telegram notifications for each new detection
- **Persist deduplication state to disk** (survives restarts)
- Automatically reconnect on connection failures

Example output:
```
============================================================
Order Block Live Monitoring (WebSocket)
============================================================
Symbols: ['BTC/USDT', 'ETH/USDT']
Timeframes: ['15m', '30m']
Send Historical Notifications: False

============================================================
Preloading historical data...
============================================================
[BTC/USDT 15m] Fetching 500 historical klines...
[BTC/USDT 15m] Fetched 500 klines
[BTC/USDT 15m] Running detection on historical data...
[BTC/USDT 15m] Marked 3 historical blocks as seen (no notifications)
[BTC/USDT 30m] Fetching 500 historical klines...
[BTC/USDT 30m] Fetched 500 klines
[BTC/USDT 30m] Running detection on historical data...
[BTC/USDT 30m] Marked 2 historical blocks as seen (no notifications)
============================================================
Historical data preloading complete!
============================================================

Connecting to Binance Futures WebSocket...
URL: wss://fstream.binance.com/stream?streams=btcusdt@kline_15m/btcusdt@kline_30m/ethusdt@kline_15m/ethusdt@kline_30m
Monitoring 2 symbols on 2 timeframes

✓ Connected to Binance Futures WebSocket
Listening for kline events... Press Ctrl+C to stop
============================================================

[BTC/USDT 15m] New bullish order block detected at index 150 (score: 0.73)
Telegram notification sent successfully

[ETH/USDT 30m] New bearish order block detected at index 85 (score: 0.68)
Telegram notification sent successfully
```

**Key advantages of WebSocket approach:**
- **Futures-specific**: Uses Binance USDT-margined Futures data exclusively
- **Symbol validation**: Automatically checks and skips unsupported symbols
- **Immediate detection**: Historical preloading enables detection from the first moment
- **Real-time updates**: Receives data as soon as candles close
- **Efficient**: No polling overhead, lower latency
- **Reliable**: Automatic reconnection with exponential backoff
- **Persistent deduplication**: State saved to `data/state.json`
- **Restart-safe**: Won't resend old notifications after restarts
- **Smart historical handling**: Control whether to notify about historical blocks on startup

#### 2. Polling-Based Monitoring (Legacy)

Traditional polling method using REST API:

```bash
python run_live.py
```

This will:
- Start a separate worker thread for each symbol/timeframe combination
- Poll Binance every 30 seconds (configurable via `POLL_INTERVAL_SEC`)
- Detect new order blocks in real-time
- Send Telegram notifications for each new detection
- Keep track of notified blocks in memory (lost on restart)

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

Notifications include enhanced information:
- Symbol name (e.g., BTC/USDT)
- Timeframe (e.g., 15m)
- Block type (BULLISH or BEARISH)
- Price levels (low and high)
- Candle index
- **Confidence score (0-1) with star rating**
- **Number of touches**
- **Liquidity sweep indicator** (if detected)

Example notification:
```
🟢 BULLISH Order Block Detected

Symbol: BTC/USDT
Timeframe: 15m
Block Low: 42150.50
Block High: 42350.75
Candle Index: 150

Confidence Score: 0.73 / 1.00
⭐⭐⭐ HIGH CONFIDENCE
Touches: 2
🔥 Liquidity Sweep Detected!

Buy zone identified
```

**Confidence Score Ratings:**
- ⭐⭐⭐ HIGH CONFIDENCE: Score ≥ 0.7
- ⭐⭐ MEDIUM CONFIDENCE: Score ≥ 0.5
- ⭐ LOW CONFIDENCE: Score < 0.5

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
│   ├── notifier.py            # Telegram notification handling
│   └── live_ws.py             # WebSocket-based live monitoring (NEW)
├── tests/                     # Unit tests
│   ├── test_detection.py      # Detection algorithm tests
│   └── test_live_ws.py        # WebSocket functionality tests (NEW)
├── charts/                    # Generated charts directory
├── run_history.py             # Historical analysis script
├── run_live.py                # Live monitoring script (polling)
├── run_live_ws.py             # Live monitoring script (WebSocket, NEW)
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```


## Order Block Detection Logic

The system uses an advanced order block detection algorithm with multiple validation layers:

### Detection Algorithm Features

1. **ATR-based Candle Filtering**
   - Candidate candles must have a sufficiently large body relative to ATR
   - Opposite-side wicks must be small to avoid false signals
   - Configurable via `BODY_MIN_RATIO` and `WICK_MAX_RATIO`

2. **Impulse Confirmation**
   - After the candidate candle, there must be a strong directional move
   - Validates both the number of directional candles and net price movement
   - Configurable via `DETECTION_LOOKAHEAD`, `IMPULSE_MIN_DIR_CANDLES`, and `IMPULSE_MIN_NET_MOVE`

3. **Multi-touch Validation**
   - Tracks how many times price returns to touch the zone
   - Higher touch counts indicate stronger zones
   - Configurable via `TOUCHES_REQUIRED` and `MAX_TOUCHES`

4. **Liquidity Sweep Detection (Optional)**
   - Identifies stop-hunts: quick wick extensions followed by reversals
   - Zones with liquidity sweeps receive higher confidence scores
   - Marked with special highlighting in charts and notifications

5. **Confidence Scoring**
   - Composite score (0-1) based on multiple factors:
     - Candle body size relative to ATR (20% weight)
     - Impulse strength (30% weight)
     - Number of touches (20% weight)
     - Volume spike (15% weight)
     - Liquidity sweep detection (15% weight)
   - Zones are displayed with shading intensity based on score

6. **Zone Management**
   - Overlapping zones are automatically merged
   - Zones expire after a configurable number of bars
   - Configurable via `ZONE_EXPIRY_BARS` and `ZONE_MERGE_THRESHOLD`

### Block Types

**Bullish Order Block:**
- A down candle (close < open) with substantial body
- Small upper wick (opposite side)
- Followed by strong upward impulse
- Represents a potential support zone where buyers stepped in

**Bearish Order Block:**
- An up candle (close > open) with substantial body
- Small lower wick (opposite side)
- Followed by strong downward impulse
- Represents a potential resistance zone where sellers stepped in

### Detection Parameters

You can tune the detection algorithm by editing these parameters in `src/config.py`:

```python
# ATR settings
ATR_PERIOD = 14              # ATR calculation period
ATR_MULT = 1.0              # ATR multiplier for thresholds

# Candle filters
BODY_MIN_RATIO = 0.5        # Min body size as ratio of ATR (0.5 = 50%)
WICK_MAX_RATIO = 0.3        # Max opposite wick as ratio of body (0.3 = 30%)

# Impulse confirmation
DETECTION_LOOKAHEAD = 10    # Bars to check for impulse
IMPULSE_MIN_DIR_CANDLES = 6 # Min directional candles required
IMPULSE_MIN_NET_MOVE = 1.5  # Min net movement as multiple of ATR

# Touch validation
TOUCHES_REQUIRED = 1        # Min touches for validation (1 = initial)
MAX_TOUCHES = 5             # Max touches before zone exhaustion

# Zone management
ZONE_EXPIRY_BARS = 100     # Bars until zone expires
ZONE_MERGE_THRESHOLD = 0.5  # Overlap % for merging zones

# Volume and liquidity
MIN_VOLUME_SPIKE_MULT = 1.5    # Min volume spike multiplier
LIQUIDITY_SWEEP_WICK_RATIO = 0.6  # Wick ratio for sweep detection
LIQUIDITY_SWEEP_REVERSAL_BARS = 3 # Bars to check for reversal

# Scoring weights (must sum to 1.0)
SCORE_WEIGHT_BODY_SIZE = 0.20
SCORE_WEIGHT_IMPULSE = 0.30
SCORE_WEIGHT_TOUCHES = 0.20
SCORE_WEIGHT_VOLUME = 0.15
SCORE_WEIGHT_LIQUIDITY_SWEEP = 0.15
```

### Tuning Tips

- **Increase `BODY_MIN_RATIO`** to detect only stronger candles (more selective)
- **Decrease `WICK_MAX_RATIO`** to filter out candles with large wicks (cleaner signals)
- **Increase `IMPULSE_MIN_DIR_CANDLES`** to require stronger impulse moves (fewer but higher quality)
- **Increase `TOUCHES_REQUIRED`** to wait for price confirmation (more reliable but delayed)
- **Adjust `ZONE_EXPIRY_BARS`** based on your timeframe (longer for higher timeframes)
- **Adjust scoring weights** to emphasize factors most important for your strategy

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
