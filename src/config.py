# src/config.py
# List of symbols to process. Edit this list to add or remove trading pairs.
SYMBOLS = [
    "BTC/USDT",
    "ETH/USDT",
]

# Timeframes to run the detector for (both history and live). Default: 15m and 30m
TIMEFRAMES = ["15m", "30m"]

# Live polling interval in seconds (used by run_live worker)
POLL_INTERVAL_SEC = 30
