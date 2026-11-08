"""Usage: AGENT_STAGE_DIR=<dir> python tests/incoming_media_stage.py <port>, then node tests/incoming_media_browser.cjs.
Disposable staging for incoming media display: real ViewServer + real UnifiedInbox store, synthetic WhatsApp/Telegram
chats fed through the real ingest path (GIF, animated sticker, static GIF, @mentions, expired media, a decrypt-retry
edit that becomes a photo). Media bytes are generated with ffmpeg and pre-seeded into the media cache: no homeserver,
no provider, no real account. Writes <dir>/state.json."""
import hashlib, itertools, json, os, subprocess, sys, tempfile, time
from unittest.mock import Mock
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'tests'))
OUT = os.environ.get('AGENT_STAGE_DIR', '/home/oscar/.hermes/cache/scratch/incoming-stage'); os.makedirs(OUT, exist_ok=True)
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
port = int(sys.argv[1]) if len(sys.argv) > 1 else 18951
origin = 'http://127.0.0.1:%d' % port
server = ViewServer(('127.0.0.1', port), engine, fx.TOKEN, [origin])
inbox = UnifiedInbox(tmp, engine); server.unified = inbox
_sent = itertools.count(1)
inbox.mx = Mock(side_effect=lambda *a, **k: {'event_id': '$sent%d' % next(_sent)})  # unique: a reaction swap redacts the old one
inbox.matrix_token = lambda: 'staged'
server.drafts = Drafts(tmp)

# ---- synthetic media, seeded into the cache the media endpoint reads ----
media_dir = os.path.join(tmp, 'gen'); os.makedirs(media_dir)
def ff(name, *args):
    path = os.path.join(media_dir, name)
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', *args, path], check=True)
    return path
files = {
    'gif': ff('gif.webm', '-f', 'lavfi', '-i', 'testsrc2=s=320x240:d=2:r=15', '-c:v', 'libvpx-vp9', '-b:v', '300k', '-an'),
    'sticker': ff('sticker.webm', '-f', 'lavfi', '-i', 'testsrc=s=256x256:d=2:r=15', '-c:v', 'libvpx-vp9', '-b:v', '200k', '-an'),
    'sticker_thumb': ff('sticker.png', '-f', 'lavfi', '-i', 'testsrc=s=256x256', '-frames:v', '1'),
    'anim': ff('anim.gif', '-f', 'lavfi', '-i', 'testsrc=s=240x160:d=1:r=8'),
    'photo': ff('photo.png', '-f', 'lavfi', '-i', 'smptebars=s=640x480', '-frames:v', '1'),
}
cache = os.path.join(tmp, 'unified', 'media-cache'); os.makedirs(cache, exist_ok=True)
def seed(mxc, path, kind='full', mime=None):
    key = hashlib.sha256((mxc + '|' + kind).encode()).hexdigest()
    with open(path, 'rb') as src, open(os.path.join(cache, key), 'wb') as dst:
        dst.write(src.read())
    if mime:
        open(os.path.join(cache, key + '.type'), 'w').write(mime)
seed('mxc://messenger.internal/gif', files['gif'], mime='video/webm')
seed('mxc://messenger.internal/sticker', files['sticker'], mime='video/webm')
seed('mxc://messenger.internal/stickerthumb', files['sticker_thumb'], 'thumb', 'image/png')
seed('mxc://messenger.internal/anim', files['anim'], mime='image/gif')
seed('mxc://messenger.internal/photo', files['photo'], mime='image/png')
seed('mxc://messenger.internal/photo', files['photo'], 'thumb', 'image/png')

# ---- chats ----
ANA, BRAM, OWNER = '@whatsapp_lid-111:messenger.internal', '@whatsapp_316123:messenger.internal', '@owner:messenger.internal'
inbox.store.remember_own_names('whatsapp', ['Miguel Ortiz'])
bram = inbox.store.identity('whatsapp', '!bram', 'Bram')
group = inbox.store.identity('whatsapp', '!family', 'Family', 'group')
tg = inbox.store.identity('telegram', '!devs', 'Wizard devs', 'group')
metas = {
    '!bram': {'network': 'whatsapp', 'kind': 'person', 'label': 'Bram', 'names': {BRAM: '+31 6 1234 5678 (WA)'}},
    '!family': {'network': 'whatsapp', 'kind': 'group', 'label': 'Family', 'names': {ANA: 'Ana (WA)', BRAM: '+31 6 1234 5678 (WA)', OWNER: 'Miguel'}},
    '!devs': {'network': 'telegram', 'kind': 'group', 'label': 'Wizard devs', 'names': {'@telegram_9:messenger.internal': 'Zoe', '@telegram_8:messenger.internal': 'Sam'}},
}
with inbox.store.db() as db:
    for room, meta in metas.items():
        db.execute('INSERT OR REPLACE INTO room_meta VALUES (?,?)', (room, json.dumps(meta)))
inbox.rooms.update(metas)
now = int(time.time() * 1000)
t = [now - 3600000]
def ev(eid, content, sender=ANA, etype='m.room.message'):
    t[0] += 60000
    return {'event_id': eid, 'type': etype, 'sender': sender, 'origin_server_ts': t[0], 'content': content}
def put(identity, room, *events):
    for e in events:
        inbox.ingest(identity, metas[room], e)

put(bram, '!bram', ev('$b1', {'msgtype': 'm.text', 'body': 'see you at the party'}, sender=BRAM))
GIF_INFO = {'mimetype': 'video/mp4', 'w': 320, 'h': 240, 'size': 40000, 'duration': 2000,
            'fi.mau.gif': True, 'fi.mau.loop': True, 'fi.mau.autoplay': True, 'fi.mau.no_audio': True, 'fi.mau.hide_controls': True}
put(group, '!family', ev('$gif', {'msgtype': 'm.video', 'body': 'video.mp4', 'url': 'mxc://messenger.internal/gif', 'info': GIF_INFO}))
for i in range(12):
    put(group, '!family', ev('$f%d' % i, {'msgtype': 'm.text', 'body': 'line %d of the plan' % (i + 1)}, sender=ANA if i % 2 else BRAM))
put(group, '!family',
    ev('$static', {'msgtype': 'm.image', 'body': 'dance.gif', 'url': 'mxc://messenger.internal/anim', 'info': {'mimetype': 'image/gif', 'w': 240, 'h': 160, 'size': 30000}}),
    ev('$mention', {'msgtype': 'm.text', 'body': 'welcome +31 6 1234 5678 (WA) !! Miguel (WA) can you add him?', 'format': 'org.matrix.custom.html',
                    'formatted_body': 'welcome <a href="https://matrix.to/#/%s">+31 6 1234 5678 (WA)</a> !! <a href="https://matrix.to/#/%s">Miguel (WA)</a> can you add him?' % (BRAM, OWNER),
                    'm.mentions': {'user_ids': [BRAM, OWNER]}}),
    ev('$expired', {'msgtype': 'm.notice', 'body': 'Failed to bridge photo, please view it on the WhatsApp app\n\nour trip to the lake', 'fi.mau.whatsapp.failed_media': {}}),
    ev('$wait', {'msgtype': 'm.notice', 'body': 'Decrypting message from WhatsApp failed, waiting for sender to re-send... ([learn more](https://faq.whatsapp.com/))'}, sender=BRAM),
)
put(group, '!family', ev('$wait-edit', {'msgtype': 'm.image', 'body': '* sunset', 'm.new_content': {'msgtype': 'm.image', 'body': 'sunset', 'filename': 'IMG.png', 'url': 'mxc://messenger.internal/photo',
                                                                                         'info': {'mimetype': 'image/png', 'w': 640, 'h': 480, 'size': 9000}},
                                         'm.relates_to': {'rel_type': 'm.replace', 'event_id': '$wait'}}, sender=BRAM))
# A decrypt failure WhatsApp never re-sent (two days old): "couldn't be decrypted", not "waiting" forever.
put(group, '!family', dict(ev('$lost', {'msgtype': 'm.notice', 'body': 'Decrypting message from WhatsApp failed, waiting for sender to re-send... ([learn more](https://faq.whatsapp.com/))'}, sender=BRAM),
                           origin_server_ts=now - 2 * 86400000))
# A photo with no caption (bubble-less) and an incoming reaction on the GIF: both must stay reactable (react_media_browser).
put(group, '!family', ev('$photo', {'msgtype': 'm.image', 'body': 'IMG_2041.png', 'url': 'mxc://messenger.internal/photo',
                                    'info': {'mimetype': 'image/png', 'w': 640, 'h': 480, 'size': 9000}}, sender=BRAM),
    ev('$gif-heart', {'m.relates_to': {'rel_type': 'm.annotation', 'event_id': '$gif', 'key': '❤️'}}, sender=BRAM, etype='m.reaction'))
put(group, '!family', ev('$expired2', {'msgtype': 'm.notice', 'body': 'Failed to bridge voice message, please view it on the WhatsApp app'}, sender=BRAM))
put(tg, '!devs',
    ev('$sticker', {'msgtype': 'm.video', 'body': 'sticker.webm', 'url': 'mxc://messenger.internal/sticker',
                    'info': {'mimetype': 'video/webm', 'w': 256, 'h': 256, 'size': 30000, 'thumbnail_url': 'mxc://messenger.internal/stickerthumb',
                             'fi.mau.bridged_sticker': True, 'fi.mau.telegram.animated_sticker': True, 'fi.mau.gif': True, 'fi.mau.loop': True, 'fi.mau.no_audio': True}},
       sender='@telegram_9:messenger.internal'),
    ev('$md', {'msgtype': 'm.text', 'body': '**Install Wizard OS** today, then run `wam doctor` and ping @zoe_dev', 'format': 'org.matrix.custom.html',
               'formatted_body': '<strong>Install Wizard OS</strong> today, then run <code>wam doctor</code> and ping <a href="https://matrix.to/#/@telegram_9:messenger.internal">@zoe_dev</a>',
               'm.mentions': {'user_ids': ['@telegram_9:messenger.internal']}}, sender='@telegram_8:messenger.internal'),
)
# WhatsApp Status Broadcast (bridge portal status@broadcast): a status post the bridge could not decrypt reads as a
# status update to view on the phone; an ordinary chat's fresh decrypt failure still waits for the re-send.
WAIT_BODY = 'Decrypting message from WhatsApp failed, waiting for sender to re-send... ([learn more](https://faq.whatsapp.com/))'
status = inbox.store.identity('whatsapp', '!status', 'WhatsApp Status Broadcast', 'group')
ana = inbox.store.identity('whatsapp', '!ana', 'Ana')
more = {'!status': {'network': 'whatsapp', 'kind': 'group', 'label': 'WhatsApp Status Broadcast', 'channel_id': 'status@broadcast', 'names': {'@whatsapp_lid-222:messenger.internal': 'Eric (WA)'}},
        '!ana': {'network': 'whatsapp', 'kind': 'person', 'label': 'Ana', 'channel_id': '111@s.whatsapp.net', 'names': {ANA: 'Ana (WA)'}}}
with inbox.store.db() as db:
    for room, meta in more.items():
        db.execute('INSERT OR REPLACE INTO room_meta VALUES (?,?)', (room, json.dumps(meta)))
inbox.rooms.update(more); metas.update(more)
put(status, '!status', dict(ev('$status', {'msgtype': 'm.notice', 'body': WAIT_BODY}, sender='@whatsapp_lid-222:messenger.internal'), origin_server_ts=now - 60000))
put(ana, '!ana', dict(ev('$ana-wait', {'msgtype': 'm.notice', 'body': WAIT_BODY}), origin_server_ts=now - 30000))
token, session = server.auth.create()
state = {'port': port, 'origin': origin, 'cookie': token, 'family': group['person_id'], 'devs': tg['person_id'], 'status': status['person_id'], 'ana': ana['person_id'], 'data': tmp}
open(os.path.join(OUT, 'state.json'), 'w').write(json.dumps(state))
print('ready', flush=True)
server.serve_forever()
