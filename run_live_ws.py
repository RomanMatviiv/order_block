#!/usr/bin/env python3
"""
Entry point for WebSocket-based live order block detection.
This script starts the WebSocket client and monitors for order blocks in real-time.
"""
import sys
import os
import argparse

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src import live_ws

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="WebSocket-based live order block detection with historical preloading"
    )
    parser.add_argument(
        '--send-historical',
        action='store_true',
        help='Send Telegram notifications for historical blocks found on startup. '
             'If not set, historical blocks are marked as seen without notifications.'
    )
    args = parser.parse_args()
    
    live_ws.main(send_historical=args.send_historical)
