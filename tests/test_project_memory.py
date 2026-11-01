import json
from pathlib import Path
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from myai.project_memory import ProjectMemory
from myai.shared_memory import SharedMemoryError
from myai.tasks import Tasks, ACTIVE


def context(workspace=''):
    return {'project': {'id': 'a'*32, 'goal': 'Library app', 'workspace': workspace,
        'acceptance': ['Persist loans'], 'revision': 2, 'state': 'Backend ready', 'next_action': 'Build UI'},
        'decisions': [{'id': 'b'*32, 'key': 'owner', 'value': 'NILA', 'revision': 2}],
        'conflicts': [], 'handoff': None,
        'manifest': {'project_id': 'a'*32, 'revision': 2, 'sha256': 'c'*64}}


class Engine:
    context = 4096
    def __init__(self, name='model-A'):
        self.name = name
        self.seen = None
        self.hook = lambda: None
        self.last_llama_event = {'choices': [{'finish_reason': 'stop'}]}
    def status(self): return {'running': True, 'model': self.name}
    def stream(self, messages, temperature, max_tokens=1024):
        self.seen = messages
        yield '{"final":"NILA should build UI."}'
        self.hook()
    def stop(self): pass


class ProjectMemoryTests(unittest.TestCase):
    def setUp(self):
        self.shared = Mock()
        self.shared.request.return_value = context()
        self.memory = ProjectMemory(self.shared)
    def test_paraphrase_uses_mandatory_state_for_two_models(self):
        for name in ('model-A', 'model-B'):
            engine = Engine(name)
            answer = self.memory.ask(engine, {'project_id': 'a'*32, 'question': 'Who leads this work?'}, threading.Event())
            self.assertIn('NILA', json.dumps(engine.seen))
            self.assertIn('Persist loans', json.dumps(engine.seen))
            self.assertEqual(answer['model'], name)
    def test_revision_change_or_wrong_project_refuses_publication(self):
        engine = Engine()
        changed = context(); changed['manifest']['revision'] = 3
        self.shared.request.side_effect = [context(), changed]
        with self.assertRaises(SharedMemoryError):
            self.memory.ask(engine, {'project_id': 'a'*32, 'question': 'Continue'}, threading.Event())
        wrong = context(); wrong['project']['id'] = 'd'*32
        self.shared.request.side_effect = None; self.shared.request.return_value = wrong
        with self.assertRaises(SharedMemoryError): self.memory.context('a'*32)
    def test_context_overflow_does_not_drop_required_records_or_call_model(self):
        oversized = context(); oversized['project']['goal'] = 'x'*20000
        self.shared.request.return_value = oversized
        engine = Engine()
        with self.assertRaises(ValueError):
            self.memory.ask(engine, {'project_id': 'a'*32, 'question': 'Continue'}, threading.Event())
        self.assertIsNone(engine.seen)
    def test_conflicts_are_supplied_and_incomplete_stream_is_refused(self):
        conflicted = context(); conflicted['conflicts'] = [{'key': 'channel', 'values': ['GREEN', 'RED']}]
        self.shared.request.return_value = conflicted
        engine = Engine(); engine.last_llama_event = {'choices': [{'finish_reason': 'length'}]}
        with self.assertRaises(SharedMemoryError):
            self.memory.ask(engine, {'project_id': 'a'*32, 'question': 'Channel?'}, threading.Event())
        self.assertIn('CONFLICT', json.dumps(engine.seen))
        self.assertIn('GREEN', json.dumps(engine.seen))


class LinkedTaskTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.source = self.root/'source'; self.source.mkdir()
        (self.source/'app.py').write_text('answer = 1\n')
        shared = Mock(); shared.request.return_value = context(str(self.source))
        self.memory = ProjectMemory(shared)
        self.memory.mutate = Mock(return_value={'handoff_id': 'd'*32})
        self.app = SimpleNamespace(root=self.root/'app', busy=threading.Lock(), engine=Engine(), project_memory=self.memory)
        self.tasks = Tasks(self.app)
    def tearDown(self):
        self.tasks.close(); self.temp.cleanup()
    def wait(self, task_id):
        for _ in range(200):
            result = self.tasks.get(task_id)
            if result['status'] not in ACTIVE and task_id not in self.tasks.threads: return result
            time.sleep(.01)
        self.fail('Task did not finish')
    def test_linked_task_receives_current_state_and_publishes_hashed_handoff(self):
        task = self.tasks.start({'goal': 'Explain next work', 'project_path': str(self.source), 'shared_project_id': 'a'*32})
        result = self.wait(task['id'])
        self.assertIn('NILA', json.dumps(self.app.engine.seen))
        self.assertEqual(result['memory_sync']['status'], 'saved')
        saved = self.memory.mutate.call_args.args[2]
        self.assertIn('not run', saved['verification'].lower())
        self.assertRegex(saved['artifacts'][0]['sha256'], '^[0-9a-f]{64}$')
        self.assertEqual(Tasks(self.app).get(task['id'])['shared_context']['manifest']['revision'], 2)
    def test_wrong_workspace_is_refused_before_task_creation(self):
        with self.assertRaises(ValueError):
            self.tasks.start({'goal': 'Update', 'project_path': str(self.root), 'shared_project_id': 'a'*32})
        self.assertEqual(self.tasks.list(), [])
    def test_offline_handoff_retains_local_result_and_reports_pending(self):
        self.memory.mutate.side_effect = SharedMemoryError('offline')
        task = self.tasks.start({'goal': 'Explain next work', 'project_path': str(self.source), 'shared_project_id': 'a'*32})
        result = self.wait(task['id'])
        self.assertEqual(result['memory_sync']['status'], 'pending')
        self.assertTrue(Path(result['output_path']).is_file())
