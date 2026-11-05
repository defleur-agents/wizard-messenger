#!/usr/bin/env python3
"""Parent-admitted finite Forum job; private namespaces/daemon only. No live target writes."""
from pathlib import Path
import hashlib, json, os, shutil, signal, stat, subprocess, sys, tarfile, time, urllib.request
sys.path.insert(0,str(Path(__file__).parent))
from registry_archive import export,digest_file
ROOT=Path(__file__).resolve().parents[1]
RUN='msg'+hashlib.sha256((ROOT/'manifest.json').read_bytes()).hexdigest()[:12]
OUT=ROOT/'results'; WORK=ROOT/'run'; R={'pass':False,'live_mutation':False,'source_suite_repeated':False,'run':RUN,'native_accepted':False,'converter_ingress_native_pass':False,'native_gate_note':'Signal converter public-ingress fixture remains required; no skip is native acceptance'}
def call(a,**kw):return subprocess.run(a,check=True,**kw)
def verify():
    assert str(ROOT).startswith('/srv/work/') and os.uname().machine=='x86_64'
    m=json.loads((ROOT/'manifest.json').read_text())
    for n,h in m['files'].items(): assert digest_file(ROOT/n)==h,n
    custody=json.loads((ROOT/'capsule/source-custody.json').read_text())
    for group,names in [('messenger',['approved-source','candidate','engine-source','recipe-source','live-source','current-live-source']),('shell',['shell']),('wam',['wam'])]:
        probe=ROOT/('verify-'+group+'.git');assert not probe.exists()
        call(['git','init','--bare','-q',str(probe)])
        try:
            with open(ROOT/'capsule'/(group+'-provenance.pack'),'rb') as f:call(['git','--git-dir='+str(probe),'index-pack','--stdin'],stdin=f,stdout=subprocess.DEVNULL)
            for name in names:
                raw=subprocess.check_output(['git','--git-dir='+str(probe),'archive','--format=tar',custody[name]['commit']]+(['web'] if name=='shell' else []))
                assert hashlib.sha256(raw).hexdigest()==custody[name]['sha256']
        finally:shutil.rmtree(probe)
    return json.loads((ROOT/'capsule/inputs.json').read_text())
def tools(i):
    d=ROOT/'tools';d.mkdir(exist_ok=True);b=d/'bin';b.mkdir(exist_ok=True)
    for name,s in i['tools'].items():
        p=d/name
        if not p.exists():
            with urllib.request.urlopen(s['url'],timeout=180) as r,open(str(p)+'.part','wb') as f:shutil.copyfileobj(r,f)
            Path(str(p)+'.part').replace(p)
        assert digest_file(p)==s['sha256']
    with tarfile.open(d/'docker') as t:
        for m in t:
            if m.isfile() and m.name.startswith('docker/'):
                m.name=m.name.split('/',1)[1];t.extract(m,b,filter='data')
    cfg=d/'config';(cfg/'cli-plugins').mkdir(parents=True,exist_ok=True)
    shutil.copy2(d/'compose',cfg/'cli-plugins/docker-compose');(cfg/'cli-plugins/docker-compose').chmod(0o755)
    base=Path(i['reuse_tools_root']);closure=json.loads((ROOT/'capsule/accepted-tool-closure.json').read_text())
    # Accepted complete Node/Playwright/Chromium closure, never a version-only or host-node substitute.
    for n,h in closure.items():assert digest_file(base/n)==h,n
    node=base/'node/node_modules/node/bin/node';assert node.is_file()
    return b,cfg,node,base
INNER=r'''#!/bin/sh
set -eu
mount --make-rprivate /
ip link set lo up
phase() { printf '%s\n' "$1" >"$OUT/root-phase.txt"; }
phase namespace_setup
# DNS/registry routing exists only in this mount+network namespace.
cp /etc/hosts "$WORK/hosts"
printf '\n127.0.0.1 ghcr.io dock.mau.dev registry-1.docker.io docker.io\n' >>"$WORK/hosts"
mount --bind "$WORK/hosts" /etc/hosts
if [ -S /var/run/docker.sock ]; then touch "$WORK/host-socket-blocked"; mount --bind "$WORK/host-socket-blocked" /var/run/docker.sock; fi
python3 "$ROOT/capsule/registry_fixture.py" "$ROOT" >"$OUT/registry.log" 2>&1 &
RPID=$!
mkdir -p "$WORK/graph" "$WORK/exec" "$WORK/socket" "$WORK/cdi" "$WORK/extensions"
# Use the existing admitted sudo capability; never chmod/chown the worker host socket or alter privilege policy.
phase daemon_start
"$BIN/dockerd" --config-file "$WORK/daemon.json" --host "unix://$WORK/socket/docker.sock" --data-root "$WORK/graph" --exec-root "$WORK/exec" --pidfile "$WORK/daemon.pid" \
 --bridge wzmsg0 --bip 172.30.0.1/24 --default-address-pool base=172.31.0.0/16,size=24 --iptables=true --ip6tables=false \
 --cdi-spec-dir "$WORK/cdi" --extension-dir "$WORK/extensions" --init-path "$BIN/docker-init" \
 --userland-proxy-path "$BIN/docker-proxy" --exec-opt native.cgroupdriver=cgroupfs --cgroup-parent "$RUN" \
 --insecure-registry ghcr.io --insecure-registry dock.mau.dev --insecure-registry registry-1.docker.io --insecure-registry docker.io --registry-mirror http://127.0.0.1 \
 --feature containerd-snapshotter=false --storage-driver overlay2 --containerd-namespace "$RUN" --containerd-plugins-namespace "${RUN}p" --label "wizard.qa.run=$RUN" >"$OUT/dockerd.log" 2>&1 &
DPID=$!
cleanup() {
 inner_rc=$?
 set +e
 if [ "$inner_rc" != 0 ]; then cat "$OUT/root-phase.txt" >"$OUT/root-failure-phase.txt"; fi
 phase cleanup
 D="$BIN/docker -H unix://$WORK/socket/docker.sock"
 before=0; $D ps -aq >"$OUT/nested-before-cleanup.txt" || before=$?
 for c in $($D ps -aq); do $D rm -f "$c" >/dev/null 2>&1; done
 after=0; $D ps -aq >"$OUT/nested-after-cleanup.txt" || after=$?
 printf '%s %s\n' "$before" "$after" >"$OUT/nested-cleanup-status.txt"
 kill -TERM "$DPID" "$RPID" 2>/dev/null
 for i in $(seq 1 30); do kill -0 "$DPID" 2>/dev/null || break; sleep 1; done
 kill -KILL "$DPID" "$RPID" 2>/dev/null
}
trap cleanup EXIT INT TERM
phase daemon_readiness
ready=0
for i in $(seq 1 90); do if "$BIN/docker" -H "unix://$WORK/socket/docker.sock" info >/dev/null 2>&1; then ready=1; break; fi; kill -0 "$DPID" 2>/dev/null || break; sleep 1; done
[ "$ready" = 1 ]
chown 1000:1000 "$WORK/socket/docker.sock"; chmod 600 "$WORK/socket/docker.sock"
phase delivery_driver
setpriv --reuid=1000 --regid=1000 --clear-groups env -i PATH="$BIN:/usr/bin:/bin" HOME="$WORK/home" TMPDIR="$WORK/tmp" \
 ROOT="$ROOT" WORK="$WORK" OUT="$OUT" RUN="$RUN" DOCKER_HOST="unix://$WORK/socket/docker.sock" DOCKER_CONFIG="$CONFIG" DOCKER_BUILDKIT=0 \
 NODE="$NODE" NODE_PATH="$DEPS/node/node_modules" PLAYWRIGHT_MODULE="$DEPS/node/node_modules/playwright" PLAYWRIGHT_BROWSERS_PATH="$DEPS/browsers" \
 python3 -B "$ROOT/capsule/delivery_driver.py" >"$OUT/driver.log" 2>&1
'''
# Fixed worker-owned outputs: root shell redirection truncates, never replaces,
# these 0600 inodes. Native ownership/append proof remains a Forum gate.
ROOT_OUTPUTS = ('registry.log', 'dockerd.log', 'driver.log',
                'nested-before-cleanup.txt', 'nested-after-cleanup.txt',
                'nested-cleanup-status.txt', 'root-phase.txt', 'root-failure-phase.txt')
def phase(name):
    R['phase'] = name

def problem(kind, exc):
    # Preserve the first phase failure; diagnostic I/O never masks it.
    row = {'phase': R.get('phase'), 'type': type(exc).__name__, 'message': str(exc)}
    R.setdefault(kind, []).append(row)
    R['pass'] = False

def prepare_outputs():
    assert os.getuid() == 1000 and os.getgid() == 1000
    for name in ROOT_OUTPUTS:
        fd = os.open(OUT/name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        os.close(fd)
    config = WORK/'daemon.json'
    fd = os.open(config, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as f:
        f.write('{}\n')
    R['daemon_config_sha256'] = digest_file(config)

def safe_read(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        st = os.fstat(fd)
        if path.parent == OUT and path.name in ROOT_OUTPUTS and (st.st_uid != 1000 or st.st_gid != 1000 or stat.S_IMODE(st.st_mode) != 0o600):
            raise PermissionError('worker artifact ownership/mode mismatch: '+path.name)
        if not stat.S_ISREG(st.st_mode):
            raise ValueError('nonregular artifact: '+str(path.relative_to(OUT)))
        with os.fdopen(fd, 'rb', closefd=False) as f:
            return f.read()
    finally:
        os.close(fd)

def cleanup_observation():
    phase('outer_cleanup')
    c = {'known': False}
    R['cleanup'] = c
    # The runner and its existing launcher ancestors are controllers, not strays.
    controllers = set()
    pid = os.getpid()
    while pid > 1 and pid not in controllers:
        controllers.add(pid)
        pid = int(Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[1])
    try:
        processes = subprocess.check_output(['ps','-eo','pid,args'], text=True)
        c['stray_processes'] = [line for line in processes.splitlines()
            if (str(WORK) in line or RUN in line) and 'ps -eo' not in line
            and int(line.split(None, 1)[0]) not in controllers]
        c['mounts'] = [line for line in Path('/proc/self/mountinfo').read_text().splitlines() if str(WORK) in line]
        bridge = subprocess.run(['ip','link','show','wzmsg0'], capture_output=True)
        if bridge.returncode not in (0, 1):
            raise RuntimeError('bridge inspection failed')
        c['host_bridge_present'] = bridge.returncode == 0
    except BaseException as e:
        problem('cleanup_errors', e)
    # All cleanup attempts run even if a previous observation fails.
    for name in ['graph','exec','socket']:
        try:
            call(['sudo','-n','rm','-rf','--one-file-system',str(WORK/name)])
        except BaseException as e:
            problem('cleanup_errors', e)
    cg = Path('/sys/fs/cgroup')/RUN
    try:
        if cg.exists():
            for pth in sorted([cg,*[p for p in cg.rglob('*') if p.is_dir()]],key=lambda p:len(p.parts),reverse=True):
                call(['sudo','-n','rmdir',str(pth)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        c['cgroup_present'] = cg.exists()
        status = safe_read(OUT/'nested-cleanup-status.txt').decode().strip()
        c['nested_query_status'] = status
        c['nested_containers_empty'] = status == '0 0' and not safe_read(OUT/'nested-after-cleanup.txt').strip()
        c['private_graph_removed'] = all(not (WORK/n).exists() for n in ['graph','exec','socket'])
        c['known'] = not R.get('cleanup_errors')
    except BaseException as e:
        problem('cleanup_errors', e)
    R['absence_pass'] = bool(c['known'] and not c.get('stray_processes', True)
        and not c.get('mounts', True) and c.get('host_bridge_present') is False
        and c.get('cgroup_present') is False and c.get('nested_containers_empty') is True
        and c.get('private_graph_removed') is True)

def main():
    phase('verify_inputs')
    i=verify()
    R.update(source=i['source'], manifest_sha256=digest_file(ROOT/'manifest.json'),
        durable_retention_required=True, release_accepted=False, live_activation=False)
    phase('prepare_private_outputs')
    OUT.mkdir(); WORK.mkdir(mode=0o700)
    for p in [OUT,WORK,WORK/'home',WORK/'tmp',WORK/'state',WORK/'work']:
        p.mkdir(exist_ok=True); p.chmod(0o700)
    prepare_outputs()
    phase('verify_tools')
    b,cfg,node,deps=tools(i)
    phase('verify_images')
    images=ROOT/'images'; images.mkdir(exist_ok=True); ids={}
    for ref in i['images']:
        dest=images/(hashlib.sha256(ref.encode()).hexdigest()[:20]+'.tar')
        ids[ref]=export(ref,dest) if not dest.with_suffix('.identity.json').exists() else json.loads(dest.with_suffix('.identity.json').read_text())
        assert digest_file(dest)==ids[ref]['archive_sha256']
    (images/'identities.json').write_text(json.dumps(ids,indent=2)+'\n')
    R['input_image_identities_sha256']=digest_file(images/'identities.json')
    script=WORK/'inner.sh';script.write_text(INNER);script.chmod(0o700)
    # env -i is applied after sudo as well: no host daemon proxy/plugin env leaks.
    env=dict(ROOT=str(ROOT),WORK=str(WORK),OUT=str(OUT),RUN=RUN,BIN=str(b),CONFIG=str(cfg),NODE=str(node),DEPS=str(deps),PATH=str(b)+':/usr/bin:/bin',HOME=str(WORK/'home'))
    p=None; rc=None
    phase('namespace_launch')
    try:
        with open(OUT/'namespace.log','x') as log:
            p=subprocess.Popen(['sudo','-n','env','-i',*[k+'='+v for k,v in env.items()],
                'timeout','-k','30','4500','unshare','--kill-child','--net','--mount','--pid','--fork','--mount-proc','/bin/sh',str(script)],
                env={'PATH':'/usr/bin:/bin'},start_new_session=True,stdout=log,stderr=subprocess.STDOUT)
        phase('namespace_wait')
        rc=p.wait(timeout=4560)
        R['namespace_exit']=rc
        if rc != 0:
            raise RuntimeError('private namespace exited '+str(rc))
    except BaseException as e:
        problem('primary_errors', e)
    finally:
        if p is not None and p.poll() is None:
            try:
                os.killpg(p.pid,signal.SIGTERM)
                try:p.wait(timeout=35)
                except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
            except BaseException as e:problem('cleanup_errors',e)
        try:cleanup_observation()
        except BaseException as e:problem('cleanup_errors',e);R['absence_pass']=False
    phase('driver_receipt')
    driver=json.loads(safe_read(OUT/'delivery.json')) if (OUT/'delivery.json').exists() else {}
    for name in ['driver_pass','packaging_pass','canonical_pass','lifecycle_pass']:
        R[name]=driver.get('pass' if name=='driver_pass' else name) is True
    R['pass']=bool(rc==0 and R['driver_pass'] and R.get('absence_pass') is True
        and not any(R.get(k) for k in ['primary_errors','cleanup_errors','artifact_errors']))
    return 0 if R['pass'] else 1

def finalize():
    phase('finalize')
    OUT.mkdir(exist_ok=True)
    try:
        R['root_phase']=safe_read(OUT/'root-phase.txt').decode().strip()
        R['root_failure_phase']=safe_read(OUT/'root-failure-phase.txt').decode().strip()
    except BaseException as e:problem('artifact_errors',e)
    R['result_files']={}
    # Do not follow directory symlinks, nor open a symlink/FIFO as a log.
    for base, dirs, files in os.walk(OUT, followlinks=False, onerror=lambda e:problem('artifact_errors',e)):
        for name in list(dirs):
            p=Path(base)/name
            if p.is_symlink():
                dirs.remove(name);problem('artifact_errors',ValueError('symlink directory: '+str(p.relative_to(OUT))))
        for name in files:
            if name=='receipt.json':continue
            p=Path(base)/name
            try:R['result_files'][str(p.relative_to(OUT))]=hashlib.sha256(safe_read(p)).hexdigest()
            except BaseException as e:problem('artifact_errors',e)
    if any(R.get(k) for k in ['primary_errors','cleanup_errors','artifact_errors']) or R.get('absence_pass') is not True:
        R['pass']=False
    tmp=OUT/'receipt.json.part'
    fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as f:
        f.write(json.dumps(R,indent=2,sort_keys=True)+'\n');f.flush();os.fsync(f.fileno())
    os.replace(tmp,OUT/'receipt.json')
    print(json.dumps(R),flush=True)
    return 0 if R['pass'] else 1

def entry():
    # Never finalize into an existing failed packet or reuse its runtime root.
    assert not WORK.exists() and not OUT.exists(),'immutable single-run root: never overwrite earlier receipt'
    try:main()
    except BaseException as e:problem('primary_errors',e)
    return finalize()

if __name__=='__main__':
    sys.exit(entry())
