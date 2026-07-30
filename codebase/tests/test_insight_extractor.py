import pytest
from app.services.insight_extractor import LabInsightExtractor

def test_insight_extraction_fallback_regex():
    """
    Test bộ trích xuất insight sử dụng cơ chế Fallback Regex (khi không có API key).
    Đảm bảo các cấu trúc chính của tài liệu Lab được gom nhóm và phân tích đúng.
    """
    mock_documents = [
        {
            "file_name": "README.md",
            "relative_path": "README.md",
            "raw_content": "",
            "sections": [
                {
                    "heading": "Giới thiệu & Mục tiêu cốt lõi",
                    "content": "Sinh viên cần xây dựng một AI Agent có khả năng hỗ trợ học tập tự động."
                },
                {
                    "heading": "Hướng dẫn cài đặt môi trường",
                    "content": "Hãy chạy lệnh `uv run main.py` để setup."
                },
                {
                    "heading": "Tiêu chí đánh giá bài làm",
                    "content": "Hoàn thành CP1 được 5 điểm. CP2 được 5 điểm."
                },
                {
                    "heading": "Một số lưu ý và bẫy lỗi hay gặp",
                    "content": "Tránh clone đè các thư mục hệ thống."
                }
            ]
        }
    ]

    extractor = LabInsightExtractor()
    # Ép buộc sử dụng regex fallback bằng cách xóa API key (nếu có) khỏi đối tượng test
    extractor.api_key = None

    insights = extractor.extract_insights(mock_documents)

    # Kiểm tra cấu trúc trả về
    assert "lab_objective" in insights
    assert "setup_instructions" in insights
    assert "tasks" in insights
    assert "grading_rubrics" in insights
    assert "common_pitfalls" in insights

    # Kiểm tra xem từ khóa Regex hoạt động đúng và phân nhóm chuẩn xác không
    assert "xây dựng một AI Agent" in insights["lab_objective"]
    assert "uv run main.py" in insights["setup_instructions"]
    assert "Hoàn thành CP1" in insights["grading_rubrics"]
    assert len(insights["common_pitfalls"]) > 0
    assert "Tránh clone đè" in insights["common_pitfalls"][0]
