"""
Plotting module for visualizing order blocks on price charts.
"""
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from datetime import datetime


def plot_with_blocks(df, blocks, symbol, timeframe, save_path=None):
    """
    Plot candlestick chart with order blocks highlighted.
    
    Args:
        df: pandas.DataFrame with OHLCV data
        blocks: dict with 'bullish' and 'bearish' order block lists
        symbol: Trading pair symbol (e.g., "BTC/USDT")
        timeframe: Timeframe string (e.g., "15m", "30m")
        save_path: Path to save the chart (optional)
    """
    fig, ax = plt.subplots(figsize=(14, 8))
    
    # Plot candlesticks
    for i in range(len(df)):
        row = df.iloc[i]
        color = 'green' if row['close'] >= row['open'] else 'red'
        
        # Plot the wick
        ax.plot([i, i], [row['low'], row['high']], color='black', linewidth=0.5)
        
        # Plot the body
        body_height = abs(row['close'] - row['open'])
        body_bottom = min(row['open'], row['close'])
        rect = patches.Rectangle((i - 0.3, body_bottom), 0.6, body_height, 
                                 linewidth=0.5, edgecolor='black', 
                                 facecolor=color, alpha=0.7)
        ax.add_patch(rect)
    
    # Highlight bullish order blocks (green rectangles)
    for block in blocks['bullish']:
        idx = block['index']
        block_rect = patches.Rectangle((idx - 0.5, block['low']), 1, 
                                      block['high'] - block['low'],
                                      linewidth=2, edgecolor='darkgreen', 
                                      facecolor='lightgreen', alpha=0.3)
        ax.add_patch(block_rect)
    
    # Highlight bearish order blocks (red rectangles)
    for block in blocks['bearish']:
        idx = block['index']
        block_rect = patches.Rectangle((idx - 0.5, block['low']), 1, 
                                      block['high'] - block['low'],
                                      linewidth=2, edgecolor='darkred', 
                                      facecolor='lightcoral', alpha=0.3)
        ax.add_patch(block_rect)
    
    ax.set_xlabel('Candle Index')
    ax.set_ylabel('Price')
    ax.set_title(f'{symbol} {timeframe} - Order Blocks')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=100, bbox_inches='tight')
        print(f"Chart saved to: {save_path}")
    else:
        plt.show()
    
    plt.close()
