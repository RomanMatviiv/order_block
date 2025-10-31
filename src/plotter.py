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
    
    # Highlight bullish order blocks (green rectangles with score-based alpha)
    for block in blocks['bullish']:
        idx = block['index']
        score = block.get('score', 0.5)
        has_sweep = block.get('has_sweep', False)
        
        # Alpha based on score (min 0.2, max 0.6)
        alpha = 0.2 + (score * 0.4)
        
        # Edge color and width based on sweep detection
        edge_color = 'lime' if has_sweep else 'darkgreen'
        edge_width = 3 if has_sweep else 2
        
        block_rect = patches.Rectangle((idx - 0.5, block['low']), 1, 
                                      block['high'] - block['low'],
                                      linewidth=edge_width, edgecolor=edge_color, 
                                      facecolor='lightgreen', alpha=alpha)
        ax.add_patch(block_rect)
        
        # Add score annotation
        mid_price = (block['low'] + block['high']) / 2
        ax.text(idx, mid_price, f"{score:.2f}", 
               fontsize=8, ha='center', va='center',
               bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.7))
    
    # Highlight bearish order blocks (red rectangles with score-based alpha)
    for block in blocks['bearish']:
        idx = block['index']
        score = block.get('score', 0.5)
        has_sweep = block.get('has_sweep', False)
        
        # Alpha based on score (min 0.2, max 0.6)
        alpha = 0.2 + (score * 0.4)
        
        # Edge color and width based on sweep detection
        edge_color = 'orangered' if has_sweep else 'darkred'
        edge_width = 3 if has_sweep else 2
        
        block_rect = patches.Rectangle((idx - 0.5, block['low']), 1, 
                                      block['high'] - block['low'],
                                      linewidth=edge_width, edgecolor=edge_color, 
                                      facecolor='lightcoral', alpha=alpha)
        ax.add_patch(block_rect)
        
        # Add score annotation
        mid_price = (block['low'] + block['high']) / 2
        ax.text(idx, mid_price, f"{score:.2f}", 
               fontsize=8, ha='center', va='center',
               bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.7))
    
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
