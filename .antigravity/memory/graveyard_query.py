#!/usr/bin/env python3
"""
The Graveyard RAG Query Interface.
Stores past failed code attempts, sanitizer stack traces, and compiler errors.
Queries vector or hash-indexed failure patterns to inject negative prompts into The Artificer.
"""

import json
import sys
import os
import sqlite3
from typing import List, Dict

DB_PATH = os.path.join(os.path.dirname(__file__), "graveyard_db", "graveyard.sqlite3")

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS failures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                feature_name TEXT,
                iteration INTEGER,
                failed_code TEXT,
                error_category TEXT,
                error_log TEXT,
                negative_lesson TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

def record_failure(feature_name: str, iteration: int, failed_code: str,
                   error_category: str, error_log: str, negative_lesson: str):
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO failures (feature_name, iteration, failed_code, error_category, error_log, negative_lesson)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (feature_name, iteration, failed_code, error_category, error_log, negative_lesson))
        conn.commit()

def query_negative_prompts(feature_name: str, top_k: int = 3) -> List[str]:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT negative_lesson FROM failures
            WHERE feature_name = ?
            ORDER BY id DESC LIMIT ?
        """, (feature_name, top_k))
        rows = cursor.fetchall()
        return [r[0] for r in rows]

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "record":
        # Example record usage
        feature = sys.argv[2] if len(sys.argv) > 2 else "generic"
        record_failure(feature, 1, "// failed code", "Sanitizer/ASan", "heap-use-after-free",
                       "Do not return std::string_view pointing to temporary stack buffers.")
        print("Failure recorded.")
    else:
        feature = sys.argv[1] if len(sys.argv) > 1 else "generic"
        lessons = query_negative_prompts(feature)
        print(json.dumps({"feature": feature, "negative_constraints": lessons}, indent=2))
