"""Explicit local memory and document retrieval. No silent conversation harvesting."""
import hashlib
import unicodedata
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path


class Knowledge:
    def __init__(self, root, uploader):
        self.path = Path(root) / 'knowledge.sqlite3'
        self.uploader = uploader
        self.lock = threading.RLock()
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS items (
                    id TEXT PRIMARY KEY, kind TEXT NOT NULL, title TEXT NOT NULL,
                    content TEXT NOT NULL DEFAULT '', scope TEXT NOT NULL DEFAULT '',
                    upload_id TEXT, digest TEXT, state TEXT NOT NULL DEFAULT 'ready',
                    detail TEXT NOT NULL DEFAULT '', file_sig TEXT NOT NULL DEFAULT '', updated REAL NOT NULL);
                CREATE UNIQUE INDEX IF NOT EXISTS upload_scope ON items(upload_id, scope);
                CREATE VIRTUAL TABLE IF NOT EXISTS passages USING fts5(
                    item_id UNINDEXED, page UNINDEXED, title, text, tokenize='unicode61');
            ''')
            columns = {r[1] for r in db.execute('PRAGMA table_info(items)')}
            if 'file_sig' not in columns:
                db.execute("ALTER TABLE items ADD COLUMN file_sig TEXT NOT NULL DEFAULT ''")

    @contextmanager
    def connect(self):
        with self.lock:
            db = sqlite3.connect(self.path, timeout=10)
            db.row_factory = sqlite3.Row
            try:
                with db:
                    yield db
            finally:
                db.close()

    def scope(self, value):
        if value in ('', None):
            return ''
        if not isinstance(value, str) or len(value) > 2000:
            raise ValueError('Scope must be a project folder path.')
        path = Path(value).expanduser()
        if not path.is_absolute():
            raise ValueError('Choose an absolute project folder path.')
        return str(path.resolve())

    def get(self, ident):
        with self.connect() as db:
            row = db.execute('SELECT * FROM items WHERE id=?', (ident,)).fetchone()
            if not row:
                raise ValueError('Saved item not found.')
            return dict(row)

    def list(self):
        self.refresh_documents()
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT * FROM items ORDER BY updated DESC')]

    def index(self, db, ident, title, passages):
        db.execute('DELETE FROM passages WHERE item_id=?', (ident,))
        for passage in passages:
            content = passage['text']
            for offset in range(0, len(content), 1800):
                chunk = content[offset:offset + 2000]
                if chunk.strip():
                    db.execute('INSERT INTO passages(item_id,page,title,text) VALUES (?,?,?,?)',
                               (ident, passage.get('page'), title, chunk))

    def save_memory(self, body):
        title, content = body.get('title', ''), body.get('content', '')
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 120:
            raise ValueError('Give the memory a title of 1–120 characters.')
        if not isinstance(content, str) or not 1 <= len(content.strip()) <= 6000:
            raise ValueError('Memory must contain 1–6,000 characters.')
        scope = self.scope(body.get('scope'))
        ident = body.get('id')
        with self.connect() as db:
            if ident:
                old = db.execute('SELECT kind FROM items WHERE id=?', (ident,)).fetchone()
                if not old or old['kind'] != 'memory':
                    raise ValueError('Memory not found.')
                db.execute('UPDATE items SET title=?,content=?,scope=?,updated=? WHERE id=?',
                           (title.strip(), content.strip(), scope, time.time(), ident))
            else:
                self.check_capacity(db)
                ident = uuid.uuid4().hex
                db.execute('INSERT INTO items(id,kind,title,content,scope,updated) VALUES (?,?,?,?,?,?)',
                           (ident, 'memory', title.strip(), content.strip(), scope, time.time()))
            self.index(db, ident, title.strip(), [{'page': None, 'text': content.strip()}])
        return self.get(ident)

    def check_capacity(self, db):
        if db.execute('SELECT count(*) FROM items').fetchone()[0] >= 500:
            raise ValueError('This local library supports 500 items. Forget unused items first.')

    def save_document(self, body):
        ident = body.get('upload_id')
        meta = self.uploader.metadata(ident)
        scope = self.scope(body.get('scope'))
        with self.connect() as db:
            row = db.execute('SELECT id FROM items WHERE upload_id=? AND scope=?', (ident, scope)).fetchone()
            if row:
                return self.get(row['id'])
            self.check_capacity(db)
            key = uuid.uuid4().hex
            db.execute('INSERT INTO items(id,kind,title,scope,upload_id,updated) VALUES (?,?,?,?,?,?)',
                       (key, 'document', meta['filename'], scope, ident, time.time()))
        self.refresh_document(key)
        return self.get(key)

    def refresh_document(self, ident):
        with self.lock:
            item = self.get(ident)
            try:
                path = self.uploader.find(item['upload_id'])
                stat = path.stat()
                signature = f'{stat.st_size}:{stat.st_mtime_ns}:{stat.st_ctime_ns}:{stat.st_ino}'
                if signature == item['file_sig'] and item['state'] != 'missing':
                    return
                h = hashlib.sha256()
                with path.open('rb') as f:
                    while chunk := f.read(65536):
                        h.update(chunk)
                digest = h.hexdigest()
                if digest == item['digest'] and item['state'] != 'missing':
                    with self.connect() as db:
                        db.execute('UPDATE items SET file_sig=? WHERE id=?', (signature, ident))
                    return
                meta = self.uploader.metadata(item['upload_id'])
                result = meta['extraction']
                state, detail = result['status'], result['detail']
                passages = result.get('passages', []) if state == 'ready' else []
            except (ValueError, FileNotFoundError, OSError):
                signature = ''
                digest, state, detail, passages = '', 'missing', 'Stored source is missing or unreadable; not used in answers.', []
            with self.connect() as db:
                # A concurrent Forget must never resurrect indexed passages.
                if not db.execute('SELECT 1 FROM items WHERE id=?', (ident,)).fetchone():
                    return
                self.index(db, ident, item['title'], passages)
                db.execute('UPDATE items SET digest=?,state=?,detail=?,updated=?,file_sig=? WHERE id=?',
                           (digest, state, detail, time.time(), signature, ident))

    def refresh_documents(self):
        with self.lock:
            with self.connect() as db:
                ids = [r[0] for r in db.execute("SELECT id FROM items WHERE kind='document'")]
            for ident in ids:
                self.refresh_document(ident)

    def forget(self, ident):
        with self.connect() as db:
            db.execute('DELETE FROM passages WHERE item_id=?', (ident,))
            db.execute('DELETE FROM items WHERE id=?', (ident,))
        return {'forgotten': True, 'original_upload_retained': True}

    def context(self, query, scope=''):
        self.refresh_documents()
        normalized = ''.join(c if unicodedata.category(c)[0] in 'LMN' else ' ' for c in query.lower())
        terms = list(dict.fromkeys(word for word in normalized.split() if len(word) >= 2))[:24]
        scope = self.scope(scope)
        with self.connect() as db:
            rows = []
            if terms:
                expression = ' OR '.join('"' + word.replace('"', '""') + '"' for word in terms)
                rows = db.execute('''SELECT p.item_id,p.page,snippet(passages,3,'','',' … ',64) AS text,i.title,i.kind,i.updated,i.upload_id
                    FROM passages p JOIN items i ON i.id=p.item_id
                    WHERE passages MATCH ? AND i.scope IN ('',?) AND i.state='ready'
                    ORDER BY bm25(passages) LIMIT 6''', (expression, scope)).fetchall()
            result = [{'citation': 'K' + str(n), **dict(row)} for n, row in enumerate(rows, 1)]
        return result

    def valid_refs(self, refs):
        with self.connect() as db:
            for ref in refs:
                row = db.execute('SELECT updated,state FROM items WHERE id=?', (ref.get('item_id'),)).fetchone()
                if not row or row['state'] != 'ready' or row['updated'] != ref.get('updated'):
                    return False
        return True
