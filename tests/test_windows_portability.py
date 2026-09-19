"""Exact project bytes and native command quoting protect Windows review/testing."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

from myai.process import run_process, split_command
from myai.project import ProjectCopy


class PortabilityTests(unittest.TestCase):
    def test_crlf_is_not_a_phantom_edit_and_undo_restores_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'source'
            source.mkdir()
            original = b'answer = 1\r\n'
            file = source / 'answer.py'
            file.write_bytes(original)
            project = ProjectCopy(root / 'task')
            project.create(source)
            self.assertEqual(project.review()['files'], [])
            project.write('answer.py', 'answer = 2\n')
            review = project.review()
            self.assertEqual(review['files'][0]['before'].encode(), original)
            project.apply(review['review_id'])
            self.assertEqual(file.read_bytes(), b'answer = 2\n')
            project.apply(None, undo=True)
            self.assertEqual(file.read_bytes(), original)

    @unittest.skipUnless(os.name == 'nt', 'Native Windows quoting')
    def test_windows_paths_quotes_and_backslashes_roundtrip(self):
        args = [r'C:\Program Files\Python\python.exe', '-c', 'print("hi")', r'C:\data\file.txt']
        self.assertEqual(split_command(subprocess.list2cmdline(args)), args)
        with tempfile.TemporaryDirectory() as tmp:
            command = subprocess.list2cmdline([sys.executable, '-c', 'print("windows-ok")'])
            result = run_process(split_command(command), tmp, threading.Event())
            self.assertEqual(result['returncode'], 0)
            self.assertIn('windows-ok', result['output'])


if __name__ == '__main__':
    unittest.main()
