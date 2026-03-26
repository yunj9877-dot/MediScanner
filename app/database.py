"""
MediScanner SQLite 데이터베이스
====================================
상담 히스토리 저장 + 사용자 건강 프로필 관리
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "mediscanner.db")


def get_connection():
    """SQLite 연결 반환"""
    db_path = os.path.abspath(DB_PATH)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """테이블 생성 (앱 시작 시 호출)"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_profile (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT UNIQUE NOT NULL,
            name TEXT DEFAULT '',
            age INTEGER DEFAULT 0,
            diseases TEXT DEFAULT '',
            medications TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT DEFAULT 'default',
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            answer_mode TEXT DEFAULT 'simple',
            sources TEXT DEFAULT '',
            drug_names TEXT DEFAULT '',
            tokens_input INTEGER DEFAULT 0,
            tokens_output INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)

    conn.commit()
    conn.close()
    print("✅ SQLite DB 초기화 완료")


# ── 상담 히스토리 ──

def save_chat(user_id: str, question: str, answer: str, answer_mode: str = "simple",
              sources: str = "", drug_names: str = "",
              tokens_input: int = 0, tokens_output: int = 0):
    """상담 내역 저장"""
    conn = get_connection()
    conn.execute(
        """INSERT INTO chat_history 
           (user_id, question, answer, answer_mode, sources, drug_names, tokens_input, tokens_output)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, question, answer, answer_mode, sources, drug_names, tokens_input, tokens_output)
    )
    conn.commit()
    conn.close()


def get_chat_history(user_id: str = "default", limit: int = 50):
    """상담 내역 조회 (최신순)"""
    conn = get_connection()
    rows = conn.execute(
        """SELECT id, question, answer, answer_mode, sources, drug_names, 
                  tokens_input, tokens_output, created_at
           FROM chat_history WHERE user_id = ?
           ORDER BY id DESC LIMIT ?""",
        (user_id, limit)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def clear_chat_history(user_id: str = "default"):
    """상담 내역 삭제"""
    conn = get_connection()
    conn.execute("DELETE FROM chat_history WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


# ── 건강 프로필 ──

def save_profile(user_id: str, name: str = "", age: int = 0,
                 diseases: str = "", medications: str = ""):
    """건강 프로필 저장 (없으면 생성, 있으면 업데이트)"""
    conn = get_connection()
    conn.execute(
        """INSERT INTO user_profile (user_id, name, age, diseases, medications)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(user_id) DO UPDATE SET
             name = excluded.name,
             age = excluded.age,
             diseases = excluded.diseases,
             medications = excluded.medications,
             updated_at = datetime('now', 'localtime')""",
        (user_id, name, age, diseases, medications)
    )
    conn.commit()
    conn.close()


def get_profile(user_id: str = "default"):
    """건강 프로필 조회"""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM user_profile WHERE user_id = ?", (user_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_profile(user_id: str = "default"):
    """건강 프로필 삭제"""
    conn = get_connection()
    conn.execute("DELETE FROM user_profile WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
