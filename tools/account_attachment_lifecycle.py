"""Parent-only existing WAM lifecycle packet. Never run promote/rollback from a child.
No user-config writes; its entire response is hash-guarded model-blind and existing two workers stay untouched.
Image import must precede plan, with archive SHA verified; no build/export occurs here.
"""
import argparse
import base64
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
PKT = Path('/home/telos/.local/share/messenger-releases/account-attachment-composite-20261105')
STORE = Path('/home/telos/runtipi/repos/wizardapps/apps/messenger')
INSTALLED = Path('/home/telos/runtipi/apps/wizardapps/messenger')
LOCK = Path('/home/telos/.local/state/wizard-app-promotions/messenger.lock')
WAM = '/home/telos/.local/share/wam-private-test/releases/9309d85767203983aa18917e53660d2c968bd2aa'
BASE = '4566306576d3a6805da1ba531da3a89214dfd7af'
BASE_IMAGE = 'sha256:75dde49255cdb88b789103170b69c68517a7acc6a8523fec3ee0f2174235b84e'
NAMES = ['config.json', 'docker-compose.yml', 'wizard.md', '.wizard-commit', '.wizard-selection']


def h(b):
    return hashlib.sha256(b).hexdigest()


def dump(path, obj):
    with Path(path).open('x') as f:
        json.dump(obj, f, indent=2)
    Path(path).chmod(0o600)


def cmd(*args):
    return subprocess.check_output(args, text=True, timeout=180).strip()


def target(before, revision, image, tipi):
    result = dict(before)
    cfg = json.loads(before['config.json'])
    cfg['tipi_version'] = tipi
    result['config.json'] = json.dumps(cfg, indent=2) + '\n'
    old = '${MESSENGER_IMAGE:-wizard-messenger:0.2.0-unified.15.14}'
    assert before['docker-compose.yml'].count(old) == 4, 'exact live four shared-image uses required'
    stanza = '  messenger:\n    image: ' + old
    assert before['docker-compose.yml'].count(stanza) == 1
    # Change only the main app. Init and translation keep their current full image bytes.
    result['docker-compose.yml'] = before['docker-compose.yml'].replace(stanza, '  messenger:\n    image: ' + image)
    result['.wizard-commit'] = revision + '\n'
    result['.wizard-selection'] = json.dumps({'repo': 'humanitylabs-org/wizard-messenger', 'commit': revision}) + '\n'
    return result


def files(path):
    return {n: (path / n).read_text() for n in NAMES}


def writefiles(tree):
    for root in [STORE, INSTALLED]:
        for n, text in tree.items():
            p = root / n
            # Existing root-owned installed directories have owner-writable files; no chmod/chown escalation.
            with p.open('r+b') as f:
                f.seek(0); f.truncate(); f.write(text.encode()); f.flush(); os.fsync(f.fileno())
            assert p.read_text() == text


def service_metadata():
    names = cmd('docker', 'ps', '-a', '--filter', 'label=com.docker.compose.project=messenger_wizardapps', '--format', '{{.Names}}').splitlines()
    result = {}
    for name in sorted(names):
        # Narrow metadata only; never Env, Mounts, logs, data or app settings/content.
        row = cmd('docker', 'inspect', '--format', '{{.Id}}|{{.Image}}|{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{end}}|{{index .Config.Labels "com.docker.compose.service"}}', name).split('|')
        ident, image, status, health, service = row
        assert service not in result
        result[service] = {'container_id': ident, 'image': image, 'status': status, 'health': health}
    assert {'messenger', 'slack', 'instagram', 'signal', 'whatsapp', 'matrix', 'telegram', 'translation'} <= set(result)
    return result


def settings_hash(rt):
    obj = rt.req('GET', '/user-config/messenger:wizardapps')
    assert obj['isEnabled'] is True
    # Deliberately do not expose or persist values; no PUT/PATCH of settings exists in this tool.
    # sourceCompose is generated from the recipe and must legitimately change on update.
    # Guard every owner-controlled field exactly; public generated recipe bytes have their own strict guards.
    owner = {key: obj[key] for key in ('isEnabled', 'appEnv', 'dockerCompose')}
    return h(json.dumps(owner, sort_keys=True, separators=(',', ':')).encode())


def pins():
    old = json.loads(Path('/home/telos/.hermes/state/share-people-release-20261031/messenger-expected-prior-v2.json').read_text())
    paths = [Path(old['caddy_config']), *[Path(old['pinned_gateway_view']) / n for n in old['pinned_files']]]
    return {str(p): h(p.read_bytes()) for p in paths}


def image_info(ref):
    return json.loads(cmd('docker', 'image', 'inspect', ref))[0]


def verify_image(ref, identity):
    i = image_info(ref)
    assert i['Config'] == identity['config'] and i['RootFS'] == identity['rootfs']
    assert i['Id'] in [identity['manifest_digest'], identity['config_digest']]
    return i['Id']


def public_static(expected):
    result = {}
    for n, digest in expected.items():
        with urllib.request.urlopen('http://127.0.0.1:9245/' + n, timeout=15) as f:
            b = f.read()
        assert h(b) == digest, 'direct served static mismatch ' + n
        result[n] = h(b)
    return result


def verify_state(plan, rt, wanted_files, image, product, rollback=False):
    assert files(STORE) == wanted_files and files(INSTALLED) == wanted_files, 'recipe/pin readback drift'
    assert settings_hash(rt) == plan['owner_settings_sha256'], 'owner settings changed; never overwrite'
    assert pins() == plan['gateway_pins'], 'gateway/shared static drift'
    services = service_metadata()
    assert set(services) == set(plan['services']), 'service set changed'
    for name, old in plan['services'].items():
        now = services[name]
        expected = image if name == 'messenger' else old['image']
        assert now['image'] == expected, 'service image drift ' + name
        if old['status'] == 'running':
            assert now['status'] == 'running' and now['health'] == old['health'], 'service readiness drift ' + name
    assets = public_static(product)
    with urllib.request.urlopen('http://127.0.0.1:9245/healthz', timeout=15) as f:
        health = json.load(f)
    assert health.get('ok') is True and health.get('version') == '0.2.0-unified.15.14'
    # Metadata-only registry readback, no Messenger API or provider page access.
    registry = json.loads(cmd('wam', 'apps', '--json'))
    rows = registry if isinstance(registry, list) else registry.get('apps', [])
    row = next(x for x in rows if x.get('id') == 'messenger')
    expected_revision = BASE if rollback else plan['revision']
    assert row['commit'] == expected_revision and row['status'] == 'running'
    return {'services': services, 'static': assets, 'owner_settings_unchanged': True, 'gateway_pins_unchanged': True, 'registry_commit': row['commit']}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['plan', 'promote', 'rollback', 'verify'])
    p.add_argument('--evidence', type=Path, required=True)
    p.add_argument('--expected-receipt-sha256', required=True)
    p.add_argument('--authority', type=Path)
    p.add_argument('--no-concurrent-config-writers', action='store_true')
    a = p.parse_args()
    sys.path.insert(0, WAM)
    from wam.runtipi import Runtipi
    rt = Runtipi.from_install(Path('/home/telos/runtipi'))
    E = a.evidence
    assert h((E / 'qa-receipt.json').read_bytes()) == a.expected_receipt_sha256
    receipt = json.loads((E / 'qa-receipt.json').read_text())
    assert receipt['scoped_qa_pass'] is True and receipt['native_builds'] == 0 and receipt['activation_performed'] is False
    assert receipt['image_identity_sha256'] == h((E / 'image-identity.json').read_bytes())
    identity = json.loads((E / 'image-identity.json').read_text())
    assert cmd('git', '-C', str(ROOT), 'rev-parse', 'HEAD') == receipt['revision']
    assert not cmd('git', '-C', str(ROOT), 'status', '--porcelain')
    candidate = verify_image(identity['tag'], identity)
    planfile = PKT / 'activation-plan.json'
    with LOCK.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if a.action == 'plan':
            assert not planfile.exists(), 'do not overwrite an existing consumed or unconsumed plan'
            before = files(STORE)
            assert files(INSTALLED) == before and before['.wizard-commit'].strip() == BASE
            services = service_metadata()
            assert services['messenger']['image'] == BASE_IMAGE
            base = image_info(BASE_IMAGE)
            assert base['Config']['Labels']['org.opencontainers.image.revision'] == BASE
            product = {n: h((ROOT / 'static' / n).read_bytes()) for n in ['index.html', 'app.js', 'app.css', 'unified.js', 'unified.css', 'connectors.js']}
            assert all(product[n] == receipt['product'][n] for n in receipt['product'])
            baseline = {n: h(subprocess.check_output(['git', '-C', str(ROOT), 'show', BASE + ':static/' + n])) for n in product}
            public_static(baseline)
            tipi = json.loads(before['config.json'])['tipi_version']
            wanted = target(before, receipt['revision'], candidate, tipi + 1)
            rollback_files = dict(before)
            cfg = json.loads(before['config.json']); cfg['tipi_version'] = tipi + 2
            rollback_files['config.json'] = json.dumps(cfg, indent=2) + '\n'
            # Make rollback independent of a mutable/deleted old tag.
            rollback_files['docker-compose.yml'] = before['docker-compose.yml'].replace('  messenger:\n    image: ${MESSENGER_IMAGE:-wizard-messenger:0.2.0-unified.15.14}', '  messenger:\n    image: ' + BASE_IMAGE)
            dump(planfile, {'revision': receipt['revision'], 'receipt_sha256': a.expected_receipt_sha256,
                'candidate_image': candidate, 'candidate_identity': identity, 'base_image': BASE_IMAGE,
                'base_config': base['Config'], 'base_rootfs': base['RootFS'], 'before': before, 'after': wanted,
                'rollback': rollback_files, 'owner_settings_sha256': settings_hash(rt), 'gateway_pins': pins(),
                'services': services, 'product': product, 'baseline_product': baseline,
                'wam_launcher_sha256': h(Path('/home/telos/.local/bin/wam').read_bytes()),
                'authority_required': True, 'scope': 'static three-file overlay only; preserve every worker override; no settings API write'})
            print(json.dumps({'plan': str(planfile), 'sha256': h(planfile.read_bytes()), 'activation_performed': False})); return
        plan = json.loads(planfile.read_text())
        assert plan['receipt_sha256'] == a.expected_receipt_sha256
        assert plan['wam_launcher_sha256'] == h(Path('/home/telos/.local/bin/wam').read_bytes())
        if a.action == 'verify':
            print(json.dumps(verify_state(plan, rt, plan['after'], candidate, plan['product']))); return
        assert a.no_concurrent_config_writers and a.authority, 'parent authority and serialized owner writers required'
        authority = json.loads(a.authority.read_text())
        assert authority['plan_sha256'] == h(planfile.read_bytes()) and authority['action'] == a.action
        assert authority['screenshots_reviewed'] is True and authority['parent_authorizes_existing_lifecycle'] is True
        assert authority['gateway_served_assets_verified'] is True, 'parent must verify authenticated gateway assets, not only direct app origin'
        assert settings_hash(rt) == plan['owner_settings_sha256'] and pins() == plan['gateway_pins']
        consume = PKT / (a.action + '-consumed.json')
        assert not consume.exists(), 'one-shot authority consumed; preserve receipt, do not retry blindly'
        if a.action == 'promote':
            assert files(STORE) == plan['before'] and files(INSTALLED) == plan['before']
            assert service_metadata() == plan['services'], 'prewrite service/container drift; create fresh plan'
            prior = image_info(BASE_IMAGE)
            assert prior['Config'] == plan['base_config'] and prior['RootFS'] == plan['base_rootfs']
            # Keep both old and new image bytes across Runtipi update cleanup. Never start these containers.
            for role, image in [('base', BASE_IMAGE), ('candidate', candidate)]:
                cmd('docker', 'create', '--name', 'messenger-release-retain-' + plan['revision'][:12] + '-' + role,
                    '--network', 'none', '--entrypoint', '/bin/true', image)
            wanted, image, product = plan['after'], candidate, plan['product']
        else:
            assert files(STORE) == plan['after'] and files(INSTALLED) == plan['after'], 'unexpected partial state: stop and reconcile, never force rollback'
            wanted, image, product = plan['rollback'], BASE_IMAGE, plan['baseline_product']
        dump(consume, {'authority_sha256': h(a.authority.read_bytes()), 'plan_sha256': h(planfile.read_bytes()), 'intent': a.action})
        writefiles(wanted)
        # EXACT supported existing WAM adapter: queued App Manager update, not raw docker compose/restart.
        cmd('wam', 'app', 'update', 'messenger:wizardapps', '--no-backup')
        readback = verify_state(plan, rt, wanted, image, product, rollback=a.action == 'rollback')
        dump(PKT / (a.action + '-readback.json'), readback)
        print(json.dumps({'verified': True, 'action': a.action, 'image': image, 'settings_writes': 0}))

if __name__ == '__main__':
    main()
