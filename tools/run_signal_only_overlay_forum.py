"""One admitted forum LIGHT job: exact-base Messenger overlay + frozen Signal image identity proof.
No native build, browser matrix, owner mounts, providers or live writes. Invoke with the stage-manifest SHA256.
Stage layout (immutable): source/ (this tree), baseline/ (live 4566306 copies of the 3 overlay paths),
verified/ (a23fd8e copies of the same paths), stage-manifest.json.
"""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
S = ROOT.parent
OUT = S / 'evidence'
LIVE = '4566306576d3a6805da1ba531da3a89214dfd7af'
VERIFIED = 'a23fd8e26a7205f861a409681de4437f7394a386'
PATHS = ['unified.py', 'static/unified.js', 'plumbing/connectors-provenance.json']
BASE_ARCHIVE = Path('/srv/work/share-people-messenger-4566306/evidence/messenger-image.tar')
BASE_ARCHIVE_SHA = '1a2e3e048f1ed25a2380f068feff2717238c4fdeed0b1488a58e404c155f9ee5'
BASE_MANIFEST = 'sha256:75dde49255cdb88b789103170b69c68517a7acc6a8523fec3ee0f2174235b84e'
BASE_CONFIG = 'sha256:6c68782818b973d40f4949189d34564d46218a3c78e57b986a826814d579b362'
SIGNAL_ARCHIVE = Path('/srv/work/messenger-signal-runtime-a23fd8e26a72-import1/evidence/signal-image.tar')
SIGNAL_ARCHIVE_SHA = '556ccc992151093869d7d16493ee81a2478415278de9bbbe162be2676cde3312'
SIGNAL_ID = 'sha256:14f0f9454b11cb334dc165abe55c6ac30af896abd2ddb5c2e1ed137a8027f6ba'
SIGNAL_BINARY = 'a5993d2b530c07bcae345674294aa5b7416a785c910ec1566a28c0945f198759'
SIGNAL_TAG = 'wizard-signal-bridge:0.2610.0-native-albums1-a23fd8e26a72'
runs = []


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


def run(name, argv, timeout=300, cwd=ROOT):
    log = OUT / (name + '.log')
    with log.open('x') as f:
        p = subprocess.run(argv, cwd=cwd, stdout=f, stderr=subprocess.STDOUT, timeout=timeout)
    runs.append({'name': name, 'argv': list(map(str, argv)), 'returncode': p.returncode, 'log': str(log), 'log_sha256': sha(log)})
    dump(OUT / 'progress.json', runs)
    assert p.returncode == 0, name + ' failed; retained ' + str(log)
    return log.read_text()


def archive_identity(path):
    """Verify every blob byte, one typed root, exact config and ordered layer descriptors."""
    with tarfile.open(path) as t:
        for m in t.getmembers():
            if m.isfile() and m.name.startswith('blobs/sha256/'):
                h = hashlib.sha256()
                with t.extractfile(m) as f:
                    for b in iter(lambda: f.read(1024 * 1024), b''):
                        h.update(b)
                assert h.hexdigest() == m.name.rsplit('/', 1)[1], 'archive blob corrupt: ' + m.name
        index = json.load(t.extractfile('index.json'))
        assert len(index['manifests']) == 1, 'single-image reachable root required'
        root = index['manifests'][0]
        body = json.load(t.extractfile('blobs/' + root['digest'].replace(':', '/')))
        assert 'config' in body and 'layers' in body
        config = json.load(t.extractfile('blobs/' + body['config']['digest'].replace(':', '/')))
        assert len(body['layers']) == len(config['rootfs']['diff_ids'])
        return {'manifest_digest': root['digest'], 'config_digest': body['config']['digest'], 'raw_config': config}


def inspect(ref):
    return json.loads(subprocess.check_output(['docker', 'image', 'inspect', ref]))[0]


def main():
    assert str(S).startswith('/srv/work/messenger-signal-only-'), 'forum immutable stage only'
    assert len(sys.argv) == 2 and sha(S / 'stage-manifest.json') == sys.argv[1]
    manifest = json.loads((S / 'stage-manifest.json').read_text())
    for rel, h in manifest['files'].items():
        assert sha(S / rel) == h, 'staged input drift: ' + rel
    assert not OUT.exists(), 'fresh evidence only'
    OUT.mkdir()
    revision = manifest['revision']
    assert (ROOT / 'REVISION').read_text().strip() == revision
    # The three overlay paths must be byte-identical to the QA-verified a23fd8e files.
    for rel in PATHS[:2]:
        assert sha(S / 'verified' / rel) == sha(ROOT / rel), 'overlay differs from verified file ' + rel
    # --- frozen Signal image: identity + binary, no network/mounts ---
    assert sha(SIGNAL_ARCHIVE) == SIGNAL_ARCHIVE_SHA, 'Signal archive drift'
    sig = archive_identity(SIGNAL_ARCHIVE)
    run('load-signal', ['docker', 'load', '-i', str(SIGNAL_ARCHIVE)])
    signal = inspect(SIGNAL_ID)
    assert signal['Id'] in (sig['manifest_digest'], sig['config_digest']) and signal['Architecture'] == 'amd64'
    digest = run('signal-binary-hash', ['docker', 'run', '--rm', '--network=none', '--read-only', '--cap-drop=ALL', '--entrypoint=sha256sum',
                                          SIGNAL_ID, '/usr/bin/mautrix-signal']).split()[0]
    assert digest == SIGNAL_BINARY, 'Signal binary hash mismatch'
    run('signal-version', ['docker', 'run', '--rm', '--network=none', '--read-only', '--cap-drop=ALL', '--entrypoint=/usr/bin/mautrix-signal',
                           SIGNAL_ID, '--version'])
    # --- exact live Messenger base ---
    assert sha(BASE_ARCHIVE) == BASE_ARCHIVE_SHA, 'base archive drift'
    frozen = archive_identity(BASE_ARCHIVE)
    assert frozen['manifest_digest'] == BASE_MANIFEST and frozen['config_digest'] == BASE_CONFIG
    run('load-base', ['docker', 'load', '-i', str(BASE_ARCHIVE)], timeout=240)
    base = inspect('wizard-messenger:0.2.0-unified.15.14')
    assert base['Id'] in (BASE_MANIFEST, BASE_CONFIG) and base['Config']['Labels']['org.opencontainers.image.revision'] == LIVE
    assert base['RootFS']['Layers'] == frozen['raw_config']['rootfs']['diff_ids']
    tag = 'wizard-messenger:signal-albums-' + revision[:12]
    run('build-overlay', ['docker', 'build', '--network=none', '--pull=false', '--build-arg', 'BASE=' + base['Id'],
                         '--build-arg', 'REVISION=' + revision, '-f', 'release/signal-only.Dockerfile', '-t', tag, '.'])
    candidate = inspect(tag)
    expected = json.loads(json.dumps(base['Config']))
    expected['Labels']['org.opencontainers.image.revision'] = revision
    assert candidate['Config'] == expected, 'unexpected full Config change'
    assert candidate['RootFS']['Layers'][:-1] == base['RootFS']['Layers'] and len(candidate['RootFS']['Layers']) == len(base['RootFS']['Layers']) + 1
    script = 'import pathlib,hashlib,json;print(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in pathlib.Path("/app").rglob("*") if p.is_file()}))'
    trees = {}
    for key, image in [('base', base), ('candidate', candidate)]:
        text = run('image-files-' + key, ['docker', 'run', '--rm', '--network=none', '--read-only', '--cap-drop=ALL', '--security-opt=no-new-privileges',
                                          '--user=1000:1000', '--entrypoint=python3', image['Id'], '-c', script])
        trees[key] = json.loads(text)
    changed = {p for p in set(trees['base']) | set(trees['candidate']) if trees['base'].get(p) != trees['candidate'].get(p)}
    assert changed == {'/app/' + p for p in PATHS}, sorted(changed)
    for rel in PATHS:
        assert trees['base']['/app/' + rel] == sha(S / 'baseline' / rel), 'base image differs from live source ' + rel
        assert trees['candidate']['/app/' + rel] == sha(ROOT / rel)
    archive = OUT / 'messenger-signal-albums-image.tar'
    run('export-overlay-image', ['docker', 'save', '-o', str(archive), tag], timeout=240)
    proof = archive_identity(archive)
    assert candidate['Id'] in (proof['manifest_digest'], proof['config_digest']), 'unqualified loaded ID'
    assert proof['raw_config']['config']['Labels'] == candidate['Config']['Labels'] and proof['raw_config']['rootfs']['diff_ids'] == candidate['RootFS']['Layers']
    dump(OUT / 'image-identity.json', {
        'archive_path': str(archive), 'archive_sha256': sha(archive), 'base_archive_sha256': BASE_ARCHIVE_SHA, 'base_manifest_digest': BASE_MANIFEST,
        'base_config_digest': BASE_CONFIG, 'loaded_id': candidate['Id'], 'tag': tag, 'manifest_digest': proof['manifest_digest'],
        'config_digest': proof['config_digest'], 'config': candidate['Config'], 'rootfs': candidate['RootFS'], 'changed_app_files': sorted(changed)})
    for rel, h in manifest['files'].items():
        assert sha(S / rel) == h, 'post-run input drift: ' + rel
    dump(OUT / 'qa-receipt.json', {
        'scoped_qa_pass': True, 'revision': revision, 'verified_source_revision': VERIFIED, 'live_base_revision': LIVE,
        'source_manifest_sha256': sys.argv[1], 'runner_sha256': sha(Path(__file__)), 'native_builds': 0, 'browser_matrix_reruns': 0,
        'activation_performed': False, 'image_identity_sha256': sha(OUT / 'image-identity.json'),
        'overlay_files': {p: sha(ROOT / p) for p in PATHS},
        'signal': {'image_id': SIGNAL_ID, 'binary_sha256': SIGNAL_BINARY, 'archive_sha256': SIGNAL_ARCHIVE_SHA, 'tag': SIGNAL_TAG},
        'runs': runs,
        'remaining': ['parent fresh live/service/recipe/pin check', 'parent visual review of retained screenshots', 'parent authorized lifecycle only']})


if __name__ == '__main__':
    try:
        main()
    except BaseException as exc:
        if OUT.exists():
            dump(OUT / 'failure.json', {'error': repr(exc), 'runs': runs})
        raise
