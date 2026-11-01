"""The one-book-at-a-time review page (served at / by scripts/review.py).

One book on screen. Left: what is on your shelf (the spine, the shelf photo,
the title and author as read — click to correct). Right: the options, as large
tiles with cover and details, already looked up; your own images (sent with the
bookmark or saved to Downloads) appear above them, auto-cropped and selected.
One click on a tile — or None of these / Not a book / Skip — decides; the
decision is applied at once, the book leaves the queue and the next one
appears, with Undo. Publish sends everything that is ready.

Keys: 1–9 pick a tile · N none of these · B not a book · S skip · U undo.

The page reuses the helpers in review.JS (api, el, lightbox, cropper, auto-crop,
spine view, side window, version banner, actions log).
"""

CSS = r"""
.fx{max-width:1240px;margin:0 auto;padding:18px 20px 120px}
.fhead{position:sticky;top:0;z-index:4;background:var(--bg);border-bottom:1px solid var(--line);
  padding:12px 20px;display:flex;gap:16px;align-items:center;flex-wrap:wrap}
.fhead h1{font:600 19px/1 Georgia,serif;margin:0}
.fhead .prog{flex:1;min-width:160px;display:flex;flex-direction:column;gap:5px}
.fhead .prog .t{font-size:13px;color:var(--mute)}.fhead .prog .t b{color:var(--ink)}
.fhead .prog .bar{height:6px}
.fhead .pub{font-weight:600}.fhead .pub:disabled{opacity:.4;cursor:default}
.fhead details{position:relative}.fhead summary{list-style:none;cursor:pointer;font-size:20px;line-height:1;
  padding:4px 10px;border:1px solid var(--line);border-radius:6px;background:var(--chip)}
.fhead summary::-webkit-details-marker{display:none}
.menu{position:absolute;right:0;top:36px;background:var(--card);border:1px solid var(--line);border-radius:10px;
  box-shadow:0 10px 30px rgba(0,0,0,.15);padding:8px;display:flex;flex-direction:column;gap:4px;min-width:260px;z-index:6}
.menu button,.menu a.mi{text-align:left;width:100%;border:0;background:none;padding:7px 10px;border-radius:6px;
  font-size:14px;color:var(--ink);text-decoration:none;cursor:pointer}
.menu button:hover,.menu a.mi:hover{background:var(--chip)}
.menu hr{border:0;border-top:1px solid var(--line);margin:4px 0}.menu .bmrow{padding:6px 10px;font-size:12px;color:var(--mute)}
.book{display:grid;grid-template-columns:300px 1fr;gap:28px;align-items:start}
@media (max-width:860px){.book{grid-template-columns:1fr}}
.lab{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--mute);margin:0 0 8px}
.shelfside .spinebox{height:340px;display:flex;align-items:center;justify-content:center;background:var(--chip);
  border-radius:8px;overflow:hidden;cursor:zoom-in;margin-bottom:10px;position:relative}
.shelfside .spinebox .vp{position:relative;overflow:hidden}.shelfside .spinebox img{position:absolute;max-width:none}
.shelfside h2{font:600 22px/1.2 Georgia,serif;margin:6px 0 2px}.shelfside .by{color:var(--mute);margin-bottom:6px}
.shelfside .why{font-size:13px;color:var(--acc);margin:8px 0}.shelfside .notes{font-size:12px;color:var(--mute)}
.shelfside .fixlink{font-size:12px;margin-left:6px}
.shelfside form.fix2{display:none;flex-direction:column;gap:6px;margin:8px 0}.shelfside form.fix2.open{display:flex}
.shelfside input,.findrow input{font:inherit;font-size:13px;padding:6px 9px;border:1px solid var(--line);border-radius:6px;
  background:var(--bg);color:var(--ink)}
.tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:14px}
.tile{position:relative;border:2px solid var(--line);border-radius:10px;padding:10px;background:var(--card);cursor:pointer;
  text-align:left;font:inherit;color:var(--ink);display:flex;flex-direction:column;gap:4px;transition:border-color .12s,transform .12s}
.tile:hover,.tile:focus-visible{border-color:var(--acc);transform:translateY(-2px);outline:none}
.tile .n{position:absolute;top:8px;left:8px;background:var(--acc);color:var(--card);border-radius:5px;font-size:12px;
  font-weight:700;padding:1px 7px;z-index:1}
.tile .cv{width:100%;aspect-ratio:2/3;border-radius:5px;background:var(--chip);object-fit:contain;display:block}
.tile .nocv{width:100%;aspect-ratio:2/3;border-radius:5px;background:var(--chip);display:flex;align-items:center;
  justify-content:center;color:var(--mute);font-size:12px}
.tile b{font-size:14px;line-height:1.25}.tile small{color:var(--mute);font-size:12px;display:block}
.tile .use{margin-top:6px;font-size:13px;font-weight:600;color:var(--acc)}
.tile.current{border-color:var(--ok)}.tile .cur{position:absolute;top:8px;right:8px;background:var(--ok);color:var(--card);
  border-radius:5px;font-size:11px;padding:1px 6px;z-index:1}
.tile .ed{position:absolute;bottom:8px;right:8px;font-size:11px;color:var(--mute);background:none;border:0;cursor:pointer;
  text-decoration:underline;padding:2px}
.tile form{display:none;flex-direction:column;gap:5px;margin-top:6px}.tile form.open{display:flex}
.tile form input{font:inherit;font-size:12px;padding:5px 7px;border:1px solid var(--line);border-radius:5px;
  background:var(--bg);color:var(--ink)}
.searching{font-size:13px;color:var(--mute);margin:0 0 10px;min-height:18px}
.outcomes{display:flex;gap:10px;flex-wrap:wrap;margin:18px 0 10px}
.outcomes button{font-size:14px;padding:9px 14px}.outcomes kbd,.tile kbd{font-size:11px;opacity:.7;margin-left:6px}
.findrow{display:flex;gap:8px;flex-wrap:wrap;align-items:center;font-size:13px;color:var(--mute);margin-top:6px}
.findrow input{min-width:220px}
.mine{border:1px dashed var(--acc);border-radius:10px;padding:10px;margin:0 0 14px;display:none}
.mine.open{display:block}.mine .items{display:flex;gap:12px;flex-wrap:wrap}
.mine figure{margin:0;width:130px;font-size:11px;color:var(--mute)}
.mine figure img{width:130px;height:170px;object-fit:contain;background:var(--chip);border-radius:5px;display:block;cursor:zoom-in}
.mine figure label{display:flex;gap:5px;align-items:center;margin-top:4px;color:var(--ink);font-size:12px}
.mine figure .row{display:flex;gap:4px;margin-top:4px}.mine figure .row button{font-size:11px;padding:2px 6px}
.toast{position:fixed;left:50%;bottom:24px;transform:translateX(-50%);background:var(--ink);color:var(--bg);
  padding:10px 16px;border-radius:10px;font-size:14px;display:none;gap:14px;align-items:center;z-index:8;
  box-shadow:0 8px 24px rgba(0,0,0,.25)}
.toast.open{display:flex}.toast button{background:var(--bg);color:var(--ink);border:0;font-weight:600}
.done{text-align:center;padding:80px 20px}.done h2{font:600 26px Georgia,serif}
"""

BODY = r"""
<div class="fhead">
  <h1>Bookshelf</h1>__VERSION__
  <div class="prog"><span class="t" id="counts">Loading…</span><div class="bar"><i id="pbar" style="width:0%"></i></div></div>
  <button class="primary pub" id="pubbtn" onclick="act('publish')" disabled>Publish</button>
  <details id="more"><summary title="More">⋯</summary><div class="menu">
    <button onclick="act('update')">Get latest version &amp; restart</button>
    <button onclick="restartPage()">Restart</button>
    <hr>
    <button onclick="act('photos')">Import shelf photos</button>
    <button onclick="act('retry')">Retry lookups</button>
    <button onclick="act('build')">Rebuild &amp; preview site</button>
    <button onclick="act('test')">Run tests</button>
    <a class="mi" href="/site/" target="_blank">Open site preview</a>
    <a class="mi" href="/list">Old list view</a>
    <hr>
    <div class="bmrow">Drag to your bookmarks bar once:</div>
    <div class="bmrow">__BOOKMARK__</div>
    <div class="bmrow">On Google Images, click a picture, then the bookmark — it arrives here.</div>
  </div></details>
  <div id="newver" class="newver"></div>
</div>
<main class="fx" id="fx"><p class="searching">Loading…</p></main>
<div class="toast" id="toast"><span id="toastmsg"></span><button onclick="undoLast()">Undo <kbd>U</kbd></button></div>
"""

JS = r"""
/* ================= one book at a time ================= */
const F = {cur: null, last: null, mine: [], searched: {}};

async function call(path, body){
  const r = await api(path, body || {});
  const t = await r.text();
  if(!r.ok) throw new Error(t);
  try { return JSON.parse(t) } catch(e) { return t }
}
function setCounts(c){
  const done = c.total - c.to_review;
  document.getElementById('counts').innerHTML =
    '<b>' + c.to_review + '</b> to review · <b>' + c.ready + '</b> ready to publish · ' + c.published + ' published';
  document.getElementById('pbar').style.width = (100 * done / Math.max(1, c.total)) + '%';
  const pb = document.getElementById('pubbtn');
  pb.disabled = !c.ready; pb.textContent = c.ready ? 'Publish ' + c.ready : 'Publish';
}
async function nextBook(after){
  try { render(await call('/api/next', {after: after || ''})) }
  catch(e){ document.getElementById('fx').innerHTML = '<p class="searching">Could not load: ' + e.message + '</p>' }
}
async function showBook(row_id){ render(await call('/api/book', {row_id})) }

function render(d){
  setCounts(d.counts);
  const fx = document.getElementById('fx');
  if(!d.book){
    F.cur = null;
    fx.innerHTML = '<div class="done"><h2>Nothing left to review 🎉</h2><p>' +
      (d.counts.ready ? d.counts.ready + ' decisions are ready — press <b>Publish</b> to put them on the site.'
                      : 'Everything is published.') + '</p></div>';
    return;
  }
  const b = d.book; F.cur = d; F.mine = [];
  fx.replaceChildren();
  const wrap = el('div', {class: 'book'});

  /* ---- left: on your shelf ---- */
  const left = el('section', {class: 'shelfside'});
  left.append(el('p', {class: 'lab'}, 'On your shelf'));
  if(d.spine && d.spine.box){
    const sb = el('div', {class: 'spinebox', title: 'Click to enlarge'});
    left.append(sb); drawSpine(sb, d.spine.small, d.spine.box);
    sb.onclick = () => spineView(d.spine.big, d.spine.box, d.spine.cap);
  }
  const h = el('h2', null, b.title);
  const fixl = el('a', {href: '#', class: 'fixlink'}, '✎ correct');
  const fixf = el('form', {class: 'fix2'});
  const ti = el('input', {name: 'title', placeholder: 'title'}); ti.value = b.title;
  const au = el('input', {name: 'author', placeholder: 'author'}); au.value = b.author;
  const sv = el('button', {class: 'primary'}, 'Save and look it up again');
  fixf.append(ti, au, sv);
  fixl.onclick = e => { e.preventDefault(); fixf.classList.toggle('open'); ti.focus() };
  fixf.onsubmit = async e => { e.preventDefault();
    await api('/edit', {row_id: b.row_id, title: ti.value, author: au.value});
    F.searched[b.row_id] = true; await showBook(b.row_id); lookFurther('', '', false) };
  const by = el('div', {class: 'by'}, b.author); by.append(fixl);
  left.append(h, by, fixf);
  if(b.why) left.append(el('div', {class: 'why'}, b.why));
  if(b.notes) left.append(el('div', {class: 'notes'}, b.notes));
  const shelf = el('div'); shelf.innerHTML = d.shelf_html || ''; left.append(shelf);

  /* ---- right: which one is it? ---- */
  const right = el('section');
  right.append(el('p', {class: 'lab'}, b.unreadable ? 'What is it?' : 'Which one is it?'));
  const mine = el('div', {class: 'mine'}); right.append(mine); F.mineBox = mine;
  const status = el('p', {class: 'searching'}); right.append(status); F.status = status;
  const tiles = el('div', {class: 'tiles'}); right.append(tiles); F.tiles = tiles;
  drawTiles(b.candidates, b.current);

  const out = el('div', {class: 'outcomes'});
  const none = el('button', null, b.unreadable ? 'Keep as read' : 'None of these — keep as read'); none.append(el('kbd', null, 'N'));
  none.onclick = () => choose('no-match', null, 'kept as read');
  const nab = el('button', null, 'Not a book'); nab.append(el('kbd', null, 'B'));
  nab.onclick = () => choose('not-a-book', null, 'not a book');
  const sk = el('button', null, 'Skip for now'); sk.append(el('kbd', null, 'S'));
  sk.onclick = skipBook;
  out.append(none, nab, sk); right.append(out);

  const find = el('div', {class: 'findrow'});
  const g = el('a', {href: d.google_url, target: '_blank', rel: 'noopener'}, 'Google Images ↗');
  g.onclick = () => { F.linkAt = Date.now()/1000 - 5; return openGoogle(g) };
  const q = el('input', {placeholder: 'ISBN or other words to search'});
  const go = el('button', null, 'Search');
  const doSearch = () => { const v = q.value.trim(); if(!v) return;
    const isbn = /^[0-9xX\- ]{10,17}$/.test(v) ? v : ''; lookFurther(isbn ? '' : v, isbn) };
  go.onclick = doSearch; q.onkeydown = e => { if(e.key === 'Enter') doSearch() };
  const dl = el('a', {href: '#'}, 'Check Downloads');
  dl.onclick = e => { e.preventDefault(); showMine(0, false) };
  find.append('Find more:', g, q, go, '·', dl);
  right.append(find);

  wrap.append(left, right); fx.append(wrap);
  for(const img of d.own || []) addMine({own: true, url: img.url, kind: img.kind, source: img.source});
  if(d.auto_find && !F.searched[b.row_id]) lookFurther('', '', true);
  window.scrollTo(0, 0);
  if(d.next) call('/api/warm', {row_id: d.next}).catch(() => {});      /* look the next book up in advance */
}

function drawTiles(list, current){
  const tiles = F.tiles; tiles.replaceChildren();
  F.cands = list;
  list.slice(0, 9).forEach((c, i) => tiles.append(optTile(c, i, current && i === 0)));
  if(!list.length) F.status.textContent = F.status.textContent || 'No options found yet — try Find more below, or keep as read.';
}
function optTile(c, i, isCurrent){
  const t = el('div', {class: 'tile' + (isCurrent ? ' current' : ''), tabindex: '0', role: 'button'});
  t.append(el('span', {class: 'n'}, String(i + 1)));
  if(isCurrent) t.append(el('span', {class: 'cur'}, 'current match'));
  if(c.cover_url){ const im = el('img', {class: 'cv', src: c.cover_url, loading: 'lazy', alt: ''});
    im.onerror = () => im.replaceWith(el('div', {class: 'nocv'}, 'no cover')); t.append(im) }
  else t.append(el('div', {class: 'nocv'}, 'no cover'));
  t.append(el('b', null, c.title), el('small', null, c.author));
  const line = [c.publisher, c.year].filter(Boolean).join(' · '); if(line) t.append(el('small', null, line));
  if(c.isbn) t.append(el('small', null, 'ISBN ' + c.isbn));
  t.append(el('span', {class: 'use'}, isCurrent ? 'Yes, this one' : 'This one'));
  const ed = el('button', {class: 'ed', type: 'button'}, 'edit');
  const f = el('form');
  for(const [k, label] of [['title','title'],['author','author'],['year','year'],['isbn','ISBN']]){
    const inp = el('input', {name: k, placeholder: label}); inp.value = c[k] || ''; f.append(inp) }
  const okb = el('button', {class: 'primary'}, 'Use with these details'); f.append(okb);
  ed.onclick = e => { e.stopPropagation(); f.classList.toggle('open') };
  f.onclick = e => e.stopPropagation();
  f.onsubmit = e => { e.preventDefault();
    choose('pick', Object.assign({}, c, {title: f.title.value, author: f.author.value, year: f.year.value,
                                          isbn: f.isbn.value, edited: true}), 'chosen (edited)') };
  t.append(ed, f);
  const pick = () => choose('pick', c, c.title);
  t.onclick = pick; t.onkeydown = e => { if(e.key === 'Enter') pick() };
  return t;
}

async function lookFurther(q, isbn, gentle){
  const d = F.cur; if(!d) return; const row = d.book.row_id;
  F.status.textContent = isbn ? 'Looking up the ISBN…' : q ? 'Searching…' : 'Looking further…';
  let found = [];
  try { found = await call('/search', {row_id: row, q: q || '', isbn: isbn || '', gentle: !!gentle}) } catch(e) {}
  if(!F.cur || F.cur.book.row_id !== row) return;
  F.searched[row] = true;
  const key = c => c.work_id || c.gb_id || (c.title + '|' + c.author);
  const old = F.cands || [], seen = new Set(old.map(key));
  const fresh = found.filter(c => !seen.has(key(c)));
  let merged;
  if(isbn || q){ const got = new Set(found.map(key)); merged = found.concat(old.filter(c => !got.has(key(c)))) }
  else {
    const keep = d.book.current && old.length ? [old[0]] : [];       /* the current match stays first */
    merged = keep.concat(old.slice(keep.length).concat(fresh).sort((a, b) => (b.score || 0) - (a.score || 0)));
  }
  drawTiles(merged, d.book.current && !(isbn || q));
  F.status.textContent = fresh.length ? fresh.length + ' more found.' : (isbn || q) ? 'Nothing new found.' : '';
}

/* ---- your own images: from the bookmark or Downloads, auto-cropped, used on decide ---- */
async function showMine(since, quiet){
  if(!F.cur) return;
  let files = [];
  try { files = await call('/downloads', {since: since || 0}) } catch(e) { if(!quiet) alert(e.message); return }
  if(!files.length){ if(!quiet){ F.status.textContent = 'No new images in Downloads.' } return }
  for(const f of files) if(f.showable && !F.mine.some(m => m.name === f.name)) addMine({name: f.name, source: f.source});
}
function addMine(m){
  const box = F.mineBox; if(!box.classList.contains('open')){
    box.replaceChildren(el('p', {class: 'lab'}, 'Your images — used for this book when you choose'), el('div', {class: 'items'}));
    box.classList.add('open') }
  const items = box.querySelector('.items');
  const fig = el('figure'); items.append(fig); F.mine.push(m); m.fig = fig;
  const im = el('img', {alt: ''});
  const use = el('input', {type: 'checkbox'}); use.checked = true; m.use = use;
  const kind = el('button', {type: 'button'}); const setK = k => { m.kind = k; kind.textContent = k === 'spine' ? 'Spine' : 'Cover' };
  setK(m.kind || 'cover'); kind.onclick = () => setK(m.kind === 'cover' ? 'spine' : 'cover');
  const lab = el('label'); lab.append(use, m.own ? 'Already saved' : 'Use it');
  const rc = el('button', {type: 'button'}, 'Re-crop');
  const row = el('div', {class: 'row'}); row.append(kind, rc);
  fig.append(im, lab, row);
  if(m.source) fig.append(el('div', null, 'from ' + m.source));
  if(m.own){ im.src = m.url; use.checked = false; use.disabled = true; rc.remove(); kind.disabled = true; return }
  const src = '/downloads/' + encodeURIComponent(m.name);
  im.onload = () => { if(m.loaded) return; m.loaded = true;
    setK(im.naturalHeight > 2.6 * im.naturalWidth ? 'spine' : 'cover');
    const r = suggestRect(im, m.kind); m.sug = r;
    if(r){ m.crop = cropURL(im, r); setK(r.h > 2.6 * r.w ? 'spine' : 'cover'); im.src = m.crop } };
  im.src = src;
  const doCrop = () => openCropper(src, m.name, (url, w, h) => { m.crop = url; im.src = url; setK(h > 2.6 * w ? 'spine' : 'cover') }, m.sug);
  rc.onclick = doCrop; im.onclick = doCrop;
}
window.addEventListener('focus', () => { if(F.cur && F.linkAt) showMine(F.linkAt, true) });

/* ---- deciding ---- */
async function choose(decision, pick, label){
  const d = F.cur; if(!d || F.busy) return; F.busy = true;
  const row = d.book.row_id;
  try {
    for(const m of F.mine) if(!m.own && m.use.checked)
      await call('/attach', {row_id: row, name: m.name, kind: m.kind, data: m.crop || ''});
    await call('/api/decide', {row_id: row, decision, pick_json: pick ? JSON.stringify(pick) : ''});
    F.last = {row_id: row, title: d.book.title};
    toast('Saved: ' + d.book.title + ' → ' + label);
    F.linkAt = 0;
    await nextBook(row);
  } catch(e) { alert('Not saved: ' + e.message) }
  finally { F.busy = false }
}
async function skipBook(){ const d = F.cur; if(!d) return;
  await call('/api/skip', {row_id: d.book.row_id}); nextBook(d.book.row_id) }
async function undoLast(){ if(!F.last) return; const row = F.last.row_id; F.last = null; hideToast();
  await call('/api/undo', {row_id: row}); F.searched[row] = false; showBook(row) }
let toastTimer = null;
function toast(msg){ const t = document.getElementById('toast'); document.getElementById('toastmsg').textContent = msg;
  t.classList.add('open'); clearTimeout(toastTimer); toastTimer = setTimeout(hideToast, 9000) }
function hideToast(){ document.getElementById('toast').classList.remove('open') }

/* ---- the spine, cropped from the shelf photo ---- */
function drawSpine(box, src, b){
  const im = new Image(); im.onload = () => {
    const W = im.naturalWidth, H = im.naturalHeight, bw = b[2]-b[0], bh = b[3]-b[1];
    const x0 = Math.max(0, b[0]-bw*0.15), x1 = Math.min(1, b[2]+bw*0.15), y0 = Math.max(0, b[1]-bh*0.02), y1 = Math.min(1, b[3]+bh*0.02);
    const rw = (x1-x0)*W, rh = (y1-y0)*H, k = Math.min(280/rw, 330/rh);
    const vp = el('div', {class: 'vp'}); vp.style.width = rw*k + 'px'; vp.style.height = rh*k + 'px';
    Object.assign(im.style, {width: W*k + 'px', height: H*k + 'px', left: (-x0*W*k) + 'px', top: (-y0*H*k) + 'px'});
    vp.append(im); box.replaceChildren(vp) };
  im.onerror = () => box.remove();
  im.src = src;
}

/* ---- keys ---- */
document.addEventListener('keydown', e => {
  if(e.target.closest && e.target.closest('input,textarea,form')) return;
  if(document.querySelector('#crop.open, #lb.open, #sv.open')) return;
  if(e.metaKey || e.ctrlKey || e.altKey) return;
  const k = e.key.toLowerCase();
  if(/^[1-9]$/.test(k)){ const c = (F.cands || [])[Number(k) - 1]; if(c){ e.preventDefault(); choose('pick', c, c.title) } }
  else if(k === 'n') choose('no-match', null, 'kept as read');
  else if(k === 'b') choose('not-a-book', null, 'not a book');
  else if(k === 's') skipBook();
  else if(k === 'u') undoLast();
});
document.addEventListener('click', e => { const m = document.getElementById('more');
  if(m && m.open && !m.contains(e.target)) m.open = false });

nextBook('');
"""


def page(css: str, js: str, token: str, version_html: str, bookmark_html: str, port: int = 0, favicon: str = "") -> str:
    body = BODY.replace("__VERSION__", version_html).replace("__BOOKMARK__", bookmark_html)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>📚 Bookshelf · {port}</title>{favicon}
<style>{css}{CSS}</style></head><body data-token="{token}">
{body}
<div id="lb" class="lb" onclick="lbClick(event)"><span class="lbwrap"><img alt=""><div class="lbbox"></div></span><div class="lbcap"></div></div>
<div id="sv" class="sv" onclick="if(event.target===this)closeSpine()"><div class="cbar"><b class="svcap"></b></div>
<div class="svstage"><div class="svport"><img alt=""><div class="svbox"></div></div></div>
<div class="cbar"><button type="button" onclick="turnSpine()">Turn to read ↺</button>
<button type="button" onclick="closeSpine()">Close</button></div></div>
<div id="crop" class="crop"><div class="cbar"><b class="ctitle"></b> · <span id="cropsize"></span></div>
<div class="stage"><canvas></canvas><div class="sel"></div></div>
<div class="cbar"><button type="button" onclick="rotateCrop()">Rotate ↻</button>
<button type="button" class="primary" onclick="finishCrop(false)">Use crop</button>
<button type="button" onclick="finishCrop(true)">Use whole image</button>
<button type="button" onclick="closeCrop()">Cancel</button></div></div>
<div id="log"><div class="lh"><b>Actions</b><span id="jobstate"></span>
<button onclick="closeLog()">Hide</button></div><pre id="logtext"></pre></div>
<script>{js}
{JS}</script></body></html>"""
