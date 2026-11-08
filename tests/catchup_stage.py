"""Usage: AGENT_STAGE_DIR=<dir> python tests/catchup_stage.py <port>, then node tests/catchup_browser.cjs. Same synthetic chats as unread_divider_stage.py plus a fake summarizer
(no network, no Tinfoil): the reply cites the first and last numbered line it was given, and a 1000-line chat Big is added.
Disposable staging for the "N new messages" divider: real ViewServer + real UnifiedInbox store, synthetic chats fed
through the real ingest path, read marks set the way the server keeps them (identity.last_read_ts). No homeserver,
no provider, no real account; `read` POSTs only touch this throw-away store. Writes <dir>/state.json.
Chats: Lena (25 unread after 30 read, taller than any window), Bram (2 unread, fits), Cora (all read),
Dan (150 unread, older than the first page of 60), Family (group, 3 senders, 18 unread), Mia (merged WhatsApp +
Telegram, 12 unread across both accounts), Wizard chat Noor (network messenger, 20 unread)."""
import itertools, json, os, sys, tempfile, time
from unittest.mock import Mock
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'tests'))
OUT = os.environ.get('AGENT_STAGE_DIR', '/home/oscar/.hermes/cache/scratch/unread-stage'); os.makedirs(OUT, exist_ok=True)
os.environ['MESSENGER_COOKIE_SECURE'] = '0'
import test_web as fx
from web import ViewServer
from unified import UnifiedInbox
from drafts import Drafts


class Engine(fx.FakeEngine):
    def __init__(self): super().__init__(); self.ready = True
    def dms(self): return {'dms': []}
    def invites(self): return {'invites': []}
    def messages(self, *a, **k): return {'messages': []}


tmp = tempfile.mkdtemp(dir=OUT)
engine = Engine(); engine.data = tmp
port = int(sys.argv[1]) if len(sys.argv) > 1 else 18961
origin = 'http://127.0.0.1:%d' % port
server = ViewServer(('127.0.0.1', port), engine, fx.TOKEN, [origin])
inbox = UnifiedInbox(tmp, engine); server.unified = inbox
_sent = itertools.count(1)
inbox.mx = Mock(side_effect=lambda *a, **k: {'event_id': '$sent%d' % next(_sent)})
inbox.matrix_token = lambda: 'staged'
server.drafts = Drafts(tmp)
inbox.store.remember_own_names('whatsapp', ['Miguel Ortiz'])
import re as _re
calls = []


def _fake(model, system, user):
    calls.append(model)
    time.sleep(0.4)
    nums = [int(n) for n in _re.findall(r'^\[(\d+)\]', user, _re.M)]
    if system.startswith('You merge') or not nums:
        return json.dumps({'bullets': [{'kind': 'decision', 'text': 'The ferry leaves at nine.', 'refs': [1]}, {'kind': 'said', 'text': 'Several people talked through the trip details.', 'refs': [2]}]})
    return json.dumps({'bullets': [{'kind': 'for_you', 'text': 'Can you bring the charger this time? (asked of you)', 'refs': [nums[-1]]},
                                   {'kind': 'question', 'text': 'Nobody has said who is booking the restaurant yet.', 'refs': [nums[0]]},
                                   {'kind': 'said', 'text': 'Ferry is at nine, be there by half past eight; the restaurant closes at ten.', 'refs': [nums[0], nums[-1]]}]})


inbox.catchup.complete = _fake

now = int(time.time() * 1000)
LINES = ['Are you around later?', 'I found the photos from the weekend', 'The ferry leaves at nine, so we should be there by half past eight',
         'ok', 'Did you see what Sam sent?', 'Let me know when you land', 'haha yes', 'Can you bring the charger this time?',
         'I think the restaurant closes at ten', 'Sounds good to me', 'Running ten minutes late, sorry!', 'Here is the address: Soi 11, second floor']
metas, state = {}, {}


def chat(key, network, room, label, kind='person', names=None):
    ident = inbox.store.identity(network, room, label, kind)
    meta = {'network': network, 'kind': kind, 'label': label, 'names': names or {}}
    with inbox.store.db() as db:
        db.execute('INSERT OR REPLACE INTO room_meta VALUES (?,?)', (room, json.dumps(meta)))
    inbox.rooms[room] = meta; metas[room] = meta
    state[key] = ident['person_id']
    return ident


def run(ident, room, start, rows):
    """rows: (sender or None for own, text); one minute apart starting at `start` minutes ago. Returns timestamps."""
    out = []
    for i, (sender, text) in enumerate(rows):
        ts = now - (start - i) * 60000
        event = {'event_id': '$%s-%d-%d' % (room.strip('!'), start, i), 'type': 'm.room.message', 'origin_server_ts': ts,
                 'sender': sender or '@owner:messenger.internal', 'content': {'msgtype': 'm.text', 'body': text}}
        inbox.ingest(ident, metas[room], event)
        out.append(ts)
    return out


def read_upto(ident, ts):
    with inbox.store.db() as db:
        db.execute('UPDATE identity SET last_read_ts=?,seq=? WHERE id=?', (ts, inbox.store.next_seq(), ident['id']))


def line(i): return LINES[i % len(LINES)] + ('' if i < len(LINES) else ' (%d)' % i)


LENA = '@whatsapp_lid-501:messenger.internal'
lena = chat('lena', 'whatsapp', '!lena', 'Lena', names={LENA: 'Lena'})
ts = run(lena, '!lena', 200, [(LENA if i % 3 else None, line(i)) for i in range(30)])
read_upto(lena, ts[-1])
run(lena, '!lena', 120, [(LENA, line(i + 3)) for i in range(25)])

BRAM = '@whatsapp_316123:messenger.internal'
bram = chat('bram', 'whatsapp', '!bram', 'Bram', names={BRAM: 'Bram'})
ts = run(bram, '!bram', 90, [(BRAM if i % 2 else None, line(i)) for i in range(20)])
read_upto(bram, ts[-1])
run(bram, '!bram', 30, [(BRAM, 'See you at the ferry'), (BRAM, 'I am at the gate')])

CORA = '@telegram_77:messenger.internal'
cora = chat('cora', 'telegram', '!cora', 'Cora', names={CORA: 'Cora'})
ts = run(cora, '!cora', 80, [(CORA if i % 2 else None, line(i)) for i in range(24)])
read_upto(cora, ts[-1])

DAN = '@signal_dan:messenger.internal'
dan = chat('dan', 'signal', '!dan', 'Dan', names={DAN: 'Dan'})
ts = run(dan, '!dan', 400, [(None, 'Did you get my last message?')])
read_upto(dan, ts[-1])
run(dan, '!dan', 380, [(DAN, line(i)) for i in range(150)])

ANA, SAM, ZOE = '@whatsapp_lid-111:messenger.internal', '@whatsapp_lid-112:messenger.internal', '@whatsapp_lid-113:messenger.internal'
fam = chat('family', 'whatsapp', '!family', 'Family', 'group', {ANA: 'Ana', SAM: 'Sam', ZOE: 'Zoe'})
ts = run(fam, '!family', 70, [((ANA, SAM, None)[i % 3], line(i)) for i in range(15)])
read_upto(fam, ts[-1])
run(fam, '!family', 50, [((ANA, SAM, ZOE)[i % 3], line(i + 5)) for i in range(18)])

# Merged: Mia on WhatsApp and Telegram, unread on both; the Telegram account's read mark is the newer one, so
# person.last_read_ts (max over accounts) alone would hide the older WhatsApp unread.
MIA_W, MIA_T = '@whatsapp_lid-600:messenger.internal', '@telegram_600:messenger.internal'
mia_w = chat('mia', 'whatsapp', '!mia-w', 'Mia', names={MIA_W: 'Mia'})
mia_t = inbox.store.identity('telegram', '!mia-t', 'Mia T')
metas['!mia-t'] = {'network': 'telegram', 'kind': 'person', 'label': 'Mia T', 'names': {MIA_T: 'Mia'}}
with inbox.store.db() as db:
    db.execute('INSERT OR REPLACE INTO room_meta VALUES (?,?)', ('!mia-t', json.dumps(metas['!mia-t'])))
inbox.rooms['!mia-t'] = metas['!mia-t']
w = run(mia_w, '!mia-w', 160, [(MIA_W if i % 2 else None, line(i)) for i in range(16)])
read_upto(mia_w, w[-1])
run(mia_w, '!mia-w', 100, [(MIA_W, line(i + 2)) for i in range(8)])            # 8 unread on WhatsApp
t2 = run(mia_t, '!mia-t', 60, [(None, 'Switching to Telegram')])
read_upto(mia_t, t2[-1])
run(mia_t, '!mia-t', 40, [(MIA_T, line(i + 6)) for i in range(4)])             # 4 unread on Telegram
inbox.store.merge(state['mia'], mia_t['person_id'])

NOOR = 'npub1noor'
noor = chat('noor', 'messenger', '!noor', 'Noor', names={NOOR: 'Noor'})
ts = run(noor, '!noor', 140, [(NOOR if i % 2 else None, line(i)) for i in range(10)])
read_upto(noor, ts[-1])
run(noor, '!noor', 110, [(NOOR, line(i + 1)) for i in range(20)])

BIG = '@whatsapp_big:messenger.internal'
big = chat('big', 'whatsapp', '!big', 'Big', 'group', {BIG: 'Ann'})
FILL = ' Long voice-note style message about the trip plans, the booking and who is bringing what.' * 4  # ~350 chars each: 1000 of them exceed one pass
run(big, '!big', 1100, [(BIG, line(i) + FILL) for i in range(1000)])

token, session = server.auth.create()
state.update({'port': port, 'origin': origin, 'cookie': token, 'data': tmp})
open(os.path.join(OUT, 'state.json'), 'w').write(json.dumps(state))
print('ready', flush=True)
server.serve_forever()
