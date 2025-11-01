"""
Unit tests for state management module.
"""
import sys
import os
import pytest
import json
import tempfile

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src import state


class TestLoadState:
    """Test load_state function."""
    
    def test_load_nonexistent_file(self):
        """Test loading from a nonexistent file returns empty dict."""
        with tempfile.NamedTemporaryFile(mode='w', delete=True, suffix='.json') as f:
            path = f.name
        # File is now deleted
        result = state.load_state(path)
        assert result == {}
    
    def test_load_valid_file(self):
        """Test loading from a valid JSON file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            test_data = {'key1': 'value1', 'key2': [1, 2, 3]}
            json.dump(test_data, f)
            path = f.name
        
        try:
            result = state.load_state(path)
            assert result == test_data
        finally:
            os.remove(path)
    
    def test_load_invalid_json(self):
        """Test loading from an invalid JSON file returns empty dict."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            f.write("invalid json content {]")
            path = f.name
        
        try:
            result = state.load_state(path)
            assert result == {}
        finally:
            os.remove(path)


class TestSaveState:
    """Test save_state function."""
    
    def test_save_to_new_file(self):
        """Test saving state to a new file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=True, suffix='.json') as f:
            path = f.name
        
        # File is now deleted, will be created by save_state
        test_data = {'key1': 'value1', 'key2': [1, 2, 3]}
        
        try:
            state.save_state(path, test_data)
            
            # Verify file was created and contains correct data
            assert os.path.exists(path)
            with open(path, 'r') as f:
                loaded_data = json.load(f)
            assert loaded_data == test_data
        finally:
            if os.path.exists(path):
                os.remove(path)
    
    def test_save_overwrites_existing_file(self):
        """Test that save_state overwrites existing file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            old_data = {'old': 'data'}
            json.dump(old_data, f)
            path = f.name
        
        try:
            # Save new data
            new_data = {'new': 'data'}
            state.save_state(path, new_data)
            
            # Verify file contains new data
            with open(path, 'r') as f:
                loaded_data = json.load(f)
            assert loaded_data == new_data
            assert loaded_data != old_data
        finally:
            os.remove(path)
    
    def test_save_creates_directory(self):
        """Test that save_state creates parent directories if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a path with nested directories that don't exist
            path = os.path.join(tmpdir, 'subdir', 'nested', 'state.json')
            
            test_data = {'test': 'data'}
            state.save_state(path, test_data)
            
            # Verify file was created
            assert os.path.exists(path)
            with open(path, 'r') as f:
                loaded_data = json.load(f)
            assert loaded_data == test_data
    
    def test_atomic_write(self):
        """Test that save_state uses atomic write."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            path = f.name
        
        try:
            # Save some data
            state.save_state(path, {'test': 'data'})
            
            # Verify no temp files are left behind
            directory = os.path.dirname(path)
            temp_files = [f for f in os.listdir(directory or '.') 
                         if f.startswith('.tmp_state_')]
            assert len(temp_files) == 0
        finally:
            if os.path.exists(path):
                os.remove(path)
    
    def test_save_and_load_roundtrip(self):
        """Test that data can be saved and loaded correctly."""
        with tempfile.NamedTemporaryFile(mode='w', delete=True, suffix='.json') as f:
            path = f.name
        
        try:
            # Save data
            original_data = {
                'seen_blocks': ['block1', 'block2', 'block3'],
                'metadata': {'version': 1}
            }
            state.save_state(path, original_data)
            
            # Load data
            loaded_data = state.load_state(path)
            
            # Verify data matches
            assert loaded_data == original_data
        finally:
            if os.path.exists(path):
                os.remove(path)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
