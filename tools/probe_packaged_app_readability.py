"""Executed only in admitted, networkless packaged containers as uid/gid 1000.
Read the whole actual /app tree; retain directory metadata to compare with base.
The preserved broken package must fail on the untouched /app/static/app.js.
"""
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

assert os.getuid() == 1000 and os.getgid() == 1000
if sys.argv[1:] == ['--expect-permission-error']:
    try:
        Path('/app/static/app.js').read_bytes()
    except PermissionError as exc:
        print(json.dumps({'expected_failure': 'PermissionError', 'path': exc.filename}))
    else:
        raise AssertionError('preserved recursive-COPY package unexpectedly readable')
else:
    assert not sys.argv[1:]
    # Explicit sentinel read: rglob can silently omit non-traversable subtrees.
    Path('/app/static/app.js').read_bytes()
    files, directories, modes = {}, {}, {}
    for p in [Path('/app'), *Path('/app').rglob('*')]:
        meta = p.stat()
        if stat.S_ISDIR(meta.st_mode):
            assert os.access(p, os.R_OK | os.X_OK), str(p)
            directories[str(p)] = [stat.S_IMODE(meta.st_mode), meta.st_uid, meta.st_gid]
        elif stat.S_ISREG(meta.st_mode):
            files[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
            modes[str(p)] = stat.S_IMODE(meta.st_mode)
    print(json.dumps({'files': files, 'directories': directories, 'file_modes': modes}))
