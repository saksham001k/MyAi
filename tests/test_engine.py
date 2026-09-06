import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from myai.engine import Engine


class AliveProcess:
    def poll(self):
        return None


class EngineProtocolTests(unittest.TestCase):
    def test_real_http_sse_parser_and_private_headers(self):
        received = {}

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                received["path"] = self.path
                received["auth"] = self.headers["Authorization"]
                received["body"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b': heartbeat\n\ndata: {"choices":[{"delta":{"role":"assistant"}}]}\n\n')
                self.wfile.write(b'data: {"choices":[{"delta":{"content":"Hello"}}]}\n\ndata: [DONE]\n\n')

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as temp:
                engine = Engine(Path(temp))
                engine.process = AliveProcess()
                engine.port = server.server_port
                self.assertEqual(list(engine.stream([{"role": "user", "content": "Hi"}], 0.7)), ["Hello"])
                self.assertEqual(received["path"], "/v1/chat/completions")
                self.assertEqual(received["auth"], "Bearer " + engine.key)
                self.assertTrue(received["body"]["stream"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_unowned_paths_are_not_models(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "models").mkdir()
            (root / "models" / "one.gguf").write_bytes(b"GGUF")
            engine = Engine(root)
            self.assertEqual([m["name"] for m in engine.models()], ["one.gguf"])
            with self.assertRaises(ValueError):
                engine.start("../outside.gguf")
            with self.assertRaises(ValueError):
                engine.start("one.gguf")  # Runtime is not installed.


if __name__ == "__main__":
    unittest.main()
