"""
Discord API Tools
Provides functions to interact with the Discord platform.
"""

import os
import requests
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GUILD_ID = os.getenv("DISCORD_GUILD_ID")
BASE_URL = "https://discord.com/api/v10"

def _get_headers() -> Dict[str, str]:
    if not DISCORD_TOKEN:
        raise ValueError("DISCORD_BOT_TOKEN is not set")
    return {
        "Authorization": f"Bot {DISCORD_TOKEN}",
        "Content-Type": "application/json"
    }

def create_group_room(room_name: str, member_ids: list) -> Optional[Dict]:
    """Tạo room chat nhóm và gửi link mời"""
    headers = _get_headers()
    url = f"{BASE_URL}/guilds/{GUILD_ID}/channels"
    data = {"name": room_name, "type": 0}
    response = requests.post(url, headers=headers, json=data)
    
    if response.status_code in [200, 201]:
        channel = response.json()
        channel_id = channel['id']
        for user_id in member_ids:
            perm_url = f"{BASE_URL}/channels/{channel_id}/permissions/{user_id}"
            requests.put(perm_url, headers=headers, json={"type": 1, "allow": str(1024)})
        return channel
    return None

def send_message(target_id: str, message: str) -> bool:
    """Gửi tin nhắn hướng dẫn/trao đổi trực tiếp"""
    headers = _get_headers()
    url = f"{BASE_URL}/channels/{target_id}/messages"
    response = requests.post(url, headers=headers, json={"content": message})
    return response.status_code == 200

def send_notification(room_id: str, user_ids_to_tag: list, content: str) -> bool:
    """Tag tên (@username) và báo tin khẩn cấp"""
    mentions = " ".join([f"<@{uid}>" for uid in user_ids_to_tag])
    message = f"{mentions}\n{content}"
    return send_message(room_id, message)

def schedule_reminder(target_id: str, remind_at: str, message: str) -> bool:
    """Đặt lịch hẹn giờ nhắc nhở (Timer/Cron)"""
    print(f"Scheduled reminder for {target_id} at {remind_at}: {message}")
    # Mock behavior. Thường cần DB + celery để chạy ngầm.
    return True
