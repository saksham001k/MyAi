"""Verified runtime/model catalog with explicit license information."""
from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path
from urllib.parse import quote

from .engine import platform_tag
from .hardware import recommend_model

CATALOG_PATH = Path(__file__).with_name("catalog.json")
LOCK_PATH = Path(__file__).resolve().parents[1] / "runtimes.lock.json"
ALLOWED_HOSTS = {
    "huggingface.co",
    "github.com",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
}
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def load_catalog():
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def load_runtime_lock():
    if not LOCK_PATH.is_file():
        return {}
    return json.loads(LOCK_PATH.read_text(encoding="utf-8"))


def _https_url(url):
    if not isinstance(url, str) or not url.startswith("https://"):
        return False
    host = url.split("/")[2].split(":")[0].lower()
    return host in ALLOWED_HOSTS


def installed_models(root):
    folder = Path(root) / "models"
    if not folder.is_dir():
        return {}
    found = {}
    for path in folder.glob("*.gguf"):
        if path.is_file() and not path.is_symlink():
            found[path.name] = path.stat().st_size
    return found


def describe(root, memory=None, hardware=None):
    """Return catalog rows annotated with install state and a conservative pick."""
    data = load_catalog()
    lock = load_runtime_lock()
    tag = platform_tag()
    local = installed_models(root)
    models = []
    for item in data.get("models", []):
        row = dict(item)
        row["installed"] = row["filename"] in local
        row["installed_bytes"] = local.get(row["filename"])
        row["downloadable"] = _https_url(row.get("url", ""))
        if not row["downloadable"]:
            row["notes"] = (row.get("notes") or "") + " Download URL is not on the allowlist."
        models.append(row)
    recommendation = recommend_model(models, memory, hardware)
    runtimes = []
    for source in lock.get(tag, []):
        runtimes.append({
            "platform": tag,
            "repo": source.get("repo"),
            "tag": source.get("tag"),
            "name": source.get("name"),
            "url": source.get("url"),
            "sha256": source.get("sha256"),
            "executable": source.get("executable"),
            "license": data.get("runtimes", {}).get("license"),
            "license_url": data.get("runtimes", {}).get("license_url"),
            "downloadable": _https_url(source.get("url", "")),
        })
    return {
        "platform": tag,
        "models": models,
        "runtimes": runtimes,
        "runtime_notes": data.get("runtimes", {}).get("notes"),
        "recommendation": recommendation,
        "disclaimer": (
            "Licenses belong to each publisher. Checksums are either pinned in this "
            "repository or fetched from publisher metadata at download time. "
            "Recommendations are conservative memory estimates, not quality rankings."
        ),
    }


def find_model(model_id):
    for item in load_catalog().get("models", []):
        if item.get("id") == model_id:
            if not _https_url(item.get("url", "")):
                raise ValueError("Catalog entry is not downloadable from an allowed host.")
            return item
    raise KeyError("Unknown catalog model")


def resolve_digest(item):
    """Return (url, sha256) using a pinned digest or publisher LFS metadata."""
    pinned = str(item.get("sha256") or "").strip().lower()
    if pinned:
        if not HEX64.fullmatch(pinned):
            raise ValueError("Catalog SHA-256 is invalid")
        return item["url"], pinned
    if item.get("sha256_source") != "huggingface-lfs-at-download":
        raise ValueError("No publisher checksum available for this catalog entry")
    repo = item.get("repo")
    filename = item.get("filename")
    request = urllib.request.Request(
        f"https://huggingface.co/api/models/{quote(repo, safe='/')}?blobs=true",
        headers={"User-Agent": "MyAi-catalog/0.2"},
    )
    http = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with http.open(request, timeout=30) as response:
        info = json.load(response)
    matches = [s for s in info.get("siblings", [])
               if str(s.get("rfilename", "")).lower() == str(filename).lower()]
    if len(matches) != 1:
        raise ValueError(f"Publisher file changed or unavailable: {repo}/{filename}")
    digest = str(matches[0].get("lfs", {}).get("sha256", "")).lower()
    if not HEX64.fullmatch(digest):
        raise ValueError("Publisher SHA-256 unavailable; download refused")
    revision = info.get("sha")
    if not revision:
        raise ValueError("Publisher revision unavailable; download refused")
    url = f"https://huggingface.co/{repo}/resolve/{revision}/" + quote(matches[0]["rfilename"], safe="/")
    if not _https_url(url):
        raise ValueError("Publisher URL is not on the allowlist")
    return url, digest
