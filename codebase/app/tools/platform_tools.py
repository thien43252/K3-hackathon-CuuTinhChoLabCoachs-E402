"""
Module chứa các công cụ Tương tác Nền tảng & Ngữ cảnh (Platform & Context Tools).
Bao gồm:
4. get_user_context
5. create_group_room
6. send_message
7. send_notification
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

# Mock Store lưu trữ thông tin người dùng và room chat
_USER_DATABASE: Dict[str, Dict[str, Any]] = {
    "U123456": {
        "user_id": "U123456",
        "full_name": "Pham Duc Thien",
        "role": "group_leader",
        "group_id": "G01",
        "today_lab": {
            "lab_id": "LAB05_GROUP",
            "type": "group",
            "title": "Xây dựng AI Agent Workflow"
        }
    },
    "U789012": {
        "user_id": "U789012",
        "full_name": "Nguyen Van A",
        "role": "member",
        "group_id": "G01",
        "today_lab": {
            "lab_id": "LAB05_GROUP",
            "type": "group",
            "title": "Xây dựng AI Agent Workflow"
        }
    },
    "U345678": {
        "user_id": "U345678",
        "full_name": "Tran Thi B",
        "role": "member",
        "group_id": "G01",
        "today_lab": {
            "lab_id": "LAB05_GROUP",
            "type": "group",
            "title": "Xây dựng AI Agent Workflow"
        }
    },
    "U999999": {
        "user_id": "U999999",
        "full_name": "Le Van C",
        "role": "student",
        "group_id": None,
        "today_lab": {
            "lab_id": "LAB05_INDIVIDUAL",
            "type": "individual",
            "title": "Bài lab cá nhân Python Basis"
        }
    }
}

_ROOMS_STORE: Dict[str, Dict[str, Any]] = {}


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
    Mô tả: Lấy thông tin chi tiết về người dùng đang gọi bot, lịch làm lab trong ngày và danh sách nhóm.
    
    Trường hợp lỗi cover:
    - 400 Bad Request: user_id rỗng.
    - 404 Not Found: Không tìm thấy học viên hoặc không có bài lab nào trong ngày.
    - 500 Internal Error: Lỗi kết nối dịch vụ user (khi user_id chứa 'TRIGGER_500').
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

        user_data = _USER_DATABASE.get(user_id)
        if not user_data:
            # Nếu user lạ, kiểm tra xem có cờ NO_LAB hay không
            if "NOLAB" in user_id:
                return {
                    "status": "empty",
                    "error_code": "NO_LAB_TODAY",
                    "message": "Không tìm thấy lịch bài lab nào cho học viên trong ngày hôm nay."
                }
            # Mặc định trả về context mẫu nếu là user bất kỳ
            user_data = {
                "user_id": user_id,
                "full_name": f"Học viên {user_id}",
                "role": "student",
                "group_id": None,
                "today_lab": {
                    "lab_id": "LAB05_INDIVIDUAL",
                    "type": "individual",
                    "title": "Bài lab cá nhân"
                }
            }

        group_info = None
        if user_data.get("group_id"):
            gid = user_data["group_id"]
            members = [uid for uid, u in _USER_DATABASE.items() if u.get("group_id") == gid]
            group_info = {
                "group_id": gid,
                "members": members if members else [user_id]
            }

        return {
            "status": "success",
            "user": {
                "user_id": user_data["user_id"],
                "full_name": user_data["full_name"],
                "role": user_data["role"]
            },
            "today_lab": user_data["today_lab"],
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
    Mô tả: Tự động tạo channel/room chat nhóm trên nền tảng (Slack/Discord/Teams) và gửi lời mời.
    
    Trường hợp lỗi cover:
    - 400 Bad Request: room_name rỗng hoặc danh sách member_ids rỗng.
    - 207 Multi-Status: Tạo room thành công nhưng một số thành viên không tồn tại.
    - 500 Internal Error: Lỗi API nền tảng chat (khi room_name chứa 'TRIGGER_500').
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

        room_id = f"C_{abs(hash(room_name)) % 100000000}"
        invite_link = f"https://chat.platform.com/rooms/{room_id}"

        _ROOMS_STORE[room_id] = {
            "room_id": room_id,
            "room_name": room_name,
            "members": added_members,
            "is_private": is_private
        }

        if failed_members:
            return {
                "status": "partial_success",
                "room_id": room_id,
                "added_members": added_members,
                "failed_members": failed_members
            }

        return {
            "status": "success",
            "room_id": room_id,
            "room_name": room_name,
            "added_members": added_members,
            "invite_link": invite_link
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
    Mô tả: Gửi tin nhắn hướng dẫn, phân công task hoặc trao đổi trực tiếp với học viên hoặc kênh nhóm.
    
    Trường hợp lỗi cover:
    - 400 Bad Request: target_id hoặc nội dung message rỗng.
    - 403 Forbidden / Error: Người dùng chặn bot hoặc room_id không tồn tại.
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
    Mô tả: Tag tên học viên (@username) hoặc phát thông báo khẩn cấp/nhắc nhở quan trọng trong kênh làm việc.
    
    Trường hợp lỗi cover:
    - 400 Bad Request: room_id hoặc nội dung content rỗng.
    - 500 Internal Error: Hệ thống push notification bị sập (khi room_id chứa 'TRIGGER_500').
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

        return {
            "status": "success",
            "notified_users_count": notified_count
        }
    except Exception as e:
        return {
            "status": "error",
            "error_code": "NOTIFICATION_FAILED",
            "message": f"Gửi thông báo thất bại: {str(e)}"
        }
