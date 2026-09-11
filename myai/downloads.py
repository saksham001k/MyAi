"""Resumable HTTPS downloads with publisher SHA-256 verification."""
from __future__ import annotations

import hashlib
import os
import re
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from .model_verifier import sha256_file

CHUNK = 1024 * 1024
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class DownloadCancelled(Exception):
    """Raised when a download is cooperatively cancelled."""


def _opener():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _require_https(url, allow_loopback=False):
    if allow_loopback and url.startswith("http://127.0.0.1"):
        return
    if not url.startswith("https://"):
        raise ValueError("Downloads require HTTPS")


def _valid_digest(digest):
    value = str(digest or "").strip().lower()
    if not HEX64.fullmatch(value):
        raise ValueError("Download has no valid publisher SHA-256")
    return value


def download_file(url, destination, digest, progress=None, cancel=None, allow_loopback=False):
    """Write ``destination`` only after the publisher checksum matches.

    Interrupted transfers leave a ``.part`` file so a later call can resume
    with HTTP Range. A complete file that already matches is left untouched.
    A complete file with the wrong digest is never overwritten.
    """
    destination = Path(destination)
    expected = _valid_digest(digest)
    _require_https(url, allow_loopback=allow_loopback)
    if destination.exists():
        if destination.is_file() and sha256_file(destination) == expected:
            if progress:
                progress({"status": "verified", "received": destination.stat().st_size,
                          "total": destination.stat().st_size})
            return destination
        raise ValueError(f"Existing file does not match: {destination}. It was not overwritten.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".part")
    offset = partial.stat().st_size if partial.is_file() else 0
    hasher = hashlib.sha256()
    if offset:
        with partial.open("rb") as existing:
            while chunk := existing.read(CHUNK):
                hasher.update(chunk)
    request = urllib.request.Request(url, method="GET")
    request.add_header("User-Agent", "MyAi-download/0.2")
    if offset:
        request.add_header("Range", f"bytes={offset}-")
    http = _opener()
    try:
        with http.open(request, timeout=60) as response:
            status = getattr(response, "status", 200)
            if offset and status == 200:
                # Server ignored Range; restart so the digest covers the whole object.
                hasher = hashlib.sha256()
                offset = 0
            elif offset and status not in (206,):
                raise ValueError(f"Unexpected resume response ({status})")
            total_header = response.headers.get("Content-Length")
            total = int(total_header) + (offset if status == 206 else 0) if total_header else None
            mode = "ab" if offset and status == 206 else "wb"
            received = offset
            with partial.open(mode) as out:
                while True:
                    if cancel is not None and cancel.is_set():
                        raise DownloadCancelled("Download cancelled")
                    chunk = response.read(CHUNK)
                    if not chunk:
                        break
                    hasher.update(chunk)
                    out.write(chunk)
                    received += len(chunk)
                    if progress:
                        progress({"status": "downloading", "received": received, "total": total})
                out.flush()
                os.fsync(out.fileno())
    except urllib.error.HTTPError as exc:
        if exc.code == 416 and partial.exists():
            # Partial file is already complete according to the server.
            pass
        else:
            raise
    computed = hasher.hexdigest()
    if computed != expected:
        partial.unlink(missing_ok=True)
        raise ValueError(f"Checksum failed for {destination.name}. Run the download again.")
    os.replace(partial, destination)
    if progress:
        progress({"status": "complete", "received": destination.stat().st_size,
                  "total": destination.stat().st_size})
    return destination


class DownloadManager:
    """One active catalog download; status is polled by the UI."""

    def __init__(self, root):
        self.root = Path(root)
        self.lock = threading.Lock()
        self.cancel = threading.Event()
        self.thread = None
        self.state = {"status": "idle"}

    def snapshot(self):
        with self.lock:
            return dict(self.state)

    def _set(self, **fields):
        with self.lock:
            self.state = {**self.state, **fields, "updated": time.time()}

    def start(self, item, kind="model"):
        if kind not in {"model", "runtime"}:
            raise ValueError("Unsupported download kind")
        digest = item.get("sha256")
        if not digest:
            raise ValueError("Publisher SHA-256 is required before downloading")
        filename = item["filename"] if kind == "model" else item["name"]
        folder = self.root / ("models" if kind == "model" else "data/downloads")
        target = folder / Path(filename).name
        with self.lock:
            if self.thread is not None and self.thread.is_alive():
                raise ValueError("A download is already running. Wait or cancel it.")
            self.cancel.clear()
            self.state = {
                "status": "starting",
                "id": item.get("id") or item.get("name"),
                "filename": target.name,
                "kind": kind,
                "received": 0,
                "total": item.get("size_bytes_approx"),
                "error": None,
            }
        def run():
            try:
                self._set(status="downloading")
                download_file(
                    item["url"], target, digest, progress=self._set, cancel=self.cancel
                )
                self._set(status="complete", path=str(target.relative_to(self.root)))
            except DownloadCancelled:
                self._set(status="cancelled", error="Download cancelled. The partial file was kept for resume.")
            except Exception as exc:
                self._set(status="error", error=str(exc))
        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()
        return self.snapshot()

    def stop(self):
        self.cancel.set()
        return self.snapshot()
