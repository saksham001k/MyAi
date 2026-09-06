"""Failure parsing and guarded Python symbol repair orchestration."""
from __future__ import annotations

import ast
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .sandbox import ExecutionRequest, ExecutionResult, SandboxRunner


@dataclass(frozen=True)
class FailureLocation:
    path: Path
    line: int
    symbol: str | None


@dataclass(frozen=True)
class FailureReport:
    result: ExecutionResult
    location: FailureLocation | None
    trace: str


def parse_failure(result: ExecutionResult, root: Path) -> FailureReport:
    trace = (result.stdout + "\n" + result.stderr).strip()
    location = None
    matches = list(re.finditer(r'File ["\']([^"\']+)["\'], line (\d+)', trace))
    if matches:
        match = matches[-1]
        candidate = Path(match.group(1))
        path = candidate if candidate.is_absolute() else (root / candidate)
        path = path.resolve()
        if path.is_relative_to(root.resolve()):
            location = FailureLocation(path, int(match.group(2)), symbol_at(path, int(match.group(2))))
    return FailureReport(result, location, trace[-16000:])


def symbol_at(path: Path, line: int) -> str | None:
    if path.suffix != ".py" or not path.is_file():
        return None
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return None
    candidates = [
        node for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and node.lineno <= line <= getattr(node, "end_lineno", node.lineno)
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda node: node.end_lineno - node.lineno).name


RepairCallback = Callable[[FailureReport, str], str | None]


class SelfHealingLoop:
    """Run a command and let a bounded callback replace the failing source file."""

    def __init__(self, runner: SandboxRunner, max_attempts: int = 3):
        self.runner = runner
        self.max_attempts = max(1, min(max_attempts, 5))

    def run(self, command: str | list[str], repair: RepairCallback | None = None,
            timeout: float = 30.0) -> tuple[ExecutionResult, list[FailureReport]]:
        reports: list[FailureReport] = []
        for _ in range(self.max_attempts):
            result = self.runner.run(ExecutionRequest(command, self.runner.root, timeout))
            if result.ok:
                return result, reports
            report = parse_failure(result, self.runner.root)
            reports.append(report)
            if repair is None or report.location is None:
                return result, reports
            original = report.location.path.read_text(encoding="utf-8")
            replacement = repair(report, original)
            if replacement is None or replacement == original:
                return result, reports
            if "\x00" in replacement:
                return result, reports
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=report.location.path.parent,
                prefix=f".{report.location.path.name}.", delete=False
            ) as temp:
                temp.write(replacement)
                temporary = Path(temp.name)
            temporary.replace(report.location.path)
        return result, reports

