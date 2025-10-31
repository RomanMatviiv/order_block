"""
Data fetcher module for retrieving OHLCV data from Binance using ccxt.
"""
import ccxt
from datetime import datetime, timedelta
import pandas as pd


# Cache the exchange instance for reuse
_exchange = None


def _get_exchange():
    """Get or create the cached exchange instance."""
    global _exchange
    if _exchange is None:
        _exchange = ccxt.binance({
            'enableRateLimit': True,
        })
    return _exchange


def fetch_last_n_days(symbol, timeframe, days=2):
    """
    Fetch OHLCV data for the last N days for a given symbol and timeframe.
    
    Args:
        symbol: Trading pair symbol (e.g., "BTC/USDT")
        timeframe: Timeframe string (e.g., "15m", "30m", "1h")
        days: Number of days of historical data to fetch
        
    Returns:
        pandas.DataFrame with columns: timestamp, open, high, low, close, volume
    """
    exchange = _get_exchange()
    
    # Calculate the start time
    since = exchange.parse8601((datetime.utcnow() - timedelta(days=days)).isoformat())
    
    # Fetch OHLCV data
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since)
    
    # Convert to DataFrame
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    return df
