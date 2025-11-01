"""
Telegram notification module for sending order block alerts.
"""
import os
import requests
from . import config


def format_block_message(symbol, timeframe, block):
    """
    Format an order block detection message for Telegram.
    
    Args:
        symbol: Trading pair symbol (e.g., "BTC/USDT")
        timeframe: Timeframe string (e.g., "15m", "30m")
        block: Order block dict with index, low, high, type, score, touches, has_sweep
        
    Returns:
        Formatted message string
    """
    block_type = block['type'].upper()
    emoji = "🟢" if block['type'] == 'bullish' else "🔴"
    score = block.get('score', 0.5)
    touches = block.get('touches', 1)
    has_sweep = block.get('has_sweep', False)
    
    # Score indicator
    if score >= 0.7:
        score_indicator = "⭐⭐⭐ HIGH CONFIDENCE"
    elif score >= 0.5:
        score_indicator = "⭐⭐ MEDIUM CONFIDENCE"
    else:
        score_indicator = "⭐ LOW CONFIDENCE"
    
    # Liquidity sweep indicator
    sweep_text = "\n🔥 Liquidity Sweep Detected!" if has_sweep else ""
    
    message = f"""{emoji} {block_type} Order Block Detected

Symbol: {symbol}
Timeframe: {timeframe}
Block Low: {block['low']:.2f}
Block High: {block['high']:.2f}
Candle Index: {block['index']}

Confidence Score: {score:.2f} / 1.00
{score_indicator}
Touches: {touches}{sweep_text}

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
    bot_token = "7903409662:AAEtRB9uDV8500iFd6kEXQpQXmd7lzeopZg" # os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = "-4730782366" #os.getenv('TELEGRAM_CHAT_ID')
    
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
        response = requests.post(url, json=payload, timeout=config.TELEGRAM_TIMEOUT_SEC)
        if response.status_code == 200:
            print("Telegram notification sent successfully")
            return True
        else:
            print(f"Failed to send Telegram notification: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"Error sending Telegram notification: {e}")
        return False
