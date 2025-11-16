"""
Unit tests for WebSocket-based live detection module.
"""
import sys
import os
import pytest
import json
import tempfile
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src import live_ws
from src import config


class TestKlineBuffer:
    """Test KlineBuffer class."""
    
    def test_buffer_initialization(self):
        """Test buffer initialization."""
        buffer = live_ws.KlineBuffer(max_candles=100)
        assert buffer.max_candles == 100
        assert len(buffer.klines) == 0
        assert not buffer.is_ready()
    
    def test_add_kline(self):
        """Test adding klines to buffer."""
        buffer = live_ws.KlineBuffer(max_candles=5)
        
        kline_data = {
            't': 1609459200000,  # timestamp
            'o': '29000.00',
            'h': '29100.00',
            'l': '28900.00',
            'c': '29050.00',
            'v': '100.5'
        }
        
        buffer.add_kline(kline_data)
        assert len(buffer.klines) == 1
        assert buffer.klines[0]['open'] == 29000.0
        assert buffer.klines[0]['high'] == 29100.0
    
    def test_buffer_max_size(self):
        """Test that buffer respects max size."""
        buffer = live_ws.KlineBuffer(max_candles=3)
        
        # Add more than max_candles
        for i in range(5):
            kline_data = {
                't': 1609459200000 + i * 60000,
                'o': f'{29000 + i}.00',
                'h': f'{29100 + i}.00',
                'l': f'{28900 + i}.00',
                'c': f'{29050 + i}.00',
                'v': '100.0'
            }
            buffer.add_kline(kline_data)
        
        # Should only keep last 3
        assert len(buffer.klines) == 3
        assert buffer.klines[0]['open'] == 29002.0  # 3rd added
    
    def test_get_dataframe(self):
        """Test converting buffer to DataFrame."""
        buffer = live_ws.KlineBuffer()
        
        kline_data = {
            't': 1609459200000,
            'o': '29000.00',
            'h': '29100.00',
            'l': '28900.00',
            'c': '29050.00',
            'v': '100.5'
        }
        
        buffer.add_kline(kline_data)
        df = buffer.get_dataframe()
        
        assert len(df) == 1
        assert 'open' in df.columns
        assert 'high' in df.columns
        assert 'close' in df.columns
        assert df.iloc[0]['open'] == 29000.0
    
    def test_is_ready(self):
        """Test buffer readiness check."""
        buffer = live_ws.KlineBuffer()
        
        # Not ready with insufficient data
        assert not buffer.is_ready()
        
        # Add enough klines
        min_required = config.ATR_PERIOD + config.DETECTION_LOOKAHEAD + 1
        for i in range(min_required):
            kline_data = {
                't': 1609459200000 + i * 60000,
                'o': f'{29000 + i}.00',
                'h': f'{29100 + i}.00',
                'l': f'{28900 + i}.00',
                'c': f'{29050 + i}.00',
                'v': '100.0'
            }
            buffer.add_kline(kline_data)
        
        # Should be ready now
        assert buffer.is_ready()


class TestDeduplicationState:
    """Test DeduplicationState class."""
    
    def test_initialization(self):
        """Test state initialization."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            state_file = f.name
        
        try:
            state = live_ws.DeduplicationState(state_file)
            assert len(state.seen_blocks) == 0
            assert len(state.seen_set) == 0
        finally:
            if os.path.exists(state_file):
                os.remove(state_file)
    
    def test_mark_and_check_seen(self):
        """Test marking and checking seen blocks."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            state_file = f.name
        
        try:
            state = live_ws.DeduplicationState(state_file)
            
            block_key = "BTC/USDT|15m|100|bullish|0.75"
            
            # Initially not seen
            assert not state.is_seen(block_key)
            
            # Mark as seen
            state.mark_seen(block_key)
            
            # Should now be seen
            assert state.is_seen(block_key)
            assert len(state.seen_blocks) == 1
            assert len(state.seen_set) == 1
        finally:
            if os.path.exists(state_file):
                os.remove(state_file)
    
    def test_persistence(self):
        """Test state persistence across restarts."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            state_file = f.name
        
        try:
            # Create state and mark block as seen
            state1 = live_ws.DeduplicationState(state_file)
            block_key = "BTC/USDT|15m|100|bullish|0.75"
            state1.mark_seen(block_key)
            
            # Create new state instance (simulating restart)
            state2 = live_ws.DeduplicationState(state_file)
            
            # Should still be seen
            assert state2.is_seen(block_key)
            assert len(state2.seen_blocks) == 1
            assert len(state2.seen_set) == 1
        finally:
            if os.path.exists(state_file):
                os.remove(state_file)
    
    def test_prune_old_entries(self):
        """Test pruning old entries using FIFO."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            state_file = f.name
        
        try:
            state = live_ws.DeduplicationState(state_file)
            
            # Add many entries
            for i in range(150):
                state.mark_seen(f"block_{i}")
            
            assert len(state.seen_blocks) == 150
            assert len(state.seen_set) == 150
            
            # Remember the first and last blocks
            first_block = "block_0"
            last_block = "block_149"
            
            # Prune to 100 (should remove oldest 50)
            state.prune_old_entries(max_entries=100)
            
            # Should have exactly 100 entries
            assert len(state.seen_blocks) == 100
            assert len(state.seen_set) == 100
            
            # First 50 blocks should be removed (FIFO)
            assert not state.is_seen(first_block)
            assert not state.is_seen("block_49")
            
            # Last 100 blocks should remain
            assert state.is_seen("block_50")
            assert state.is_seen(last_block)
        finally:
            if os.path.exists(state_file):
                os.remove(state_file)


class TestBinanceWebSocketClient:
    """Test BinanceWebSocketClient class."""
    
    def test_initialization(self):
        """Test client initialization."""
        symbols = ["BTC/USDT", "ETH/USDT"]
        timeframes = ["15m", "30m"]
        
        client = live_ws.BinanceWebSocketClient(symbols, timeframes)
        
        assert len(client.buffers) == 4  # 2 symbols × 2 timeframes
        assert ("BTC/USDT", "15m") in client.buffers
        assert ("ETH/USDT", "30m") in client.buffers
        
        # Verify config values are being used
        for buffer in client.buffers.values():
            assert buffer.max_candles == config.WS_MAX_BARS
        
        assert client.dedup_state.state_file == config.STATE_FILE
    
    def test_get_stream_names(self):
        """Test stream name generation."""
        symbols = ["BTC/USDT", "ETH/USDT"]
        timeframes = ["15m", "30m"]
        
        client = live_ws.BinanceWebSocketClient(symbols, timeframes)
        streams = client.get_stream_names()
        
        assert len(streams) == 4
        assert "btcusdt@kline_15m" in streams
        assert "btcusdt@kline_30m" in streams
        assert "ethusdt@kline_15m" in streams
        assert "ethusdt@kline_30m" in streams
    
    def test_get_websocket_url(self):
        """Test WebSocket URL generation."""
        symbols = ["BTC/USDT"]
        timeframes = ["15m"]
        
        client = live_ws.BinanceWebSocketClient(symbols, timeframes)
        url = client.get_websocket_url()
        
        assert url.startswith("wss://stream.binance.com:9443/stream?streams=")
        assert "btcusdt@kline_15m" in url
    
    def test_parse_symbol_from_stream(self):
        """Test parsing symbol from stream name."""
        symbols = ["BTC/USDT", "ETH/USDT"]
        timeframes = ["15m"]
        
        client = live_ws.BinanceWebSocketClient(symbols, timeframes)
        
        # Test valid stream
        symbol, timeframe = client.parse_symbol_from_stream("btcusdt@kline_15m")
        assert symbol == "BTC/USDT"
        assert timeframe == "15m"
        
        # Test another valid stream
        symbol, timeframe = client.parse_symbol_from_stream("ethusdt@kline_30m")
        assert symbol == "ETH/USDT"
        assert timeframe == "30m"
    
    def test_parse_symbol_invalid_stream(self):
        """Test parsing invalid stream name."""
        symbols = ["BTC/USDT"]
        timeframes = ["15m"]
        
        client = live_ws.BinanceWebSocketClient(symbols, timeframes)
        
        # Should raise error for invalid stream
        with pytest.raises(ValueError):
            client.parse_symbol_from_stream("invalid_stream")
    
    @pytest.mark.asyncio
    @patch('src.live_ws.detection.detect_order_blocks')
    @patch('src.live_ws.notifier.send_telegram')
    async def test_process_kline_closed(self, mock_send_telegram, mock_detect):
        """Test processing closed kline."""
        symbols = ["BTC/USDT"]
        timeframes = ["15m"]
        
        client = live_ws.BinanceWebSocketClient(symbols, timeframes)
        
        # Mock detection to return no blocks
        mock_detect.return_value = {'bullish': [], 'bearish': []}
        
        # Create a closed kline message
        message = {
            'stream': 'btcusdt@kline_15m',
            'data': {
                'k': {
                    't': 1609459200000,
                    'o': '29000.00',
                    'h': '29100.00',
                    'l': '28900.00',
                    'c': '29050.00',
                    'v': '100.5',
                    'x': True  # Closed kline
                }
            }
        }
        
        await client.process_kline(message)
        
        # Verify kline was added to buffer
        buffer = client.buffers[("BTC/USDT", "15m")]
        assert len(buffer.klines) == 1
    
    @pytest.mark.asyncio
    @patch('src.live_ws.detection.detect_order_blocks')
    @patch('src.live_ws.notifier.send_telegram')
    async def test_process_kline_not_closed(self, mock_send_telegram, mock_detect):
        """Test that unclosed klines are ignored."""
        symbols = ["BTC/USDT"]
        timeframes = ["15m"]
        
        client = live_ws.BinanceWebSocketClient(symbols, timeframes)
        
        # Create an unclosed kline message
        message = {
            'stream': 'btcusdt@kline_15m',
            'data': {
                'k': {
                    't': 1609459200000,
                    'o': '29000.00',
                    'h': '29100.00',
                    'l': '28900.00',
                    'c': '29050.00',
                    'v': '100.5',
                    'x': False  # Not closed
                }
            }
        }
        
        await client.process_kline(message)
        
        # Verify kline was NOT added to buffer
        buffer = client.buffers[("BTC/USDT", "15m")]
        assert len(buffer.klines) == 0
        
        # Detection should not have been called
        mock_detect.assert_not_called()
    
    @pytest.mark.asyncio
    @patch('src.live_ws.detection.detect_order_blocks')
    @patch('src.live_ws.notifier.send_telegram')
    @patch('src.live_ws.notifier.format_block_message')
    async def test_score_filtering(self, mock_format, mock_send_telegram, mock_detect):
        """Test that blocks below score threshold are filtered."""
        symbols = ["BTC/USDT"]
        timeframes = ["15m"]
        
        client = live_ws.BinanceWebSocketClient(symbols, timeframes)
        
        # Fill buffer with enough data
        for i in range(30):
            kline_data = {
                't': 1609459200000 + i * 60000,
                'o': f'{29000 + i}.00',
                'h': f'{29100 + i}.00',
                'l': f'{28900 + i}.00',
                'c': f'{29050 + i}.00',
                'v': '100.0',
                'x': True
            }
            message = {
                'stream': 'btcusdt@kline_15m',
                'data': {'k': kline_data}
            }
            client.buffers[("BTC/USDT", "15m")].add_kline(kline_data)
        
        # Mock detection to return blocks with different scores
        mock_detect.return_value = {
            'bullish': [
                {'index': 100, 'type': 'bullish', 'score': 0.10},  # Below threshold
                {'index': 101, 'type': 'bullish', 'score': 0.25},  # At threshold
                {'index': 102, 'type': 'bullish', 'score': 0.75},  # Above threshold
            ],
            'bearish': [
                {'index': 103, 'type': 'bearish', 'score': 0.15},  # Below threshold
            ]
        }
        mock_format.return_value = "Test message"
        
        # Process a closed kline
        message = {
            'stream': 'btcusdt@kline_15m',
            'data': {
                'k': {
                    't': 1609459200000,
                    'o': '29000.00',
                    'h': '29100.00',
                    'l': '28900.00',
                    'c': '29050.00',
                    'v': '100.5',
                    'x': True
                }
            }
        }
        
        await client.process_kline(message)
        
        # Only blocks with score >= WS_NOTIFY_SCORE_MIN should be notified
        # That's 2 blocks (0.25 and 0.75)
        assert mock_send_telegram.call_count == 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
