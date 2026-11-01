import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from myai.artifacts import create_html, extract_html
from myai.model_import import import_model
from myai.routing import plan_request
from myai.tasks import Tasks, ACTIVE

HTML = '<!doctype html><html><head><style>body{color:black}</style></head><body><button>1</button><script>let n=1;</script></body></html>'


class Engine:
    context = 4096
    def __init__(self, answer=HTML, finish='stop'):
        self.answer = answer
        self.last_llama_event = {'choices': [{'finish_reason': finish}]}
    def status(self):
        return {'running': True, 'model': 'coder.gguf'}
    def stream(self, *args, **kwargs):
        yield self.answer


class DesktopTests(unittest.TestCase):
    def test_route_executes_only_explicit_desktop_html_requests(self):
        models = [{'name': 'coder.gguf', 'bytes': 10}]
        for prompt in ['build me a calculator html file in desktop', 'Save a clock as clock.html on my Desktop']:
            self.assertEqual(plan_request({'prompt': prompt}, models, {})['kind'], 'artifact')
        for prompt in ['How can I build a calculator HTML file on Desktop?', "Don't create an HTML file on Desktop", 'Explain HTML', 'Write a Python file on Desktop']:
            self.assertNotEqual(plan_request({'prompt': prompt}, models, {})['kind'], 'artifact')

    def test_explanation_incomplete_and_external_files_are_rejected(self):
        for content in ['Here is how to save it', '<html><body>unfinished', '<html><body><script src="script.js"></script></body></html>']:
            with self.assertRaises(ValueError):
                extract_html(content)

    def test_task_saves_real_file_and_preserves_existing_desktop_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            desktop = root / 'Desktop'
            desktop.mkdir()
            existing = desktop / 'calculator.html'
            existing.write_text('existing user file')
            app = SimpleNamespace(root=root / 'app', busy=threading.Lock(), engine=Engine())
            tasks = Tasks(app)
            with patch('myai.artifacts.desktop_directory', return_value=desktop):
                record = tasks.start({'goal': 'build me a calculator html file in desktop', 'kind': 'artifact'})
                deadline = time.monotonic() + 5
                while record['id'] in tasks.threads and time.monotonic() < deadline:
                    time.sleep(.01)
            record = tasks.get(record['id'])
            self.assertEqual(record['status'], 'file_ready')
            self.assertIn('data-key="+"', Path(record['artifact_path']).read_text())
            self.assertEqual(existing.read_text(), 'existing user file')
            self.assertFalse(app.busy.locked())
            self.assertTrue(Path(record['output_path']).exists())

    def test_truncation_and_cancellation_do_not_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for finish, cancelled in [('length', False), ('stop', True)]:
                cancel = threading.Event()
                if cancelled:
                    cancel.set()
                with patch('myai.artifacts.desktop_directory', return_value=root):
                    with self.assertRaises((ValueError, RuntimeError)):
                        create_html(Engine(finish=finish), 'Create HTML on Desktop', cancel, root / 'draft')
                self.assertFalse((root / 'myai-app.html').exists())


class ImportTests(unittest.TestCase):
    def test_copy_checksum_duplicates_and_invalid_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'model.gguf'
            source.write_bytes(b'GGUF' + b'fixture-data')
            target, checksum = import_model(source, root / 'models')
            self.assertEqual(target.read_bytes(), source.read_bytes())
            self.assertEqual(len(checksum), 64)
            with self.assertRaises(ValueError):
                import_model(source, root / 'models')
            with self.assertRaises(ValueError):
                import_model(source, root / 'mismatch', '0' * 64)
            self.assertFalse((root / 'mismatch' / 'model.gguf').exists())
            self.assertFalse((root / 'mismatch' / 'model.gguf.part').exists())
            source.write_bytes(b'not a model')
            with self.assertRaises(ValueError):
                import_model(source, root / 'invalid')

    def test_does_not_remove_another_pending_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'model.gguf'
            source.write_bytes(b'GGUFdata')
            destination = root / 'models'
            destination.mkdir()
            partial = destination / 'model.gguf.part'
            partial.write_bytes(b'other import')
            with self.assertRaises(FileExistsError):
                import_model(source, destination)
            self.assertEqual(partial.read_bytes(), b'other import')
