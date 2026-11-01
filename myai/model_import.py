"""Background import of an explicitly selected local GGUF file."""
import hashlib
import os
import threading
from pathlib import Path


def import_model(source, destination, expected=None, progress=None):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source.suffix.lower() != '.gguf':
        raise ValueError('Choose a .gguf model file.')
    if expected and (not isinstance(expected, str) or len(expected) != 64 or
                     any(c not in '0123456789abcdef' for c in expected.lower())):
        raise ValueError('SHA-256 must contain 64 hexadecimal characters.')
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / source.name
    partial = target.with_name(target.name + '.part')
    if target.exists() or target.is_symlink():
        raise ValueError('A model with this name already exists; it was not overwritten.')
    owned = False
    try:
        with source.open('rb') as inp:
            if inp.read(4) != b'GGUF':
                raise ValueError('File does not contain a GGUF header.')
            inp.seek(0)
            total = os.fstat(inp.fileno()).st_size
            digest = hashlib.sha256()
            received = 0
            with partial.open('xb') as out:
                owned = True
                while chunk := inp.read(4 * 1024 * 1024):
                    digest.update(chunk)
                    out.write(chunk)
                    received += len(chunk)
                    if progress:
                        progress(received, total)
                out.flush()
                os.fsync(out.fileno())
        checksum = digest.hexdigest()
        if expected and checksum != expected.lower():
            raise ValueError('SHA-256 mismatch; model was not imported.')
        # Atomic publication without replacing a concurrently created model.
        os.link(partial, target)
        partial.unlink()
        return target, checksum
    finally:
        if owned:
            partial.unlink(missing_ok=True)


class ModelImports:
    def __init__(self, root):
        self.destination = root / 'models'
        self.lock = threading.Lock()
        self.state = {'status': 'idle'}

    def snapshot(self):
        with self.lock:
            return dict(self.state)

    def start(self, body):
        source = body.get('path')
        if not isinstance(source, str) or not source.strip() or len(source) > 4096:
            raise ValueError('Enter the full path to a downloaded GGUF file.')
        source = Path(source.strip().strip('"')).expanduser()
        if not source.is_absolute() or not source.is_file() or source.suffix.lower() != '.gguf':
            raise ValueError('Choose an existing .gguf file using its full path.')
        expected = body.get('sha256') or None
        if expected and (not isinstance(expected, str) or len(expected) != 64 or
                         any(c not in '0123456789abcdef' for c in expected.lower())):
            raise ValueError('SHA-256 must contain 64 hexadecimal characters.')
        with self.lock:
            if self.state['status'] == 'importing':
                raise ValueError('A model import is already running.')
            self.state = {'status': 'importing', 'filename': source.name, 'received': 0,
                          'total': source.stat().st_size}
            threading.Thread(target=self.run, args=(source, expected), daemon=True).start()
            return dict(self.state)

    def run(self, source, expected):
        def progress(received, total):
            with self.lock:
                self.state.update(received=received, total=total)
        try:
            target, checksum = import_model(source, self.destination, expected, progress)
            with self.lock:
                self.state.update(status='complete', path=str(target), sha256=checksum,
                                  verification='Publisher checksum matched' if expected else 'GGUF header checked; publisher checksum not supplied')
        except Exception as exc:
            with self.lock:
                self.state.update(status='failed', error=str(exc))
