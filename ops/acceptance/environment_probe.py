#!/usr/bin/env python3
"""Run only inside the admitted mount/user/net/PID namespaces, never on the host."""
import json, os, pathlib, shutil, socket, subprocess, tempfile
assert os.getuid() == os.getgid() == 1000, 'Application-user semantics required; root-only chown is not this test lane'
assert pathlib.Path('/proc/self/uid_map').read_text().split() == ['1000','0','1']
mounts = pathlib.Path('/proc/self/mountinfo').read_text().splitlines()
assert any(line.split()[4] == '/run' and ' - tmpfs ' in line for line in mounts), 'synthetic /run required'
p = pathlib.Path('/run/messenger/probe'); p.write_text('synthetic'); p.unlink()
with tempfile.TemporaryDirectory() as t:
    p = pathlib.Path(t) / 'account-data/backend'; p.mkdir(parents=True)
    target = str(p / 'messenger-owner.sock')
    assert len(target.encode()) < 108
    with socket.socket(socket.AF_UNIX) as s: s.bind(target)
    assert pathlib.Path(t).stat().st_uid == 1000
s = socket.socket(); s.settimeout(.2); assert s.connect_ex(('1.1.1.1',443)) != 0; s.close()
for tool, args in [('opusenc',['--version']),('mkvextract',['--version']),('ffmpeg',['-version']),('node',['--version'])]:
    assert shutil.which(tool), tool
    r = subprocess.run([tool,*args],capture_output=True,text=True,timeout=10)
    assert r.returncode == 0, (tool,r.stderr)
    print(tool,shutil.which(tool),r.stdout.splitlines()[0])
print(json.dumps({'environment_probe_pass':True,'uid':os.getuid(),'gid':os.getgid(),'uid_map':pathlib.Path('/proc/self/uid_map').read_text(),'socket_bytes':len(target.encode()),'synthetic_run':True,'network_fenced':True}))
