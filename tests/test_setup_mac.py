import hashlib
import io
import os
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.setup_mac import choose_asset, download, extract


class SetupTests(unittest.TestCase):
    def test_selects_only_official_checksummed_arm_runtime(self):
        base = {"name": "llama-b9999-bin-macos-arm64.tar.gz",
                "browser_download_url": "https://github.com/ggml-org/llama.cpp/releases/download/b9999/runtime.tar.gz"}
        release = {"tag_name": "b9999", "assets": [{**base, "digest": None}, {**base, "digest": "sha256:" + "a" * 64}]}
        self.assertEqual(choose_asset([release])[1]["digest"], "sha256:" + "a" * 64)
        with self.assertRaises(ValueError):
            choose_asset([{"tag_name": "bad", "assets": [{**base, "digest": None}]}])

    def test_download_verifies_and_reuses_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "model.gguf"
            digest = hashlib.sha256(b"GGUFtest").hexdigest()
            def curl(args, **kwargs):
                Path(args[args.index("--output") + 1]).write_bytes(b"GGUFtest")
            with patch("scripts.setup_mac.subprocess.run", side_effect=curl) as run:
                download("https://example.com/file", path, digest)
                download("https://example.com/file", path, digest)
                self.assertEqual(run.call_count, 1)
            self.assertEqual(path.read_bytes(), b"GGUFtest")

    def test_failed_hash_does_not_publish_partial_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "model.gguf"
            def curl(args, **kwargs):
                Path(args[args.index("--output") + 1]).write_bytes(b"bad")
            with patch("scripts.setup_mac.subprocess.run", side_effect=curl):
                with self.assertRaises(ValueError):
                    download("https://example.com/file", path, "0" * 64)
            self.assertFalse(path.exists())
            self.assertFalse(path.with_name("model.gguf.part").exists())

    @unittest.skipIf(os.name == "nt", "macOS runtime extraction uses Unix symlinks")
    def test_extraction_keeps_nested_libraries_and_safe_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "runtime.tar.gz"
            with tarfile.open(archive, "w:gz") as bundle:
                for name in ("build/bin/llama-server", "build/lib/libggml.1.dylib"):
                    item = tarfile.TarInfo(name)
                    item.size, item.mode = 4, 0o755
                    bundle.addfile(item, io.BytesIO(b"test"))
                item = tarfile.TarInfo("build/lib/libggml.dylib")
                item.type, item.linkname = tarfile.SYMTYPE, "libggml.1.dylib"
                bundle.addfile(item)
            extract(archive, root / "out")
            self.assertEqual((root / "out/build/lib/libggml.dylib").read_bytes(), b"test")
            self.assertTrue((root / "out/build/bin/llama-server").stat().st_mode & 0o111)

    def test_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "bad.tar.gz"
            with tarfile.open(archive, "w:gz") as bundle:
                item = tarfile.TarInfo("../escape")
                item.size = 4
                bundle.addfile(item, io.BytesIO(b"oops"))
            with self.assertRaises(ValueError):
                extract(archive, root / "out")
            self.assertFalse((root / "escape").exists())


if __name__ == "__main__":
    unittest.main()
