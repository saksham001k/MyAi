"""Small local workspace index for file mentions and code navigation."""
from __future__ import annotations

import ast
import re
from pathlib import Path


def get_enclosing_symbol(file_path, line_number):
    """Return the smallest Python symbol containing a one-based source line."""
    path = Path(file_path)
    if line_number < 1:
        raise ValueError("line_number must be one-based.")
    source = path.read_text(encoding="utf-8")
    if path.suffix == ".py":
        tree = ast.parse(source, filename=str(path))
        nodes = [
            node for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and node.lineno <= line_number <= getattr(node, "end_lineno", node.lineno)
        ]
        if not nodes:
            return None
        node = min(nodes, key=lambda item: getattr(item, "end_lineno", item.lineno) - item.lineno)
        lines = source.splitlines()
        return {
            "name": node.name, "kind": "class" if isinstance(node, ast.ClassDef) else "function",
            "start_line": node.lineno, "end_line": getattr(node, "end_lineno", node.lineno),
            "source": "\n".join(lines[node.lineno - 1:getattr(node, "end_lineno", node.lineno)]),
        }
    lines = source.splitlines()
    pattern = re.compile(r"^\s*(?:export\s+)?(?:async\s+)?(?:function|class)\s+([A-Za-z_$][\w$]*)")
    candidates = [(index + 1, match.group(1)) for index, text in enumerate(lines)
                  if (match := pattern.match(text)) and index + 1 <= line_number]
    if not candidates:
        return None
    start, name = candidates[-1]
    end = len(lines)
    return {"name": name, "kind": "class" if "class" in lines[start - 1] else "function",
            "start_line": start, "end_line": end, "source": "\n".join(lines[start - 1:end])}


def apply_atomic_patch(file_path, start_line, end_line, new_code):
    """Apply a one-based inclusive patch after validating Python/TS syntax."""
    path = Path(file_path)
    if start_line < 1 or end_line < start_line:
        raise ValueError("Invalid one-based line range.")
    original = path.read_text(encoding="utf-8")
    lines = original.splitlines(keepends=True)
    if end_line > len(lines):
        raise ValueError("Patch range exceeds file length.")
    newline = "\r\n" if "\r\n" in original else "\n"
    replacement = new_code.replace("\r\n", "\n").splitlines(keepends=True)
    replacement = [line if line.endswith(("\n", "\r")) else line + newline for line in replacement]
    updated = "".join(lines[:start_line - 1] + replacement + lines[end_line:])
    if path.suffix == ".py":
        ast.parse(updated, filename=str(path))
    elif path.suffix in {".js", ".jsx", ".ts", ".tsx"}:
        if re.search(r"\b(function|class|interface)\b", updated) and updated.count("{") != updated.count("}"):
            raise SyntaxError("Unbalanced braces in patched source.")
    temp = path.with_name(path.name + ".myai.tmp")
    temp.write_text(updated, encoding="utf-8", newline="")
    temp.replace(path)
    return True


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
