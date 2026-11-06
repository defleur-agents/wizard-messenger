import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
// Execute the actual settings renderer against synthetic agent-access state.
const source=readFileSync(process.env.MESSENGER_NOTICE_SOURCE || new URL('../static/unified.js',import.meta.url),'utf8');
const body=source.slice(source.indexOf('    const sync = () => {',source.indexOf('  function moreSettings(sheet)')),source.indexOf("    api('api/view/agents').then",source.indexOf('  function moreSettings(sheet)')));
function render(state){
 const el=()=>({children:[],hidden:false,replaceChildren(){this.children=[];},append(...children){this.children.push(...children);}});
 const agents=el(),head=el(),group=el(),requests=[];
 const context=vm.createContext({agents,head,group,node:(tag,className,text)=>({tag,className,text}),levelRow:(agent,label,levels,save,options)=>({agent,label,levels,save,options}),api:(...args)=>{requests.push(args);return Promise.resolve(state);}});
 vm.runInContext(body+'\nglobalThis.paint=paintAgents;',context);context.paint(state);return {agents,head,group,requests};
}
test('disconnected gateway shows no fault/blame/access invitation and hides empty wrappers',()=>{
 const f=render({gateway_connected:false,wizard_agents:[],wizard_levels:[]});
 assert.deepEqual(f.agents.children,[]);assert.equal(f.agents.hidden,true);assert.equal(f.head.hidden,true);assert.equal(f.group.hidden,true);assert.deepEqual(f.requests,[]);
 assert.doesNotMatch(source,/Your agents can[’'\\]*t reach Messenger yet|Ask your Wizard to finish connecting it/);
});
test('notice removal leaves no-access default, legitimate controls and owner-only save unchanged',async()=>{
 const state={gateway_connected:false,wizard_agents:[{id:'synthetic',label:'Synthetic Wizard',level:'no_access'}],wizard_levels:[{id:'no_access',label:'No access'},{id:'read_only',label:'Read-only'},{id:'draft_only',label:'Draft-only'}]};
 const before=JSON.stringify(state),f=render(state);assert.equal(f.agents.hidden,false);assert.equal(f.head.hidden,false);
 assert.equal(f.agents.children.length,1);const row=f.agents.children[0];assert.equal(row.agent.level,'no_access');assert.deepEqual(row.levels,state.wizard_levels);assert.deepEqual(f.requests,[]);assert.equal(JSON.stringify(state),before);
 await row.save('read_only');assert.deepEqual(JSON.parse(JSON.stringify(f.requests)),[['api/view/agents/wizard/synthetic',{method:'POST',body:{level:'read_only'}}],['api/view/agents']]);
 assert.equal(state.wizard_agents[0].level,'no_access','renderer never grants access by itself');
});
