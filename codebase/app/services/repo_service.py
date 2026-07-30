import os
import json
from typing import Dict, Any, Optional
from app.services.git_service import clone_repo
from app.services.doc_processor import LabDocProcessor

# Đường dẫn file JSON lưu cache kết quả phân tích
CACHE_FILE = os.path.abspath("cloned_repos/.lab_cache.json")

def _load_cache() -> Dict[str, Any]:
    """Đọc cache từ file JSON nếu tồn tại."""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def _save_cache(cache: Dict[str, Any]):
    """Ghi cache xuống file JSON."""
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


class LabContentService:
    """
    Service quản lý trọn gói (Orchestrator) luồng xử lý tài liệu Lab.

    Flow khi Admin upload repo lần đầu:
        Nhận link Git → Clone → Phân tích .md → Lưu cache → Sẵn sàng cho Agent
    
    Flow khi Agent/Học viên truy vấn:
        Đọc từ cache → Trả về ngay (không phân tích lại)
    """

    def __init__(self, base_data_dir: str = "cloned_repos"):
        self.base_data_dir = os.path.abspath(base_data_dir)

    def register_lab(self, repo_url: str, lab_id: str, branch: str = None) -> Dict[str, Any]:
        """
        Được gọi DUY NHẤT 1 LẦN bởi Admin khi upload repo Lab.

        Flow:
            Bước 1: Clone repo về máy qua git_service
            Bước 2: Phân tích toàn bộ file .md qua doc_processor
            Bước 3: Lưu kết quả phân tích vào cache JSON
            Bước 4: Trả về cấu trúc dữ liệu hoàn chỉnh

        Args:
            repo_url: Link GitHub của bài Lab
            lab_id: Mã định danh (ví dụ: 'lab5', 'DAY05')
            branch: Nhánh git cần clone (mặc định nhánh chính)
        """
        print(f"\n📥 [ADMIN] Bắt đầu đăng ký Lab mới: {lab_id}")

        # Bước 1: Clone repo
        dest_dir = os.path.join(self.base_data_dir, lab_id)
        try:
            repo_path = clone_repo(repo_url=repo_url, dest_dir=dest_dir, branch=branch)
        except Exception as e:
            raise RuntimeError(f"❌ Không thể tải repository: {str(e)}")

        # Bước 2: Phân tích toàn bộ tài liệu .md
        try:
            processor = LabDocProcessor(repo_path=repo_path)
            structured_data = processor.process_repository()
        except Exception as e:
            raise RuntimeError(f"❌ Lỗi phân tích tài liệu: {str(e)}")

        # Bước 3: Đóng gói dữ liệu và lưu cache
        lab_content = {
            "lab_id": lab_id,
            "repo_url": repo_url,
            "local_path": repo_path,
            "total_documents": structured_data["total_documents"],
            "sitemap": structured_data["sitemap"],
            "documents": structured_data["documents"]
        }
        cache = _load_cache()
        cache[lab_id] = lab_content
        _save_cache(cache)

        print(f"✅ [ADMIN] Đã đăng ký thành công Lab '{lab_id}'. Tìm thấy {lab_content['total_documents']} tài liệu.")
        return lab_content

    def get_lab_data(self, lab_id: str) -> Optional[Dict[str, Any]]:
        """
        Lấy dữ liệu Lab đã phân tích từ cache (không phân tích lại).
        Được gọi bởi Agent khi học viên đặt câu hỏi.
        """
        cache = _load_cache()
        return cache.get(lab_id)

    def list_registered_labs(self) -> list:
        """
        Lấy danh sách tất cả Lab đã được Admin đăng ký trong hệ thống.
        """
        cache = _load_cache()
        return [
            {"lab_id": lab_id, "repo_url": data["repo_url"], "total_documents": data["total_documents"]}
            for lab_id, data in cache.items()
        ]

    @staticmethod
    def get_section_by_title(lab_data: Dict[str, Any], file_name: str, heading_title: str) -> Dict[str, Any]:
        """
        Tìm nhanh một phần hướng dẫn cụ thể dựa vào tên file và tiêu đề.
        Dùng để Agent truy vấn câu trả lời cho học viên.
        """
        for doc in lab_data.get("documents", []):
            if doc["file_name"].lower() == file_name.lower():
                for sec in doc.get("sections", []):
                    if heading_title.lower() in sec["heading"].lower():
                        return {
                            "heading": sec["heading"],
                            "content": sec["content"],
                            "relative_path": doc["relative_path"]
                        }
        return {}
