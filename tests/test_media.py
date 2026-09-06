import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from myai.media import PRESETS
from myai.server import App
from scripts.setup_models import model_asset


class Engine:
    def __init__(self):
        self.stopped = False
    def stop(self):
        self.stopped = True


class MediaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.engine = Engine()
        self.app = App(self.root, self.root, self.engine)
        self.media = self.app.media
        self.media.binary.parent.mkdir(parents=True, exist_ok=True)
        self.media.binary.write_text("fixture")
        for preset in PRESETS.values():
            for name in preset["files"].values():
                path = self.root / "models" / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"fixture")

    def tearDown(self):
        self.media.close()
        self.tmp.cleanup()

    def test_image_command_keeps_prompt_as_single_argument(self):
        prompt = 'a cat; $(touch nope) "quoted"'
        args, output, kind = self.media.command({"preset": "sd15", "prompt": prompt}, self.root / "job")
        self.assertEqual(args[args.index("-p") + 1], prompt)
        self.assertEqual(output.suffix, ".png")
        self.assertEqual(kind, "image")

    def test_video_is_bounded_and_requires_opt_in(self):
        body = {"preset": "wan13", "prompt": "a walking cat"}
        with self.assertRaises(ValueError):
            self.media.command(body, self.root)
        args, output, _ = self.media.command({**body, "experimental": True}, self.root)
        self.assertEqual(args[args.index("--video-frames") + 1], "17")
        self.assertEqual(output.suffix, ".avi")
        self.assertIn("--offload-to-cpu", args)

    def test_missing_components_fail_before_model_unload(self):
        (self.root / "models" / PRESETS["sd15"]["files"]["-m"]).unlink()
        with self.assertRaises(ValueError):
            self.media.start({"preset": "sd15", "prompt": "cat"})
        self.assertFalse(self.engine.stopped)
        self.assertFalse(self.app.busy.locked())

    def test_success_unloads_chat_and_persists_result(self):
        class Process:
            returncode = 0
            def __init__(self, args, **kwargs):
                Path(args[args.index("-o") + 1]).write_bytes(b"PNG fixture")
            def poll(self):
                return 0
        with patch("myai.media.subprocess.Popen", Process):
            job = self.media.start({"preset": "sd15", "prompt": "cat"})
            self.media.thread.join(3)
        self.assertTrue(self.engine.stopped)
        self.assertEqual(self.media.get(job["id"])["status"], "complete")
        self.assertTrue(self.media.result(job["id"]).is_file())
        self.assertFalse(self.app.busy.locked())

    def test_failure_unlocks_and_cannot_download(self):
        with patch("myai.media.subprocess.Popen", side_effect=OSError("missing library")):
            job = self.media.start({"preset": "sd15", "prompt": "cat"})
            self.media.thread.join(3)
        self.assertEqual(self.media.get(job["id"])["status"], "error")
        self.assertFalse(self.app.busy.locked())
        with self.assertRaises(KeyError):
            self.media.result(job["id"])
        with self.assertRaises(KeyError):
            self.media.get("../../etc/passwd")

    def test_busy_generation_does_not_start_second_process(self):
        self.app.busy.acquire()
        try:
            with self.assertRaises(ValueError):
                self.media.start({"preset": "sd15", "prompt": "cat"})
        finally:
            self.app.busy.release()

    def test_download_pins_publisher_revision_and_requires_hash(self):
        info = {"sha": "fixedrevision", "siblings": [{"rfilename": "model.gguf", "lfs": {"sha256": "a" * 64, "size": 25}}]}
        with patch("scripts.setup_models.fetch_json", return_value=info):
            url, digest, size = model_asset("publisher/repo", "model.gguf")
            self.assertIn("/resolve/fixedrevision/", url)
            self.assertEqual(size, 25)
        info["siblings"][0]["lfs"] = {}
        with patch("scripts.setup_models.fetch_json", return_value=info), self.assertRaises(ValueError):
            model_asset("publisher/repo", "model.gguf")


if __name__ == "__main__":
    unittest.main()
