"""
Unit tests for WebSocket-based live detection module.
"""
import sys
import os
import pytest
import asyncio
import json
import tempfile
from pathlib import Path
import pandas as pd

# Add parent directory to path to import src modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src import live_ws


class TestKlineBuffer:
    """Test KlineBuffer functionality."""
    
    @pytest.mark.asyncio
    async def test_add_candle(self):
        """Test adding a candle to the buffer."""
        buffer = live_ws.KlineBuffer(max_candles=100)
        
        kline = {
            't': 1609459200000,  # 2021-01-01 00:00:00
            'o': '29000.00',
            'h': '29100.00',
            'l': '28900.00',
            'c': '29050.00',
            'v': '100.5'
        }
        
        df = await buffer.add_candle('BTCUSDT', '15m', kline)
        
        assert len(df) == 1
        assert df.iloc[0]['open'] == 29000.00
        assert df.iloc[0]['close'] == 29050.00
    
    @pytest.mark.asyncio
    async def test_buffer_limit(self):
        """Test that buffer respects max_candles limit."""
        buffer = live_ws.KlineBuffer(max_candles=5)
        
        # Add more candles than the limit
        for i in range(10):
            kline = {
                't': 1609459200000 + i * 900000,  # 15-minute intervals
                'o': f'{29000 + i}',
                'h': f'{29100 + i}',
                'l': f'{28900 + i}',
                'c': f'{29050 + i}',
                'v': '100'
            }
            df = await buffer.add_candle('BTCUSDT', '15m', kline)
        
        # Should only keep last 5
        assert len(df) == 5
        # Last candle should be the 10th one added
        assert df.iloc[-1]['open'] == 29009.0
    
    @pytest.mark.asyncio
    async def test_multiple_symbols(self):
        """Test buffer handles multiple symbols independently."""
        buffer = live_ws.KlineBuffer(max_candles=100)
        
        kline1 = {
            't': 1609459200000,
            'o': '29000.00',
            'h': '29100.00',
            'l': '28900.00',
            'c': '29050.00',
            'v': '100.5'
        }
        
        kline2 = {
            't': 1609459200000,
            'o': '1500.00',
            'h': '1510.00',
            'l': '1490.00',
            'c': '1505.00',
            'v': '200.0'
        }
        
        df1 = await buffer.add_candle('BTCUSDT', '15m', kline1)
        df2 = await buffer.add_candle('ETHUSDT', '15m', kline2)
        
        assert len(df1) == 1
        assert len(df2) == 1
        assert df1.iloc[0]['open'] == 29000.00
        assert df2.iloc[0]['open'] == 1500.00


class TestDeduplicationManager:
    """Test DeduplicationManager functionality."""
    
    @pytest.mark.asyncio
    async def test_mark_and_check_seen(self):
        """Test marking and checking seen blocks."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            state_file = f.name
        
        try:
            manager = live_ws.DeduplicationManager(state_file)
            
            block_key = "BTCUSDT_15m_100_bullish_0.75"
            
            # Should not be seen initially
            assert not await manager.is_seen(block_key)
            
            # Mark as seen
            await manager.mark_seen(block_key)
            
            # Should now be seen
            assert await manager.is_seen(block_key)
            
        finally:
            if os.path.exists(state_file):
                os.remove(state_file)
    
    @pytest.mark.asyncio
    async def test_persistence(self):
        """Test that state persists across manager instances."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            state_file = f.name
        
        try:
            # Create first manager and mark a block as seen
            manager1 = live_ws.DeduplicationManager(state_file)
            block_key = "BTCUSDT_15m_100_bullish_0.75"
            await manager1.mark_seen(block_key)
            
            # Create new manager (simulating restart)
            manager2 = live_ws.DeduplicationManager(state_file)
            
            # Should still be seen
            assert await manager2.is_seen(block_key)
            
        finally:
            if os.path.exists(state_file):
                os.remove(state_file)
    
    @pytest.mark.asyncio
    async def test_load_nonexistent_file(self):
        """Test loading when state file doesn't exist."""
        state_file = "/tmp/nonexistent_state_file_12345.json"
        
        if os.path.exists(state_file):
            os.remove(state_file)
        
        manager = live_ws.DeduplicationManager(state_file)
        
        # Should start with empty set
        assert len(manager.seen_blocks) == 0
        
        # Cleanup
        if os.path.exists(state_file):
            os.remove(state_file)


class TestBinanceWebSocketClient:
    """Test BinanceWebSocketClient functionality."""
    
    def test_get_stream_names(self):
        """Test stream name generation."""
        client = live_ws.BinanceWebSocketClient(
            symbols=['BTCUSDT', 'ETHUSDT'],
            timeframes=['15m', '30m']
        )
        
        streams = client._get_stream_names()
        
        assert len(streams) == 4
        assert 'btcusdt@kline_15m' in streams
        assert 'btcusdt@kline_30m' in streams
        assert 'ethusdt@kline_15m' in streams
        assert 'ethusdt@kline_30m' in streams
    
    def test_get_ws_url(self):
        """Test WebSocket URL construction."""
        client = live_ws.BinanceWebSocketClient(
            symbols=['BTCUSDT'],
            timeframes=['15m']
        )
        
        url = client._get_ws_url()
        
        assert url.startswith('wss://stream.binance.com:9443/ws/')
        assert 'btcusdt@kline_15m' in url
    
    def test_format_symbol(self):
        """Test symbol formatting."""
        client = live_ws.BinanceWebSocketClient(
            symbols=['BTCUSDT'],
            timeframes=['15m']
        )
        
        assert client._format_symbol('BTCUSDT') == 'BTC/USDT'
        assert client._format_symbol('ETHUSDT') == 'ETH/USDT'
        assert client._format_symbol('BNBBUSD') == 'BNB/BUSD'
        assert client._format_symbol('ADABTC') == 'ADA/BTC'
        assert client._format_symbol('XRPETH') == 'XRP/ETH'


class TestKlineEventProcessing:
    """Test kline event processing logic."""
    
    @pytest.mark.asyncio
    async def test_process_closed_kline(self):
        """Test processing of closed kline event."""
        client = live_ws.BinanceWebSocketClient(
            symbols=['BTCUSDT'],
            timeframes=['15m']
        )
        
        # Create a closed kline event
        event = {
            'e': 'kline',
            'k': {
                's': 'BTCUSDT',
                'i': '15m',
                't': 1609459200000,
                'o': '29000.00',
                'h': '29100.00',
                'l': '28900.00',
                'c': '29050.00',
                'v': '100.5',
                'x': True  # Closed
            }
        }
        
        # Process the event (should not raise exception)
        await client._process_kline_event(event)
        
        # Check that candle was added to buffer
        key = 'BTCUSDT_15m'
        assert key in client.kline_buffer.buffers
        assert len(client.kline_buffer.buffers[key]) == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
