"""Strict frozen-archive identity plus observed classic-Docker serializer expansion.
No field filtering: add only exact defaults absent from raw Config, compare the
ENTIRE resulting Config, typed image identity and ordered full RootFS.
"""
import copy
import hashlib
import json
import re
import subprocess
import tarfile

# Measured on forum for frozen live archive 1a2e3e04...; Cmd/Volumes null
# were the two demonstrated omissions in the previous runner's allowlist.
OBSERVED_EXPANSIONS = {'Hostname': '', 'Domainname': '', 'AttachStdin': False,
    'AttachStdout': False, 'AttachStderr': False, 'Tty': False, 'OpenStdin': False,
    'StdinOnce': False, 'Image': '', 'OnBuild': None, 'Cmd': None, 'Volumes': None,
    # Independently observed on the frozen native Signal archive, not guessed.
    'User': '', 'Entrypoint': None}


def exact(a, b):
    # bool and number are distinct JSON values (Python False == 0 is too weak).
    return json.dumps(a, sort_keys=True, separators=(',', ':')) == json.dumps(b, sort_keys=True, separators=(',', ':'))


def archive_identity(path):
    with tarfile.open(path) as t:
        def fileobj(name):
            f = t.extractfile(name)
            assert f is not None, 'non-file archive member: ' + str(name)
            return f
        members = t.getmembers()
        assert len({m.name for m in members}) == len(members), 'duplicate archive member'
        for m in members:
            if m.isfile() and m.name.startswith('blobs/sha256/'):
                h = hashlib.sha256()
                with fileobj(m) as f:
                    for b in iter(lambda: f.read(1024 * 1024), b''): h.update(b)
                assert h.hexdigest() == m.name.rsplit('/', 1)[1], 'archive blob corrupt: ' + m.name
        def descriptor(d):
            assert re.fullmatch(r'sha256:[0-9a-f]{64}', d['digest'])
            p = 'blobs/' + d['digest'].replace(':', '/')
            assert t.getmember(p).isfile() and t.getmember(p).size == d['size'], 'descriptor size/type drift'
            return p
        index = json.load(fileobj('index.json'))
        assert len(index['manifests']) == 1, 'one reachable image root required'
        root = index['manifests'][0]
        body = json.load(fileobj(descriptor(root)))
        assert 'config' in body and 'layers' in body, 'root is not image manifest'
        cfgpath = descriptor(body['config'])
        raw = json.load(fileobj(cfgpath))
        layerpaths = [descriptor(d) for d in body['layers']]
        assert raw['rootfs']['type'] == 'layers'
        assert len(layerpaths) == len(raw['rootfs']['diff_ids'])
        legacy = json.load(fileobj('manifest.json'))
        assert len(legacy) == 1 and legacy[0]['Config'] == cfgpath
        assert legacy[0]['Layers'] == layerpaths, 'legacy ordered layer reachability drift'
        return {'manifest_digest': root['digest'], 'config_digest': body['config']['digest'],
                'raw_config': raw, 'layer_descriptors': body['layers']}


def check_loaded(info, frozen):
    assert info['Id'] in (frozen['manifest_digest'], frozen['config_digest']), 'unqualified loaded ID'
    expected = copy.deepcopy(frozen['raw_config']['config'])
    extras = set(info['Config']) - set(expected)
    for k in extras:
        assert k in OBSERVED_EXPANSIONS and exact(info['Config'][k], OBSERVED_EXPANSIONS[k]), 'nondefault image Config expansion: ' + k
        expected[k] = OBSERVED_EXPANSIONS[k]
    assert exact(info['Config'], expected), 'full image Config drift'
    assert exact(info['RootFS'], {'Type': 'layers', 'Layers': frozen['raw_config']['rootfs']['diff_ids']}), 'full ordered RootFS drift'
    for key, rawkey in [('Os', 'os'), ('Architecture', 'architecture')]:
        assert info[key] == frozen['raw_config'][rawkey]
    return 'manifest_digest' if info['Id'] == frozen['manifest_digest'] else 'config_digest'


def local_build_argv(base_tag, revision, target, dockerfile):
    assert re.fullmatch(r'wizard-messenger-base:composed-[0-9a-f]{12}', base_tag), 'job-local named base only'
    assert re.fullmatch(r'[0-9a-f]{40}', revision)
    return ['docker', 'buildx', 'build', '--builder=default', '--load', '--network=none', '--pull=false',
            '--build-arg', 'BASE=' + base_tag, '--build-arg', 'REVISION=' + revision,
            '-f', dockerfile, '-t', target, '.']


def assert_local_builder(builder):
    assert builder['Name'] == 'default' and builder['Driver'] == 'docker', 'must share daemon local image store'
    assert len(builder['Nodes']) == 1 and builder['Nodes'][0]['Endpoint'] == 'default'


def inspect(ref):
    return json.loads(subprocess.check_output(['docker', 'image', 'inspect', ref]))[0]
