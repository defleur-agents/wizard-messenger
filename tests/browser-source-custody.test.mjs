import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url), custody=require('./browser_source_custody.cjs');
function fixture(mode='correct') {
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'custody-')), out=path.join(root,'evidence'); fs.mkdirSync(out);
  let listener; const page={on:(event,fn)=>{assert.equal(event,'response');listener=fn;}};
  const check=custody(page,root,out,'unit');
  for (const name of ['app.js','unified.js']) {
    fs.writeFileSync(path.join(root,name),'// exact '+name);
    listener({url:()=>`https://messenger.test/${name}`,status:()=>200,
      request:()=>({resourceType:()=>mode==='fetch'?'fetch':'script'}),
      body:async()=>Buffer.from(mode==='wrong'?'// wrong':'// exact '+name)});
  }
  if (mode==='correct') listener({url:()=>'https://messenger.test/wizard-os-home/core/app-client.js',status:()=>404,request:()=>({resourceType:()=>'script'}),body:async()=>Buffer.alloc(0)});
  return {check,root,out};
}
for (const mode of ['correct','wrong','fetch']) test('served source custody '+mode,async()=>{
  const f=fixture(mode);
  try {if(mode==='correct') {await f.check();const p=JSON.parse(fs.readFileSync(path.join(f.out,'served-source-unit.json')));assert.equal(p.rows.length,3);assert.ok(p.rows.some(x=>x.scope==='synthetic-platform-fixture'&&x.status===404));assert.deepEqual(p.errors,[]);}
    else await assert.rejects(f.check(),mode==='wrong'?/custody mismatch/:/actual script response/);
  } finally {fs.rmSync(f.root,{recursive:true,force:true});}
});
