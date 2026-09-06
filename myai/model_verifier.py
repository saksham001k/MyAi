"""Streaming integrity checks for local GGUF model files."""
import hashlib
from pathlib import Path


CHUNK_SIZE = 8 * 1024 * 1024


def sha256_file(path, chunk_size=CHUNK_SIZE):
    """Return a file's SHA-256 digest without loading it into memory."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def verify_model_hash(file_path, expected_sha256=None):
    """Return ``(is_valid, computed_hash)`` for a model checksum."""
    path = Path(file_path)
    if not path.is_file():
        return False, ""
    try:
        computed_hash = sha256_file(path)
    except OSError:
        return False, ""
    if expected_sha256 is None:
        return True, computed_hash
    expected = str(expected_sha256).strip().lower()
    if len(expected) != 64 or any(
            character not in "0123456789abcdef" for character in expected):
        return False, computed_hash
    return computed_hash == expected, computed_hash


def verify_model(path, expected_hash):
    """Backward-compatible alias for callers using the original helper."""
    return verify_model_hash(path, expected_hash)
