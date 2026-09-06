"""Authenticated, bounded multipart uploads for workspace assets."""
from __future__ import annotations

import mimetypes
import re
import uuid
from email.parser import BytesParser
from email.policy import default
from pathlib import Path

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
ALLOWED_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".webp", ".gif",
    ".py", ".js", ".ts", ".html", ".css", ".json", ".md",
    ".pdf", ".txt", ".csv",
}


def safe_filename(value: str) -> str:
    name = Path(value or "upload").name
    name = re.sub(r"[^A-Za-z0-9._ -]+", "_", name).strip(" .")
    if not name:
        name = "upload"
    return name[:180]


class Uploader:
    def __init__(self, root: Path):
        self.root = (root / "data" / "uploads").resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def save_multipart(self, content_type: str, payload: bytes) -> dict:
        if len(payload) > MAX_UPLOAD_BYTES:
            raise ValueError("Uploads must be 50 MB or smaller.")
        if not content_type.lower().startswith("multipart/form-data"):
            raise ValueError("Expected multipart/form-data.")
        header = f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode()
        message = BytesParser(policy=default).parsebytes(header + payload)
        parts = [part for part in message.iter_parts() if part.get_filename()]
        if not parts:
            raise ValueError("No file was included in the upload.")
        part = parts[0]
        filename = safe_filename(part.get_filename())
        suffix = Path(filename).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise ValueError("Unsupported file type.")
        data = part.get_payload(decode=True) or b""
        if len(data) > MAX_UPLOAD_BYTES:
            raise ValueError("Uploads must be 50 MB or smaller.")
        ident = uuid.uuid4().hex
        destination = (self.root / f"{ident}{suffix}").resolve()
        if not destination.parent == self.root:
            raise ValueError("Invalid upload destination.")
        destination.write_bytes(data)
        mime = part.get_content_type() or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        return {
            "id": ident,
            "filename": filename,
            "filepath": str(destination.relative_to(self.root.parent.parent)),
            "size_bytes": len(data),
            "mime_type": mime,
            "url": f"/api/uploads/{ident}",
        }

    def find(self, ident: str) -> Path:
        if not re.fullmatch(r"[0-9a-f]{32}", ident):
            raise ValueError("Invalid upload ID.")
        matches = list(self.root.glob(ident + ".*"))
        if len(matches) != 1 or not matches[0].is_file() or matches[0].is_symlink():
            raise FileNotFoundError(ident)
        return matches[0]
