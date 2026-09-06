import sys
import tempfile
import unittest
from pathlib import Path

from myai.repair import SelfHealingLoop, parse_failure, symbol_at
from myai.sandbox import (
    ExecutionRequest, ExecutionSandbox, SandboxPolicyError, SandboxRunner,
    parse_traceback,
)


class SandboxTests(unittest.TestCase):
    def test_execution_sandbox_captures_output_and_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            result = ExecutionSandbox(directory).run(
                [sys.executable, "-c", "print('x'); raise RuntimeError('bad')"]
            )
        self.assertNotEqual(result["exit_code"], 0)
        self.assertEqual(result["stdout"].strip(), "x")
        self.assertEqual(parse_traceback("fixture.py:8:2: bad")[0]["line"], 8)

    def test_execution_sandbox_kills_timeout(self):
        with tempfile.TemporaryDirectory() as directory:
            result = ExecutionSandbox(directory, timeout=0.05).run(
                [sys.executable, "-c", "import time; time.sleep(1)"]
            )
        self.assertTrue(result["timed_out"])

    def test_runs_child_process_and_captures_output(self):
        with tempfile.TemporaryDirectory() as directory:
            result = SandboxRunner(Path(directory)).run(
                [sys.executable, "-c", "print('ok')"]
            )
        self.assertTrue(result.ok)
        self.assertEqual(result.stdout.strip(), "ok")

    def test_timeout_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            result = SandboxRunner(Path(directory)).run(
                ExecutionRequest([sys.executable, "-c", "import time; time.sleep(1)"],
                                 Path(directory), timeout=0.05)
            )
        self.assertTrue(result.timed_out)
        self.assertIn("timed out", result.stderr.lower())

    def test_network_commands_require_explicit_authorization(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(SandboxPolicyError):
                SandboxRunner(Path(directory)).run(["curl", "https://example.com"])

    def test_failure_parser_extracts_python_symbol(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "broken.py"
            source.write_text("def greet():\n    return missing_name\nprint(greet())\n", encoding="utf-8")
            result = SandboxRunner(root).run([sys.executable, str(source)])
            report = parse_failure(result, root)
            self.assertEqual(report.location.path, source.resolve())
            self.assertEqual(report.location.symbol, "greet")
            self.assertEqual(symbol_at(source, 2), "greet")

    def test_self_healing_callback_replaces_source_and_retries(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "broken.py"
            source.write_text("def greet():\n    return missing_name\nprint(greet())\n",
                              encoding="utf-8")
            def repair(report, original):
                self.assertEqual(report.location.symbol, "greet")
                return original.replace("missing_name", "'fixed'")
            result, reports = SelfHealingLoop(SandboxRunner(root)).run(
                [sys.executable, str(source)], repair=repair
            )
            self.assertTrue(result.ok)
            self.assertEqual(len(reports), 1)


if __name__ == "__main__":
    unittest.main()
