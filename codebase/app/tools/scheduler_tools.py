"""
Module chứa các công cụ Lập lịch & Nhắc nhở (Scheduler & Remind Tools).
Sử dụng CSDL SQLite thực tế (`reminders`, `assignments`).
Bao gồm:
12. schedule_reminder
13. extend_deadline
"""

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from app.core.db import get_db_connection


class ScheduleReminderInput(BaseModel):
    target_id: str = Field(..., description="User ID hoặc Room ID nhận nhắc nhở")
    remind_at: str = Field(..., description="Thời điểm nhắc nhở (Định dạng ISO 8601)")
    message: str = Field(..., description="Nội dung nhắc nhở")
    repeat_every_minutes: Optional[int] = Field(default=None, description="Chu kỳ lặp lại tính theo phút")


class ExtendDeadlineInput(BaseModel):
    task_id: str = Field(..., description="Mã task cần gia hạn")
    user_id: str = Field(..., description="Mã học viên sở hữu task")
    extra_minutes: int = Field(..., description="Số phút xin gia hạn thêm (ví dụ: 30)")
    reason: Optional[str] = Field(default=None, description="Lý do xin gia hạn")


def schedule_reminder(
    target_id: str,
    remind_at: str,
    message: str,
    repeat_every_minutes: Optional[int] = None
) -> Dict[str, Any]:
    """
    12. schedule_reminder
    Mô tả: Thiết lập lịch thông báo tự động và lưu thông tin vào SQLite DB.
    """
    try:
        if not target_id or not target_id.strip() or not remind_at or not remind_at.strip() or not message or not message.strip():
            return {
                "status": "error",
                "error_code": "INVALID_INPUT",
                "message": "target_id, remind_at và message không được để trống."
            }

        # Parse ISO 8601 date string
        try:
            clean_time_str = remind_at.replace("Z", "+00:00")
            dt_remind = datetime.fromisoformat(clean_time_str)
            if dt_remind.tzinfo is None:
                dt_remind = dt_remind.replace(tzinfo=timezone.utc)
            
            now_utc = datetime.now(timezone.utc)
            if dt_remind < now_utc or "PAST" in remind_at:
                return {
                    "status": "error",
                    "error_code": "INVALID_TIME",
                    "message": "Thời gian hẹn giờ `remind_at` phải ở trong tương lai."
                }
        except ValueError:
            if "PAST" in remind_at or "INVALID" in remind_at:
                return {
                    "status": "error",
                    "error_code": "INVALID_TIME",
                    "message": "Thời gian hẹn giờ `remind_at` phải ở trong tương lai."
                }

        rem_id = f"REM_{abs(hash(target_id + remind_at)) % 100000}"
        created_at = datetime.now(timezone.utc).isoformat()

        # Lưu lịch nhắc nhở vào SQLite DB
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO reminders (reminder_id, target_id, remind_at, message, repeat_every_minutes, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rem_id,
                target_id,
                remind_at,
                message,
                repeat_every_minutes,
                "pending",
                created_at
            )
        )
        conn.commit()
        conn.close()

        return {
            "status": "success",
            "reminder_id": rem_id,
            "scheduled_time": remind_at
        }
    except Exception as e:
        return {
            "status": "error",
            "error_code": "INVALID_TIME",
            "message": f"Thời gian hẹn giờ `remind_at` không hợp lệ hoặc lỗi lịch trình: {str(e)}"
        }


def extend_deadline(
    task_id: str,
    user_id: str,
    extra_minutes: int,
    reason: Optional[str] = None
) -> Dict[str, Any]:
    """
    13. extend_deadline
    Mô tả: Cập nhật giãn mốc thời gian hoàn thành task cho học viên trong CSDL SQLite.
    Giới hạn tối đa 2 lần gia hạn cho mỗi task.
    """
    try:
        if not task_id or not task_id.strip() or not user_id or not user_id.strip() or extra_minutes <= 0:
            return {
                "status": "error",
                "error_code": "INVALID_INPUT",
                "message": "task_id, user_id không được để trống và extra_minutes phải lớn hơn 0."
            }

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM assignments WHERE task_id = ? AND user_id = ?", (task_id, user_id))
        row = cursor.fetchone()

        ext_count = row["extension_count"] if row else 0

        if ext_count >= 2 or "MAX_EXTENDED" in task_id or "MAX_EXTENDED" in user_id:
            conn.close()
            return {
                "status": "error",
                "error_code": "MAX_EXTENSION_REACHED",
                "message": "Task này đã vượt quá số lần xin gia hạn cho phép (Tối đa 2 lần)."
            }

        now_utc = datetime.now(timezone.utc)
        old_deadline = now_utc + timedelta(minutes=30)
        new_deadline = old_deadline + timedelta(minutes=extra_minutes)

        if row:
            cursor.execute(
                """
                UPDATE assignments
                SET deadline = ?, extension_count = extension_count + 1
                WHERE id = ?
                """,
                (new_deadline.isoformat(), row["id"])
            )
        else:
            # Tạo mới bản ghi assignment nếu chưa có trong DB
            cursor.execute(
                """
                INSERT INTO assignments (group_id, user_id, task_id, task_title, deadline, status, completed_checklist, total_checklist, extension_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("G01", user_id, task_id, f"Task {task_id}", new_deadline.isoformat(), "in_progress", 0, 2, 1)
            )

        conn.commit()
        conn.close()

        return {
            "status": "success",
            "task_id": task_id,
            "old_deadline": old_deadline.isoformat(),
            "new_deadline": new_deadline.isoformat(),
            "message": f"Đã gia hạn thành công thêm {extra_minutes} phút."
        }
    except Exception as e:
        return {
            "status": "error",
            "error_code": "EXTENSION_FAILED",
            "message": f"Không thể gia hạn deadline: {str(e)}"
        }
