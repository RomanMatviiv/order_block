"""
Telegram notification module for sending order block alerts.
"""
import os
import requests


def format_block_message(symbol, timeframe, block):
    """
    Format an order block detection message for Telegram.
    
    Args:
        symbol: Trading pair symbol (e.g., "BTC/USDT")
        timeframe: Timeframe string (e.g., "15m", "30m")
        block: Order block dict with index, low, high, type
        
    Returns:
        Formatted message string
    """
    block_type = block['type'].upper()
    emoji = "🟢" if block['type'] == 'bullish' else "🔴"
    
    message = f"""{emoji} {block_type} Order Block Detected

Symbol: {symbol}
Timeframe: {timeframe}
Block Low: {block['low']:.2f}
Block High: {block['high']:.2f}
Candle Index: {block['index']}

{'Buy zone identified' if block['type'] == 'bullish' else 'Sell zone identified'}"""
    
    return message


def send_telegram(message):
    """
    Send a message via Telegram bot.
    
    Args:
        message: Message text to send
        
    Returns:
        True if successful, False otherwise
    """
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if not bot_token or not chat_id:
        print("Warning: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set. Skipping notification.")
        return False
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'HTML'
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print("Telegram notification sent successfully")
            return True
        else:
            print(f"Failed to send Telegram notification: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"Error sending Telegram notification: {e}")
        return False
