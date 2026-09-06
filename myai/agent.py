"""Bounded autonomous Thought/Action/Observation/Final Answer execution."""
import json
import re
from typing import Any, Dict, Optional

from .prompts import AGENT_SYSTEM_PROMPT
from .repair import SelfHealingLoop
from .sandbox import SandboxRunner
from .tools.system_control import classify_risk, is_catastrophic, require_approval


class AgentStopped(RuntimeError):
    """Raised when an agent execution is cancelled."""


class AutonomousAgent:
    def __init__(self, engine, max_iterations: int = 10, tool_call=None,
                 auto_approve: bool = False, workspace_root=None,
                 repair_callback=None):
        if callable(max_iterations) and tool_call is None:
            tool_call, max_iterations = max_iterations, 10
        self.engine = engine
        self.tool_call = tool_call
        self.max_iterations = max(1, min(max_iterations, 50))
        self.confirmation_callback = None
        self.auto_approve = auto_approve is True
        self.test_timeout = 120
        self.workspace_root = workspace_root
        self.repair_callback = repair_callback

    @staticmethod
    def parse_response(response: str) -> Dict[str, Any]:
        """Parse the strict text protocol, with legacy JSON compatibility."""
        final = re.search(r"(?ms)^\s*Final Answer:\s*(.+?)\s*$", response)
        if final:
            return {"type": "final", "content": final.group(1).strip()}
        thought = re.search(r"(?ms)^\s*Thought:\s*(.+?)(?=\nAction:|\Z)", response)
        action = re.search(r"(?ms)^\s*Action:\s*(\{.*\})\s*$", response)
        if thought and action:
            try:
                payload = json.loads(action.group(1))
            except json.JSONDecodeError as exc:
                raise ValueError("Action is not valid JSON") from exc
            if not isinstance(payload, dict) or not isinstance(payload.get("tool"), str):
                raise ValueError("Action requires a tool name")
            args = payload.get("args", {})
            if not isinstance(args, dict):
                raise ValueError("Action args must be an object")
            return {"type": "action", "thought": thought.group(1).strip(),
                    "tool": payload["tool"], "args": args}
        try:
            legacy = json.loads(response.strip())
        except json.JSONDecodeError as exc:
            raise ValueError("Expected Thought/Action or Final Answer") from exc
        if isinstance(legacy, dict) and isinstance(legacy.get("final"), str):
            return {"type": "final", "content": legacy["final"]}
        action = legacy.get("action") if isinstance(legacy, dict) else None
        if isinstance(action, dict) and isinstance(action.get("tool"), str):
            return {"type": "action", "thought": action.get("reason", ""),
                    "tool": action["tool"], "args": action.get("arguments", {})}
        raise ValueError("Expected Thought/Action or Final Answer")

    def _model(self, messages):
        if callable(self.engine):
            return self.engine(messages)
        return self.engine.stream(messages, 0.2, max_tokens=1024)

    def run(self, user_query: str, stream_callback=None) -> Dict[str, Any]:
        messages = [{"role": "system", "content": AGENT_SYSTEM_PROMPT},
                    {"role": "user", "content": user_query}]
        observations = []
        for iteration in range(1, self.max_iterations + 1):
            response = "".join(self._model(messages))
            try:
                parsed = self.parse_response(response)
            except ValueError as exc:
                observation = {"ok": False, "error": str(exc), "raw": response}
                messages.extend([{"role": "assistant", "content": response},
                                 {"role": "user", "content": "Observation: " + json.dumps(observation)}])
                self._emit(stream_callback, {"type": "observation",
                                             "iteration": iteration,
                                             "observation": observation})
                continue
            if parsed["type"] == "final":
                event = {"type": "final", "iteration": iteration,
                         "content": parsed["content"]}
                self._emit(stream_callback, event)
                return {"status": "complete", "answer": parsed["content"],
                        "iterations": iteration, "observations": observations}
            self._emit(stream_callback, {"type": "thought", "iteration": iteration,
                                         "content": parsed["thought"]})
            action_event = {"type": "action", "iteration": iteration,
                            "tool": parsed["tool"], "args": parsed["args"]}
            self._emit(stream_callback, action_event)
            command = parsed["args"].get("command", "") if parsed["tool"] == "execute_command" else ""
            try:
                if command and is_catastrophic(command):
                    raise PermissionError("Command blocked by the catastrophic-command safety policy.")
                if self.auto_approve and command:
                    parsed["args"]["confirm"] = True
                if (command and classify_risk(command) == "HIGH"
                        and not self.auto_approve and not parsed["args"].get("confirm")):
                    if not self.confirmation_callback or not self.confirmation_callback(
                            parsed["tool"], parsed["args"]):
                        raise PermissionError("User denied the high-risk action.")
                    parsed["args"]["confirm"] = True
                require_approval(command, approved=(
                    self.auto_approve or parsed["args"].get("confirm", False)
                ))
                caller = self.tool_call or self.engine.call_tool
                result = caller(parsed["tool"], **parsed["args"])
                observation = {"ok": True, "result": result}
                if parsed["tool"] in {"apply_edit", "write_file", "edit_file"} or (
                    isinstance(result, dict) and result.get("modified_files")
                ):
                    observation["tests"] = self._run_post_edit_tests()
            except Exception as exc:
                observation = {"ok": False, "error": str(exc)}
            observations.append(observation)
            self._emit(stream_callback, {"type": "observation", "iteration": iteration,
                                         "tool": parsed["tool"], "observation": observation})
            messages.extend([{"role": "assistant", "content": response},
                             {"role": "user", "content": "Observation: " + json.dumps(observation)}])
        answer = "I reached the maximum number of steps before completing the goal."
        self._emit(stream_callback, {"type": "final", "content": answer,
                                     "limited": True, "iteration": self.max_iterations})
        return {"status": "limited", "answer": answer,
                "iterations": self.max_iterations, "observations": observations}

    @staticmethod
    def _emit(callback: Optional[Any], event: Dict[str, Any]):
        if callback:
            callback(event)

    def _run_post_edit_tests(self) -> dict:
        """Run pytest in the workspace sandbox and return repairable diagnostics."""
        if self.workspace_root is None:
            return {"ok": False, "error": "No workspace root configured for post-edit tests."}
        runner = SandboxRunner(self.workspace_root)
        loop = SelfHealingLoop(runner, max_attempts=2)
        result, reports = loop.run(
            ["pytest", "tests/"],
            repair=self.repair_callback,
            timeout=self.test_timeout,
        )
        output = (result.stdout + result.stderr)[-12000:]
        return {
            "ok": result.ok,
            "returncode": result.returncode,
            "timed_out": result.timed_out,
            "output": output,
            "failures": [
                {
                    "path": str(report.location.path) if report.location else None,
                    "line": report.location.line if report.location else None,
                    "symbol": report.location.symbol if report.location else None,
                    "trace": report.trace,
                }
                for report in reports
            ],
        }
