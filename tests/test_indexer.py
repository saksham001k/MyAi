import tempfile
import unittest
from pathlib import Path

from myai.indexer import WorkspaceIndexer


class IndexerTests(unittest.TestCase):
    def test_explain_is_read_only_and_requires_review_note(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "sample.py"
            target.write_text("def hello():\n    return 1\n", encoding="utf-8")
            original = target.read_bytes()
            indexer = WorkspaceIndexer(root)
            info = indexer.explain("sample.py")
            self.assertEqual(info["symbols"][0]["name"], "hello")
            self.assertTrue(info["review_required"])
            self.assertIn("Read-only", info["note"])
            self.assertEqual(target.read_bytes(), original)
            files = indexer.scan("sample")
            self.assertEqual(files[0]["path"], "sample.py")
