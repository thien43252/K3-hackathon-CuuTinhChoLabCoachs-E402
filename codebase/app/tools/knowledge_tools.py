"""
Module chứa các công cụ Tri thức & Tra cứu nội dung Lab (Knowledge Tools).
Bao gồm:
1. get_lab_content
"""

from typing import Any, Dict, Optional
from app.services.repo_service import LabContentService

# Singleton service
_LAB_SERVICE = LabContentService()


def get_lab_content(lab_id: str) -> Dict[str, Any]:
    """
    1. get_lab_content
    Mô tả: Lấy nội dung bài lab đã được Admin phân tích từ cache.
    Trả về mục tiêu, danh sách task, tiêu chí đánh giá, bẫy lỗi,
    và danh sách tài liệu .md của bài lab.
    Dùng sau khi đã biết lab_id từ get_user_context.
    """
    try:
        if not lab_id or not lab_id.strip():
            return {
                "status": "empty",
                "error_code": "INVALID_INPUT",
                "message": "lab_id không được để trống."
            }

        data = _LAB_SERVICE.get_lab_data(lab_id)
        if not data:
            return {
                "status": "empty",
                "error_code": "NO_CACHED_DATA",
                "message": f"Không tìm thấy nội dung cho lab '{lab_id}'. Hãy nhờ Admin đăng ký lab trước."
            }

        insights = data.get("insights", {})
        return {
            "status": "success",
            "lab_id": lab_id,
            "lab_objective": insights.get("lab_objective", ""),
            "setup_instructions": insights.get("setup_instructions", ""),
            "tasks": insights.get("tasks", []),
            "grading_rubrics": insights.get("grading_rubrics", ""),
            "common_pitfalls": insights.get("common_pitfalls", []),
            "total_documents": data.get("total_documents", 0),
            "sitemap": data.get("sitemap", []),
            "message": f"Đã tìm thấy dữ liệu cho lab '{lab_id}'."
        }
    except Exception as e:
        return {
            "status": "error",
            "error_code": "CONTENT_LOOKUP_FAILED",
            "message": f"Không thể truy xuất nội dung lab: {str(e)}"
        }
