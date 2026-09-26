"""
Long-term + short-term memory for the assistant.

- Short-term: recent turns of a session, used verbatim as context.
- Long-term: every message ever exchanged, searchable by keyword, plus a
  running "profile" of facts the assistant has learned about you — this is
  what lets it remember you across sessions and restarts.
"""
import sqlite3
import time
from pathlib import Path
from typing import List, Dict


class Memory:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    ts REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS profile (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_ts REAL NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_session ON messages(session_id)")

    # ---- conversation history -------------------------------------------------
    def add_message(self, session_id: str, role: str, content: str):
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO messages (session_id, role, content, ts) VALUES (?, ?, ?, ?)",
                (session_id, role, content, time.time()),
            )

    def recent_history(self, session_id: str, limit: int = 20) -> List[Dict[str, str]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT role, content FROM messages WHERE session_id=? ORDER BY id DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        return [{"role": r, "content": c} for r, c in reversed(rows)]

    def search(self, query: str, limit: int = 5) -> List[str]:
        """Simple keyword search across ALL past sessions — this is how the
        assistant recalls something you told it weeks ago in a different chat."""
        terms = [t for t in query.lower().split() if len(t) > 2]
        if not terms:
            return []
        with self._connect() as conn:
            like_clause = " OR ".join(["LOWER(content) LIKE ?"] * len(terms))
            params = [f"%{t}%" for t in terms]
            rows = conn.execute(
                f"SELECT content FROM messages WHERE {like_clause} ORDER BY id DESC LIMIT ?",
                (*params, limit),
            ).fetchall()
        return [r[0] for r in rows]

    # ---- user profile (the "model of who you are") -----------------------------
    def set_fact(self, key: str, value: str):
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO profile (key, value, updated_ts) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_ts=excluded.updated_ts",
                (key, value, time.time()),
            )

    def get_profile(self) -> Dict[str, str]:
        with self._connect() as conn:
            rows = conn.execute("SELECT key, value FROM profile").fetchall()
        return dict(rows)

    def profile_as_text(self) -> str:
        profile = self.get_profile()
        if not profile:
            return "No profile facts learned yet."
        return "\n".join(f"- {k}: {v}" for k, v in profile.items())
