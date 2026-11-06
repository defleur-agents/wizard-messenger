#!/usr/bin/env python3
"""Inside the admitted private namespace only: packaging, real WAM/Runtipi, canonical shell.
Fixtures replace source/release/index TRANSPORT only. No lifecycle/Compose/SDK stubs.
"""
from pathlib import Path
import contextlib,hashlib,io,json,os,re,secrets,shutil,subprocess,sys,tarfile,threading,time,urllib.request,urllib.error
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from unittest.mock import patch
ROOT=Path(os.environ['ROOT']);WORK=Path(os.environ['WORK']);OUT=Path(os.environ['OUT']);RUN=os.environ['RUN'];CAP=ROOT/'capsule'
I=json.loads((CAP/'inputs.json').read_text());CUST=json.loads((CAP/'source-custody.json').read_text())
from resource_guard import resource_sample
PLAN=json.loads((CAP/'resource-plan.json').read_text())
RESOURCE_INITIAL=json.loads((WORK/'resource-initial.json').read_text());RESOURCE_SAMPLES=[]
R={'pass':False,'packaging_pass':False,'canonical_pass':False,'lifecycle_pass':False,'source':I['source'],'lifecycle_baseline':I['baseline_lifecycle'],'transport_adapters':['anonymous digest-verified namespace registry','exact commit git-archive source fetch','exact release asset gh fixture','one-app index'],'lifecycle_implementation':'unmodified installed WAM private.prepare + store_selection.resolve/execute + Runtipi app-lifecycle controller'}
PROCS=[]
def h(p):
    d=hashlib.sha256()
    with open(p,'rb') as f:
        while b:=f.read(1048576):d.update(b)
    return d.hexdigest()
def save(n,o):
    p=OUT/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(o,indent=2,sort_keys=True)+'\n')
def run(a,timeout=600,include_stderr=False,**kw):
    RESOURCE_SAMPLES.append(resource_sample(ROOT,str(a[:3]),PLAN,RESOURCE_INITIAL))
    save('resource-samples.json',RESOURCE_SAMPLES)
    r=subprocess.run(a,timeout=timeout,capture_output=True,text=True,**kw)
    if r.returncode:raise RuntimeError('command failed '+repr(a[:5])+' rc='+str(r.returncode)+' '+r.stdout[-1200:]+' '+r.stderr[-1200:])
    return r.stdout+r.stderr if include_stderr else r.stdout

def docker(*a,**kw):return run(['docker',*map(str,a)],**kw)
def info(image):return json.loads(docker('image','inspect',image))[0]
def extract(name):
    p=WORK/'work'/name;p.mkdir()
    with tarfile.open(CAP/(name+'.tar')) as t:t.extractall(p,filter='data')
    return p

def image_files(image):
    code="import pathlib,hashlib,json;p=pathlib.Path('/app');fs=[x for x in p.rglob('*') if x.is_file() and '__pycache__' not in str(x)];fs += [pathlib.Path('/usr/local/bin/wn'),pathlib.Path('/usr/local/bin/wnd')];print(json.dumps({str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in fs},sort_keys=True))"
    return json.loads(docker('run','--rm','--label','wizard.qa.run='+RUN,'--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--user','1000:1000','--entrypoint','python3',image,'-c',code))
def closure(actual,label):
    source=CUST[label]['files'];mapping={};unknown=[]
    for p,v in actual.items():
        if not p.startswith('/app/'):continue
        n=p[5:]; choices=[n]
        if n in ['static/favicon.svg','static/icon.png','static/icon-192.png']:choices.append(n.split('/')[-1])
        if n=='entrypoint.sh':choices.append('engine/entrypoint.sh')
        if n.startswith('upstream/'):choices.append('engine/'+n[9:])
        matched=[x for x in choices if source.get(x)==v]
        if not matched:unknown.append(p)
        else:mapping[p]={'source':matched[0],'sha256':v}
    assert not unknown,('unmapped-or-mismatching-runtime-files',label,unknown)
    for n in source:
        if n.endswith('.py') and '/' not in n and n not in ['setup.py']:
            # Only copied runtime Python files, not tools/tests. Every actual image file is independently checked above.
            if '/app/'+n in actual:assert actual['/app/'+n]==source[n]
    return mapping

def archive_config(p):
    with tarfile.open(p) as t:
        manifest=json.loads(t.extractfile('manifest.json').read());assert len(manifest)==1
        cfg=t.extractfile(manifest[0]['Config']).read();d='sha256:'+hashlib.sha256(cfg).hexdigest();c=json.loads(cfg)
        assert c['architecture']=='amd64' and c['os']=='linux'
        return {'config_id':d,'rootfs_diff_ids':c['rootfs']['diff_ids'],'manifest_json':manifest,'archive_sha256':h(p),'archive_bytes':p.stat().st_size}

def packaging():
    base=I['base'];docker('pull','--platform','linux/amd64',base)
    before=info(base);assert before['Config']['Labels']['org.opencontainers.image.revision']==I['engine_source']
    assert before['Config']['Labels']['org.wizardos.messenger.mdk-patches']=='rustls-0.23.46,relay-plane-drop'
    files=image_files(base);base_map=closure(files,'engine-source')
    src=extract('candidate');context=WORK/'work'/'build';context.mkdir()
    overlay=I['runtime_overlay_files']
    assert overlay==['plumbing/connectors-provenance.json','static/connectors.js','static/unified.css','static/unified.js','unified.py']
    for n in overlay:
        p=context/n;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src/n,p)
    recipe='ARG ENGINE_IMAGE\nFROM ${ENGINE_IMAGE}\nLABEL org.wizardos.engine-base.revision="'+I['engine_source']+'" org.wizardos.engine-base.origin="'+base+'" org.wizardos.source-overlay.revision="'+I['source']+'" org.opencontainers.image.version="'+I['version']+'"\n'
    recipe+=''.join('COPY '+n+' /app/'+n+'\n' for n in overlay)
    recipe+='USER 0:0\nRUN chmod 0644 '+' '.join('/app/'+n for n in overlay)+'\nUSER 1000:1000\n'
    (context/'Dockerfile').write_text(recipe)
    tag='wizard-approved-messenger:preserve-'+I['source'][:12]
    localbase='wizard-preservation-engine-base:'+RUN
    docker('tag',before['Id'],localbase);assert info(localbase)['Id']==before['Id']
    docker('build','--pull=false','--network','none','--label','wizard.qa.run='+RUN,'--build-arg','ENGINE_IMAGE='+localbase,'-t',tag,context)
    after=info(tag);actual=image_files(tag);changed=sorted(p for p in set(files)|set(actual) if files.get(p)!=actual.get(p))
    assert changed==sorted('/app/'+n for n in overlay),changed
    mapped=closure(actual,'candidate')
    assert after['Config']['User']=='1000:1000'
    assert after['Config']['Labels']['org.opencontainers.image.revision']==I['engine_source']
    assert after['Config']['Labels']['org.wizardos.source-overlay.revision']==I['source']
    expected_config=json.loads(json.dumps(before['Config']))
    expected_config['Labels'].update({'org.wizardos.engine-base.revision':I['engine_source'],'org.wizardos.engine-base.origin':base,'org.wizardos.source-overlay.revision':I['source'],'org.opencontainers.image.version':I['version'],'wizard.qa.run':RUN})
    expected_config['User']='1000:1000'
    assert after['Config']==expected_config,'full inherited engine Config drift beyond explicit source/version/QA labels'
    modecode='import json,pathlib,stat;ns='+repr(['/app','/app/static','/app/plumbing','/app/readiness','/app/push_notifications']+['/app/'+n for n in overlay])+';print(json.dumps({n:stat.S_IMODE(pathlib.Path(n).stat().st_mode) for n in ns}))'
    modes=json.loads(docker('run','--rm','--label','wizard.qa.run='+RUN,'--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--user','1000:1000','--entrypoint','python3',tag,'-c',modecode))
    assert all(v==(0o644 if n in ['/app/'+x for x in overlay] else 0o755) for n,v in modes.items()),modes
    for p in ['/usr/local/bin/wn','/usr/local/bin/wnd']:assert actual[p]==files[p]
    assert after['RootFS']['Layers'][:len(before['RootFS']['Layers'])]==before['RootFS']['Layers']
    smoke='import pathlib;assert not any(pathlib.Path("/data").iterdir());assert not any(pathlib.Path("/run/messenger").iterdir());import server,web,unified,voice_archive,inbox_feed,agent_tools,readiness.search;print("nonroot-import-smoke-PASS")'
    assert 'PASS' in docker('run','--rm','--label','wizard.qa.run='+RUN,'--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--user','1000:1000','--entrypoint','python3',tag,'-c',smoke)
    artifacts=OUT/'artifacts';artifacts.mkdir();archive=artifacts/'messenger-preservation-amd64.docker.tar';docker('save','-o',archive,tag)
    aid=archive_config(archive);assert after['Id']==aid['config_id'],'this admitted daemon explicitly uses classic image store; IDs cannot be conflated'
    (artifacts/'Dockerfile.preservation').write_text(recipe)
    asset={'asset':archive.name,'image':base.split('@')[0],'image_id':aid['config_id'],'sha256':aid['archive_sha256']}
    entry={'id':'messenger','repo':'humanitylabs-org/wizard-messenger','commit':I['source'],'tag':'approved-16.23-preservation-'+I['source'][:12],'architectures':['amd64'],'images':{'amd64':asset},'gateway':{'path':'/messenger/','strip_prefix':True}}
    save('artifacts/private-catalog.json',{'schema':1,'scope':'private-test','apps':[entry]})
    R['packaging']={'base_origin':base,'engine_source':I['engine_source'],'source_overlay':I['source'],'base_daemon_id':before['Id'],'candidate_daemon_id':after['Id'],'candidate_tag':tag,'source_version':I['version'],'image_version':after['Config']['Labels']['org.opencontainers.image.version'],'recipe_sha256':h(artifacts/'Dockerfile.preservation'),'changed_runtime_files':changed,'engine_binary_hashes':{p:actual[p] for p in ['/usr/local/bin/wn','/usr/local/bin/wnd']},'base_closure':base_map,'candidate_closure':mapped,'source_browser_reused_receipt_sha256':I['accepted_receipt_sha256'],'empty_data':'No data mounts during build/import/closure smoke; first synthetic data is created by nested Runtipi only','archive':aid,'base_rootfs':before['RootFS'],'candidate_rootfs':after['RootFS'],'image_store':'classic explicit; config ID == daemon image ID, not registry index or platform manifest'}
    # Extract actual delivered static from the image, never serve a source checkout in canonical QA.
    cid=docker('create','--label','wizard.qa.run='+RUN,tag).strip()
    static=WORK/'work'/'packaged-static';static.mkdir()
    try:docker('cp',cid+':/app/static/.',static)
    finally:docker('rm',cid)
    for p in static.rglob('*'):
        if p.is_file():assert actual['/app/static/'+str(p.relative_to(static))]==h(p)
    R['packaging'].update(file_and_directory_modes=modes,full_inherited_config_preserved=True,reconciliation_source_browser_pass=False)
    R['packaging_pass']=True;save('packaging.json',R['packaging'])
    return entry,src,static,archive

class IndexHandler(BaseHTTPRequestHandler):
    def log_message(self,*a):pass
    def do_GET(self):
        path=self.path.split('?')[0]
        if path=='/v1/search':body={'apps':[],'next_offset':None}
        else:body={'error':'fixture index has no unselected apps'}
        self.send_response(200 if path=='/v1/search' else 404);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(json.dumps(body).encode())

def wait(url,timeout=180):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        try:
            with urllib.request.urlopen(url,timeout=3) as r:
                if r.status==200:return
        except (OSError,urllib.error.HTTPError):pass
        time.sleep(1)
    raise AssertionError('fixture did not become healthy '+url)

def lifecycle(entry,src,archive):
    import yaml
    wam=extract('wam');sys.path.insert(0,str(wam))
    from wam import private,test_catalog,store_selection,cli
    from wam.runtipi import Runtipi
    state=WORK/'state'
    for d in ['postgres','cache','repos','apps','logs','app-data','backups','user-config','state','traefik','media']:(state/d).mkdir(exist_ok=True)
    index=ThreadingHTTPServer(('0.0.0.0',18881),IndexHandler);thread=threading.Thread(target=index.serve_forever,daemon=True);thread.start()
    env={'TIPI_VERSION':'v4.10.2','POSTGRES_HOST':'runtipi-db','POSTGRES_DBNAME':'tipi','POSTGRES_USERNAME':'tipi','POSTGRES_PASSWORD':secrets.token_urlsafe(32),'POSTGRES_PORT':'5432','RABBITMQ_HOST':'runtipi-queue','RABBITMQ_USERNAME':'tipi','RABBITMQ_PASSWORD':secrets.token_urlsafe(32),'ARCHITECTURE':'amd64','INTERNAL_IP':'127.0.0.1','JWT_SECRET':secrets.token_urlsafe(48),'ROOT_FOLDER_HOST':str(state),'RUNTIPI_APP_DATA_PATH':str(state/'app-data'),'NGINX_PORT':'18710','NGINX_PORT_SSL':'18711','APPS_REPO_ID':'wizardapps','APPS_REPO_URL':'http://172.30.0.1:18881','WIZARD_INDEX_URL':'http://172.30.0.1:18881','DOMAIN':'localhost','LOCAL_DOMAIN':'localhost','TZ':'UTC','NODE_ENV':'production','DEMO_MODE':'false','GUEST_DASHBOARD':'false','ALLOW_ERROR_MONITORING':'false','ALLOW_AUTO_THEMES':'false','PERSIST_TRAEFIK_CONFIG':'false','ADVANCED_SETTINGS':'false','QUEUE_TIMEOUT_IN_MINUTES':'15','MAX_BACKUPS':'3','EXPERIMENTAL_INSECURE_COOKIE':'true'}
    (state/'.env').write_text(''.join(k+'='+v+'\n' for k,v in env.items()));(state/'.env').chmod(0o600)
    labels={'wizard.qa.run':RUN}
    manager='ghcr.io/humanitylabs-org/wizard-app-manager@sha256:85dda7d674915c1d4dcf4c9fe5cf49ae52da459e91ba53504799c5a0c853e370'
    compose={'services':{'db':{'image':'postgres:14@sha256:14bfab572eec6abf65892e1db7c3ba8d41b2a2855c1b143664907d6e146eb6e1','labels':labels,'environment':{'POSTGRES_DB':'tipi','POSTGRES_USER':'tipi','POSTGRES_PASSWORD':env['POSTGRES_PASSWORD']},'volumes':[str(state/'postgres')+':/var/lib/postgresql/data'],'networks':{'default':{'aliases':['runtipi-db']}},'healthcheck':{'test':['CMD-SHELL','pg_isready -U tipi -d tipi'],'interval':'2s','retries':60}},'queue':{'image':'rabbitmq:4-alpine@sha256:2cb43283d8bbd3caa6c0f0dc00e96c8de772df33df7fd8af6aee4d605aeb8ada','labels':labels,'environment':{'RABBITMQ_DEFAULT_USER':'tipi','RABBITMQ_DEFAULT_PASS':env['RABBITMQ_PASSWORD']},'networks':{'default':{'aliases':['runtipi-queue']}}},'manager':{'image':manager,'labels':labels,'environment':env,'ports':['127.0.0.1:18710:3000'],'volumes':[str(state)+':/data',str(state/'app-data')+':/app-data',str(state/'cache')+':/cache',str(WORK/'socket/docker.sock')+':/var/run/docker.sock:ro'],'depends_on':{'db':{'condition':'service_healthy'},'queue':{'condition':'service_started'}}}},'networks':{'default':{'labels':labels}}}
    comp=state/'docker-compose.yml';comp.write_text(json.dumps(compose));comp.chmod(0o600)
    def rig(*a):return docker('compose','-p','messenger-'+RUN,'-f',comp,*a,timeout=900)
    wh=WORK/'home'/'.wizard-os';wh.mkdir(exist_ok=True)
    cfg={'runtipi_root':str(state),'index':'http://172.30.0.1:18881','update_backups':{'enabled':False}}
    (wh/'app-manager.json').write_text(json.dumps(cfg))
    # Exact gh asset transport, not a private-catalog/preloader mock. Unknown calls refuse.
    bindir=WORK/'home'/'bin';bindir.mkdir();gh=bindir/'gh'
    gh.write_text('#!/usr/bin/python3\nimport sys,shutil\nfrom pathlib import Path\na=sys.argv[1:]\nassert a[:3]==["release","download",'+repr(entry['tag'])+'] and a[3:5]==["--repo",'+repr(entry['repo'])+'] and a[5:7]==["--pattern",'+repr(archive.name)+'] and a[7]=="--dir" and len(a)==9\nshutil.copyfile('+repr(str(archive))+',Path(a[8])/'+repr(archive.name)+')\n');gh.chmod(0o755)
    cat=WORK/'home/private-catalog.json'
    def catalog(e):cat.write_text(json.dumps({'schema':1,'scope':'private-test','apps':[e]}))
    baseline=extract('baseline-recipe');baseline_sha=I['baseline_recipe']
    oldconfig=json.loads((baseline/'runtipi/config.json').read_text());newconfig=json.loads((src/'runtipi/config.json').read_text())
    assert oldconfig['version']==I['baseline_version'] and newconfig['version']==I['version']
    assert oldconfig['tipi_version']<newconfig['tipi_version']==I['recipe_counter']
    # Labels are an explicit fixture-only user-config overlay; shipped recipe bytes stay sealed.
    services=yaml.safe_load((src/'runtipi/docker-compose.yml').read_text())['services']
    labeldir=state/'user-config/wizardapps/messenger';labeldir.mkdir(parents=True,exist_ok=True)
    (labeldir/'docker-compose.yml').write_text(yaml.safe_dump({'services':{name:{'labels':{'wizard.qa.run':RUN}} for name in services}},sort_keys=False))
    docker('pull','--platform','linux/amd64',I['baseline_image'])
    base_archive=OUT/'artifacts/messenger-offered-amd64.docker.tar';docker('save','-o',base_archive,I['baseline_image']);base_aid=archive_config(base_archive)
    assert base_aid['config_id']!=entry['images']['amd64']['image_id'],'same-version/relabelled image is not a different binary proof'
    oldentry={**entry,'commit':baseline_sha,'images':{'amd64':{**entry['images']['amd64'],'asset':archive.name,'image_id':base_aid['config_id'],'sha256':base_aid['archive_sha256']}}}
    # Same fixture asset filename: atomic switch of the transport source, validated afresh by preload.
    asset_current=WORK/'work/current-release.docker.tar';shutil.copyfile(archive,asset_current)
    ghtext=gh.read_text();gh.write_text(ghtext.replace(repr(str(archive)),repr(str(asset_current))))
    fetch_log=[]
    def fetch(repo,commit,dest,tok):
        assert repo==entry['repo'] and commit in [baseline_sha,I['source']]
        selected=baseline if commit==baseline_sha else src
        shutil.copytree(selected,dest);fetch_log.append({'repo':repo,'commit':commit,'archive_sha256':CUST['baseline-recipe' if commit==baseline_sha else 'candidate']['sha256']})
    oldenv=dict(os.environ)
    os.environ.update(WIZARD_OS_HOME=str(wh),RUNTIPI_ROOT=str(state),WAM_PRIVATE_CATALOG=str(cat),WAM_INDEX='http://172.30.0.1:18881',GH_TOKEN='synthetic-fixture-not-a-real-account',PATH=str(bindir)+':'+os.environ['PATH'])
    try:
        rig('up','-d');wait('http://127.0.0.1:18710/api/health',240)
        c=cli.Config();rt=c.runtipi();assert not rt.installed()
        # Exact selected private-catalog resolver. No bare `app update` passthrough.
        with patch.object(private,'fetch',fetch):
            shutil.copyfile(base_archive,asset_current);catalog(oldentry)
            selected=store_selection.resolve(c,'messenger',{'source':'owner-private','repo':entry['repo'],'commit':baseline_sha,'operation':'install'})
            result=store_selection.execute(c,'messenger',selected);assert result.get('status')=='running',result
            assert set(cli.installed_ids(rt))=={'messenger'}
            appdir=state/'apps/wizardapps/messenger'
            assert (appdir/'.wizard-commit').read_text().strip()==baseline_sha
            def container():
                cs=docker('ps','-q','--filter','label=runtipi.appurn=messenger:wizardapps','--filter','label=com.docker.compose.service=messenger').split();assert len(cs)==1
                return json.loads(docker('inspect',cs[0]))[0]
            before=container(); assert before['Image']==base_aid['config_id']
            mounts=lambda x:sorted((m['Source'],m['Destination'],m['RW']) for m in x['Mounts'])
            # Only synthetic state; leave the real engine's own data closed.
            canary=state/'app-data/wizardapps/messenger/data/lifecycle-fixture-canary';canary.write_text('synthetic preservation '+RUN);canary_hash=h(canary)
            shutil.copyfile(archive,asset_current);catalog(entry)
            selected=store_selection.resolve(c,'messenger',{'source':'owner-private','repo':entry['repo'],'commit':I['source'],'operation':'update'})
            # Controller calls and exact request fields captured; never stubbed.
            calls=[];original=rt.req
            def logged(method,path,body=None,timeout=60):
                calls.append({'method':method,'path':path,'body':body if path.endswith('/update') else None});return original(method,path,body,timeout)
            # Config creates clients repeatedly; class-level transport wrapper keeps actual HTTP/auth.
            original_req=Runtipi.req
            def logged_req(self,method,path,body=None,timeout=60):
                if path.startswith('/app-lifecycle/'):calls.append({'method':method,'path':path,'body':body if path.endswith('/update') else None})
                return original_req(self,method,path,body,timeout)
            with patch.object(Runtipi,'req',logged_req):result=store_selection.execute(c,'messenger',selected)
            assert result.get('status')=='running' and not result.get('error'),result
            assert any(q=={'method':'PATCH','path':'/app-lifecycle/messenger:wizardapps/update','body':{'performBackup':True}} for q in calls),calls
            after=container();assert before['Id']!=after['Id'] and after['Image']==entry['images']['amd64']['image_id']
            assert mounts(before)==mounts(after),'update changed explicit mounts'
            assert h(canary)==canary_hash
            # Real app code writes isolated synthetic state after update; baseline code must read it.
            fixture=state/'app-data/wizardapps/messenger/data/lifecycle-synthetic';fixture.mkdir();fixture.chmod(0o755)
            writecode="from pathlib import Path;from unified import PeopleStore;s=PeopleStore(Path('/data/lifecycle-synthetic/people.db'));i=s.identity('signal','!synthetic:test','Synthetic');s.add_message('$post-update',i,'fixture',False,'post-update-write',1700000000000);print('write-PASS')"
            assert 'write-PASS' in docker('exec',after['Id'],'python3','-c',writecode)
            readcode="from pathlib import Path;from unified import PeopleStore;s=PeopleStore(Path('/data/lifecycle-synthetic/people.db'));assert s.message('$post-update')['original']=='post-update-write';print('old-code-read-PASS')"
            assert 'old-code-read-PASS' in docker('run','--rm','--label','wizard.qa.run='+RUN,'--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--user','1000:1000','-v',str(fixture)+':/data/lifecycle-synthetic','--entrypoint','python3',I['baseline_image'],'-c',readcode)
            assert (appdir/'.wizard-commit').read_text().strip()==I['source']
            assert json.loads((appdir/'.wizard-source').read_text())['repo']==entry['repo']
            generated=appdir/'docker-compose.generated.yml';genhash=h(generated)
            actual=R['packaging']['candidate_closure']
            code="import hashlib,pathlib,json;print(json.dumps({str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in pathlib.Path('/app').rglob('*') if x.is_file() and '__pycache__' not in str(x)}))"
            delivered=json.loads(docker('exec',after['Id'],'python3','-c',code))
            assert all(delivered[p]==v['sha256'] for p,v in actual.items())
            ports=after['HostConfig']['PortBindings'];assert all(b['HostIp'] in ['127.0.0.1','::1'] for binds in ports.values() for b in binds),ports
            # Controller restart/recreate and manager-only recreate reuse all explicit mounts and state.
            rt.stop('messenger:wizardapps');assert rt.wait_status('messenger:wizardapps',{'stopped'},120)=='stopped'
            rt.start('messenger:wizardapps');assert rt.wait_status('messenger:wizardapps',{'running'},240)=='running'
            recreated=container();assert mounts(recreated)==mounts(after) and h(canary)==canary_hash
            rig('up','-d','--force-recreate','--no-deps','manager');wait('http://127.0.0.1:18710/api/health',180)
            assert rt.app('messenger:wizardapps')['app']['status']=='running' and h(canary)==canary_hash
            # Simulate Runtipi's down --rmi removal: retained archive must restore exact identity before next update.
            rt.stop('messenger:wizardapps');assert rt.wait_status('messenger:wizardapps',{'stopped'},120)=='stopped'
            ids=docker('ps','-aq','--filter','label=runtipi.appurn=messenger:wizardapps').split()
            if ids:docker('rm','-f',*ids)
            docker('image','rm','-f',entry['images']['amd64']['image_id'])
            assert subprocess.run(['docker','image','inspect',entry['images']['amd64']['image_id']],capture_output=True).returncode!=0
            assert h(archive)==entry['images']['amd64']['sha256'];test_catalog.preload(entry,'synthetic-fixture')
            assert info(entry['images']['amd64']['image_id'])['Id']==entry['images']['amd64']['image_id']
            rt.start('messenger:wizardapps');assert rt.wait_status('messenger:wizardapps',{'running'},300)=='running'
            assert mounts(container())==mounts(after) and h(canary)==canary_hash
            assert h(generated)==genhash
            # Never contact an owner account: these URLs are the disposable engine only.
            bind=next(iter(container()['HostConfig']['PortBindings'].values()))[0];origin='http://127.0.0.1:'+bind['HostPort']
            wait(origin+'/healthz',120)
            statuses={}
            for name,headers in [('unauthenticated',{}),('wrong-origin',{'Origin':'https://unrelated.invalid'}),('spoofed-host',{'Host':'unrelated.invalid','Origin':origin})]:
                req=urllib.request.Request(origin+'/api/view/session',headers=headers)
                try:
                    with urllib.request.urlopen(req,timeout=5) as r:statuses[name]=r.status
                except urllib.error.HTTPError as e:statuses[name]=e.code
            # Reads may intentionally expose locked-state; enforce unsafe write refusal for host/origin probes.
            for name,headers in [('wrong-origin',{'Origin':'https://unrelated.invalid'}),('spoofed-host',{'Host':'unrelated.invalid','Origin':origin})]:
                req=urllib.request.Request(origin+'/api/drafts',data=b'{"text":"synthetic-refused"}',headers={'Content-Type':'application/json',**headers},method='POST')
                try:
                    with urllib.request.urlopen(req,timeout=5) as r:code=r.status
                except urllib.error.HTTPError as e:code=e.code
                assert code in [401,403],(name,code);statuses[name+'-write']=code
            # Authentic rollback roundtrip through the same selected private route, with a stale-CAS negative first.
            def cas_state():
                x=container();return {'id':x['Id'],'image':x['Image'],'mounts':mounts(x),'port_bindings':x['HostConfig']['PortBindings']}
            def guarded_selected_update(expected,target,asset_source):
                assert cas_state()==expected,'stale fixture CAS refuses before preparation or lifecycle writes'
                shutil.copyfile(asset_source,asset_current);catalog(target)
                q=store_selection.resolve(c,'messenger',{'source':'owner-private','repo':entry['repo'],'commit':target['commit'],'operation':'update'})
                with patch.object(Runtipi,'req',logged_req):outcome=store_selection.execute(c,'messenger',q)
                assert outcome.get('status')=='running' and not outcome.get('error')
            expected=cas_state();bad={**expected,'image':'sha256:'+'0'*64};fetches_before=len(fetch_log);calls_before=len(calls)
            try:guarded_selected_update(bad,oldentry,base_archive)
            except AssertionError as error:assert 'stale fixture CAS' in str(error)
            else:raise AssertionError('stale CAS did not refuse')
            assert cas_state()==expected and len(fetch_log)==fetches_before and len(calls)==calls_before
            guarded_selected_update(expected,oldentry,base_archive)
            assert container()['Image']==base_aid['config_id'] and h(canary)==canary_hash and mounts(container())==mounts(before)
            assert (appdir/'.wizard-commit').read_text().strip()==baseline_sha
            guarded_selected_update(cas_state(),entry,archive)
            assert container()['Image']==entry['images']['amd64']['image_id'] and h(canary)==canary_hash and mounts(container())==mounts(after)
            assert (appdir/'.wizard-commit').read_text().strip()==I['source']
            assert len([q for q in calls if q['method']=='PATCH' and q['path']=='/app-lifecycle/messenger:wizardapps/update' and q['body']=={'performBackup':True}])==3
            R['lifecycle']={'stale_cas_refusal_before_writes':True,'authenticated_rollback_and_repromotion_pass':True,'controller_update_count':3,'install':{'commit':baseline_sha,'image_id':base_aid['config_id']},'update':{'commit':I['source'],'image_id':after['Image']},'controller_calls':calls,'source_fetches':fetch_log,'mounted_state_preserved':True,'exact_mounts':mounts(after),'shipped_compose_sha256':CUST['candidate']['files']['runtipi/docker-compose.yml'],'generated_compose_sha256':genhash,'ports':ports,'archive_retention_reload_after_image_removal':True,'manager_recreated':True,'source_bytes_verified_after_update':True,'auth_probes':statuses,'only_app_installed':'messenger','no_real_account':True}
            R['lifecycle'].update(old_code_read_post_update_app_write=True,old_code_image=base_aid['config_id'],synthetic_only=True,baseline_version=oldconfig['version'],target_version=newconfig['version'],baseline_counter=oldconfig['tipi_version'],target_counter=newconfig['tipi_version'],different_binary_versions=True)
            R['lifecycle_pass']=True;save('lifecycle.json',R['lifecycle'])
    finally:
        # Namespace init also has a kill/absence fence if any assertion or HTTP operation failed.
        try:rig('down','--remove-orphans')
        finally:index.shutdown();index.server_close();thread.join();os.environ.clear();os.environ.update(oldenv)

def focused_reconciliation(src):
    # Only impacted files; do not re-label historical aggregate receipt as current-source proof.
    cases=[]
    converter=CAP/'converter';proof=json.loads((converter/'build-receipt.json').read_text())
    for n,digest in proof['converter_files'].items():assert h(converter/n)==digest
    signal_source=extract('signal-source')
    for n in ['plumbing/signal-bridge/Dockerfile','plumbing/signal-bridge/albums.patch','plumbing/signal-bridge/converter-fixture_test.go']:
        assert h(src/n)==h(signal_source/n),'native converter closure changed: '+n
    py=['tests.test_incoming_media','tests.test_status_broadcast','tests.test_signal_albums','tests.test_approved_composite.ApprovedCompositeTests']
    js=['tests/test_history_search_view.cjs','tests/test_draft_attachment_recovery.cjs','tests/list-scroll.test.mjs','tests/share-recents.test.mjs','tests/live_feature_map.test.mjs','tests/test_connectors_view.cjs','tests/test_connector_login_runtime.cjs']
    for name in py:
        ingress=WORK/'work'/'converter-ingress';ingress.mkdir(exist_ok=True)
        log=run(['docker','run','--rm','--label','wizard.qa.run='+RUN,'--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--user','1000:1000','--tmpfs','/tmp:rw,noexec,nosuid,uid=1000,gid=1000','--tmpfs','/run/messenger:rw,noexec,nosuid,mode=0700,uid=1000,gid=1000','-v',str(src)+':/qa:ro','-v',str(converter)+':/converter:ro','-v',str(ingress)+':/ingress','-w','/qa','-e','PYTHONDONTWRITEBYTECODE=1','-e','SIGNAL_CONVERTER_FIXTURES=/converter','-e','SIGNAL_INGRESS_PROOF=/ingress/proof.json','--entrypoint','python3',R['packaging']['candidate_tag'],'-m','unittest','-v',name],timeout=180,include_stderr=True)
        assert not re.search(r'\bskipped\b',log),name
        cases.append({'case':name,'pass':True});(OUT/(name+'.log')).write_text(log)
    for name in js:
        log=run([os.environ['NODE'],'--test',name],cwd=src,timeout=120)
        assert not re.search(r'^# (?:fail|skipped) [1-9]',log,re.M),name
        cases.append({'case':name,'pass':True});(OUT/(Path(name).name+'.log')).write_text(log)
    ingress=json.loads((WORK/'work/converter-ingress/proof.json').read_text())
    assert len(ingress['baseline'])==4 and len(ingress['candidate'])==3 and len(ingress['after_part_delete'])==3
    save('converter-ingress.json',ingress);R['converter_ingress_native_pass']=True
    shell=extract('shell')
    env=dict(os.environ,SHELL_DIR=str(shell/'web'))
    run([os.environ['NODE'],str(src/'tests/account_setup_browser.cjs'),str(OUT/'account-setup')],cwd=src,env=env,timeout=300)
    cases.append({'case':'account_setup_browser.cjs','pass':True,'scope':'synthetic hosted proxy, separate from canonical-shell acceptance'})
    R['reconciliation_pass']=True
    save('reconciliation-source.json',{'pass':True,'source':I['source'],'historical_source':I['historical_source'],'cases':cases,'untouched_closure':json.loads((CAP/'reconciliation.json').read_text())['accepted_closure'],'current_source_browser_aggregate_not_inherited':True})

def canonical(static):
    shell=WORK/'work'/'shell';assert shell.is_dir();catalogue=ROOT/'capsule/canonical_shell_origin.cjs'
    env=dict(os.environ,MESSENGER_STATIC_DIR=str(static),WIZARD_WEB_DIR=str(shell/'web'),MESSENGER_PUBLIC_PIN_DIR=str(CAP/'public-pin'))
    p=subprocess.Popen([os.environ['NODE'],str(catalogue),'--web',str(shell/'web'),'--static',str(static),'--port','18731'],env=env,stdout=open(OUT/'canonical-origin.log','w'),stderr=subprocess.STDOUT,start_new_session=True);PROCS.append(p)
    wait('http://127.0.0.1:18731/wizard-os-home/index.html',30)
    run([os.environ['NODE'],str(CAP/'canonical_shell_browser.cjs'),str(OUT/'canonical'),'http://127.0.0.1:18731'],env=env,timeout=900)
    data=json.loads((OUT/'canonical/receipt.json').read_text());assert data['pass']
    R['canonical_pass']=True;R['canonical']=data

def main():
    assert str(ROOT).startswith('/srv/work/') and str(WORK).startswith(str(ROOT)+'/')
    daemon=json.loads(docker('info','--format','{{json .}}'));assert 'wizard.qa.run='+RUN in daemon['Labels']
    entry,src,static,archive=packaging()
    current=extract('current-live-source')
    args=['python3',str(CAP/'app-parity-gate'),str(current),str(src),'--json']
    if (src/'docs/live-feature-renames.txt').exists():args+=['--renames',str(src/'docs/live-feature-renames.txt')]
    parity=subprocess.run(args,capture_output=True,text=True,timeout=120)
    (OUT/'current-live-parity.json').write_text(parity.stdout);(OUT/'current-live-parity.stderr').write_text(parity.stderr)
    R['current_live_parity_pass']=parity.returncode==0 and json.loads(parity.stdout).get('verdict')=='PASS'
    assert R['current_live_parity_pass'],'exact archived current source parity must PASS without waivers'
    R['promotion_blocked_by_live_source_drift']=I['promotion_blocked_by_live_source_drift']
    R['release_accepted']=False
    # Canonical first: does not depend on any fixture engine content or account.
    focused_reconciliation(src)
    canonical(static)
    lifecycle(entry,src,archive)
    R['pass']=R['packaging_pass'] and R['canonical_pass'] and R['lifecycle_pass'] and R['current_live_parity_pass'] and R['reconciliation_pass'] and R.get('converter_ingress_native_pass') is True
    save('delivery.json',R)
if __name__=='__main__':
    rc=1
    try:main();rc=0
    except BaseException as e:R['error']=type(e).__name__+': '+str(e);raise
    finally:
        for p in PROCS:
            if p.poll() is None:
                os.killpg(p.pid,15)
                try:p.wait(timeout=5)
                except subprocess.TimeoutExpired:os.killpg(p.pid,9);p.wait()
        save('delivery.json',R)
