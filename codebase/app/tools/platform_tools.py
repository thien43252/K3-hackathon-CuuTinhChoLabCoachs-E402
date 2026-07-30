"""
Module chứa các công cụ Tương tác Nền tảng & Ngữ cảnh (Platform & Context Tools).
Sử dụng CSDL SQLite thực tế (`users`, `rooms`, `messages`).
Bao gồm:
4. get_user_context
5. create_group_room
6. send_message
7. send_notification
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.core.db import get_db_connection


class GetUserContextInput(BaseModel):
    user_id: str = Field(..., description="ID người dùng trên hệ thống chat (Slack/Discord/LMS)")
    date: Optional[str] = Field(default=None, description="Ngày làm lab (định dạng YYYY-MM-DD)")


class CreateGroupRoomInput(BaseModel):
    room_name: str = Field(..., description="Tên room chat cần tạo")
    member_ids: List[str] = Field(..., description="Danh sách User ID của các thành viên")
    is_private: bool = Field(default=True, description="Quyền riêng tư của room")


class SendMessageInput(BaseModel):
    target_id: str = Field(..., description="Room ID hoặc User ID nhận tin nhắn")
    message: str = Field(..., description="Nội dung tin nhắn (hỗ trợ Markdown)")
    attachments: Optional[List[Dict[str, Any]]] = Field(default=None, description="Đính kèm (File, Card UI...)")


class SendNotificationInput(BaseModel):
    room_id: str = Field(..., description="Room ID nơi phát thông báo")
    user_ids_to_tag: List[str] = Field(..., description="Danh sách ID người dùng cần tag tên")
    content: str = Field(..., description="Nội dung thông báo")
    urgency: str = Field(default="normal", description="Mức độ ưu tiên ('normal', 'high', 'urgent')")


def get_user_context(
    user_id: str,
    date: Optional[str] = None
) -> Dict[str, Any]:
    """
    4. get_user_context
    Mô tả: Lấy thông tin chi tiết về người dùng đang gọi bot từ SQLite DB.
    """
    try:
        if not user_id or not user_id.strip():
            return {
                "status": "empty",
                "error_code": "INVALID_INPUT",
                "message": "user_id không được để trống."
            }

        if "TRIGGER_500" in user_id:
            return {
                "status": "error",
                "error_code": "USER_SERVICE_UNAVAILABLE",
                "message": "Không thể kết nối đến hệ thống quản lý học viên."
            }

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user_row = cursor.fetchone()

        if not user_row:
            if "NOLAB" in user_id:
                conn.close()
                return {
                    "status": "empty",
                    "error_code": "NO_LAB_TODAY",
                    "message": "Không tìm thấy lịch bài lab nào cho học viên trong ngày hôm nay."
                }
            # Mặc định thêm mới user học viên mẫu vào DB nếu chưa tồn tại
            cursor.execute(
                """
                INSERT INTO users (user_id, full_name, role, group_id, today_lab_id, today_lab_type, today_lab_title)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, f"Học viên {user_id}", "student", None, "LAB05_INDIVIDUAL", "individual", "Bài lab cá nhân")
            )
            conn.commit()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            user_row = cursor.fetchone()

        group_info = None
        group_id = user_row["group_id"]
        if group_id:
            cursor.execute("SELECT user_id FROM users WHERE group_id = ?", (group_id,))
            member_rows = cursor.fetchall()
            members_list = [r["user_id"] for r in member_rows]
            group_info = {
                "group_id": group_id,
                "members": members_list if members_list else [user_id]
            }

        today_lab = {
            "lab_id": user_row["today_lab_id"] or "LAB05_INDIVIDUAL",
            "type": user_row["today_lab_type"] or "individual",
            "title": user_row["today_lab_title"] or "Bài lab"
        }

        conn.close()

        return {
            "status": "success",
            "user": {
                "user_id": user_row["user_id"],
                "full_name": user_row["full_name"],
                "role": user_row["role"]
            },
            "today_lab": today_lab,
            "group_info": group_info
        }
    except Exception as e:
        return {
            "status": "error",
            "error_code": "USER_SERVICE_UNAVAILABLE",
            "message": f"Không thể kết nối đến hệ thống quản lý học viên: {str(e)}"
        }


def create_group_room(
    room_name: str,
    member_ids: List[str],
    is_private: bool = True
) -> Dict[str, Any]:
    """
    5. create_group_room
    Mô tả: Tự động tạo channel/room chat nhóm và ghi nhận thông tin vào SQLite DB.
    """
    try:
        if not room_name or not room_name.strip() or not member_ids:
            return {
                "status": "empty",
                "error_code": "INVALID_INPUT",
                "message": "room_name và danh sách member_ids không được để trống."
            }

        if "TRIGGER_500" in room_name:
            return {
                "status": "error",
                "error_code": "PLATFORM_API_ERROR",
                "message": "Không có quyền tạo channel trên nền tảng chat."
            }

        added_members = []
        failed_members = []

        for uid in member_ids:
            if uid.startswith("INVALID_") or uid == "U_UNKNOWN":
                failed_members.append({"user_id": uid, "reason": "User not found"})
            else:
                added_members.append(uid)

        room_id = f"1298{abs(hash(room_name)) % 100000000000000}"
        discord_channel_name = f"group-{room_name.lower().replace(' ', '-')}"
        created_at = datetime.now(timezone.utc).isoformat()

        # Lưu room vào CSDL SQLite
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO rooms (room_id, room_name, discord_channel_id, channel_name, added_members, is_private, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                room_id,
                room_name,
                room_id,
                discord_channel_name,
                json.dumps(added_members, ensure_ascii=False),
                1 if is_private else 0,
                created_at
            )
        )
        conn.commit()
        conn.close()

        if failed_members:
            return {
                "status": "partial_success",
                "room_id": room_id,
                "discord_channel_id": room_id,
                "channel_name": discord_channel_name,
                "added_members": added_members,
                "failed_members": failed_members
            }

        return {
            "status": "success",
            "room_id": room_id,
            "discord_channel_id": room_id,
            "channel_name": discord_channel_name,
            "added_members": added_members
        }
    except Exception as e:
        return {
            "status": "error",
            "error_code": "PLATFORM_API_ERROR",
            "message": f"Lỗi gọi Platform API: {str(e)}"
        }


def send_message(
    target_id: str,
    message: str,
    attachments: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    6. send_message
    Mô tả: Gửi tin nhắn hướng dẫn và lưu lịch sử vào SQLite DB.
    """
    try:
        if not target_id or not target_id.strip() or not message or not message.strip():
            return {
                "status": "error",
                "error_code": "INVALID_INPUT",
                "message": "target_id và message không được để trống."
            }

        if "BLOCKED" in target_id or "INVALID" in target_id:
            return {
                "status": "error",
                "error_code": "CANNOT_SEND_MESSAGE",
                "message": "Người dùng đã chặn tin nhắn trực tiếp từ Bot hoặc Room ID không tồn tại."
            }

        msg_id = f"MSG_{abs(hash(message + datetime.now(timezone.utc).isoformat())) % 1000000}"
        delivered_at = datetime.now(timezone.utc).isoformat()

        # Lưu tin nhắn vào CSDL SQLite
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO messages (message_id, target_id, message, attachments, delivered_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                msg_id,
                target_id,
                message,
                json.dumps(attachments or [], ensure_ascii=False),
                delivered_at
            )
        )
        conn.commit()
        conn.close()

        return {
            "status": "success",
            "message_id": msg_id,
            "delivered_at": delivered_at
        }
    except Exception as e:
        return {
            "status": "error",
            "error_code": "CANNOT_SEND_MESSAGE",
            "message": f"Không thể gửi tin nhắn: {str(e)}"
        }


def send_notification(
    room_id: str,
    user_ids_to_tag: List[str],
    content: str,
    urgency: str = "normal"
) -> Dict[str, Any]:
    """
    7. send_notification
    Mô tả: Tag tên học viên (@username) hoặc phát thông báo khẩn cấp trong kênh làm việc.
    """
    try:
        if not room_id or not room_id.strip() or not content or not content.strip():
            return {
                "status": "error",
                "error_code": "INVALID_INPUT",
                "message": "room_id và nội dung content không được để trống."
            }

        if "TRIGGER_500" in room_id:
            return {
                "status": "error",
                "error_code": "NOTIFICATION_FAILED",
                "message": "Hệ thống thông báo đẩy bị ngắt kết nối."
            }

        notified_count = len(user_ids_to_tag)
        formatted_mentions = [f"<@{uid}>" if not uid.startswith("<@") else uid for uid in user_ids_to_tag]

        # Ghi log thông báo vào SQLite messages DB
        conn = get_db_connection()
        cursor = conn.cursor()
        msg_id = f"NOTIF_{abs(hash(content + datetime.now(timezone.utc).isoformat())) % 1000000}"
        cursor.execute(
            """
            INSERT INTO messages (message_id, target_id, message, attachments, delivered_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                msg_id,
                room_id,
                f"[{urgency.upper()}] Mentions: {', '.join(formatted_mentions)} - {content}",
                json.dumps([], ensure_ascii=False),
                datetime.now(timezone.utc).isoformat()
            )
        )
        conn.commit()
        conn.close()

        return {
            "status": "success",
            "notified_users_count": notified_count,
            "discord_mentions": formatted_mentions
        }
    except Exception as e:
        return {
            "status": "error",
            "error_code": "NOTIFICATION_FAILED",
            "message": f"Gửi thông báo thất bại: {str(e)}"
        }
