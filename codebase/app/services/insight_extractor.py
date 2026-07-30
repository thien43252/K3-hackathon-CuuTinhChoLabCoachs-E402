import os
import re
import json
import urllib.request
from typing import Dict, Any, List
from app.core.config import settings

class LabInsightExtractor:
    """
    Trích xuất Insight có cấu trúc từ tài liệu bài Lab làm cơ sở tri thức cho Agent.
    Hỗ trợ gọi Gemini API bằng thư viện chuẩn (no dependencies) và tự động fallback về
    phân tích bằng từ khóa / Regex nếu không có API key.
    """
    
    def __init__(self):
        self.api_key = settings.google_api_key

    def extract_insights(self, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Nhận danh sách tài liệu thô (.md đã phân tích headings/sections)
        và trả về bộ Insight cô đọng: Mục tiêu, Cài đặt, Danh sách Task, Rubric chấm điểm, Bẫy lỗi.
        """
        # Hợp nhất nội dung các file .md chính thành một nguồn tài liệu tổng quan để phân tích
        merged_docs = []
        for doc in documents:
            merged_docs.append(f"### FILE: {doc['relative_path']}\n{doc['raw_content']}")
        full_content = "\n\n".join(merged_docs)

        if self.api_key:
            try:
                return self._extract_via_gemini(full_content)
            except Exception as e:
                print(f"⚠️ Thất bại khi gọi Gemini API ({e}). Đang tự động chuyển sang phân tích Regex...")
                return self._extract_via_regex(documents)
        else:
            print("ℹ️ Không tìm thấy GOOGLE_API_KEY. Sử dụng phân tích Regex...")
            return self._extract_via_regex(documents)

    def _extract_via_gemini(self, content: str) -> Dict[str, Any]:
        """Gọi Gemini 2.5 Flash sử dụng Structured Output để trích xuất tri thức."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.api_key}"
        
        prompt = (
            "Bạn là một chuyên gia phân tích bài toán thực hành AI cho sinh viên.\n"
            "Hãy phân tích tài liệu bài Lab dưới đây và trích xuất ra thông tin tri thức có cấu trúc:\n\n"
            f"{content[:20000]}"  # Giới hạn nội dung tránh quá tải prompt thô
        )

        schema = {
            "type": "OBJECT",
            "properties": {
                "lab_objective": {"type": "STRING", "description": "Tóm tắt mục tiêu cốt lõi của bài Lab"},
                "setup_instructions": {"type": "STRING", "description": "Các bước chuẩn bị & cài đặt môi trường cần thiết"},
                "tasks": {
                  "type": "ARRAY",
                  "items": {
                    "type": "OBJECT",
                    "properties": {
                      "name": {"type": "STRING", "description": "Tên hoặc ID của Task (ví dụ: Task 1, CP1)"},
                      "description": {"type": "STRING", "description": "Mô tả ngắn gọn yêu cầu cần đạt được"}
                    },
                    "required": ["name", "description"]
                  }
                },
                "grading_rubrics": {"type": "STRING", "description": "Các tiêu chí đánh giá / chấm điểm hoặc cách thức nghiệm thu"},
                "common_pitfalls": {
                  "type": "ARRAY",
                  "items": {"type": "STRING", "description": "Bẫy lỗi hoặc kịch bản rủi ro sinh viên hay mắc phải"}
                }
            },
            "required": ["lab_objective", "setup_instructions", "tasks", "grading_rubrics", "common_pitfalls"]
        }

        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": schema
            }
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=30) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            # Trích xuất text phản hồi từ cấu trúc response của Gemini
            json_text = res_data["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(json_text)

    def _extract_via_regex(self, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Tự động gom nhóm thông tin bằng Regex/Keywords khi không có API key."""
        objective_parts = []
        setup_parts = []
        tasks_list = []
        rubric_parts = []
        pitfalls = []

        # Các keyword để phân loại các section
        kw_objective = ["mục tiêu", "objective", "bối cảnh", "giới thiệu", "de-bai", "đề bài"]
        kw_setup = ["cài đặt", "setup", "chuẩn bị", "prerequisite", "install"]
        kw_tasks = ["task", "bước", "yêu cầu", "checkpoint", "cp", "nhiệm vụ"]
        kw_rubrics = ["rubric", "chấm điểm", "nghiệm thu", "tiêu chí", "đánh giá"]
        kw_pitfalls = ["lưu ý", "chú ý", "bẫy", "pitfall", "rủi ro", "chỗ khó"]

        for doc in documents:
            for section in doc.get("sections", []):
                heading = section["heading"].lower()
                content = section["content"].strip()
                
                if not content:
                    continue

                # 1. Phân tích Mục tiêu
                if any(k in heading for k in kw_objective):
                    objective_parts.append(f"- From {doc['file_name']} ({section['heading']}): {content[:300]}...")
                
                # 2. Phân tích Cài đặt
                elif any(k in heading for k in kw_setup):
                    setup_parts.append(content)
                
                # 3. Phân tích Rubrics
                elif any(k in heading for k in kw_rubrics):
                    rubric_parts.append(content)
                
                # 4. Phân tích Bẫy lỗi
                elif any(k in heading for k in kw_pitfalls):
                    pitfalls.append(f"Trong {doc['file_name']} -> {section['heading']}: {content[:200]}...")
                
                # 5. Phân tích Tasks
                elif any(k in heading for k in kw_tasks):
                    tasks_list.append({
                        "name": section["heading"],
                        "description": content[:300] + "..." if len(content) > 300 else content
                    })

        # Xây dựng các giá trị mặc định nếu rỗng
        lab_objective = "\n".join(objective_parts) or "Không tìm thấy thông tin mục tiêu bài toán cụ thể."
        setup_instructions = "\n".join(setup_parts[:2]) or "Không có hướng dẫn cài đặt đặc biệt."
        grading_rubrics = "\n".join(rubric_parts[:2]) or "Không tìm thấy tiêu chí chấm điểm rõ ràng."
        
        if not tasks_list:
            tasks_list = [{"name": "Tổng quát", "description": "Làm theo tài liệu hướng dẫn."}]
        if not pitfalls:
            pitfalls = ["Hãy cẩn thận tránh ảo giác (hallucination) khi lập trình AI Agent."]

        return {
            "lab_objective": lab_objective,
            "setup_instructions": setup_instructions,
            "tasks": tasks_list,
            "grading_rubrics": grading_rubrics,
            "common_pitfalls": pitfalls
        }
