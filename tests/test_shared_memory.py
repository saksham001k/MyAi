"""Transport/auth and fresh-context guarantees; live models are tested separately."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock
import urllib.error
import urllib.request

from myai.server import App, make_server
from myai.shared_memory import SharedMemory, SharedMemoryError


FACT = {'id': 'a' * 32, 'revision': 1, 'text': 'Project codename: ORION.'}


class Engine:
    context = 2048

    def __init__(self):
        self.seen = None
        self.hook = lambda: None
        self.last_llama_event = {'choices': [{'finish_reason': 'stop'}]}

    def status(self):
        return {'running': True, 'model': 'fixture.gguf'}

    def stream(self, messages, temperature, max_tokens):
        self.seen = messages
        yield 'ORION'
        self.hook()


class FreshContextTests(unittest.TestCase):
    def setUp(self):
        self.adapter = SharedMemory()
        self.adapter.records = Mock(return_value=[dict(FACT)])
        self.engine = Engine()
        self.cancel = threading.Event()
        self.body = {'namespace': 'personal', 'question': 'What is the project codename?',
                     'history': [{'role': 'assistant', 'content': 'Old answer LYRA'}]}

    def ask(self):
        return self.adapter.ask(self.engine, self.body, self.cancel)

    def test_fresh_sources_and_no_chat_history(self):
        result = self.ask()
        self.assertEqual(result['answer'], 'ORION')
        self.assertEqual(len(self.engine.seen), 2)
        self.assertNotIn('LYRA', json.dumps(self.engine.seen))
        self.assertEqual(self.adapter.records.call_count, 2)
        self.assertEqual(result['inference_owner'], 'MyAi.Engine')

    def test_no_match_never_calls_model(self):
        self.adapter.records.return_value = []
        self.assertFalse(self.ask()['model_called'])
        self.assertIsNone(self.engine.seen)

    def test_edit_or_delete_during_generation_refuses_answer(self):
        for changed in ([], [{**FACT, 'revision': 2, 'text': 'Project codename: LYRA.'}]):
            with self.subTest(changed=changed):
                self.adapter.records.side_effect = [[FACT], changed]
                with self.assertRaises(SharedMemoryError) as caught:
                    self.ask()
                self.assertEqual(caught.exception.status, 409)

    def test_connection_loss_during_generation_refuses_answer(self):
        self.adapter.records.side_effect = [[FACT], SharedMemoryError('offline')]
        with self.assertRaises(SharedMemoryError):
            self.ask()

    def test_cancellation_does_not_publish_buffered_answer(self):
        self.engine.hook = self.cancel.set
        with self.assertRaises(SharedMemoryError):
            self.ask()

    def test_truncated_generation_refuses_answer(self):
        self.engine.last_llama_event = {'choices': [{'finish_reason': 'length'}]}
        with self.assertRaises(SharedMemoryError):
            self.ask()

    def test_unfinished_stream_never_publishes_partial_text(self):
        self.engine.last_llama_event = {'choices': [{'delta': {'content': 'ORION'}}]}
        with self.assertRaises(SharedMemoryError):
            self.ask()

    def test_oversized_context_never_calls_model(self):
        self.adapter.records.return_value = [{**FACT, 'text': 'X' * 12000}]
        with self.assertRaises(ValueError):
            self.ask()
        self.assertIsNone(self.engine.seen)


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.token_file = Path(self.temp.name) / 'access.key'
        self.token_file.write_text('first-token')
        owner = self
        self.headers_seen = []
        self.response_code = 200

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                owner.headers_seen.append(self.headers.get('Authorization'))
                self.send_response(owner.response_code)
                self.send_header('Location', '/should-not-follow')
                self.end_headers()
                self.wfile.write(b'{"records": []}')

            def log_message(self, *_):
                pass

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.adapter = SharedMemory('http://127.0.0.1:' + str(self.server.server_port), self.token_file)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def test_reads_rotated_credential_and_keeps_it_out_of_status(self):
        self.assertTrue(self.adapter.status()['connected'])
        self.token_file.write_text('second-token')
        result = self.adapter.status()
        self.assertTrue(result['connected'])
        self.assertEqual(self.headers_seen, ['Bearer first-token', 'Bearer second-token'])
        self.assertNotIn('token', json.dumps(result))

    def test_redirect_not_followed(self):
        self.response_code = 302
        with self.assertRaises(SharedMemoryError):
            self.adapter.records('personal')
        self.assertEqual(len(self.headers_seen), 1)

    def test_conflict_and_invalid_credentials_fail_closed(self):
        for remote, expected in ((409, 409), (401, 503), (500, 503)):
            self.response_code = remote
            with self.assertRaises(SharedMemoryError) as caught:
                self.adapter.records('personal')
            self.assertEqual(caught.exception.status, expected)

    def test_rejects_nonliteral_loopback_configuration(self):
        for url in ('https://example.com', 'http://localhost:99', 'http://127.0.0.1:99/path',
                    'http://user:pass@127.0.0.1:99', 'http://127.0.0.1:99?x=1'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                SharedMemory(url, self.token_file)


class EndpointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.adapter = SharedMemory()
        self.app = App(Path(self.temp.name), Path(__file__).resolve().parents[1] / 'web',
                       Engine(), self.adapter)
        self.server = make_server(self.app)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def call(self, path, body=None, authorized=True):
        req = urllib.request.Request('http://127.0.0.1:' + str(self.server.server_port) + path,
            data=None if body is None else json.dumps(body).encode(),
            headers={'Authorization': 'Bearer ' + (self.app.token if authorized else 'wrong')})
        http = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            response = http.open(req)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            return response.status, json.load(response)

    def test_requires_app_authentication(self):
        self.assertEqual(self.call('/api/shared-memory/records', authorized=False)[0], 401)
        self.assertEqual(self.call('/api/shared-memory/ask', {}, False)[0], 401)

    def test_unconfigured_is_explicit_and_no_match_is_not_an_error(self):
        self.assertEqual(self.call('/api/shared-memory/status')[1], {'configured': False, 'connected': False})
        self.assertEqual(self.call('/api/shared-memory/records')[0], 503)
        self.adapter.records = Mock(return_value=[])
        code, body = self.call('/api/shared-memory/ask', {'question': 'codename'})
        self.assertEqual(code, 200)
        self.assertFalse(body['model_called'])

    def test_stale_write_is_409_and_invalid_namespace_is_400(self):
        self.adapter.request = Mock(side_effect=SharedMemoryError('changed', 409))
        self.assertEqual(self.call('/api/shared-memory/edit', {**FACT, 'namespace': 'personal'})[0], 409)
        self.assertEqual(self.call('/api/shared-memory/records?namespace=bad%20space')[0], 400)


if __name__ == '__main__':
    unittest.main()
