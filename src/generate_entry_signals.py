"""
Entry signal generation module.
Generates trading signals based on detected order blocks.
"""


def generate_entry_signals(df, blocks):
    """
    Generate entry signals based on detected order blocks.
    
    Args:
        df: pandas.DataFrame with OHLCV data
        blocks: dict with 'bullish' and 'bearish' order block lists
        
    Returns:
        dict with entry signals for bullish and bearish blocks
    """
    signals = {
        'bullish_entries': [],
        'bearish_entries': []
    }
    
    # For each bullish block, a signal is generated when price returns to the block zone
    for block in blocks['bullish']:
        signals['bullish_entries'].append({
            'index': block['index'],
            'entry_low': block['low'],
            'entry_high': block['high'],
            'type': 'buy'
        })
    
    # For each bearish block, a signal is generated when price returns to the block zone
    for block in blocks['bearish']:
        signals['bearish_entries'].append({
            'index': block['index'],
            'entry_low': block['low'],
            'entry_high': block['high'],
            'type': 'sell'
        })
    
    return signals
