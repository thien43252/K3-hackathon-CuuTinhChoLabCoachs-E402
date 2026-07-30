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
        # Build content từ sections (có cấu trúc) thay vì raw_content (phẳng)
        # Mỗi file cap 3000 chars, total cap 20000 chars
        doc_texts = []
        for doc in documents:
            fn = doc.get("relative_path", "unknown")
            parts = [f"### FILE: {fn}"]
            for sec in doc.get("sections", []):
                parts.append(f"## {sec['heading']}\n{sec['content'][:500]}")
            body = "\n".join(parts)
            if len(body) > 3000:
                body = body[:3000] + "\n...(truncated)"
            doc_texts.append(body)
        full_content = "\n\n".join(doc_texts)
        if len(full_content) > 20000:
            full_content = full_content[:20000]

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
            "Bạn là chuyên gia phân tích bài lab cho sinh viên.\n"
            "Phân tích TẤT CẢ file .md dưới đây và trích xuất thông tin CHI TIẾT (không tóm tắt quá mức):\n\n"
            f"{content[:20000]}"
        )

        schema = {
            "type": "OBJECT",
            "properties": {
                "lab_objective": {"type": "STRING", "description": "Mục tiêu + context đầy đủ của bài lab (3-5 câu)"},
                "timeline": {"type": "STRING", "description": "Timeline/lịch trình (thời lượng, các mốc checkpoint)"},
                "setup_instructions": {"type": "STRING", "description": "Từng bước cài đặt: clone, venv, pip install, .env, smoke test"},
                "tasks": {
                  "type": "ARRAY",
                  "items": {
                    "type": "OBJECT",
                    "properties": {
                      "name": {"type": "STRING", "description": "Tên task (vd: Task 1: Thiết kế & Đánh giá Agentic Fit)"},
                      "description": {"type": "STRING", "description": "Mô tả chi tiết (3-5 câu): cần làm gì, output là gì"},
                      "checklist": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Checklist cụ thể cho task này (3-6 items)"},
                      "deliverable": {"type": "STRING", "description": "Deliverable/sản phẩm cần nộp"},
                      "estimated_minutes": {"type": "NUMBER", "description": "Thời gian ước tính (phút)"}
                    },
                    "required": ["name", "description", "checklist"]
                  }
                },
                "grading_rubrics": {"type": "STRING", "description": "Tiêu chí chấm điểm + trọng số từng phần"},
                "common_pitfalls": {
                  "type": "ARRAY",
                  "items": {"type": "STRING", "description": "Bẫy lỗi cụ thể (kèm hậu quả + cách tránh)"}
                },
                "file_summaries": {
                  "type": "ARRAY",
                  "items": {
                    "type": "OBJECT",
                    "properties": {
                      "file": {"type": "STRING", "description": "Tên file"},
                      "summary": {"type": "STRING", "description": "Tóm tắt nội dung file này (2-3 câu)"}
                    },
                    "required": ["file", "summary"]
                  },
                  "description": "Tóm tắt từng file .md trong repo"
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
                "lab_objective": {"type": "string", "description": "Mục tiêu + context đầy đủ (3-5 câu)"},
                "timeline": {"type": "string", "description": "Timeline/lịch trình (thời lượng, các mốc checkpoint)"},
                "setup_instructions": {"type": "string", "description": "Từng bước cài đặt: clone, venv, pip install, .env, smoke test"},
                "tasks": {
                  "type": "array",
                  "items": {
                    "type": "object",
                    "properties": {
                      "name": {"type": "string", "description": "Tên task (vd: Task 1: Thiết kế & Đánh giá Agentic Fit)"},
                      "description": {"type": "string", "description": "Mô tả chi tiết (3-5 câu)"},
                      "checklist": {"type": "array", "items": {"type": "string"}, "description": "Checklist cụ thể (3-6 items)"},
                      "deliverable": {"type": "string", "description": "Deliverable cần nộp"},
                      "estimated_minutes": {"type": "number", "description": "Thời gian ước tính (phút)"}
                    },
                    "required": ["name", "description", "checklist"],
                    "additionalProperties": False
                  }
                },
                "grading_rubrics": {"type": "string", "description": "Tiêu chí chấm điểm + trọng số"},
                "common_pitfalls": {
                  "type": "array",
                  "items": {"type": "string", "description": "Bẫy lỗi cụ thể + cách tránh"}
                },
                "file_summaries": {
                  "type": "array",
                  "items": {
                    "type": "object",
                    "properties": {
                      "file": {"type": "string"},
                      "summary": {"type": "string", "description": "Tóm tắt 2-3 câu nội dung file này"}
                    },
                    "required": ["file", "summary"],
                    "additionalProperties": False
                  }
                }
            },
            "required": ["lab_objective", "setup_instructions", "tasks", "grading_rubrics", "common_pitfalls"],
            "additionalProperties": False
        }

        prompt = (
            "Bạn là chuyên gia phân tích bài lab cho sinh viên.\n"
            "Phân tích TẤT CẢ file .md dưới đây và trích xuất thông tin CHI TIẾT (không tóm tắt quá mức):\n\n"
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
        """Regex/Keywords fallback — cố gắng extract chi tiết nhất có thể."""
        objective_parts = []
        setup_parts = []
        tasks_list = []
        rubric_parts = []
        pitfalls = []
        timeline_parts = []
        file_summaries = []

        kw_objective = ["mục tiêu", "objective", "bối cảnh", "giới thiệu", "đề bài", "de-bai", "lời nói đầu", "lý thuyết", "tổng quan"]
        kw_setup     = ["cài đặt", "setup", "chuẩn bị", "prerequisite", "install", "môi trường", "cấu trúc thư mục"]
        kw_tasks     = [
            "task", "bước", "yêu cầu", "checkpoint", "cp", "nhiệm vụ", "mốc",
            "thiết kế", "xây dựng", "implement", "build", "lắp", "lắp ráp",
            "agent", "tool", "prototype", "phase", "giai đoạn", "thực hành",
            "setup", "evaluation", "baseline", "code", "chatbot", "prompt",
            "failed trace", "test tool", "react",
        ]
        kw_rubrics   = ["rubric", "chấm", "nghiệm thu", "tiêu chí", "đánh giá", "scoring", "bảng chấm", "so sánh"]
        kw_pitfalls  = ["lưu ý", "chú ý", "bẫy", "pitfall", "rủi ro", "chỗ khó", "cảnh báo", "bảo mật", "ghi nhớ"]
        kw_timeline  = ["thời gian", "phút", "giờ", "timeline", "lịch trình", "lộ trình", "kịch bản thời gian", "tiến độ"]

        def _clean_heading(text: str) -> str:
            """Làm sạch heading: bỏ emoji, số thứ tự '1. ', ký tự đặc biệt đầu dòng."""
            import re
            # Bỏ emoji/icon đầu dòng (kí tự có codepoint > 0x1F000)
            parts = text.strip().split(None, 1)
            if parts:
                first_word = parts[0]
                if any(ord(c) > 0x1F000 for c in first_word) or all(not c.isalnum() for c in first_word):
                    text = parts[1] if len(parts) > 1 else ''
                    parts = text.strip().split(None, 1)
                    if parts:
                        text = parts[0] + (' ' + parts[1] if len(parts) > 1 else '')
            # Bỏ số thứ tự kiểu "1. ", "2) "
            text = re.sub(r'^\d+[\.\)]\s*', '', text.strip())
            # Bỏ số La Mã ở đầu
            text = re.sub(r'^[IVX]+[\.\)]\s*', '', text)
            # Bỏ dash/pipe
            text = text.lstrip('—-|: ').strip()
            return text

        def _extract_bullets(content: str) -> list:
            items = []
            for line in content.split("\n"):
                s = line.strip()
                if s.startswith(("- ", "* ", "+ ")):
                    items.append(s[2:].strip())
                elif s and s[0].isdigit() and ". " in s[:4]:
                    items.append(s[s.index(". ")+2:].strip())
            return items[:8]

        def _extract_mermaid_title(content: str) -> str:
            """Trích xuất title từ mermaid block để dùng làm timeline text."""
            import re
            # Tìm "title ..." trong mermaid block
            m = re.search(r'title\s+(.+)', content)
            if m:
                return m.group(1).strip()
            # Tìm dòng không phải code trong mermaid
            for line in content.split('\n'):
                s = line.strip()
                if s and not s.startswith('`') and not s.startswith('%%') and s != 'timeline' and len(s) > 10:
                    return s
            return content[:200]

        for doc in documents:
            fn = doc.get("file_name", doc.get("relative_path", "unknown"))

            # File summary: từ heading đầu tiên + content preview
            sections = doc.get("sections", [])
            if sections:
                first_heading = sections[0]["heading"] if sections else fn
                first_content = sections[0]["content"][:200] if sections and sections[0].get("content") else ""
                file_summaries.append({
                    "file": fn,
                    "summary": f"{first_heading}: {first_content[:150]}..."
                })

            # Gom sections theo level-2: mỗi level-2 heading hấp thụ content của level-3+ sections sau nó
            merged_l2 = {}  # heading -> {"content": str, "level": int}
            for i, section in enumerate(sections):
                if section.get("level", 2) == 2:
                    merged_l2[i] = {"heading": section["heading"], "content": section.get("content", ""), "level": 2}
                    # Merge content từ các level-3+ sections tiếp theo cho đến level-2 tiếp theo
                    combined_content = section.get("content", "")
                    for j in range(i + 1, len(sections)):
                        if sections[j].get("level", 2) <= 2:
                            break
                        sub_content = sections[j].get("content", "")
                        if sub_content.strip():
                            combined_content += "\n" + sub_content.strip()
                    merged_l2[i]["combined"] = combined_content

            for idx, section in enumerate(sections):
                heading = section["heading"].lower()
                raw_content = section["content"].strip()
                if not raw_content:
                    continue

                # Xử lý mermaid content cho timeline
                content_clean = raw_content
                if 'mermaid' in raw_content[:50] or '```' in raw_content[:50]:
                    content_clean = _extract_mermaid_title(raw_content)

                # Dùng combined_content nếu section là level-2 (đã gom từ sub-sections)
                if section.get("level", 2) == 2 and idx in merged_l2:
                    combined_content = merged_l2[idx].get("combined", raw_content)
                else:
                    combined_content = raw_content

                if any(k in heading for k in kw_objective):
                    objective_parts.append(combined_content[:500])
                elif any(k in heading for k in kw_setup):
                    setup_parts.append(combined_content[:600])
                elif any(k in heading for k in kw_rubrics):
                    rubric_parts.append(combined_content[:600])
                elif any(k in heading for k in kw_timeline):
                    timeline_text = content_clean if content_clean != raw_content else combined_content
                    timeline_parts.append(timeline_text[:300])
                elif any(k in heading for k in kw_pitfalls):
                    pitfalls.append(f"[{fn}] {section['heading']}: {combined_content[:200]}")
                elif any(k in heading for k in kw_tasks):
                    if section.get("level", 2) == 2:
                        checklist = _extract_bullets(combined_content)
                        clean_name = _clean_heading(section["heading"])
                        if len(clean_name) >= 5:
                            tasks_list.append({
                                "name": clean_name or section["heading"],
                                "description": combined_content[:400],
                                "checklist": checklist if checklist else _extract_bullets(combined_content[:800]),
                                "deliverable": "",
                                "estimated_minutes": None
                            })

        # Merge & build output
        lab_objective = "\n\n".join(objective_parts[:3]) or "Xem chi tiết trong tài liệu đính kèm."
        setup_instructions = "\n\n".join(setup_parts[:2]) or "Làm theo hướng dẫn trong README.md."
        grading_rubrics = "\n\n".join(rubric_parts[:2]) or "Xem rubric trong tài liệu."
        timeline = "\n".join(timeline_parts[:2]) or ""

        if not tasks_list:
            # Fallback: tạo tasks từ H2 sections, LOẠI bỏ rubric/objective/timeline/pitfalls
            skip_kw = kw_rubrics + kw_objective + kw_timeline + kw_pitfalls + ["cấu trúc", "danh sách", "phân công"]
            # Ưu tiên sections từ file hướng dẫn chính (CODELAB, guide) — không lấy từ reference docs
            prefer_files = ["codelab", "guide", "readme"]
            secondary_files = ["phan_cong", "danh_sach", "de_tai", "trace", "eval"]
            h2_sections = []
            for doc in documents:
                fn = doc.get("file_name", doc.get("relative_path", "")).lower()
                for sec in doc.get("sections", []):
                    if sec.get("level") != 2:
                        continue
                    h = sec.get("heading", "").lower()
                    if any(k in h for k in skip_kw):
                        continue
                    # Skip nếu là reference doc không có nội dung task
                    if any(rf in fn for rf in secondary_files):
                        continue
                    h2_sections.append((sec, fn))
            # Ưu tiên sections từ file chính (codelab, guide)
            h2_sections.sort(key=lambda x: not any(pf in x[1] for pf in prefer_files))
            for sec, fn in h2_sections:
                    clean_name = _clean_heading(sec["heading"])
                    bullets = _extract_bullets(sec.get("content", ""))
                    tasks_list.append({
                        "name": clean_name or sec["heading"],
                        "description": sec.get("content", "")[:300],
                        "checklist": bullets if bullets else [clean_name],
                        "deliverable": "",
                        "estimated_minutes": None
                    })
            if not tasks_list:
                tasks_list = [{"name": "Hoàn thành bài lab", "description": "Làm theo hướng dẫn trong tài liệu.",
                               "checklist": ["Đọc kỹ tài liệu", "Làm theo từng bước", "Nộp bài đúng hạn"],
                               "deliverable": "", "estimated_minutes": None}]

        if not pitfalls:
            pitfalls = ["Kiểm tra kỹ file .env trước khi chạy.", "Không commit API key lên GitHub.",
                        "Đọc kỹ rubric để không bỏ sót tiêu chí chấm điểm."]

        return {
            "lab_objective": lab_objective,
            "timeline": timeline,
            "setup_instructions": setup_instructions,
            "tasks": tasks_list,
            "grading_rubrics": grading_rubrics,
            "common_pitfalls": pitfalls,
            "file_summaries": file_summaries,
        }
