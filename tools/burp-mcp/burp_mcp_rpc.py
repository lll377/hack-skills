import argparse, json, queue, re, socket, sys, threading, time, urllib.parse, urllib.request
from pathlib import Path

BASE='http://127.0.0.1:9876'
# Local MCP must not go through system HTTP/SOCKS proxy (xray on 10808 breaks SSE).
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

class Session:
    def __init__(self, base=BASE, timeout=20):
        self.base=base; self.timeout=timeout; self.q=queue.Queue(); self.stop=threading.Event(); self.resp=None; self.next_id=1
        self.t=threading.Thread(target=self._reader, daemon=True); self.t.start(); self.session_id=None
        deadline=time.time()+timeout
        while time.time()<deadline and not self.session_id:
            try: kind,data=self.q.get(timeout=0.5)
            except queue.Empty: continue
            if kind=='endpoint':
                m=re.search(r'sessionId=([^&\s]+)', data)
                if m: self.session_id=m.group(1)
            elif kind=='reader_error':
                raise RuntimeError(data)
        if not self.session_id: raise RuntimeError('no sessionId from SSE endpoint')
        self.post_url=self.base+'?sessionId='+urllib.parse.quote(self.session_id)
    def _reader(self):
        try:
            req=urllib.request.Request(self.base, headers={'Accept':'text/event-stream','Cache-Control':'no-cache'})
            self.resp=_OPENER.open(req, timeout=60)
            event='message'
            for raw in self.resp:
                if self.stop.is_set(): break
                line=raw.decode('utf-8','replace').rstrip('\r\n')
                if line.startswith('event:'):
                    event=line.split(':',1)[1].strip()
                elif line.startswith('data:'):
                    self.q.put((event, line.split(':',1)[1].lstrip()))
        except Exception as e:
            if not self.stop.is_set(): self.q.put(('reader_error', repr(e)))
    def rpc(self, method, params, wait=True):
        rid=self.next_id if wait else None
        if wait: self.next_id+=1
        obj={'jsonrpc':'2.0','method':method,'params':params}
        if rid is not None: obj['id']=rid
        data=json.dumps(obj,separators=(',',':')).encode('utf-8')
        req=urllib.request.Request(self.post_url, data=data, headers={'Content-Type':'application/json','Accept':'application/json, text/event-stream'}, method='POST')
        with _OPENER.open(req, timeout=self.timeout) as r:
            http_status=r.status; http_body=r.read().decode('utf-8','replace')
        if not wait:
            return {'http_status':http_status,'http_body':http_body}
        deadline=time.time()+self.timeout
        seen=[]
        while time.time()<deadline:
            try: kind,payload=self.q.get(timeout=0.5)
            except queue.Empty: continue
            if kind=='reader_error':
                return {'error': {'message': payload, 'kind':'reader_error'}, '_http_status': http_status, '_http_body': http_body}
            if kind!='message':
                continue
            try: msg=json.loads(payload)
            except Exception:
                seen.append(payload); continue
            seen.append(msg)
            if msg.get('id')==rid:
                msg['_http_status']=http_status; msg['_http_body']=http_body
                return msg
        return {'error': {'message':'timeout waiting for response','seen':seen[-10:]}, '_http_status': http_status, '_http_body': http_body}
    def initialize(self):
        init=self.rpc('initialize', {'protocolVersion':'2025-03-26','capabilities':{},'clientInfo':{'name':'burp-mcp-rpc','version':'2026-08-01'}}, wait=True)
        self.rpc('notifications/initialized', {}, wait=False)
        return init
    def close(self):
        self.stop.set()
        resp=self.resp
        self.resp=None
        if not resp:
            return
        try:
            sock=resp.fp.raw._sock
            sock.shutdown(socket.SHUT_RDWR)
            sock.close()
        except Exception:
            pass
        try:
            resp.close()
        except Exception:
            pass

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('mode', choices=['list-tools','call'])
    ap.add_argument('--tool')
    ap.add_argument('--args-json', default='{}')
    ap.add_argument('--timeout', type=int, default=20)
    ap.add_argument('--base', default=BASE)
    ap.add_argument('--out-file')
    ns=ap.parse_args()
    s=Session(ns.base, ns.timeout)
    try:
        init=s.initialize()
        if ns.mode=='list-tools':
            resp=s.rpc('tools/list', {}, wait=True)
            payload=json.dumps({'initialize':init,'response':resp}, ensure_ascii=False, indent=2)
        else:
            args=json.loads(ns.args_json)
            resp=s.rpc('tools/call', {'name':ns.tool,'arguments':args}, wait=True)
            payload=json.dumps({'initialize':init,'tool':ns.tool,'arguments':args,'response':resp}, ensure_ascii=False, indent=2)
        if ns.out_file:
            Path(ns.out_file).write_text(payload, encoding='utf-8')
        else:
            print(payload)
            sys.stdout.flush()
    finally:
        s.close()
    import os
    os._exit(0)

if __name__=='__main__':
    main()
