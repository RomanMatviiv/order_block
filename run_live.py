#!/usr/bin/env python3
"""
Live order block detection script.
Monitors configured symbols and timeframes in real-time,
sends Telegram notifications when new order blocks are detected.
"""
import os
import sys
import time
import threading
from collections import defaultdict

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src import config
from src import data_fetcher
from src import detection
from src import notifier


# Global store for seen blocks (in-memory deduplication)
# Key format: "{symbol}_{timeframe}_{index}_{type}"
SEEN_BLOCKS = set()
LOCK = threading.Lock()


def worker_thread(symbol, timeframe):
    """
    Worker thread that monitors a single symbol/timeframe combination.
    
    Args:
        symbol: Trading pair symbol (e.g., "BTC/USDT")
        timeframe: Timeframe string (e.g., "15m", "30m")
    """
    print(f"[{symbol} {timeframe}] Worker started")
    
    while True:
        try:
            # Fetch recent data (2 days to have enough history for detection)
            df = data_fetcher.fetch_last_n_days(symbol, timeframe, days=2)
            
            # Detect order blocks
            blocks = detection.detect_order_blocks(df)
            
            # Process all detected blocks
            all_blocks = blocks['bullish'] + blocks['bearish']
            
            for block in all_blocks:
                # Create unique key for this block
                block_key = f"{symbol}_{timeframe}_{block['index']}_{block['type']}"
                
                # Check if we've already notified about this block
                with LOCK:
                    if block_key in SEEN_BLOCKS:
                        continue
                    SEEN_BLOCKS.add(block_key)
                
                # New block detected - send notification
                message = notifier.format_block_message(symbol, timeframe, block)
                print(f"\n[{symbol} {timeframe}] New {block['type']} order block detected at index {block['index']}")
                notifier.send_telegram(message)
            
        except Exception as e:
            print(f"[{symbol} {timeframe}] Error: {e}")
        
        # Wait before next poll
        time.sleep(config.POLL_INTERVAL_SEC)


def main():
    """Main function to start live order block monitoring."""
    print("=" * 60)
    print("Order Block Live Monitoring")
    print("=" * 60)
    print(f"Symbols: {config.SYMBOLS}")
    print(f"Timeframes: {config.TIMEFRAMES}")
    print(f"Poll Interval: {config.POLL_INTERVAL_SEC} seconds")
    print()
    
    # Create a thread for each symbol/timeframe combination
    threads = []
    for symbol in config.SYMBOLS:
        for timeframe in config.TIMEFRAMES:
            thread = threading.Thread(
                target=worker_thread,
                args=(symbol, timeframe),
                daemon=True,
                name=f"{symbol}_{timeframe}"
            )
            thread.start()
            threads.append(thread)
    
    print(f"Started {len(threads)} worker threads")
    print("Monitoring for order blocks... Press Ctrl+C to stop")
    print("=" * 60)
    print()
    
    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nStopping live monitoring...")
        sys.exit(0)


if __name__ == "__main__":
    main()
