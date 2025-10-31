"""
Order block detection module.
Identifies bullish and bearish order blocks in price data with advanced features.
"""
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from . import config


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Calculate Average True Range (ATR) for the given data.
    
    Args:
        df: DataFrame with OHLCV data
        period: ATR period (default: 14)
        
    Returns:
        Series with ATR values
    """
    high = df['high']
    low = df['low']
    close = df['close'].shift(1)
    
    tr1 = high - low
    tr2 = abs(high - close)
    tr3 = abs(low - close)
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    
    return atr


def check_candle_filters(candle: pd.Series, atr_value: float, 
                         is_bullish: bool, body_min_ratio: float = 0.5, 
                         wick_max_ratio: float = 0.3) -> bool:
    """
    Check if candle meets body size and wick filter criteria.
    
    Args:
        candle: Series with candle OHLC data
        atr_value: Current ATR value
        is_bullish: True if checking for bullish block, False for bearish
        body_min_ratio: Minimum body size as ratio of ATR
        wick_max_ratio: Maximum opposite-side wick as ratio of body
        
    Returns:
        True if candle passes filters
    """
    body_size = abs(candle['close'] - candle['open'])
    candle_range = candle['high'] - candle['low']
    
    # Check minimum body size relative to ATR
    if body_size < atr_value * body_min_ratio:
        return False
    
    # For bullish block: check upper wick (opposite side)
    # For bearish block: check lower wick (opposite side)
    if is_bullish:
        # Bullish block from down candle
        if candle['close'] >= candle['open']:
            return False  # Not a down candle
        upper_wick = candle['high'] - candle['open']
        if upper_wick > body_size * wick_max_ratio:
            return False
    else:
        # Bearish block from up candle
        if candle['close'] <= candle['open']:
            return False  # Not an up candle
        lower_wick = candle['open'] - candle['low']
        if lower_wick > body_size * wick_max_ratio:
            return False
    
    return True


def check_impulse_confirmation(df: pd.DataFrame, start_idx: int, 
                               is_bullish: bool, atr_value: float,
                               lookahead: int = 10, 
                               min_dir_candles: int = 6,
                               min_net_move: float = 1.5) -> Tuple[bool, float]:
    """
    Check if there's an impulsive move after the candidate candle.
    
    Args:
        df: DataFrame with OHLCV data
        start_idx: Index of candidate candle
        is_bullish: True for bullish block, False for bearish
        atr_value: Current ATR value
        lookahead: Number of bars to check
        min_dir_candles: Minimum directional candles required
        min_net_move: Minimum net movement as multiple of ATR
        
    Returns:
        Tuple of (confirmation_passed, impulse_strength_score)
    """
    end_idx = min(start_idx + lookahead + 1, len(df))
    if end_idx - start_idx < 3:
        return False, 0.0
    
    lookahead_slice = df.iloc[start_idx + 1:end_idx]
    
    # Count directional candles
    if is_bullish:
        dir_candles = (lookahead_slice['close'] > lookahead_slice['open']).sum()
        net_move = lookahead_slice['high'].max() - df.iloc[start_idx]['high']
    else:
        dir_candles = (lookahead_slice['close'] < lookahead_slice['open']).sum()
        net_move = df.iloc[start_idx]['low'] - lookahead_slice['low'].min()
    
    # Check if minimum directional candles met
    if dir_candles < min_dir_candles:
        return False, 0.0
    
    # Check if minimum net movement met
    net_move_ratio = net_move / atr_value if atr_value > 0 else 0
    if net_move_ratio < min_net_move:
        return False, 0.0
    
    # Calculate impulse strength score (0 to 1)
    dir_candles_score = min(dir_candles / lookahead, 1.0)
    net_move_score = min(net_move_ratio / (min_net_move * 2), 1.0)
    impulse_strength = (dir_candles_score + net_move_score) / 2
    
    return True, impulse_strength


def detect_liquidity_sweep(df: pd.DataFrame, zone_idx: int, zone_low: float, 
                           zone_high: float, is_bullish: bool,
                           check_bars: int = 3, 
                           wick_ratio: float = 0.6) -> Tuple[bool, int]:
    """
    Detect if there's a liquidity sweep (stop-hunt) at the zone.
    
    Args:
        df: DataFrame with OHLCV data
        zone_idx: Index where zone was created
        zone_low: Zone low price
        zone_high: Zone high price
        is_bullish: True for bullish zone
        check_bars: Number of bars to check after zone
        wick_ratio: Minimum wick ratio for sweep detection
        
    Returns:
        Tuple of (sweep_detected, sweep_bar_offset)
    """
    end_idx = min(zone_idx + check_bars + 1, len(df))
    
    for i in range(zone_idx + 1, end_idx):
        candle = df.iloc[i]
        candle_range = candle['high'] - candle['low']
        
        if candle_range == 0:
            continue
        
        if is_bullish:
            # Look for wick below zone followed by close above zone
            if candle['low'] < zone_low:
                lower_wick = min(candle['open'], candle['close']) - candle['low']
                if lower_wick / candle_range >= wick_ratio and candle['close'] > zone_low:
                    return True, i - zone_idx
        else:
            # Look for wick above zone followed by close below zone
            if candle['high'] > zone_high:
                upper_wick = candle['high'] - max(candle['open'], candle['close'])
                if upper_wick / candle_range >= wick_ratio and candle['close'] < zone_high:
                    return True, i - zone_idx
    
    return False, 0


def calculate_zone_score(body_size_ratio: float, impulse_strength: float,
                        touch_count: int, volume_spike: float,
                        has_liquidity_sweep: bool) -> float:
    """
    Calculate confidence score for a zone based on multiple factors.
    
    Args:
        body_size_ratio: Candle body size relative to ATR
        impulse_strength: Impulse confirmation strength (0-1)
        touch_count: Number of times zone was touched
        volume_spike: Volume relative to average
        has_liquidity_sweep: Whether liquidity sweep was detected
        
    Returns:
        Confidence score between 0 and 1
    """
    # Normalize body size score (cap at 2x ATR for max score)
    body_score = min(body_size_ratio / 2.0, 1.0)
    
    # Impulse strength is already 0-1
    impulse_score = impulse_strength
    
    # Touch score (more touches = higher confidence, up to MAX_TOUCHES)
    touch_score = min(touch_count / config.MAX_TOUCHES, 1.0)
    
    # Volume score (normalize to 0-1, cap at 3x average)
    volume_score = min((volume_spike - 1.0) / 2.0, 1.0) if volume_spike > 1.0 else 0.0
    
    # Liquidity sweep score
    sweep_score = 1.0 if has_liquidity_sweep else 0.0
    
    # Weighted composite score
    total_score = (
        config.SCORE_WEIGHT_BODY_SIZE * body_score +
        config.SCORE_WEIGHT_IMPULSE * impulse_score +
        config.SCORE_WEIGHT_TOUCHES * touch_score +
        config.SCORE_WEIGHT_VOLUME * volume_score +
        config.SCORE_WEIGHT_LIQUIDITY_SWEEP * sweep_score
    )
    
    return round(total_score, 3)


def check_zone_touches(df: pd.DataFrame, zone_idx: int, zone_low: float,
                      zone_high: float, is_bullish: bool, 
                      current_idx: int) -> int:
    """
    Count how many times price has touched the zone since creation.
    
    Args:
        df: DataFrame with OHLCV data
        zone_idx: Index where zone was created
        zone_low: Zone low price
        zone_high: Zone high price
        is_bullish: True for bullish zone
        current_idx: Current bar index
        
    Returns:
        Number of touches
    """
    touches = 0
    zone_range = zone_high - zone_low
    
    for i in range(zone_idx + 1, current_idx + 1):
        candle = df.iloc[i]
        
        # Check if candle intersects with zone
        if candle['low'] <= zone_high and candle['high'] >= zone_low:
            touches += 1
            
            # For bullish zone, check if price broke below
            if is_bullish and candle['close'] < zone_low - zone_range * 0.1:
                # Zone broken, stop counting
                break
            # For bearish zone, check if price broke above
            elif not is_bullish and candle['close'] > zone_high + zone_range * 0.1:
                # Zone broken, stop counting
                break
    
    return touches


def merge_overlapping_zones(zones: List[Dict]) -> List[Dict]:
    """
    Merge overlapping or adjacent zones into consolidated zones.
    
    Args:
        zones: List of zone dictionaries
        
    Returns:
        List of merged zones
    """
    if not zones:
        return []
    
    # Sort by index
    sorted_zones = sorted(zones, key=lambda x: x['index'])
    merged = []
    
    i = 0
    while i < len(sorted_zones):
        current = sorted_zones[i].copy()
        j = i + 1
        
        # Check for overlapping zones of same type
        while j < len(sorted_zones):
            next_zone = sorted_zones[j]
            
            if next_zone['type'] != current['type']:
                j += 1
                continue
            
            # Calculate overlap
            overlap_low = max(current['low'], next_zone['low'])
            overlap_high = min(current['high'], next_zone['high'])
            
            if overlap_high >= overlap_low:
                overlap_amount = overlap_high - overlap_low
                zone1_range = current['high'] - current['low']
                zone2_range = next_zone['high'] - next_zone['low']
                min_range = min(zone1_range, zone2_range)
                
                if min_range > 0 and overlap_amount / min_range >= config.ZONE_MERGE_THRESHOLD:
                    # Merge zones
                    current['low'] = min(current['low'], next_zone['low'])
                    current['high'] = max(current['high'], next_zone['high'])
                    current['score'] = max(current['score'], next_zone['score'])
                    current['touches'] = max(current.get('touches', 1), next_zone.get('touches', 1))
                    sorted_zones.pop(j)
                    continue
            
            j += 1
        
        merged.append(current)
        i += 1
    
    return merged


def detect_order_zones(df: pd.DataFrame,
                      atr_period: int = None,
                      atr_mult: float = None,
                      body_min_ratio: float = None,
                      wick_max_ratio: float = None,
                      lookahead: int = None,
                      min_dir_candles: int = None,
                      min_net_move: float = None,
                      touches_required: int = None,
                      expiry_bars: int = None,
                      min_volume_spike: float = None) -> List[Dict]:
    """
    Advanced order block detection with scoring and validation.
    
    This function implements a comprehensive order block detection algorithm with:
    - ATR-based candle filtering
    - Impulse confirmation
    - Multi-touch validation
    - Liquidity sweep detection
    - Confidence scoring
    - Zone expiry and merging
    
    Args:
        df: DataFrame with OHLCV data (columns: open, high, low, close, volume)
        atr_period: ATR calculation period (default from config)
        atr_mult: ATR multiplier (default from config)
        body_min_ratio: Minimum body size ratio (default from config)
        wick_max_ratio: Maximum wick ratio (default from config)
        lookahead: Lookahead bars for impulse (default from config)
        min_dir_candles: Minimum directional candles (default from config)
        min_net_move: Minimum net movement (default from config)
        touches_required: Minimum touches required (default from config)
        expiry_bars: Zone expiry period (default from config)
        min_volume_spike: Minimum volume spike (default from config)
        
    Returns:
        List of zone dictionaries with keys:
        - index: candle index
        - low: zone low price
        - high: zone high price
        - type: 'bullish' or 'bearish'
        - score: confidence score (0-1)
        - touches: number of touches
        - has_sweep: whether liquidity sweep detected
    """
    # Use config defaults if not specified
    atr_period = atr_period or config.ATR_PERIOD
    atr_mult = atr_mult or config.ATR_MULT
    body_min_ratio = body_min_ratio or config.BODY_MIN_RATIO
    wick_max_ratio = wick_max_ratio or config.WICK_MAX_RATIO
    lookahead = lookahead or config.DETECTION_LOOKAHEAD
    min_dir_candles = min_dir_candles or config.IMPULSE_MIN_DIR_CANDLES
    min_net_move = min_net_move or config.IMPULSE_MIN_NET_MOVE
    touches_required = touches_required or config.TOUCHES_REQUIRED
    expiry_bars = expiry_bars or config.ZONE_EXPIRY_BARS
    min_volume_spike = min_volume_spike or config.MIN_VOLUME_SPIKE_MULT
    
    zones = []
    
    if len(df) < atr_period + lookahead + 1:
        return zones
    
    # Calculate ATR
    atr = calculate_atr(df, atr_period)
    
    # Calculate average volume for spike detection
    avg_volume = df['volume'].rolling(window=20).mean()
    
    # Scan for candidate candles
    for i in range(atr_period, len(df) - lookahead):
        candle = df.iloc[i]
        atr_value = atr.iloc[i] * atr_mult
        
        if pd.isna(atr_value) or atr_value == 0:
            continue
        
        # Try bullish block (down candle before upward move)
        if check_candle_filters(candle, atr_value, is_bullish=True, 
                               body_min_ratio=body_min_ratio, 
                               wick_max_ratio=wick_max_ratio):
            confirmed, impulse_strength = check_impulse_confirmation(
                df, i, is_bullish=True, atr_value=atr_value,
                lookahead=lookahead, min_dir_candles=min_dir_candles,
                min_net_move=min_net_move
            )
            
            if confirmed:
                zone_low = candle['low']
                zone_high = candle['high']
                
                # Check for liquidity sweep
                has_sweep, _ = detect_liquidity_sweep(
                    df, i, zone_low, zone_high, is_bullish=True,
                    check_bars=config.LIQUIDITY_SWEEP_REVERSAL_BARS,
                    wick_ratio=config.LIQUIDITY_SWEEP_WICK_RATIO
                )
                
                # Count touches
                touches = check_zone_touches(df, i, zone_low, zone_high, 
                                            is_bullish=True, current_idx=len(df) - 1)
                
                # Calculate volume spike
                volume_ratio = candle['volume'] / avg_volume.iloc[i] if not pd.isna(avg_volume.iloc[i]) and avg_volume.iloc[i] > 0 else 1.0
                
                # Calculate body size ratio
                body_size = abs(candle['close'] - candle['open'])
                body_size_ratio = body_size / atr_value
                
                # Calculate score
                score = calculate_zone_score(
                    body_size_ratio, impulse_strength, touches,
                    volume_ratio, has_sweep
                )
                
                zones.append({
                    'index': i,
                    'low': zone_low,
                    'high': zone_high,
                    'type': 'bullish',
                    'score': score,
                    'touches': touches,
                    'has_sweep': has_sweep
                })
        
        # Try bearish block (up candle before downward move)
        if check_candle_filters(candle, atr_value, is_bullish=False,
                               body_min_ratio=body_min_ratio,
                               wick_max_ratio=wick_max_ratio):
            confirmed, impulse_strength = check_impulse_confirmation(
                df, i, is_bullish=False, atr_value=atr_value,
                lookahead=lookahead, min_dir_candles=min_dir_candles,
                min_net_move=min_net_move
            )
            
            if confirmed:
                zone_low = candle['low']
                zone_high = candle['high']
                
                # Check for liquidity sweep
                has_sweep, _ = detect_liquidity_sweep(
                    df, i, zone_low, zone_high, is_bullish=False,
                    check_bars=config.LIQUIDITY_SWEEP_REVERSAL_BARS,
                    wick_ratio=config.LIQUIDITY_SWEEP_WICK_RATIO
                )
                
                # Count touches
                touches = check_zone_touches(df, i, zone_low, zone_high,
                                            is_bullish=False, current_idx=len(df) - 1)
                
                # Calculate volume spike
                volume_ratio = candle['volume'] / avg_volume.iloc[i] if not pd.isna(avg_volume.iloc[i]) and avg_volume.iloc[i] > 0 else 1.0
                
                # Calculate body size ratio
                body_size = abs(candle['close'] - candle['open'])
                body_size_ratio = body_size / atr_value
                
                # Calculate score
                score = calculate_zone_score(
                    body_size_ratio, impulse_strength, touches,
                    volume_ratio, has_sweep
                )
                
                zones.append({
                    'index': i,
                    'low': zone_low,
                    'high': zone_high,
                    'type': 'bearish',
                    'score': score,
                    'touches': touches,
                    'has_sweep': has_sweep
                })
    
    # Merge overlapping zones
    zones = merge_overlapping_zones(zones)
    
    # Filter by minimum touches
    zones = [z for z in zones if z['touches'] >= touches_required]
    
    # Apply expiry filter
    current_idx = len(df) - 1
    zones = [z for z in zones if current_idx - z['index'] <= expiry_bars]
    
    return zones


def detect_order_blocks(df: pd.DataFrame, lookback: int = 20) -> Dict[str, List[Dict]]:
    """
    Backward-compatible wrapper for detect_order_zones.
    
    This function maintains the original API for existing code while using
    the new advanced detection algorithm internally.
    
    Args:
        df: DataFrame with OHLCV data
        lookback: Number of candles to look back (for compatibility, not used)
        
    Returns:
        Dict with 'bullish' and 'bearish' lists of order blocks
    """
    zones = detect_order_zones(df)
    
    # Convert to old format
    blocks = {
        'bullish': [],
        'bearish': []
    }
    
    for zone in zones:
        block = {
            'index': zone['index'],
            'low': zone['low'],
            'high': zone['high'],
            'type': zone['type'],
            'score': zone.get('score', 0.5),  # Include score in blocks
            'touches': zone.get('touches', 1),
            'has_sweep': zone.get('has_sweep', False)
        }
        
        if zone['type'] == 'bullish':
            blocks['bullish'].append(block)
        else:
            blocks['bearish'].append(block)
    
    return blocks
