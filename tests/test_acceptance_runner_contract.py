"""Focused runner contract selfchecks; no namespaces, suite, browser or workload execution."""
import ast
from pathlib import Path
import unittest
from typing import Any
SOURCE = Path(__file__).resolve().parents[1] / 'ops/acceptance/forum_apps_acceptance.py'
class RunnerContracts(unittest.TestCase):
    def functions(self):
        tree=ast.parse(SOURCE.read_text())
        wanted: list[ast.stmt]=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['isolated','path_preflight']]
        ctx: dict[str,Any]={'Path':Path}; exec(compile(ast.Module(body=wanted,type_ignores=[]),str(SOURCE),'exec'),ctx)
        return ctx
    def test_socket_budget_accepts_short_and_rejects_prior_long_root(self):
        f=self.functions()['path_preflight']
        self.assertLess(f('/srv/work/mmr2-20261105')['max_socket_path_bytes'],108)
        with self.assertRaisesRegex(AssertionError,'AF_UNIX'):
            f('/srv/work/approved-messenger-acceptance-aaeff1c-r1-20261105')
    def test_mount_and_nonroot_app_mapping_are_mandatory(self):
        argv=self.functions()['isolated'](['python3','sentinel'])
        for flag in ['--mount','--net','--pid','--kill-child=KILL']: self.assertIn(flag,argv)
        shell=argv[-4]
        self.assertIn('mount -t tmpfs',shell); self.assertIn('tmpfs /run',shell)
        self.assertIn('--map-user=1000 --map-group=1000',shell)
        self.assertEqual(argv[-2:],['python3','sentinel'])
    def test_no_chown_or_host_install_escape(self):
        text=SOURCE.read_text()
        self.assertNotIn('sudo',text.replace('# Authenticated download only; no host install/update/sudo. Pins from forum APT policy.',''))
        self.assertIn("['apt-get','download'",text)
        self.assertEqual(text.count("'apt-get'"),1)
        self.assertNotIn("'dpkg','-i'",text)
        self.assertNotIn("'apt-get','install'",text)
        self.assertIn("before==digest(Path('/var/lib/dpkg/status'))",text)
        self.assertIn("assert not counts[label]['skipped']",text)
if __name__=='__main__': unittest.main()
