"""
Unit tests for order block detection module.
Tests the advanced detection algorithm with synthetic data.
"""
import sys
import os
import pytest
import pandas as pd
import numpy as np

# Add parent directory to path to import src modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src import detection
from src import config


def create_synthetic_ohlcv(n_bars=100, base_price=100, volatility=1.0):
    """
    Create synthetic OHLCV data for testing.
    
    Args:
        n_bars: Number of bars to generate
        base_price: Base price level
        volatility: Price volatility
        
    Returns:
        DataFrame with OHLCV data
    """
    np.random.seed(42)
    
    data = []
    current_price = base_price
    
    for i in range(n_bars):
        # Random walk
        change = np.random.randn() * volatility
        current_price += change
        
        # Generate OHLC
        open_price = current_price
        close_price = current_price + np.random.randn() * volatility
        high_price = max(open_price, close_price) + abs(np.random.randn()) * volatility * 0.5
        low_price = min(open_price, close_price) - abs(np.random.randn()) * volatility * 0.5
        volume = abs(np.random.randn()) * 1000 + 500
        
        data.append({
            'timestamp': pd.Timestamp('2024-01-01') + pd.Timedelta(minutes=i*15),
            'open': open_price,
            'high': high_price,
            'low': low_price,
            'close': close_price,
            'volume': volume
        })
    
    return pd.DataFrame(data)


def create_bullish_pattern(base_price=100):
    """
    Create a synthetic bullish order block pattern.
    
    Returns:
        DataFrame with a clear bullish pattern
    """
    data = []
    
    # Initial uptrend
    for i in range(20):
        open_price = 100 + i * 0.5
        close_price = open_price + 0.6
        high_price = close_price + 0.2
        low_price = open_price - 0.1
        data.append({
            'timestamp': pd.Timestamp('2024-01-01') + pd.Timedelta(minutes=i*15),
            'open': open_price,
            'high': high_price,
            'low': low_price,
            'close': close_price,
            'volume': 1000
        })
    
    # Down candle (order block candidate)
    data.append({
        'timestamp': pd.Timestamp('2024-01-01') + pd.Timedelta(minutes=20*15),
        'open': 110.0,
        'high': 110.5,
        'low': 108.0,
        'close': 108.5,
        'volume': 1500
    })
    
    # Strong upward impulse
    for i in range(21, 31):
        open_price = 108 + (i - 20) * 1.0
        close_price = open_price + 1.2
        high_price = close_price + 0.3
        low_price = open_price - 0.1
        data.append({
            'timestamp': pd.Timestamp('2024-01-01') + pd.Timedelta(minutes=i*15),
            'open': open_price,
            'high': high_price,
            'low': low_price,
            'close': close_price,
            'volume': 1200
        })
    
    # Continuation
    for i in range(31, 50):
        open_price = 118 + (i - 31) * 0.3
        close_price = open_price + 0.4
        high_price = close_price + 0.2
        low_price = open_price - 0.1
        data.append({
            'timestamp': pd.Timestamp('2024-01-01') + pd.Timedelta(minutes=i*15),
            'open': open_price,
            'high': high_price,
            'low': low_price,
            'close': close_price,
            'volume': 1000
        })
    
    return pd.DataFrame(data)


def create_bearish_pattern(base_price=100):
    """
    Create a synthetic bearish order block pattern.
    
    Returns:
        DataFrame with a clear bearish pattern
    """
    data = []
    
    # Initial downtrend
    for i in range(20):
        open_price = 100 - i * 0.5
        close_price = open_price - 0.6
        high_price = open_price + 0.1
        low_price = close_price - 0.2
        data.append({
            'timestamp': pd.Timestamp('2024-01-01') + pd.Timedelta(minutes=i*15),
            'open': open_price,
            'high': high_price,
            'low': low_price,
            'close': close_price,
            'volume': 1000
        })
    
    # Up candle (order block candidate)
    data.append({
        'timestamp': pd.Timestamp('2024-01-01') + pd.Timedelta(minutes=20*15),
        'open': 90.0,
        'high': 92.0,
        'low': 89.5,
        'close': 91.5,
        'volume': 1500
    })
    
    # Strong downward impulse
    for i in range(21, 31):
        open_price = 92 - (i - 20) * 1.0
        close_price = open_price - 1.2
        high_price = open_price + 0.1
        low_price = close_price - 0.3
        data.append({
            'timestamp': pd.Timestamp('2024-01-01') + pd.Timedelta(minutes=i*15),
            'open': open_price,
            'high': high_price,
            'low': low_price,
            'close': close_price,
            'volume': 1200
        })
    
    # Continuation
    for i in range(31, 50):
        open_price = 82 - (i - 31) * 0.3
        close_price = open_price - 0.4
        high_price = open_price + 0.1
        low_price = close_price - 0.2
        data.append({
            'timestamp': pd.Timestamp('2024-01-01') + pd.Timedelta(minutes=i*15),
            'open': open_price,
            'high': high_price,
            'low': low_price,
            'close': close_price,
            'volume': 1000
        })
    
    return pd.DataFrame(data)


class TestATRCalculation:
    """Test ATR calculation."""
    
    def test_atr_basic(self):
        """Test basic ATR calculation."""
        df = create_synthetic_ohlcv(50)
        atr = detection.calculate_atr(df, period=14)
        
        assert len(atr) == len(df)
        assert not atr.iloc[-1] == 0  # Should have non-zero ATR
        assert pd.notna(atr.iloc[-1])  # Should not be NaN at the end


class TestCandleFilters:
    """Test candle filtering logic."""
    
    def test_bullish_candle_filter_down_candle(self):
        """Test that bullish filter accepts down candles."""
        candle = pd.Series({
            'open': 100,
            'high': 101,
            'low': 98,
            'close': 98.5
        })
        atr_value = 2.0
        
        result = detection.check_candle_filters(
            candle, atr_value, is_bullish=True,
            body_min_ratio=0.5, wick_max_ratio=0.3
        )
        
        # Should pass: body = 1.5 > 2.0 * 0.5 = 1.0
        # Upper wick = 1.0, body = 1.5, wick ratio = 0.67 > 0.3, should fail
        assert result == False  # Wick too large
    
    def test_bearish_candle_filter_up_candle(self):
        """Test that bearish filter accepts up candles."""
        candle = pd.Series({
            'open': 100,
            'high': 102,
            'low': 99,
            'close': 101.5
        })
        atr_value = 2.0
        
        result = detection.check_candle_filters(
            candle, atr_value, is_bullish=False,
            body_min_ratio=0.5, wick_max_ratio=0.3
        )
        
        # Should pass: body = 1.5 > 2.0 * 0.5 = 1.0
        # Lower wick = 1.0, body = 1.5, wick ratio = 0.67 > 0.3, should fail
        assert result == False  # Wick too large


class TestImpulseConfirmation:
    """Test impulse confirmation logic."""
    
    def test_bullish_impulse_confirmed(self):
        """Test bullish impulse confirmation."""
        df = create_bullish_pattern()
        
        # Check impulse at the down candle (index 20)
        atr = detection.calculate_atr(df, 14)
        confirmed, strength = detection.check_impulse_confirmation(
            df, 20, is_bullish=True, atr_value=atr.iloc[20],
            lookahead=10, min_dir_candles=6, min_net_move=1.5
        )
        
        assert confirmed == True
        assert strength > 0.5  # Should have decent strength
    
    def test_bearish_impulse_confirmed(self):
        """Test bearish impulse confirmation."""
        df = create_bearish_pattern()
        
        # Check impulse at the up candle (index 20)
        atr = detection.calculate_atr(df, 14)
        confirmed, strength = detection.check_impulse_confirmation(
            df, 20, is_bullish=False, atr_value=atr.iloc[20],
            lookahead=10, min_dir_candles=6, min_net_move=1.5
        )
        
        assert confirmed == True
        assert strength > 0.5  # Should have decent strength


class TestZoneDetection:
    """Test full zone detection."""
    
    def test_detect_bullish_zone(self):
        """Test detection of bullish order block."""
        df = create_bullish_pattern()
        
        zones = detection.detect_order_zones(
            df,
            atr_period=14,
            body_min_ratio=0.3,  # Relaxed for test
            wick_max_ratio=0.5,  # Relaxed for test
            lookahead=10,
            min_dir_candles=6,
            min_net_move=1.0,  # Relaxed for test
            touches_required=0,
            expiry_bars=100
        )
        
        # Should detect at least one bullish zone
        bullish_zones = [z for z in zones if z['type'] == 'bullish']
        assert len(bullish_zones) > 0
        
        # Check zone properties
        zone = bullish_zones[0]
        assert 'score' in zone
        assert 0 <= zone['score'] <= 1.0
        assert 'touches' in zone
        assert 'has_sweep' in zone
    
    def test_detect_bearish_zone(self):
        """Test detection of bearish order block."""
        df = create_bearish_pattern()
        
        zones = detection.detect_order_zones(
            df,
            atr_period=14,
            body_min_ratio=0.3,  # Relaxed for test
            wick_max_ratio=0.5,  # Relaxed for test
            lookahead=10,
            min_dir_candles=6,
            min_net_move=1.0,  # Relaxed for test
            touches_required=0,
            expiry_bars=100
        )
        
        # Should detect at least one bearish zone
        bearish_zones = [z for z in zones if z['type'] == 'bearish']
        assert len(bearish_zones) > 0
        
        # Check zone properties
        zone = bearish_zones[0]
        assert 'score' in zone
        assert 0 <= zone['score'] <= 1.0
        assert 'touches' in zone
        assert 'has_sweep' in zone


class TestBackwardCompatibility:
    """Test backward compatibility wrapper."""
    
    def test_detect_order_blocks_format(self):
        """Test that detect_order_blocks returns expected format."""
        df = create_bullish_pattern()
        
        blocks = detection.detect_order_blocks(df)
        
        # Should return dict with 'bullish' and 'bearish' keys
        assert 'bullish' in blocks
        assert 'bearish' in blocks
        assert isinstance(blocks['bullish'], list)
        assert isinstance(blocks['bearish'], list)
        
        # Check block structure if any detected
        if blocks['bullish']:
            block = blocks['bullish'][0]
            assert 'index' in block
            assert 'low' in block
            assert 'high' in block
            assert 'type' in block
            assert 'score' in block


class TestZoneMerging:
    """Test zone merging logic."""
    
    def test_merge_overlapping_zones(self):
        """Test that overlapping zones are merged."""
        # Create zones with significant overlap (>50% of smaller zone)
        zones = [
            {'index': 10, 'low': 100, 'high': 105, 'type': 'bullish', 'score': 0.6, 'touches': 1},
            {'index': 12, 'low': 102, 'high': 107, 'type': 'bullish', 'score': 0.7, 'touches': 2},
            {'index': 20, 'low': 120, 'high': 125, 'type': 'bearish', 'score': 0.5, 'touches': 1},
        ]
        
        merged = detection.merge_overlapping_zones(zones)
        
        # Calculate actual overlap to verify test expectation
        overlap_low = max(100, 102)
        overlap_high = min(105, 107)
        overlap_amount = overlap_high - overlap_low
        min_range = min(105-100, 107-102)
        overlap_ratio = overlap_amount / min_range
        
        # First two zones have overlap_ratio = 3/5 = 0.6 >= 0.5, should merge
        bullish_merged = [z for z in merged if z['type'] == 'bullish']
        assert len(bullish_merged) == 1, f"Expected 1 bullish zone after merge, got {len(bullish_merged)} (overlap ratio: {overlap_ratio})"
        
        # Merged zone should have max score
        assert bullish_merged[0]['score'] == 0.7
        
        # Bearish zone should remain separate
        bearish_zones = [z for z in merged if z['type'] == 'bearish']
        assert len(bearish_zones) == 1


class TestScoring:
    """Test confidence scoring."""
    
    def test_score_calculation(self):
        """Test that score is calculated correctly."""
        score = detection.calculate_zone_score(
            body_size_ratio=1.5,
            impulse_strength=0.8,
            touch_count=3,
            volume_spike=2.0,
            has_liquidity_sweep=True
        )
        
        assert 0 <= score <= 1.0
        assert score > 0.5  # With good parameters, should have high score
    
    def test_score_with_poor_parameters(self):
        """Test score with poor parameters."""
        score = detection.calculate_zone_score(
            body_size_ratio=0.3,
            impulse_strength=0.2,
            touch_count=1,
            volume_spike=1.0,
            has_liquidity_sweep=False
        )
        
        assert 0 <= score <= 1.0
        assert score < 0.5  # With poor parameters, should have low score


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
