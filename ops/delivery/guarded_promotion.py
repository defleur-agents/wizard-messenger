#!/usr/bin/env python3
"""Guarded Messenger-only promotion adapter. NOT invoked by acceptance job.
Default action is check (no live reads/writes). Apply/rollback require a parent-supplied acceptance
binding, durable verified image archive, fresh live CAS and established shared promotion lock.
Refuses the newly detected post-acceptance live source drift; no automatic merge or old snapshot restore.
"""
from pathlib import Path
import argparse,fcntl,hashlib,json,os,shutil,subprocess,sys,tarfile,time,urllib.request
from unittest.mock import patch
ROOT=Path(__file__).resolve().parent
if ROOT.name=='capsule':ROOT=ROOT.parent
CAP=ROOT/'capsule'
H=lambda b:hashlib.sha256(b).hexdigest()
def filehash(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        while b:=f.read(1048576):h.update(b)
    return h.hexdigest()
def read(p):return json.loads(Path(p).read_text())
def eligibility(inputs,accepted):
    assert not inputs['promotion_blocked_by_live_source_drift'],'REFUSED: current live source changed after accepted preservation baseline; restage/reconcile first'
    assert accepted['source']==inputs['source']
    assert accepted['packaging_pass'] and accepted['canonical_pass'] and accepted['lifecycle_pass'] and accepted['absence_pass']
    assert accepted['independently_reviewed'] and accepted['screenshots_visually_reviewed'] and accepted['current_live_parity_pass']
    assert accepted['no_waivers'] and accepted['durable_archive_readback_verified'] and accepted['reconciliation_pass']
    assert accepted['signal_override_preservation_reviewed'] and accepted['no_auth_policy_change']
    assert accepted['candidate_mount_free_retention_verified'] and accepted['baseline_retention_verified']
    assert accepted['converter_ingress_native_pass'] and accepted['protected_app_mapping_reviewed']
    assert accepted['durable_archive_uri'].startswith(('r2:','s3://'))
    return True

def validate(approval):
    i=read(CAP/'inputs.json');m=read(ROOT/'manifest.json')
    for n,h in m['files'].items():assert filehash(ROOT/n)==h,'sealed capsule drift '+n
    a=read(approval);eligibility(i,a)
    assert a['manifest_sha256']==filehash(ROOT/'manifest.json')
    for path,key in [('receipt.json','forum_receipt_sha256'),('delivery.json','delivery_receipt_sha256'),('packaging.json','packaging_receipt_sha256'),('lifecycle.json','lifecycle_receipt_sha256'),('reconciliation-source.json','reconciliation_receipt_sha256'),('canonical/receipt.json','canonical_receipt_sha256'),('current-live-parity.json','parity_receipt_sha256')]:assert filehash(ROOT/'results'/path)==a[key]
    rr=read(ROOT/'results/receipt.json');d=read(ROOT/'results/delivery.json');p=read(ROOT/'results/packaging.json');cat=read(ROOT/'results/artifacts/private-catalog.json')
    assert rr['native_accepted'] and rr['converter_ingress_native_pass'] and d['converter_ingress_native_pass']
    assert rr['pass'] and rr['absence_pass'] and d['current_live_parity_pass'] and d['reconciliation_pass'] and not d['promotion_blocked_by_live_source_drift']
    assert cat['schema']==1 and cat['scope']=='private-test' and len(cat['apps'])==1
    entry=cat['apps'][0];assert entry['id']=='messenger' and entry['commit']==i['source'] and entry['repo']=='humanitylabs-org/wizard-messenger'
    asset=entry['images']['amd64'];archive=ROOT/'results/artifacts'/asset['asset']
    assert filehash(archive)==asset['sha256']==a['archive_sha256']==p['archive']['archive_sha256']
    assert p['source_version']==i['version'] and p['image_version']==i['version']
    assert p['source_overlay']==i['source'] and p['engine_source']==i['engine_source'] and p['base_origin']==i['base']
    return i,a,entry,archive

def command(a):return subprocess.check_output(a,text=True,timeout=45)
def docker(*a):return command(['docker',*a])
def metadata(c):
    rt=c.runtipi();rows=rt.installed();expected=read(CAP/'inputs.json')['live_control_metadata'];assert len(rows)==expected['installed_count'],'installed app census changed; explicitly restage'
    # Raw account/config data is not saved/projected; only row hashes and fixed metadata are retained.
    rowhash={((x.get('info') or {}).get('urn') or ''):H(json.dumps(x,sort_keys=True,separators=(',',':')).encode()) for x in rows}
    assert len(rowhash)==expected['installed_count'] and '' not in rowhash
    rec=[x for x in rows if ((x.get('info') or {}).get('urn') or '').startswith('recorder:')];assert len(rec)==expected['recorder_count']
    recorder_stopped=len(rec)==1 and rec[0]['app']['status']=='stopped';assert recorder_stopped==expected['recorder_stopped']
    cid=docker('ps','-aq','--filter','label=runtipi.appurn=messenger:wizardapps','--filter','label=com.docker.compose.service=messenger').split();assert len(cid)==1
    fmt='{"Id":{{json .Id}},"Image":{{json .Image}},"Mounts":{{json .Mounts}},"Config":{"Labels":{{json .Config.Labels}}},"HostConfig":{"PortBindings":{{json .HostConfig.PortBindings}}}}'
    x=json.loads(docker('inspect','--format',fmt,cid[0]))
    # All explicit mounts, actual generated-file list and ports are part of the CAS. Never read /data or app.env values.
    image=json.loads(docker('image','inspect','--format','{"Config":{"Labels":{{json .Config.Labels}}},"RootFS":{{json .RootFS}}}',x['Image']))
    signal=json.loads(docker('inspect','--format',fmt,'messenger_wizardapps-signal-1'))
    signal_image=json.loads(docker('image','inspect','--format','{"id":{{json .Id}},"rootfs":{{json .RootFS}},"labels":{{json .Config.Labels}}}',signal['Image']))
    assert signal_image==read(CAP/'signal-image-identity.json'),'Signal image/ordered RootFS/source label drift'
    sealed_signal=read(CAP/'signal-readonly-metadata.json')
    assert signal['Image']==sealed_signal['image_id'] and signal['Mounts']==sealed_signal['mounts'],'Signal image or mounted view changed'
    current=Path('/home/telos/.local/share/wizard-ux/current').resolve()
    unit=lambda n:command(['systemctl','--user','show',n,'-p','MainPID','--value']).strip()
    controls=[c.runtipi_root/'apps/wizardapps/messenger/docker-compose.generated.yml',c.runtipi_root/'app-data/wizardapps/messenger/app.env',c.runtipi_root/'user-config/wizardapps/messenger/docker-compose.yml',c.runtipi_root/'user-config/wizardapps/messenger/app.env',c.home/'apps.json',Path('/home/telos/.local/bin/wam')]
    files={str(p):filehash(p) for p in controls if p.is_file()}
    # Gateway config path is supplied by the already-audited parent, not guessed or rewritten by this adapter.
    return {'container_id':x['Id'],'image_id':x['Image'],'image_revision':image['Config']['Labels'].get('org.opencontainers.image.revision'),'image_overlay':image['Config']['Labels'].get('org.wizardos.source-overlay.revision'),'rootfs':image['RootFS'],'signal_image':signal_image,'signal_mounts':signal['Mounts'],'compose_config_files':x['Config']['Labels'].get('com.docker.compose.project.config_files'),'config_hash':x['Config']['Labels'].get('com.docker.compose.config-hash'),'mounts':sorted((m['Source'],m['Destination'],m['RW']) for m in x['Mounts']),'ports':x['HostConfig']['PortBindings'],'rows':rowhash,'recorder_stopped':recorder_stopped,'shell_release':str(current),'service_pid':unit('wizard-mobile.service'),'gateway_pid':unit('private-gateway-https.service'),'files':files}

def siblings(before,after):
    assert {k:v for k,v in before['rows'].items() if k!='messenger:wizardapps'}=={k:v for k,v in after['rows'].items() if k!='messenger:wizardapps'},'sibling app row drift'
    for k in ['mounts','ports','shell_release','service_pid','gateway_pid','recorder_stopped','signal_image','signal_mounts']:assert before[k]==after[k],'protected state drift '+k

def replace_control(path,b):
    t=path.with_name(path.name+'.messenger-'+str(os.getpid()));t.write_bytes(b);t.chmod(0o644);os.replace(t,path)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['check','prepare','apply','rollback']);ap.add_argument('--approval',type=Path);args=ap.parse_args()
    i=read(CAP/'inputs.json')
    if args.action=='check':
        print(json.dumps({'no_live_reads_or_writes':True,'source':i['source'],'current_live_revision_at_seal':i['current_live_revision'],'accepted_live_revision':i['accepted_live_revision'],'promotion_eligible':False,'source_reconciliation_unblocks_future_acceptance':not i['promotion_blocked_by_live_source_drift'],'reason':'prepared only; requires passing admitted job, independent receipts, durable archive and fresh locked CAS'}));return
    assert args.approval,'all target operations require independent parent acceptance'
    i,a,entry,archive=validate(args.approval)
    assert Path.home()==Path('/home/telos'),'wrong owner target'
    # Use the unchanged installed WAM CLI closure; never the mutable workspace checkout.
    wam=Path('/home/telos/.local/share/wam-private-test/releases')/i['wam']['commit'];sys.path.insert(0,str(wam))
    from wam import cli,private,test_catalog,store_selection
    c=cli.Config();lock=Path('/home/telos/.local/state/wizard-app-promotions/wam.lock');messenger_lock=lock.with_name('messenger.lock');assert lock.is_file() and messenger_lock.is_file()
    tx=ROOT/'promotion';tx.mkdir(exist_ok=True)
    with lock.open('r') as f,messenger_lock.open('r') as mf:
        fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        fcntl.flock(mf,fcntl.LOCK_EX|fcntl.LOCK_NB)
        now=metadata(c)
        for p,h in a['protected_control_hashes'].items():assert filehash(Path(p))==h,'sibling Caddy/About/Service control changed'
        if args.action=='prepare':
            assert now['image_revision']==i['accepted_live_revision']==i['current_live_revision']
            assert now['image_id']==read(CAP/'live-readonly-metadata.json')['image_id']
            assert now['rootfs']==read(CAP/'messenger-image-identity.json')['rootfs']
            assert now['shell_release'].endswith('/'+i['shell']['commit'])
            assert now['mounts']==sorted((m['Source'],m['Destination'],m['RW']) for m in read(CAP/'live-readonly-metadata.json')['mounts'])
            assert a['fresh_parity_live_image_id']==now['image_id']
            (tx/'before.json').write_text(json.dumps(now,indent=2)+'\n')
            # Snapshot code recipe controls ONLY. No app data, credentials, app.env or owner content is copied.
            repo=c.runtipi_root/'repos/wizardapps/apps/messenger';backup=tx/'recipe-before';backup.mkdir()
            allowed={'docker-compose.yml','config.json','metadata','config','.wizard-source','.wizard-commit','.wizard-selection','.wizard-private','.wizard-view-source','.wizard-managed'}
            for p in repo.iterdir():
                if p.is_file() and p.name in allowed:shutil.copyfile(p,backup/p.name)
            (tx/'recipe-before-hashes.json').write_text(json.dumps({p.name:filehash(p) for p in backup.iterdir() if p.is_file()},indent=2)+'\n')
            print(json.dumps({'prepared':True,'live_unmodified':True,'source':i['source'],'before_cas_sha256':filehash(tx/'before.json')}));return
        before=read(tx/'before.json')
        if args.action=='apply':assert now==before,'live CAS changed since prepare; nothing changed'
        else:
            own=read(tx/'after.json');assert now==own,'rollback CAS refuses later work; never restore an old OAuth/environment snapshot'
        repo=c.runtipi_root/'repos/wizardapps/apps/messenger'
        def rollback():
            # Only if the current target still matches the latest own receipt, under the same lock.
            own=read(tx/'after.json');assert metadata(c)==own,'automatic rollback refused stale CAS'
            current_tipi=int(read(repo/'config.json')['tipi_version'])
            for n,h in read(tx/'recipe-before-hashes.json').items():
                p=tx/'recipe-before'/n;assert filehash(p)==h;replace_control(repo/n,p.read_bytes())
            # Rollback restores the exact prior source/image, but Runtipi's lifecycle identity must advance.
            cfg=read(repo/'config.json');cfg['tipi_version']=max(int(cfg['tipi_version']),current_tipi+1);replace_control(repo/'config.json',(json.dumps(cfg,indent=2)+'\n').encode())
            # Existing authenticated controller backup path; NO raw owner-data read or environment restore.
            result=cli.app_update(c,'messenger',backup=True);assert not result.get('error')
            after=metadata(c);siblings(before,after);assert after['image_id']==before['image_id']
            (tx/'rollback.json').write_text(json.dumps(after,indent=2)+'\n')
        if args.action=='rollback':rollback();print('{"rolled_back":true}');return
        catalog=tx/'catalog.json';oldcat=read(os.environ.get('WAM_PRIVATE_CATALOG','/home/telos/projects/wizard-app-test-release-20261015/private-test-catalog.json'))
        oldcat['apps']=[entry if x['id']=='messenger' else x for x in oldcat['apps']];assert sum(x['id']=='messenger' for x in oldcat['apps'])==1
        catalog.write_text(json.dumps(oldcat,indent=2)+'\n')
        # Local immutable source + image archive are transport adapters already exercised in the fixture lifecycle.
        def fetch(repo_name,commit,dest,tok):
            assert repo_name==entry['repo'] and commit==i['source']
            with tarfile.open(CAP/'candidate.tar') as t:t.extractall(dest,filter='data')
        def preload(e,tok):
            assert e==entry and filehash(archive)==e['images']['amd64']['sha256']
            subprocess.run(['docker','load','-i',str(archive)],check=True,capture_output=True,timeout=900)
            return test_catalog._loaded_identity(e['images']['amd64'],archive,'amd64')
        old=os.environ.get('WAM_PRIVATE_CATALOG');os.environ['WAM_PRIVATE_CATALOG']=str(catalog)
        try:
            with patch.object(private,'fetch',fetch),patch.object(test_catalog,'preload',preload):
                selection=store_selection.resolve(c,'messenger',{'source':'owner-private','repo':entry['repo'],'commit':i['source'],'operation':'update'})
                result=store_selection.execute(c,'messenger',selection)
            after=metadata(c);(tx/'after.json').write_text(json.dumps(after,indent=2)+'\n')
            assert not result.get('error') and result.get('status')=='running'
            siblings(before,after);assert after['image_id']==read(ROOT/'results/packaging.json')['candidate_daemon_id']
            for p,h in a['protected_control_hashes'].items():assert filehash(Path(p))==h
            # Read static assets only; no message/history/account reads and no new owner sign-in.
            binds=[x for xs in after['ports'].values() for x in xs];assert len(binds)>=1
            base='http://127.0.0.1:'+binds[0]['HostPort']
            assets={}
            for n,v in read(ROOT/'results/packaging.json')['candidate_closure'].items():
                if not n.startswith('/app/static/'):continue
                rel=n[len('/app/static/'):]
                with urllib.request.urlopen(base+'/'+rel,timeout=10) as r:b=r.read()
                assert H(b)==v['sha256'];assets[rel]=H(b)
            (tx/'static-http-readback.json').write_text(json.dumps(assets,indent=2)+'\n')
            print(json.dumps({'applied':True,'source':i['source'],'siblings_preserved':True,'static_hash_readback':True,'owner_content_read':False}))
        except BaseException:
            if (tx/'after.json').exists():rollback()
            raise
        finally:
            if old is None:os.environ.pop('WAM_PRIVATE_CATALOG',None)
            else:os.environ['WAM_PRIVATE_CATALOG']=old
if __name__=='__main__':main()
