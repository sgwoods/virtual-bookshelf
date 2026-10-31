#!/usr/bin/env python3
"""Local review page for the catalogue — and the control panel for everyday actions.

Usage:  python3 scripts/review.py            # opens http://127.0.0.1:8765
        python3 scripts/review.py --all      # show every row, not just the queue
        python3 scripts/review.py --port 9000 --no-browser

Shows each book that needs a human: weak or missing Open Library match, or a
spine read below high confidence. After those come quick checks: matches that
dropped the spine's subtitle (e.g. "Manifold: Time" → "Manifold"), which are
usually right but sometimes another book. For each card you can
  • pick the right candidate (cover, title, author, year shown),
  • say the best guess looks right,
  • mark it "not listed" (real book, just not in Open Library — keep as read),
  • mark it "not a book",
  • or fix the title/author as read from the spine (writes back to books.csv;
    the next lookup run looks it up again).

Decisions go to data/overrides.csv. The Actions bar runs the steps in
scripts/pipeline.py without leaving the page: get the latest from GitHub,
retry lookups, apply decisions, rebuild and preview the site, run the tests,
save and push the data on a review branch — or Finish, which does apply →
build → test → push in one go and gives the pull-request link.

Standard library only. Binds to 127.0.0.1, so only this Mac can reach it.
Requests must carry the page's per-session token and a localhost Host header,
so other websites open in the browser cannot drive these actions.
"""
from __future__ import annotations

import argparse, csv, html, json, secrets, sys, threading, time, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote_plus, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline                                    # noqa: E402
import resolve                                     # noqa: E402
from resolve import clean_title, norm              # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BOOKS = ROOT / "data/books.csv"
RESOLVED = ROOT / "data/resolved.csv"
OVERRIDES = ROOT / "data/overrides.csv"
DRIVE = ROOT / "data/drive_files.tsv"
PHOTOS = ROOT / "photos/jpg"
OV_FIELDS = ["row_id", "decision", "pick_json", "note", "decided_at"]
SITE = ROOT / "_site"
LOCK = threading.Lock()
SHOW_ALL = False
TOKEN = secrets.token_urlsafe(24)       # per run; required on every POST
PORT = 8765
JOB = {"action": "", "running": False, "ok": None, "log": [], "started": 0.0}
JOB_LOCK = threading.Lock()
ACTIONS = {           # button → (label, pipeline step, reload cards afterwards)
    "update":  ("Get latest",        "update",  True),
    "retry":   ("Retry lookups",     "retry",   True),
    "apply":   ("Apply decisions",   "apply",   True),
    "build":   ("Rebuild site",      "build",   False),
    "test":    ("Run tests",         "test",    False),
    "save":    ("Save & push",       "save",    True),
    "finish":  ("Finish",            "finish",  True),
}


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


def subtitle_dropped(spine_title: str, match_title: str) -> bool:
    """The spine title has a subtitle that the matched title leaves out.

    "Outliers: The Story of Success" → "Outliers" is fine; "Serenity: Better
    Days" → "Serenity" is another book. Only a person can tell, so these are
    shown as quick checks rather than demoted automatically."""
    ct = clean_title(spine_title or "")
    if ":" not in ct or not match_title:
        return False
    sub = norm(ct.split(":", 1)[1])
    return len(sub) >= 4 and sub not in norm(clean_title(match_title))


def quick_check(b, r):
    return (b["position"] != "0" and b["confidence"] in ("high", "checked")
            and (r or {}).get("status") == "matched"
            and subtitle_dropped(b["title"], (r or {}).get("match_title", "")))


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
display:grid;grid-template-columns:300px 1fr;gap:20px;transition:opacity .25s}
.card.done{opacity:.35}
@media (max-width:820px){.card{grid-template-columns:1fr}}
.read h2{font:600 17px/1.25 Georgia,serif;margin:0 0 4px}.read .by{color:var(--mute);margin-bottom:8px}
.chips{display:flex;gap:6px;flex-wrap:wrap;margin:6px 0}.chip{background:var(--chip);border-radius:99px;
padding:2px 9px;font-size:12px;color:var(--mute)}.chip.low,.chip.none{color:var(--bad)}
.chip.medium,.chip.weak{color:var(--warn)}.chip.skipped{color:var(--mute)}
.note{font-size:13px;color:var(--mute)}a{color:var(--acc)}
.cands{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:12px;align-content:start}
.cand{border:1px solid var(--line);border-radius:8px;padding:10px;display:flex;gap:8px;flex-direction:column}
.cand .cover{width:100%;aspect-ratio:2/3;max-height:260px;border-radius:4px;background:var(--chip);
object-fit:contain;cursor:zoom-in;display:block}
.cand .ph{width:100%;height:90px;border-radius:4px;background:var(--chip);display:flex;
align-items:center;justify-content:center;color:var(--mute);font-size:12px}
.cand b{font-size:14px;line-height:1.25;display:block}
.cand small{color:var(--mute);font-size:12px;display:block}.sc{font-size:11px;color:var(--mute)}
.cand .row{display:flex;gap:6px}.cand .row button{flex:1}
.cands .more{grid-column:1/-1;font-size:13px;color:var(--mute);margin:0}
.shelf{margin:10px 0 4px}.shelf img{width:100%;max-height:230px;object-fit:contain;border-radius:6px;
background:var(--chip);cursor:zoom-in;display:block}.shelf .cap{font-size:12px;color:var(--mute);margin-top:4px}
form.more,form.details,form.edit{display:none;flex-direction:column;gap:6px;margin-top:8px}
form.more.open,form.details.open,form.edit.open{display:flex}
form.more input,form.details input,form.edit input{font:inherit;font-size:13px;padding:5px 8px;
border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--ink)}
.lb{position:fixed;inset:0;z-index:10;background:rgba(0,0,0,.82);display:none;align-items:center;
justify-content:center;overflow:auto;cursor:zoom-out}.lb.open{display:flex}
.lb img{max-width:96vw;max-height:94vh;object-fit:contain;cursor:zoom-in;background:#222}
.lb.zoom{align-items:flex-start;justify-content:flex-start}.lb.zoom img{max-width:none;max-height:none;cursor:zoom-out}
.lb .lbcap{position:fixed;left:0;right:0;bottom:0;padding:8px 14px;color:#eee;font-size:13px;
background:rgba(0,0,0,.55);pointer-events:none}
button{font:inherit;font-size:13px;border:1px solid var(--line);background:var(--chip);color:var(--ink);
border-radius:6px;padding:5px 10px;cursor:pointer}button:hover{border-color:var(--acc)}
button.primary{background:var(--acc);color:var(--card);border-color:var(--acc)}
.acts{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}
form.fix{display:none;gap:6px;margin-top:8px;flex-wrap:wrap}form.fix.open{display:flex}
form.fix input{font:inherit;font-size:13px;padding:5px 8px;border:1px solid var(--line);border-radius:6px;
background:var(--bg);color:var(--ink);flex:1;min-width:140px}
.empty{text-align:center;color:var(--mute);padding:60px 0}.decided{font-size:13px;color:var(--ok);margin-top:6px}
.chip.check{color:var(--acc)}h3.sect{font:600 15px/1.3 Georgia,serif;margin:26px 0 4px}
p.sect{margin:0 0 14px;color:var(--mute);font-size:13px}
.tools{width:100%;display:flex;gap:6px;flex-wrap:wrap;align-items:center;font-size:13px}
.tools .stat{color:var(--mute);margin-right:auto}.tools .stat b{color:var(--ink);font-weight:600}
.tools button:disabled{opacity:.45;cursor:default}
#log{position:fixed;left:0;right:0;bottom:0;z-index:3;background:var(--card);border-top:1px solid var(--line);
max-height:42vh;display:none;flex-direction:column;box-shadow:0 -6px 18px rgba(0,0,0,.08)}
#log.open{display:flex}#log .lh{display:flex;gap:10px;align-items:center;padding:8px 14px;
border-bottom:1px solid var(--line);font-size:13px}#log .lh b{margin-right:auto}
#log pre{margin:0;padding:10px 14px;overflow:auto;font:12px/1.45 ui-monospace,Menlo,monospace;white-space:pre-wrap}
#log .ok{color:var(--ok)}#log .bad{color:var(--bad)}#log a{word-break:break-all}
body.logopen main{padding-bottom:44vh}
"""

JS = """
const TOKEN = document.body.dataset.token;
function api(path, data){
  return fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-Review-Token':TOKEN},
    body:JSON.stringify(data||{})});
}
async function post(path, data, card){
  const r = await api(path, data);
  if(!r.ok){alert('save failed: '+await r.text());return}
  card.classList.add('done');
  card.querySelector('.decided').textContent = '✓ ' + (data.label||data.decision) + ' — saved';
  const n=document.querySelectorAll('.card:not(.done)').length, t=document.querySelectorAll('.card').length;
  document.getElementById('left').textContent=n; document.querySelector('.bar i').style.width=(100*(t-n)/t)+'%';
}
function decide(btn,decision,pick,label){const c=btn.closest('.card');
  post('/decide',{row_id:c.dataset.id,decision,pick_json:pick?JSON.stringify(pick):'',label:label||btn.textContent.trim()},c)}
function toggleFix(btn){btn.closest('.card').querySelector('form.fix').classList.toggle('open')}
function fix(ev,form){ev.preventDefault();const c=form.closest('.card');
  post('/edit',{row_id:c.dataset.id,title:form.title.value,author:form.author.value,label:'corrected'},c)}

/* ---- candidates: drawn here for both the first lookup and Search harder ---- */
function big(url){return (url||'').replace('-M.jpg','-L.jpg').replace('zoom=1','zoom=0')}
function el(tag, attrs, text){const e=document.createElement(tag);
  for(const k in (attrs||{})) e.setAttribute(k, attrs[k]); if(text!=null) e.textContent=text; return e}
function tile(c, first){
  const t=el('div',{class:'cand'});
  if(c.cover_url){const im=el('img',{class:'cover',loading:'lazy',src:c.cover_url,alt:''});
    im.onclick=()=>lightbox(big(c.cover_url), c.title+' — '+c.author);
    im.onerror=()=>im.replaceWith(el('div',{class:'ph'},'no cover'));
    t.append(im)} else t.append(el('div',{class:'ph'},'no cover'));
  t.append(el('b',null,c.title), el('small',null,c.author),
    el('small',null,[c.year,c.isbn?'ISBN '+c.isbn:'',c.source].filter(Boolean).join(' · ')),
    el('span',{class:'sc'},'score '+Number(c.score||0).toFixed(2)));
  const row=el('div',{class:'row'});
  const use=el('button',first?{class:'primary'}:{},'Use this');
  use.onclick=()=>decide(use,'pick',c);
  const ed=el('button',{title:'Fix the title, author, year or ISBN, then use it'},'Edit & use…');
  ed.onclick=()=>f.classList.toggle('open');
  row.append(use, ed); t.append(row);
  const f=el('form',{class:'edit'});
  for(const [k,label] of [['title','title'],['author','author'],['year','year'],['isbn','ISBN']]){
    const i=el('input',{name:k,placeholder:label}); i.value=c[k]||''; f.append(i)}
  const sv=el('button',{class:'primary'},'Save'); f.append(sv);
  f.onsubmit=ev=>{ev.preventDefault();
    const e=Object.assign({},c,{title:f.title.value,author:f.author.value,year:f.year.value,isbn:f.isbn.value,edited:true});
    decide(sv,'pick',e,'picked (edited)')};
  t.append(f);
  return t;
}
function drawCands(box, list, note){
  box.replaceChildren();
  if(note) box.append(el('p',{class:'more'},note));
  if(!list.length){box.append(el('p',{class:'note'},'No candidates found.'));return}
  list.forEach((c,i)=>box.append(tile(c,i===0)));
}
document.querySelectorAll('.cands').forEach(b=>drawCands(b, JSON.parse(b.dataset.cands||'[]')));

function toggle(btn, cls){btn.closest('.card').querySelector('form.'+cls).classList.toggle('open')}
async function searchMore(btn, own){
  const card=btn.closest('.card'), f=card.querySelector('form.more'), box=card.querySelector('.cands');
  f.classList.add('open');
  const q=own?f.q.value:'', isbn=own?f.isbn.value:'';
  const label=btn.textContent; btn.disabled=true; btn.textContent='Searching…';
  try{
    const r=await api('/search',{row_id:card.dataset.id,q,isbn});
    if(!r.ok){alert(await r.text());return}
    const found=await r.json();
    const old=JSON.parse(box.dataset.cands||'[]');
    const key=c=>c.work_id||c.gb_id||(c.title+'|'+c.author);
    const seen=new Set(found.map(key));
    const all=found.concat(old.filter(c=>!seen.has(key(c))));
    box.dataset.cands=JSON.stringify(all);
    drawCands(box, all, found.length+' found by '+(isbn?'ISBN':q?'your search':'a wider search')+
      ' (best first); earlier candidates follow.');
  } finally {btn.disabled=false; btn.textContent=label}
}
function details(ev, f){ev.preventDefault();
  const d={title:f.title.value,author:f.author.value,year:f.year.value,publisher:f.publisher.value,isbn:f.isbn.value};
  decide(f.querySelector('button'),'no-match',d,'not listed (details saved)')}

/* ---- lightbox ---- */
function lightbox(src, cap){
  const lb=document.getElementById('lb'); lb.classList.remove('zoom');
  lb.querySelector('img').src=src; lb.querySelector('.lbcap').textContent=cap||'';
  lb.classList.add('open')}
document.addEventListener('keydown',e=>{if(e.key==='Escape')document.getElementById('lb').classList.remove('open')});
function lbClick(e){const lb=document.getElementById('lb');
  if(e.target.tagName==='IMG'){lb.classList.toggle('zoom');return}
  lb.classList.remove('open')}

/* ---- actions bar ---- */
const CONFIRM = {
  save:'Apply your decisions, then commit the review data and push it to GitHub on a review branch?',
  finish:'Apply decisions, rebuild, run tests, then commit and push the data on a review branch?',
  update:'Switch to main and pull the latest from GitHub?'};
let polling = null;
async function act(name){
  if(CONFIRM[name] && !confirm(CONFIRM[name])) return;
  const r = await api('/run',{action:name});
  if(!r.ok){alert(await r.text());return}
  openLog(); poll();
}
function openLog(){document.getElementById('log').classList.add('open');document.body.classList.add('logopen')}
function closeLog(){document.getElementById('log').classList.remove('open');document.body.classList.remove('logopen')}
function linkify(t){return t.replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))
  .replace(/(https:\\/\\/github\\.com\\/[^\\s]+)/g,'<a href="$1" target="_blank">$1</a>')}
async function poll(){
  clearTimeout(polling);
  const j = await (await fetch('/job')).json();
  document.querySelectorAll('.tools button').forEach(b=>b.disabled=j.running);
  const st = document.getElementById('jobstate');
  st.textContent = j.running ? (j.label+' — running…') : j.action ? (j.label+(j.ok?' — done':' — failed')) : '';
  st.className = j.running ? '' : (j.ok ? 'ok' : 'bad');
  const pre = document.getElementById('logtext');
  pre.innerHTML = linkify(j.log.join('\\n'));
  pre.scrollTop = pre.scrollHeight;
  if(j.running){polling=setTimeout(poll,800);return}
  if(j.ok && j.action==='build') window.open('/site/','_blank');
  if(j.ok && j.reload) setTimeout(()=>location.reload(), 1200);
}
fetch('/job').then(r=>r.json()).then(j=>{if(j.running){openLog();poll()}});
"""


def esc(s): return html.escape(str(s or ""), quote=True)


def shelf_photo(b, drive):
    """The shelf photo this book was read from: a local copy if there is one,
    otherwise Drive's thumbnail (shown because the browser is signed in to
    Google; the photos themselves stay private in Drive)."""
    photo = b["photo"]
    if (PHOTOS / f"{photo}_small.jpg").exists():
        small = big = f"/photo/{photo}"
    elif photo in drive:
        fid = drive[photo]
        small = f"https://drive.google.com/thumbnail?id={fid}&sz=w900"
        big = f"https://drive.google.com/thumbnail?id={fid}&sz=w4000"
    else:
        return ""
    where = f"{b['stack']} stack, #{b['position']}" if b["stack"] not in ("shelf", "") else f"#{b['position']} on the shelf"
    cap = f"{photo} — this book is {where}"
    return (f'<div class="shelf"><img loading="lazy" src="{esc(small)}" alt="shelf photo {esc(photo)}" '
            f'onclick="lightbox(&#39;{esc(big)}&#39;, &#39;{esc(cap)}&#39;)" '
            f'onerror="this.parentNode.querySelector(&#39;.cap&#39;).textContent=&#39;Shelf photo not available here — {esc(photo)}&#39;;this.remove()">'
            f'<div class="cap">{esc(cap)} · click to enlarge, click again to zoom</div></div>')


def image_search_url(b) -> str:
    """Google image search for the spine read, to open in a new tab.

    For a person to look at — seller photos often show the ISBN, publisher and
    catalogue number. Nothing is fetched automatically and none of those images
    are used as covers (they belong to the sellers)."""
    q = f"{b['title']} {resolve.first_author(b['author'])}".strip()
    return "https://www.google.com/search?udm=2&q=" + quote_plus(q)


def photo_link(photo, drive):
    if (PHOTOS / f"{photo}_small.jpg").exists():
        return f'<a href="/photo/{esc(photo)}" target="_blank">view photo</a>'
    if photo in drive:
        return f'<a href="https://drive.google.com/file/d/{esc(drive[photo])}/view" target="_blank">photo in Drive</a>'
    return ""


def card(b, r, ov, drive, check=False):
    rid_ = rid(b)
    status = (r or {}).get("status") or "unresolved"
    cands = json.loads((r or {}).get("candidates") or "[]")
    done = ""
    if ov:
        done = f'✓ already decided: {esc(ov["decision"])} ({esc(ov["decided_at"])})'
    return f"""
<section class="card{' done' if ov else ''}" data-id="{esc(rid_)}">
  <div class="read">
    <h2>{esc(b['title'])}</h2><div class="by">{esc(b['author'])}</div>
    <div class="chips"><span class="chip {esc(b['confidence'])}">spine: {esc(b['confidence'])}</span>
      <span class="chip {esc(status)}">lookup: {esc(status)}</span>
      {f'<span class="chip check">check: matched without the subtitle</span>' if check else ''}</div>
    {f'<div class="note">matched to <b>{esc(r.get("match_title"))}</b> · {esc(r.get("match_author"))} {esc(r.get("year"))}</div>' if check else ''}
    <div class="note">{esc(b['photo'])} · {esc(b['stack'])} #{esc(b['position'])} · {photo_link(b['photo'], drive)}
      · <a href="{esc(image_search_url(b))}" target="_blank" rel="noopener"
           title="Look at photos of this book (ISBN, publisher, edition) — opens Google Images">Google Images ↗</a></div>
    {f'<div class="note">{esc(b["notes"])}</div>' if b["notes"] else ''}
    {shelf_photo(b, drive)}
    <div class="acts">
      {(f'<button {"class=primary " if check else ""}onclick="decide(this,&#39;accept&#39;)" '
        f'title="The current best match is the right book">{"Looks right" if check else "Best guess is right"}</button>')
       if cands else ''}
      <button onclick="searchMore(this,false)" title="Wider searches with more results">Search harder</button>
      <button onclick="toggle(this,'more')">Search by text or ISBN…</button>
      <button onclick="decide(this,'no-match')" title="Real book, just not in Open Library">Not listed — keep as read</button>
      <button onclick="toggle(this,'details')">Not listed — add details…</button>
      <button onclick="decide(this,'not-a-book')">Not a book</button>
      <button onclick="toggleFix(this)">Fix spine read…</button>
      {'<button onclick="decide(this,&#39;undo&#39;)">Undo</button>' if ov else ''}
    </div>
    <form class="fix" onsubmit="fix(event,this)">
      <input name="title" value="{esc(b['title'])}" placeholder="title">
      <input name="author" value="{esc(b['author'])}" placeholder="author">
      <button class="primary">Save</button></form>
    <form class="more" onsubmit="event.preventDefault();searchMore(this.querySelector('button'),true)">
      <input name="q" value="{esc(clean_title(b['title']) + ' ' + resolve.first_author(b['author']))}" placeholder="your own search">
      <input name="isbn" placeholder="ISBN from the back cover (surest)" inputmode="numeric">
      <button class="primary">Search</button></form>
    <form class="details" onsubmit="details(event,this)">
      <input name="title" value="{esc(b['title'])}" placeholder="title">
      <input name="author" value="{esc(b['author'])}" placeholder="author">
      <input name="year" placeholder="year">
      <input name="publisher" placeholder="publisher">
      <input name="isbn" placeholder="ISBN">
      <button class="primary">Save as not listed</button></form>
    <div class="decided">{done}</div>
  </div>
  <div class="cands" data-cands="{esc(json.dumps(cands))}"></div>
</section>"""


def tools_bar():
    s = pipeline.status()
    lk = s["lookup"]
    counts = " · ".join(f"{k} <b>{v}</b>" for k, v in sorted(lk.items()))
    unpub = len(s["unpublished"])
    state = (f"branch <b>{esc(s['branch'])}</b> · {s['decisions']} decisions · "
             + (f"<b>{unpub} data file{'s' if unpub != 1 else ''} not yet pushed</b>" if unpub else "all pushed"))
    btns = "".join(
        f'<button {"class=primary " if k == "finish" else ""}onclick="act(\'{k}\')" '
        f'title="{esc(pipeline.STEPS[step].__doc__ or "")}">{esc(label)}</button>'
        for k, (label, step, _) in ACTIONS.items())
    return (f'<div class="tools"><span class="stat">{counts}<br>{state}</span>{btns}'
            f'<button onclick="window.open(\'/site/\',\'_blank\')">Preview site</button></div>')


def page():
    books, res, ov, drive = load()
    live = [b for b in books if b["position"] != "0"]
    if SHOW_ALL:
        rows, checks = live, []
    else:
        rows = [b for b in live if needs_review(b, res.get(rid(b)))]
        checks = [b for b in live if quick_check(b, res.get(rid(b)))]
    every = rows + checks
    left = sum(1 for b in every if rid(b) not in ov)
    body = "".join(card(b, res.get(rid(b)), ov.get(rid(b)), drive) for b in rows)
    if checks:
        body += (f'<h3 class="sect">Quick checks · {len(checks)}</h3><p class="sect">Matched, but without the '
                 'subtitle on the spine. Usually the same book — press <b>Looks right</b> — but sometimes '
                 'another one (<i>Serenity: Better Days</i> is not <i>Serenity</i>).</p>')
        body += "".join(card(b, res.get(rid(b)), ov.get(rid(b)), drive, check=True) for b in checks)
    body = body or '<p class="empty">Nothing to review. 🎉  Press <b>Finish</b> to apply, build, test and push.</p>'
    hint = "" if res else ('<p class="note" style="padding:0 20px">No <code>data/resolved.csv</code> yet — '
                           'run <code>python3 scripts/resolve.py</code> first to get Open Library candidates.</p>')
    pct = 100 * (len(every) - left) / len(every) if every else 100
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Bookshelf Review</title>
<style>{CSS}</style></head><body data-token="{esc(TOKEN)}">
<header><h1>Bookshelf review</h1><span class="count"><b id="left">{left}</b> of {len(every)} left</span>
<div class="bar"><i style="width:{pct:.0f}%"></i></div>
<a href="/?all={'0' if SHOW_ALL else '1'}">{'queue only' if SHOW_ALL else 'show all books'}</a>
{tools_bar()}</header>
{hint}<main>{body}</main>
<div id="lb" class="lb" onclick="lbClick(event)"><img alt=""><div class="lbcap"></div></div>
<div id="log"><div class="lh"><b>Actions</b><span id="jobstate"></span>
<button onclick="closeLog()">Hide</button></div><pre id="logtext"></pre></div>
<script>{JS}</script></body></html>"""


# ---------------------------------------------------------------- jobs
def start_job(name: str) -> str:
    """Run one ACTIONS entry in the background. Returns '' or a reason it can't start."""
    if name not in ACTIONS:
        return "unknown action"
    label, step, reload = ACTIONS[name]
    with JOB_LOCK:
        if JOB["running"]:
            return f"'{JOB['label']}' is still running"
        JOB.update(action=name, label=label, running=True, ok=None, log=[], reload=reload,
                   started=time.time())

    def work():
        def log(line):
            with JOB_LOCK:
                JOB["log"].append(line)
        try:
            ok = pipeline.STEPS[step](log)
        except Exception as e:                      # keep the server alive, report it
            log(f"error: {type(e).__name__}: {e}")
            ok = False
        with JOB_LOCK:
            JOB.update(running=False, ok=ok)
    threading.Thread(target=work, daemon=True).start()
    return ""


def allowed_host(host: str, port: int) -> bool:
    """Only answer to our own address, which blocks DNS-rebinding tricks."""
    return host in (f"127.0.0.1:{port}", f"localhost:{port}")


# ---------------------------------------------------------------- server
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def send(self, code, body, ctype="text/html; charset=utf-8"):
        b = body if isinstance(body, bytes) else body.encode()
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        global SHOW_ALL
        if not allowed_host(self.headers.get("Host", ""), PORT):
            return self.send(403, "forbidden", "text/plain")
        u = urlparse(self.path)
        if u.path == "/job":
            with JOB_LOCK:
                return self.send(200, json.dumps({k: v for k, v in JOB.items() if k != "started"}),
                                 "application/json")
        if u.path in ("/site", "/site/"):
            f = SITE / "index.html"
            if f.exists():
                return self.send(200, f.read_bytes())
            return self.send(404, "No site built yet — press Rebuild site.", "text/plain")
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
        if not allowed_host(self.headers.get("Host", ""), PORT) or \
                not secrets.compare_digest(self.headers.get("X-Review-Token", ""), TOKEN):
            return self.send(403, "forbidden — reload the review page", "text/plain")
        try:
            data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            if self.path == "/run":
                why = start_job(str(data.get("action", "")))
                return self.send(409 if why else 200, why or "started", "text/plain")
            if self.path == "/search":
                books = {rid(b): b for b in csv.DictReader(open(BOOKS, encoding="utf-8"))}
                row = books[data["row_id"]]
                found = resolve.search_more(row, str(data.get("q", "")), str(data.get("isbn", "")))
                return self.send(200, json.dumps(found), "application/json")
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
    global SHOW_ALL, PORT
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    SHOW_ALL, PORT = a.all, a.port
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", a.port), H)
    except OSError:
        sys.exit(f"Port {a.port} is busy — the review page is probably already open in another "
                 f"Terminal window (http://127.0.0.1:{a.port}/). Use that one, or run with "
                 f"--port {a.port + 1}.")
    url = f"http://127.0.0.1:{a.port}/"
    print(f"review page: {url}   (Ctrl-C to stop)")
    if not a.no_browser:
        threading.Timer(0.5, webbrowser.open, [url]).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped. To apply, build, test and push in one go: python3 scripts/pipeline.py finish")


if __name__ == "__main__":
    main()
