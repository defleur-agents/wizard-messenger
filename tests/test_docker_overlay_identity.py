"""Run only inside the parent-admitted forum/light continuation."""
from pathlib import Path
import copy
import json
import hashlib
import io
import tarfile
import tempfile
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from docker_overlay_identity import check_loaded, local_build_argv, assert_local_builder, archive_identity

class ImportedSerializer(unittest.TestCase):
    def setUp(self):
        d=json.loads((Path(__file__).parent/'fixtures/docker_imported_base.json').read_text())
        self.info=d['loaded']; self.frozen=d['frozen']
    def test_exact_observed_cmd_and_volumes_null_expansion(self):
        raw=self.frozen['raw_config']['config']; actual=self.info['Config']
        self.assertNotIn('Cmd',raw); self.assertIsNone(actual['Cmd'])
        self.assertNotIn('Volumes',raw); self.assertIsNone(actual['Volumes'])
        self.assertEqual(check_loaded(self.info,self.frozen),'config_digest')
    def test_every_observed_extra_rejects_nondefault_and_wrong_json_type(self):
        extras=set(self.info['Config'])-set(self.frozen['raw_config']['config'])
        self.assertEqual(extras,{'Hostname','Domainname','AttachStdin','AttachStdout','AttachStderr','Tty','OpenStdin','StdinOnce','Image','OnBuild','Cmd','Volumes'})
        for k in extras:
            for value in ['not-default',[],{},0]:
                with self.subTest(field=k,value=value):
                    i=copy.deepcopy(self.info);i['Config'][k]=value
                    with self.assertRaises(AssertionError):check_loaded(i,self.frozen)
    def test_no_unknown_fields_or_raw_field_removal_or_drift(self):
        variants=[]
        i=copy.deepcopy(self.info);i['Config']['UnknownEmpty']=None;variants.append(i)
        for k in self.frozen['raw_config']['config']:
            i=copy.deepcopy(self.info);del i['Config'][k];variants.append(i)
            i=copy.deepcopy(self.info);i['Config'][k]={'unexpected':'value'};variants.append(i)
        for i in variants:
            with self.assertRaises(AssertionError):check_loaded(i,self.frozen)
    def test_raw_null_cannot_be_removed_and_raw_value_never_normalized(self):
        f=copy.deepcopy(self.frozen);f['raw_config']['config']['Cmd']=None
        i=copy.deepcopy(self.info);del i['Config']['Cmd']
        with self.assertRaises(AssertionError):check_loaded(i,f)
        f['raw_config']['config']['Cmd']=['fixed-command']
        with self.assertRaises(AssertionError):check_loaded(self.info,f)
    def test_unrelated_typed_id_arch_and_os_refused(self):
        for key,value in [('Id','sha256:'+'0'*64),('Architecture','arm64'),('Os','windows')]:
            i=copy.deepcopy(self.info);i[key]=value
            with self.assertRaises(AssertionError):check_loaded(i,self.frozen)
    def test_ordered_full_rootfs_not_subset(self):
        for layers in [[],self.info['RootFS']['Layers'][::-1],self.info['RootFS']['Layers'][:-1],self.info['RootFS']['Layers']+['sha256:'+'0'*64]]:
            i=copy.deepcopy(self.info);i['RootFS']['Layers']=layers
            with self.assertRaises(AssertionError):check_loaded(i,self.frozen)
        i=copy.deepcopy(self.info);i['RootFS']['Type']='other'
        with self.assertRaises(AssertionError):check_loaded(i,self.frozen)
    def test_raw_oci_config_remains_accepted_without_expansion(self):
        i=copy.deepcopy(self.info);i['Config']=copy.deepcopy(self.frozen['raw_config']['config']);i['Id']=self.frozen['manifest_digest']
        self.assertEqual(check_loaded(i,self.frozen),'manifest_digest')
    def test_exact_signal_user_and_entrypoint_expansion(self):
        d=json.loads((Path(__file__).parent/'fixtures/docker_imported_signal.json').read_text())
        self.assertNotIn('User',d['frozen']['raw_config']['config'])
        self.assertNotIn('Entrypoint',d['frozen']['raw_config']['config'])
        self.assertEqual(check_loaded(d['loaded'],d['frozen']),'config_digest')
        for k,value in [('User','root'),('Entrypoint',[]),('Entrypoint',['changed'])]:
            i=copy.deepcopy(d['loaded']);i['Config'][k]=value
            with self.assertRaises(AssertionError):check_loaded(i,d['frozen'])
    def test_named_local_base_and_shared_docker_driver_only(self):
        argv=local_build_argv('wizard-messenger-base:composed-123456789abc','1'*40,'target:one','release/composed.Dockerfile')
        self.assertIn('--builder=default',argv);self.assertIn('--pull=false',argv)
        self.assertIn('BASE=wizard-messenger-base:composed-123456789abc',argv)
        self.assertNotIn('BASE='+self.info['Id'],argv)
        with self.assertRaises(AssertionError):local_build_argv(self.info['Id'],'1'*40,'target:one','release/composed.Dockerfile')
        good={'Name':'default','Driver':'docker','Nodes':[{'Endpoint':'default'}]}
        assert_local_builder(good)
        for key,value in [('Driver','docker-container'),('Name','remote')]:
            bad=copy.deepcopy(good);bad[key]=value
            with self.assertRaises(AssertionError):assert_local_builder(bad)

class FrozenArchive(unittest.TestCase):
    def fixture(self, path, fault=None):
        blobs={}
        def blob(data):
            b=data if isinstance(data,bytes) else json.dumps(data).encode()
            d='sha256:'+hashlib.sha256(b).hexdigest();blobs['blobs/'+d.replace(':','/')]=b
            return {'digest':d,'size':len(b)}
        layers=[blob(b'first-layer'),blob(b'second-layer')]
        cfg=blob({'config':{'User':'1000:1000'},'os':'linux','architecture':'amd64','rootfs':{'type':'layers','diff_ids':['sha256:'+'1'*64,'sha256:'+'2'*64]}})
        manifest=blob({'config':cfg,'layers':layers})
        index={'manifests':[manifest]}
        legacy=[{'Config':'blobs/'+cfg['digest'].replace(':','/'),'Layers':['blobs/'+x['digest'].replace(':','/') for x in layers]}]
        if fault=='size':index['manifests'][0]['size']+=1
        if fault=='legacy-order':legacy[0]['Layers'].reverse()
        if fault=='unreachable-extra':index['manifests'].append(manifest)
        if fault=='layer-corrupt':blobs[legacy[0]['Layers'][0]]=b'changed'
        blobs['index.json']=json.dumps(index).encode();blobs['manifest.json']=json.dumps(legacy).encode()
        with tarfile.open(path,'w') as t:
            for name,data in blobs.items():
                m=tarfile.TarInfo(name);m.size=len(data);t.addfile(m,io.BytesIO(data))
    def test_archive_graph_and_all_blob_bytes_remain_strict(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'image.tar';self.fixture(p);proof=archive_identity(p)
            self.assertEqual(len(proof['raw_config']['rootfs']['diff_ids']),2)
            for fault in ['size','legacy-order','unreachable-extra','layer-corrupt']:
                with self.subTest(fault=fault):
                    self.fixture(p,fault)
                    with self.assertRaises(AssertionError):archive_identity(p)

if __name__=='__main__':unittest.main()
