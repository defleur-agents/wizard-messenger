import fcntl
import importlib.util
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

spec=importlib.util.spec_from_file_location('delivery_resources',Path(__file__).with_name('resource_guard.py'))
g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)


def test_wrong_lane_fails_before_locks(monkeypatch):
    monkeypatch.setenv('WIZARD_WORKER_LANE','light')
    with pytest.raises(RuntimeError,match='heavy lane'):g.acquire_resource_locks({})


def test_inherited_lock_identity_and_light_contention(tmp_path,monkeypatch):
    heavy=tmp_path/'worker.lock';light=tmp_path/'packaging.lock'
    heavy.touch();light.touch()
    fd=os.open(heavy,os.O_RDWR);other=os.open(light,os.O_RDWR)
    monkeypatch.setenv('WIZARD_WORKER_LANE','heavy');monkeypatch.setenv('WIZARD_HEAVY_LOCK_FD',str(fd))
    plan={'heavy_lock':str(heavy),'light_lock':str(light)}
    try:
        with patch.object(g.Path,'glob',return_value=[]):
            acquired=g.acquire_resource_locks(plan);os.close(acquired)
            fcntl.flock(other,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with pytest.raises(BlockingIOError):g.acquire_resource_locks(plan)
        fcntl.flock(other,fcntl.LOCK_UN)
        plan['heavy_lock']=str(light)
        with pytest.raises(RuntimeError,match='wrong inherited'):g.acquire_resource_locks(plan)
    finally:os.close(fd);os.close(other)


@pytest.mark.parametrize('free,growth,passes',[(1300,0,True),(1199,0,False),(1100,200,True),(1300,301,False)])
def test_phase_budget_preserves_reserve_and_foreign_allowance(tmp_path,free,growth,passes):
    from types import SimpleNamespace
    plan={'incremental_peak_bytes':300,'reserve_floor_bytes':800,'concurrent_runtime_allowance_bytes':100}
    initial={'used_bytes':1000}
    with patch.object(g.subprocess,'check_output',return_value=f'{1000+growth} root\n'),patch.object(g.shutil,'disk_usage',return_value=SimpleNamespace(free=free)):
        if passes:assert g.resource_sample(tmp_path,'phase',plan,initial)['remaining_budget_bytes']==300-growth
        else:
            with pytest.raises(RuntimeError,match='resource fence'):g.resource_sample(tmp_path,'phase',plan,initial)
