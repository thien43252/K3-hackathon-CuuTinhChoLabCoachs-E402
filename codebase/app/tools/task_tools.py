"""
Module chứa các công cụ Quản lý Nhiệm vụ & Bài tập (Task Management Tools).
Bao gồm:
8. parse_lab_requirements
9. assign_task
10. track_group_progress
11. generate_reflection
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

# Mock database lưu trữ thông tin assignment và tiến độ công việc
_ASSIGNMENTS_STORE: Dict[str, List[Dict[str, Any]]] = {}
_GROUP_PROGRESS_STORE: Dict[str, Dict[str, Any]] = {}


class AssignmentItem(BaseModel):
    user_id: str = Field(..., description="ID học viên được phân công")
    task_id: str = Field(..., description="Mã task được phân công")
    deadline: Optional[str] = Field(default=None, description="Thời hạn hoàn thành (ISO string)")


class ParseLabRequirementsInput(BaseModel):
    lab_id: str = Field(..., description="Mã bài lab cần phân tích")
    member_count: int = Field(..., description="Số lượng thành viên trong nhóm")
    duration_hours: Optional[float] = Field(default=2.0, description="Thời lượng làm lab dự kiến (tính theo giờ)")


class AssignTaskInput(BaseModel):
    group_id: str = Field(..., description="Mã định danh nhóm")
    assignments: List[AssignmentItem] = Field(..., description="Danh sách phân công: [{ user_id, task_id, deadline }]")


class TrackGroupProgressInput(BaseModel):
    group_id: str = Field(..., description="Mã nhóm cần kiểm tra tiến độ")


class GenerateReflectionInput(BaseModel):
    user_id: str = Field(..., description="Mã học viên")
    lab_id: str = Field(..., description="Mã bài lab")


def parse_lab_requirements(
    lab_id: str,
    member_count: int,
    duration_hours: Optional[float] = 2.0
) -> Dict[str, Any]:
    """
    8. parse_lab_requirements
    Mô tả: Sử dụng AI để phân tích yêu cầu bài lab nhóm thành các task nhỏ, ước lượng timeline/phase và tạo checklist.
    
    Trường hợp lỗi cover:
    - 400 Bad Request: member_count <= 0 hoặc lab_id rỗng.
    - 422 Unprocessable: Nội dung bài lab quá ngắn hoặc thiếu thông tin (khi lab_id chứa 'UNPARSEABLE').
    """
    try:
        if not lab_id or not lab_id.strip() or member_count <= 0:
            return {
                "status": "empty",
                "error_code": "INVALID_INPUT",
                "message": "lab_id không được để trống và member_count phải lớn hơn 0."
            }

        if "UNPARSEABLE" in lab_id or "SHORT" in lab_id:
            return {
                "status": "empty",
                "error_code": "UNABLE_TO_PARSE",
                "message": "Nội dung bài lab quá ngắn hoặc thiếu thông tin để chia task."
            }

        # Mock AI generation tasks chia theo phase
        tasks = [
            {
                "task_id": "T1",
                "title": "Thiết kế Schema Database & Model Dữ liệu",
                "phase": "Phase 1 (0-30 phút)",
                "checklist": ["Tạo bảng User & Group", "Tạo bảng Task & Assignment"]
            },
            {
                "task_id": "T2",
                "title": "Xây dựng các API Backend chính",
                "phase": "Phase 2 (30-90 phút)",
                "checklist": ["Viết API GET /tasks", "Viết API POST /tasks/assign"]
            },
            {
                "task_id": "T3",
                "title": "Tích hợp Bot Agent & Xử lý Prompt",
                "phase": "Phase 3 (90-120 phút)",
                "checklist": ["Tạo Prompt Template cho Bot", "Kết nối Tool vào Agent Loop"]
            }
        ]

        # Giới hạn số task tương ứng với số thành viên
        if member_count == 1:
            tasks = [tasks[0]]
        elif member_count == 2:
            tasks = tasks[:2]

        return {
            "status": "success",
            "tasks": tasks
        }
    except Exception as e:
        return {
            "status": "empty",
            "error_code": "UNABLE_TO_PARSE",
            "message": f"Không thể phân tích yêu cầu bài lab: {str(e)}"
        }


def assign_task(
    group_id: str,
    assignments: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    9. assign_task
    Mô tả: Phân công task và checklist cho từng thành viên sau khi Nhóm trưởng đã xác nhận chia công việc.
    
    Trường hợp lỗi cover:
    - 400 Bad Request: group_id rỗng hoặc danh sách assignments rỗng.
    - 404 Not Found: Mã task_id không tồn tại (khi task_id chứa 'T99' hoặc 'INVALID').
    """
    try:
        if not group_id or not group_id.strip() or not assignments:
            return {
                "status": "empty",
                "error_code": "INVALID_INPUT",
                "message": "group_id và danh sách assignments không được để trống."
            }

        valid_task_ids = {"T1", "T2", "T3", "T4", "T5"}
        
        parsed_assignments = []
        for item in assignments:
            tid = item.get("task_id") if isinstance(item, dict) else getattr(item, "task_id", None)
            uid = item.get("user_id") if isinstance(item, dict) else getattr(item, "user_id", None)
            deadline = item.get("deadline") if isinstance(item, dict) else getattr(item, "deadline", None)

            if not tid or (tid not in valid_task_ids and "T99" in tid):
                return {
                    "status": "empty",
                    "error_code": "INVALID_TASK_ID",
                    "message": f"Mã task_id {tid} không tồn tại trong bài lab này."
                }
            
            parsed_assignments.append({
                "user_id": uid,
                "task_id": tid,
                "deadline": deadline or "2026-07-30T18:00:00Z"
            })

        _ASSIGNMENTS_STORE[group_id] = parsed_assignments
        
        # Cập nhật tiến độ ban đầu
        _GROUP_PROGRESS_STORE[group_id] = {
            "group_id": group_id,
            "overall_completion_percent": 0.0,
            "members_progress": [
                {
                    "user_id": a["user_id"],
                    "task_title": f"Task {a['task_id']}",
                    "status": "in_progress",
                    "completed_checklist": 0,
                    "total_checklist": 2
                } for a in parsed_assignments
            ]
        }

        assignments_summary = [
            f"- [ ] Task `{a['task_id']}`: Phân công cho <@{a['user_id']}> (Deadline: {a['deadline']})"
            for a in parsed_assignments
        ]

        return {
            "status": "success",
            "assigned_count": len(parsed_assignments),
            "assignments_summary": assignments_summary,
            "message": f"Đã phân công thành công {len(parsed_assignments)} task cho nhóm {group_id} trên Discord."
        }
    except Exception as e:
        return {
            "status": "error",
            "error_code": "ASSIGNMENT_FAILED",
            "message": f"Phân công task thất bại: {str(e)}"
        }


def track_group_progress(
    group_id: str
) -> Dict[str, Any]:
    """
    10. track_group_progress
    Mô tả: Tổng hợp phần trăm hoàn thành, danh sách task đã xong / chưa xong của tất cả thành viên trong nhóm.
    
    Trường hợp lỗi cover:
    - 400 Bad Request: group_id rỗng.
    - 404 Not Found: Nhóm chưa được phân công task nào.
    """
    try:
        if not group_id or not group_id.strip():
            return {
                "status": "empty",
                "error_code": "INVALID_INPUT",
                "message": "group_id không được để trống."
            }

        if "UNASSIGNED" in group_id or (group_id not in _GROUP_PROGRESS_STORE and group_id not in _ASSIGNMENTS_STORE and not group_id.startswith("G")):
            return {
                "status": "empty",
                "error_code": "NO_TASK_ASSIGNED",
                "message": "Nhóm này chưa được phân công task nào."
            }

        progress_data = _GROUP_PROGRESS_STORE.get(group_id)
        if not progress_data:
            # Mock progress data cho nhóm G01 / Gxx bất kỳ
            progress_data = {
                "group_id": group_id,
                "overall_completion_percent": 75.0,
                "members_progress": [
                    {
                        "user_id": "U123456",
                        "task_title": "Thiết kế Schema Database",
                        "status": "completed",
                        "completed_checklist": 2,
                        "total_checklist": 2
                    },
                    {
                        "user_id": "U789012",
                        "task_title": "Xây dựng API Backend",
                        "status": "in_progress",
                        "completed_checklist": 1,
                        "total_checklist": 2
                    }
                ]
            }

        return {
            "status": "success",
            "group_id": group_id,
            "overall_completion_percent": progress_data["overall_completion_percent"],
            "members_progress": progress_data["members_progress"]
        }
    except Exception as e:
        return {
            "status": "error",
            "error_code": "TRACKING_FAILED",
            "message": f"Không thể lấy tiến độ nhóm: {str(e)}"
        }


def generate_reflection(
    user_id: str,
    lab_id: str
) -> Dict[str, Any]:
    """
    11. generate_reflection
    Mô tả: Tổng hợp lịch sử làm bài, mức độ hoàn thành task và thái độ để sinh bài đánh giá/reflection cá nhân.
    
    Trường hợp lỗi cover:
    - 400 Bad Request: user_id hoặc lab_id rỗng.
    - 400 Bad Request: Học viên chưa hoàn thành bài lab (khi user_id hoặc lab_id chứa 'INCOMPLETE').
    """
    try:
        if not user_id or not user_id.strip() or not lab_id or not lab_id.strip():
            return {
                "status": "empty",
                "error_code": "INVALID_INPUT",
                "message": "user_id và lab_id không được để trống."
            }

        if "INCOMPLETE" in user_id or "INCOMPLETE" in lab_id:
            return {
                "status": "empty",
                "error_code": "INCOMPLETE_LAB",
                "message": "Học viên chưa hoàn thành bài lab nên chưa thể sinh reflection."
            }

        reflection_data = {
            "summary": "Bạn đã hoàn thành xuất sắc nhiệm vụ thiết kế Database đúng thời hạn.",
            "strengths": [
                "Quản lý thời gian tốt và chủ động theo dõi checklist",
                "Hỗ trợ thành viên khác trong nhóm gỡ lỗi API"
            ],
            "improvements": [
                "Nên viết comment rõ ràng hơn trong file migration",
                "Chú ý cập nhật trạng thái task nhanh hơn qua lệnh chat trên Discord"
            ]
        }

        return {
            "status": "success",
            "user_id": user_id,
            "reflection": reflection_data
        }
    except Exception as e:
        return {
            "status": "error",
            "error_code": "REFLECTION_FAILED",
            "message": f"Không thể sinh reflection: {str(e)}"
        }
