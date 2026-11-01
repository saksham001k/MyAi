"""Own an optional Earthma service for the lifetime of the desktop app."""
import importlib
import json
import logging
from pathlib import Path
import socket
import sys
import threading

from .shared_memory import SharedMemory


class DesktopMemory:
    def __init__(self, root):
        self.root = Path(root)
        self.server = self.thread = None

    def start(self):
        config_file = self.root / 'data' / 'desktop-memory.json'
        if not config_file.exists():
            # Preserve explicitly supplied external-service configurations.
            return SharedMemory.from_environment()
        config = json.loads(config_file.read_text(encoding='utf-8'))
        data = Path(config['data']).resolve()
        repo = Path(config['earthma']).resolve()
        port = int(config.get('port', 8877))
        adapter = SharedMemory(f'http://127.0.0.1:{port}', data / 'access.key')
        if adapter.status()['connected']:
            logging.info('Reusing existing Earthma shared-memory service')
            return adapter
        # Never replace another listener or rotate credentials for a running service.
        with socket.socket() as probe:
            if probe.connect_ex(('127.0.0.1', port)) == 0:
                raise RuntimeError('The shared-memory port is busy or its credentials were rejected. '
                                   'Close the old memory service and open MyAi again.')
        if not (repo / 'earthma' / 'memory_service.py').is_file():
            raise RuntimeError('Earthma shared-memory installation was not found: ' + str(repo))
        sys.path.insert(0, str(repo))
        factory = importlib.import_module('earthma.memory_service').create_server
        self.server = factory(data, port)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        if not adapter.status()['connected']:
            self.close()
            raise RuntimeError('Earthma started but its shared-memory connection failed.')
        logging.info('Started Earthma shared memory in desktop app')
        return adapter

    def close(self):
        if self.server is not None:
            self.server.shutdown()
            self.thread.join(timeout=5)
            self.server.server_close()
            self.server.memory.close()
            self.server = self.thread = None
            logging.info('Desktop-owned Earthma service stopped')
