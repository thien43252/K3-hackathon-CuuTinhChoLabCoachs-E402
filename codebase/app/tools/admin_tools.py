"""
Module chứa các công cụ Quản trị & Tri thức (Admin & Knowledge Tools).
Bao gồm:
1. upload_lab_material
2. codebase_indexer
3. RAG_search
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

# In-memory storage mock cho Lab Materials & Vector Index
_LAB_MATERIALS_STORE: Dict[str, Dict[str, Any]] = {}
_VECTOR_INDEX_STORE: Dict[str, List[Dict[str, Any]]] = {}


class UploadLabMaterialInput(BaseModel):
    lab_id: str = Field(..., description="Mã định danh duy nhất của bài lab (ví dụ: 'LAB05_INDIVIDUAL')")
    title: str = Field(..., description="Tiêu đề bài lab")
    type: str = Field(..., description="Loại bài lab ('individual' hoặc 'group')")
    description: str = Field(..., description="Nội dung mô tả yêu cầu bài lab")
    lecture_files: Optional[List[str]] = Field(default=None, description="Danh sách Discord Attachment URLs hoặc đường dẫn tệp bài giảng")
    codebase_repo_url: Optional[str] = Field(default=None, description="Đường dẫn kho chứa codebase mẫu")


class CodebaseIndexerInput(BaseModel):
    lab_id: str = Field(..., description="Mã bài lab cần index dữ liệu")
    force_reindex: bool = Field(default=False, description="Bắt buộc index lại từ đầu")


class RAGSearchInput(BaseModel):
    query: str = Field(..., description="Câu hỏi hoặc vấn đề cần tra cứu")
    lab_id: str = Field(..., description="Mã bài lab cần giới hạn phạm vi truy vấn")
    top_k: int = Field(default=5, description="Số lượng kết quả phù hợp nhất cần trả về")


def upload_lab_material(
    lab_id: str,
    title: str,
    type: str,
    description: str,
    lecture_files: Optional[List[str]] = None,
    codebase_repo_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    1. upload_lab_material
    Mô tả: Admin tải lên nội dung bài lab code, bài giảng và mã nguồn codebase mẫu lên hệ thống.
    
    Trường hợp lỗi cover:
    - 400 Bad Request: Thiếu thông tin hoặc lab_id rỗng.
    - 400 Bad Request: Loại lab không thuộc 'individual' hoặc 'group'.
    - 500 Internal Error: Lỗi kết nối lưu trữ giả lập (ví dụ khi lab_id chứa từ khóa 'TRIGGER_500').
    """
    try:
        # Validate Input
        if not lab_id or not lab_id.strip() or not title or not title.strip() or not description or not description.strip():
            return {
                "status": "empty",
                "error_code": "INVALID_INPUT",
                "message": "Nội dung bài lab, tiêu đề hoặc lab_id không được để trống."
            }
        
        if type not in ["individual", "group"]:
            return {
                "status": "empty",
                "error_code": "INVALID_TYPE",
                "message": "Loại bài lab (type) phải là 'individual' hoặc 'group'."
            }

        # Giả lập lỗi hệ thống nếu gặp cờ test 500
        if "TRIGGER_500" in lab_id:
            return {
                "status": "error",
                "error_code": "STORAGE_FAILED",
                "message": "Không thể kết nối đến hệ thống lưu trữ dữ liệu Admin."
            }

        created_at = datetime.now(timezone.utc).isoformat()
        _LAB_MATERIALS_STORE[lab_id] = {
            "lab_id": lab_id,
            "title": title,
            "type": type,
            "description": description,
            "lecture_files": lecture_files or [],
            "codebase_repo_url": codebase_repo_url,
            "created_at": created_at
        }

        return {
            "status": "success",
            "lab_id": lab_id,
            "message": "Đã lưu trữ nội dung bài lab thành công.",
            "created_at": created_at
        }
    except Exception as e:
        return {
            "status": "error",
            "error_code": "STORAGE_FAILED",
            "message": f"Không thể kết nối đến hệ thống lưu trữ dữ liệu Admin: {str(e)}"
        }


def codebase_indexer(
    lab_id: str,
    force_reindex: bool = False
) -> Dict[str, Any]:
    """
    2. codebase_indexer
    Mô tả: Tự động trích xuất, phân tích và đánh chỉ mục (index) tệp bài giảng và codebase vào hệ thống RAG / Vector Database.
    
    Trường hợp lỗi cover:
    - 400 Bad Request: lab_id không hợp lệ.
    - 404 Not Found: Không tìm thấy tài liệu bài lab để index.
    - 500 Internal Error: Lỗi kết nối Vector DB giả lập (khi lab_id chứa 'TRIGGER_500').
    """
    try:
        if not lab_id or not lab_id.strip():
            return {
                "status": "empty",
                "error_code": "INVALID_INPUT",
                "message": "lab_id không được để trống."
            }

        # Giả lập lỗi hệ thống Vector DB
        if "TRIGGER_500" in lab_id:
            return {
                "status": "error",
                "error_code": "VECTOR_DB_ERROR",
                "message": "Lỗi kết nối Vector Database khi ghi dữ liệu nhúng (embeddings)."
            }

        # Kiểm tra xem material có tồn tại không
        if lab_id not in _LAB_MATERIALS_STORE and not lab_id.startswith("MOCK_"):
            return {
                "status": "empty",
                "error_code": "NO_MATERIAL_FOUND",
                "message": "Không tìm thấy tệp codebase hoặc bài giảng để index cho bài lab này."
            }

        # Mock index creation
        chunks_count = 142
        collection_name = f"{lab_id.lower()}_knowledge_base"
        
        # Populate mock vector index data
        _VECTOR_INDEX_STORE[lab_id] = [
            {
                "content": "Sử dụng hàm connectDB() trong src/db.js để khởi tạo kết nối CSDL.",
                "source": "src/db.js",
                "keywords": ["database", "db", "connect", "kết nối"]
            },
            {
                "content": "Để phân chia task nhóm, sử dụng bot command !assign kèm danh sách checklist.",
                "source": "lecture_05.pdf",
                "keywords": ["task", "checklist", "nhóm", "phân chia"]
            },
            {
                "content": "Hướng dẫn xử lý trễ tiến độ: Đặt lịch gia hạn qua tool extend_deadline.",
                "source": "guide.md",
                "keywords": ["trễ", "tiến độ", "gia hạn", "deadline"]
            }
        ]

        return {
            "status": "success",
            "lab_id": lab_id,
            "indexed_chunks": chunks_count,
            "vector_collection": collection_name
        }
    except Exception as e:
        return {
            "status": "error",
            "error_code": "VECTOR_DB_ERROR",
            "message": f"Lỗi kết nối Vector Database khi ghi dữ liệu nhúng (embeddings): {str(e)}"
        }


def RAG_search(
    query: str,
    lab_id: str,
    top_k: int = 5
) -> Dict[str, Any]:
    """
    3. RAG_search
    Mô tả: Truy vấn cơ sở tri thức để lấy các đoạn mã nguồn mẫu, hướng dẫn làm bài hoặc đáp án bài giảng liên quan đến câu hỏi.
    
    Trường hợp lỗi cover:
    - 400 Bad Request: query hoặc lab_id rỗng.
    - 200 OK (data empty): Không tìm thấy kết quả phù hợp với query.
    - 500 Internal Error: Dịch vụ RAG tìm kiếm bị tắt/lỗi giả lập (khi query chứa 'TRIGGER_500').
    """
    try:
        if not query or not query.strip() or not lab_id or not lab_id.strip():
            return {
                "status": "empty",
                "error_code": "INVALID_INPUT",
                "message": "Nội dung truy vấn query và lab_id không được để trống."
            }

        if "TRIGGER_500" in query or "TRIGGER_500" in lab_id:
            return {
                "status": "error",
                "error_code": "SEARCH_SERVICE_DOWN",
                "message": "Dịch vụ truy vấn RAG tạm thời không khả dụng."
            }

        # Lấy dữ liệu index (nếu chưa có thì tạo mock index mặc định cho MOCK_ labs)
        indexed_items = _VECTOR_INDEX_STORE.get(lab_id, [])
        if not indexed_items and (lab_id in _LAB_MATERIALS_STORE or lab_id.startswith("MOCK_") or lab_id.startswith("LAB")):
            # Fallback mock items
            indexed_items = [
                {
                    "content": f"Sử dụng hàm connectDB() trong src/db.js cho bài lab {lab_id}.",
                    "source": "src/db.js",
                    "keywords": ["database", "db", "connect", "kết nối", "khởi tạo"]
                },
                {
                    "content": "Cấu hình AI Agent Workflow bằng cách đăng ký các Tools định nghĩa trong app/tools.",
                    "source": "docs/architecture.md",
                    "keywords": ["workflow", "agent", "tool", "cấu hình"]
                }
            ]

        query_lower = query.lower()
        matched_results = []
        for idx, item in enumerate(indexed_items):
            content_lower = item["content"].lower()
            keywords = item.get("keywords", [])
            # Simple keyword match scoring mock
            score = 0.5
            if any(kw in query_lower for kw in keywords) or any(word in content_lower for word in query_lower.split()):
                score = 0.94 - (idx * 0.05)
                matched_results.append({
                    "content": item["content"],
                    "source": item["source"],
                    "score": round(score, 2)
                })

        if not matched_results:
            return {
                "status": "empty",
                "data": [],
                "message": "Không tìm thấy nội dung phù hợp với truy vấn trong tài liệu bài lab."
            }

        return {
            "status": "success",
            "query": query,
            "data": matched_results[:top_k]
        }
    except Exception as e:
        return {
            "status": "error",
            "error_code": "SEARCH_SERVICE_DOWN",
            "message": f"Dịch vụ truy vấn RAG tạm thời không khả dụng: {str(e)}"
        }
