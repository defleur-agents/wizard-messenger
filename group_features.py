"""Group presentation/serialization helpers; no provider I/O or inferred identities."""
import html
import re
from html.parser import HTMLParser
from urllib.parse import unquote

# Native mention conversion is known for these maintained Matrix bridges. Other
# networks offer name autocomplete as plain text, without promising a notification.
MENTION_NETWORKS = frozenset(('telegram', 'signal', 'whatsapp', 'slack'))
MXID = re.compile(r'@[^\s:<>"/]{1,255}:[^\s<>"/]{1,255}\Z')


def member_labels(members):
    counts = {}
    for member in members:
        counts[member['name']] = counts.get(member['name'], 0) + 1
    return [dict(m, label=m['name'] if counts[m['name']] == 1 else m['name'] + ' (' + m['id'] + ')') for m in members]


def find_mentions(body, members):
    """Exact, boundary-delimited display tokens; longest first; UTF-16 offsets."""
    out, occupied = [], set()
    for member in sorted(members, key=lambda m: -len(m['label'])):
        # Picker-only names are plain text, never evidence of native addressing.
        if member.get('native') is False:
            continue
        for match in re.finditer(r'(?<![\w@])' + re.escape('@' + member['label']) + r'(?![\w])', body):
            a, b = match.span()
            if occupied.intersection(range(a, b)):
                continue
            occupied.update(range(a, b))
            out.append({'id': member['id'], 'name': member['name'], 'start': len(body[:a].encode('utf-16-le')) // 2,
                        'end': len(body[:b].encode('utf-16-le')) // 2})
    return sorted(out, key=lambda m: m['start'])


def mention_content(body, mentions):
    """Matrix standard: explicit m.mentions AND escaped matrix.to links."""
    if not mentions:
        return {}
    encoded, at = body.encode('utf-16-le'), 0
    pieces = []
    for mention in mentions:
        a, b = mention['start'] * 2, mention['end'] * 2
        pieces.append(html.escape(encoded[at:a].decode('utf-16-le')))
        pieces.append('<a href="https://matrix.to/#/' + html.escape(mention['id'], quote=True) + '">' + html.escape(encoded[a:b].decode('utf-16-le')) + '</a>')
        at = b
    pieces.append(html.escape(encoded[at:].decode('utf-16-le')))
    return {'m.mentions': {'user_ids': sorted({m['id'] for m in mentions})},
            'format': 'org.matrix.custom.html', 'formatted_body': ''.join(pieces).replace('\n', '<br>')}


class MentionLinks(HTMLParser):
    def __init__(self):
        super().__init__(); self.links = []; self.current = None
    def handle_starttag(self, tag, attrs):
        href = dict(attrs).get('href') or ''
        if tag == 'a' and href.startswith('https://matrix.to/#/'):
            ident = unquote(href[len('https://matrix.to/#/'):].split('?')[0])
            if MXID.fullmatch(ident):
                self.current = [ident, '']
    def handle_data(self, data):
        if self.current is not None:
            self.current[1] += data
    def handle_endtag(self, tag):
        if tag == 'a' and self.current is not None:
            self.links.append(self.current); self.current = None


def incoming_mentions(content, body, is_me):
    parser = MentionLinks()
    parser.feed(content.get('formatted_body', '') if isinstance(content.get('formatted_body'), str) else '')
    raw = content.get('m.mentions')
    ids = raw.get('user_ids', []) if isinstance(raw, dict) else []
    ids = {i for i in ids if isinstance(i, str) and MXID.fullmatch(i)} if isinstance(ids, list) else set()
    out, at = [], 0
    for ident, label in parser.links:
        ids.add(ident)
        start = body.find(label, at) if label else -1
        if start >= 0:
            end = start + len(label)
            out.append({'id': ident, 'name': label.lstrip('@'), 'start': len(body[:start].encode('utf-16-le')) // 2,
                        'end': len(body[:end].encode('utf-16-le')) // 2})
            at = end
    return out, any(is_me(i) for i in ids)
