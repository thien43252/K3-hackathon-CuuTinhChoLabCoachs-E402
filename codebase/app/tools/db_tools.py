"""
Database & State Management Tools
Manages lab assignments, progress, and system state using SQLite.
"""

import sqlite3
import json
from typing import Dict, List, Optional
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', 'app.db')

def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS labs (
            lab_id TEXT PRIMARY KEY,
            title TEXT,
            type TEXT,
            description TEXT,
            lecture_files TEXT,
            codebase_repo_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id TEXT,
            task_id TEXT,
            user_id TEXT,
            status TEXT DEFAULT 'pending', 
            deadline TIMESTAMP,
            extension_count INTEGER DEFAULT 0,
            extension_reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def upload_lab_material(lab_id: str, title: str, type: str, description: str, lecture_files: list, codebase_repo_url: str) -> bool:
    """Admin tải nội dung lab, bài giảng, codebase"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT OR REPLACE INTO labs (lab_id, title, type, description, lecture_files, codebase_repo_url)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (lab_id, title, type, description, json.dumps(lecture_files), codebase_repo_url))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False
    finally:
        conn.close()

def get_user_context(user_id: str, date: str) -> Optional[Dict]:
    """Lấy ngữ cảnh user, lịch lab, vai trò, nhóm"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM labs ORDER BY created_at DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def assign_task(group_id: str, assignments: list) -> bool:
    """Lưu vết phân công task cho từng người"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        for assign in assignments:
            cursor.execute('''
                INSERT INTO assignments (group_id, task_id, user_id, deadline)
                VALUES (?, ?, ?, ?)
            ''', (group_id, assign.get('task_id'), assign.get('user_id'), assign.get('deadline')))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False
    finally:
        conn.close()

def track_group_progress(group_id: str) -> List[Dict]:
    """Báo cáo % tiến độ hoàn thành bài lab nhóm"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT user_id, task_id, status, deadline 
        FROM assignments 
        WHERE group_id = ?
    ''', (group_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def extend_deadline(task_id: str, user_id: str, extra_minutes: int, reason: str) -> Dict:
    """Giãn mốc deadline hoàn thành task (tối đa 2 lần)"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT extension_count FROM assignments WHERE task_id = ? AND user_id = ?', (task_id, user_id))
        row = cursor.fetchone()
        if not row:
            return {"status": "error", "message": "Task not found"}
        
        count = row['extension_count']
        if count >= 2:
            return {"status": "error", "message": "MAX_EXTENSION_REACHED"}
            
        cursor.execute('''
            UPDATE assignments 
            SET extension_count = extension_count + 1, extension_reason = ?, status = 'in_progress'
            WHERE task_id = ? AND user_id = ?
        ''', (reason, task_id, user_id))
        conn.commit()
        return {"status": "success", "message": f"Deadline extended. Extensions used: {count + 1}/2"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        conn.close()

def fetch_peer_solution(group_id: str, current_task_id: str, requesting_user_id: str) -> Optional[Dict]:
    """Tìm bài làm của đồng đội đã xong để tham khảo"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT user_id, task_id 
        FROM assignments 
        WHERE group_id = ? AND task_id = ? AND status = 'completed' AND user_id != ?
        LIMIT 1
    ''', (group_id, current_task_id, requesting_user_id))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"reference_user": row["user_id"], "note": "Tham khảo bài của thành viên này"}
    return None
