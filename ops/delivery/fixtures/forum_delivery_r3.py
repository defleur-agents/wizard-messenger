#!/usr/bin/env python3
"""Parent-admitted finite Forum job; private namespaces/daemon only. No live target writes."""
from pathlib import Path
import hashlib, json, os, shutil, signal, subprocess, sys, tarfile, time, urllib.request
sys.path.insert(0,str(Path(__file__).parent))
from registry_archive import export,digest_file
ROOT=Path(__file__).resolve().parents[1]
RUN='msg'+hashlib.sha256((ROOT/'manifest.json').read_bytes()).hexdigest()[:12]
OUT=ROOT/'results'; WORK=ROOT/'run'; R={'pass':False,'live_mutation':False,'source_suite_repeated':False,'run':RUN}
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
# DNS/registry routing exists only in this mount+network namespace.
cp /etc/hosts "$WORK/hosts"
printf '\n127.0.0.1 ghcr.io dock.mau.dev registry-1.docker.io docker.io\n' >>"$WORK/hosts"
mount --bind "$WORK/hosts" /etc/hosts
if [ -S /var/run/docker.sock ]; then touch "$WORK/host-socket-blocked"; mount --bind "$WORK/host-socket-blocked" /var/run/docker.sock; fi
python3 "$ROOT/capsule/registry_fixture.py" "$ROOT" >"$OUT/registry.log" 2>&1 &
RPID=$!
mkdir -p "$WORK/graph" "$WORK/exec" "$WORK/socket"
# Use the existing admitted sudo capability; never chmod/chown the worker host socket or alter privilege policy.
"$BIN/dockerd" --host "unix://$WORK/socket/docker.sock" --data-root "$WORK/graph" --exec-root "$WORK/exec" --pidfile "$WORK/daemon.pid" \
 --bridge wzmsg0 --bip 172.30.0.1/24 --default-address-pool base=172.31.0.0/16,size=24 --iptables=true --ip6tables=false \
 --userland-proxy-path "$BIN/docker-proxy" --exec-opt native.cgroupdriver=cgroupfs --cgroup-parent "$RUN" \
 --insecure-registry ghcr.io --insecure-registry dock.mau.dev --insecure-registry registry-1.docker.io --insecure-registry docker.io --registry-mirror http://127.0.0.1 \
 --feature containerd-snapshotter=false --storage-driver overlay2 --containerd-namespace "$RUN" --containerd-plugins-namespace "${RUN}p" --label "wizard.qa.run=$RUN" >"$OUT/dockerd.log" 2>&1 &
DPID=$!
cleanup() {
 set +e
 D="$BIN/docker -H unix://$WORK/socket/docker.sock"
 $D ps -aq >"$OUT/nested-before-cleanup.txt"
 for c in $($D ps -aq); do $D rm -f "$c" >/dev/null 2>&1; done
 $D ps -aq >"$OUT/nested-after-cleanup.txt"
 kill -TERM "$DPID" "$RPID" 2>/dev/null
 for i in $(seq 1 30); do kill -0 "$DPID" 2>/dev/null || break; sleep 1; done
 kill -KILL "$DPID" "$RPID" 2>/dev/null
}
trap cleanup EXIT INT TERM
ready=0
for i in $(seq 1 90); do if "$BIN/docker" -H "unix://$WORK/socket/docker.sock" info >/dev/null 2>&1; then ready=1; break; fi; sleep 1; done
[ "$ready" = 1 ]
chown 1000:1000 "$WORK/socket/docker.sock"; chmod 600 "$WORK/socket/docker.sock"
setpriv --reuid=1000 --regid=1000 --clear-groups env -i PATH="$BIN:/usr/bin:/bin" HOME="$WORK/home" TMPDIR="$WORK/tmp" \
 ROOT="$ROOT" WORK="$WORK" OUT="$OUT" RUN="$RUN" DOCKER_HOST="unix://$WORK/socket/docker.sock" DOCKER_CONFIG="$CONFIG" DOCKER_BUILDKIT=0 \
 NODE="$NODE" NODE_PATH="$DEPS/node/node_modules" PLAYWRIGHT_MODULE="$DEPS/node/node_modules/playwright" PLAYWRIGHT_BROWSERS_PATH="$DEPS/browsers" \
 python3 -B "$ROOT/capsule/delivery_driver.py" >"$OUT/driver.log" 2>&1
'''
def main():
    i=verify(); assert not WORK.exists() and not OUT.exists(),'immutable single-run root: never overwrite earlier receipt'
    OUT.mkdir();WORK.mkdir();
    for p in [OUT,WORK,WORK/'home',WORK/'tmp',WORK/'state',WORK/'work']:
        p.mkdir(exist_ok=True);p.chmod(0o777)
    b,cfg,node,deps=tools(i)
    images=ROOT/'images';images.mkdir(exist_ok=True);ids={}
    for ref in i['images']:
        dest=images/(hashlib.sha256(ref.encode()).hexdigest()[:20]+'.tar')
        ids[ref]=export(ref,dest) if not dest.with_suffix('.identity.json').exists() else json.loads(dest.with_suffix('.identity.json').read_text())
        assert digest_file(dest)==ids[ref]['archive_sha256']
    (images/'identities.json').write_text(json.dumps(ids,indent=2)+'\n')
    R['input_image_identities_sha256']=digest_file(images/'identities.json')
    script=WORK/'inner.sh';script.write_text(INNER);script.chmod(0o755)
    env=dict(os.environ,ROOT=str(ROOT),WORK=str(WORK),OUT=str(OUT),RUN=RUN,BIN=str(b),CONFIG=str(cfg),NODE=str(node),DEPS=str(deps))
    keep=','.join(['ROOT','WORK','OUT','RUN','BIN','CONFIG','NODE','DEPS'])
    p=subprocess.Popen(['sudo','-n','--preserve-env='+keep,'timeout','-k','30','4500','unshare','--kill-child','--net','--mount','--pid','--fork','--mount-proc','/bin/sh',str(script)],env=env,start_new_session=True,stdout=open(OUT/'namespace.log','w'),stderr=subprocess.STDOUT)
    rc=None
    try: rc=p.wait(timeout=4560)
    finally:
        if p.poll() is None:
            os.killpg(p.pid,signal.SIGTERM)
            try:p.wait(timeout=35)
            except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
        time.sleep(1)
        processes=subprocess.check_output(['ps','-eo','pid,args'],text=True)
        stray=[s for s in processes.splitlines() if (str(WORK) in s or RUN in s) and 'ps -eo' not in s]
        mounts=[s for s in Path('/proc/self/mountinfo').read_text().splitlines() if str(WORK) in s]
        bridge=subprocess.run(['ip','link','show','wzmsg0'],capture_output=True).returncode==0
        # Delete only this fresh capsule's private disposable graph, never Docker host data.
        for name in ['graph','exec','socket']:
            call(['sudo','-n','rm','-rf','--one-file-system',str(WORK/name)])
        cg=Path('/sys/fs/cgroup')/RUN
        if cg.exists():
            for pth in sorted([cg,*[p for p in cg.rglob('*') if p.is_dir()]],key=lambda p:len(p.parts),reverse=True):
                subprocess.run(['sudo','-n','rmdir',str(pth)],capture_output=True)
        empty=(OUT/'nested-after-cleanup.txt').exists() and not (OUT/'nested-after-cleanup.txt').read_text().strip()
        R['cleanup']={'stray_processes':stray,'mounts':mounts,'host_bridge_present':bridge,'cgroup_present':cg.exists(),'nested_containers_empty':empty,'private_graph_removed':all(not (WORK/n).exists() for n in ['graph','exec','socket'])}
        R['absence_pass']=bool(not stray and not mounts and not bridge and not cg.exists() and empty and R['cleanup']['private_graph_removed'])
    driver=json.loads((OUT/'delivery.json').read_text()) if (OUT/'delivery.json').exists() else {}
    R.update({'namespace_exit':rc,'source':i['source'],'driver_pass':driver.get('pass') is True,'packaging_pass':driver.get('packaging_pass') is True,'canonical_pass':driver.get('canonical_pass') is True,'lifecycle_pass':driver.get('lifecycle_pass') is True,'manifest_sha256':digest_file(ROOT/'manifest.json'),'durable_retention_required':True,'release_accepted':False,'live_activation':False})
    R['pass']=bool(rc==0 and R['driver_pass'] and R['absence_pass'])
    return 0 if R['pass'] else 1
if __name__=='__main__':
    rc=1
    try: rc=main()
    except BaseException as e:R['error']=type(e).__name__+': '+str(e)
    finally:
        OUT.mkdir(exist_ok=True)
        R['result_files']={str(p.relative_to(OUT)):digest_file(p) for p in OUT.rglob('*') if p.is_file() and p.name!='receipt.json'}
        (OUT/'receipt.json').write_text(json.dumps(R,indent=2,sort_keys=True)+'\n');print(json.dumps(R),flush=True)
    sys.exit(rc)
