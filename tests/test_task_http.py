import json
import threading
import tempfile
import time
import unittest
import urllib.request
import urllib.error
from pathlib import Path
from myai.server import App, make_server
from test_app import FakeEngine


class TaskHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name).resolve()
        self.engine=FakeEngine()
        self.app=App(self.root,Path(__file__).resolve().parents[1]/'web',self.engine)
        self.server=make_server(self.app)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.url=f'http://127.0.0.1:{self.server.server_port}'
        self.http=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def tearDown(self):
        self.app.tasks.close();self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup()
    def req(self,path,body=None,auth=True):
        h={'Content-Type':'application/json'}
        if auth:h['Authorization']='Bearer '+self.app.token
        q=urllib.request.Request(self.url+path,headers=h,data=json.dumps(body).encode() if body is not None else None)
        try:
            with self.http.open(q,timeout=5) as r:return r.status,r.read()
        except urllib.error.HTTPError as e:return e.code,e.read()
    def test_task_auth_status_and_invalid_parameters(self):
        self.assertEqual(self.req('/api/tasks',auth=False)[0],401)
        self.assertEqual(self.req('/api/tasks',{'goal':'test'},auth=False)[0],401)
        self.assertEqual(self.req('/api/tasks',{'goal':'test'})[0],400)
        self.assertEqual(self.req('/api/tasks/not-an-id')[0],400)
        state=json.loads(self.req('/api/status')[1])
        self.assertFalse(state['account_required']);self.assertFalse(state['paid_provider_required'])
        self.assertEqual(self.req('/css/base.css',auth=False)[0],200)
        self.assertEqual(self.req('/js/tasks.js',auth=False)[0],200)
    def test_unified_route_is_authenticated_and_uses_local_catalog(self):
        self.assertEqual(self.req('/api/route', {'prompt': 'Hello'}, auth=False)[0], 401)
        code, body = self.req('/api/route', {'prompt': 'Write a Python function'})
        self.assertEqual(code, 200)
        plan = json.loads(body)
        self.assertEqual(plan['kind'], 'code')
        self.assertEqual(plan['model'], 'test.gguf')
        self.assertIsNone(self.engine.seen)
        self.assertEqual(self.req('/api/route', {'prompt': ''})[0], 400)

    def test_unified_shell_preserves_kiss_brand_and_single_upload(self):
        html = self.req('/', auth=False)[1].decode()
        self.assertIn('alt="KISS"', html)
        self.assertIn('src="/logo.svg"', html)
        self.assertEqual(html.count('id="global-file-input"'), 1)
        self.assertNotIn('data-workspace=', html)
        self.assertNotIn('id="upload-folder"', html)
        self.assertNotIn('id="media-prompt"', html)
        self.assertNotIn('id="task-goal"', html)

    def test_preferences_and_docs_context(self):
        self.assertEqual(self.req('/api/preferences',{'instructions':'Be concise.','max_output_tokens':4096})[0],200)
        self.assertEqual(json.loads(self.req('/api/preferences')[1])['instructions'],'Be concise.')
        self.assertEqual(self.req('/api/preferences',{'max_output_tokens':-1})[0],400)
        ident='d'*32
        (self.app.uploader.root/(ident+'.txt')).write_text('The launch date is October 12.')
        cid=json.loads(self.req('/api/chats',{})[1])['id']
        code,_=self.req('/api/generate',{'chat_id':cid,'mode':'docs','prompt':'What is the launch date?','uploads':[{'id':ident,'content':'fake date'}]})
        self.assertEqual(code,200)
        supplied=json.dumps(self.engine.seen)
        self.assertIn('October 12',supplied);self.assertNotIn('fake date',supplied)
        self.assertIn('Be concise.',supplied)
        self.assertNotIn('You have no web access.', supplied)
        self.assertIn('automatically routed research workflow', supplied)
    def test_task_receives_saved_response_preferences(self):
        self.app.preferences.save({'instructions': 'Answer in concise Hinglish.', 'max_output_tokens': 2048})
        seen = []
        def stream(messages):
            seen.extend(messages)
            return iter('{"final":"No sources retrieved."}')
        self.engine.agent_stream = stream
        code, body = self.req('/api/tasks', {'kind': 'research', 'goal': 'Research a topic'})
        self.assertEqual(code, 202)
        ident = json.loads(body)['id']
        for _ in range(100):
            record = json.loads(self.req('/api/tasks/' + ident)[1])
            if record.get('output_path'):
                break
            time.sleep(.02)
        self.assertIn('Answer in concise Hinglish.', json.dumps(seen))
        self.assertIn('Do not invent capabilities', json.dumps(seen))

    def test_knowledge_api_and_forgotten_history_excluded(self):
        self.assertEqual(self.req('/api/knowledge', auth=False)[0], 401)
        self.assertEqual(self.req('/api/knowledge/memory', {'title': 'x', 'content': 'y'}, auth=False)[0], 401)
        code, saved = self.req('/api/knowledge/memory', {'title': 'Observatory launch', 'content': 'Observatory launch is 17 October.'})
        self.assertEqual(code, 200)
        saved = json.loads(saved)
        cid = json.loads(self.req('/api/chats', {})[1])['id']
        def answer(messages, temperature, max_tokens=1024):
            yield 'The observatory launch is 17 October.'
        self.engine.stream = answer
        code, stream = self.req('/api/generate', {'chat_id': cid, 'prompt': 'When is the observatory launch?'})
        self.assertEqual(code, 200)
        self.assertIn(b'"knowledge"', stream)
        self.assertTrue(self.app.store.get(cid)['messages'][-1]['knowledge_refs'])
        self.req('/api/knowledge/forget', {'id': saved['id']})
        seen = []
        def capture(messages, temperature, max_tokens=1024):
            seen.extend(messages)
            yield 'I do not have that saved fact.'
        self.engine.stream = capture
        self.req('/api/generate', {'chat_id': cid, 'prompt': 'What is the observatory launch date?'})
        self.assertNotIn('17 October', json.dumps(seen))
        self.assertEqual(json.loads(self.req('/api/knowledge')[1]), [])

    def test_library_blocks_mutation_during_generation(self):
        self.app.busy.acquire()
        try:
            self.assertEqual(self.req('/api/knowledge/memory', {'title':'x','content':'y'})[0], 409)
        finally:
            self.app.busy.release()

    def test_saved_knowledge_used_for_project_not_public_research(self):
        self.app.knowledge.save_memory({'title':'Observatory release', 'content':'Private verification code: violet-pond.'})
        seen = []
        def stream(messages):
            seen.extend(messages)
            return iter('{"final":"No files changed."}')
        self.engine.agent_stream = stream
        source = self.root / 'source'
        source.mkdir()
        (source / 'readme.txt').write_text('Verification project')
        for kind in ('project', 'research'):
            seen.clear()
            code, body = self.req('/api/tasks', {'kind':kind,'goal':'Inspect observatory release','project_path':str(source)})
            self.assertEqual(code, 202, body)
            ident = json.loads(body)['id']
            for _ in range(100):
                record = json.loads(self.req('/api/tasks/' + ident)[1])
                if record.get('output_path') and not self.app.busy.locked():
                    break
                time.sleep(.02)
            self.assertEqual('violet-pond' in json.dumps(seen), kind == 'project')

    def test_task_record_and_report_survive_new_http_request(self):
        self.engine.agent_stream=lambda _:iter('{"final":"No source read yet."}')
        code,body=self.req('/api/tasks',{'kind':'research','goal':'Make a report'})
        self.assertEqual(code,202)
        ident=json.loads(body)['id']
        for _ in range(100):
            code,body=self.req('/api/tasks/'+ident)
            record=json.loads(body)
            if record.get('output_path'):break
            time.sleep(.02)
        self.assertEqual(record['status'],'unverified')
        self.assertEqual(self.req('/api/tasks/'+ident+'/report')[0],200)
        self.assertIn(ident,self.req('/api/tasks')[1].decode())
        self.assertEqual(self.req('/api/tasks/'+ident+'/report',auth=False)[0],401)
