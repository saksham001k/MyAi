import json
import tempfile
import unittest
from pathlib import Path
from myai.workbench import Workbench
import test_app


class WorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.w = Workbench(Path(self.temp.name))

    def test_apply_undo_and_conflict(self):
        self.w.upload('src/a.py', 'old\n')
        p = self.w.propose(json.dumps({'files':[{'path':'src/a.py','content':'new\n'}, {'path':'b.py','content':'created'}]}), ['src/a.py'])
        self.assertEqual(self.w.read('src/a.py'), 'old\n')
        self.w.apply(p['id'])
        self.assertEqual(self.w.read('b.py'), 'created')
        self.w.apply(p['id'], undo=True)
        self.assertEqual(self.w.read('src/a.py'), 'old\n')
        self.assertFalse(self.w.path('b.py').exists())
        p = self.w.propose(json.dumps({'files':[{'path':'src/a.py','content':'new'}]}), ['src/a.py'])
        self.w.path('src/a.py').write_text('external')
        with self.assertRaises(ValueError): self.w.apply(p['id'])
        self.assertEqual(self.w.read('src/a.py'), 'external')

    def test_reject_unsafe_paths_binary_and_unselected_edits(self):
        for name in ['../escape','/absolute','a/../x','a\\x','.env','x/.git/config','CON','a:stream']:
            with self.subTest(name=name), self.assertRaises(ValueError): self.w.upload(name,'x')
        with self.assertRaises(ValueError): self.w.upload('bin','a\x00b')
        self.w.upload('safe.py','ok')
        with self.assertRaises(ValueError): self.w.upload('safe.py','overwrite')
        with self.assertRaises(ValueError): self.w.propose('{"files":[{"path":"safe.py","content":"bad"}]}',[])
        self.assertEqual(self.w.read('safe.py'),'ok')

    def test_context_budget_and_malformed_proposal(self):
        self.w.upload('big.txt','a'*13000)
        with self.assertRaises(ValueError): self.w.context(['big.txt'])
        for answer in ['hello','{}','{"files": []}']:
            with self.assertRaises(ValueError): self.w.propose(answer,[])


class ProjectHTTPTests(unittest.TestCase):
    setUp = test_app.ServerTests.setUp
    tearDown = test_app.ServerTests.tearDown
    request = test_app.ServerTests.request
    def test_upload_context_and_review_workflow(self):
        self.assertEqual(self.request('/api/project/upload', {'path':'hello.py','content':'print(1)'})[0],201)
        chat=json.loads(self.request('/api/chats',{})[1])
        def stream(messages, temperature, **kwargs):
            self.engine.seen=messages
            yield '{"files":[{"path":"hello.py","content":"print(2)"}]}'
        self.engine.stream=stream
        status, data = self.request('/api/generate',{'chat_id':chat['id'],'prompt':'change to 2','mode':'edit','files':['hello.py']})
        self.assertEqual(status,200)
        events=[json.loads(line) for line in data.splitlines()]
        p=next(e['proposal'] for e in events if 'proposal' in e)
        self.assertIn('print(1)',str(self.engine.seen))
        self.assertEqual(self.app.workbench.read('hello.py'),'print(1)')
        self.assertEqual(self.request('/api/project/apply',{'id':p['id']})[0],200)
        self.assertEqual(self.app.workbench.read('hello.py'),'print(2)')
        self.assertEqual(self.request('/api/project/undo',{'id':p['id']})[0],200)
        self.assertEqual(self.app.workbench.read('hello.py'),'print(1)')
