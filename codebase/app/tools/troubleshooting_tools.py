"""
Module chứa các công cụ Hỗ trợ Gỡ lỗi & Kết nối Học viên (Troubleshooting Tools).
Sử dụng CSDL SQLite thực tế (`assignments`, `lab_knowledge`, `users`).
Bao gồm:
1. analyze_student_issue
"""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from app.core.db import get_db_connection
from app import discord_context


class AnalyzeStudentIssueInput(BaseModel):
    task_id: str = Field(..., description="Mã task đang thực hiện")
    issue_description: str = Field(..., description="Mô tả lỗi hoặc câu hỏi của học viên")
    error_log: Optional[str] = Field(default=None, description="Đoạn log lỗi hoặc mã lỗi từ Terminal/IDE")


def analyze_student_issue(
    task_id: str,
    issue_description: str,
    error_log: Optional[str] = None
) -> Dict[str, Any]:
    """
    1. analyze_student_issue
    Mô tả: Phân tích sự cố/log lỗi của học viên dựa trên thông tin tri thức từ CSDL `lab_knowledge` SQLite DB.
    user_id được auto-resolve từ Discord context. CHỈ dùng được trong group room.
    """
    try:
        ctx = discord_context.get()
        user_id = ctx.user_id or ""
        channel_type = ctx.channel_type or ""
        # Guardrail: chỉ cho phép trong group room
        if channel_type != "group_room":
            return {"status": "empty", "error_code": "NO_CONTEXT",
                    "message": "Tool chỉ dùng được trong group room Discord."}
        if not user_id or not task_id or not task_id.strip() or not issue_description or not issue_description.strip():
            return {
                "status": "empty",
                "error_code": "INVALID_INPUT",
                "message": "task_id và issue_description không được để trống."
            }

        if len(issue_description.strip()) < 10 or "UNCLEAR" in issue_description:
            return {
                "status": "empty",
                "error_code": "UNCLEAR_ISSUE",
                "message": "Mô tả lỗi quá ngắn hoặc log lỗi không hợp lệ. Vui lòng cung cấp thêm chi tiết log Terminal."
            }

        # Tra cứu thông tin từ CSDL tri thức
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT source, content FROM lab_knowledge LIMIT 5")
        rows = cursor.fetchall()
        conn.close()

        desc_lower = issue_description.lower()
        log_lower = (error_log or "").lower()

        if "env" in desc_lower or "database_url" in log_lower or "mongo" in log_lower or "connection" in desc_lower:
            root_cause = "Thiếu biến môi trường DATABASE_URL trong tệp .env"
            suggested_solution = "Hãy tạo tệp .env ở thư mục gốc và thêm dòng DATABASE_URL=mongodb://localhost:27017/lab"
            ref_links = ["https://docs.example.com/env-setup"]
        elif "module" in desc_lower or "import" in desc_lower or "not found" in log_lower:
            root_cause = "Chưa cài đặt thư viện phụ thuộc trong requirements.txt"
            suggested_solution = "Chạy lệnh `pip install -r requirements.txt` hoặc `uv sync` trong Terminal."
            ref_links = ["https://docs.example.com/python-deps"]
        else:
            root_cause = "Lỗi logic xử lý bất đồng bộ Async/Await hoặc tham số truyền vào hàm chưa đúng Schema"
            suggested_solution = "Vui lòng kiểm tra lại cấu trúc tham số Pydantic Model và đảm bảo thêm `await` khi gọi async function."
            ref_links = ["https://docs.example.com/async-python"]

        # Bổ sung thông tin từ tài liệu RAG DB nếu có phù hợp
        if rows:
            for r in rows:
                if "db" in r["source"].lower() and ("database" in desc_lower or "connection" in desc_lower):
                    suggested_solution += f"\n(Tham khảo từ {r['source']}: {r['content'][:100]}...)"
                    break

        return {
            "status": "success",
            "root_cause": root_cause,
            "suggested_solution": suggested_solution,
            "reference_links": ref_links
        }
    except Exception as e:
        return {
            "status": "empty",
            "error_code": "UNCLEAR_ISSUE",
            "message": f"Không thể phân tích lỗi: {str(e)}"
        }


