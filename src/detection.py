"""
Order block detection module.
Identifies bullish and bearish order blocks in price data.
"""
import pandas as pd
import numpy as np


def detect_order_blocks(df, lookback=20):
    """
    Detect order blocks in the price data.
    
    An order block is identified as a candle before a strong move:
    - Bullish order block: Down candle before a strong upward move
    - Bearish order block: Up candle before a strong downward move
    
    Args:
        df: pandas.DataFrame with OHLCV data
        lookback: Number of candles to look back for detection
        
    Returns:
        dict with 'bullish' and 'bearish' lists of order blocks
        Each block is a dict with: index, low, high, type
    """
    blocks = {
        'bullish': [],
        'bearish': []
    }
    
    if len(df) < lookback + 1:
        return blocks
    
    for i in range(lookback, len(df) - 1):
        current = df.iloc[i]
        next_candle = df.iloc[i + 1]
        
        # Look for strong moves
        current_range = current['high'] - current['low']
        next_range = next_candle['high'] - next_candle['low']
        
        # Bullish order block: down candle followed by strong up move
        if current['close'] < current['open'] and next_candle['close'] > next_candle['open']:
            if next_range > current_range * 1.5:  # Strong move threshold
                blocks['bullish'].append({
                    'index': i,
                    'low': current['low'],
                    'high': current['high'],
                    'type': 'bullish'
                })
        
        # Bearish order block: up candle followed by strong down move
        if current['close'] > current['open'] and next_candle['close'] < next_candle['open']:
            if next_range > current_range * 1.5:  # Strong move threshold
                blocks['bearish'].append({
                    'index': i,
                    'low': current['low'],
                    'high': current['high'],
                    'type': 'bearish'
                })
    
    return blocks
