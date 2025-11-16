#!/usr/bin/env python3
"""
WebSocket-based live order block detection module.
Connects to Binance WebSocket streams for real-time kline data.
"""
import asyncio
import json
import os
import websockets
import pandas as pd
import requests
from typing import Dict, Set, Tuple, Optional
from datetime import datetime
from collections import defaultdict, deque

from . import config
from . import detection
from . import notifier





class KlineBuffer:
    """Manages a rolling buffer of klines for a symbol/timeframe pair."""
    
    def __init__(self, max_candles: int = 200):
        """
        Initialize the kline buffer.
        
        Args:
            max_candles: Maximum number of candles to keep in buffer
        """
        self.max_candles = max_candles
        self.klines = []
    
    def add_kline(self, kline_data: Dict) -> None:
        """
        Add a closed kline to the buffer.
        
        Args:
            kline_data: Kline data from WebSocket
        """
        # Extract OHLCV data
        kline = {
            'timestamp': pd.to_datetime(kline_data['t'], unit='ms'),
            'open': float(kline_data['o']),
            'high': float(kline_data['h']),
            'low': float(kline_data['l']),
            'close': float(kline_data['c']),
            'volume': float(kline_data['v'])
        }
        
        # Add to buffer
        self.klines.append(kline)
        
        # Keep only max_candles most recent
        if len(self.klines) > self.max_candles:
            self.klines = self.klines[-self.max_candles:]
    
    def get_dataframe(self) -> pd.DataFrame:
        """
        Get the buffer as a DataFrame.
        
        Returns:
            DataFrame with OHLCV data
        """
        if not self.klines:
            return pd.DataFrame()
        return pd.DataFrame(self.klines)
    
    def is_ready(self) -> bool:
        """
        Check if buffer has enough data for detection.
        
        Returns:
            True if buffer has sufficient data
        """
        # Need at least ATR_PERIOD + DETECTION_LOOKAHEAD + 1 candles
        min_required = config.ATR_PERIOD + config.DETECTION_LOOKAHEAD + 1
        return len(self.klines) >= min_required


class DeduplicationState:
    """Manages persistent deduplication state across restarts."""
    
    def __init__(self, state_file: str):
        """
        Initialize deduplication state.
        
        Args:
            state_file: Path to state file
        """
        self.state_file = state_file
        # Use deque to maintain order for pruning
        self.seen_blocks: deque = deque()
        self.seen_set: Set[str] = set()  # For fast lookup
        self.load_state()
    
    def load_state(self) -> None:
        """Load state from file if it exists."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    blocks = data.get('seen_blocks', [])
                    self.seen_blocks = deque(blocks)
                    self.seen_set = set(blocks)
                print(f"Loaded {len(self.seen_blocks)} seen blocks from state file")
            except Exception as e:
                print(f"Warning: Could not load state file: {e}")
                self.seen_blocks = deque()
                self.seen_set = set()
    
    def save_state(self) -> None:
        """Save state to file."""
        try:
            data = {
                'seen_blocks': list(self.seen_blocks),
                'last_updated': datetime.now().isoformat()
            }
            with open(self.state_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save state file: {e}")
    
    def is_seen(self, block_key: str) -> bool:
        """
        Check if a block has been seen.
        
        Args:
            block_key: Unique block identifier
            
        Returns:
            True if block was seen before
        """
        return block_key in self.seen_set
    
    def mark_seen(self, block_key: str) -> None:
        """
        Mark a block as seen.
        
        Args:
            block_key: Unique block identifier
        """
        if block_key not in self.seen_set:
            self.seen_blocks.append(block_key)
            self.seen_set.add(block_key)
            self.save_state()
    
    def prune_old_entries(self, max_entries: int = 10000) -> None:
        """
        Prune old entries if state grows too large.
        Removes oldest entries first (FIFO).
        
        Args:
            max_entries: Maximum number of entries to keep
        """
        if len(self.seen_blocks) > max_entries:
            # Remove oldest entries
            to_remove = len(self.seen_blocks) - max_entries
            print(f"State file too large ({len(self.seen_blocks)} entries), removing {to_remove} oldest entries...")
            for _ in range(to_remove):
                if self.seen_blocks:
                    old_key = self.seen_blocks.popleft()
                    self.seen_set.discard(old_key)
            self.save_state()


class BinanceWebSocketClient:
    """WebSocket client for Binance kline streams."""
    
    def __init__(self, symbols: list, timeframes: list, max_bars: int = None):
        """
        Initialize WebSocket client.
        
        Args:
            symbols: List of trading pairs (e.g., ["BTC/USDT", "ETH/USDT"])
            timeframes: List of timeframes (e.g., ["15m", "30m"])
            max_bars: Maximum number of bars to keep in buffer (defaults to config.WS_MAX_BARS)
        """
        self.symbols = symbols
        self.timeframes = timeframes
        self.max_bars = max_bars or config.WS_MAX_BARS
        self.buffers: Dict[Tuple[str, str], KlineBuffer] = {}
        self.dedup_state = DeduplicationState(config.STATE_FILE)
        
        # Initialize buffers for each symbol/timeframe pair
        for symbol in symbols:
            for timeframe in timeframes:
                key = (symbol, timeframe)
                self.buffers[key] = KlineBuffer(max_candles=self.max_bars)
    
    def get_stream_names(self) -> list:
        """
        Generate WebSocket stream names for all symbol/timeframe pairs.
        
        Returns:
            List of stream names
        """
        streams = []
        for symbol in self.symbols:
            # Convert symbol format: "BTC/USDT" -> "btcusdt"
            binance_symbol = symbol.replace('/', '').lower()
            for timeframe in self.timeframes:
                # Stream name format: btcusdt@kline_15m
                stream_name = f"{binance_symbol}@kline_{timeframe}"
                streams.append(stream_name)
        return streams
    
    def get_websocket_url(self) -> str:
        """
        Build WebSocket URL with combined streams.
        
        Returns:
            WebSocket URL
        """
        streams = self.get_stream_names()
        streams_param = '/'.join(streams)
        return f"{config.WS_BASE}/stream?streams={streams_param}"
    
    def parse_symbol_from_stream(self, stream_name: str) -> Tuple[str, str]:
        """
        Parse symbol and timeframe from stream name.
        
        Args:
            stream_name: Stream name (e.g., "btcusdt@kline_15m")
            
        Returns:
            Tuple of (symbol, timeframe)
        """
        # Parse stream name: "btcusdt@kline_15m" -> ("BTC/USDT", "15m")
        parts = stream_name.split('@')
        if len(parts) != 2:
            raise ValueError(f"Invalid stream name: {stream_name}")
        
        binance_symbol = parts[0]
        kline_part = parts[1]  # "kline_15m"
        
        # Extract timeframe
        if not kline_part.startswith('kline_'):
            raise ValueError(f"Invalid kline stream: {kline_part}")
        timeframe = kline_part.replace('kline_', '')
        
        # Find matching symbol from config
        # Try to match by converting to lowercase and removing /
        for symbol in self.symbols:
            if symbol.replace('/', '').lower() == binance_symbol:
                return (symbol, timeframe)
        
        raise ValueError(f"Unknown symbol: {binance_symbol}")
    
    def fetch_exchange_info(self) -> Set[str]:
        """
        Fetch available symbols from Binance Futures exchangeInfo API.
        
        Returns:
            Set of valid symbol names (e.g., {"BTCUSDT", "ETHUSDT"})
        """
        url = f"{config.REST_BASE}/fapi/v1/exchangeInfo"
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Extract symbols with status TRADING
            valid_symbols = set()
            for symbol_info in data.get('symbols', []):
                if symbol_info.get('status') == 'TRADING':
                    valid_symbols.add(symbol_info['symbol'])
            
            return valid_symbols
        
        except Exception as e:
            print(f"Warning: Could not fetch exchangeInfo: {e}")
            return set()
    
    def fetch_historical_klines(self, symbol: str, timeframe: str, limit: int = None) -> pd.DataFrame:
        """
        Fetch historical klines from Binance Futures REST API.
        
        Args:
            symbol: Trading pair symbol (e.g., "BTC/USDT")
            timeframe: Timeframe string (e.g., "15m", "30m")
            limit: Number of klines to fetch (defaults to self.max_bars)
            
        Returns:
            DataFrame with OHLCV data
        """
        if limit is None:
            limit = self.max_bars
        
        # Convert symbol format: "BTC/USDT" -> "BTCUSDT"
        binance_symbol = symbol.replace('/', '')
        
        # Build URL for Binance Futures API
        url = f"{config.REST_BASE}/fapi/v1/klines"
        params = {
            'symbol': binance_symbol,
            'interval': timeframe,
            'limit': limit
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            klines = response.json()
            
            # Convert to DataFrame
            # Binance kline format: [open_time, open, high, low, close, volume, close_time, ...]
            if not klines:
                return pd.DataFrame()
            
            df = pd.DataFrame(klines, columns=[
                'open_time', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                'taker_buy_quote', 'ignore'
            ])
            
            # Convert types and select only needed columns
            df['timestamp'] = pd.to_datetime(df['open_time'], unit='ms')
            df['open'] = df['open'].astype(float)
            df['high'] = df['high'].astype(float)
            df['low'] = df['low'].astype(float)
            df['close'] = df['close'].astype(float)
            df['volume'] = df['volume'].astype(float)
            
            # Return only OHLCV columns
            return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
        
        except Exception as e:
            print(f"Error fetching historical klines for {symbol} {timeframe}: {e}")
            return pd.DataFrame()
    
    def preload_historical_data(self, send_historical: bool = False) -> None:
        """
        Preload historical klines into buffers and run initial detection.
        
        Args:
            send_historical: If True, send Telegram notifications for historical blocks.
                           If False, mark historical blocks as seen without notifications.
        """
        print("=" * 60)
        print("Preloading historical data...")
        print("=" * 60)
        
        # Fetch valid symbols from exchangeInfo
        valid_symbols = self.fetch_exchange_info()
        
        if valid_symbols:
            print(f"Fetched {len(valid_symbols)} valid symbols from Binance Futures exchangeInfo")
        else:
            print("Warning: Could not fetch exchangeInfo, will attempt all configured symbols")
        
        for symbol in self.symbols:
            # Check if symbol is supported (skip gracefully if not)
            binance_symbol = symbol.replace('/', '')
            if valid_symbols and binance_symbol not in valid_symbols:
                print(f"[{symbol}] Skipping - not available on Binance Futures")
                continue
            
            for timeframe in self.timeframes:
                buffer_key = (symbol, timeframe)
                
                print(f"[{symbol} {timeframe}] Fetching {self.max_bars} historical klines...")
                
                # Fetch historical data
                df = self.fetch_historical_klines(symbol, timeframe, self.max_bars)
                
                if df.empty:
                    print(f"[{symbol} {timeframe}] Warning: No historical data fetched")
                    continue
                
                print(f"[{symbol} {timeframe}] Fetched {len(df)} klines")
                
                # Populate buffer with historical data
                buffer = self.buffers[buffer_key]
                for _, row in df.iterrows():
                    # Convert DataFrame row to kline format expected by buffer
                    kline_data = {
                        't': int(row['timestamp'].timestamp() * 1000),
                        'o': str(row['open']),
                        'h': str(row['high']),
                        'l': str(row['low']),
                        'c': str(row['close']),
                        'v': str(row['volume'])
                    }
                    buffer.add_kline(kline_data)
                
                # Check if buffer is ready for detection
                if not buffer.is_ready():
                    print(f"[{symbol} {timeframe}] Buffer not ready for detection (need {config.ATR_PERIOD + config.DETECTION_LOOKAHEAD + 1} candles)")
                    continue
                
                # Run detection on historical data
                print(f"[{symbol} {timeframe}] Running detection on historical data...")
                df_buffer = buffer.get_dataframe()
                blocks = detection.detect_order_blocks(df_buffer)
                
                # Process detected blocks
                all_blocks = blocks['bullish'] + blocks['bearish']
                historical_blocks_count = 0
                notified_count = 0
                
                for block in all_blocks:
                    # Create unique key for deduplication
                    score = block.get('score', 0.5)
                    score_rounded = round(score, 2)
                    
                    # Skip blocks below minimum score threshold
                    if score < config.WS_NOTIFY_SCORE_MIN:
                        continue
                    
                    block_key = f"{symbol}|{timeframe}|{block['index']}|{block['type']}|{score_rounded}"
                    
                    # Check if already seen
                    if self.dedup_state.is_seen(block_key):
                        continue
                    
                    historical_blocks_count += 1
                    
                    if send_historical:
                        # Send notification for historical block
                        message_text = notifier.format_block_message(symbol, timeframe, block)
                        print(f"[{symbol} {timeframe}] Historical {block['type']} order block at index {block['index']} (score: {score:.2f})")
                        notifier.send_telegram(message_text)
                        notified_count += 1
                    
                    # Mark as seen
                    self.dedup_state.mark_seen(block_key)
                
                if send_historical:
                    print(f"[{symbol} {timeframe}] Sent {notified_count} historical notifications")
                else:
                    print(f"[{symbol} {timeframe}] Marked {historical_blocks_count} historical blocks as seen (no notifications)")
        
        # Save state after preloading
        self.dedup_state.save_state()
        
        print("=" * 60)
        print("Historical data preloading complete!")
        print("=" * 60)
        print()
    
    async def process_kline(self, message: Dict) -> None:
        """
        Process a kline message from WebSocket.
        
        Args:
            message: WebSocket message
        """
        try:
            # Extract kline data
            stream_name = message.get('stream', '')
            data = message.get('data', {})
            kline = data.get('k', {})
            
            # Only process closed klines
            is_closed = kline.get('x', False)
            if not is_closed:
                return
            
            # Parse symbol and timeframe
            symbol, timeframe = self.parse_symbol_from_stream(stream_name)
            
            # Get buffer for this pair
            buffer_key = (symbol, timeframe)
            buffer = self.buffers.get(buffer_key)
            if not buffer:
                return
            
            # Add kline to buffer
            buffer.add_kline(kline)
            
            # Check if buffer has enough data for detection
            if not buffer.is_ready():
                print(f"[{symbol} {timeframe}] Buffering data... ({len(buffer.klines)} candles)")
                return
            
            # Get DataFrame from buffer
            df = buffer.get_dataframe()
            
            # Detect order blocks
            blocks = detection.detect_order_blocks(df)
            
            # Process all detected blocks
            all_blocks = blocks['bullish'] + blocks['bearish']
            
            for block in all_blocks:
                # Create unique key for deduplication using pipe delimiter
                # Format: symbol|timeframe|index|type|score
                score = block.get('score', 0.5)
                score_rounded = round(score, 2)
                
                # Skip blocks below minimum score threshold
                if score < config.WS_NOTIFY_SCORE_MIN:
                    continue
                
                block_key = f"{symbol}|{timeframe}|{block['index']}|{block['type']}|{score_rounded}"
                
                # Check if already seen
                if self.dedup_state.is_seen(block_key):
                    continue
                
                # Mark as seen
                self.dedup_state.mark_seen(block_key)
                
                # Send notification
                message_text = notifier.format_block_message(symbol, timeframe, block)
                print(f"\n[{symbol} {timeframe}] New {block['type']} order block detected at index {block['index']} (score: {score:.2f})")
                notifier.send_telegram(message_text)
            
            # Periodically prune state file
            if len(self.dedup_state.seen_set) > 10000:
                self.dedup_state.prune_old_entries()
        
        except Exception as e:
            print(f"Error processing kline: {e}")
    
    async def connect_and_listen(self, send_historical: bool = False) -> None:
        """
        Connect to WebSocket and listen for messages.
        
        Args:
            send_historical: If True, send Telegram notifications for historical blocks on startup.
        """
        # Preload historical data before connecting to WebSocket
        self.preload_historical_data(send_historical=send_historical)
        
        url = self.get_websocket_url()
        print(f"Connecting to Binance WebSocket...")
        print(f"URL: {url}")
        print(f"Monitoring {len(self.symbols)} symbols on {len(self.timeframes)} timeframes")
        print()
        
        retry_delay = 1
        max_retry_delay = 60
        
        while True:
            try:
                async with websockets.connect(url, ping_interval=20, ping_timeout=10) as websocket:
                    print("✓ Connected to Binance WebSocket")
                    print("Listening for kline events... Press Ctrl+C to stop")
                    print("=" * 60)
                    print()
                    
                    # Reset retry delay on successful connection
                    retry_delay = 1
                    
                    # Listen for messages
                    async for message in websocket:
                        try:
                            data = json.loads(message)
                            await self.process_kline(data)
                        except json.JSONDecodeError as e:
                            print(f"Error decoding message: {e}")
                        except Exception as e:
                            print(f"Error processing message: {e}")
            
            except websockets.exceptions.WebSocketException as e:
                print(f"WebSocket error: {e}")
                print(f"Reconnecting in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, max_retry_delay)
            
            except Exception as e:
                print(f"Unexpected error: {e}")
                print(f"Reconnecting in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, max_retry_delay)


async def run_live_ws(send_historical: bool = False):
    """
    Main function to run WebSocket-based live detection.
    
    Args:
        send_historical: If True, send Telegram notifications for historical blocks on startup.
    """
    print("=" * 60)
    print("Order Block Live Monitoring (WebSocket)")
    print("=" * 60)
    print(f"Symbols: {config.SYMBOLS}")
    print(f"Timeframes: {config.TIMEFRAMES}")
    print(f"Send Historical Notifications: {send_historical}")
    print()
    
    # Create WebSocket client
    client = BinanceWebSocketClient(config.SYMBOLS, config.TIMEFRAMES)
    
    # Connect and listen
    await client.connect_and_listen(send_historical=send_historical)


def main(send_historical: bool = False):
    """
    Entry point for WebSocket-based live monitoring.
    
    Args:
        send_historical: If True, send Telegram notifications for historical blocks on startup.
    """
    try:
        asyncio.run(run_live_ws(send_historical=send_historical))
    except KeyboardInterrupt:
        print("\n\nStopping live monitoring...")


if __name__ == "__main__":
    main()
