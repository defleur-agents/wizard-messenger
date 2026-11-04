"""Private, bounded original-take custody. Never a send receipt or capture ack."""
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import stat
import threading
from engine import EngineError

MAX_BYTES = 25 * 1048576
BUDGET = 250 * 1048576
_LOCK = threading.Lock()


@contextmanager
def _directory(root, create=False):
    root = Path(root)
    parent = os.open(root.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        if create:
            try:
                os.mkdir(root.name, 0o700, dir_fd=parent)
                os.fsync(parent)
            except FileExistsError:
                pass
        fd = os.open(root.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        try:
            os.fchmod(fd, 0o700)
            yield fd
        finally:
            os.close(fd)
    finally:
        os.close(parent)


def _read(fd, name, limit):
    if not re.fullmatch(r'[a-f0-9]{64}\.(?:blob|json)', name):
        raise EngineError('not_found', 'No such recording', 404)
    # Resolve the identifier against local archive entries; never pass request-derived text as a path.
    entry = next((entry for entry in os.listdir(fd) if entry == name), None)
    if entry is None:
        raise FileNotFoundError()
    f = os.open(entry, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    with os.fdopen(f, 'rb') as source:
        info = os.fstat(f)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > limit:
            raise EngineError('archive_corrupt', 'Recording readback failed', 500)
        os.fchmod(f, 0o600)
        data = source.read(limit + 1)
        if len(data) > limit:
            raise EngineError('archive_corrupt', 'Recording readback failed', 500)
        return data


def _write(fd, name, content):
    temporary = '.partial-' + secrets.token_hex(16)
    f = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
    try:
        with os.fdopen(f, 'wb') as target:
            os.fchmod(f, 0o600)
            target.write(content)
            target.flush()
            os.fsync(f)
        os.replace(temporary, name, src_dir_fd=fd, dst_dir_fd=fd)
        os.fsync(fd)
    finally:
        try:
            os.unlink(temporary, dir_fd=fd)
        except FileNotFoundError:
            pass


def archive(root, data, metadata):
    if not 0 < len(data) <= MAX_BYTES:
        raise EngineError('too_large', 'Recording exceeds 25 MB', 413)
    if set(metadata) != {'take', 'duration', 'mime', 'size'}:
        raise EngineError('invalid_input', 'Invalid recording metadata', 400)
    take, mime = metadata['take'], metadata['mime']
    try:
        duration = float(metadata['duration'])
        size = int(metadata['size'])
    except (ValueError, TypeError):
        raise EngineError('invalid_input', 'Invalid recording metadata', 400) from None
    if not isinstance(take, str) or not 1 <= len(take) <= 160 or not isinstance(mime, str) or len(mime) > 160 or not math.isfinite(duration) or not 0 <= duration <= 86400000 or size != len(data):
        raise EngineError('invalid_input', 'Invalid recording metadata', 400)
    manifest = dict(take=take, duration=duration, mime=mime, size=len(data), sha256=hashlib.sha256(data).hexdigest(), head_hex=data[:32].hex())
    encoded = json.dumps(manifest, sort_keys=True).encode()
    key = hashlib.sha256(encoded).hexdigest()
    try:
        with _LOCK, _directory(root, create=True) as fd:
            try:
                existing = _read(fd, key + '.json', 4096)
            except FileNotFoundError:
                existing = None
            if existing is not None:
                if existing != encoded or _read(fd, key + '.blob', MAX_BYTES) != data:
                    raise EngineError('archive_corrupt', 'Recording readback failed', 500)
            else:
                try:
                    orphan = _read(fd, key + '.blob', MAX_BYTES)
                except FileNotFoundError:
                    orphan = None
                if orphan is not None and orphan != data:
                    raise EngineError('archive_corrupt', 'Recording readback failed', 500)
                used, entries = 0, {}
                for name in os.listdir(fd):
                    info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                        raise EngineError('archive_corrupt', 'Recording archive unavailable. Use Save recording.', 500)
                    used += info.st_size
                    match = re.fullmatch(r'([a-f0-9]{64})\.(?:blob|json)', name)
                    if match and match.group(1) != key:
                        entry = entries.setdefault(match.group(1), [info.st_mtime, 0, []])
                        entry[0] = min(entry[0], info.st_mtime)
                        entry[1] += info.st_size
                        entry[2].append(name)
                needed = (len(data) if orphan is None else 0) + len(encoded)
                # A bounded rolling buffer: the newest take matters most, so the
                # oldest takes give way instead of every later voice note failing.
                for _, size, names in sorted(entries.values()):
                    if used + needed <= BUDGET:
                        break
                    for name in sorted(names, key=lambda n: not n.endswith('.json')):  # commit marker first
                        os.unlink(name, dir_fd=fd)
                    os.fsync(fd)
                    used -= size
                if used + needed > BUDGET:
                    raise EngineError('archive_full', 'Recording archive is full. Save recording instead.', 507)
                if orphan is None:
                    _write(fd, key + '.blob', data)
                _write(fd, key + '.json', encoded)  # commit marker published last
    except OSError:
        raise EngineError('archive_unavailable', 'Could not keep original recording. Use Save recording.', 503) from None
    return dict(manifest, id=key)


def readback(root, key):
    if not re.fullmatch(r'[a-f0-9]{64}', key):
        raise EngineError('not_found', 'No such recording', 404)
    try:
        with _LOCK, _directory(root) as fd:
            data = _read(fd, key + '.blob', MAX_BYTES)
            manifest = json.loads(_read(fd, key + '.json', 4096))
        if len(data) != manifest['size'] or hashlib.sha256(data).hexdigest() != manifest['sha256']:
            raise EngineError('archive_corrupt', 'Recording readback failed', 500)
    except FileNotFoundError:
        raise EngineError('not_found', 'No such recording', 404) from None
    except (OSError, ValueError, KeyError, TypeError):
        raise EngineError('archive_corrupt', 'Recording readback failed', 500) from None
    return data
