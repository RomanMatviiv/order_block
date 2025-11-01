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

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src import config
from src import data_fetcher
from src import detection
from src import notifier
from src import state


# Global store for seen blocks (persistent deduplication via state module)
LOCK = threading.Lock()
# Load seen blocks from persistent state
STATE_DATA = state.load_state(config.STATE_FILE)
SEEN_BLOCKS = set(STATE_DATA.get('seen_blocks', []))


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
            # Fetch recent data
            df = data_fetcher.fetch_last_n_days(symbol, timeframe, days=config.HISTORY_DAYS)
            
            # Detect order blocks with new advanced algorithm
            blocks = detection.detect_order_blocks(df)
            
            # Process all detected blocks
            all_blocks = blocks['bullish'] + blocks['bearish']
            
            for block in all_blocks:
                # Create unique key for this block (include rounded score for dedup)
                score = block.get('score', 0.5)
                
                # Filter by minimum confidence score (same as WebSocket version)
                if score < config.WS_NOTIFY_SCORE_MIN:
                    continue
                
                score_rounded = round(score, 2)
                block_key = f"{symbol}_{timeframe}_{block['index']}_{block['type']}_{score_rounded}"
                
                # Check if we've already notified about this block
                with LOCK:
                    if block_key in SEEN_BLOCKS:
                        continue
                    SEEN_BLOCKS.add(block_key)
                    
                    # Save state after adding new block
                    try:
                        state.save_state(config.STATE_FILE, {'seen_blocks': list(SEEN_BLOCKS)})
                    except Exception as e:
                        print(f"Warning: Could not save state: {e}")
                
                # New block detected - send notification
                message = notifier.format_block_message(symbol, timeframe, block)
                print(f"\n[{symbol} {timeframe}] New {block['type']} order block detected at index {block['index']} (score: {score:.2f})")
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
    print(f"Minimum Confidence Score: {config.WS_NOTIFY_SCORE_MIN}")
    if SEEN_BLOCKS:
        print(f"Loaded {len(SEEN_BLOCKS)} seen blocks from persistent state")
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
