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
            CREATE TABLE IF NOT EXISTS reference_items (
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
            CREATE TABLE IF NOT EXISTS audit_logs (
                id TEXT PRIMARY KEY,
                doc_type TEXT,
                reference_id TEXT,
                result_json TEXT NOT NULL,
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
            INSERT INTO reference_items (id, doc_type, version, metadata, image_path, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (ref_id, doc_type, version, json.dumps(metadata), image_path, created_at),
        )
        conn.commit()


def list_references() -> List[Dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM reference_items ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in rows]


def get_reference(ref_id: str) -> Optional[Dict[str, Any]]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM reference_items WHERE id = ?", (ref_id,)).fetchone()
        return dict(row) if row else None


def add_audit_log(audit_id: str, doc_type: Optional[str], reference_id: Optional[str], result: Dict[str, Any]) -> None:
    created_at = datetime.utcnow().isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO audit_logs (id, doc_type, reference_id, result_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (audit_id, doc_type, reference_id, json.dumps(result), created_at),
        )
        conn.commit()
