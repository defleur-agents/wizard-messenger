"""Focused startup contract; no daemon/namespace/browser starts on the control plane."""
import ast
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess

import pytest
from test_forum_delivery import load

HERE = Path(__file__).parent


def runner_path():
    return Path(os.environ.get('RUNNER_UNDER_TEST', HERE/'forum_delivery.py'))


def daemon_argv(path, network):
    tree = ast.parse(path.read_text())
    inner = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == 'INNER' for t in n.targets))
    body = inner.split('"$BIN/dockerd"', 1)[1].split('\n}', 1)[0].replace('\\\n', '')
    # Expand only declared scalar variables; no evaluation or native operations.
    values = dict(WORK='/synthetic/run', RUN='msgsynthetic', BIN='/synthetic/bin')
    args = []
    for token in shlex.split(body):
        if token == '$@':
            args.extend(network)
        else:
            for k, v in values.items():
                token = token.replace('${'+k+'}', v).replace('$'+k, v)
            args.append(token)
    return inner, args


def test_owned_bridge_and_exact_network_delta(tmp_path):
    inner, positive = daemon_argv(runner_path(), ['--bridge', 'wzmsg0'])
    _, negative = daemon_argv(runner_path(), ['--bridge', 'wzmsg0', '--bip', '172.30.0.1/24'])
    idx = negative.index('--bip')
    assert negative[:idx] + negative[idx+2:] == positive
    assert '--bip' not in positive
    order = [inner.index(x) for x in ['mount --make-rprivate /', 'ip link add wzmsg0 type bridge',
        'ip addr add 172.30.0.1/24 dev wzmsg0', 'ip link set wzmsg0 up', 'phase daemon_start']]
    assert order == sorted(order)
    src = runner_path().read_text()
    assert "'--net','--mount','--pid','--fork','--mount-proc'" in src
    assert "['ip','link','show','wzmsg0']" in src
    assert 'docker0' not in src and 'ip link del' not in src
    assert 'daemon --bridge wzmsg0 --bip 172.30.0.1/24' in inner
    assert 'mutually exclusive options' in inner
    subprocess.run(['/bin/sh', '-n'], input=inner, text=True, check=True)


def test_actual_pinned_options_validate_without_daemon(tmp_path):
    binary = Path(os.environ['PINNED_DOCKERD'])
    assert hashlib.sha256(binary.read_bytes()).hexdigest() == '86eb329d12e512790966fa60df4e9add4bed71c310ac1fd910b5dc79cd493202'
    _, args = daemon_argv(runner_path(), ['--bridge', 'wzmsg0'])
    config = tmp_path/'daemon.json';config.write_text('{}\n')
    args[args.index('--config-file')+1] = str(config)
    # Real pinned sibling binaries, not a fake executable in a synthetic path.
    for flag, name in [('--init-path', 'docker-init'), ('--userland-proxy-path', 'docker-proxy')]:
        sibling = binary.with_name('messenger-pinned-'+name+'-29.9.0')
        assert sibling.is_file()
        args[args.index(flag)+1] = str(sibling)
    result = subprocess.run([str(binary), *args, '--validate'], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout+result.stderr
    assert 'configuration OK' in result.stdout+result.stderr
    # Explicitly retain the limitation: --validate misses the demonstrated startup conflict.
    result = subprocess.run([str(binary), *args, '--bip', '172.30.0.1/24', '--validate'], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0


@pytest.mark.parametrize('ds,status,log,expected', [
    ('0 1', '1 1', 'You specified -b & --bip, mutually exclusive options', 'never_started_config_rejected'),
    ('1 1', '1 1', '', 'ready'),
    ('0 1', '1 1', 'other failure', 'never_ready'),
    ('', '1 1', '', 'unknown'),
])
def test_failed_queries_are_not_success(tmp_path, monkeypatch, ds, status, log, expected):
    r = load(runner_path(), tmp_path)
    r['OUT'].mkdir();r['WORK'].mkdir();r['prepare_outputs']()
    for name, text in [('daemon-status.txt', ds), ('nested-cleanup-status.txt', status), ('dockerd.log', log)]:
        (r['OUT']/name).write_text(text)
    monkeypatch.setattr(subprocess, 'check_output', lambda *a, **k: ' PID COMMAND\n')
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: type('Result', (), {'returncode': 1})())
    monkeypatch.setitem(r, 'call', lambda *a, **k: None)
    r['cleanup_observation']()
    assert r['R']['cleanup']['daemon_state'] == expected
    assert r['R']['resource_absence_pass'] is True
    assert r['R']['cleanup']['nested_containers_empty'] is False
    assert r['R']['absence_pass'] is False
