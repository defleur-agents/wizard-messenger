// Synthetic-only route contract shared by browser QA and its browser-free boot replay.
const assert = require('node:assert/strict');
const {encodePublic} = require('../../static/app.js');
const {parseMentions} = require('../../static/unified.js');
const origin = 'https://messenger.test';
function createFixture() {
  const alice={id:'@telegram_101:messenger.internal',name:'Alice Example',label:'Alice Example',identity_id:'synthetic-id'}, bob={id:'@telegram_102:messenger.internal',name:'Bob Example',label:'Bob Example',identity_id:'synthetic-id'};
  const msg={id:'matrix:$synthetic',person_id:'synthetic-group',network:'telegram',identity_id:'synthetic-id',outgoing:false,timestamp:Date.now()-10000,msgtype:'m.text',original:'Welcome @Owner Example',mentions:[{id:'@owner:messenger.internal',name:'Owner Example',start:8,end:22}],mentioned:true,sender:'Alice Example',reactions:[{key:'👍',count:2,mine:false,identities_complete:true,reactors:[alice,bob]},{key:'❤️',count:1,mine:false,identities_complete:true,reactors:[bob]}],deleted:false,media:null};
  const person={id:'synthetic-group',kind:'group',display_name:'Synthetic test group',unread:1,unread_mentions:1,language:'en',translation_enabled:false,labels:[],identities:[{id:'synthetic-id',network:'telegram',address:'!synthetic',label:'Synthetic test group',kind:'group'}],preferred_identity:'synthetic-id',members:[alice,bob],last:{text:msg.original,timestamp:msg.timestamp,outgoing:false,msgtype:'m.text'}};
  const sent=[], key='11'.repeat(32); let draft=null;
  const routes={
    '/api/view/trusted-owner':{enabled:false},
    '/api/view/session':{authenticated:true,csrf_token:'synthetic'},
    '/api/view/passkey':{enabled:false},
    '/api/status':{state:'ready',account_configured:true},
    '/api/identity':{identity:{account_id:key,npub:encodePublic(key),display_name:'Synthetic Owner'}},
    '/api/contacts':{contacts:[]}, '/api/invites':{invites:[]}, '/api/dms':{dms:[]},
    '/api/unified/people':{people:[],seq:1},
    '/api/unified/groups':{groups:[person],seq:1},
    '/api/unified/qr-codes':{codes:[]},
    '/api/unified/directory':{people:[],groups:[person]},
    '/api/unified/updates':{seq:1,messages:{},people:[],typing:{},removed:[]},
    '/api/unified/people/synthetic-group':{person,messages:[msg],typing:[],has_more:false,next_cursor:null},
    '/api/unified/people/synthetic-group/read':{ok:true},
    '/api/unified/people/synthetic-group/typing':{ok:true},
  };
  function reply(url,method='GET',body) {
    const u=new URL(url,origin), p=u.pathname.replace(/^\/app\//,'/');
    // Contacts is a separate public app contract: no Messenger envelope.
    if(p==='/contacts/api/contacts') return {contacts:[]};
    const draftPath=p.match(/^\/api\/drafts(?:\/(synthetic-draft))?$/);
    if(draftPath) {
      if(method==='GET') return {ok:true,result:draftPath[1]?{draft}:{drafts:draft?[draft]:[]}};
      if(method==='DELETE') {draft=null;return {ok:true,result:{cleared:true}};}
      assert.equal(method,'POST');draft={...draft,...body,id:'synthetic-draft',state:'draft',revision:(draft?.revision||0)+1,attachments:[],updated_at:Date.now()};
      return {ok:true,result:{draft}};
    }
    if(p==='/api/unified/people/synthetic-group/send'&&method==='POST') {
      const m={...msg,id:'matrix:$sent'+sent.length,outgoing:true,timestamp:Date.now(),original:body.text,mentioned:false,mentions:parseMentions(body.text,[alice,bob]),reactions:[],client_id:body.client_id}; sent.push(m);
      return {ok:true,result:{message:m,seq:2}};
    }
    if(!(p in routes)) return null; // Fail closed; never hide a new boot prerequisite behind {}.
    assert(method==='GET'||(method==='POST'&&/\/(read|typing)$/.test(p)),method+' '+p);
    if(p==='/api/unified/people/synthetic-group') {
      assert(!u.searchParams.has('cursor')); assert(['60',null].includes(u.searchParams.get('limit')));
      return {ok:true,result:{...routes[p],messages:[msg,...sent]}};
    }
    return {ok:true,result:routes[p]};
  }
  return {reply,person,msg,routes};
}
module.exports={origin,createFixture};
