'use strict';
// Native node:test events; preserve assertion causes, not timing-dependent TAP text.
const util = require('node:util');
function errorRecord(error) {
  if (!error) return null;
  const result = {};
  for (const key of ['name','message','code','failureType','operator','stack'])
    if (error[key] !== undefined) result[key] = String(error[key]);
  for (const key of ['actual','expected']) if (key in error)
    result[key] = util.inspect(error[key], {depth:12, sorted:true, breakLength:Infinity});
  if (error.cause) result.cause = errorRecord(error.cause);
  return result;
}
module.exports = async function* (events) {
  for await (const event of events) {
    if (!['test:pass','test:fail','test:summary'].includes(event.type)) continue;
    const data = event.data;
    yield JSON.stringify({type:event.type,name:data.name,file:data.file,line:data.line,column:data.column,
      nesting:data.nesting,skip:data.skip||false,todo:data.todo||false,
      details:{...data.details,error:errorRecord(data.details?.error)},
      ...(event.type==='test:summary'?{counts:data.counts}:{} )})+'\n';
  }
};
