"""
Database Manager for YouTube Study Notes Tool using SQLite.
Stores history, metadata, notes markdown, and PDF documents.
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
    """Initialize the database tables if they do not exist."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS study_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        conn.commit()


def save_study_record(
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
    """Save or update a study session in the database."""
    init_db()
    
    if pdf_bytes is None and os.path.exists(pdf_path):
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

    pdf_filename = Path(pdf_path).name

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO study_history (
                video_id, url, title, channel, duration, thumbnail_url,
                playlist_title, notes_markdown, transcript_text,
                pdf_filename, pdf_path, pdf_blob, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
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


def get_all_records(search_query: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve all study records ordered by newest first, with optional search."""
    init_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if search_query and search_query.strip():
            term = f"%{search_query.strip()}%"
            cursor.execute("""
                SELECT id, video_id, url, title, channel, duration, thumbnail_url,
                       playlist_title, pdf_filename, pdf_path, created_at,
                       LENGTH(notes_markdown) as markdown_length
                FROM study_history
                WHERE title LIKE ? OR channel LIKE ? OR playlist_title LIKE ?
                ORDER BY id DESC
            """, (term, term, term))
        else:
            cursor.execute("""
                SELECT id, video_id, url, title, channel, duration, thumbnail_url,
                       playlist_title, pdf_filename, pdf_path, created_at,
                       LENGTH(notes_markdown) as markdown_length
                FROM study_history
                ORDER BY id DESC
            """)
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_record_by_id(record_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve full record including markdown and PDF blob by ID."""
    init_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM study_history WHERE id = ?", (record_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None


def delete_record(record_id: int) -> bool:
    """Delete a record by ID."""
    init_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM study_history WHERE id = ?", (record_id,))
        conn.commit()
        return cursor.rowcount > 0


def get_db_stats() -> Dict[str, Any]:
    """Get high level statistics for the history dashboard."""
    init_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*), COUNT(DISTINCT channel) FROM study_history")
        total_notes, total_channels = cursor.fetchone()
        return {
            'total_notes': total_notes or 0,
            'total_channels': total_channels or 0
        }
