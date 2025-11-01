"""
WebSocket-based live order block detection for Binance.

This module provides a robust async WebSocket client that:
- Connects to Binance's public kline stream
- Processes only closed kline events
- Persists deduplication state across restarts
- Implements reconnection with exponential backoff
- Integrates with the advanced detection logic
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Set, Optional
import websockets
import pandas as pd

# Add src directory to Python path if needed
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src import config
from src import detection
from src import notifier

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
BINANCE_WS_URL = "wss://stream.binance.com:9443/ws"
DEDUP_STATE_FILE = "dedup_state.json"
MAX_RECONNECT_DELAY = 300  # 5 minutes max delay
INITIAL_RECONNECT_DELAY = 1  # Start with 1 second
PING_INTERVAL = 20  # Send ping every 20 seconds
PING_TIMEOUT = 10  # Wait 10 seconds for pong


class KlineBuffer:
    """
    Buffer to accumulate kline data for detection.
    Maintains a sliding window of recent candles for each symbol/timeframe.
    """
    
    def __init__(self, max_candles: int = 200):
        """
        Initialize the kline buffer.
        
        Args:
            max_candles: Maximum number of candles to keep in buffer
        """
        self.max_candles = max_candles
        self.buffers: Dict[str, pd.DataFrame] = {}
        self.lock = asyncio.Lock()
    
    async def add_candle(self, symbol: str, timeframe: str, kline: Dict) -> pd.DataFrame:
        """
        Add a closed candle to the buffer.
        
        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT")
            timeframe: Timeframe string (e.g., "15m")
            kline: Kline data dict
            
        Returns:
            Updated DataFrame for this symbol/timeframe
        """
        async with self.lock:
            key = f"{symbol}_{timeframe}"
            
            # Create new candle row
            new_row = pd.DataFrame([{
                'timestamp': pd.to_datetime(kline['t'], unit='ms'),
                'open': float(kline['o']),
                'high': float(kline['h']),
                'low': float(kline['l']),
                'close': float(kline['c']),
                'volume': float(kline['v'])
            }])
            
            if key not in self.buffers:
                self.buffers[key] = new_row
            else:
                # Append new candle
                self.buffers[key] = pd.concat([self.buffers[key], new_row], ignore_index=True)
                
                # Keep only last max_candles
                if len(self.buffers[key]) > self.max_candles:
                    self.buffers[key] = self.buffers[key].iloc[-self.max_candles:].reset_index(drop=True)
            
            return self.buffers[key].copy()


class DeduplicationManager:
    """
    Manages deduplication state with persistence across restarts.
    """
    
    def __init__(self, state_file: str = DEDUP_STATE_FILE):
        """
        Initialize deduplication manager.
        
        Args:
            state_file: Path to the state file
        """
        self.state_file = Path(state_file)
        self.seen_blocks: Set[str] = set()
        self.lock = asyncio.Lock()
        self._load_state()
    
    def _load_state(self):
        """Load deduplication state from file."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    self.seen_blocks = set(data.get('seen_blocks', []))
                    logger.info(f"Loaded {len(self.seen_blocks)} seen blocks from {self.state_file}")
            except Exception as e:
                logger.error(f"Failed to load state file: {e}")
                self.seen_blocks = set()
        else:
            logger.info("No existing state file found, starting fresh")
    
    async def _save_state(self):
        """Save deduplication state to file."""
        try:
            data = {
                'seen_blocks': list(self.seen_blocks),
                'last_updated': datetime.now(timezone.utc).isoformat()
            }
            with open(self.state_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Saved {len(self.seen_blocks)} seen blocks to {self.state_file}")
        except Exception as e:
            logger.error(f"Failed to save state file: {e}")
    
    async def is_seen(self, block_key: str) -> bool:
        """
        Check if a block has been seen before.
        
        Args:
            block_key: Unique block identifier
            
        Returns:
            True if block was seen before
        """
        async with self.lock:
            return block_key in self.seen_blocks
    
    async def mark_seen(self, block_key: str):
        """
        Mark a block as seen and persist to disk.
        
        Args:
            block_key: Unique block identifier
        """
        async with self.lock:
            if block_key not in self.seen_blocks:
                self.seen_blocks.add(block_key)
                await self._save_state()


class BinanceWebSocketClient:
    """
    Async WebSocket client for Binance kline streams with reconnection logic.
    """
    
    def __init__(self, symbols: List[str], timeframes: List[str]):
        """
        Initialize WebSocket client.
        
        Args:
            symbols: List of trading pair symbols (e.g., ["BTCUSDT", "ETHUSDT"])
            timeframes: List of timeframes (e.g., ["15m", "30m"])
        """
        self.symbols = symbols
        self.timeframes = timeframes
        self.kline_buffer = KlineBuffer()
        self.dedup_manager = DeduplicationManager()
        self.websocket = None
        self.reconnect_delay = INITIAL_RECONNECT_DELAY
        self.running = False
    
    def _get_stream_names(self) -> List[str]:
        """
        Generate stream names for subscription.
        
        Returns:
            List of stream names (e.g., ["btcusdt@kline_15m", "ethusdt@kline_30m"])
        """
        streams = []
        for symbol in self.symbols:
            for timeframe in self.timeframes:
                stream = f"{symbol.lower()}@kline_{timeframe}"
                streams.append(stream)
        return streams
    
    def _get_ws_url(self) -> str:
        """
        Build WebSocket URL with stream subscriptions.
        
        Returns:
            Full WebSocket URL
        """
        streams = self._get_stream_names()
        stream_path = "/".join(streams)
        return f"{BINANCE_WS_URL}/{stream_path}"
    
    async def _process_kline_event(self, data: Dict):
        """
        Process a kline event from WebSocket.
        
        Args:
            data: Kline event data
        """
        try:
            kline = data.get('k', {})
            
            # Only process closed candles
            if not kline.get('x', False):
                logger.debug(f"Skipping unclosed candle for {kline.get('s')}")
                return
            
            symbol = kline.get('s', '')
            interval = kline.get('i', '')
            
            # Convert Binance symbol format (BTCUSDT -> BTC/USDT for display)
            display_symbol = self._format_symbol(symbol)
            
            logger.info(f"Processing closed kline: {display_symbol} {interval}")
            
            # Add to buffer
            df = await self.kline_buffer.add_candle(symbol, interval, kline)
            
            # Need enough data for detection
            min_required = config.ATR_PERIOD + config.DETECTION_LOOKAHEAD + 1
            if len(df) < min_required:
                logger.debug(f"Not enough data for {display_symbol} {interval}: {len(df)}/{min_required}")
                return
            
            # Run detection
            zones = detection.detect_order_zones(df)
            
            if not zones:
                logger.debug(f"No zones detected for {display_symbol} {interval}")
                return
            
            # Process detected zones
            for zone in zones:
                # Create unique key for deduplication
                score_rounded = round(zone['score'], 2)
                block_key = f"{symbol}_{interval}_{zone['index']}_{zone['type']}_{score_rounded}"
                
                # Check if already seen
                if await self.dedup_manager.is_seen(block_key):
                    logger.debug(f"Block already seen: {block_key}")
                    continue
                
                # Mark as seen
                await self.dedup_manager.mark_seen(block_key)
                
                # Create block dict for notification (compatible with notifier)
                block = {
                    'index': zone['index'],
                    'low': zone['low'],
                    'high': zone['high'],
                    'type': zone['type'],
                    'score': zone['score'],
                    'touches': zone.get('touches', 1),
                    'has_sweep': zone.get('has_sweep', False)
                }
                
                # Send notification
                logger.info(f"New {zone['type']} order block detected: {display_symbol} {interval} "
                          f"(score: {zone['score']:.2f})")
                message = notifier.format_block_message(display_symbol, interval, block)
                notifier.send_telegram(message)
                
        except Exception as e:
            logger.error(f"Error processing kline event: {e}", exc_info=True)
    
    def _format_symbol(self, binance_symbol: str) -> str:
        """
        Convert Binance symbol format to display format.
        
        Args:
            binance_symbol: Symbol in Binance format (e.g., "BTCUSDT")
            
        Returns:
            Symbol in display format (e.g., "BTC/USDT")
        """
        # Simple conversion for common pairs
        if binance_symbol.endswith('USDT'):
            base = binance_symbol[:-4]
            return f"{base}/USDT"
        elif binance_symbol.endswith('BUSD'):
            base = binance_symbol[:-4]
            return f"{base}/BUSD"
        elif binance_symbol.endswith('BTC'):
            base = binance_symbol[:-3]
            return f"{base}/BTC"
        elif binance_symbol.endswith('ETH'):
            base = binance_symbol[:-3]
            return f"{base}/ETH"
        else:
            return binance_symbol
    
    async def _handle_message(self, message: str):
        """
        Handle incoming WebSocket message.
        
        Args:
            message: Raw message string
        """
        try:
            data = json.loads(message)
            
            # Check if it's a kline event
            if data.get('e') == 'kline':
                await self._process_kline_event(data)
            else:
                logger.debug(f"Received non-kline event: {data.get('e')}")
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode message: {e}")
        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)
    
    async def _connect_and_listen(self):
        """
        Connect to WebSocket and listen for messages with ping/pong.
        """
        ws_url = self._get_ws_url()
        logger.info(f"Connecting to {ws_url}")
        
        try:
            async with websockets.connect(
                ws_url,
                ping_interval=PING_INTERVAL,
                ping_timeout=PING_TIMEOUT,
                close_timeout=10
            ) as websocket:
                self.websocket = websocket
                self.reconnect_delay = INITIAL_RECONNECT_DELAY  # Reset delay on successful connection
                
                logger.info("WebSocket connected successfully")
                logger.info(f"Monitoring {len(self.symbols)} symbols on {len(self.timeframes)} timeframes")
                
                # Listen for messages
                async for message in websocket:
                    if not self.running:
                        break
                    await self._handle_message(message)
                    
        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(f"WebSocket connection closed: {e}")
            raise
        except Exception as e:
            logger.error(f"WebSocket error: {e}", exc_info=True)
            raise
    
    async def _run_with_reconnect(self):
        """
        Run WebSocket client with automatic reconnection and exponential backoff.
        """
        while self.running:
            try:
                await self._connect_and_listen()
            except Exception as e:
                if not self.running:
                    break
                
                logger.error(f"Connection failed: {e}")
                logger.info(f"Reconnecting in {self.reconnect_delay} seconds...")
                
                await asyncio.sleep(self.reconnect_delay)
                
                # Exponential backoff with jitter
                self.reconnect_delay = min(self.reconnect_delay * 2, MAX_RECONNECT_DELAY)
    
    async def start(self):
        """
        Start the WebSocket client.
        """
        self.running = True
        logger.info("Starting Binance WebSocket client")
        await self._run_with_reconnect()
    
    async def stop(self):
        """
        Stop the WebSocket client.
        """
        logger.info("Stopping Binance WebSocket client")
        self.running = False
        if self.websocket:
            await self.websocket.close()


async def main():
    """
    Main function to run the WebSocket-based live detection.
    """
    print("=" * 60)
    print("Order Block Live Detection (WebSocket)")
    print("=" * 60)
    print(f"Symbols: {config.SYMBOLS}")
    print(f"Timeframes: {config.TIMEFRAMES}")
    print()
    
    # Convert symbols from BTC/USDT format to BTCUSDT format for Binance WebSocket
    binance_symbols = [symbol.replace('/', '') for symbol in config.SYMBOLS]
    
    # Create and start WebSocket client
    client = BinanceWebSocketClient(binance_symbols, config.TIMEFRAMES)
    
    try:
        await client.start()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        await client.stop()
        logger.info("WebSocket client stopped")


if __name__ == "__main__":
    asyncio.run(main())
