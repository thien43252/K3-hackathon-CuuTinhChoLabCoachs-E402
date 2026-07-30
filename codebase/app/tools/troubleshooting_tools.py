"""
Module chứa các công cụ Hỗ trợ Gỡ lỗi & Kết nối Học viên (Troubleshooting Tools).
Bao gồm:
14. analyze_student_issue
15. fetch_peer_solution
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AnalyzeStudentIssueInput(BaseModel):
    user_id: str = Field(..., description="Mã học viên báo lỗi")
    task_id: str = Field(..., description="Mã task đang thực hiện")
    issue_description: str = Field(..., description="Mô tả lỗi hoặc câu hỏi của học viên")
    error_log: Optional[str] = Field(default=None, description="Đoạn log lỗi hoặc mã lỗi từ Terminal/IDE")


class FetchPeerSolutionInput(BaseModel):
    group_id: str = Field(..., description="Mã nhóm")
    current_task_id: str = Field(..., description="Mã task học viên đang trễ/gặp khó khăn")
    requesting_user_id: str = Field(..., description="Mã học viên yêu cầu hỗ trợ")


def analyze_student_issue(
    user_id: str,
    task_id: str,
    issue_description: str,
    error_log: Optional[str] = None
) -> Dict[str, Any]:
    """
    14. analyze_student_issue
    Mô tả: Tiếp nhận mô tả sự cố/log lỗi của học viên, phân tích nguyên nhân và đưa ra hướng dẫn khắc phục.
    
    Trường hợp lỗi cover:
    - 400 Bad Request: user_id, task_id hoặc issue_description rỗng.
    - 422 Unprocessable: Mô tả quá ngắn (<10 ký tự) hoặc log không hợp lệ (khi chứa cờ 'UNCLEAR').
    """
    try:
        if not user_id or not user_id.strip() or not task_id or not task_id.strip() or not issue_description or not issue_description.strip():
            return {
                "status": "empty",
                "error_code": "INVALID_INPUT",
                "message": "user_id, task_id và issue_description không được để trống."
            }

        if len(issue_description.strip()) < 10 or "UNCLEAR" in issue_description or "UNCLEAR" in user_id:
            return {
                "status": "empty",
                "error_code": "UNCLEAR_ISSUE",
                "message": "Mô tả lỗi quá ngắn hoặc log lỗi không hợp lệ. Vui lòng cung cấp thêm chi tiết log Terminal."
            }

        # Mock AI diagnostic logic dựa vào log hoặc keyword
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


def fetch_peer_solution(
    group_id: str,
    current_task_id: str,
    requesting_user_id: str
) -> Dict[str, Any]:
    """
    15. fetch_peer_solution
    Mô tả: Tìm kiếm các thành viên trong cùng nhóm đã hoàn thành thành công task tương tự/liên quan để gợi ý tham khảo kết quả.
    
    Trường hợp lỗi cover:
    - 400 Bad Request: group_id, current_task_id hoặc requesting_user_id rỗng.
    - 404 Not Found: Chưa có thành viên nào trong nhóm hoàn thành task tiền đề (khi group_id chứa 'NO_PEER').
    - 500 Internal Error: Lỗi kết nối hệ thống dữ liệu mã nguồn (khi group_id chứa 'TRIGGER_500').
    """
    try:
        if not group_id or not group_id.strip() or not current_task_id or not current_task_id.strip() or not requesting_user_id or not requesting_user_id.strip():
            return {
                "status": "empty",
                "error_code": "INVALID_INPUT",
                "message": "group_id, current_task_id và requesting_user_id không được để trống."
            }

        if "TRIGGER_500" in group_id:
            return {
                "status": "error",
                "error_code": "PEER_FETCH_FAILED",
                "message": "Không thể truy xuất dữ liệu mã nguồn của các thành viên trong nhóm."
            }

        if "NO_PEER" in group_id or "EMPTY" in group_id:
            return {
                "status": "empty",
                "data": [],
                "message": "Hiện chưa có thành viên nào trong nhóm hoàn thành task tiền đề này để tham khảo."
            }

        # Mock helper results với code_snippet trực tiếp để hiển thị trên Discord
        code_example = (
            "```python\n"
            "# Code mẫu tham khảo từ thành viên U123456 cho task T1\n"
            "import os\n\n"
            "def init_database():\n"
            "    db_url = os.getenv('DATABASE_URL')\n"
            "    print(f'Connecting to {db_url}...')\n"
            "    return True\n"
            "```"
        )

        helpers = [
            {
                "user_id": "U123456",
                "full_name": "Pham Duc Thien",
                "completed_task_id": "T1",
                "code_snippet": code_example,
                "github_commit_url": f"https://github.com/example-org/lab-{group_id.lower()}/commit/a1b2c3d4",
                "note": "Học viên này đã hoàn thành task T1 liên quan đến phần kết nối Database."
            }
        ]

        return {
            "status": "success",
            "helpers": helpers
        }
    except Exception as e:
        return {
            "status": "error",
            "error_code": "PEER_FETCH_FAILED",
            "message": f"Không thể truy xuất dữ liệu từ thành viên khác: {str(e)}"
        }
