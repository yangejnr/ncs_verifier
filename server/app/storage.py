from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.config import settings


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(settings.database_path), exist_ok=True)
    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS references (
                id TEXT PRIMARY KEY,
                doc_type TEXT NOT NULL,
                version TEXT NOT NULL,
                metadata TEXT NOT NULL,
                image_path TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                doc_type TEXT,
                stage TEXT NOT NULL,
                percent INTEGER NOT NULL,
                message TEXT,
                result TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def add_reference(
    ref_id: str,
    doc_type: str,
    version: str,
    metadata: Dict[str, Any],
    image_path: str,
) -> None:
    created_at = datetime.utcnow().isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO references (id, doc_type, version, metadata, image_path, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (ref_id, doc_type, version, json.dumps(metadata), image_path, created_at),
        )
        conn.commit()


def list_references() -> List[Dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM references ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in rows]


def get_reference(ref_id: str) -> Optional[Dict[str, Any]]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM references WHERE id = ?", (ref_id,)).fetchone()
        return dict(row) if row else None


def create_session(session_id: str, doc_type: Optional[str]) -> None:
    created_at = datetime.utcnow().isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO sessions (id, doc_type, stage, percent, message, result, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (session_id, doc_type, "queued", 0, None, None, created_at),
        )
        conn.commit()


def update_session_status(
    session_id: str,
    stage: str,
    percent: int,
    message: Optional[str] = None,
) -> None:
    with _connect() as conn:
        conn.execute(
            """
            UPDATE sessions SET stage = ?, percent = ?, message = ? WHERE id = ?
            """,
            (stage, percent, message, session_id),
        )
        conn.commit()


def update_session_result(session_id: str, result: Dict[str, Any]) -> None:
    with _connect() as conn:
        conn.execute(
            """
            UPDATE sessions SET result = ?, stage = ?, percent = ? WHERE id = ?
            """,
            (json.dumps(result), "done", 100, session_id),
        )
        conn.commit()


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return dict(row) if row else None
