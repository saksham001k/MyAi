"""Exercise a native packaged app using a relocated workspace containing spaces."""
import json
import queue
import re
import subprocess
import sys
import tempfile
import threading
import urllib.request
from pathlib import Path


def smoke(binary):
    with tempfile.TemporaryDirectory(prefix="MyAi relocated workspace ") as tmp:
        workspace = Path(tmp) / "Shared data"
        process = subprocess.Popen([str(Path(binary).resolve()), "--root", str(workspace), "--no-browser"],
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        lines = queue.Queue()
        def reader():
            for line in process.stdout:
                lines.put(line)
        threading.Thread(target=reader, daemon=True).start()
        seen = []
        try:
            for _ in range(20):
                line = lines.get(timeout=30)
                seen.append(line)
                match = re.search(r"(http://127.0.0.1:\d+)/#token=([^\s]+)", line)
                if match:
                    break
            else:
                raise RuntimeError("Packaged app did not print a session URL")
            base, token = match.groups()
            http = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            def request(path, data=None):
                req = urllib.request.Request(base + path, headers={"Authorization": "Bearer " + token,
                    "Content-Type": "application/json"}, data=json.dumps(data).encode() if data is not None else None)
                with http.open(req, timeout=10) as response:
                    return response.read()
            assert b"MyAi" in request("/")
            json.loads(request("/api/status"))
            chat = json.loads(request("/api/chats", {}))
            assert json.loads(request("/api/chats/" + chat["id"]))["id"] == chat["id"]
            assert (workspace / "data/myai.sqlite3").is_file()
            print("Native package smoke test passed: assets, authenticated API, relocated storage.")
        except Exception as exc:
            raise RuntimeError("".join(seen) + str(exc)) from exc
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            process.stdout.close()


if __name__ == "__main__":
    smoke(sys.argv[1])
