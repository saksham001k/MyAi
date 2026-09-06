import tempfile
import unittest
import sys
from pathlib import Path

from myai.healer import SelfHealingAgent
from myai.sandbox import ExecutionSandbox


class FakeInference:
    def generate_patch(self, prompt, temperature=0.1):
        self.prompt = prompt
        return "def broken():\n    return 2\n"


class HealerTests(unittest.TestCase):
    def test_repairs_and_retries_a_python_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "fixture.py"
            target.write_text("def broken():\n    assert 1 == 2\n    return 1\n\nbroken()\n", encoding="utf-8")
            healer = SelfHealingAgent(
                workspace_root=root, sandbox=ExecutionSandbox(root),
                inference=FakeInference(), max_attempts=2,
            )
            result = healer.repair([sys.executable, str(target)])
            self.assertTrue(result["success"])
            self.assertEqual(target.read_text(encoding="utf-8").splitlines()[1], "    return 2")


if __name__ == "__main__":
    unittest.main()
