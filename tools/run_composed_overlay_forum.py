"""Parent-admitted packaging-only continuation of passed exact-source composed QA.
No behavior/browser reruns, owner content/providers/live writes or native build.
"""
from pathlib import Path
import copy
import hashlib
import json
import os
import re
import shutil

import subprocess
import sys

from docker_overlay_identity import archive_identity, check_loaded, exact, inspect, local_build_argv, assert_local_builder

ROOT=Path(__file__).resolve().parents[1]
S=ROOT.parent
OUT=S/'evidence'
LIVE='4566306576d3a6805da1ba531da3a89214dfd7af'
PATHS=['unified.py','static/unified.js','static/unified.css','static/connectors.js','plumbing/connectors-provenance.json']
BASE_ARCHIVE=Path('/srv/work/share-people-messenger-4566306/evidence/messenger-image.tar')
BASE_SHA='1a2e3e048f1ed25a2380f068feff2717238c4fdeed0b1488a58e404c155f9ee5'
BASE_MANIFEST='sha256:75dde49255cdb88b789103170b69c68517a7acc6a8523fec3ee0f2174235b84e'
BASE_CONFIG='sha256:6c68782818b973d40f4949189d34564d46218a3c78e57b986a826814d579b362'
SIGNAL_ARCHIVE=Path('/srv/work/messenger-signal-runtime-a23fd8e26a72-import1/evidence/signal-image.tar')
SIGNAL_SHA='556ccc992151093869d7d16493ee81a2478415278de9bbbe162be2676cde3312'
SIGNAL_IMAGE='sha256:14f0f9454b11cb334dc165abe55c6ac30af896abd2ddb5c2e1ed137a8027f6ba'
SIGNAL_BINARY='a5993d2b530c07bcae345674294aa5b7416a785c910ec1566a28c0945f198759'
runs=[]
ENV=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def dump(name,obj):
    p=OUT/(name+'.json')
    p.write_text(json.dumps(obj,indent=2)+'\n')

def run(name,argv,extra=None,cwd=ROOT,timeout=180):
    p=OUT/(name+'.log')
    with p.open('x') as f:
        result=subprocess.run(argv,cwd=cwd,env=dict(ENV,**(extra or {})),stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
    row={'name':name,'argv':list(map(str,argv)),'returncode':result.returncode,'log':str(p),'log_sha256':sha(p)}
    runs.append(row);dump('progress',runs);print(json.dumps(row),flush=True)
    assert result.returncode==0,name+' failed: '+str(p)
    return p.read_text()

def verify_seal(manifest):
    for rel,meta in manifest['files'].items():
        p=S/rel
        assert p.is_file() and not p.is_symlink() and sha(p)==meta['sha256'],'input drift: '+rel
        assert p.stat().st_mode & 0o777 == meta['mode'],'input mode drift: '+rel
    # Full exact tracked source membership, not only a passing subset.
    actual={str(p.relative_to(ROOT)) for p in ROOT.rglob('*') if p.is_file() and '.git' not in p.relative_to(ROOT).parts}
    assert actual==set(manifest['source_files']),'source member drift'

def inheritance(manifest):
    ledger=json.loads((S/'inheritance.json').read_text())
    for root,entries in ledger['frozen_files'].items():
        for rel,digest in entries.items():assert sha(Path(root)/rel)==digest,'frozen evidence drift: '+rel
    for group,closure in ledger['exact_file_closures'].items():
        for rel,digest in closure.items():assert sha(ROOT/rel)==digest,group+' closure drift: '+rel
    prior=ledger['packaging_continuation']
    assert prior['revision']=='2a408e4fe38834e82d78d5f01c52e0edea1089be'
    for rel,digest in prior['unchanged_source_files'].items():
        assert sha(ROOT/rel)==digest,'inherited exact-source drift: '+rel
    for rel,delta in prior['allowed_source_delta'].items():
        assert sha(ROOT/rel)==delta['after_sha256'],'packaging delta drift: '+rel
    old=Path(prior['stage'])
    progress=json.loads((old/'evidence/progress.json').read_text())
    byname={r['name']:r for r in progress}
    for name in prior['inherited_passed_runs']:
        assert byname[name]['returncode']==0
        assert sha(byname[name]['log'])==byname[name]['log_sha256']
    assert byname['image-files-candidate']['returncode']==1
    assert prior['obsolete_permission_failures']==5
    # Exact disjoint JS composition AND prior merged execution are hash-bound above.
    work=S/'composition-check';work.mkdir()
    shutil.copyfile(S/'attachment-unified.js',work/'unified.js')
    subprocess.run(['git','apply',str(S/'signal-unified.patch')],cwd=work,check=True,env=ENV)
    assert (work/'unified.js').read_bytes()==(ROOT/'static/unified.js').read_bytes(),'unreviewed JS composition'
    dump('inherited-source-bound-evidence',ledger)
    return ledger

def main():
    global ENV
    assert str(S).startswith('/srv/work/messenger-composed-')
    assert os.environ.get('WIZARD_WORKER_LANE')=='light','durable light admission required'
    assert len(sys.argv)==2 and sha(S/'stage-manifest.json')==sys.argv[1]
    manifest=json.loads((S/'stage-manifest.json').read_text());verify_seal(manifest)
    assert not OUT.exists(),'fresh evidence only';OUT.mkdir()
    ENV=dict(ENV,TMPDIR=str(S/'tmp'))
    Path(ENV['TMPDIR']).mkdir()
    rev=manifest['revision']
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==rev
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip()
    ledger=inheritance(manifest)
    # All unchanged behavior/security/account/native, parity, lifecycle and identity
    # regressions passed in r3. Inherit exact source + result/log/artifact hashes.
    # Only the actual packaging defect is exercised in this admitted continuation.
    dump('qa-checkpoint',{'scoped_qa_pass':True,'all_suites_green':False,'revision':rev,
        'packaging_pending':True,'inherited_case_ledger':ledger['case_ledger']})
    # Frozen base, all blob bytes + exact Config + ordered RootFS; no normalization of raw archive.
    assert sha(BASE_ARCHIVE)==BASE_SHA
    frozen=archive_identity(BASE_ARCHIVE)
    assert frozen['manifest_digest']==BASE_MANIFEST and frozen['config_digest']==BASE_CONFIG
    run('load-base',['docker','load','-i',str(BASE_ARCHIVE)],timeout=180)
    base=inspect('wizard-messenger:0.2.0-unified.15.14');base_kind=check_loaded(base,frozen)
    assert base['Config']['Labels']['org.opencontainers.image.revision']==LIVE
    # Named immutable local alias + docker driver sharing this daemon. Never FROM sha256:<config>.
    alias='wizard-messenger-base:composed-'+rev[:12]
    run('tag-exact-local-base',['docker','tag',base['Id'],alias])
    assert inspect(alias)['Id']==base['Id'];check_loaded(inspect(alias),frozen)
    # This pinned buildx has no inspect --format; bind its actual text schema.
    text=subprocess.check_output(['docker','buildx','inspect','default'],text=True)
    head,nodes=text.split('Nodes:',1)
    field=lambda body,key:re.findall(r'^'+key+r':\s+(\S+)\s*$',body,re.M)
    assert field(head,'Name')==['default'] and field(head,'Driver')==['docker']
    assert field(nodes,'Name')==['default'] and field(nodes,'Endpoint')==['default']
    assert field(nodes,'Status')==['running']
    builder={'Name':'default','Driver':'docker','Nodes':[{'Endpoint':'default'}],'observed_text':text}
    assert_local_builder(builder);dump('builder',builder)
    ctx=S/'build-context';(ctx/'payload').mkdir(parents=True)
    for rel in PATHS:
        p=ctx/'payload'/rel;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/rel,p)
        assert sha(p)==sha(ROOT/rel)
    # Assert the local named alias again immediately before BuildKit resolution.
    assert inspect(alias)['Id']==base['Id'];check_loaded(inspect(alias),frozen)
    tag='wizard-messenger:composed-'+rev[:12]
    argv=local_build_argv(alias,rev,tag,str(ROOT/'release/composed.Dockerfile'))
    run('build-composed-overlay',argv,cwd=ctx,timeout=180)
    candidate=inspect(tag)
    expected=copy.deepcopy(base['Config']);expected['Labels']['org.opencontainers.image.revision']=rev
    assert exact(candidate['Config'],expected),'full candidate Config drift'
    assert candidate['RootFS']['Type']=='layers' and candidate['RootFS']['Layers'][:-len(PATHS)]==base['RootFS']['Layers']
    assert len(candidate['RootFS']['Layers'])==len(base['RootFS']['Layers'])+len(PATHS),'five per-file payload layers required'
    # Real packaged regression: original defective image must reproduce EACCES;
    # base and corrected candidate must read every /app file as the actual app uid.
    probe=(ROOT/'tools/probe_packaged_app_readability.py').read_text()
    sandbox=['docker','run','--rm','--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges','--user=1000:1000','--entrypoint=python3']
    broken=ledger['packaging_continuation']['failed_image']
    assert inspect(broken)['Id']==broken
    run('packaged-readability-old-negative',sandbox+[broken,'-B','-c',probe,'--expect-permission-error'])
    trees={};metadata={}
    for role,image in [('base',base),('candidate',candidate)]:
        text=run('image-files-'+role,sandbox+[image['Id'],'-B','-c',probe])
        metadata[role]=json.loads(text);trees[role]=metadata[role]['files']
    assert metadata['candidate']['directories']==metadata['base']['directories'],'base directory mode/owner drift'
    for rel in PATHS:assert metadata['candidate']['file_modes']['/app/'+rel]==0o644,rel
    dump('packaged-readability-regression',{'scoped_pass':True,'uid':1000,'gid':1000,
        'old_defective_image':broken,'base_directory_metadata_unchanged':True,
        'directory_metadata':metadata['candidate']['directories'],'payload_modes':{p:metadata['candidate']['file_modes']['/app/'+p] for p in PATHS},
        'untouched_app_js_sha256':trees['candidate']['/app/static/app.js']})
    changed={p for p in set(trees['base'])|set(trees['candidate']) if trees['base'].get(p)!=trees['candidate'].get(p)}
    assert changed=={'/app/'+p for p in PATHS},sorted(changed)
    for rel in PATHS:
        assert trees['base']['/app/'+rel]==sha(S/'baseline'/rel)
        assert trees['candidate']['/app/'+rel]==sha(ROOT/rel)
    run('app-user-import',['docker','run','--rm','--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges','--user=1000:1000','--entrypoint=python3',candidate['Id'],'-B','-c','import unified, web; import os; assert os.getuid()==1000'])
    archive=OUT/'messenger-composed-image.tar'
    run('export-overlay',['docker','save','-o',str(archive),tag],timeout=180)
    proof=archive_identity(archive);kind=check_loaded(candidate,proof)
    # Reuse frozen native image, prove complete image Config/rootfs and binary only. No Rust/Go build.
    assert sha(SIGNAL_ARCHIVE)==SIGNAL_SHA
    sigproof=archive_identity(SIGNAL_ARCHIVE)
    run('load-frozen-signal',['docker','load','-i',str(SIGNAL_ARCHIVE)],timeout=180)
    sig=inspect(SIGNAL_IMAGE);sigkind=check_loaded(sig,sigproof)
    binary=run('frozen-signal-binary',['docker','run','--rm','--network=none','--read-only','--cap-drop=ALL','--entrypoint=sha256sum',SIGNAL_IMAGE,'/usr/bin/mautrix-signal']).split()[0]
    assert binary==SIGNAL_BINARY
    dump('signal-image-identity',dict(sigproof,loaded_id=sig['Id'],loaded_id_kind=sigkind,config=sig['Config'],rootfs=sig['RootFS'],archive_sha256=SIGNAL_SHA))
    dump('image-identity',{'archive_path':str(archive),'archive_sha256':sha(archive),'base_archive_sha256':BASE_SHA,'base_manifest_digest':BASE_MANIFEST,'base_config_digest':BASE_CONFIG,'base_loaded_id':base['Id'],'base_loaded_id_kind':base_kind,'loaded_id':candidate['Id'],'loaded_id_kind':kind,'tag':tag,'manifest_digest':proof['manifest_digest'],'config_digest':proof['config_digest'],'raw_config':proof['raw_config'],'config':candidate['Config'],'rootfs':candidate['RootFS'],'changed_app_files':sorted(changed)})
    binding={'revision':rev,'dockerfile_sha256':sha(ROOT/'release/composed.Dockerfile'),
        'lifecycle_sha256':sha(ROOT/'tools/composed_lifecycle.py'),'identity_helper_sha256':sha(ROOT/'tools/docker_overlay_identity.py'),
        'readability_probe_sha256':sha(ROOT/'tools/probe_packaged_app_readability.py'),
        'source_recipe_files':{p:sha(ROOT/p) for p in ['runtipi/config.json','runtipi/docker-compose.yml','wizard.md']},
        'inheritance_sha256':sha(S/'inheritance.json'),'payload_layers':len(PATHS)}
    assert binding==manifest['packaging_binding'],'source/recipe/lifecycle binding drift'
    verify_seal(manifest)
    dump('qa-receipt',{'scoped_pass':True,'scoped_qa_pass':True,'all_suites_green':False,'packaging_only':True,'packaging_binding':binding,'readability_regression_sha256':sha(OUT/'packaged-readability-regression.json'),'behavior_browser_reruns':0,'obsolete_permission_failures':5,'synthetic_only':True,'live_provider_sends':0,'native_builds':0,'activation_performed':False,'revision':rev,'source_manifest_sha256':sys.argv[1],'runner_sha256':sha(__file__),'image_identity_sha256':sha(OUT/'image-identity.json'),'signal_identity_sha256':sha(OUT/'signal-image-identity.json'),'overlay_files':{p:sha(ROOT/p) for p in PATHS},'signal':{'image_id':SIGNAL_IMAGE,'binary_sha256':SIGNAL_BINARY,'archive_sha256':SIGNAL_SHA},'inherited_case_ledger':ledger['case_ledger'],'runs':runs,'remaining':['parent review fresh synthetic screenshots','parent target-daemon archive identity proof','parent fresh live/overrides/serving-shell guards and lifecycle authority only']})

if __name__=='__main__':
    try:main()
    except BaseException as exc:
        if OUT.exists():dump('FAILED',{'error':str(exc),'type':type(exc).__name__,'runs':runs})
        raise
