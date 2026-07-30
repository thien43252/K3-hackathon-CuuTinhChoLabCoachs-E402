import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional
from app.core.config import settings


def get_db_connection() -> sqlite3.Connection:
    db_path = Path(settings.database_path)
    db_path.parent.mkdir(parents=os.path.join(db_path.parent), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Bảng lưu trữ metadata bài lab upload từ Admin
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lab_materials (
            lab_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            type TEXT NOT NULL,
            description TEXT NOT NULL,
            lecture_files TEXT,
            codebase_repo_url TEXT,
            created_at TEXT NOT NULL
        )
    """)
    
    # Bảng lưu trữ dữ liệu chỉ mục RAG / Knowledge Base
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lab_knowledge (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lab_id TEXT NOT NULL,
            source TEXT NOT NULL,
            content TEXT NOT NULL,
            keywords TEXT,
            created_at TEXT NOT NULL
        )
    """)
    
    conn.commit()
    conn.close()


# Khởi tạo DB sẵn sàng
init_db()
