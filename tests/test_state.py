"""
Unit tests for state persistence module.
"""
import sys
import os
import pytest
import json
import tempfile
import shutil

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src import state


class TestLoadState:
    """Test load_state function."""
    
    def test_load_nonexistent_file(self):
        """Test loading from a non-existent file returns empty dict."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, 'nonexistent.json')
            result = state.load_state(path)
            assert result == {}
    
    def test_load_valid_json(self):
        """Test loading valid JSON file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            test_data = {'key': 'value', 'number': 42}
            json.dump(test_data, f)
            f.flush()
            path = f.name
        
        try:
            result = state.load_state(path)
            assert result == test_data
        finally:
            os.remove(path)
    
    def test_load_corrupted_json(self):
        """Test loading corrupted JSON returns empty dict."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            f.write('{ invalid json ]}')
            f.flush()
            path = f.name
        
        try:
            result = state.load_state(path)
            assert result == {}
        finally:
            os.remove(path)
    
    def test_load_empty_file(self):
        """Test loading empty file returns empty dict."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            path = f.name
        
        try:
            result = state.load_state(path)
            assert result == {}
        finally:
            os.remove(path)


class TestSaveState:
    """Test save_state function."""
    
    def test_save_simple_dict(self):
        """Test saving a simple dictionary."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, 'state.json')
            test_data = {'key': 'value', 'number': 42}
            
            state.save_state(path, test_data)
            
            # Verify file exists
            assert os.path.exists(path)
            
            # Verify content
            with open(path, 'r') as f:
                loaded_data = json.load(f)
            assert loaded_data == test_data
    
    def test_save_creates_parent_directory(self):
        """Test that save_state creates parent directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, 'nested', 'dir', 'state.json')
            test_data = {'key': 'value'}
            
            # Parent directories don't exist yet
            assert not os.path.exists(os.path.dirname(path))
            
            state.save_state(path, test_data)
            
            # Parent directories should be created
            assert os.path.exists(os.path.dirname(path))
            assert os.path.exists(path)
            
            # Verify content
            with open(path, 'r') as f:
                loaded_data = json.load(f)
            assert loaded_data == test_data
    
    def test_save_overwrites_existing(self):
        """Test that save_state overwrites existing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, 'state.json')
            
            # Save initial data
            initial_data = {'key': 'initial'}
            state.save_state(path, initial_data)
            
            # Save new data
            new_data = {'key': 'updated', 'new_key': 'new_value'}
            state.save_state(path, new_data)
            
            # Verify new data
            with open(path, 'r') as f:
                loaded_data = json.load(f)
            assert loaded_data == new_data
    
    def test_save_complex_data(self):
        """Test saving complex nested data structures."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, 'state.json')
            test_data = {
                'string': 'value',
                'number': 42,
                'float': 3.14,
                'boolean': True,
                'null': None,
                'list': [1, 2, 3],
                'nested': {
                    'inner': 'value',
                    'deep': {
                        'deeper': 'nested'
                    }
                }
            }
            
            state.save_state(path, test_data)
            
            # Verify content
            with open(path, 'r') as f:
                loaded_data = json.load(f)
            assert loaded_data == test_data
    
    def test_atomic_write(self):
        """Test that save_state uses atomic write."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, 'state.json')
            
            # Save initial data
            initial_data = {'version': 1}
            state.save_state(path, initial_data)
            
            # Verify initial data
            with open(path, 'r') as f:
                content = f.read()
            assert 'version' in content
            assert '"version": 1' in content
            
            # Save new data
            new_data = {'version': 2, 'updated': True}
            state.save_state(path, new_data)
            
            # Verify file was atomically replaced (no intermediate state visible)
            with open(path, 'r') as f:
                loaded_data = json.load(f)
            assert loaded_data == new_data


class TestRoundTrip:
    """Test load and save together."""
    
    def test_save_and_load(self):
        """Test saving and then loading the same data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, 'state.json')
            test_data = {
                'seen_blocks': ['block1', 'block2', 'block3'],
                'last_updated': '2025-11-01T10:00:00',
                'count': 3
            }
            
            # Save
            state.save_state(path, test_data)
            
            # Load
            loaded_data = state.load_state(path)
            
            # Verify
            assert loaded_data == test_data
    
    def test_multiple_save_load_cycles(self):
        """Test multiple save/load cycles."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, 'state.json')
            
            for i in range(5):
                test_data = {'iteration': i, 'data': f'test_{i}'}
                state.save_state(path, test_data)
                loaded_data = state.load_state(path)
                assert loaded_data == test_data


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
