"""Pure packet regression only; executed exclusively by admitted forum/light runner."""
from pathlib import Path
import json
import sys
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import composed_lifecycle as L

class ComposedLifecycle(unittest.TestCase):
    def before(self):
        return {'config.json':json.dumps({'tipi_version':55}),'docker-compose.yml':(ROOT/'runtipi/docker-compose.yml').read_text(),'wizard.md':'unchanged','.wizard-commit':L.BASE+'\n','.wizard-selection':'{}'}
    def test_only_two_service_images_and_two_pins_change(self):
        import difflib
        before=self.before();after=L.target(before,'a'*40,'sha256:'+'b'*64,56)
        delta=[l[1:].strip() for l in difflib.ndiff(before['docker-compose.yml'].splitlines(),after['docker-compose.yml'].splitlines()) if l[:1] in '+-']
        self.assertEqual(sorted(delta),sorted(['image: '+L.SIGNAL_OLD,'image: ${MESSENGER_IMAGE:-wizard-messenger:0.2.0-unified.15.14}','image: sha256:'+'b'*64,'image: '+L.SIGNAL_IMAGE,'pull_policy: never']))
        self.assertEqual(before['wizard.md'],after['wizard.md'])
        self.assertEqual(json.loads(after['config.json'])['tipi_version'],56)
    def test_wrong_baseline_image_stanza_is_refused(self):
        for token in [L.SIGNAL_OLD,'  messenger:\n']:
            b=self.before();b['docker-compose.yml']=b['docker-compose.yml'].replace(token,'wrong')
            with self.assertRaises(AssertionError):L.target(b,'a'*40,'sha256:'+'b'*64,56)
    def test_target_inspection_keeps_full_raw_config_and_rootfs_proof(self):
        d=json.loads((ROOT/'tests/fixtures/docker_imported_base.json').read_text())
        with patch.object(L,'image_info',return_value=d['loaded']):self.assertEqual(L.verify_image('test',d['frozen']),d['loaded']['Id'])
        for key in ['Cmd','Volumes']:
            d=json.loads((ROOT/'tests/fixtures/docker_imported_base.json').read_text());d['loaded']['Config'][key]=['not-null']
            with patch.object(L,'image_info',return_value=d['loaded']):
                with self.assertRaises(AssertionError):L.verify_image('test',d['frozen'])
    def test_wrong_service_identity_blocks_readback_before_content_read(self):
        # settings/gateway/recipe seams are synthetic; no WAM/Docker/API execution.
        old={'image':'old','container_id':'keep','started':'same','status':'running','health':'healthy'}
        plan={'services':{'messenger':dict(old),'signal':dict(old),'slack':dict(old)},'owner_settings_sha256':'settings','gateway_pins':{},'revision':'a'*40}
        now={k:dict(v) for k,v in plan['services'].items()};now['messenger']['image']='new';now['signal']['image']='sig';now['slack']['container_id']='restarted'
        with patch.object(L,'files',return_value={}),patch.object(L,'settings_hash',return_value='settings'),patch.object(L,'pins',return_value={}),patch.object(L,'service_metadata',return_value=now),patch.object(L,'public_static',side_effect=AssertionError('must not read assets after drift')):
            with self.assertRaisesRegex(AssertionError,'unrelated service restarted slack'):
                L.verify_state(plan,None,{},'new',{},'sig')
    def test_signal_target_digest_kind_is_archive_qualified(self):
        import copy
        import subprocess
        d=json.loads((ROOT/'tests/fixtures/docker_imported_signal.json').read_text())
        i=copy.deepcopy(d['loaded']);i['Id']=d['frozen']['manifest_digest']
        with patch.object(L,'image_info',return_value=i):
            self.assertEqual(L.resolve_signal(d['frozen']),i['Id'])
        with patch.object(L,'image_info',side_effect=[subprocess.CalledProcessError(1,['docker']),d['loaded']]):
            self.assertEqual(L.resolve_signal(d['frozen']),d['loaded']['Id'])
        i['Config']['User']='root'
        with patch.object(L,'image_info',return_value=i):
            with self.assertRaises(AssertionError):L.resolve_signal(d['frozen'])
    def test_five_file_payload_has_no_gateway_pinned_changes(self):
        import run_composed_overlay_forum as R
        self.assertEqual(set(R.PATHS),{'unified.py','static/unified.js','static/unified.css','static/connectors.js','plumbing/connectors-provenance.json'})
        self.assertEqual(L.CHANGED,{'messenger','signal'})
        self.assertNotIn('static/index.html',R.PATHS)
        self.assertNotIn('static/app.js',R.PATHS)

if __name__=='__main__':unittest.main()
