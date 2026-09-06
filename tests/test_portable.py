import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from myai.runtime import executable
from myai.storage import Store
from scripts.package_portable import zip_tree
from scripts.prepare_pendrive import populate
from scripts.setup_mac import extract

ROOT = Path(__file__).resolve().parents[1]


class PortableTests(unittest.TestCase):
    def test_nested_runtime_paths_and_escape_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "runtime.json").write_text(json.dumps({"llama-server": "vendor/bin/llama-server"}))
            self.assertEqual(executable(root, "llama-server"), (root / "vendor/bin/llama-server").resolve())
            (root / "runtime.json").write_text(json.dumps({"llama-server": "../outside"}))
            with self.assertRaises(ValueError):
                executable(root, "llama-server")

    def test_copy_keeps_models_chats_and_platform_runtimes(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, dest = Path(tmp) / "Mac source", Path(tmp) / "USB target"
            (source / "models/video").mkdir(parents=True)
            (source / "models/test.gguf").write_bytes(b"GGUFtest")
            (source / "models/video/model.safetensors").write_bytes(b"video")
            (source / "models/incomplete.part").write_bytes(b"skip")
            store = Store(source / "data")
            cid = store.create()["id"]
            store.add(cid, "user", "Remember this")
            runtime = dest / "Workspace/runtime/windows-x86_64"
            runtime.mkdir(parents=True)
            (runtime / "runtime.json").write_text("{}")
            populate(source, dest)
            self.assertTrue((runtime / "runtime.json").is_file())
            self.assertFalse((dest / "Workspace/models/incomplete.part").exists())
            self.assertTrue((dest / "Workspace/models/video/model.safetensors").is_file())
            self.assertEqual(Store(dest / "Workspace/data").get(cid)["messages"][0]["content"], "Remember this")
            self.assertTrue((source / "models/test.gguf").exists())

    @unittest.skipIf(os.name == "nt", "Unix launcher test")
    def test_linux_launcher_follows_renamed_folder_with_spaces(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "My drive space"
            app = root / "Apps/linux-x86_64/MyAi"
            app.parent.mkdir(parents=True)
            app.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
            app.chmod(0o755)
            shutil.copy2(ROOT / "portable/Start-Linux.sh", root)
            renamed = root.with_name("Changed drive name")
            root.rename(renamed)
            # Stub uname for testing the Linux launcher on a Mac CI runner too.
            bins = Path(tmp) / "bin"
            bins.mkdir()
            (bins / "uname").write_text('#!/bin/sh\necho x86_64\n')
            (bins / "uname").chmod(0o755)
            env = {**os.environ, "PATH": str(bins) + os.pathsep + os.environ["PATH"]}
            result = subprocess.check_output(["sh", str(renamed / "Start-Linux.sh"), "--no-browser"], env=env, text=True)
            self.assertEqual(result.splitlines(), ["--root", str(renamed / "Workspace"), "--no-browser"])

    def test_zip_roundtrip_keeps_runtime_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "source/Apps").mkdir(parents=True)
            (root / "source/Apps/MyAi").write_bytes(b"app")
            zip_tree(root / "source", root / "bundle.zip")
            extract(root / "bundle.zip", root / "out")
            self.assertEqual((root / "out/Apps/MyAi").read_bytes(), b"app")
