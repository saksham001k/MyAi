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
        self.root=Path(self.tmp.name)
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
