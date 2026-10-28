#!/usr/bin/env python3
"""internship-tracker — a tiny CLI + JSON store for tracking internship postings.

Designed to be driven by an agent (Hermes cron) or a human. All output is
plain text, one job per line, easy to paste into chat digests.

Store: data/jobs.json (git-tracked; `sync` commits+pushes changes).

Commands:
  add        --company --role [--url --location --remote --pay --pay-source
             --deadline --term --source --tags --notes]
  update     ID [--status ... --deadline ... --notes ... --pay ...]
  list       [--status S] [--company C] [--due-within N] [--term T]
  show       ID
  due        [--within N]        # open jobs with deadlines, soonest first
  stats
  import     FILE.json           # bulk add (list of job dicts, same fields as add)
  sync       [-m MSG]            # git add/commit/push data/ if changed
"""
import argparse, datetime, json, os, re, subprocess, sys, unicodedata

ROOT = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(ROOT, "data", "jobs.json")
STATUSES = ["new", "interested", "applied", "interview", "offer", "rejected", "closed", "dropped"]
TODAY = datetime.date.today()

def load():
    if not os.path.exists(DB):
        return {"jobs": []}
    with open(DB) as f:
        return json.load(f)

def save(db):
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    tmp = DB + ".tmp"
    with open(tmp, "w") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, DB)

def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60]

def norm_url(u):
    if not u:
        return ""
    u = re.sub(r"[?#].*$", "", u.strip().lower())
    return u.rstrip("/")

def make_id(db, company, role):
    base = slug(company + "-" + role)
    existing = {j["id"] for j in db["jobs"]}
    if base not in existing:
        return base
    n = 2
    while f"{base}-{n}" in existing:
        n += 1
    return f"{base}-{n}"

def parse_date(s):
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d %b %Y", "%b %d, %Y"):
        try:
            return datetime.datetime.strptime(s.strip(), fmt).date().isoformat()
        except ValueError:
            pass
    raise SystemExit(f"error: unrecognized date '{s}' (use YYYY-MM-DD)")

def job_line(j):
    dl = j.get("deadline")
    bits = [f"[{j['status']}]", j["id"], f"{j['company']} — {j['role']}"]
    if j.get("location"):
        bits.append(j["location"] + (" (remote)" if j.get("remote") else ""))
    if j.get("pay"):
        bits.append(j["pay"])
    if dl:
        days = (datetime.date.fromisoformat(dl) - TODAY).days
        bits.append(f"deadline {dl} ({days}d)" if days >= 0 else f"deadline {dl} (PASSED {-days}d)")
    elif j.get("term"):
        bits.append(j["term"])
    return " | ".join(str(b) for b in bits)

def cmd_add(db, a):
    url = norm_url(a.url)
    if url:
        for j in db["jobs"]:
            if norm_url(j.get("url")) == url:
                print(f"dup: {j['id']} already tracks this URL — skipped")
                return 0
    j = {
        "id": make_id(db, a.company, a.role),
        "company": a.company, "role": a.role, "url": a.url or "",
        "location": a.location or "", "remote": bool(a.remote),
        "pay": a.pay or "", "pay_source": a.pay_source or "",
        "deadline": parse_date(a.deadline), "term": a.term or "Summer 2027",
        "status": "new", "source": a.source or "",
        "tags": [t for t in (a.tags or "").split(",") if t],
        "notes": a.notes or "",
        "added": TODAY.isoformat(), "updated": TODAY.isoformat(),
    }
    db["jobs"].append(j)
    save(db)
    print("added: " + job_line(j))
    return 0

def cmd_update(db, a):
    for j in db["jobs"]:
        if j["id"] == a.id:
            if a.status:
                if a.status not in STATUSES:
                    raise SystemExit(f"error: status must be one of {STATUSES}")
                j["status"] = a.status
            for k in ("deadline", "notes", "pay", "url", "location"):
                v = getattr(a, k)
                if v is not None:
                    j[k] = parse_date(v) if k == "deadline" else v
            if a.tag:
                j["tags"] = sorted(set(j.get("tags", [])) | {a.tag})
            j["updated"] = TODAY.isoformat()
            save(db)
            print("updated: " + job_line(j))
            return 0
    raise SystemExit(f"error: no job with id '{a.id}'")

def matches(j, a):
    if a.status and j["status"] != a.status:
        return False
    if a.company and a.company.lower() not in j["company"].lower():
        return False
    if a.term and j.get("term") != a.term:
        return False
    if a.due_within:
        dl = j.get("deadline")
        if not dl:
            return False
        days = (datetime.date.fromisoformat(dl) - TODAY).days
        if days < 0 or days > a.due_within:
            return False
    return True

def cmd_list(db, a):
    rows = [j for j in db["jobs"] if matches(j, a)]
    for j in rows:
        print(job_line(j))
    print(f"-- {len(rows)} job(s)")
    return 0

def cmd_show(db, a):
    for j in db["jobs"]:
        if j["id"] == a.id:
            print(json.dumps(j, indent=2, ensure_ascii=False))
            return 0
    raise SystemExit(f"error: no job with id '{a.id}'")

def cmd_due(db, a):
    rows = [j for j in db["jobs"]
            if j["status"] in ("new", "interested", "applied") and j.get("deadline")]
    rows.sort(key=lambda j: j["deadline"])
    shown = 0
    for j in rows:
        days = (datetime.date.fromisoformat(j["deadline"]) - TODAY).days
        if days < 0 or days > a.within:
            continue
        print(job_line(j))
        shown += 1
    print(f"-- {shown} deadline(s) within {a.within} days")
    return 0

def cmd_stats(db, a):
    from collections import Counter
    c = Counter(j["status"] for j in db["jobs"])
    print(f"total: {len(db['jobs'])}")
    for s in STATUSES:
        if c.get(s):
            print(f"  {s}: {c[s]}")
    return 0

def cmd_import(db, a):
    with open(a.file) as f:
        items = json.load(f)
    if isinstance(items, dict):
        items = items.get("jobs", [])
    added = dup = 0
    for it in items:
        ns = argparse.Namespace(
            company=it["company"], role=it["role"], url=it.get("url"),
            location=it.get("location"), remote=it.get("remote"),
            pay=it.get("pay"), pay_source=it.get("pay_source"),
            deadline=it.get("deadline"), term=it.get("term"),
            source=it.get("source"), tags=",".join(it.get("tags", [])),
            notes=it.get("notes"))
        url = norm_url(ns.url)
        if url and any(norm_url(j.get("url")) == url for j in db["jobs"]):
            dup += 1
            continue
        j = {
            "id": make_id(db, ns.company, ns.role),
            "company": ns.company, "role": ns.role, "url": ns.url or "",
            "location": ns.location or "", "remote": bool(ns.remote),
            "pay": ns.pay or "", "pay_source": ns.pay_source or "",
            "deadline": parse_date(ns.deadline), "term": ns.term or "Summer 2027",
            "status": it.get("status", "new"), "source": ns.source or "",
            "tags": it.get("tags", []), "notes": ns.notes or "",
            "added": TODAY.isoformat(), "updated": TODAY.isoformat(),
        }
        db["jobs"].append(j)
        added += 1
    save(db)
    print(f"imported {added}, skipped {dup} dup(s)")
    return 0

def cmd_sync(db, a):
    def git(*args):
        return subprocess.run(("git",) + args, cwd=ROOT, capture_output=True, text=True)
    r = git("status", "--porcelain", "data/")
    if not r.stdout.strip():
        print("sync: no data changes")
        return 0
    git("add", "data/")
    msg = a.m or f"tracker update {TODAY.isoformat()}"
    c = git("commit", "-m", msg)
    if c.returncode != 0:
        print("commit failed:", c.stderr.strip())
        return 1
    p = git("push")
    if p.returncode != 0:
        print("committed locally; push failed:", (p.stderr or p.stdout).strip())
        return 1
    print(f"synced: {msg}")
    return 0

def main():
    p = argparse.ArgumentParser(prog="tracker", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    def addjob(sp):
        sp.add_argument("--company", required=True)
        sp.add_argument("--role", required=True)
        sp.add_argument("--url"); sp.add_argument("--location")
        sp.add_argument("--remote", action="store_true")
        sp.add_argument("--pay"); sp.add_argument("--pay-source")
        sp.add_argument("--deadline"); sp.add_argument("--term")
        sp.add_argument("--source"); sp.add_argument("--tags"); sp.add_argument("--notes")

    sp = sub.add_parser("add"); addjob(sp); sp.set_defaults(fn=cmd_add)
    sp = sub.add_parser("update")
    sp.add_argument("id")
    sp.add_argument("--status"); sp.add_argument("--deadline")
    sp.add_argument("--notes"); sp.add_argument("--pay")
    sp.add_argument("--url"); sp.add_argument("--location"); sp.add_argument("--tag")
    sp.set_defaults(fn=cmd_update)
    sp = sub.add_parser("list")
    sp.add_argument("--status"); sp.add_argument("--company")
    sp.add_argument("--term"); sp.add_argument("--due-within", type=int)
    sp.set_defaults(fn=cmd_list)
    sp = sub.add_parser("show"); sp.add_argument("id"); sp.set_defaults(fn=cmd_show)
    sp = sub.add_parser("due"); sp.add_argument("--within", type=int, default=30)
    sp.set_defaults(fn=cmd_due)
    sp = sub.add_parser("stats"); sp.set_defaults(fn=cmd_stats)
    sp = sub.add_parser("import"); sp.add_argument("file"); sp.set_defaults(fn=cmd_import)
    sp = sub.add_parser("sync"); sp.add_argument("-m"); sp.set_defaults(fn=cmd_sync)

    a = p.parse_args()
    sys.exit(a.fn(load(), a))

if __name__ == "__main__":
    main()
