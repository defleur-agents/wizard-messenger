"""Queue-only synthetic red/green runner. No installed app/data access."""
import json, os, pathlib, subprocess, sys
root=pathlib.Path(__file__).resolve().parents[1]
assert str(root).startswith('/srv/work/')
out=root/'artifacts/avatar-refresh'; out.mkdir(parents=True,exist_ok=True)
env=dict(os.environ,PLAYWRIGHT_MODULE='/srv/work/tt-late-git/node_modules/playwright',SHELL_DIR=str(root/'shell-source'))
# Use the exact pre-fix default branch static assets, not synthetic replacement JS.
red=root/'baseline-static'
results=[]
for label,static in [('red',red),('green',root/'static')]:
    target=out/label;target.mkdir(exist_ok=True)
    runenv=dict(env,STATIC_DIR=str(static))
    p=subprocess.run(['node','tests/avatar_refresh_browser.cjs',str(target)],cwd=root,env=runenv,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=180)
    (target/'console.log').write_text(p.stdout)
    data=json.loads((target/'result.json').read_text()) if (target/'result.json').exists() else None
    results.append(dict(label=label,exit_code=p.returncode,result=data))
    print(label,p.returncode,p.stdout[-3000:],flush=True)
summary=dict(synthetic_only=True,results=results,pass_=results[0]['exit_code']!=0 and results[0]['result'] is not None and any(x['violationCount'] for x in results[0]['result']['results']) and results[1]['exit_code']==0)
(out/'summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
sys.exit(0 if summary['pass_'] else 1)
