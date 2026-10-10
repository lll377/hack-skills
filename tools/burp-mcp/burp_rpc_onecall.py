import argparse, json, queue, re, threading, time, urllib.parse, urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:9876"

class SSESession:
    def __init__(self, base=BASE, timeout=20):
        self.base = base
        self.timeout = timeout
        self.q = queue.Queue()
        self.stop = threading.Event()
        self.response = None
        self.session_id = None
        self.thread = threading.Thread(target=self._reader, daemon=True)
        self.thread.start()
        deadline = time.time() + timeout
        while time.time() < deadline and not self.session_id:
            try:
                kind, data = self.q.get(timeout=0.5)
            except queue.Empty:
                continue
            if kind == "endpoint":
                m = re.search(r"sessionId=([^&\s]+)", data)
                if m:
                    self.session_id = m.group(1)
            elif kind == "reader_error":
                raise RuntimeError(data)
        if not self.session_id:
            raise RuntimeError("no sessionId from SSE endpoint")
        self.post_url = self.base + "?sessionId=" + urllib.parse.quote(self.session_id)
        self.next_id = 1

    def _reader(self):
        try:
            req = urllib.request.Request(self.base, headers={"Accept": "text/event-stream", "Cache-Control": "no-cache"})
            self.response = urllib.request.urlopen(req, timeout=60)
            event = "message"
            for raw in self.response:
                if self.stop.is_set():
                    break
                line = raw.decode("utf-8", "replace").rstrip("\r\n")
                if line.startswith("event:"):
                    event = line.split(":", 1)[1].strip()
                elif line.startswith("data:"):
                    self.q.put((event, line.split(":", 1)[1].lstrip()))
        except Exception as e:
            if not self.stop.is_set():
                self.q.put(("reader_error", repr(e)))

    def rpc(self, method, params, wait=True):
        rid = self.next_id if wait else None
        if wait:
            self.next_id += 1
        obj = {"jsonrpc": "2.0", "method": method, "params": params}
        if rid is not None:
            obj["id"] = rid
        data = json.dumps(obj, separators=(",", ":")).encode("utf-8")
        req = urllib.request.Request(self.post_url, data=data, headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            http_status = r.status
            http_body = r.read().decode("utf-8", "replace")
        if not wait:
            return {"http_status": http_status, "http_body": http_body}
        deadline = time.time() + self.timeout
        seen = []
        while time.time() < deadline:
            try:
                kind, payload = self.q.get(timeout=0.5)
            except queue.Empty:
                continue
            if kind == "reader_error":
                return {"error": {"message": payload, "kind": "reader_error"}, "_http_status": http_status, "_http_body": http_body}
            if kind != "message":
                continue
            try:
                msg = json.loads(payload)
            except Exception:
                seen.append(payload)
                continue
            seen.append(msg)
            if msg.get("id") == rid:
                msg["_http_status"] = http_status
                msg["_http_body"] = http_body
                return msg
        return {"error": {"message": "timeout waiting for response", "seen": seen[-10:]}, "_http_status": http_status, "_http_body": http_body}

    def close(self):
        self.stop.set()
        try:
            if self.response is not None:
                self.response.close()
        except Exception:
            pass
        try:
            self.thread.join(timeout=2)
        except Exception:
            pass


def main():
    import os, sys, traceback
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['list-tools', 'call'])
    ap.add_argument('--tool')
    ap.add_argument('--args-json', default='{}')
    ap.add_argument('--args-file')
    ap.add_argument('--timeout', type=int, default=20)
    ap.add_argument('--out-file')
    ns = ap.parse_args()
    payload = None
    status = 0
    session = None
    try:
        session = SSESession(timeout=ns.timeout)
        init = session.rpc('initialize', {'protocolVersion': '2025-03-26', 'capabilities': {}, 'clientInfo': {'name': 'burp-mcp-onecall', 'version': '2026-08-01'}}, wait=True)
        session.rpc('notifications/initialized', {}, wait=False)
        if ns.mode == 'list-tools':
            resp = session.rpc('tools/list', {}, wait=True)
            payload = {'initialize': init, 'response': resp}
        else:
            args = json.loads(Path(ns.args_file).read_text(encoding='utf-8-sig')) if ns.args_file else json.loads(ns.args_json)
            resp = session.rpc('tools/call', {'name': ns.tool, 'arguments': args}, wait=True)
            payload = {'initialize': init, 'tool': ns.tool, 'arguments': args, 'response': resp}
    except Exception as e:
        status = 1
        payload = {'exception': repr(e), 'traceback': traceback.format_exc(), 'tool': getattr(ns, 'tool', None)}
    try:
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        if ns.out_file:
            Path(ns.out_file).write_text(text, encoding='utf-8')
        else:
            print(text)
            sys.stdout.flush()
    finally:
        try:
            if session is not None:
                session.stop.set()
        except Exception:
            pass
        os._exit(status)

if __name__ == '__main__':
    main()

