"""
LLM & RAG Tools
Core AI functions for reasoning, generation, and analysis using Google Generative AI (Gemini).
"""

import os
import json
import google.generativeai as genai
from typing import Dict, List
from dotenv import load_dotenv

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    
model = genai.GenerativeModel('gemini-2.0-flash')

def codebase_indexer(lab_id: str, force_reindex: bool = False) -> bool:
    """Index dữ liệu lab vào Vector DB cho RAG (Mock implementation)"""
    print(f"Indexing codebase for lab {lab_id} (force={force_reindex})")
    return True

def RAG_search(query: str, lab_id: str, top_k: int = 3) -> List[str]:
    """Tra cứu kiến thức, ví dụ code từ tài liệu"""
    print(f"RAG search query '{query}' in lab {lab_id}")
    return ["Mock documentation snippet 1", "Mock code example 2"]

def parse_lab_requirements(lab_id: str, member_count: int) -> Dict:
    """Phân tích bài lab nhóm thành task & checklist"""
    prompt = f"""
    Bạn là một AI Trợ lý Học viên. Bài Lab ID: {lab_id} cần được phân chia cho {member_count} người.
    Hãy phân tích và chia bài lab thành các task nhỏ, có checklist cụ thể.
    Trả về định dạng JSON: {{"requirements": [{{"phase": "tên phase", "sub_task": "tên task", "checklist": ["item 1"]}}]}}
    """
    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(response_mime_type="application/json")
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Error: {e}")
        return {"requirements": []}

def generate_reflection(user_id: str, lab_id: str) -> str:
    """Sinh nhận xét/đánh giá cá nhân cuối buổi"""
    prompt = f"""
    Bạn là AI Trợ lý Học viên. Viết nhận xét (reflection) cho học viên {user_id} về bài lab {lab_id}.
    Động viên, khen ngợi và đưa ra bài học kinh nghiệm.
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return "Cảm ơn bạn đã tham gia bài lab!"

def analyze_student_issue(user_id: str, task_id: str, issue_description: str, error_log: str = "") -> str:
    """Phân tích log lỗi Terminal/IDE & gợi ý sửa"""
    prompt = f"""
    Học viên {user_id} đang gặp lỗi ở task {task_id}.
    Khó khăn: {issue_description}
    Log lỗi: {error_log}
    
    Hãy phân tích nguyên nhân lỗi và gợi ý (hint) cách sửa. KHÔNG giải hộ code.
    Giọng điệu thân thiện, hỗ trợ.
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return "Xin lỗi, tôi không phân tích được lỗi này. Hãy tham khảo code của đồng đội nhé!"
