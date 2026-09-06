import unittest
import sys
from unittest.mock import patch

from myai.tools.system_control import execute_command, inspect_system


class SystemControlTests(unittest.TestCase):
    def test_execute_command_does_not_use_a_shell(self):
        result = execute_command([sys.executable, "-c", "print('ok')"])
        self.assertEqual(result["returncode"], 0)
        self.assertEqual(result["stdout"].strip(), "ok")

    def test_command_string_is_tokenized_without_shell_expansion(self):
        result = execute_command(f'{sys.executable} -c "print(\'safe\')"')
        self.assertEqual(result["stdout"].strip(), "safe")

    @patch("myai.tools.system_control.psutil")
    def test_inspection_returns_resource_sections(self, psutil):
        psutil.virtual_memory.return_value = type(
            "Memory", (), {"total": 10, "available": 6, "used": 4, "percent": 40}
        )()
        psutil.disk_usage.return_value = type(
            "Disk", (), {"total": 20, "free": 12, "used": 8, "percent": 40}
        )()
        psutil.cpu_percent.return_value = 5
        psutil.cpu_count.return_value = 4
        psutil.process_iter.return_value = []
        report = inspect_system()
        self.assertEqual(report["cpu_percent"], 5)
        self.assertIn("memory", report)
        self.assertIn("disk", report)
        self.assertEqual(report["processes"], [])


if __name__ == "__main__":
    unittest.main()
