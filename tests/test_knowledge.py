import json
import tempfile
import unittest
from pathlib import Path
from myai.knowledge import Knowledge
from myai.uploader import Uploader
from myai.storage import Store


class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / 'data').mkdir()
        self.uploader = Uploader(self.root)
        self.k = Knowledge(self.root / 'data', self.uploader)
    def tearDown(self):
        self.temp.cleanup()
    def memory(self, content='The observatory launch date is 17 October.', **kw):
        return self.k.save_memory(dict(title='Observatory launch', content=content, **kw))
    def upload(self, text='The observatory launch date is 17 October.'):
        ident = 'f'*32
        p = self.uploader.root / (ident + '.txt')
        p.write_text(text)
        return ident, p
    def test_persistence_edit_and_forget_remove_old_passages(self):
        m = self.memory()
        k = Knowledge(self.root / 'data', self.uploader)
        self.assertIn('17 October', k.context('observatory launch')[0]['text'])
        refs = k.context('observatory launch')
        self.memory('The observatory launch date is 19 November.', id=m['id'])
        self.assertFalse(k.valid_refs(refs))
        text = json.dumps(k.context('observatory launch'))
        self.assertIn('19 November', text)
        self.assertNotIn('17 October', text)
        k.forget(m['id'])
        self.assertEqual(k.context('observatory launch'), [])
        self.assertFalse(k.valid_refs(refs))
    def test_project_scope_does_not_leak_to_other_projects(self):
        scope = str(self.root / 'project')
        self.memory(scope=scope)
        self.assertEqual(self.k.context('observatory launch'), [])
        self.assertEqual(self.k.context('observatory launch', str(self.root/'other')), [])
        self.assertTrue(self.k.context('observatory launch', scope))
    def test_document_edit_delete_restore_and_deduplication(self):
        ident, path = self.upload()
        doc = self.k.save_document({'upload_id': ident})
        self.assertEqual(self.k.save_document({'upload_id': ident})['id'], doc['id'])
        self.assertEqual(len(self.k.list()), 1)
        old = self.k.context('observatory launch')
        path.write_text('The observatory launch date is 22 December.')
        now = self.k.context('observatory launch')
        self.assertIn('22 December', now[0]['text'])
        self.assertNotIn('17 October', json.dumps(now))
        self.assertFalse(self.k.valid_refs(old))
        path.unlink()
        self.assertEqual(self.k.context('observatory launch'), [])
        self.assertEqual(self.k.list()[0]['state'], 'missing')
        path.write_text('The observatory launch date is 23 December.')
        self.assertIn('23 December', self.k.context('observatory launch')[0]['text'])
        self.k.forget(doc['id'])
        self.assertTrue(path.exists())
        self.assertEqual(self.k.context('observatory launch'), [])
    def test_unrelated_query_does_not_insert_memories(self):
        self.memory()
        self.assertEqual(self.k.context('photosynthesis'), [])
        self.assertEqual(self.k.context(''), [])
    def test_safe_fts_query_and_unicode(self):
        self.memory('मेरा पसंदीदा रंग नीला है।')
        self.assertTrue(self.k.context('नीला'))
        self.k.context('" OR * NEAR() : - ( )')
    def test_server_owned_document_and_no_symlinks(self):
        ident, path = self.upload()
        self.k.save_document({'upload_id': ident, 'content': 'forged'})
        self.assertNotIn('forged', json.dumps(self.k.context('observatory')))
        path.unlink()
        try:
            path.symlink_to(self.root/'outside.txt')
        except OSError as exc:
            if getattr(exc, 'winerror', None) == 1314:
                self.skipTest('Windows account cannot create symbolic links')
            raise
        (self.root/'outside.txt').write_text('outside secret')
        self.assertEqual(self.k.context('outside secret'), [])
    def test_unchanged_document_does_not_invalidate_old_reference(self):
        ident, _ = self.upload()
        self.k.save_document({'upload_id': ident})
        refs = self.k.context('observatory')
        self.k.list()
        self.assertTrue(self.k.valid_refs(refs))
    def test_invalid_memory_fields(self):
        for body in ({}, {'title': 'x', 'content': ''}, {'title':'x','content':'a'*6001}, {'title':'x','content':'hello','scope':'relative'}):
            with self.assertRaises(ValueError): self.k.save_memory(body)
    def test_existing_chat_store_migrates_and_preserves_messages(self):
        store = Store(self.root/'data')
        cid = store.create()['id']
        store.add(cid, 'user', 'Keep this message')
        store.add(cid, 'assistant', 'Remembered', knowledge_refs=[{'item_id':'example','updated':1}])
        reopened = Store(self.root/'data').get(cid)
        self.assertEqual(reopened['messages'][0]['content'], 'Keep this message')
        self.assertEqual(reopened['messages'][1]['knowledge_refs'][0]['item_id'], 'example')
