"""Read-only census of the exact failed r3 capsule; never uses Docker API."""
from pathlib import Path
import hashlib,json,os,subprocess
ROOT=Path('/srv/work/messenger-delivery-da34eb4-current-r3')
EXPECTED='ab33b9200d21f01225590f1f4b57dc9c3828fc27501eb2ddd930cfe838780cf9'
H=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert H(ROOT/'manifest.json')==EXPECTED
WORK=ROOT/'run';RUN='msg'+EXPECTED[:12]
r={'schema':'messenger-failed-original-recovery/1','original_heavy_id':'heavy_7c5e248d28484dccb23bbe3bad4726d2','original_heavy_log_sha256_parent_verified':'9a2f8c2d4c01f69926366b766eb7387166c20112093e1d526bb28a4a3704d134','original_manifest_sha256':EXPECTED,'original_run':RUN,'read_only':True,'original_pass':False,'original_receipt_missing':not (ROOT/'results/receipt.json').exists(),'original_handoff_seal_sha256':H(ROOT/'handoff-seal.json'),'owned_processes':[],'owned_mounts':[],'inspection_errors':[]}
selfpid=os.getpid()
for p in Path('/proc').iterdir():
    if not p.name.isdigit() or int(p.name)==selfpid:continue
    try:
        raw=(p/'cmdline').read_bytes()
        if str(WORK).encode() in raw or RUN.encode() in raw:
            r['owned_processes'].append({'pid':int(p.name),'comm':(p/'comm').read_text().strip(),'pid_namespace':os.readlink(p/'ns/pid'),'net_namespace':os.readlink(p/'ns/net'),'mount_namespace':os.readlink(p/'ns/mnt'),'cgroup':(p/'cgroup').read_text().strip()})
        rows=[line for line in (p/'mountinfo').read_text().splitlines() if str(WORK) in line or RUN in line]
        if rows:r['owned_mounts'].append({'pid':int(p.name),'matches':rows})
    except (FileNotFoundError,ProcessLookupError):pass
    except BaseException as e:
        try: state=(p/'stat').read_text().rsplit(')',1)[1].split()[0]
        except (FileNotFoundError,ProcessLookupError):continue
        row={'pid':int(p.name),'type':type(e).__name__,'errno':getattr(e,'errno',None),'state':state}
        if isinstance(e,OSError) and getattr(e,'errno',None)==22 and state=='Z':
            r.setdefault('unrelated_zombie_mountinfo_unavailable',[]).append(row)
        else:r['inspection_errors'].append(row)
cg=Path('/sys/fs/cgroup')/RUN
r['cgroup_present']=cg.exists()
r['private_paths']={name:(WORK/name).exists() for name in ['graph','exec','socket','socket/docker.sock','daemon.pid']}
bridge=subprocess.run(['ip','link','show','wzmsg0'],capture_output=True)
r['host_bridge_present']=bridge.returncode==0;r['host_bridge_inspection_exit']=bridge.returncode
r['original_owned_results']={}
for p in sorted((ROOT/'results').iterdir()):
    st=p.lstat()
    if p.is_file() and not p.is_symlink():r['original_owned_results'][p.name]={'sha256':H(p),'uid':st.st_uid,'gid':st.st_gid,'mode':oct(st.st_mode&0o777),'size':st.st_size}
r['cleanup_absence_observed']=bool(not r['owned_processes'] and not r['owned_mounts'] and not r['cgroup_present'] and not any(r['private_paths'].values()) and not r['host_bridge_present'] and bridge.returncode==1 and not r['inspection_errors'])
r['namespace_identity_note']='Original namespace inode was not recorded; no surviving task or mount references the exact owned run/root. No synthetic namespace probe was started.'
r['packaging_canonical_lifecycle']='never started in original job; no PASS inferred'
print(json.dumps(r,indent=2,sort_keys=True))
