"""Regression coverage for BOT50 integration into the unified KISS app."""
import hashlib
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import test_app
from myai.context import budget_messages
from myai.downloads import DownloadManager
from myai.hardware import _darwin_memory, MemoryInfo, recommend_model
from myai.metrics import StreamMeter


class IntegrationTests(unittest.TestCase):
    def test_download_manager_progress_and_exclusive_start(self):
        started, finish = threading.Event(), threading.Event()

        def transfer(url, target, digest, progress, cancel):
            progress({'status': 'downloading', 'received': 20, 'total': 40})
            started.set()
            finish.wait(2)
            progress({'status': 'complete', 'received': 40, 'total': 40})
        with tempfile.TemporaryDirectory() as tmp, patch('myai.downloads.download_file', transfer):
            manager = DownloadManager(Path(tmp))
            item = {'id': 'fixture', 'filename': 'fixture.gguf', 'url': 'https://example.com/m',
                    'sha256': hashlib.sha256(b'fixture').hexdigest()}
            manager.start(item)
            try:
                self.assertTrue(started.wait(2))
                self.assertEqual(manager.snapshot()['received'], 20)
                with self.assertRaises(ValueError):
                    manager.start(item)
            finally:
                finish.set()
                manager.thread.join(3)
            self.assertEqual(manager.snapshot()['status'], 'complete')
            self.assertEqual(manager.snapshot()['received'], 40)

    def test_mac_memory_uses_16k_page_header(self):
        sample = 'Mach Virtual Memory Statistics: (page size of 16384 bytes)\nPages free: 1000.\nPages speculative: 100.\nPages purgeable: 100.\n'
        # Also accept vm_stat versions whose header has no colon.
        for header in (sample, sample.replace('Statistics:', 'Statistics')):
            with patch('myai.hardware._command_output', side_effect=[str(16 * 1024**3), header]):
                total, available, _ = _darwin_memory()
                self.assertEqual(total, 16384)
                self.assertEqual(available, 1200 * 16384 // 1024**2)

    def test_unknown_available_ram_does_not_claim_total_is_available(self):
        pick = recommend_model([{'id': 'x', 'size_bytes_approx': 1}],
                               MemoryInfo(16384, None, None, 'fixture'),
                               type('H', (), {'backend': 'cpu'})())
        self.assertIsNone(pick['model_id'])

    def test_context_preserves_current_sources_and_question(self):
        messages = [{'role': 'system', 'content': 'rules'},
                    {'role': 'user', 'content': 'old' * 3000},
                    {'role': 'assistant', 'content': 'old answer'},
                    {'role': 'user', 'content': 'current cited attachment'},
                    {'role': 'user', 'content': 'current question'}]
        result = budget_messages(messages, 2048, 256, protected_tail=2)
        self.assertEqual(result['dropped'], 2)
        self.assertEqual(result['messages'][-2:], messages[-2:])
        self.assertTrue(result['fitted'])
        messages[-2]['content'] = 'large' * 6000
        self.assertFalse(budget_messages(messages, 2048, 256, protected_tail=2)['fitted'])

    def test_first_content_latency_includes_request_setup(self):
        with patch('myai.metrics.time.monotonic', side_effect=[10, 12, 13]):
            meter = StreamMeter()
            meter.metrics.update({'prompt_ms': 17, 'source': 'llama.cpp timings'})
            list(meter.watch(iter(['Hi'])))
        self.assertEqual(meter.metrics['time_to_first_token_ms'], 2000)
        self.assertEqual(meter.metrics['prompt_ms'], 17)


class IntegratedHTTPTests(unittest.TestCase):
    setUp = test_app.ServerTests.setUp
    tearDown = test_app.ServerTests.tearDown
    request = test_app.ServerTests.request
    chat = test_app.ServerTests.chat

    def test_catalog_ui_and_readonly_explanation(self):
        self.assertEqual(self.request('/api/catalog', authorized=False)[0], 401)
        catalog = json.loads(self.request('/api/catalog')[1])
        self.assertTrue(catalog['models'])
        status = json.loads(self.request('/api/status')[1])
        self.assertIn('available_mb', status['memory'])
        self.assertFalse(status['paid_provider_required'])
        html = self.request('/', authorized=False)[1].decode()
        self.assertIn('Models &amp; performance', html)
        self.assertNotIn('/js/docs.js', html)
        self.assertEqual(self.request('/js/setup.js', authorized=False)[0], 200)
        (self.app.root / 'sample.py').write_text('def hello():\n    return 1\n')
        self.assertEqual(self.request('/api/index/explain', {'path': 'sample.py'})[0], 200)
        self.assertEqual(self.request('/api/index/explain', {'path': 'data/engine.log'})[0], 400)
        self.assertEqual(self.request('/api/catalog/download', {'id': 'missing'})[0], 404)
        self.assertEqual(self.request('/api/catalog/cancel', {})[0], 200)
        self.engine.calibrate = lambda: {'calibration': True, 'source': 'fixture only'}
        self.assertEqual(self.request('/api/engine/calibrate', {})[0], 200)

    def test_context_overflow_does_not_write_or_call_engine(self):
        cid = self.chat()
        self.engine.context = 2048
        self.app.preferences.save({'max_output_tokens': 512})
        code, body = self.request('/api/generate', {'chat_id': cid, 'prompt': 'x' * 16000})
        self.assertEqual(code, 400)
        self.assertIn('context budget', body.decode())
        self.assertIsNone(self.engine.seen)
        self.assertEqual(self.app.store.get(cid)['messages'], [])

    def test_history_pruning_preserves_saved_history_and_current_memory(self):
        cid = self.chat()
        self.engine.context = 2048
        self.app.preferences.save({'max_output_tokens': 512})
        self.app.knowledge.save_memory({'title': 'Launch', 'content': 'Launch date is October 12.'})
        self.app.store.add(cid, 'user', 'old irrelevant text ' * 1000)
        self.app.store.add(cid, 'assistant', 'old answer')
        code, body = self.request('/api/generate', {'chat_id': cid, 'prompt': 'Launch date?'})
        self.assertEqual(code, 200)
        events = [json.loads(line) for line in body.splitlines()]
        self.assertEqual(next(e['context'] for e in events if 'context' in e)['dropped'], 2)
        self.assertIn('October 12', json.dumps(self.engine.seen))
        self.assertEqual(len(self.app.store.get(cid)['messages']), 4)
