"""Disposable namespace-only immutable registry transport; no upstream forwarding."""
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
import hashlib,json,re,sys
ROOT=Path(sys.argv[1]); docs={};blobs={}
for p in (ROOT/'images').glob('*.tar.parts/*'):
    if p.name.startswith('manifest-'):
        d='sha256:'+p.name[9:-5];assert hashlib.sha256(p.read_bytes()).hexdigest()==d[7:];docs[d]=p
    elif re.fullmatch('[a-f0-9]{64}',p.name):blobs['sha256:'+p.name]=p
class H(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def handle_request(self):
        path=self.path.split('?')[0]
        if path.rstrip('/')=='/v2':
            self.send_response(200);self.send_header('Docker-Distribution-API-Version','registry/2.0');self.end_headers();return
        m=re.fullmatch(r'/v2/(.+)/(manifests|blobs)/(sha256:[a-f0-9]{64})',path)
        if not m:self.send_response(404);self.end_headers();return
        repo,kind,d=m.groups(); p=(docs if kind=='manifests' else blobs).get(d)
        if not p:self.send_response(404);self.end_headers();return
        self.send_response(200); self.send_header('Docker-Content-Digest',d);self.send_header('Docker-Distribution-API-Version','registry/2.0');self.send_header('Content-Length',str(p.stat().st_size)); self.send_header('Content-Type',json.loads(p.read_bytes()).get('mediaType','application/vnd.docker.distribution.manifest.v2+json') if kind=='manifests' else 'application/octet-stream');self.end_headers()
        if self.command!='HEAD':
            with open(p,'rb') as f:
                while b:=f.read(1024*1024):self.wfile.write(b)
    do_GET=handle_request;do_HEAD=handle_request
ThreadingHTTPServer(('127.0.0.1',80),H).serve_forever()
