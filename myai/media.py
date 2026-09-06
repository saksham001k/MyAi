"""Local diffusion jobs; only one expensive operation runs at a time."""
import json
import os
import re
import subprocess
import threading
import time
import uuid
from .engine import platform_tag
from .runtime import executable
from .progress import progress_event
from .studio import preprocess_image

PRESETS = {
    "sd15": {"name": "Stable Diffusion 1.5", "kind": "image", "files": {"-m": "images/v1-5-pruned-emaonly.safetensors"}},
    "sdxl": {"name": "SDXL Base 1.0 · heavier", "kind": "image", "files": {"-m": "images/sd_xl_base_1.0.safetensors"}},
    "wan13": {"name": "Wan 2.1 1.3B · experimental", "kind": "video", "files": {
        "--diffusion-model": "video/wan2.1_t2v_1.3B_fp16.safetensors",
        "--vae": "video/wan_2.1_vae.safetensors", "--t5xxl": "video/umt5-xxl-encoder-Q4_K_M.gguf"}},
}


class Media:
    def __init__(self, app):
        self.app = app
        self.root = app.root
        self.directory = self.root / "data" / "creations"
        self.directory.mkdir(exist_ok=True)
        self.state_lock = threading.Lock()
        self.thread = None
        self.cancel_event = threading.Event()
        # Interrupted jobs are never shown as still running after a restart.
        for file in self.directory.glob("*/job.json"):
            try:
                job = json.loads(file.read_text())
                if job["status"] == "running":
                    job["status"] = "interrupted"
                    self.save(job)
            except (OSError, ValueError, KeyError):
                pass

    @property
    def binary(self):
        return executable(self.root / "runtime" / platform_tag(), "sd-cli.exe" if os.name == "nt" else "sd-cli")

    def catalog(self):
        result = []
        for key, item in PRESETS.items():
            missing = [name for name in item["files"].values() if not (self.root / "models" / name).is_file()]
            result.append({"id": key, "name": item["name"], "kind": item["kind"], "missing": missing,
                           "ready": self.binary.is_file() and not missing})
        return {"presets": result, "runtime_found": self.binary.is_file()}

    def save(self, job):
        with self.state_lock:
            path = self.directory / job["id"] / "job.json"
            temp = path.with_suffix(".tmp")
            temp.write_text(json.dumps(job), encoding="utf-8")
            os.replace(temp, path)

    def get(self, jid):
        if not re.fullmatch(r"[0-9a-f]{32}", jid):
            raise KeyError("Creation not found")
        try:
            with self.state_lock:
                return json.loads((self.directory / jid / "job.json").read_text())
        except FileNotFoundError:
            raise KeyError("Creation not found") from None

    def list(self):
        jobs = []
        for file in sorted(self.directory.glob("*/job.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:100]:
            try:
                jobs.append(self.get(file.parent.name))
            except (KeyError, ValueError):
                pass
        return jobs

    def command(self, body, folder):
        preset = PRESETS.get(body.get("preset"))
        prompt = body.get("prompt")
        if preset is None or not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 4000:
            raise ValueError("Select a preset and enter a prompt of up to 4000 characters.")
        if not self.binary.is_file():
            raise ValueError("Diffusion runtime is not installed. See docs/STUDIO.md.")
        args = [str(self.binary)]
        for flag, name in preset["files"].items():
            path = self.root / "models" / name
            if not path.is_file() or not path.resolve().is_relative_to((self.root / "models").resolve()):
                raise ValueError(f"Missing model component: {name}")
            args += [flag, str(path)]
        seed = body.get("seed", 42)
        steps = body.get("steps", 20)
        if type(seed) is not int or not 0 <= seed <= 2147483647:
            raise ValueError("Seed must be a nonnegative 32-bit integer")
        if type(steps) is not int or not 1 <= steps <= 40:
            raise ValueError("Steps must be between 1 and 40")
        video = preset["kind"] == "video"
        if video and body.get("experimental") is not True:
            raise ValueError("Enable experimental video to continue.")
        output = folder / ("output.avi" if video else "output.png")
        size = 512 if body["preset"] != "sdxl" else 768
        args += ["-p", prompt.strip(), "-W", str(256 if video else size), "-H", str(256 if video else size),
                 "--steps", str(steps), "--seed", str(seed), "-o", str(output)]
        if body.get("negative_prompt"):
            if not isinstance(body["negative_prompt"], str) or len(body["negative_prompt"]) > 4000:
                raise ValueError("Negative prompt must be text up to 4000 characters.")
            args += ["-n", body["negative_prompt"].strip()]
        if body.get("img2img"):
            args += ["--init-img", body["source_path"], "--strength", str(body["strength"])]
        if video:
            args += ["-M", "vid_gen", "--video-frames", "17", "--cfg-scale", "6.0",
                     "--sampling-method", "euler", "--flow-shift", "3.0", "--offload-to-cpu", "--diffusion-fa"]
        return args, output, preset["kind"]

    def start(self, body):
        jid = uuid.uuid4().hex
        folder = self.directory / jid
        args, output, kind = self.command(body, folder)
        if not self.app.busy.acquire(blocking=False):
            raise ValueError("Another operation is running. Wait for it to finish.")
        try:
            folder.mkdir()
            self.cancel_event.clear()
            job = {"id": jid, "kind": kind, "preset": body["preset"], "prompt": body["prompt"],
                   "seed": body.get("seed", 42), "steps": body.get("steps", 20), "status": "running",
                   "created": time.time(), "error": None,
                   "progress": progress_event("studio", "Structuring composition", 5)}
            self.save(job)
            self.thread = threading.Thread(target=self.run, args=(job, args, output), daemon=True)
            self.thread.start()
            return job
        except Exception:
            self.app.busy.release()
            raise

    def start_img2img(self, body):
        """Create an img2img job after validating and normalizing its source."""
        prompt = body.get("prompt")
        if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 4000:
            raise ValueError("Enter an image editing prompt of up to 4000 characters.")
        strength = body.get("strength", 0.65)
        if type(strength) not in (int, float) or not 0.1 <= strength <= 0.95:
            raise ValueError("Strength must be between 0.1 and 0.95.")
        preset = body.get("preset", "sd15")
        target = 768 if preset == "sdxl" else 512
        jid = uuid.uuid4().hex
        folder = self.directory / jid
        source = preprocess_image(body.get("image"), folder / "source.png", target)
        payload = dict(body, preset=preset, img2img=True, source_path=str(source["path"]),
                       strength=float(strength))
        args, output, kind = self.command(payload, folder)
        if kind != "image":
            raise ValueError("Image editing requires an image preset.")
        if not self.app.busy.acquire(blocking=False):
            raise ValueError("Another operation is running. Wait for it to finish.")
        try:
            folder.mkdir(exist_ok=True)
            self.cancel_event.clear()
            job = {"id": jid, "kind": kind, "preset": preset, "prompt": prompt,
                   "source": {"width": source["width"], "height": source["height"]},
                   "strength": float(strength), "img2img": True,
                   "seed": payload.get("seed", 42), "steps": payload.get("steps", 20),
                   "status": "running", "created": time.time(), "error": None,
                   "progress": progress_event("studio", "Reading source image", 5)}
            self.save(job)
            self.thread = threading.Thread(target=self.run, args=(job, args, output), daemon=True)
            self.thread.start()
            return job
        except Exception:
            self.app.busy.release()
            raise

    def run(self, job, args, output):
        process = None
        started = time.monotonic()
        try:
            self.app.engine.stop()  # Release text-model RAM before diffusion starts.
            with (output.parent / "engine.log").open("wb") as log:
                process = subprocess.Popen(args, cwd=output.parent, stdout=log, stderr=subprocess.STDOUT)
                while process.poll() is None:
                    elapsed = time.monotonic() - started
                    percentage = min(95, max(5, int(elapsed / 1800 * 90)))
                    job["progress"] = progress_event(
                        "studio",
                        "Filling colors & lighting" if percentage >= 50
                        else "Structuring composition",
                        percentage,
                    )
                    self.save(job)
                    if self.cancel_event.wait(0.2):
                        job["status"] = "cancelled"
                        job["progress"] = progress_event("studio", "Generation cancelled", 100)
                        break
                    if time.monotonic() - started > 1800:
                        raise RuntimeError("Generation exceeded 30 minutes; try an image or fewer steps.")
                if job["status"] == "running":
                    if process.returncode != 0 or not output.is_file() or output.stat().st_size == 0:
                        raise RuntimeError("Diffusion failed. See this creation's engine.log; runtime/model compatibility may differ.")
                    job["status"] = "complete"
                    job["progress"] = progress_event("studio", "Refining textures", 100)
        except Exception as exc:
            job["status"], job["error"] = "error", str(exc)
            job["progress"] = progress_event("studio", "Generation stopped", 100, str(exc))
        finally:
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            job["seconds"] = round(time.monotonic() - started, 1)
            try:
                self.save(job)
            finally:
                self.app.busy.release()

    def result(self, jid):
        job = self.get(jid)
        if job["status"] != "complete":
            raise KeyError("Creation is not complete")
        return self.directory / jid / ("output.avi" if job["kind"] == "video" else "output.png")

    def source(self, jid):
        job = self.get(jid)
        if not job.get("img2img"):
            raise KeyError("Source image not found")
        path = self.directory / jid / "source.png"
        if not path.is_file():
            raise KeyError("Source image not found")
        return path

    def close(self):
        self.cancel_event.set()
        if self.thread:
            self.thread.join(timeout=10)
