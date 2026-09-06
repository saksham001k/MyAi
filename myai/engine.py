"""Own only the llama-server process started by this application."""
import json
import secrets
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from .runtime import executable
from .platform import detect_platform
from .hardware import detect_hardware
from .model_verifier import verify_model_hash
from .tools import (click_and_type, execute_command, inspect_system, navigate,
                    take_screenshot)


def platform_tag():
    return detect_platform()["runtime_tag"]


class Engine:
    def __init__(self, root, hardware=None):
        self.root = root
        self.hardware = hardware
        self.process = None
        self.model = None
        self.port = None
        self.key = secrets.token_urlsafe(32)
        self.lock = threading.Lock()
        self.log = None
        self.http = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    @property
    def binary(self):
        info = detect_platform()
        return executable(self.root / "runtime" / info["runtime_tag"], info["executable"])

    def models(self):
        return [{"name": p.name, "bytes": p.stat().st_size}
                for p in sorted((self.root / "models").glob("*.gguf"))
                if p.is_file() and not p.is_symlink()]

    @staticmethod
    def tools():
        return {
            "navigate": navigate,
            "take_screenshot": take_screenshot,
            "click_and_type": click_and_type,
            "inspect_system": inspect_system,
            "execute_command": execute_command,
        }

    def call_tool(self, name, **arguments):
        """Invoke one of the explicitly allow-listed local agent tools."""
        try:
            tool = self.tools()[name]
        except KeyError as exc:
            raise ValueError(f"Unknown tool: {name}") from exc
        return tool(**arguments)

    def status(self):
        running = self.process is not None and self.process.poll() is None
        return {"running": running, "model": self.model if running else None,
                "runtime_found": self.binary.is_file(), "platform": platform_tag()}

    def start(self, name, context=4096, gpu_layers=None, model_sha256=None):
        if name not in {m["name"] for m in self.models()}:
            raise ValueError("Select a GGUF model from the models folder.")
        if not self.binary.is_file():
            raise ValueError(f"Add llama-server and its libraries to runtime/{platform_tag()}/ first.")
        with self.lock:
            self.stop()
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                self.port = sock.getsockname()[1]
            path = self.root / "models" / name
            valid, computed_hash = verify_model_hash(path, model_sha256)
            if not valid:
                raise ValueError(
                    f"Model checksum verification failed "
                    f"(computed {computed_hash or 'none'})."
                )
            hardware = self.hardware or detect_hardware()
            selected_layers = hardware.gpu_layers if gpu_layers is None else gpu_layers
            self.log = open(self.root / "data" / "engine.log", "wb")
            args = [str(self.binary), "--model", str(path), "--host", "127.0.0.1",
                    "--port", str(self.port), "--api-key", self.key,
                    "--ctx-size", str(context), "--n-gpu-layers", str(selected_layers),
                    "--threads", str(hardware.threads),
                    "--parallel", "1"]
            try:
                self.process = subprocess.Popen(args, cwd=self.binary.parent,
                                                stdout=self.log, stderr=subprocess.STDOUT)
                deadline = time.monotonic() + 180
                while time.monotonic() < deadline:
                    if self.process.poll() is not None:
                        raise RuntimeError("Engine exited. Check data/engine.log for model or runtime errors.")
                    try:
                        with self.http.open(self.request("/health"), timeout=2) as response:
                            if response.status == 200:
                                self.model = name
                                return self.status()
                    except (OSError, urllib.error.URLError):
                        pass
                    time.sleep(0.25)
                raise RuntimeError("Model loading timed out. Try a smaller model; see data/engine.log.")
            except Exception:
                self.stop()
                raise

    def request(self, path, data=None):
        return urllib.request.Request(f"http://127.0.0.1:{self.port}{path}",
            data=json.dumps(data).encode() if data is not None else None,
            headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"})

    def stream(self, messages, temperature, max_tokens=1024):
        if not self.status()["running"]:
            raise ValueError("Load a model before sending a message.")
        payload = {"messages": messages, "stream": True, "temperature": temperature,
                   "max_tokens": max_tokens}
        try:
            with self.http.open(self.request("/v1/chat/completions", payload), timeout=180) as response:
                for raw in response:
                    if not raw.startswith(b"data: "):
                        continue
                    line = raw[6:].strip()
                    if line == b"[DONE]":
                        return
                    event = json.loads(line)
                    if "error" in event:
                        raise RuntimeError("The inference engine reported an error.")
                    choices = event.get("choices", [])
                    if choices:
                        content = choices[0].get("delta", {}).get("content")
                        if content:
                            yield content
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Engine rejected the request ({exc.code}). The conversation may exceed the context; start a new chat or increase context.") from exc

    def stop(self):
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=5)
            self.process = None
        if self.log:
            self.log.close()
            self.log = None
        self.model = None
