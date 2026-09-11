import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from myai.engine import Engine
from myai.metrics import parse_llama_timings


class MetricsTests(unittest.TestCase):
    def test_parse_llama_timings(self):
        parsed = parse_llama_timings({
            "timings": {"prompt_ms": 120.4, "predicted_per_second": 18.5, "predicted_n": 12}
        })
        self.assertEqual(parsed["time_to_first_token_ms"], 120)
        self.assertEqual(parsed["tokens_per_second"], 18.5)
        self.assertEqual(parsed["source"], "llama.cpp timings")
        self.assertIsNone(parse_llama_timings({"choices": []}))

    def test_stream_records_llama_timings(self):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'data: {"choices":[{"delta":{"content":"Hi"}}]}\n\n')
                self.wfile.write(
                    b'data: {"choices":[{"delta":{}}],'
                    b'"timings":{"prompt_ms":50,"predicted_per_second":12.0,"predicted_n":1}}\n\n'
                )
                self.wfile.write(b"data: [DONE]\n\n")

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as temp:
                engine = Engine(Path(temp))
                engine.process = type("P", (), {"poll": staticmethod(lambda: None)})()
                engine.port = server.server_port
                self.assertEqual(list(engine.stream([{"role": "user", "content": "Hi"}], 0.7)), ["Hi"])
                self.assertEqual(engine.last_metrics["tokens_per_second"], 12.0)
                self.assertEqual(engine.last_metrics["time_to_first_token_ms"], 50)
                self.assertEqual(engine.last_metrics["source"], "llama.cpp timings")
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()
