#!/usr/bin/env python3
"""
Entry point for WebSocket-based live order block detection.
This script starts the WebSocket client and monitors for order blocks in real-time.
"""
import sys
import os

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src import live_ws

if __name__ == "__main__":
    live_ws.main()
