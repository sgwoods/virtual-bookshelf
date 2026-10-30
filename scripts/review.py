#!/usr/bin/env python3
"""Local review page for the catalogue.

Usage:  python3 scripts/review.py            # opens http://127.0.0.1:8765
        python3 scripts/review.py --all      # show every row, not just the queue
        python3 scripts/review.py --port 9000 --no-browser

Shows each book that needs a human: weak or missing Open Library match, or a
spine read below high confidence. For each one you can
  • pick the right candidate (cover, title, author, year shown),
  • accept the best guess,
  • mark it "not listed" (real book, just not in Open Library — keep as read),
  • mark it "not a book",
  • or fix the title/author as read from the spine (writes back to books.csv;
    the next resolve.py run looks it up again).

Decisions go to data/overrides.csv. Re-run scripts/resolve.py afterwards to
fold them into data/resolved.csv (instant — everything is cached).

Standard library only. Binds to 127.0.0.1, so only this Mac can reach it.
"""
from __future__ import annotations

import argparse, csv, html, json, sys, threading, time, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
BOOKS = ROOT / "data/books.csv"
RESOLVED = ROOT / "data/resolved.csv"
OVERRIDES = ROOT / "data/overrides.csv"
DRIVE = ROOT / "data/drive_files.tsv"
PHOTOS = ROOT / "photos/jpg"
OV_FIELDS = ["row_id", "decision", "pick_json", "note", "decided_at"]
LOCK = threading.Lock()
SHOW_ALL = False


# ---------------------------------------------------------------- data
def rid(r): return f"{r['photo']}:{r['stack']}:{r['position']}"


def load():
    books = list(csv.DictReader(open(BOOKS, encoding="utf-8")))
    res = {r["row_id"]: r for r in csv.DictReader(open(RESOLVED, encoding="utf-8"))} \
        if RESOLVED.exists() else {}
    ov = {r["row_id"]: r for r in csv.DictReader(open(OVERRIDES, encoding="utf-8"))} \
        if OVERRIDES.exists() else {}
    drive = dict(l.rstrip("\n").split("\t") for l in open(DRIVE)) if DRIVE.exists() else {}
    return books, res, ov, drive


def needs_review(b, r):
    if b["position"] == "0":
        return False
    if b["confidence"] not in ("high", "checked"):
        return True
    return (r or {}).get("status") in ("weak", "none", "skipped", None, "")


def write_override(row_id, decision, pick_json="", note=""):
    with LOCK:
        rows = {r["row_id"]: r for r in csv.DictReader(open(OVERRIDES, encoding="utf-8"))} \
            if OVERRIDES.exists() else {}
        if decision == "undo":
            rows.pop(row_id, None)
        else:
            rows[row_id] = {"row_id": row_id, "decision": decision, "pick_json": pick_json,
                            "note": note, "decided_at": time.strftime("%Y-%m-%d %H:%M")}
        with open(OVERRIDES, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=OV_FIELDS); w.writeheader(); w.writerows(rows.values())


def edit_book(row_id, title, author):
    with LOCK:
        rows = list(csv.DictReader(open(BOOKS, encoding="utf-8")))
        fields = list(rows[0].keys())
        for r in rows:
            if rid(r) == row_id:
                if title: r["title"] = title.strip()
                if author: r["author"] = author.strip()
                r["confidence"] = "checked"
                r["notes"] = (r["notes"] + "; " if r["notes"] else "") + "corrected in review"
        with open(BOOKS, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)
    # an edited spine read invalidates any earlier decision on this row
    write_override(row_id, "undo")


# ---------------------------------------------------------------- html
CSS = """
:root{--bg:#f6f4ef;--card:#fff;--ink:#1d1b18;--mute:#6d675e;--line:#e3ded4;--acc:#7a3e1d;
--ok:#2f6b3a;--warn:#9a6a00;--bad:#9b2c2c;--chip:#efe9dd}
@media (prefers-color-scheme:dark){:root{--bg:#171513;--card:#211e1b;--ink:#ece6dc;--mute:#a39b8f;
--line:#38332d;--acc:#e0a370;--ok:#7fc48b;--warn:#e2b44f;--bad:#ef8b8b;--chip:#2c2824}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
header{position:sticky;top:0;z-index:2;background:var(--bg);border-bottom:1px solid var(--line);
padding:14px 20px;display:flex;gap:16px;align-items:baseline;flex-wrap:wrap}
h1{font:600 19px/1 Georgia,serif;margin:0}.count{color:var(--mute)}
.bar{flex:1;min-width:120px;height:6px;background:var(--line);border-radius:3px;overflow:hidden}
.bar i{display:block;height:100%;background:var(--acc)}
main{max-width:1100px;margin:0 auto;padding:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;margin:0 0 14px;
display:grid;grid-template-columns:260px 1fr;gap:18px;transition:opacity .25s}
.card.done{opacity:.35}
@media (max-width:760px){.card{grid-template-columns:1fr}}
.read h2{font:600 17px/1.25 Georgia,serif;margin:0 0 4px}.read .by{color:var(--mute);margin-bottom:8px}
.chips{display:flex;gap:6px;flex-wrap:wrap;margin:6px 0}.chip{background:var(--chip);border-radius:99px;
padding:2px 9px;font-size:12px;color:var(--mute)}.chip.low,.chip.none{color:var(--bad)}
.chip.medium,.chip.weak{color:var(--warn)}.chip.skipped{color:var(--mute)}
.note{font-size:13px;color:var(--mute)}a{color:var(--acc)}
.cands{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:10px}
.cand{border:1px solid var(--line);border-radius:8px;padding:8px;display:flex;gap:8px;flex-direction:column}
.cand .cv{display:flex;gap:8px}.cand img,.cand .ph{width:52px;height:78px;object-fit:cover;border-radius:3px;
background:var(--chip);flex:none}.cand b{font-size:13px;line-height:1.25;display:block}
.cand small{color:var(--mute);font-size:12px;display:block}.sc{font-size:11px;color:var(--mute)}
button{font:inherit;font-size:13px;border:1px solid var(--line);background:var(--chip);color:var(--ink);
border-radius:6px;padding:5px 10px;cursor:pointer}button:hover{border-color:var(--acc)}
button.primary{background:var(--acc);color:var(--card);border-color:var(--acc)}
.acts{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}
form.fix{display:none;gap:6px;margin-top:8px;flex-wrap:wrap}form.fix.open{display:flex}
form.fix input{font:inherit;font-size:13px;padding:5px 8px;border:1px solid var(--line);border-radius:6px;
background:var(--bg);color:var(--ink);flex:1;min-width:140px}
.empty{text-align:center;color:var(--mute);padding:60px 0}.decided{font-size:13px;color:var(--ok);margin-top:6px}
"""

JS = """
async function post(path, data, card){
  const r = await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
  if(!r.ok){alert('save failed: '+await r.text());return}
  card.classList.add('done');
  card.querySelector('.decided').textContent = '✓ ' + (data.label||data.decision) + ' — saved';
  const n=document.querySelectorAll('.card:not(.done)').length, t=document.querySelectorAll('.card').length;
  document.getElementById('left').textContent=n; document.querySelector('.bar i').style.width=(100*(t-n)/t)+'%';
}
function decide(btn,decision,pick){const c=btn.closest('.card');
  post('/decide',{row_id:c.dataset.id,decision,pick_json:pick?JSON.stringify(pick):'',label:btn.textContent.trim()},c)}
function pick(btn){decide(btn,'pick',JSON.parse(btn.dataset.cand))}
function toggleFix(btn){btn.closest('.card').querySelector('form.fix').classList.toggle('open')}
function fix(ev,form){ev.preventDefault();const c=form.closest('.card');
  post('/edit',{row_id:c.dataset.id,title:form.title.value,author:form.author.value,label:'corrected'},c)}
"""


def esc(s): return html.escape(str(s or ""), quote=True)


def photo_link(photo, drive):
    if (PHOTOS / f"{photo}_small.jpg").exists():
        return f'<a href="/photo/{esc(photo)}" target="_blank">view photo</a>'
    if photo in drive:
        return f'<a href="https://drive.google.com/file/d/{esc(drive[photo])}/view" target="_blank">photo in Drive</a>'
    return ""


def card(b, r, ov, drive):
    rid_ = rid(b)
    status = (r or {}).get("status") or "unresolved"
    cands = json.loads((r or {}).get("candidates") or "[]")
    cand_html = "".join(f"""
      <div class="cand"><div class="cv">
        {f'<img loading="lazy" src="{esc(c["cover_url"])}" alt="" onerror="this.outerHTML=&#39;<div class=ph></div>&#39;">' if c.get("cover_url") else '<div class="ph"></div>'}
        <div><b>{esc(c["title"])}</b><small>{esc(c["author"])}</small>
        <small>{esc(c["year"])} · {esc(c["source"])}</small><span class="sc">score {c["score"]:.2f}</span></div></div>
        <button {'class="primary"' if i == 0 else ''} data-cand="{esc(json.dumps(c))}" onclick="pick(this)">Use this</button>
      </div>""" for i, c in enumerate(cands)) or '<p class="note">No candidates found.</p>'
    done = ""
    if ov:
        done = f'✓ already decided: {esc(ov["decision"])} ({esc(ov["decided_at"])})'
    return f"""
<section class="card{' done' if ov else ''}" data-id="{esc(rid_)}">
  <div class="read">
    <h2>{esc(b['title'])}</h2><div class="by">{esc(b['author'])}</div>
    <div class="chips"><span class="chip {esc(b['confidence'])}">spine: {esc(b['confidence'])}</span>
      <span class="chip {esc(status)}">lookup: {esc(status)}</span></div>
    <div class="note">{esc(b['photo'])} · {esc(b['stack'])} #{esc(b['position'])} · {photo_link(b['photo'], drive)}</div>
    {f'<div class="note">{esc(b["notes"])}</div>' if b["notes"] else ''}
    <div class="acts">
      <button onclick="decide(this,'no-match')" title="Real book, just not in Open Library">Not listed — keep as read</button>
      <button onclick="decide(this,'not-a-book')">Not a book</button>
      <button onclick="toggleFix(this)">Fix spine read…</button>
      {'<button onclick="decide(this,&#39;undo&#39;)">Undo</button>' if ov else ''}
    </div>
    <form class="fix" onsubmit="fix(event,this)">
      <input name="title" value="{esc(b['title'])}" placeholder="title">
      <input name="author" value="{esc(b['author'])}" placeholder="author">
      <button class="primary">Save</button></form>
    <div class="decided">{done}</div>
  </div>
  <div class="cands">{cand_html}</div>
</section>"""


def page():
    books, res, ov, drive = load()
    rows = [b for b in books if b["position"] != "0" and (SHOW_ALL or needs_review(b, res.get(rid(b))))]
    left = sum(1 for b in rows if rid(b) not in ov)
    body = "".join(card(b, res.get(rid(b)), ov.get(rid(b)), drive) for b in rows) or \
        '<p class="empty">Nothing to review. 🎉  Run <code>python3 scripts/resolve.py</code> to apply decisions.</p>'
    hint = "" if res else ('<p class="note" style="padding:0 20px">No <code>data/resolved.csv</code> yet — '
                           'run <code>python3 scripts/resolve.py</code> first to get Open Library candidates.</p>')
    pct = 100 * (len(rows) - left) / len(rows) if rows else 100
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Bookshelf Review</title>
<style>{CSS}</style></head><body>
<header><h1>Bookshelf review</h1><span class="count"><b id="left">{left}</b> of {len(rows)} left</span>
<div class="bar"><i style="width:{pct:.0f}%"></i></div>
<a href="/?all={'0' if SHOW_ALL else '1'}">{'queue only' if SHOW_ALL else 'show all books'}</a></header>
{hint}<main>{body}</main><script>{JS}</script></body></html>"""


# ---------------------------------------------------------------- server
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def send(self, code, body, ctype="text/html; charset=utf-8"):
        b = body if isinstance(body, bytes) else body.encode()
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        global SHOW_ALL
        u = urlparse(self.path)
        if u.path == "/":
            q = parse_qs(u.query)
            if "all" in q: SHOW_ALL = q["all"][0] == "1"
            return self.send(200, page())
        if u.path.startswith("/photo/"):
            name = Path(u.path).name
            f = PHOTOS / f"{name}_small.jpg"
            if f.parent == PHOTOS and f.exists():
                return self.send(200, f.read_bytes(), "image/jpeg")
        self.send(404, "not found", "text/plain")

    def do_POST(self):
        try:
            data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            if self.path == "/decide":
                if data["decision"] not in ("pick", "accept", "no-match", "not-a-book", "undo"):
                    raise ValueError("bad decision")
                write_override(data["row_id"], data["decision"], data.get("pick_json", ""))
            elif self.path == "/edit":
                edit_book(data["row_id"], data.get("title", ""), data.get("author", ""))
            else:
                return self.send(404, "not found", "text/plain")
            self.send(200, "ok", "text/plain")
        except Exception as e:
            self.send(400, str(e), "text/plain")


def main():
    global SHOW_ALL
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    SHOW_ALL = a.all
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), H)
    url = f"http://127.0.0.1:{a.port}/"
    print(f"review page: {url}   (Ctrl-C to stop)")
    if not a.no_browser:
        threading.Timer(0.5, webbrowser.open, [url]).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped. next: python3 scripts/resolve.py  (applies your decisions)")


if __name__ == "__main__":
    main()
