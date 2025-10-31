#!/usr/bin/env python3
"""
Historical order block detection script.
Fetches historical data for configured symbols and timeframes,
detects order blocks, and generates charts.
"""
import os
import sys

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src import config
from src import data_fetcher
from src import detection
from src import plotter


def main():
    """Main function to run historical order block detection."""
    print("=" * 60)
    print("Order Block Historical Analysis")
    print("=" * 60)
    print(f"Symbols: {config.SYMBOLS}")
    print(f"Timeframes: {config.TIMEFRAMES}")
    print()
    
    # Ensure charts directory exists
    os.makedirs('charts', exist_ok=True)
    
    # Process each symbol and timeframe combination
    for symbol in config.SYMBOLS:
        for timeframe in config.TIMEFRAMES:
            print(f"\nProcessing {symbol} on {timeframe}...")
            
            try:
                # Fetch historical data
                df = data_fetcher.fetch_last_n_days(symbol, timeframe, days=config.HISTORY_DAYS)
                print(f"  Fetched {len(df)} candles")
                
                # Detect order blocks
                blocks = detection.detect_order_blocks(df)
                bullish_count = len(blocks['bullish'])
                bearish_count = len(blocks['bearish'])
                print(f"  Detected {bullish_count} bullish and {bearish_count} bearish order blocks")
                
                # Generate and save chart
                symbol_filename = symbol.replace('/', '_')
                chart_path = f"charts/{symbol_filename}_{timeframe}_order_blocks.png"
                plotter.plot_with_blocks(df, blocks, symbol, timeframe, save_path=chart_path)
                
            except Exception as e:
                print(f"  Error processing {symbol} {timeframe}: {e}")
                continue
    
    print("\n" + "=" * 60)
    print("Historical analysis complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
