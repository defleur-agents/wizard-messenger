"""Bounded acceptance resource fence, called by the existing delivery controller.
No deletion, daemon, VM or queue admission. The parent supplies the sealed budget.
"""
from pathlib import Path
import fcntl, json, os, shutil, subprocess


def resource_sample(root, phase, plan, initial):
    root = Path(root)
    # du does not dereference the independently verified shared image/tool links.
    used = int(subprocess.check_output(['sudo', '-n', 'du', '-s', '-B1', str(root)], text=True).split()[0])
    free = shutil.disk_usage(root).free
    growth = max(0, used - initial['used_bytes'])
    remaining = max(0, plan['incremental_peak_bytes'] - growth)
    required = plan['reserve_floor_bytes'] + plan['concurrent_runtime_allowance_bytes'] + remaining
    row = dict(phase=phase, free_bytes=free, owned_bytes=used, owned_growth_bytes=growth,
               remaining_budget_bytes=remaining, required_free_bytes=required)
    if growth > plan['incremental_peak_bytes'] or free < required:
        raise RuntimeError('resource fence: '+json.dumps(row, sort_keys=True))
    return row


def acquire_resource_locks(plan):
    if os.environ.get('WIZARD_WORKER_LANE') != 'heavy':
        raise RuntimeError('full acceptance requires parent-admitted heavy lane')
    inherited = int(os.environ['WIZARD_HEAVY_LOCK_FD'])
    got, want = os.fstat(inherited), Path(plan['heavy_lock']).stat()
    if (got.st_dev, got.st_ino) != (want.st_dev, want.st_ino):
        raise RuntimeError('wrong inherited worker lock')
    # Same open-file description, never reopen and deadlock on our own lock.
    fcntl.flock(inherited, fcntl.LOCK_EX | fcntl.LOCK_NB)
    fd = os.open(plan['light_lock'], os.O_RDWR | os.O_NOFOLLOW)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Retained/manual VM writers are not excluded by the worker lease.
        writers=[]
        for proc in Path('/proc').glob('[0-9]*'):
            try:
                if (proc/'comm').read_text().strip().startswith('qemu-system-'):
                    writers.append(int(proc.name))
            except FileNotFoundError:
                pass
        if writers:
            raise RuntimeError('unbounded retained VM writer present; parent resource reconciliation required')
    except BaseException:
        os.close(fd)
        raise
    return fd
