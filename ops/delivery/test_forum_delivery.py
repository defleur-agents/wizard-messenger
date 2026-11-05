"""Browser/daemon-free regressions; never invoke sudo/unshare/dockerd."""
import ast
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import types

import pytest

HERE=Path(__file__).parent


def load(path, tmp_path):
    tree=ast.parse(Path(path).read_text())
    # Execute actual source functions, not its top-level native entry/imports.
    keep=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.Assign)) and not (isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in {'ROOT','RUN','OUT','WORK','R'} for t in n.targets))]
    ns=dict(Path=Path,hashlib=hashlib,json=json,os=os,stat=stat,subprocess=subprocess,
            ROOT=tmp_path,WORK=tmp_path/'run',OUT=tmp_path/'results',RUN='msgsynthetic',
            R={'pass':False},digest_file=lambda p:hashlib.sha256(p.read_bytes()).hexdigest(),
            time=types.SimpleNamespace(sleep=lambda _:None))
    exec(compile(ast.Module(body=keep,type_ignores=[]),str(path),'exec'),ns)
    return ns


@pytest.fixture
def runner(tmp_path):
    return load(os.environ.get('RUNNER_UNDER_TEST',HERE/'forum_delivery.py'),tmp_path)


def test_private_daemon_config_and_no_host_env(runner):
    inner=runner['INNER']
    assert '--config-file "$WORK/daemon.json"' in inner
    assert '/etc/docker/daemon.json' not in inner
    src=Path(os.environ.get('RUNNER_UNDER_TEST',HERE/'forum_delivery.py')).read_text()
    assert "['sudo','-n','env','-i'" in src
    assert 'dict(os.environ' not in src
    for guard in ['--net','--mount','--pid','--mount-proc','host-socket-blocked','--cgroup-parent','--registry-mirror http://127.0.0.1']:
        assert guard in src


def test_precreated_worker_owned_outputs_preserve_inode(runner):
    out=runner['OUT'];out.mkdir();runner['WORK'].mkdir()
    runner['prepare_outputs']()
    assert json.loads((runner['WORK']/'daemon.json').read_text())=={}
    for name in runner['ROOT_OUTPUTS']:
        p=out/name;st=p.stat()
        assert (st.st_uid,st.st_gid,stat.S_IMODE(st.st_mode))==(1000,1000,0o600)
        # Ordinary redirection behavior only: actual root append checked natively later.
        subprocess.run(['/bin/sh','-c','printf synthetic >"$1"','sh',str(p)],check=True)
        assert p.stat().st_ino==st.st_ino
        assert runner['safe_read'](p)==b'synthetic'
    with pytest.raises(FileExistsError):runner['prepare_outputs']()


@pytest.mark.parametrize('kind',['unreadable','symlink','fifo'])
def test_artifact_error_never_masks_primary_and_receipt(runner,monkeypatch,kind):
    out=runner['OUT'];out.mkdir()
    p=out/'diagnostic.log'
    if kind=='symlink':p.symlink_to(out/'absent')
    elif kind=='fifo':os.mkfifo(p)
    else:p.write_text('synthetic')
    (out/'root-phase.txt').write_text('daemon_readiness');(out/'root-phase.txt').chmod(0o600)
    real=runner['safe_read']
    def reader(path):
        if kind=='unreadable' and path==p:raise PermissionError('synthetic denied')
        return real(path)
    monkeypatch.setitem(runner,'safe_read',reader)
    runner['R'].update(pass_=False,absence_pass=True,primary_errors=[{'phase':'namespace_wait','type':'RuntimeError','message':'private namespace exited 17'}])
    assert runner['finalize']()==1
    r=json.loads((out/'receipt.json').read_text())
    assert r['primary_errors'][0]['message']=='private namespace exited 17'
    assert r['artifact_errors'] and r['pass'] is False


def test_native_namespace_exit_failure_keeps_receipt(runner,monkeypatch):
    monkeypatch.setitem(runner,'verify',lambda:{'source':'immutable','images':[]})
    (runner['ROOT']/'manifest.json').write_text('{}')
    monkeypatch.setitem(runner,'tools',lambda _:tuple(Path('/synthetic') for _ in range(4)))
    class Child:
        pid=12345
        def wait(self,**kw):return 17
        def poll(self):return 17
    monkeypatch.setattr(subprocess,'Popen',lambda *a,**k:Child())
    monkeypatch.setitem(runner,'cleanup_observation',lambda:runner['R'].update(absence_pass=False,cleanup={'known':False}))
    assert runner['entry']()==1
    r=json.loads((runner['OUT']/'receipt.json').read_text())
    assert r['namespace_exit']==17 and r['primary_errors'][0]['phase']=='namespace_wait'
    assert r['pass'] is False and not r['driver_pass']


@pytest.mark.parametrize('status,empty,expected',[('0 0',True,True),('1 1',True,False),('',True,False),('0 0',False,False)])
def test_cleanup_empty_requires_successful_queries(runner,monkeypatch,status,empty,expected):
    out=runner['OUT'];out.mkdir();runner['WORK'].mkdir();runner['prepare_outputs']()
    (out/'nested-cleanup-status.txt').write_text(status)
    (out/'nested-after-cleanup.txt').write_text('' if empty else 'container')
    monkeypatch.setattr(subprocess,'check_output',lambda *a,**k:' PID COMMAND\n')
    monkeypatch.setattr(subprocess,'run',lambda *a,**k:types.SimpleNamespace(returncode=1))
    monkeypatch.setitem(runner,'call',lambda *a,**k:None)
    runner['cleanup_observation']()
    assert runner['R']['absence_pass'] is expected


def test_unknown_cleanup_cannot_pass(runner):
    out=runner['OUT'];out.mkdir()
    (out/'root-phase.txt').write_text('cleanup');(out/'root-phase.txt').chmod(0o600)
    runner['R'].update({'pass':True,'absence_pass':False,'cleanup':{'known':False}})
    assert runner['finalize']()==1
    assert json.loads((out/'receipt.json').read_text())['pass'] is False


def test_inner_phase_and_query_status_are_recorded(runner):
    inner=runner['INNER']
    assert 'inner_rc=$?' in inner and 'root-failure-phase.txt' in inner
    assert 'before=0;' in inner and 'after=0;' in inner
    subprocess.run(['/bin/sh','-n'],input=inner.encode(),check=True)


def test_old_finalizer_negative_control(tmp_path):
    old=HERE/'fixtures/forum_delivery_r3.py'
    assert hashlib.sha256(old.read_bytes()).hexdigest()=='dc5e0ae2377864d30114e7bc9f88ee727a4cbedcc4cf8de432f02c05e1460de9'
    tree=ast.parse(old.read_text())
    guard=next(n for n in tree.body if isinstance(n,ast.If))
    final=next(n for n in guard.body if isinstance(n,ast.Try)).finalbody
    out=tmp_path/'results';out.mkdir();(out/'dockerd.log').write_text('synthetic')
    def denied(_):raise PermissionError('synthetic root-owned diagnostic')
    ns=dict(OUT=out,R={'error':'original daemon startup failed'},digest_file=denied,json=json)
    with pytest.raises(PermissionError):exec(compile(ast.Module(body=final,type_ignores=[]),str(old),'exec'),ns)
    assert not (out/'receipt.json').exists()
    assert ns['R']['error']=='original daemon startup failed'


def test_cleanup_unreadable_status_records_unknown_not_pass(runner,monkeypatch):
    out=runner['OUT'];out.mkdir();runner['WORK'].mkdir();runner['prepare_outputs']()
    monkeypatch.setattr(subprocess,'check_output',lambda *a,**k:' PID COMMAND\n')
    monkeypatch.setattr(subprocess,'run',lambda *a,**k:types.SimpleNamespace(returncode=1))
    monkeypatch.setitem(runner,'call',lambda *a,**k:None)
    def denied(_):raise PermissionError('synthetic status denied')
    monkeypatch.setitem(runner,'safe_read',denied)
    runner['R']['primary_errors']=[{'message':'startup failed'}]
    runner['cleanup_observation']()
    assert runner['R']['cleanup_errors'] and not runner['R']['absence_pass']
    assert runner['R']['primary_errors']==[{'message':'startup failed'}]


def test_entry_refuses_existing_original_results(runner):
    runner['OUT'].mkdir();p=runner['OUT']/'receipt.json';p.write_text('original')
    with pytest.raises(AssertionError):runner['entry']()
    assert p.read_text()=='original'
