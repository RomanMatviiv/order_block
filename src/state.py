#!/usr/bin/env python3
"""
State persistence module for order block detection.
Provides generic helper functions for loading and saving state to JSON files.
"""
import json
import os
import tempfile
from typing import Any, Dict


def load_state(path: str) -> Dict[str, Any]:
    """
    Load state from a JSON file.
    
    Args:
        path: Path to the state file
        
    Returns:
        Dictionary containing the state, or empty dict if file doesn't exist
        
    Raises:
        json.JSONDecodeError: If the file contains invalid JSON
        IOError: If there's an error reading the file
    """
    if not os.path.exists(path):
        return {}
    
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        # Return empty dict if file is corrupted
        return {}


def save_state(path: str, state: Dict[str, Any]) -> None:
    """
    Save state to a JSON file with atomic write operation.
    Creates parent directories if they don't exist.
    
    Args:
        path: Path to the state file
        state: Dictionary to save as JSON
        
    Raises:
        IOError: If there's an error writing the file
    """
    # Create parent directory if it doesn't exist
    parent_dir = os.path.dirname(path)
    if parent_dir and not os.path.exists(parent_dir):
        os.makedirs(parent_dir, exist_ok=True)
    
    # Atomic write: write to temp file first, then rename
    # This prevents corruption if the process is interrupted
    dir_name = os.path.dirname(path) or '.'
    file_name = os.path.basename(path)
    
    # Create a temporary file in the same directory as the target
    # This ensures the rename operation is atomic (same filesystem)
    with tempfile.NamedTemporaryFile(
        mode='w',
        dir=dir_name,
        prefix=f'.{file_name}.',
        suffix='.tmp',
        delete=False
    ) as tmp_file:
        tmp_path = tmp_file.name
        json.dump(state, tmp_file, indent=2)
    
    # Atomic rename: replaces the old file if it exists
    # This is atomic on POSIX systems
    os.replace(tmp_path, path)
