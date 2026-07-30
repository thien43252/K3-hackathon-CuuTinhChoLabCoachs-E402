import os
import re
from typing import List, Dict, Any

class LabDocProcessor:
    """
    Workflow xử lý tài liệu đặc thù cho các bài Lab:
    Tìm kiếm, đọc và trích xuất cấu trúc thông tin từ tất cả các file .md trong Repo Lab
    để chuẩn bị dữ liệu sạch, có cấu trúc cho Agent/Học viên sử dụng.
    """
    
    def __init__(self, repo_path: str):
        self.repo_path = os.path.abspath(repo_path)
        
    def find_all_markdown_files(self) -> List[str]:
        """
        Tìm tất cả các file .md trong thư mục repo (bỏ qua các thư mục ẩn/git).
        """
        md_files = []
        for root, dirs, files in os.walk(self.repo_path):
            # Bỏ qua các thư mục ẩn như .git, .venv
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for file in files:
                if file.endswith('.md'):
                    full_path = os.path.join(root, file)
                    md_files.append(full_path)
        return md_files

    def parse_markdown_content(self, file_path: str) -> Dict[str, Any]:
        """
        Phân tích cú pháp file Markdown để trích xuất cấu trúc tiêu đề, mã code và các phần hướng dẫn quan trọng.
        """
        relative_path = os.path.relpath(file_path, self.repo_path)
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 1. Trích xuất Tiêu đề chính (H1)
        h1_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        title = h1_match.group(1).strip() if h1_match else relative_path
        
        # 2. Phân tích cấu trúc tiêu đề (Headings) và chia nhỏ nội dung (Chunking)
        headings = []
        sections = []
        
        # Tìm tất cả các dòng tiêu đề (# H1, ## H2, ### H3, ...)
        heading_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
        matches = list(heading_pattern.finditer(content))
        
        # Chia nhỏ nội dung dựa trên tiêu đề
        for i, match in enumerate(matches):
            level = len(match.group(1))
            heading_text = match.group(2).strip()
            start_pos = match.end()
            
            # Nội dung của phần này kéo dài đến tiêu đề tiếp theo
            end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            section_content = content[start_pos:end_pos].strip()
            
            headings.append({
                "level": level,
                "text": heading_text
            })
            
            sections.append({
                "heading": heading_text,
                "level": level,
                "content": section_content
            })

        # 3. Trích xuất các khối mã nguồn (Code Blocks)
        code_blocks = []
        code_pattern = re.compile(r'```(\w*)\n(.*?)```', re.DOTALL)
        for code_match in code_pattern.finditer(content):
            language = code_match.group(1).strip() or "text"
            code_content = code_match.group(2).strip()
            code_blocks.append({
                "language": language,
                "code": code_content
            })

        # 4. Trích xuất các liên kết (Links) mẫu
        links = []
        link_pattern = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
        for link_match in link_pattern.finditer(content):
            text = link_match.group(1).strip()
            url = link_match.group(2).strip()
            links.append({
                "text": text,
                "url": url
            })

        return {
            "file_name": os.path.basename(file_path),
            "relative_path": relative_path,
            "title": title,
            "headings": headings,
            "sections": sections,
            "code_blocks": code_blocks,
            "links": links,
            "raw_content": content
        }

    def process_repository(self) -> Dict[str, Any]:
        """
        Workflow chính: Quét toàn bộ repository, đọc và cấu trúc hóa tất cả tài liệu.
        
        Returns:
            Dict: Chứa metadata của repo và danh sách tài liệu đã được phân tích chi tiết.
        """
        md_files = self.find_all_markdown_files()
        documents = []
        
        # Tạo bản đồ tổng quan cấu trúc thư mục tài liệu
        sitemap = []
        
        for file_path in md_files:
            try:
                doc_info = self.parse_markdown_content(file_path)
                documents.append(doc_info)
                sitemap.append({
                    "title": doc_info["title"],
                    "relative_path": doc_info["relative_path"]
                })
            except Exception as e:
                print(f"⚠️ Lỗi khi xử lý file {file_path}: {e}")
                
        return {
            "repo_path": self.repo_path,
            "total_documents": len(documents),
            "sitemap": sitemap,
            "documents": documents
        }
