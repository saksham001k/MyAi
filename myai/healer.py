"""Bounded local test-and-repair loop with reviewable patch events."""
from __future__ import annotations

import json
from pathlib import Path

from .indexer import apply_atomic_patch, get_enclosing_symbol
from .inference import LocalInference
from .sandbox import ExecutionSandbox, parse_traceback


def _clean_patch(text):
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines and lines[-1].strip() == "```" else lines[1:])
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and isinstance(parsed.get("replacement"), str):
            return parsed["replacement"]
    except json.JSONDecodeError:
        pass
    return text


class SelfHealingAgent:
    def __init__(self, engine=None, workspace_root=".", sandbox=None, inference=None,
                 max_attempts=3, apply_changes=True):
        self.workspace_root = Path(workspace_root).resolve()
        self.sandbox = sandbox or ExecutionSandbox(self.workspace_root)
        self.inference = inference or (LocalInference(engine) if engine else None)
        self.max_attempts = max_attempts
        self.apply_changes = apply_changes
        if self.inference is None:
            raise ValueError("An inference engine or patch provider is required.")

    def repair(self, command, event_callback=None, max_attempts=None):
        events, attempts = [], 0

        def emit(item):
            events.append(item)
            if event_callback:
                event_callback(item)

        while attempts < (max_attempts or self.max_attempts):
            attempts += 1
            emit({"type": "action", "stage": "test", "attempt": attempts, "command": command})
            result = self.sandbox.run(command)
            emit({"type": "test_output", "attempt": attempts, "result": result})
            if result["exit_code"] == 0:
                return {"success": True, "attempts": attempts, "events": events, "result": result}
            trace = parse_traceback(result.get("stderr", "") + "\n" + result.get("stdout", ""))
            if not trace:
                return {"success": False, "attempts": attempts, "events": events,
                        "error": "No source location found in test output."}
            # The final traceback frame is the failing application symbol rather
            # than the module-level call site.
            location = trace[-1]
            path = Path(location["file"])
            path = path if path.is_absolute() else self.workspace_root / path
            symbol = get_enclosing_symbol(path, location["line"])
            if not symbol:
                return {"success": False, "attempts": attempts, "events": events,
                        "error": f"No enclosing symbol found for {path}:{location['line']}"}
            prompt = (
                "Repair the failing symbol below. Return only the complete replacement block.\n"
                f"Error:\n{location['context']}\n\nSymbol:\n{symbol['source']}"
            )
            emit({"type": "thought", "attempt": attempts, "path": str(path),
                  "symbol": symbol["name"]})
            patch = _clean_patch(self.inference.generate_patch(prompt, temperature=0.1))
            emit({"type": "applied_diff", "attempt": attempts, "path": str(path),
                  "start_line": symbol["start_line"], "end_line": symbol["end_line"],
                  "replacement": patch, "applied": self.apply_changes})
            if self.apply_changes:
                apply_atomic_patch(path, symbol["start_line"], symbol["end_line"], patch)
        return {"success": False, "attempts": attempts, "events": events,
                "error": "Maximum repair attempts reached."}

    diagnose_and_repair = repair
