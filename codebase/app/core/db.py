import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional
from app.core.config import settings


def get_db_connection() -> sqlite3.Connection:
    db_path = Path(settings.database_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Bảng lưu trữ metadata bài lab upload từ Admin
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
    
    # 2. Bảng lưu trữ dữ liệu chỉ mục RAG / Knowledge Base
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

    # 3. Bảng lưu trữ thông tin học viên & vai trò (users)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL,
            group_id TEXT,
            today_lab_id TEXT,
            today_lab_type TEXT,
            today_lab_title TEXT
        )
    """)

    # 4. Bảng lưu trữ thông tin room/channel chat nhóm (rooms)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rooms (
            room_id TEXT PRIMARY KEY,
            room_name TEXT NOT NULL,
            discord_channel_id TEXT NOT NULL,
            channel_name TEXT NOT NULL,
            added_members TEXT,
            is_private INTEGER DEFAULT 1,
            created_at TEXT NOT NULL
        )
    """)

    # 5. Bảng lưu trữ thông tin phân công task và tiến độ (assignments)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            task_id TEXT NOT NULL,
            task_title TEXT,
            deadline TEXT,
            status TEXT DEFAULT 'in_progress',
            completed_checklist INTEGER DEFAULT 0,
            total_checklist INTEGER DEFAULT 2,
            extension_count INTEGER DEFAULT 0
        )
    """)

    # 6. Bảng lưu trữ nhắc nhở (reminders)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            reminder_id TEXT PRIMARY KEY,
            target_id TEXT NOT NULL,
            remind_at TEXT NOT NULL,
            message TEXT NOT NULL,
            repeat_every_minutes INTEGER,
            status TEXT DEFAULT 'pending',
            created_at TEXT NOT NULL
        )
    """)

    # 7. Bảng lưu trữ lịch sử tin nhắn (messages)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            message_id TEXT PRIMARY KEY,
            target_id TEXT NOT NULL,
            message TEXT NOT NULL,
            attachments TEXT,
            delivered_at TEXT NOT NULL
        )
    """)

    # Nạp dữ liệu học viên mặc định (Seed Data) nếu chưa có
    cursor.execute("SELECT COUNT(*) as cnt FROM users")
    if cursor.fetchone()["cnt"] == 0:
        seed_users = [
            ("U123456", "Pham Duc Thien", "group_leader", "G01", "LAB05_GROUP", "group", "Xây dựng AI Agent Workflow"),
            ("U789012", "Nguyen Van A", "member", "G01", "LAB05_GROUP", "group", "Xây dựng AI Agent Workflow"),
            ("U345678", "Tran Thi B", "member", "G01", "LAB05_GROUP", "group", "Xây dựng AI Agent Workflow"),
            ("U999999", "Le Van C", "student", None, "LAB05_INDIVIDUAL", "individual", "Bài lab cá nhân Python Basis"),
        ]
        cursor.executemany(
            """
            INSERT INTO users (user_id, full_name, role, group_id, today_lab_id, today_lab_type, today_lab_title)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            seed_users
        )
    
    conn.commit()
    conn.close()


# Khởi tạo DB sẵn sàng
init_db()
