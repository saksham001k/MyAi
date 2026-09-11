"""Small local workspace index for file mentions and code navigation."""
from __future__ import annotations

import ast
import os
from .project import EXCLUDED, allowed, confined
from pathlib import Path


class WorkspaceIndexer:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def scan(self, query: str = "") -> list[dict]:
        query = (query or "").lower()
        entries = []
        candidates = []
        for directory, dirs, names in os.walk(self.root, followlinks=False):
            dirs[:] = sorted(d for d in dirs if d not in EXCLUDED and not (Path(directory) / d).is_symlink())
            for name in sorted(names):
                path = Path(directory) / name
                if allowed(path.relative_to(self.root).as_posix()) and not path.is_symlink():
                    candidates.append(path)
                if len(candidates) >= 500:
                    break
            if len(candidates) >= 500:
                break
        for path in candidates:
            rel = path.relative_to(self.root).as_posix()
            if rel.startswith("data/") and not rel.startswith("data/workbench/files/"):
                continue
            if query and query not in rel.lower():
                continue
            item = {"path": rel, "bytes": path.stat().st_size, "symbols": []}
            if path.suffix == ".py" and path.stat().st_size <= 200_000:
                try:
                    tree = ast.parse(path.read_text(encoding="utf-8"))
                    item["symbols"] = [
                        {"kind": "class" if isinstance(node, ast.ClassDef) else "function",
                         "name": node.name, "line": node.lineno}
                        for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                    ]
                except (OSError, SyntaxError, UnicodeDecodeError):
                    pass
            entries.append(item)
            if len(entries) >= 500:
                break
        return entries

    def mention_context(self, names: list[str]) -> str:
        chunks = []
        for name in dict.fromkeys(names):
            path = confined(self.root, name)
            if not path.is_relative_to(self.root) or not path.is_file() or path.stat().st_size > 60_000:
                raise ValueError(f"Cannot attach file: {name}")
            chunks.append(f"--- {name} ---\n{path.read_text(encoding='utf-8')}")
        return "\n\n".join(chunks)

    def explain(self, relative: str) -> dict:
        """Read-only file excerpt plus symbols. Does not propose or apply patches."""
        if not isinstance(relative, str) or not relative or len(relative) > 240:
            raise ValueError("Invalid path")
        path = confined(self.root, relative)
        if not path.is_relative_to(self.root) or not path.is_file():
            raise ValueError(f"Cannot read file: {relative}")
        if any(part in EXCLUDED for part in path.relative_to(self.root).parts):
            raise ValueError("That path is excluded from the read-only index")
        if path.stat().st_size > 200_000:
            raise ValueError("File is too large to explain in this view")
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("Only UTF-8 text files can be explained") from exc
        symbols = []
        if path.suffix == ".py":
            try:
                tree = ast.parse(text)
                symbols = [
                    {"kind": "class" if isinstance(node, ast.ClassDef) else "function",
                     "name": node.name, "line": node.lineno}
                    for node in ast.walk(tree)
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                ]
            except SyntaxError:
                symbols = []
        return {
            "path": path.relative_to(self.root).as_posix(),
            "bytes": path.stat().st_size,
            "symbols": symbols[:80],
            "excerpt": text[:8000],
            "truncated": len(text) > 8000,
            "review_required": True,
            "note": "Read-only excerpt. Any proposed patch must be reviewed in Project files before it is applied.",
        }
