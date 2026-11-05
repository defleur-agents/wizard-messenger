// Preserve exact semantic failure identities without unstable absolute stacks/timings.
const path=require('node:path');
const error=e=>e?{name:e.name,message:e.message,code:e.code,failureType:e.failureType,operator:e.operator,expected:e.expected,actual:e.actual,cause:error(e.cause)}:null;
module.exports=async function*(source){for await(const event of source){if(['test:pass','test:fail'].includes(event.type)){const d=event.data;yield JSON.stringify({type:event.type,name:d.name,file:path.basename(d.file||''),skip:d.skip||false,todo:d.todo||false,error:error(d.details?.error)})+'\n';}else if(event.type==='test:diagnostic')yield JSON.stringify({type:event.type,message:event.data.message})+'\n';}};
