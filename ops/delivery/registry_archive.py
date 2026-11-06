"""Anonymous digest-only Registry V2 -> verified Docker archive. No Docker host access.
Registry/index/platform-manifest/config/diffIDs and archive SHA are separate identities.
Only the parent-admitted Forum runner calls this (network, decompression and archive work).
"""
import gzip, hashlib, io, json, os, re, shutil, tarfile, urllib.request, urllib.error
from pathlib import Path

def digest_file(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        while b:=f.read(1024*1024): h.update(b)
    return h.hexdigest()

def export(ref, dest):
    assert re.fullmatch(r'[^\s@]+@sha256:[0-9a-f]{64}',ref),ref
    named, pin=ref.split('@'); host,repo=named.split('/',1) if '.' in named.split('/')[0] else ('registry-1.docker.io',named)
    repo=repo.split(':')[0]
    if host=='registry-1.docker.io' and '/' not in repo: repo='library/'+repo
    base='https://'+host+'/v2/'+repo+'/'
    token=None
    accept='application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.list.v2+json, application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json'
    def get(path):
        nonlocal token
        req=urllib.request.Request(base+path,headers={'Accept':accept,'User-Agent':'Wizard-Messenger-sealed-acceptance','Authorization':'Bearer '+token} if token else {'Accept':accept,'User-Agent':'Wizard-Messenger-sealed-acceptance'})
        try: return urllib.request.urlopen(req,timeout=180)
        except urllib.error.HTTPError as e:
            if e.code!=401 or token: raise
            challenge=e.headers.get('WWW-Authenticate',''); parts=dict(re.findall(r'(\w+)="([^"]+)"',challenge))
            from urllib.parse import urlencode
            assert challenge.startswith('Bearer ') and parts['realm'].startswith('https://')
            url=parts['realm']+'?'+urlencode({k:parts[k] for k in ('service','scope') if k in parts})
            with urllib.request.urlopen(url,timeout=60) as response: auth=json.load(response)
            token=auth.get('token') or auth['access_token']; return get(path)
    def document(d):
        with get('manifests/'+d) as r: b=r.read()
        assert 'sha256:'+hashlib.sha256(b).hexdigest()==d
        return b,json.loads(b)
    work=dest.parent/(dest.name+'.parts');work.mkdir(parents=True,exist_ok=True)
    raw,doc=document(pin); index=raw
    (work/('manifest-'+pin.split(':')[1]+'.json')).write_bytes(raw)
    if 'manifests' in doc:
        choices=[x for x in doc['manifests'] if x.get('platform',{}).get('os')=='linux' and x['platform'].get('architecture')=='amd64']
        assert len(choices)==1,choices
        platform=choices[0]['digest']; raw,doc=document(platform)
    else: platform=pin
    (work/('manifest-'+platform.split(':')[1]+'.json')).write_bytes(raw)
    def blob(d):
        p=work/d.split(':')[1]
        if not p.exists():
            with get('blobs/'+d) as r,open(str(p)+'.part','wb') as f: shutil.copyfileobj(r,f,1024*1024)
            Path(str(p)+'.part').replace(p)
        assert 'sha256:'+digest_file(p)==d
        return p
    config=blob(doc['config']['digest']); cfg=json.loads(config.read_bytes()); assert cfg['os']=='linux' and cfg['architecture']=='amd64'
    assert len(doc['layers'])==len(cfg['rootfs']['diff_ids'])
    layers=[]
    expanded=0
    for i,(layer,diff) in enumerate(zip(doc['layers'],cfg['rootfs']['diff_ids'])):
        p=blob(layer['digest']); target=work/('layer-'+str(i)+'.tar')
        if not target.exists():
            with open(p,'rb') as f: magic=f.read(2)
            if magic==b'\x1f\x8b':
                with gzip.open(p,'rb') as f,open(target,'wb') as o:
                    while block:=f.read(1024*1024):
                        expanded+=len(block)
                        assert expanded<=1024**3,'new carrier exceeds sealed 1 GiB expansion cap'
                        o.write(block)
            else:
                assert 'zstd' not in layer.get('mediaType',''),'zstd layers unsupported (fail closed)'
                shutil.copyfile(p,target)
                expanded+=target.stat().st_size
                assert expanded<=1024**3,'new carrier exceeds sealed 1 GiB expansion cap'
        assert 'sha256:'+digest_file(target)==diff,(ref,i,diff)
        layers.append(target)
    alias='wizard-custody:'+doc['config']['digest'].split(':')[1][:20]
    cname=doc['config']['digest'].split(':')[1]+'.json'
    manifest=[{'Config':cname,'RepoTags':[alias],'Layers':['layer-'+str(i)+'.tar' for i in range(len(layers))]}]
    def add(t,name,b):
        m=tarfile.TarInfo(name);m.size=len(b);m.mode=0o644;m.mtime=0;t.addfile(m,io.BytesIO(b))
    with tarfile.open(str(dest)+'.part','w') as t:
        add(t,cname,config.read_bytes());add(t,'manifest.json',json.dumps(manifest).encode())
        for i,p in enumerate(layers):
            m=t.gettarinfo(p,arcname='layer-'+str(i)+'.tar');m.uid=m.gid=m.mtime=0;m.uname=m.gname='';
            with open(p,'rb') as f:t.addfile(m,f)
    Path(str(dest)+'.part').replace(dest)
    result={'origin':ref,'origin_digest':pin,'platform_manifest_digest':platform,'config_digest':doc['config']['digest'],'rootfs_diff_ids':cfg['rootfs']['diff_ids'],'docker_archive_tag':alias,'archive_sha256':digest_file(dest),'archive_bytes':dest.stat().st_size,'manifest':doc,'index_document_sha256':hashlib.sha256(index).hexdigest()}
    (dest.with_suffix('.identity.json')).write_text(json.dumps(result,indent=2)+'\n')
    # Retain compressed, hash-verified registry transport for the isolated daemon.
    # The decompressed layer tar is already in the Docker custody archive.
    for p in work.glob('layer-*.tar'): p.unlink()
    return result
