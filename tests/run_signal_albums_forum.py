"""Single admitted forum release job: same-test live A/B gate, then real pinned build.

Synthetic fixtures only. Inherited obsolete assertions remain failed and visible;
scoped_pass is NOT an all-suite-green claim or permission to activate anything.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from signal_release_gate import load_events, compare, strict_pass

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT.parent
OUT = STAGE / 'evidence'
BASE = STAGE / 'baseline'
ENV = dict(os.environ, PYTHONPATH=str(ROOT)+':'+str(ROOT/'tests'),
           TMPDIR='/srv/work/sa-'+STAGE.name.rsplit('-',1)[-1][:10], PYTHONDONTWRITEBYTECODE='1',
           NODE_PATH='/srv/work/morning-diff-deps-r4/node_modules',
           SIGNAL_SHELL_WEB=str(STAGE/'shell-web'), OUT=str(OUT/'browser'),
           SIGNAL_CONVERTER_FIXTURES='', SIGNAL_INGRESS_PROOF='')
records = []
container = None
receipt = {'result':'not_run','all_suite_green':False,'build_started':False,'build_verified':False,
           'phase':'integrity','deployed':False,'owner_data_read':False,'runs':records}

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def save(name, value):
    path=OUT/(name+'.json'); temp=path.with_suffix('.json.tmp')
    temp.write_text(json.dumps(value,indent=2)+'\n');temp.replace(path)

def checkpoint(phase, **values):
    receipt.update(phase=phase,**values);save('qa-receipt',receipt)
    print(json.dumps({'phase':phase,**values}),flush=True)

def marked_children():
    marker=('TMPDIR='+ENV['TMPDIR']).encode()
    found=[]
    for proc in Path('/proc').glob('[0-9]*'):
        pid=int(proc.name)
        if pid<=1 or pid==os.getpid():continue
        try:
            if proc.stat().st_uid==os.geteuid() and marker in (proc/'environ').read_bytes().split(b'\0'):
                found.append(pid)
        except (FileNotFoundError,ProcessLookupError,PermissionError):pass
    return found

def cleanup_children():
    import signal
    for sig in [signal.SIGTERM,signal.SIGKILL]:
        for pid in marked_children():
            try:os.kill(pid,sig)
            except ProcessLookupError:pass
        if marked_children():time.sleep(0.2)
    assert not marked_children(),'owned marked processes survived cleanup'

def run(name, argv, extra=None, timeout=600, required=True, cwd=ROOT):
    log=OUT/(name+'.log');started=time.monotonic()
    item={'name':name,'argv':list(map(str,argv)),'cwd':str(cwd),'state':'running','log':str(log)}
    records.append(item);save('runs',records);save('qa-receipt',receipt)
    try:
        with log.open('w') as f:
            p=subprocess.run(argv,cwd=cwd,env=dict(ENV,PYTHONPATH=str(cwd)+':'+str(cwd/'tests'),**(extra or {})),
                             stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
        code=p.returncode
    except subprocess.TimeoutExpired:
        code=124
        cleanup_children()
    item.update(state='complete',returncode=code,seconds=round(time.monotonic()-started,2),log_sha256=digest(log))
    save('runs',records);save('qa-receipt',receipt);print(json.dumps(item),flush=True)
    if required and code:raise RuntimeError('Failed '+name+'; inspect '+str(log))
    return code

def node(name, tests, cwd=ROOT, expected_skips=(), differential=False, extra=None):
    events=OUT/(name+'.jsonl');tap=OUT/(name+'.tap')
    code=run(name,['node','--test','--test-reporter=tap','--test-reporter='+str(ROOT/'tests/helpers/signal_test_reporter.cjs'),
                  '--test-reporter-destination='+str(tap),'--test-reporter-destination='+str(events),*tests],
             cwd=cwd,extra=extra,required=False)
    cases=load_events(events,cwd,tap,code)
    save(name+'-cases',cases)
    if not differential:
        strict_pass(cases,expected_skips);assert code==0,name+' failed'
    return cases

def python(name, modules, extra=None):
    run(name,[sys.executable,str(ROOT/'tests/helpers/signal_unittest.py'),str(OUT/(name+'-cases.json')),*modules],extra)
    result=json.loads((OUT/(name+'-cases.json')).read_text())
    assert result['result']=='scoped_pass' and result['skips']==0 and result['tests_run']>0
    return result

try:
    assert str(ROOT).startswith('/srv/work/'), 'Linux work belongs on admitted forum /srv/work'
    assert os.environ.get('WIZARD_HEAVY_LOCK_FD'), 'must run through durable heavy admission'
    OUT.mkdir(exist_ok=False)
    Path(ENV['TMPDIR']).mkdir(exist_ok=False)
    manifest=json.loads((STAGE/'stage.json').read_text())
    receipt.update(source_revision=manifest['source_revision'],baseline_live_revision=manifest['baseline_live_revision'],
                   product_revision=manifest['product_revision'],shell_revision=manifest['shell_revision'],
                   historical_attempts=manifest['historical_attempts'],runner_sha256=digest(__file__))
    assert manifest['baseline_live_revision']=='4566306576d3a6805da1ba531da3a89214dfd7af'
    for directory,field in [(ROOT,'source_files'),(BASE,'baseline_files'),(STAGE/'shell-web','shell_files')]:
        for filename,expected in manifest[field].items():
            assert digest(directory/filename)==expected,'immutable source mismatch: '+str(directory/filename)
    for filename,expected in manifest['fixture_files'].items():
        assert digest(ROOT/filename)==digest(BASE/filename)==expected,'A/B fixture mismatch: '+filename
    for entry in manifest['preserved_evidence']:
        assert digest(entry['path'])==entry['sha256'],'historical evidence drift: '+entry['path']
    receipt['product_bytes_unchanged']=manifest['product_bytes_unchanged']
    assert receipt['product_bytes_unchanged'] is True
    def permission_block(root):
        source=(root/'static/unified.js').read_text()
        return source[source.index('  // Agents: what each'):source.index('  // Drafts an agent saved')]
    block=permission_block(ROOT)
    assert block==permission_block(BASE),'permission UI source differs from live baseline'
    source_witnesses=["choice.setAttribute('aria-label', 'What ' + name + ' may do')",
        "const shown = levels.filter(l => l.id !== 'draft_and_send' || agent.level === 'draft_and_send')",
        "for (const agent of st.wizard_agents || [])", "if (location.hash !== '#advanced' || !s.ready) return;",
        'Settings has no list of them.']
    assert all(text in block for text in source_witnesses),'obsolete-control provenance missing'
    assert 'Review agent drafts' not in block and 'Add agent' not in block
    receipt['obsolete_controls_source_proof']={'identical_live_candidate_permission_block_sha256':hashlib.sha256(block.encode()).hexdigest(),
        'witnesses':source_witnesses,'baseline_source_sha256':digest(BASE/'static/unified.js'),
        'candidate_source_sha256':digest(ROOT/'static/unified.js')}
    free=shutil.disk_usage(STAGE).free
    checkpoint('integrity',result='running',free_bytes=free,required_free_bytes=30*1024**3)
    assert free>=30*1024**3,'full libsignal build needs 30 GiB free; no global pruning'
    python('gate-regressions',['test_signal_release_gate','test_signal_native_recorded'])
    # Execute full comprehensive browser contract on BOTH shipped IIFEs first.
    node('baseline-browser-vm-contract',['tests/unified_browser_context.test.cjs'],cwd=BASE)
    node('candidate-browser-vm-contract',['tests/unified_browser_context.test.cjs'])
    baseline=node('baseline-original-tests',manifest['original_node_tests'],cwd=BASE,differential=True)
    candidate=node('candidate-original-tests',manifest['original_node_tests'],differential=True)
    comparison=compare(baseline,candidate)
    save('original-test-ab',comparison)
    checkpoint('original-test-ab',original_test_comparison=comparison,
               inherited_baseline_failures=comparison['inherited_baseline_failures'],
               baseline_only_incompatibilities=comparison['baseline_only_incompatibilities'],
               all_suite_green=comparison['all_suite_green'])
    # No changed assertions/extra skips. Optional converter projection is the ONE
    # pre-existing skip here; it executes without skipping after the actual build.
    node('current-permissions',['tests/current_permissions.test.cjs'])
    node('signal-projection-prebuild',['tests/signal_albums.test.cjs'],
         expected_skips=['actual old vs patched converter outputs through persisted public ingress rows'])
    python('schema-and-existing-photo-albums',['test_photo_albums','test_signal_albums.SignalAlbumSchemaTests'])
    python('current-security',['test_agent_keys','test_wizard_agents','test_permission_runtime',
                               'test_passkey','test_owner_ingress','test_trusted_owner'])
    run('current-security-pytest',[sys.executable,str(ROOT/'tests/helpers/signal_pytest.py'),
        str(OUT/'current-security-pytest-cases.json'),'tests/test_remote_authority.py'],
        {'PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1'})
    pytest_result=json.loads((OUT/'current-security-pytest-cases.json').read_text())
    assert pytest_result['result']=='scoped_pass' and pytest_result['tests_run']>0 and pytest_result['skips']==0
    receipt['security_counts']={'unittest':json.loads((OUT/'current-security-cases.json').read_text())['tests_run'],
                                'pytest':pytest_result['tests_run']}
    unit={'result':'scoped_pass','suite_result':comparison['suite_result'],'all_suite_green':comparison['all_suite_green'],
          'source_revision':manifest['source_revision'],'comparison':comparison,'build_started':False,
          'optional_converter_skip':'pre-existing only; must execute with zero skips after real build','runs':list(records)}
    save('unit-receipt',unit)
    checkpoint('units-complete',unit_result='scoped_pass')
    run('playwright-pin',['node','-e',"if(require('playwright/package.json').version!=='1.64.1')process.exit(1)"])
    tag='wizard-signal-bridge:0.2610.0-native-albums1-'+manifest['source_revision'][:12]
    checkpoint('build',build_started=True,image_tag=tag)
    run('full-pinned-signal-build',['docker','build','--platform=linux/amd64','--progress=plain',
        '--label','org.opencontainers.image.revision='+manifest['source_revision'],
        '--iidfile',str(OUT/'signal-image-id.txt'),'-f','plumbing/signal-bridge/Dockerfile','-t',tag,'.'],timeout=18000)
    image_id=(OUT/'signal-image-id.txt').read_text().strip()
    run('signal-image-metadata',['docker','image','inspect',image_id])
    metadata=json.loads((OUT/'signal-image-metadata.log').read_text())[0]
    assert metadata['Id']==image_id and metadata['Architecture']=='amd64' and metadata['Os']=='linux'
    assert metadata['Config']['Labels']['org.opencontainers.image.revision']==manifest['source_revision']
    assert metadata['Config']['Labels']['org.wizard.signal.upstream']=='d129f0ecc6bd29cfb5e54b18e025bd0c8a20a4bf'
    container=subprocess.check_output(['docker','create','--network=none','--entrypoint=/bin/true',image_id],text=True).strip()
    proof=OUT/'converter';proof.mkdir()
    run('converter-fixture-readback',['docker','cp',container+':/usr/share/wizard-signal-albums/.',str(proof)])
    for variant in ['baseline','candidate']:
        log=(proof/(variant+'-go.log')).read_text()
        assert re.search(r'--- PASS: TestWizardConverterFixture\b',log),'actual converter test not executed: '+variant
        assert not re.search(r'--- SKIP:|--- FAIL:',log),'actual converter integration must not skip or fail'
    run('binary-readback',['docker','cp',container+':/usr/bin/mautrix-signal',str(OUT/'mautrix-signal')])
    binary_hash=digest(OUT/'mautrix-signal')
    assert binary_hash==(proof/'binary.sha256').read_text().split()[0],'binary hash differs from build proof'
    run('final-runtime-version',['docker','run','--rm','--network=none','--entrypoint=/usr/bin/mautrix-signal',image_id,'--version'])
    run('final-runtime-dependencies',['docker','run','--rm','--network=none','--entrypoint=/usr/bin/ldd',image_id,'/usr/bin/mautrix-signal'])
    run('retain-image',['docker','save','-o',str(OUT/'signal-image.tar'),image_id],timeout=600)
    provenance={'result':'scoped_pass','image_id':image_id,'image_tag':tag,'architecture':'amd64','binary_sha256':binary_hash,
                'source_revision':manifest['source_revision'],'product_revision':manifest['product_revision'],
                'archive':str(OUT/'signal-image.tar'),'archive_sha256':digest(OUT/'signal-image.tar'),
                'converter_files':{p.name:digest(p) for p in proof.iterdir() if p.is_file()},'build_executed':True}
    save('build-receipt',provenance)
    checkpoint('build-verified',build_verified=True,provenance=provenance)
    integration={'SIGNAL_CONVERTER_FIXTURES':str(proof),'SIGNAL_INGRESS_PROOF':str(OUT/'ingress.json')}
    python('real-converter-ingress',['test_signal_albums.SignalConverterIngressTests'],integration)
    assert (OUT/'ingress.json').is_file(),'actual converter ingress proof not produced'
    node('real-ingress-projection',['tests/signal_albums.test.cjs'],extra=integration)
    checkpoint('converter-integration',converter_integration='scoped_pass',converter_integration_skips=0)
    run('two-skin-browser',['node','tests/signal_album_browser.cjs'],integration,timeout=300)
    run('compose-validation',['docker','compose','-f','runtipi/docker-compose.yml','config','--quiet'],
        {'APP_DATA_DIR':str(OUT/'never-started-data'),'APP_PORT':'0','APP_ID':'synthetic-messenger'})
    checkpoint('complete',result='scoped_pass',suite_result=comparison['suite_result'],
        limits=['Inherited original UI failures are not green or waived feature tests',
                'Synthetic converter pointers, not authenticated Signal ingress or real provider sends',
                'Appearance hosted proxy, not installed shell/device proof; screenshots require visual inspection',
                'No activation; preserve parent current Slack/Instagram service overrides during later composition',
                'Forum archive is scratch: parent must retain valuable outputs on approved durable storage'])
except Exception as error:
    receipt.update(result='fail',error=str(error))
    if not receipt['build_started']:
        receipt['dependent_phases']={name:'not_run_dependency_failed' for name in ['build','binary_verification','converter_integration','browser']}
    else:
        receipt['dependent_phases']={'unfinished_phases':'not_run_dependency_failed; consult checkpointed runs, no old-image fallback'}
finally:
    if container:
        try:
            run('cleanup-owned-container',['docker','rm',container])
            check=subprocess.run(['docker','container','inspect',container],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            assert check.returncode!=0,'owned container survived cleanup'
            receipt['owned_container_removed']=True
        except Exception as error:receipt.update(result='fail',cleanup_error=str(error))
    try:
        cleanup_children()
        receipt['owned_marked_processes_remaining']=[]
    except Exception as error:receipt.update(result='fail',cleanup_error=str(error))
    if OUT.is_dir():save('qa-receipt',receipt)
    print(json.dumps(receipt),flush=True)
sys.exit(0 if receipt['result']=='scoped_pass' else 1)
