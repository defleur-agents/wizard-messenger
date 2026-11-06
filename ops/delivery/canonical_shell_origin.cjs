'use strict';
// Actual installed shell tree + actual packaged static bytes. No API forwarding, owner-state writes or streams.
const http=require('node:http'),fs=require('node:fs'),path=require('node:path');
const arg=n=>process.argv[process.argv.indexOf('--'+n)+1],WEB=path.resolve(arg('web')),STATIC=path.resolve(arg('static')),PORT=Number(arg('port'));
const PIN=process.env.MESSENGER_PUBLIC_PIN_DIR&&path.resolve(process.env.MESSENGER_PUBLIC_PIN_DIR);
const log={unknownReads:[],refusedWrites:[],refusedStreams:[],served:{}};
const apps={apps:[{id:'messenger',name:'Messenger',type:'service',category:'app',source:'apps.json',url:'/messenger/',view:{mode:'original',url:'/messenger/'},desc:'Synthetic installed Messenger fixture'}],in_development:[]};
const catalogue={
 '/wizard/v1/bootstrap':{bootstrap:1,settings:{owner:{name:'Synthetic Owner'},agent:{name:'Wizard'},clock:{timezone:'UTC'}},capabilities:{},endpoints:{apps:'/wizard/v1/apps'}},
 '/wizard/v1/apps':apps,'/wizard/hermes/api/sessions':{data:[],has_more:false},
 '/wizard/v1/ui-preferences':{pinnedChats:[],spaces:[],readyOrder:'newest',subjectOrder:[],migrations:{'launcher.v1':true}},'/wizard/v1/app-logos':{},
};
const TYPES={'.js':'application/javascript','.css':'text/css','.html':'text/html','.svg':'image/svg+xml','.png':'image/png','.webp':'image/webp','.jpg':'image/jpeg','.woff2':'font/woff2','.json':'application/json','.ico':'image/x-icon','.webmanifest':'application/manifest+json'};
const j=(res,status,x)=>{res.writeHead(status,{'content-type':'application/json','cache-control':'no-store'});res.end(JSON.stringify(x));};
http.createServer((req,res)=>{
 const u=new URL(req.url,'http://fixture');
 if(u.pathname==='/__qa/log')return j(res,200,log);
 if(req.method!=='GET'&&req.method!=='HEAD'){log.refusedWrites.push(req.method+' '+u.pathname);return j(res,403,{error:'all fixture-server writes refused'});}
 if(/events|stream|\/updates$/.test(u.pathname)){log.refusedStreams.push(u.pathname);return j(res,403,{error:'owner streams refused'});}
 if(Object.hasOwn(catalogue,u.pathname))return j(res,200,catalogue[u.pathname]);
 let root,rel;
 if(u.pathname.startsWith('/messenger/')){root=STATIC;rel=u.pathname.slice(11)||'index.html';}
 else if(u.pathname.startsWith('/wizard-os-home/')){root=WEB;rel=u.pathname.slice(16)||'index.html';}
 else {log.unknownReads.push(u.pathname);return j(res,404,{});}
 if(root===STATIC&&PIN&&['index.html','app.js','app.css'].includes(rel))root=PIN;
 rel=decodeURIComponent(rel);if(rel.includes('..')||rel.split('/').some(s=>s.startsWith('.')))return j(res,404,{});
 const f=path.join(root,rel);
 if(!fs.existsSync(f)||!fs.statSync(f).isFile()){
  if(root===WEB&&/^(data|summaries)\.js$/.test(rel)){res.writeHead(200,{'content-type':'application/javascript'});return res.end(rel==='data.js'?'window.WIZ_DATA={threads:[],projects:{}};':'window.WIZ_SUMMARIES={};');}
  log.unknownReads.push(u.pathname);return j(res,404,{});
 }
 log.served[u.pathname]=(log.served[u.pathname]||0)+1;
 res.writeHead(200,{'content-type':TYPES[path.extname(f)]||'application/octet-stream','cache-control':'no-store'});fs.createReadStream(f).pipe(res);
}).listen(PORT,'127.0.0.1',()=>console.log(JSON.stringify({origin:'http://127.0.0.1:'+PORT,web:WEB,static:STATIC,syntheticBackend:true,realShellAndSDK:true})));
