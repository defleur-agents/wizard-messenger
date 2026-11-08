"""Usage: AGENT_STAGE_DIR=<dir> python tests/group_last_read_stage.py <port>, then node tests/group_last_read_browser.cjs.
James, 6 Nov 2026: "when I open a group chat, it seems to scroll all the way to the bottom. It shouldn't do that. It
should show me where my last read message is and start the reading there."
Disposable staging: real ViewServer + real UnifiedInbox store, SYNTHETIC group chats fed through the real ingest path,
read marks set the way the server keeps them (identity.last_read_ts). No homeserver, provider or real account.
Groups (each taller than any window once unread):
  Climbing crew  Telegram  4 senders, 20 read, 40 unread with 6 photos (3 sized, 3 without dimensions)
  Signal family  Signal    3 senders, 15 read, 30 unread with 4 photos
  Ferry friends  WhatsApp  5 senders, 25 read, 35 unread with 2 photos
  Tokyo trip     LINE      3 senders, 10 read, 28 unread with 3 photos
  Big group      Telegram  6 senders, 5 read, 200 unread (older than the first page of 60)
Writes <dir>/state.json."""
import itertools, json, os, sys, tempfile, time
from unittest.mock import Mock
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'tests'))
OUT = os.environ.get('AGENT_STAGE_DIR') or sys.exit('AGENT_STAGE_DIR required'); os.makedirs(OUT, exist_ok=True)
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
port = int(sys.argv[1]) if len(sys.argv) > 1 else 18971
origin = 'http://127.0.0.1:%d' % port
server = ViewServer(('127.0.0.1', port), engine, fx.TOKEN, [origin])
inbox = UnifiedInbox(tmp, engine); server.unified = inbox
_sent = itertools.count(1)
inbox.mx = Mock(side_effect=lambda *a, **k: {'event_id': '$sent%d' % next(_sent)})
inbox.matrix_token = lambda: 'staged'
server.drafts = Drafts(tmp)

now = int(time.time() * 1000)
LINES = ['Are you around later?', 'I found the photos from the weekend', 'The ferry leaves at nine, so we should be there by half past eight',
         'ok', 'Did you see what Sam sent?', 'Let me know when you land', 'haha yes', 'Can you bring the charger this time?',
         'I think the restaurant closes at ten', 'Sounds good to me', 'Running ten minutes late, sorry!', 'Here is the address: Soi 11, second floor']
metas, state = {}, {'groups': {}}


def line(i): return LINES[i % len(LINES)] + ('' if i < len(LINES) else ' (%d)' % i)


def group(key, network, room, label, senders):
    names = {mx: name for mx, name in senders}
    ident = inbox.store.identity(network, room, label, 'group')
    meta = {'network': network, 'kind': 'group', 'label': label, 'names': names}
    with inbox.store.db() as db:
        db.execute('INSERT OR REPLACE INTO room_meta VALUES (?,?)', (room, json.dumps(meta)))
    inbox.rooms[room] = meta; metas[room] = meta
    return ident


def run(ident, room, start, rows):
    """rows: (sender or None for own, text, photo); one minute apart starting `start` minutes ago."""
    out = []
    for i, (sender, text, photo) in enumerate(rows):
        ts = now - (start - i) * 60000
        content = {'msgtype': 'm.text', 'body': text}
        if photo:
            info = {'mimetype': 'image/jpeg', 'size': 120000}
            if photo == 'sized': info.update(w=800, h=1000)
            content = {'msgtype': 'm.image', 'body': 'IMG_%d.jpg' % i, 'url': 'mxc://messenger.internal/%s-%d-%d' % (room.strip('!'), start, i), 'info': info}
        event = {'event_id': '$%s-%d-%d' % (room.strip('!'), start, i), 'type': 'm.room.message', 'origin_server_ts': ts,
                 'sender': sender or '@owner:messenger.internal', 'content': content}
        inbox.ingest(ident, metas[room], event)
        out.append(ts)
    return out


def read_upto(ident, ts):
    with inbox.store.db() as db:
        db.execute('UPDATE identity SET last_read_ts=?,seq=? WHERE id=?', (ts, inbox.store.next_seq(), ident['id']))


def stage(key, network, room, label, senders, read, unread, photos, own_every=3):
    ident = group(key, network, room, label, senders)
    mx = [s for s, _ in senders]
    start = read + unread + 30
    ts = run(ident, room, start, [(None if i % own_every == 0 else mx[i % len(mx)], line(i), None) for i in range(read)])
    read_upto(ident, ts[-1])
    shapes = {}
    for n, i in enumerate(photos): shapes[i] = 'sized' if n % 2 == 0 else 'bare'
    run(ident, room, start - read - 5, [(mx[(i * 7 + 1) % len(mx)], line(i + 3), shapes.get(i)) for i in range(unread)])
    state['groups'][key] = {'id': ident['person_id'], 'label': label, 'network': network, 'unread': unread, 'room': room}


def senders(prefix, names): return [('@%s_%d:messenger.internal' % (prefix, 100 + i), n) for i, n in enumerate(names)]


stage('climbing', 'telegram', '!climbing', 'Climbing crew', senders('telegram', ['Ana', 'Sam', 'Zoe', 'Kit']), 20, 40, [1, 4, 9, 15, 22, 33])
stage('signal', 'signal', '!sigfam', 'Signal family', senders('signal', ['Mum', 'Dad', 'Ivy']), 15, 30, [2, 6, 12, 20])
stage('ferry', 'whatsapp', '!ferry', 'Ferry friends', senders('whatsapp_lid', ['Bo', 'Cy', 'Di', 'Ed', 'Flo']), 25, 35, [3, 17])
stage('tokyo', 'line', '!tokyo', 'Tokyo trip', senders('line', ['Haru', 'Yui', 'Ren']), 10, 28, [0, 5, 11])
stage('big', 'telegram', '!big', 'Big group', senders('telegram', ['A1', 'B2', 'C3', 'D4', 'E5', 'F6']), 5, 200, [10, 50, 150])

token, session = server.auth.create()
state.update({'port': port, 'origin': origin, 'cookie': token, 'data': tmp})
open(os.path.join(OUT, 'state.json'), 'w').write(json.dumps(state))
print('ready', flush=True)
server.serve_forever()
