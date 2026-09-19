"""Task-owned project copies with complete review, conflict checks and undo."""
import difflib
import hashlib
import json
import os
import subprocess
from pathlib import Path

EXCLUDED = {'.git', '.kiss', '.local-planning', '.venv', 'venv', 'node_modules',
            'models', 'runtime', 'data', 'dist', 'build', '__pycache__', 'testpic'}
TEXT = {'.py', '.js', '.jsx', '.ts', '.tsx', '.json', '.md', '.txt', '.html', '.css',
        '.yml', '.yaml', '.toml', '.sh', '.bat', '.command', '.csv', '.xml', '.ini', '.cfg'}
MAX_FILE = 200_000
MAX_TOTAL = 8_000_000


def digest(data):
    return hashlib.sha256(data).hexdigest() if data is not None else None


def allowed(name):
    p = Path(name)
    return (not p.is_absolute() and not any(x in EXCLUDED or x in ('.', '..') or
            x.startswith('.env') or x.lower().endswith(('.pem', '.key')) for x in p.parts)
            and (p.suffix.lower() in TEXT or p.name in ('Dockerfile', 'Makefile', '.gitignore')))


def confined(root, name):
    if not isinstance(name, str) or not name or '\\' in name or not allowed(name):
        raise ValueError('Choose a supported relative source/text path. Private and generated folders are excluded.')
    p = root / name
    if any(x.is_symlink() for x in [p, *p.parents]):
        raise ValueError('Symbolic links are not supported for task files.')
    if not p.resolve().is_relative_to(root.resolve()):
        raise ValueError('File is outside this project.')
    return p


class ProjectCopy:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.work = self.folder / 'project'
        self.meta = self.folder / 'project.json'

    def create(self, source):
        source = Path(source).expanduser().resolve()
        if not source.is_dir() or source == Path(source.anchor) or source == Path.home():
            raise ValueError('Choose a specific project directory, not the entire drive or home directory.')
        candidates = []
        ignored = set()
        try:
            result = subprocess.run(['git', '-C', str(source), 'ls-files', '--others', '--ignored', '--exclude-standard', '-z'],
                                    capture_output=True, timeout=10, check=False)
            if result.returncode == 0:
                ignored = set(result.stdout.decode().split('\0'))
        except (OSError, subprocess.TimeoutExpired, UnicodeDecodeError):
            pass
        for directory, dirs, names in os.walk(source, followlinks=False):
            dirs[:] = sorted(d for d in dirs if d not in EXCLUDED and not (Path(directory) / d).is_symlink())
            for name in sorted(names):
                p = Path(directory) / name
                rel = p.relative_to(source).as_posix()
                if allowed(rel) and rel not in ignored and not p.is_symlink():
                    candidates.append((rel, p))
        baseline, total, skipped = {}, 0, 0
        self.work.mkdir(parents=True)
        for rel, p in candidates:
            if p.stat().st_size > MAX_FILE:
                skipped += 1
                continue
            data = p.read_bytes()
            try:
                data.decode('utf-8')
            except UnicodeDecodeError:
                skipped += 1
                continue
            if b'\x00' in data:
                skipped += 1
                continue
            total += len(data)
            if total > MAX_TOTAL or len(baseline) >= 500:
                raise ValueError('Project exceeds the 500-file / 8 MB source-copy budget. Choose a smaller project folder.')
            dest = confined(self.work, rel)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            baseline[rel] = {'hash': digest(data), 'text': data.decode('utf-8')}
        meta = {'source': str(source), 'baseline': baseline, 'skipped': skipped, 'status': 'draft'}
        self.save(meta)
        return {'source': str(source), 'files': len(baseline), 'skipped': skipped, 'working_copy': str(self.work)}

    def save(self, value):
        temp = self.meta.with_suffix('.tmp')
        temp.write_text(json.dumps(value), encoding='utf-8')
        os.replace(temp, self.meta)

    def read(self, name):
        p = confined(self.work, name)
        if p.stat().st_size > MAX_FILE:
            raise ValueError('File exceeds the source-reading budget.')
        # Review and conflict checks compare exact bytes, including CRLF on Windows.
        return p.read_bytes().decode('utf-8')

    def write(self, name, content):
        if not isinstance(content, str) or '\x00' in content or len(content.encode()) > MAX_FILE:
            raise ValueError('Write UTF-8 text up to 200 KB.')
        p = confined(self.work, name)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content.encode('utf-8'))
        return {'path': name, 'bytes': p.stat().st_size, 'location': 'working copy; original unchanged'}

    def files(self):
        result = []
        for directory, dirs, names in os.walk(self.work, followlinks=False):
            dirs[:] = sorted(d for d in dirs if d not in EXCLUDED and not (Path(directory) / d).is_symlink())
            for n in sorted(names):
                p = Path(directory) / n
                rel = p.relative_to(self.work).as_posix()
                if allowed(rel) and not p.is_symlink() and p.stat().st_size <= MAX_FILE:
                    result.append(rel)
                    if len(result) > 500:
                        raise ValueError('Too many generated source files to review.')
        return result

    def review(self):
        meta = json.loads(self.meta.read_text())
        changes = []
        # Files skipped at import must never be treated as new/overwritable originals.
        for name in sorted(set(meta['baseline']) | set(self.files())):
            before = meta['baseline'].get(name, {}).get('text')
            p = confined(self.work, name)
            after = self.read(name) if p.exists() else None
            if before == after:
                continue
            diff = ''.join(difflib.unified_diff((before or '').splitlines(True), (after or '').splitlines(True),
                         fromfile=name if before is not None else '/dev/null',
                         tofile=name if after is not None else '/dev/null'))
            changes.append({'path': name, 'before': before, 'after': after, 'diff': diff})
        review_id = digest(json.dumps(changes, sort_keys=True).encode())
        return {'source': meta['source'], 'status': meta['status'], 'files': changes, 'review_id': review_id}

    def apply(self, review_id, undo=False):
        meta = json.loads(self.meta.read_text())
        if undo:
            if meta['status'] != 'applied':
                raise ValueError('This task has no applied changes to undo.')
            changes = meta['applied']
        else:
            if meta['status'] != 'draft':
                raise ValueError('Changes have already been applied or undone.')
            review = self.review()
            if review_id != review['review_id'] or not review['files']:
                raise ValueError('Review changed or is empty. Open the latest review.')
            changes = review['files']
        root = Path(meta['source'])
        source_key, dest_key = ('after', 'before') if undo else ('before', 'after')
        for item in changes:
            p = confined(root, item['path'])
            current = p.read_bytes() if p.exists() else None
            expected = item[source_key].encode() if item[source_key] is not None else None
            if current != expected:
                raise ValueError(f"Original changed since review: {item['path']}. No files were applied.")
        def write(item, key):
            p = confined(root, item['path'])
            if item[key] is None:
                p.unlink(missing_ok=True)
            else:
                p.parent.mkdir(parents=True, exist_ok=True)
                temp = p.with_name(p.name + '.myai-tmp')
                # Never overwrite a user's existing temporary file.
                with temp.open('x', encoding='utf-8', newline='') as stream:
                    stream.write(item[key])
                try:
                    os.replace(temp, p)
                finally:
                    temp.unlink(missing_ok=True)
        written = []
        try:
            for item in changes:
                write(item, dest_key)
                written.append(item)
            meta['status'] = 'undone' if undo else 'applied'
            meta['applied'] = changes
            self.save(meta)
        except OSError:
            for item in reversed(written):
                write(item, source_key)
            raise
        return {'status': meta['status'], 'files': [x['path'] for x in changes]}
