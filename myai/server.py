"""Loopback-only HTTP API with per-launch authentication and bounded requests."""
import hmac
import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .storage import Store
from .engine import Engine
from .media import Media


class App:
    def __init__(self, root, web, engine=None):
        self.root, self.web = root, web
        for directory in ("data", "models", "runtime"):
            (root / directory).mkdir(parents=True, exist_ok=True)
        self.store = Store(root / "data")
        self.engine = engine or Engine(root)
        self.token = secrets.token_urlsafe(32)
        self.busy = threading.Lock()
        self.cancel = threading.Event()
        self.media = Media(self)


def make_server(app, port=0):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Never log prompts or session tokens.

        def headers_out(self, code, kind="application/json; charset=utf-8"):
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' blob:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers()

        def output(self, code, obj):
            self.headers_out(code)
            self.wfile.write(json.dumps(obj).encode())

        def authorized(self):
            expected_host = f"127.0.0.1:{self.server.server_port}"
            if self.headers.get("Host") != expected_host:
                self.output(403, {"error": "Invalid host"})
                return False
            origin = self.headers.get("Origin")
            if origin and origin != "http://" + expected_host:
                self.output(403, {"error": "Invalid origin"})
                return False
            if not hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + app.token):
                self.output(401, {"error": "Session expired. Open the URL printed by MyAi again."})
                return False
            return True

        def body(self):
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 256_000:
                raise ValueError("Request must be between 1 byte and 256 KB.")
            obj = json.loads(self.rfile.read(length))
            if not isinstance(obj, dict):
                raise ValueError("Expected a JSON object")
            return obj

        def do_GET(self):
            path = urlparse(self.path).path
            static = {"/": ("index.html", "text/html; charset=utf-8"),
                      "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                      "/style.css": ("style.css", "text/css; charset=utf-8")}
            if path in static:
                name, kind = static[path]
                self.headers_out(200, kind)
                self.wfile.write((app.web / name).read_bytes())
                return
            if not self.authorized():
                return
            try:
                if path == "/api/media":
                    self.output(200, {**app.media.catalog(), "jobs": app.media.list()})
                elif path.startswith("/api/media/result/"):
                    result = app.media.result(path.rsplit("/", 1)[1])
                    self.headers_out(200, "image/png" if result.suffix == ".png" else "video/x-msvideo")
                    with result.open("rb") as stream:
                        while chunk := stream.read(65536):
                            self.wfile.write(chunk)
                elif path == "/api/status":
                    self.output(200, {**app.engine.status(), "models": app.engine.models(),
                                      "busy": app.busy.locked(), "version": "0.2.0"})
                elif path == "/api/chats":
                    self.output(200, app.store.list())
                elif path.startswith("/api/chats/"):
                    self.output(200, app.store.get(path.rsplit("/", 1)[1]))
                else:
                    self.output(404, {"error": "Not found"})
            except KeyError:
                self.output(404, {"error": "Conversation not found"})

        def do_POST(self):
            if not self.authorized():
                return
            path = urlparse(self.path).path
            if path == "/api/media/start":
                try:
                    self.output(202, app.media.start(self.body()))
                except (ValueError, TypeError) as exc:
                    self.output(400, {"error": str(exc)})
                return
            if path == "/api/media/cancel":
                app.media.cancel_event.set()
                self.output(200, {"ok": True})
                return
            if path == "/api/cancel":
                app.cancel.set()
                self.output(200, {"ok": True})
                return
            if not app.busy.acquire(blocking=False):
                self.output(409, {"error": "An operation is already in progress. Stop it or wait."})
                return
            try:
                body = self.body()
                if path == "/api/chats":
                    self.output(201, app.store.create())
                elif path == "/api/engine/start":
                    context = body.get("context", 4096)
                    layers = body.get("gpu_layers", 0)
                    if type(context) is not int or context not in (2048, 4096, 8192, 16384):
                        raise ValueError("Unsupported context size")
                    if type(layers) is not int or not 0 <= layers <= 999:
                        raise ValueError("GPU layers must be between 0 and 999")
                    self.output(200, app.engine.start(body.get("model"), context, layers))
                elif path == "/api/engine/stop":
                    app.engine.stop()
                    self.output(200, {"ok": True})
                elif path == "/api/generate":
                    self.generate(body)
                else:
                    self.output(404, {"error": "Not found"})
            except KeyError:
                self.output(404, {"error": "Conversation not found"})
            except (ValueError, TypeError) as exc:
                self.output(400, {"error": str(exc)})
            except (OSError, RuntimeError):
                self.output(503, {"error": "Operation failed. Check drive permissions, free space, and data/engine.log."})
            finally:
                app.busy.release()

        def do_DELETE(self):
            if not self.authorized():
                return
            if not app.busy.acquire(blocking=False):
                self.output(409, {"error": "Wait for the current operation to finish."})
                return
            try:
                path = urlparse(self.path).path
                if not path.startswith("/api/chats/"):
                    self.output(404, {"error": "Not found"})
                    return
                app.store.delete(path.rsplit("/", 1)[1])
                self.output(200, {"ok": True})
            finally:
                app.busy.release()

        def generate(self, body):
            prompt = body.get("prompt")
            if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 16000:
                raise ValueError("Enter a message of 1–16,000 characters.")
            temperature = body.get("temperature", 0.7)
            if type(temperature) not in (int, float) or not 0 <= temperature <= 2:
                raise ValueError("Temperature must be between 0 and 2")
            if not app.engine.status()["running"]:
                raise ValueError("Load a model first.")
            chat = app.store.get(body.get("chat_id"))
            mode = body.get("mode", "chat")
            if mode not in ("chat", "code"):
                raise ValueError("Unknown chat mode")
            system = "You are MyAi, a helpful local assistant. You have no web access. Be clear and honest about uncertainty."
            if mode == "code":
                system += " You are helping with coding. State assumptions, provide complete code in fenced code blocks, explain fixes briefly, and suggest relevant tests. Never claim to have run code or accessed files."
            messages = [{"role": "system", "content": system}]
            messages += [{"role": m["role"], "content": m["content"]} for m in chat["messages"]
                         if m["status"] == "complete"]
            messages.append({"role": "user", "content": prompt.strip()})
            app.store.add(chat["id"], "user", prompt.strip())
            app.cancel.clear()
            self.headers_out(200, "application/x-ndjson; charset=utf-8")
            answer, state, error = [], "complete", None

            def event(obj):
                self.wfile.write(json.dumps(obj).encode() + b"\n")
                self.wfile.flush()

            stream = app.engine.stream(messages, temperature)
            try:
                for token in stream:
                    if app.cancel.is_set():
                        state = "interrupted"
                        break
                    answer.append(token)
                    event({"token": token})
            except (BrokenPipeError, ConnectionResetError):
                state = "interrupted"
            except Exception as exc:
                state, error = "error", str(exc)
            finally:
                stream.close()
            try:
                app.store.add(chat["id"], "assistant", "".join(answer), state)
            except Exception:
                error = "Could not save the response. Check the drive before closing this tab."
            try:
                event({"done": True, "status": state, "error": error})
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server
