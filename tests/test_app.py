import json
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from myai.server import App, make_server
from myai.storage import Store
from scripts.import_model import import_model


class FakeEngine:
    """Protocol fixture only: never used by the production application."""
    def __init__(self):
        self.running = True
        self.fail = False
        self.seen = None
        self.cancel = None

    def status(self):
        return {"running": self.running, "model": "test.gguf", "runtime_found": True, "platform": "test"}

    def models(self):
        return [{"name": "test.gguf", "bytes": 100}]

    def start(self, *args):
        self.running = True
        return self.status()

    def stop(self):
        self.running = False

    def stream(self, messages, temperature):
        self.seen = messages
        yield "Hello "
        if self.fail:
            raise RuntimeError("Test engine failure")
        if self.cancel:
            self.cancel.set()
        yield "नमस्ते 🌱"


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = FakeEngine()
        self.app = App(Path(self.temp.name), Path(__file__).resolve().parents[1] / "web", self.engine)
        self.server = make_server(self.app)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.http = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def request(self, path, body=None, method=None, authorized=True, headers=None):
        h = {"Content-Type": "application/json"}
        if authorized:
            h["Authorization"] = "Bearer " + self.app.token
        h.update(headers or {})
        req = urllib.request.Request(self.url + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers=h, method=method)
        try:
            with self.http.open(req, timeout=5) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as exc:
            with exc:
                return exc.code, exc.read()

    def chat(self):
        return json.loads(self.request("/api/chats", {})[1])["id"]

    def test_private_api_rejects_missing_token_and_foreign_origin(self):
        self.assertEqual(self.request("/api/chats", authorized=False)[0], 401)
        self.assertEqual(self.request("/api/chats", headers={"Origin": "https://evil.example"})[0], 403)
        self.assertEqual(self.request("/api/chats", headers={"Host": "evil.example"})[0], 403)

    def test_static_assets_do_not_expose_workspace(self):
        self.assertEqual(self.request("/", authorized=False)[0], 200)
        self.assertEqual(self.request("/app.js", authorized=False)[0], 200)
        self.assertEqual(self.request("/data/myai.sqlite3")[0], 404)
        self.assertEqual(self.request("/../run.py")[0], 404)

    def test_stream_unicode_and_history_used_on_next_turn(self):
        cid = self.chat()
        status, body = self.request("/api/generate", {"chat_id": cid, "prompt": "Hi"})
        self.assertEqual(status, 200)
        events = [json.loads(line) for line in body.splitlines()]
        self.assertTrue(events[-1]["done"])
        self.assertEqual("".join(e.get("token", "") for e in events), "Hello नमस्ते 🌱")
        chat = self.app.store.get(cid)
        self.assertEqual(chat["title"], "Hi")
        self.assertEqual(len(chat["messages"]), 2)
        self.request("/api/generate", {"chat_id": cid, "prompt": "Continue"})
        self.assertEqual(len(self.engine.seen), 4)
        self.assertEqual(self.engine.seen[2]["content"], "Hello नमस्ते 🌱")

    def test_engine_error_preserves_partial_response(self):
        self.engine.fail = True
        cid = self.chat()
        _, body = self.request("/api/generate", {"chat_id": cid, "prompt": "Hi"})
        self.assertEqual(json.loads(body.splitlines()[-1])["status"], "error")
        self.assertEqual(self.app.store.get(cid)["messages"][-1]["content"], "Hello ")

    def test_cancel_preserves_partial_response(self):
        self.engine.cancel = self.app.cancel
        cid = self.chat()
        self.request("/api/generate", {"chat_id": cid, "prompt": "Hi"})
        last = self.app.store.get(cid)["messages"][-1]
        self.assertEqual(last["status"], "interrupted")
        self.assertEqual(last["content"], "Hello ")

    def test_bad_requests_and_busy_gate(self):
        self.assertEqual(self.request("/api/generate", {"prompt": ""})[0], 400)
        self.assertEqual(self.request("/api/engine/start", {"context": 999})[0], 400)
        self.app.busy.acquire()
        try:
            self.assertEqual(self.request("/api/chats", {})[0], 409)
            self.assertEqual(self.request("/api/cancel", {})[0], 200)
        finally:
            self.app.busy.release()

    def test_delete_and_unloaded_model(self):
        cid = self.chat()
        self.engine.running = False
        self.assertEqual(self.request("/api/generate", {"chat_id": cid, "prompt": "Hi"})[0], 400)
        self.assertEqual(self.request(f"/api/chats/{cid}", method="DELETE")[0], 200)
        self.assertEqual(self.request(f"/api/chats/{cid}")[0], 404)

    def test_code_mode_and_media_api_auth(self):
        cid = self.chat()
        self.request("/api/generate", {"chat_id": cid, "prompt": "Write a function", "mode": "code"})
        self.assertIn("coding", self.engine.seen[0]["content"])
        self.assertEqual(self.request("/api/media", authorized=False)[0], 401)
        state = json.loads(self.request("/api/media")[1])
        self.assertEqual(len(state["presets"]), 3)
        self.assertEqual(self.request("/api/media/start", {"preset": "sd15", "prompt": "cat"})[0], 400)
        self.assertEqual(self.request("/api/media/result/invalid")[0], 404)


class PortableStorageTests(unittest.TestCase):
    def test_workspace_relocation_and_backup(self):
        with tempfile.TemporaryDirectory() as temp:
            old = Path(temp) / "Original folder" / "data"
            store = Store(old)
            cid = store.create()["id"]
            store.add(cid, "user", "Keep this on my drive")
            store.backup(Path(temp) / "backup.sqlite3")
            new = Path(temp) / "Different drive" / "data"
            shutil.copytree(old, new)
            self.assertEqual(Store(new).get(cid)["messages"][0]["content"], "Keep this on my drive")

    def test_model_import_checksums_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            model = root / "test.gguf"
            model.write_bytes(b"GGUF" + b"test" * 1024)
            with self.assertRaises(ValueError):
                import_model(model, root / "models", "0" * 64)
            self.assertFalse((root / "models" / "test.gguf").exists())
            self.assertFalse((root / "models" / "test.gguf.part").exists())
            target, digest = import_model(model, root / "models")
            self.assertEqual(target.read_bytes(), model.read_bytes())
            self.assertEqual(len(digest), 64)
            with self.assertRaises(ValueError):
                import_model(model, root / "models")

    def test_invalid_gguf(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "bad.gguf"
            source.write_bytes(b"html error page")
            with self.assertRaises(ValueError):
                import_model(source, Path(temp) / "models")


if __name__ == "__main__":
    unittest.main()
