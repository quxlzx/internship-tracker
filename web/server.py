#!/usr/bin/env python3
"""tracker-web — read-only web view of ~/internship-tracker/data/jobs.json.
Stdlib only (fleet convention). Serves one vanilla-JS page + /api/jobs.
Port 8101. Read-only by design: mutations stay in tracker.py (cron-safe)."""
import json, os, sqlite3
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parent
TRACKER = Path.home() / "internship-tracker"
PORT = 8101

def load_jobs():
    data = json.loads((TRACKER / "data" / "jobs.json").read_text())
    return data.get("jobs", data if isinstance(data, list) else [])

class H(SimpleHTTPRequestHandler):
    def log_message(self, format, *a): pass

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/api/jobs":
            q = parse_qs(u.query)
            jobs = load_jobs()
            st = q.get("status", [None])[0]
            tag = q.get("tag", [None])[0]
            s = (q.get("q", [""])[0] or "").lower()
            if st: jobs = [j for j in jobs if j.get("status") == st]
            if tag: jobs = [j for j in jobs if tag in (j.get("tags") or [])]
            if s:
                jobs = [j for j in jobs if s in (j.get("company","")+" "+j.get("role","")+" "+j.get("location","")).lower()]
            jobs.sort(key=lambda j: (j.get("status") != "new", j.get("status") != "interested", j.get("added",""), j.get("company","")))
            return self._json({"total": len(load_jobs()), "shown": len(jobs), "jobs": jobs})
        if u.path in ("/", "/index.html"):
            html = (ROOT / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)
            return
        self._json({"error": "not found"}, 404)

if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
