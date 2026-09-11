import hashlib
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from myai.catalog import describe, find_model, resolve_digest
from myai.downloads import download_file
from myai.hardware import MemoryInfo, recommend_context, recommend_model


class CatalogTests(unittest.TestCase):
    def test_catalog_lists_licenses_and_pinned_runtime_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = describe(Path(tmp), MemoryInfo(16384, 12000, None, "test"),
                               type("H", (), {"backend": "cpu", "gpu_layers": 0, "threads": 4})())
        self.assertTrue(payload["models"])
        self.assertTrue(all(m.get("license") for m in payload["models"]))
        qwen = next(m for m in payload["models"] if m["id"] == "qwen3-4b-q4")
        self.assertEqual(len(qwen["sha256"]), 64)
        self.assertIn("Apache", qwen["license"])
        self.assertTrue(payload["disclaimer"])

    def test_find_model_rejects_unknown(self):
        with self.assertRaises(KeyError):
            find_model("missing-model")

    def test_resolve_digest_uses_pinned_hash(self):
        item = find_model("qwen3-4b-q4")
        url, digest = resolve_digest(item)
        self.assertTrue(url.startswith("https://"))
        self.assertEqual(digest, item["sha256"])


class RecommendationTests(unittest.TestCase):
    def test_small_ram_rejects_large_model(self):
        self.assertIsNone(recommend_context(3000, 4_000_000_000, "cpu"))
        self.assertIn(recommend_context(16000, 2_500_000_000, "cpu"), (2048, 4096, 8192, 16384))

    def test_recommend_model_picks_smallest_fit(self):
        models = [
            {"id": "big", "filename": "big.gguf", "size_bytes_approx": 8_000_000_000, "min_ram_gb": 16, "recommended_context": 4096},
            {"id": "small", "filename": "small.gguf", "size_bytes_approx": 1_000_000_000, "min_ram_gb": 6, "recommended_context": 4096},
        ]
        hardware = type("H", (), {"backend": "cpu", "gpu_layers": 0, "threads": 4})()
        pick = recommend_model(models, MemoryInfo(8192, 7000, None, "test"), hardware)
        self.assertEqual(pick["model_id"], "small")
        self.assertEqual(pick["context"], 4096)


class DownloadResumeTests(unittest.TestCase):
    def test_resume_and_refuse_bad_complete_file(self):
        payload = b"GGUF" + b"xyz" * 1000
        digest = hashlib.sha256(payload).hexdigest()

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                start = 0
                rng = self.headers.get("Range")
                if rng and rng.startswith("bytes="):
                    start = int(rng.split("=", 1)[1].split("-")[0] or 0)
                    self.send_response(206)
                    self.send_header("Content-Range", f"bytes {start}-{len(payload)-1}/{len(payload)}")
                else:
                    self.send_response(200)
                body = payload[start:]
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/file"
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "model.gguf"
                partial = path.with_name("model.gguf.part")
                partial.write_bytes(payload[:200])
                download_file(url, path, digest, allow_loopback=True)
                self.assertEqual(path.read_bytes(), payload)
                self.assertFalse(partial.exists())
                download_file(url, path, digest, allow_loopback=True)
                path.write_bytes(b"wrong")
                with self.assertRaises(ValueError):
                    download_file(url, path, digest, allow_loopback=True)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()
