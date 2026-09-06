"""Transactional portable conversation storage. No browser storage required."""
import sqlite3
import uuid
from contextlib import contextmanager


class Store:
    def __init__(self, root):
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / "myai.sqlite3"
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS chats (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL,
                    updated TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id TEXT NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
                    role TEXT NOT NULL, content TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'complete');
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA synchronous=FULL")
        # Default rollback journal avoids WAL sidecars when transporting the drive.
        try:
            with db:
                yield db
        finally:
            db.close()

    def list(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute(
                "SELECT * FROM chats ORDER BY updated DESC, rowid DESC")]

    def create(self, title="New conversation"):
        cid = str(uuid.uuid4())
        with self.connect() as db:
            db.execute("INSERT INTO chats(id,title) VALUES (?,?)", (cid, title[:100]))
        return self.get(cid)

    def get(self, cid):
        with self.connect() as db:
            row = db.execute("SELECT * FROM chats WHERE id=?", (cid,)).fetchone()
            if row is None:
                raise KeyError("Conversation not found")
            chat = dict(row)
            chat["messages"] = [dict(r) for r in db.execute(
                "SELECT role,content,status FROM messages WHERE chat_id=? ORDER BY id", (cid,))]
            return chat

    def add(self, cid, role, content, status="complete"):
        with self.connect() as db:
            db.execute("INSERT INTO messages(chat_id,role,content,status) VALUES (?,?,?,?)",
                       (cid, role, content, status))
            db.execute("UPDATE chats SET updated=strftime('%Y-%m-%d %H:%M:%f','now') WHERE id=?", (cid,))
            if role == "user":
                db.execute("UPDATE chats SET title=? WHERE id=? AND title='New conversation'",
                           (content[:80], cid))

    def delete(self, cid):
        with self.connect() as db:
            db.execute("DELETE FROM chats WHERE id=?", (cid,))

    def backup(self, destination):
        with self.connect() as db:
            target = sqlite3.connect(destination)
            try:
                db.backup(target)
            finally:
                target.close()
