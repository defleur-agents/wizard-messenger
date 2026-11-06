#!/usr/bin/env python3
"""Real LINE first-run proof using only disposable scratch and internal networking.

No production containers/data, provider egress, credentials, QR payloads, login
start, pairing, or sends. Reuses the existing pinned bridge and setup adapter.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from unified_setup import setup
from connector_setup import setup_connectors
from tools.prove_connector_stack import docker, SYNAPSE, CARRIER

ROOT = Path(__file__).resolve().parents[1]


def main():
    import yaml
    pin = json.loads((ROOT / 'plumbing/connectors-provenance.json').read_text())['line']
    spec = yaml.safe_load((ROOT / 'runtipi/connectors.compose.yml').read_text())['services']['line']
    image = os.environ.get('LINE_PROOF_IMAGE', pin.get('local_image_id', pin['image']))
    for required in (SYNAPSE, CARRIER, image):
        docker('image', 'inspect', required)
    work = Path(tempfile.mkdtemp(prefix='line-first-run-', dir=os.environ.get('TMPDIR')))
    data = work / 'data'
    with patch.dict(os.environ, {'TELEGRAM_API_ID': '', 'TELEGRAM_API_HASH': ''}):
        setup(data)
    setup_connectors(data)
    assert not (data / 'line' / 'configured').exists()
    project = 'messenger-line-first-run-' + str(os.getpid())
    created = []
    result = {'coverage': 'real pinned LINE bridge; disposable data and internal network only',
              'owner_pairing_attempted': False, 'login_started': False,
              'messages_sent': 0, 'provider_egress': False, 'source_commit': pin['source_commit'],
              'tested_image_id': docker('image', 'inspect', '--format', '{{.Id}}', image),
              'tested_binary_sha256': docker('run', '--rm', '--pull=never', '--network', 'none', '--entrypoint', 'sha256sum', image, '/usr/bin/matrix-line').split()[0]}
    try:
        docker('network', 'create', '--internal', project)
        carrier = project + '-carrier'
        def launch(name, img, args, mounts, alias=None):
            cname = project + '-' + name
            docker('run', '-d', '--pull=never', '--name', cname, '--network', project,
                   '--network-alias', alias or name, '--memory', '512m', '--pids-limit', '128',
                   '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--user', '0:0',
                   *mounts, '--entrypoint', args[0], img, *args[1:])
            created.append(cname)
        launch('carrier', CARRIER, ['sleep', '600'], ['-v', str(data)+':/data', '-v', str(ROOT)+':/app:ro'])
        launch('matrix', SYNAPSE, ['python', '-m', 'synapse.app.homeserver', '--config-path', '/data/homeserver.yaml'], ['-v', str(data / 'matrix')+':/data'])
        probe = "import urllib.request,time\nfor i in range(90):\n try:\n  r=urllib.request.urlopen('http://matrix:8008/_matrix/client/versions',timeout=2);assert r.status==200;break\n except Exception:time.sleep(1)\nelse:raise RuntimeError('Disposable Synapse not ready')"
        docker('exec', carrier, 'python', '-c', probe)
        launch('line', image, ['/bin/sh', '-c', spec['command'][0]], ['-v', str(data / 'line')+':/data'])
        proof = '''import sys,json,time
sys.path.insert(0,'/app')
from unittest.mock import Mock
from connectors import Connectors
from connector_inbox import ConnectorInbox
from connector_sender import LocalOwnerSender
c=Connectors('/data/unified',writer=Mock())
assert c.status('line')['state']=='not_configured'
assert not c.pending
result={'initial_state':'not_configured'}
# Reuse the real owner bootstrap, strictly against disposable local Synapse.
inbox=ConnectorInbox('/data',Mock(),LocalOwnerSender())
try:
 inbox.matrix_token()
 result['enable']=c.dispatch('POST',['line','enable'],{})
 for i in range(60):
  status=c.status('line')
  if status['state']=='disconnected':break
  time.sleep(1)
 else:raise AssertionError('LINE did not wake after owner enable')
 expected={'dev.highest.matrix.line.qr_login','dev.highest.matrix.line.email_login'}
 ids={f['id'] for f in status['flows']}
 assert expected <= ids, 'Pinned LINE bridge must advertise both maintained owner login options'
 assert not status['logins'] and not c.pending
 result.update(final_state=status['state'],bridge_live=status['capabilities']['bridge_live'],flow_ids=sorted(ids),login_started=False)
 print(json.dumps(result))
finally:
 inbox.close()
 if inbox.store._conn is not None:inbox.store._conn.close()
'''
        result.update(json.loads(docker('exec', carrier, 'python', '-c', proof)))
    finally:
        for name in reversed(created):
            docker('rm', '-f', name)
        docker('network', 'rm', project)
        result['owned_runtime_cleaned'] = True
    output = Path(sys.argv[1] if len(sys.argv) > 1 else 'line-first-run-evidence')
    output.mkdir(parents=True, exist_ok=True)
    (output / 'real-line-first-run.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
