"""Disposable owner-session fixture. Never points at installed Messenger."""
import json
from pathlib import Path
import sys
import tempfile
from test_web import FakeEngine
from web import ViewServer

with tempfile.TemporaryDirectory() as root:
    engine = FakeEngine()
    engine.data = Path(root)
    server = ViewServer(('127.0.0.1', 0), engine, 'fixture-token' * 4, [sys.argv[1]])
    token, session = server.auth.create()
    print(json.dumps(dict(port=server.server_port, cookie=token, csrf=session['csrf'])), flush=True)
    server.serve_forever()
