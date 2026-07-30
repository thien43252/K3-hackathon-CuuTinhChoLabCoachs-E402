import os
import re
import json
import urllib.request
from typing import Dict, Any, List

class LabInsightExtractor:
    """
    Trích xuất Insight có cấu trúc từ tài liệu bài Lab làm cơ sở tri thức cho Agent.
    Hỗ trợ gọi Gemini API bằng thư viện chuẩn (no dependencies) và tự động fallback về
    phân tích bằng từ khóa / Regex nếu không có API key.
    """
    
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.default_provider = os.getenv("DEFAULT_PROVIDER", "openai").lower()

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

        # Xây dựng danh sách mức độ ưu tiên chạy AI dựa trên .env
        ai_providers = []
        if self.default_provider == "openai":
            ai_providers = [
                ("openai", self.openai_key, self._extract_via_openai),
                ("gemini", self.api_key, self._extract_via_gemini)
            ]
        else:
            ai_providers = [
                ("gemini", self.api_key, self._extract_via_gemini),
                ("openai", self.openai_key, self._extract_via_openai)
            ]

        # Thử lần lượt các phương án AI theo độ ưu tiên
        for name, key, func in ai_providers:
            if key:
                try:
                    return func(full_content)
                except Exception as e:
                    print(f"⚠️ Thất bại khi gọi {name.upper()} API ({e}). Đang thử chuyển hướng phương án dự phòng...")

        # Fallback về Regex/Keywords
        print("ℹ️ Sử dụng phân tích Regex/Keywords làm phương án dự phòng...")
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

    def _extract_via_openai(self, content: str) -> Dict[str, Any]:
        """Gọi OpenAI GPT-4o-mini để trích xuất tri thức sử dụng Structured Output."""
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("Install openai dependency first: pip install openai") from exc

        client = OpenAI(api_key=self.openai_key)
        
        schema = {
            "type": "object",
            "properties": {
                "lab_objective": {"type": "string", "description": "Tóm tắt mục tiêu cốt lõi của bài Lab"},
                "setup_instructions": {"type": "string", "description": "Các bước chuẩn bị & cài đặt môi trường cần thiết"},
                "tasks": {
                  "type": "array",
                  "items": {
                    "type": "object",
                    "properties": {
                      "name": {"type": "string", "description": "Tên hoặc ID của Task (ví dụ: Task 1, CP1)"},
                      "description": {"type": "string", "description": "Mô tả ngắn gọn yêu cầu cần đạt được"}
                    },
                    "required": ["name", "description"],
                    "additionalProperties": False
                  }
                },
                "grading_rubrics": {"type": "string", "description": "Các tiêu chí đánh giá / chấm điểm hoặc cách thức nghiệm thu"},
                "common_pitfalls": {
                  "type": "array",
                  "items": {"type": "string", "description": "Bẫy lỗi hoặc kịch bản rủi ro sinh viên hay mắc phải"}
                }
            },
            "required": ["lab_objective", "setup_instructions", "tasks", "grading_rubrics", "common_pitfalls"],
            "additionalProperties": False
        }
        
        prompt = (
            "Bạn là một chuyên gia phân tích bài toán thực hành AI cho sinh viên.\n"
            "Hãy phân tích tài liệu bài Lab dưới đây và trích xuất ra thông tin tri thức có cấu trúc:\n\n"
            f"{content[:20000]}"
        )
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "lab_insight",
                    "strict": True,
                    "schema": schema
                }
            },
            temperature=0.0
        )
        
        return json.loads(response.choices[0].message.content)

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
