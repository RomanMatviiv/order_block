#!/usr/bin/env python3
"""
State management module for persistent deduplication and configuration state.
Provides atomic file operations for safe state persistence.
"""
import json
import os
import tempfile
from typing import Dict, Any


def load_state(path: str = 'data/state.json') -> Dict[str, Any]:
    """
    Load state from a JSON file.
    
    Args:
        path: Path to the state file (default: 'data/state.json')
        
    Returns:
        Dictionary containing the state data. Returns empty dict if file doesn't exist
        or if there's an error loading it.
    """
    if not os.path.exists(path):
        return {}
    
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load state file from {path}: {e}")
        return {}


def save_state(path: str, state: Dict[str, Any]) -> None:
    """
    Save state to a JSON file using atomic write operation.
    
    Uses a temporary file and atomic rename to ensure the state file
    is never corrupted even if the process is interrupted.
    
    Args:
        path: Path to the state file
        state: Dictionary containing the state data to save
        
    Raises:
        IOError: If the state cannot be written
    """
    # Ensure the directory exists
    directory = os.path.dirname(path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
    
    # Write to a temporary file first
    # Use the same directory to ensure atomic rename works (same filesystem)
    fd, temp_path = tempfile.mkstemp(
        dir=directory if directory else None,
        prefix='.tmp_state_',
        suffix='.json'
    )
    
    try:
        # Write state to temporary file
        with os.fdopen(fd, 'w') as f:
            json.dump(state, f, indent=2)
        
        # Atomic rename (overwrites destination on Unix-like systems)
        os.replace(temp_path, path)
    except Exception as e:
        # Clean up temporary file if something went wrong
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise IOError(f"Failed to save state to {path}: {e}")
