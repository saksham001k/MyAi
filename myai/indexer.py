"""Small local workspace index for file mentions and code navigation."""
from __future__ import annotations

import ast
import re
from pathlib import Path


class WorkspaceIndexer:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def scan(self, query: str = "") -> list[dict]:
        query = (query or "").lower()
        entries = []
        for path in self.root.rglob("*"):
            if not path.is_file() or any(part in {".git", ".venv", "node_modules", ".kiss"} for part in path.parts):
                continue
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
            path = (self.root / name).resolve()
            if not path.is_relative_to(self.root) or not path.is_file() or path.stat().st_size > 60_000:
                raise ValueError(f"Cannot attach file: {name}")
            chunks.append(f"--- {name} ---\n{path.read_text(encoding='utf-8')}")
        return "\n\n".join(chunks)
