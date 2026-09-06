"""Bounded UTF-8 project files and reviewable, reversible model edits."""
import difflib
import json
import os
import re
import uuid
from pathlib import PurePosixPath

MAX_FILE = 60000
MAX_CONTEXT = 12000


class Workbench:
    def __init__(self, root):
        self.root = (root / 'data' / 'workbench').resolve()
        self.files = self.root / 'files'
        self.records = self.root / 'changes'
        self.files.mkdir(parents=True, exist_ok=True)
        self.records.mkdir(exist_ok=True)

    def path(self, name):
        if not isinstance(name, str) or len(name) > 200 or '\\' in name:
            raise ValueError('Invalid project path')
        parts = name.split('/')
        if any(not re.fullmatch(r'[A-Za-z0-9_. -]+', p) or p in ('.', '..') or p.endswith((' ', '.')) or ':' in p for p in parts):
            raise ValueError('Use ordinary relative filenames without .. or special characters.')
        if any(p.lower() in ('.git', '.env') or p.lower().startswith('.env.') or p.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(10)),*(f'LPT{i}' for i in range(10))} for p in parts):
            raise ValueError('Git metadata, environment secrets, and reserved names are excluded.')
        path = self.files / PurePosixPath(name)
        if any(p.is_symlink() for p in [path, *path.parents]):
            raise ValueError('Symbolic links are not supported')
        if not path.resolve().is_relative_to(self.files.resolve()):
            raise ValueError('Path outside project')
        return path

    def validate(self, text):
        if not isinstance(text, str) or '\x00' in text or len(text.encode('utf-8')) > MAX_FILE:
            raise ValueError('Upload UTF-8 text/code files up to 60 KB each. Binary files are not supported.')

    def read(self, name):
        path = self.path(name)
        if not path.is_file():
            raise ValueError('Project file not found')
        if path.stat().st_size > MAX_FILE:
            raise ValueError('File is too large')
        with path.open(encoding='utf-8', newline='') as stream:
            return stream.read()

    def listing(self):
        return [{'path': str(p.relative_to(self.files).as_posix()), 'bytes': p.stat().st_size}
                for p in sorted(self.files.rglob('*')) if p.is_file() and not p.is_symlink()][:200]

    def upload(self, name, text):
        self.validate(text)
        path = self.path(name)
        if path.exists():
            raise ValueError('File already exists. Rename the upload to keep the existing file.')
        if len(self.listing()) >= 100:
            raise ValueError('Project limit is 100 files')
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x', encoding='utf-8', newline='') as stream:
            stream.write(text)
        return {'path': name}

    def context(self, names):
        if not isinstance(names, list) or len(names) > 12 or any(not isinstance(n,str) for n in names):
            raise ValueError('Select up to 12 project files')
        entries = [{'path': n, 'content': self.read(n)} for n in dict.fromkeys(names)]
        data = json.dumps(entries, ensure_ascii=False)
        if len(data) > MAX_CONTEXT:
            raise ValueError('Selected files exceed 12,000 characters. Select fewer or smaller files.')
        return data

    def save(self, record):
        path = self.records / (record['id'] + '.json')
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(record), encoding='utf-8')
        os.replace(temp, path)

    def get(self, ident):
        if not isinstance(ident, str) or not re.fullmatch('[0-9a-f]{32}', ident):
            raise ValueError('Invalid change ID')
        try:
            return json.loads((self.records / (ident + '.json')).read_text(encoding='utf-8'))
        except FileNotFoundError:
            raise ValueError('Change not found') from None

    def propose(self, answer, selected, snapshot=None):
        answer = re.sub(r'<think>.*?</think>', '', answer, flags=re.S).strip()
        if answer.startswith('```'):
            answer = re.sub(r'^```(?:json)?\s*|\s*```$', '', answer)
        try:
            payload = json.loads(answer)
        except ValueError:
            raise ValueError('The model did not produce a valid change proposal. Try a smaller task or a coding model.') from None
        changes = payload.get('files') if isinstance(payload,dict) else None
        if not isinstance(changes, list) or not 1 <= len(changes) <= 8:
            raise ValueError('A proposal must contain 1–8 files')
        record = {'id': uuid.uuid4().hex, 'status': 'pending', 'files': []}
        seen = set()
        for change in changes:
            if not isinstance(change, dict):
                raise ValueError('Invalid file change')
            name, after = change.get('path'), change.get('content')
            path = self.path(name)
            self.validate(after)
            if name in seen:
                raise ValueError('Duplicate file change')
            seen.add(name)
            before = self.read(name) if path.exists() else None
            if snapshot is not None and name in snapshot and before != snapshot[name]:
                raise ValueError('Selected file changed during generation. Request a fresh proposal.')
            if before is not None and name not in selected:
                raise ValueError('Model tried to edit a file that was not selected')
            if before == after:
                continue
            diff = ''.join(difflib.unified_diff((before or '').splitlines(True), after.splitlines(True), fromfile=name if before is not None else '/dev/null', tofile=name))
            record['files'].append({'path': name, 'before': before, 'after': after, 'diff': diff})
        if not record['files']:
            raise ValueError('The model proposed no changes')
        if len(self.listing()) + sum(f['before'] is None for f in record['files']) > 100:
            raise ValueError('Project limit is 100 files')
        self.save(record)
        return record

    def apply(self, ident, undo=False):
        record = self.get(ident)
        if record['status'] != ('applied' if undo else 'pending'):
            raise ValueError('Change is not in the expected state')
        source, target = ('after', 'before') if undo else ('before', 'after')
        for f in record['files']:
            path = self.path(f['path'])
            current = self.read(f['path']) if path.exists() else None
            if current != f[source]:
                raise ValueError('File changed since review; create a fresh proposal. No files were modified.')
        written = []
        def write(f, key):
            path = self.path(f['path'])
            if f[key] is None:
                path.unlink(missing_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                temp = path.with_name(path.name + '.myai-' + uuid.uuid4().hex)
                try:
                    temp.write_text(f[key], encoding='utf-8', newline='')
                    os.replace(temp, path)
                finally:
                    temp.unlink(missing_ok=True)
        try:
            for f in record['files']:
                write(f, target)
                written.append(f)
            record['status'] = 'undone' if undo else 'applied'
            self.save(record)
        except OSError:
            for f in reversed(written):
                write(f, source)
            raise
        return record
