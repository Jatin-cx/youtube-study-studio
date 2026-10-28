"""
Database Manager for YouTube Study Notes Tool using SQLite.
Stores history, metadata, notes markdown, and PDF documents with strict per-user isolation.
"""

import sqlite3
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

DB_PATH = Path("study_history.db")


def get_db_connection() -> sqlite3.Connection:
    """Create a connection to the SQLite database."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize the database tables if they do not exist and handle migrations."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS study_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL DEFAULT 'anonymous',
                video_id TEXT NOT NULL,
                url TEXT NOT NULL,
                title TEXT NOT NULL,
                channel TEXT NOT NULL,
                duration TEXT,
                thumbnail_url TEXT,
                playlist_title TEXT,
                notes_markdown TEXT NOT NULL,
                transcript_text TEXT,
                pdf_filename TEXT NOT NULL,
                pdf_path TEXT NOT NULL,
                pdf_blob BLOB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Check if user_id column exists (for backward compatibility migration)
        cursor.execute("PRAGMA table_info(study_history)")
        columns = [col['name'] for col in cursor.fetchall()]
        if 'user_id' not in columns:
            cursor.execute("ALTER TABLE study_history ADD COLUMN user_id TEXT DEFAULT 'anonymous'")
            
        conn.commit()


def save_study_record(
    user_id: str,
    video_id: str,
    url: str,
    title: str,
    channel: str,
    duration: str,
    thumbnail_url: str,
    playlist_title: Optional[str],
    notes_markdown: str,
    transcript_text: str,
    pdf_path: str,
    pdf_bytes: Optional[bytes] = None
) -> int:
    """Save a study session isolated to a specific user_id."""
    init_db()
    
    if pdf_bytes is None and os.path.exists(pdf_path):
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

    pdf_filename = Path(pdf_path).name

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO study_history (
                user_id, video_id, url, title, channel, duration, thumbnail_url,
                playlist_title, notes_markdown, transcript_text,
                pdf_filename, pdf_path, pdf_blob, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            video_id,
            url,
            title,
            channel,
            duration,
            thumbnail_url,
            playlist_title,
            notes_markdown,
            transcript_text,
            pdf_filename,
            pdf_path,
            pdf_bytes,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        conn.commit()
        return cursor.lastrowid


def get_all_records(user_id: str, search_query: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve study records strictly belonging to the given user_id."""
    init_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if search_query and search_query.strip():
            term = f"%{search_query.strip()}%"
            cursor.execute("""
                SELECT id, user_id, video_id, url, title, channel, duration, thumbnail_url,
                       playlist_title, pdf_filename, pdf_path, created_at,
                       LENGTH(notes_markdown) as markdown_length
                FROM study_history
                WHERE user_id = ? AND (title LIKE ? OR channel LIKE ? OR playlist_title LIKE ?)
                ORDER BY id DESC
            """, (user_id, term, term, term))
        else:
            cursor.execute("""
                SELECT id, user_id, video_id, url, title, channel, duration, thumbnail_url,
                       playlist_title, pdf_filename, pdf_path, created_at,
                       LENGTH(notes_markdown) as markdown_length
                FROM study_history
                WHERE user_id = ?
                ORDER BY id DESC
            """, (user_id,))
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_record_by_id(record_id: int, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieve full record by ID with optional user_id verification."""
    init_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if user_id:
            cursor.execute("SELECT * FROM study_history WHERE id = ? AND user_id = ?", (record_id, user_id))
        else:
            cursor.execute("SELECT * FROM study_history WHERE id = ?", (record_id,))
            
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None


def delete_record(record_id: int, user_id: str) -> bool:
    """Delete a record by ID strictly if owned by the user_id."""
    init_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM study_history WHERE id = ? AND user_id = ?", (record_id, user_id))
        conn.commit()
        return cursor.rowcount > 0


def get_db_stats(user_id: str) -> Dict[str, Any]:
    """Get statistics strictly for the current user."""
    init_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*), COUNT(DISTINCT channel) FROM study_history WHERE user_id = ?", (user_id,))
        total_notes, total_channels = cursor.fetchone()
        return {
            'total_notes': total_notes or 0,
            'total_channels': total_channels or 0
        }
