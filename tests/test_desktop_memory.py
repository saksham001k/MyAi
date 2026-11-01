import json
from pathlib import Path
import socket
import tempfile
import unittest

from myai.desktop_memory import DesktopMemory


EARTHMA = Path(__file__).resolve().parents[2] / 'Earthma'


@unittest.skipUnless((EARTHMA / 'earthma/memory_service.py').exists(), 'Sibling Earthma checkout required')
class DesktopMemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'data').mkdir()
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            self.port = sock.getsockname()[1]
        (self.root / 'data/desktop-memory.json').write_text(json.dumps({
            'earthma': str(EARTHMA), 'data': str(self.root / 'memory'), 'port': self.port}))

    def test_starts_reuses_preserves_records_and_restarts(self):
        owner = DesktopMemory(self.root)
        self.addCleanup(owner.close)
        adapter = owner.start()
        self.assertTrue(adapter.status()['connected'])
        record = adapter.mutate('create', {'namespace': 'desktop-test', 'text': 'Persist through desktop restart'})
        key_before = (self.root / 'memory/access.key').read_text()
        other = DesktopMemory(self.root)
        self.assertTrue(other.start().status()['connected'])
        self.assertIsNone(other.server)
        other.close()
        self.assertEqual((self.root / 'memory/access.key').read_text(), key_before)
        self.assertTrue(adapter.status()['connected'])
        owner.close()
        self.assertFalse(adapter.status()['connected'])
        adapter = owner.start()
        self.assertTrue(adapter.status()['connected'])
        self.assertEqual(adapter.records('desktop-test')[0]['text'], 'Persist through desktop restart')

    def test_busy_port_does_not_overwrite_credentials(self):
        key = self.root / 'memory/access.key'
        key.parent.mkdir()
        key.write_text('preserve-this-key')
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', self.port))
            listener.listen()
            # A missing key makes the initial health check fail without a timeout.
            key.unlink()
            with self.assertRaisesRegex(RuntimeError, 'port is busy'):
                DesktopMemory(self.root).start()
            self.assertFalse(key.exists())


if __name__ == '__main__':
    unittest.main()
