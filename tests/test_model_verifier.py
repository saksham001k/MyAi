import hashlib
import tempfile
import unittest
from pathlib import Path

from myai.model_verifier import sha256_file, verify_model


class ModelVerifierTests(unittest.TestCase):
    def test_checksum_matches_streamed_file(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "model.gguf"
            path.write_bytes(b"GGUF" + b"binary model data" * 100)
            expected = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(sha256_file(path), expected)
            self.assertEqual(verify_model(path, expected), (True, expected))

    def test_checksum_mismatch_and_missing_file(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "model.gguf"
            path.write_bytes(b"GGUF")
            valid, computed = verify_model(path, "0" * 64)
            self.assertFalse(valid)
            self.assertEqual(len(computed), 64)
            self.assertEqual(
                verify_model(Path(temp) / "missing.gguf", "0" * 64), (False, "")
            )


if __name__ == "__main__":
    unittest.main()
