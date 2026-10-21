"""SQLite transcript, project facts and an operation journal independent of checkpoints."""

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def execution_lock(directory: Path):
    """One desktop operation per workspace, across processes; released by the OS on exit."""
    stream = (directory / "execution.lock").open("a+b")
    locked = False
    try:
        if (directory / "execution.lock").stat().st_size == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise BlockingIOError("Another agent operation is running in this workspace.") from exc
        locked = True
        yield
    finally:
        if locked:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)
        stream.close()


class SessionStore:
    def __init__(self, directory: Path):
        self.directory = directory.resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "sessions.sqlite3"
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, provider TEXT NOT NULL,
                    created TEXT NOT NULL, updated TEXT NOT NULL, status TEXT NOT NULL,
                    data TEXT NOT NULL DEFAULT '{}'
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id),
                    role TEXT NOT NULL, content TEXT NOT NULL, created TEXT NOT NULL,
                    detail TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS messages_session ON messages(session_id,created);
                CREATE TABLE IF NOT EXISTS operations (
                    id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id),
                    tool TEXT NOT NULL, arguments TEXT NOT NULL, status TEXT NOT NULL,
                    result TEXT, created TEXT NOT NULL
                );
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def create(self, title: str, provider: str) -> dict:
        identifier, timestamp = uuid4().hex, now()
        with self.connect() as db:
            db.execute(
                "INSERT INTO sessions VALUES (?,?,?,?,?,?,?)",
                (
                    identifier,
                    title.strip()[:120] or "New conversation",
                    provider,
                    timestamp,
                    timestamp,
                    "idle",
                    json.dumps({"facts": {}, "jobs": []}),
                ),
            )
        return self.get(identifier)

    def get(self, identifier: str) -> dict:
        with self.connect() as db:
            row = db.execute("SELECT * FROM sessions WHERE id=?", (identifier,)).fetchone()
        if row is None:
            raise ValueError("Session not found.")
        result = dict(row)
        result["data"] = json.loads(result["data"])
        return result

    def list(self) -> list[dict]:
        with self.connect() as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT id,title,provider,created,updated,status FROM sessions ORDER BY updated DESC"
                )
            ]

    def delete(self, identifier: str) -> None:
        self.get(identifier)
        with self.connect() as db:
            db.execute("DELETE FROM operations WHERE session_id=?", (identifier,))
            db.execute("DELETE FROM messages WHERE session_id=?", (identifier,))
            db.execute("DELETE FROM sessions WHERE id=?", (identifier,))

    def update(
        self,
        identifier: str,
        *,
        status: str | None = None,
        data: dict | None = None,
        title: str | None = None,
    ) -> None:
        session = self.get(identifier)
        with self.connect() as db:
            db.execute(
                "UPDATE sessions SET status=?,data=?,title=?,updated=? WHERE id=?",
                (
                    status if status is not None else session["status"],
                    json.dumps(data if data is not None else session["data"], allow_nan=False),
                    title if title is not None else session["title"],
                    now(),
                    identifier,
                ),
            )

    def add_message(
        self,
        identifier: str,
        role: str,
        content: str,
        *,
        detail: dict | None = None,
        message_id: str | None = None,
    ) -> str:
        message_id = message_id or uuid4().hex
        with self.connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO messages VALUES (?,?,?,?,?,?)",
                (
                    message_id,
                    identifier,
                    role,
                    content,
                    now(),
                    json.dumps(detail or {}, allow_nan=False),
                ),
            )
        return message_id

    def messages(self, identifier: str) -> list[dict]:
        self.get(identifier)
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM messages WHERE session_id=? ORDER BY created,rowid", (identifier,)
            )
            return [{**dict(row), "detail": json.loads(row["detail"])} for row in rows]

    def operation(self, identifier: str) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM operations WHERE id=?", (identifier,)).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["result"] = json.loads(result["result"]) if result["result"] else None
        return result

    def begin_operation(self, identifier: str, session_id: str, tool: str, arguments: dict) -> bool:
        with self.connect() as db:
            cursor = db.execute(
                "INSERT OR IGNORE INTO operations VALUES (?,?,?,?,?,?,?)",
                (
                    identifier,
                    session_id,
                    tool,
                    json.dumps(arguments),
                    "running",
                    None,
                    now(),
                ),
            )
            return cursor.rowcount == 1

    def finish_operation(self, identifier: str, result: dict) -> None:
        with self.connect() as db:
            db.execute(
                "UPDATE operations SET status='completed',result=? WHERE id=?",
                (json.dumps(result, allow_nan=False), identifier),
            )

    def recover(self) -> None:
        with self.connect() as db:
            db.execute("UPDATE sessions SET status='interrupted' WHERE status='running'")
