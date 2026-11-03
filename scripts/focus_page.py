"""The book editor — the review page's main screen (served at / by scripts/review.py).

A content-editing workflow for one book at a time, built for the first pass
over the shelves and for every book added later:

    queue rail         To review · Check in hand · Waiting to publish · All
                       books, with search; click any book to open it
    on your shelf      the spine cropped from your shelf photo, the title and
                       author as read, why the book needs you
    1 Details          the matches found (Open Library, Google Books) and
                       "as read from the spine"; the chosen one fills title,
                       author, year, publisher and ISBN, each marked with where
                       it came from; edit any field for your copy's edition
    2 Cover            the match's cover, your images, or none
    3 Spine            the crop from your shelf photo, your images, or none
    web pictures       pictures of the book from the web, already searched;
                       one click adds one (tall ones as spine, others as cover);
                       ⌘V pastes any copied picture
    save bar           what will be saved; Save & next, Skip, Check in hand,
                       Not a book; Undo after saving

Every step starts on the best guess, so most books take one key: Enter.
Saved books are published in the background (after five, or when you pause).

Keys: Enter save & next · 1–9 choose a match · 0 as read · S skip ·
H check in hand · B not a book · ← previous book · U undo · / search.

The page reuses the helpers in review.JS (api, el, lightbox, cropper,
auto-crop, spine view, side window, version banner, actions log).
"""

CSS = r"""
body{background:var(--bg)}
.fhead{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line);
  padding:10px 20px;display:flex;gap:14px;align-items:center;flex-wrap:wrap}
.fhead h1{font:600 19px/1 Georgia,serif;margin:0}
.chips{display:flex;gap:6px;flex-wrap:wrap}
.chipb{border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:999px;padding:4px 11px;
  font-size:13px;cursor:pointer}
.chipb b{font-weight:700}.chipb.on{background:var(--acc);color:var(--card);border-color:var(--acc)}
.pubst{font-size:12px;color:var(--mute);display:flex;gap:8px;align-items:center;margin-left:auto}
.pubst .dot{width:8px;height:8px;border-radius:50%;background:var(--ok);display:inline-block}
.pubst .dot.wait{background:var(--warn)}.pubst .dot.run{background:var(--acc);animation:pulse 1s infinite}
.pubst .dot.bad{background:var(--bad)}
@keyframes pulse{50%{opacity:.3}}
.pubst a{cursor:pointer}
.fhead details{position:relative}.fhead summary{list-style:none;cursor:pointer;font-size:20px;line-height:1;
  padding:4px 10px;border:1px solid var(--line);border-radius:6px;background:var(--chip)}
.fhead summary::-webkit-details-marker{display:none}
.menu{position:absolute;right:0;top:36px;background:var(--card);border:1px solid var(--line);border-radius:10px;
  box-shadow:0 10px 30px rgba(0,0,0,.15);padding:8px;display:flex;flex-direction:column;gap:4px;min-width:270px;z-index:6}
.menu button,.menu a.mi,.menu label{text-align:left;width:100%;border:0;background:none;padding:7px 10px;border-radius:6px;
  font-size:14px;color:var(--ink);text-decoration:none;cursor:pointer;display:block}
.menu button:hover,.menu a.mi:hover{background:var(--chip)}
.menu hr{border:0;border-top:1px solid var(--line);margin:4px 0}.menu .bmrow{padding:6px 10px;font-size:12px;color:var(--mute)}

.ed{display:grid;grid-template-columns:240px minmax(0,1fr) 300px;gap:0;align-items:start;min-height:calc(100vh - 60px)}
@media (max-width:1250px){.ed{grid-template-columns:200px minmax(0,1fr)}.web{grid-column:2}}
@media (max-width:860px){.ed{grid-template-columns:1fr}.rail{display:none}.web{grid-column:1}}
.rail{position:sticky;top:58px;height:calc(100vh - 60px);overflow:auto;border-right:1px solid var(--line);padding:12px 10px}
.rail input{width:100%;box-sizing:border-box;font:inherit;font-size:13px;padding:6px 9px;border:1px solid var(--line);
  border-radius:6px;background:var(--card);color:var(--ink);margin-bottom:8px}
.rail .item{display:flex;gap:8px;align-items:center;padding:5px 6px;border-radius:6px;cursor:pointer;font-size:12.5px;line-height:1.25}
.rail .item:hover{background:var(--chip)}.rail .item.cur{background:var(--acc);color:var(--card)}
.rail .item img,.rail .item .ph{width:22px;height:32px;object-fit:cover;border-radius:2px;background:var(--chip);flex:none}
.rail .item small{display:block;opacity:.7}.rail .lab{margin:4px 6px 6px}
.main{padding:16px 24px 140px;min-width:0}
.web{position:sticky;top:58px;height:calc(100vh - 60px);overflow:auto;border-left:1px solid var(--line);padding:12px 14px}

.lab{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--mute);margin:0 0 8px}
.shelfbar{display:flex;gap:16px;align-items:flex-start;padding-bottom:14px;border-bottom:1px solid var(--line);margin-bottom:6px}
.spinebox{width:120px;height:200px;flex:none;display:flex;align-items:center;justify-content:center;background:var(--chip);
  border-radius:6px;overflow:hidden;cursor:zoom-in;position:relative}
.spinebox .vp{position:relative;overflow:hidden}.spinebox img{position:absolute;max-width:none}
.shelfbar h2{font:600 24px/1.2 Georgia,serif;margin:0 0 2px}.shelfbar .by{color:var(--mute)}
.why{display:inline-block;margin-top:8px;font-size:12.5px;background:var(--chip);color:var(--acc);border-radius:5px;padding:3px 8px}
.shelfbar .notes{font-size:12px;color:var(--mute);margin-top:6px}
.shelfbar .photo{margin-left:auto;width:220px;flex:none}.shelfbar .photo .shelf .cap{font-size:11px}
.shelfbar .photo img{max-width:100%}

.step{padding:16px 0;border-bottom:1px solid var(--line)}
.step h3{display:flex;gap:10px;align-items:baseline;margin:0 0 10px;font:600 16px/1.2 -apple-system,system-ui,sans-serif}
.step h3 .num{display:inline-flex;width:22px;height:22px;border-radius:50%;background:var(--acc);color:var(--card);
  align-items:center;justify-content:center;font-size:12px}
.step h3 .sum{font-weight:400;font-size:13px;color:var(--mute)}
.matches{display:flex;flex-direction:column;gap:4px;margin-bottom:12px}
.mrow{display:grid;grid-template-columns:22px 34px 1fr auto;gap:10px;align-items:center;padding:6px 8px;border:1px solid var(--line);
  border-radius:8px;background:var(--card);cursor:pointer;text-align:left;font:inherit;color:var(--ink)}
.mrow:hover{border-color:var(--acc)}.mrow.on{border:2px solid var(--acc);padding:5px 7px}
.mrow .k{font-size:11px;color:var(--mute);text-align:center}
.mrow img,.mrow .ph{width:34px;height:50px;object-fit:cover;border-radius:3px;background:var(--chip)}
.mrow b{font-size:14px}.mrow small{color:var(--mute);font-size:12px}
.mrow .src{font-size:11px;color:var(--mute);text-align:right}
.morerow{display:flex;gap:8px;align-items:center;font-size:13px;color:var(--mute);margin:4px 0 12px;flex-wrap:wrap}
.morerow input{font:inherit;font-size:13px;padding:5px 8px;border:1px solid var(--line);border-radius:6px;background:var(--card);
  color:var(--ink);min-width:240px}
.fields{display:grid;grid-template-columns:90px minmax(0,1fr) 130px;gap:6px 10px;align-items:center;max-width:760px}
.fields label{font-size:12px;color:var(--mute);text-align:right}
.fields input{font:inherit;font-size:14px;padding:6px 9px;border:1px solid var(--line);border-radius:6px;background:var(--card);color:var(--ink)}
.fields input.empty{border-style:dashed}
.srcchip{font-size:11px;border-radius:4px;padding:2px 6px;background:var(--chip);color:var(--mute);justify-self:start;cursor:default}
.srcchip.you{background:var(--acc);color:var(--card)}.srcchip.spine{background:#e8dcc8;color:#5a4320}
.srcchip.hint{cursor:pointer;text-decoration:underline}
.edhint{font-size:12px;color:var(--mute);margin:8px 0 0 100px}
.opts{display:flex;gap:10px;flex-wrap:wrap}
.opt{width:118px;border:2px solid var(--line);border-radius:8px;padding:5px;background:var(--card);cursor:pointer;
  display:flex;flex-direction:column;gap:4px;font:inherit;color:var(--ink);text-align:left;position:relative}
.opt:hover{border-color:var(--acc)}.opt.on{border-color:var(--acc);box-shadow:0 0 0 2px var(--acc)}
.opt img{width:100%;height:150px;object-fit:contain;background:var(--chip);border-radius:4px;display:block}
.opt .none{height:150px;display:flex;align-items:center;justify-content:center;background:var(--chip);border-radius:4px;
  color:var(--mute);font-size:12px;text-align:center;padding:6px}
.opt small{font-size:11px;color:var(--mute);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.opt .tools{display:flex;gap:4px}.opt .tools button{font-size:10.5px;padding:1px 5px}
.opt.pending img{opacity:.75}.opt .badge{position:absolute;top:8px;left:8px;background:var(--ok);color:var(--card);
  font-size:10px;padding:1px 5px;border-radius:4px}
.pubtoggle{font-size:11.5px;color:var(--mute);display:flex;gap:4px;align-items:center}
.opthint{font-size:12px;color:var(--mute);margin-top:8px}

.savebar{position:fixed;bottom:0;left:240px;right:300px;background:var(--card);border-top:1px solid var(--line);
  box-shadow:0 -6px 20px rgba(0,0,0,.06);padding:10px 24px;display:flex;gap:14px;align-items:center;z-index:4}
@media (max-width:1250px){.savebar{left:200px;right:0}}@media (max-width:860px){.savebar{left:0}}
.savebar .cv{width:40px;height:58px;object-fit:cover;border-radius:3px;background:var(--chip);flex:none}
.savebar .what{flex:1;min-width:0;font-size:13px;line-height:1.35}
.savebar .what b{font-size:14.5px}.savebar .what div{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.savebar button{white-space:nowrap}.savebar kbd{font-size:10.5px;opacity:.65;margin-left:5px}
.savebar .primary{font-size:15px;padding:9px 16px}

.webq{display:flex;gap:6px;margin-bottom:6px}.webq input{flex:1;min-width:0;font:inherit;font-size:13px;padding:6px 9px;
  border:1px solid var(--line);border-radius:6px;background:var(--card);color:var(--ink)}
.webgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(82px,1fr));gap:7px}
.webimg{position:relative;padding:0;border:2px solid transparent;border-radius:6px;background:var(--chip);cursor:pointer;
  display:flex;flex-direction:column;overflow:hidden}
.webimg:hover{border-color:var(--acc)}
.webimg img{width:100%;height:112px;object-fit:contain;display:block}
.webimg span{font-size:9.5px;color:var(--mute);padding:1px 4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.webimg.busy{opacity:.5;cursor:progress}.webimg.used{border-color:var(--ok)}
.webimg.used::after{content:'✓';position:absolute;top:3px;right:3px;background:var(--ok);color:var(--card);
  font-size:10px;padding:0 5px;border-radius:4px}
.webimg.failed{opacity:.3}
.webhint{font-size:12px;color:var(--mute);margin:10px 0 0}
.searching{font-size:12.5px;color:var(--mute);margin:4px 0 8px;min-height:16px}

.toast{position:fixed;left:50%;bottom:92px;transform:translateX(-50%);background:var(--ink);color:var(--bg);
  padding:9px 15px;border-radius:10px;font-size:14px;display:none;gap:14px;align-items:center;z-index:8;
  box-shadow:0 8px 24px rgba(0,0,0,.25)}
.toast.open{display:flex}.toast button{background:var(--bg);color:var(--ink);border:0;font-weight:600}
.done{text-align:center;padding:80px 20px}.done h2{font:600 26px Georgia,serif}
"""

BODY = r"""
<div class="fhead">
  <h1>📚 Bookshelf</h1>__VERSION__
  <div class="chips" id="chips"></div>
  <div class="pubst" id="pubst"></div>
  <details id="more"><summary title="More">⋯</summary><div class="menu">
    <button onclick="act('publish')">Publish now</button>
    <label><input type="checkbox" id="autopub" onchange="setAuto(this.checked)"> Publish automatically</label>
    <hr>
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
    <div class="bmrow">Optional bookmark (drag to the bookmarks bar): __BOOKMARK__</div>
  </div></details>
  <div id="newver" class="newver"></div>
</div>
<div class="ed">
  <aside class="rail" id="rail"></aside>
  <main class="main" id="main"><p class="searching">Loading…</p></main>
  <aside class="web" id="web"></aside>
</div>
<div class="savebar" id="savebar"></div>
<div class="toast" id="toast"><span id="toastmsg"></span><button onclick="undoLast()">Undo <kbd>U</kbd></button></div>
"""

JS = r"""
/* ================= the book editor ================= */
const E = {bucket: 'to_review', list: [], hist: [], last: null, busy: false};
const SRC = {openlibrary: 'Open Library', googlebooks: 'Google Books', manual: 'You', spine: 'Spine'};
const FIELDS = [['title','Title'],['author','Author'],['year','Year'],['publisher','Publisher'],['isbn','ISBN']];

async function call(path, body){
  const r = await api(path, body || {});
  const t = await r.text();
  if(!r.ok) throw new Error(t);
  try { return JSON.parse(t) } catch(e) { return t }
}
function key(c){ return c.work_id || c.gb_id || (c.title + '|' + c.author) }

/* ---------- header: buckets and publishing ---------- */
const BUCKETS = [['to_review','To review'],['in_hand','Check in hand'],['ready','Waiting to publish'],['all','All books']];
function drawChips(c){
  const box = document.getElementById('chips'); box.replaceChildren();
  for(const [k, label] of BUCKETS){
    const n = k === 'all' ? c.total : c[k];
    const b = el('button', {class: 'chipb' + (E.bucket === k ? ' on' : ''), type: 'button'});
    b.append(label + ' ', el('b', null, String(n))); b.onclick = () => openBucket(k); box.append(b);
  }
}
function drawPub(p){
  const box = document.getElementById('pubst'); box.replaceChildren();
  const dot = el('span', {class: 'dot' + (p.running ? ' run' : p.error ? ' bad' : p.waiting ? ' wait' : '')});
  let text = p.running ? 'Publishing…' : p.error ? 'Publishing failed — ' + p.error
    : p.waiting ? p.waiting + ' waiting to publish' + (p.auto ? ' (automatic)' : '') : 'All published';
  if(!p.running && !p.waiting && p.last_ok) text += ' · ' + ago(p.last_ok);
  box.append(dot, el('span', null, text));
  if(p.waiting && !p.running){ const a = el('a', null, 'Publish now'); a.onclick = () => act('publish'); box.append(a) }
  document.getElementById('autopub').checked = p.auto;
  drawChips(p.counts); E.counts = p.counts;
}
function ago(t){ const m = Math.round((Date.now()/1000 - t) / 60); return m < 1 ? 'just now' : m + ' min ago' }
async function refreshPub(){ try { drawPub(await call('/api/pubstate')) } catch(e) {} }
async function setAuto(on){ drawPub(await call('/api/autopublish', {on})) }
setInterval(refreshPub, 5000);

/* ---------- queue rail ---------- */
async function openBucket(k){ E.bucket = k; await loadList(); if(E.list.length) openBook(E.list[0].row_id); else drawEmpty() }
async function loadList(q){
  E.list = await call('/api/list', {bucket: E.bucket, q: q || ''});
  drawRail(q);
  if(E.counts) drawChips(E.counts);
}
function drawRail(q){
  const r = document.getElementById('rail'); r.replaceChildren();
  const s = el('input', {placeholder: 'Search all books  ( / )', id: 'search'}); s.value = q || '';
  let t; s.oninput = () => { clearTimeout(t); t = setTimeout(() => loadList(s.value), 250) };
  r.append(s, el('p', {class: 'lab'}, q ? 'Search results' : BUCKETS.find(b => b[0] === E.bucket)[1]));
  for(const it of E.list){
    const row = el('div', {class: 'item' + (E.d && E.d.book && E.d.book.row_id === it.row_id ? ' cur' : '')});
    const im = it.cover_url ? el('img', {src: it.cover_url, loading: 'lazy', alt: ''}) : el('span', {class: 'ph'});
    if(it.cover_url) im.onerror = () => im.replaceWith(el('span', {class: 'ph'}));
    const tx = el('div'); tx.append(it.title); tx.append(el('small', null, it.author + (E.bucket === 'all' || q ? ' · ' + it.state : '')));
    row.append(im, tx); row.onclick = () => { E.hist.push(E.d && E.d.book && E.d.book.row_id); openBook(it.row_id) };
    r.append(row);
  }
  if(!E.list.length) r.append(el('p', {class: 'searching'}, q ? 'No books match.' : 'Nothing here.'));
  if(q) setTimeout(() => { s.focus(); s.setSelectionRange(s.value.length, s.value.length) });
}
function markCurrent(){
  document.querySelectorAll('.rail .item').forEach((x, i) =>
    x.classList.toggle('cur', E.list[i] && E.d && E.d.book && E.list[i].row_id === E.d.book.row_id));
}
function nextInList(after){
  const i = E.list.findIndex(x => x.row_id === after);
  const rest = E.list.filter(x => x.row_id !== after);
  return (i >= 0 ? E.list.slice(i + 1).concat(E.list.slice(0, i)) : rest).map(x => x.row_id)[0];
}

/* ---------- opening a book ---------- */
async function openBook(row_id){
  let d;
  try { d = await call('/api/book', {row_id}) } catch(e) { document.getElementById('main').textContent = 'Could not open: ' + e.message; return }
  E.d = d; E.counts = d.counts; drawChips(d.counts);
  const b = d.book;
  E.matches = (b.candidates || []).slice(0, 9);
  E.mine = (d.own || []).map(o => ({own: true, url: o.url, kind: o.kind, source: o.source, published: o.published}));
  E.fields = {}; E.src = {}; E.base = 'match'; E.sel = 0; E.match = null;
  const dec = b.decided && b.decided.decision !== 'in-hand' ? b.decided : null;
  if(dec && dec.pick && dec.pick.title){                         /* reopening a saved book: show what was saved */
    const p = dec.pick, i = E.matches.findIndex(c => (p.work_id && c.work_id === p.work_id) || (p.gb_id && c.gb_id === p.gb_id));
    if(dec.decision === 'pick' && i < 0) E.matches.unshift({source: p.source, work_id: p.work_id, gb_id: p.gb_id, title: p.title,
      author: p.author, year: p.year, isbn: p.isbn, publisher: p.publisher, cover_url: p.cover_url});
    E.base = dec.decision === 'pick' ? 'match' : 'spine'; E.sel = dec.decision === 'pick' ? Math.max(0, i) : -1;
    E.match = E.base === 'match' ? E.matches[E.sel] : null;
    for(const [k] of FIELDS){ E.fields[k] = p[k] || ''; E.src[k] = (p.sources || {})[k] || (dec.decision === 'pick' ? SRC[p.source] || 'Match' : 'Spine') }
  } else if(E.matches.length && !b.unreadable && b.status !== 'none'){
    useMatch(0, false);
  } else useSpine(false);
  const ownCover = E.mine.find(m => m.kind === 'cover'), ownSpine = E.mine.find(m => m.kind === 'spine');
  E.cover = ownCover && ownCover.published !== false ? {type: 'mine', m: ownCover}
          : (dec && dec.pick && dec.pick.cover === 'none') ? {type: 'none'} : {type: 'match'};
  E.spine = ownSpine ? (ownSpine.published === false && ownSpine.source !== 'your shelf photo' ? {type: 'none'} : {type: 'mine', m: ownSpine})
          : (d.spine && d.spine.local ? {type: 'shelf'} : {type: 'none'});
  E.autoCover = !ownCover;
  if(E.cover.type === 'match' && !(E.base === 'match' && E.match && E.match.cover_url)) E.cover = {type: 'none'};
  drawMain(); drawWeb(); markCurrent(); drawSave();
  document.querySelector('.main').scrollTo && window.scrollTo(0, 0);
  if(d.auto_find && !dec) lookFurther('', '', true);
  const nxt = nextInList(b.row_id); if(nxt) call('/api/warm', {row_id: nxt}).catch(() => {});
}
function drawEmpty(){
  E.d = null;
  const m = document.getElementById('main');
  m.innerHTML = '<div class="done"><h2>' + (E.bucket === 'to_review' ? 'Nothing left to review 🎉' : 'Nothing here') +
    '</h2><p>New books appear in “To review” as they are added. Use search to reopen any book.</p></div>';
  document.getElementById('savebar').replaceChildren(); document.getElementById('web').replaceChildren();
}

/* ---------- step 1: details ---------- */
function useMatch(i, draw = true){
  const c = E.matches[i]; if(!c) return;
  E.base = 'match'; E.sel = i; E.match = c;
  const s = SRC[c.source] || 'Match';
  for(const [k] of FIELDS){ E.fields[k] = String(c[k] || ''); E.src[k] = c[k] ? s : '' }
  if(E.autoCover && E.cover.type !== 'mine') E.cover = {type: c.cover_url ? 'match' : (E.mine.find(m => m.kind === 'cover') ? 'mine' : 'none'),
                                                          m: E.mine.filter(m => m.kind === 'cover').slice(-1)[0]};
  if(draw){ drawMain(); drawSave() }
}
function useSpine(draw = true){
  const b = E.d.book;
  E.base = 'spine'; E.sel = -1; E.match = null;
  E.fields = {title: b.unreadable ? '' : b.title, author: b.author === '?' ? '' : b.author, year: '', publisher: spinePublisher(), isbn: ''};
  E.src = {title: 'Spine', author: 'Spine', year: '', publisher: E.fields.publisher ? 'Spine' : '', isbn: ''};
  if(E.cover && E.cover.type === 'match') E.cover = E.mine.find(m => m.kind === 'cover') ? {type: 'mine', m: E.mine.filter(m => m.kind === 'cover').slice(-1)[0]} : {type: 'none'};
  if(draw){ drawMain(); drawSave() }
}
function spinePublisher(){
  const n = (E.d.book.notes || '').split(/\s+[—–-]\s+|;/)[0].trim();
  return /^[A-Z][\w&.' ]{1,30}$/.test(n) && !/hidden|copy|spine|edge|stack/i.test(n) ? n : '';
}

function drawMain(){
  const d = E.d, b = d.book, m = document.getElementById('main'); m.replaceChildren();
  /* on your shelf */
  const bar = el('div', {class: 'shelfbar'});
  if(d.spine && d.spine.box){ const sb = el('div', {class: 'spinebox', title: 'Click to enlarge'}); bar.append(sb);
    drawSpineCrop(sb, d.spine.small, d.spine.box); sb.onclick = () => spineView(d.spine.big, d.spine.box, d.spine.cap) }
  const info = el('div');
  info.append(el('p', {class: 'lab'}, 'On your shelf — as read'), el('h2', null, b.unreadable ? 'Spine not readable' : b.title),
              el('div', {class: 'by'}, b.author));
  if(b.why) info.append(el('div', {class: 'why'}, b.why));
  if(b.notes) info.append(el('div', {class: 'notes'}, 'Spine notes: ' + b.notes));
  bar.append(info);
  const ph = el('div', {class: 'photo'}); ph.innerHTML = d.shelf_html || ''; bar.append(ph);
  m.append(bar);

  /* 1 details */
  const s1 = el('section', {class: 'step'});
  const h1 = el('h3'); h1.append(el('span', {class: 'num'}, '1'), 'Book details', el('span', {class: 'sum'},
    E.base === 'match' ? 'from ' + (SRC[E.match.source] || 'a match') + ' — check it is your edition' : 'as read from the spine — fill in what you know'));
  s1.append(h1);
  const ms = el('div', {class: 'matches'}); E.matchBox = ms; s1.append(ms); drawMatches();
  const more = el('div', {class: 'morerow'});
  const q = el('input', {placeholder: 'ISBN from the back cover, or other words'});
  const go = el('button', {type: 'button'}, 'Find');
  const doQ = () => { const v = q.value.trim(); if(!v) return; const isbn = /^[0-9xX\- ]{10,17}$/.test(v) ? v : ''; lookFurther(isbn ? '' : v, isbn) };
  go.onclick = doQ; q.onkeydown = e => { if(e.key === 'Enter'){ e.preventDefault(); doQ() } };
  E.status = el('span', {class: 'searching'});
  more.append('Not listed?', q, go, E.status); s1.append(more);
  const f = el('div', {class: 'fields'});
  for(const [k, label] of FIELDS){
    const inp = el('input', {name: k}); inp.value = E.fields[k] || ''; if(!inp.value) inp.classList.add('empty');
    const chip = el('span', {class: 'srcchip'});
    const paint = () => { const s = E.src[k]; chip.textContent = s || (k === 'publisher' && spinePublisher() && !inp.value ? 'Spine says “' + spinePublisher() + '” — use' : 'empty');
      chip.className = 'srcchip' + (s === 'You' ? ' you' : s === 'Spine' ? ' spine' : '') + (!s && k === 'publisher' && spinePublisher() && !inp.value ? ' hint' : '') };
    chip.onclick = () => { if(chip.classList.contains('hint')){ inp.value = spinePublisher(); inp.dispatchEvent(new Event('input')) } };
    inp.oninput = () => { E.fields[k] = inp.value; E.src[k] = 'You'; inp.classList.toggle('empty', !inp.value); paint(); drawSave() };
    paint(); f.append(el('label', null, label), inp, chip);
  }
  s1.append(f, el('p', {class: 'edhint'}, 'Year, publisher and ISBN are for your copy — change them if your edition differs.'));
  m.append(s1);

  /* 2 cover */
  const s2 = el('section', {class: 'step'}); E.coverBox = s2; m.append(s2); drawCover();
  /* 3 spine */
  const s3 = el('section', {class: 'step'}); E.spineBox = s3; m.append(s3); drawSpineStep();
}
function drawMatches(){
  const ms = E.matchBox; ms.replaceChildren();
  E.matches.forEach((c, i) => {
    const r = el('button', {class: 'mrow' + (E.base === 'match' && E.sel === i ? ' on' : ''), type: 'button'});
    const im = c.cover_url ? el('img', {src: c.cover_url, loading: 'lazy', alt: ''}) : el('span', {class: 'ph'});
    if(c.cover_url) im.onerror = () => im.replaceWith(el('span', {class: 'ph'}));
    const t = el('div'); t.append(el('b', null, c.title), el('br'), el('small', null,
      [c.author, c.year, c.publisher, c.isbn ? 'ISBN ' + c.isbn : ''].filter(Boolean).join(' · ')));
    r.append(el('span', {class: 'k'}, String(i + 1)), im, t, el('span', {class: 'src'}, SRC[c.source] || c.source || ''));
    r.onclick = () => useMatch(i); ms.append(r);
  });
  const r = el('button', {class: 'mrow' + (E.base === 'spine' ? ' on' : ''), type: 'button'});
  const t = el('div'); t.append(el('b', null, 'None of these — use what the spine says'), el('br'),
    el('small', null, 'for books no catalogue lists; fill in the details below'));
  r.append(el('span', {class: 'k'}, '0'), el('span', {class: 'ph'}), t, el('span', {class: 'src'}, 'Spine'));
  r.onclick = () => useSpine(); ms.append(r);
}
async function lookFurther(q, isbn, gentle){
  const d = E.d; if(!d) return; const row = d.book.row_id;
  if(E.status) E.status.textContent = isbn ? 'Looking up the ISBN…' : q ? 'Searching…' : 'Looking further…';
  let found = [];
  try { found = await call('/search', {row_id: row, q: q || '', isbn: isbn || '', gentle: !!gentle}) } catch(e) {}
  if(!E.d || E.d.book.row_id !== row) return;
  const seen = new Set(E.matches.map(key));
  const fresh = found.filter(c => !seen.has(key(c)));
  if(isbn || q){ E.matches = fresh.concat(E.matches).slice(0, 9); if(fresh.length) useMatch(0) }
  else E.matches = E.matches.concat(fresh).slice(0, 9);
  drawMatches(); drawSave();
  if(E.status) E.status.textContent = fresh.length ? fresh.length + ' more found.' : (isbn || q) ? 'Nothing new found.' : '';
}

/* ---------- step 2 and 3: cover and spine ---------- */
function drawCover(){
  const s = E.coverBox; s.replaceChildren();
  const h = el('h3'); h.append(el('span', {class: 'num'}, '2'), 'Cover', el('span', {class: 'sum'}, coverSummary())); s.append(h);
  const o = el('div', {class: 'opts'});
  if(E.base === 'match' && E.match && E.match.cover_url)
    o.append(opt(E.cover.type === 'match', E.match.cover_url, 'from ' + (SRC[E.match.source] || 'match'), () => { E.cover = {type: 'match'}; redrawCS() }));
  for(const m of E.mine.filter(m => m.kind === 'cover'))
    o.append(mineOpt(m, E.cover.type === 'mine' && E.cover.m === m, () => { E.cover = {type: 'mine', m}; redrawCS() }));
  o.append(opt(E.cover.type === 'none', '', 'No cover — show the title', () => { E.cover = {type: 'none'}; redrawCS() }));
  s.append(o, el('p', {class: 'opthint'}, 'More covers: click a picture on the right, or paste one with ⌘V.'));
}
function drawSpineStep(){
  const s = E.spineBox; s.replaceChildren(); const d = E.d;
  const h = el('h3'); h.append(el('span', {class: 'num'}, '3'), 'Spine', el('span', {class: 'sum'}, spineSummary())); s.append(h);
  const o = el('div', {class: 'opts'});
  if(d.spine && d.spine.box && d.spine.local){
    const b = opt(E.spine.type === 'shelf', '', 'from your shelf photo', () => { E.spine = {type: 'shelf'}; redrawCS() });
    const box = b.querySelector('.none'); box.textContent = ''; drawSpineCrop(box, d.spine.small, d.spine.box, 108, 146);
    o.append(b);
  }
  for(const m of E.mine.filter(m => m.kind === 'spine'))
    o.append(mineOpt(m, E.spine.type === 'mine' && E.spine.m === m, () => { E.spine = {type: 'mine', m}; redrawCS() }));
  o.append(opt(E.spine.type === 'none', '', 'No spine image', () => { E.spine = {type: 'none'}; redrawCS() }));
  s.append(o);
  if(!(d.spine && d.spine.box)) s.append(el('p', {class: 'opthint'}, 'This spine is not outlined on its shelf photo yet. Tall pictures on the right are added here.'));
  else if(!d.spine.local) s.append(el('p', {class: 'opthint'}, 'Import the shelf photos (⋯ menu) to crop the spine from them.'));
  else s.append(el('p', {class: 'opthint'}, 'Crops of your shelf photos stay private unless you publish them (switch under the picture once saved).'));
}
function opt(on, src, label, pick){
  const b = el('button', {class: 'opt' + (on ? ' on' : ''), type: 'button'});
  if(src){ const im = el('img', {src, alt: ''}); im.onerror = () => im.replaceWith(el('div', {class: 'none'}, 'not available')); b.append(im) }
  else b.append(el('div', {class: 'none'}, label));
  b.append(el('small', null, label)); b.onclick = pick; return b;
}
function mineOpt(m, on, pick){
  const b = opt(on, m.crop || m.url || ('/downloads/' + encodeURIComponent(m.name)), m.own ? 'saved · ' + (m.source || 'yours') : 'new · ' + (m.source || 'yours'), pick);
  if(!m.own) b.classList.add('pending');
  const tools = el('div', {class: 'tools'});
  const flip = el('button', {type: 'button'}, m.kind === 'cover' ? '→ spine' : '→ cover');
  flip.onclick = e => { e.stopPropagation(); if(m.own) return; m.kind = m.kind === 'cover' ? 'spine' : 'cover';
    if(m.kind === 'cover') E.cover = {type: 'mine', m}; else E.spine = {type: 'mine', m}; fixChoices(); redrawCS() };
  if(!m.own) tools.append(flip);
  const rc = el('button', {type: 'button'}, 'Crop');
  rc.onclick = e => { e.stopPropagation();
    const src = m.own ? m.orig || m.url : '/downloads/' + encodeURIComponent(m.name);
    openCropper(src, 'Crop to just this book', (url) => { m.crop = url; m.recrop = m.own; redrawCS() }, m.sug) };
  tools.append(rc); b.append(tools);
  if(m.own){
    const lab = el('label', {class: 'pubtoggle'}); const cb = el('input', {type: 'checkbox'}); cb.checked = m.published !== false;
    cb.onclick = e => e.stopPropagation();
    cb.onchange = async () => { await call('/publish', {row_id: E.d.book.row_id, kind: m.kind, on: cb.checked}); m.published = cb.checked };
    lab.append(cb, 'on the public site'); lab.onclick = e => e.stopPropagation(); b.append(lab);
  }
  return b;
}
function fixChoices(){
  if(E.cover.type === 'mine' && E.cover.m.kind !== 'cover') E.cover = {type: E.match && E.match.cover_url ? 'match' : 'none'};
  if(E.spine.type === 'mine' && E.spine.m.kind !== 'spine') E.spine = {type: E.d.spine && E.d.spine.local ? 'shelf' : 'none'};
}
function redrawCS(){ drawCover(); drawSpineStep(); drawSave() }
function coverSummary(){
  return E.cover.type === 'match' ? 'the match’s cover' : E.cover.type === 'mine' ? 'your picture' + (E.cover.m.source ? ' from ' + E.cover.m.source : '') : 'none — the site shows the title';
}
function spineSummary(){
  return E.spine.type === 'shelf' ? 'cropped from your shelf photo' : E.spine.type === 'mine' ? 'your picture' : 'none';
}

/* your new pictures: from the web column, a paste, or Downloads; auto-cropped */
function addMine(m){
  E.mine.push(m);
  const im = new Image();
  im.onload = () => {
    const tall = im.naturalHeight > 2.6 * im.naturalWidth;
    m.kind = m.kind || (tall ? 'spine' : 'cover');
    const r = suggestRect(im, m.kind); m.sug = r;
    if(r){ m.crop = cropURL(im, r); if(!m.forced) m.kind = r.h > 2.6 * r.w ? 'spine' : 'cover' }
    if(m.kind === 'cover'){ E.cover = {type: 'mine', m}; E.autoCover = false } else E.spine = {type: 'mine', m};
    redrawCS();
  };
  im.onerror = () => { E.mine = E.mine.filter(x => x !== m); alert('That picture could not be opened.') };
  im.src = '/downloads/' + encodeURIComponent(m.name);
}

/* ---------- web pictures column ---------- */
function drawWeb(){
  const d = E.d, box = document.getElementById('web'); box.replaceChildren();
  box.append(el('p', {class: 'lab'}, 'Pictures on the web — click to add'));
  const qrow = el('div', {class: 'webq'});
  const qi = el('input', {placeholder: 'search words'}); qi.value = d.image_q || '';
  const go = el('button', {type: 'button'}, 'Search'); qrow.append(qi, go);
  const note = el('p', {class: 'searching'}); const grid = el('div', {class: 'webgrid'});
  const g = el('a', {href: d.google_url, target: '_blank', rel: 'noopener'}, 'Google Images ↗');
  g.onclick = () => { E.linkAt = Date.now()/1000 - 5; return openGoogle(g) };
  const hint = el('p', {class: 'webhint'});
  hint.append('Tall pictures become the spine, others the cover. Not here? ', g,
              ' — right-click a picture, Copy Image, then ⌘V here.');
  box.append(qrow, note, grid, hint);
  const load = async q => {
    if(!q){ note.textContent = 'Type words to search for.'; return }
    note.textContent = 'Looking for pictures…'; grid.replaceChildren();
    let r; try { r = await call('/api/images', {q}) } catch(e) { note.textContent = 'Could not search: ' + e.message; return }
    if(E.d !== d) return;
    if(!r.results.length){ note.textContent = 'No pictures found' + (r.error ? ' (' + r.error + ')' : '') + '.'; return }
    note.textContent = r.results.length + ' pictures (' + r.source + ')';
    for(const x of r.results){
      const b = el('button', {class: 'webimg', type: 'button', title: (x.title ? x.title + ' — ' : '') + x.host});
      const im = el('img', {src: x.thumb, loading: 'lazy', alt: '', referrerpolicy: 'no-referrer'}); im.onerror = () => b.remove();
      b.append(im, el('span', null, x.host)); b.onclick = () => useWeb(x, b); grid.append(b);
    }
  };
  go.onclick = () => load(qi.value); qi.onkeydown = e => { if(e.key === 'Enter') load(qi.value) };
  load(qi.value);
}
async function useWeb(x, b){
  if(b.classList.contains('busy')) return;
  b.classList.add('busy'); b.classList.remove('failed');
  try { const r = await call('/api/grab', {image: x.image, page: x.page, thumb: x.thumb});
        b.classList.remove('busy'); b.classList.add('used'); addMine({name: r.name, source: r.source}) }
  catch(e) { b.classList.remove('busy'); b.classList.add('failed'); b.title = 'Could not fetch it: ' + e.message }
}
document.addEventListener('paste', async e => {
  if(!E.d || (e.target.closest && e.target.closest('input,textarea'))) return;
  const it = [...((e.clipboardData && e.clipboardData.items) || [])].find(i => i.type.startsWith('image/'));
  if(!it) return; e.preventDefault();
  const url = await new Promise(res => { const fr = new FileReader(); fr.onload = () => res(fr.result); fr.readAsDataURL(it.getAsFile()) });
  try { const r = await call('/api/paste', {data: url}); addMine({name: r.name, source: 'pasted'}) }
  catch(err) { alert('Could not use the pasted picture: ' + err.message) }
});
window.addEventListener('focus', async () => {          /* pictures sent with the old bookmark, or saved to Downloads */
  if(!E.d || !E.linkAt) return;
  try { const files = await call('/downloads', {since: E.linkAt});
        for(const f of files) if(f.showable && !E.mine.some(m => m.name === f.name)) addMine({name: f.name, source: f.source}) } catch(e) {}
});

/* ---------- the save bar ---------- */
function drawSave(){
  const s = document.getElementById('savebar'); s.replaceChildren(); if(!E.d) return;
  const f = E.fields;
  const cv = E.cover.type === 'match' && E.match ? E.match.cover_url : E.cover.type === 'mine' ? (E.cover.m.crop || E.cover.m.url) : '';
  const ci = cv ? el('img', {class: 'cv', src: cv, alt: ''}) : el('span', {class: 'cv'});
  if(cv) ci.onerror = () => ci.replaceWith(el('span', {class: 'cv'}));
  s.append(ci);
  const w = el('div', {class: 'what'});
  const l1 = el('div'); l1.append(el('b', null, f.title || '(no title yet)'), ' — ' + (f.author || '?'));
  w.append(l1, el('div', null, [f.year, f.publisher, f.isbn ? 'ISBN ' + f.isbn : ''].filter(Boolean).join(' · ') +
    '  ·  cover: ' + coverSummary() + '  ·  spine: ' + spineSummary()));
  s.append(w);
  const btn = (label, k, fn, cls) => { const b = el('button', {type: 'button', class: cls || ''}, label); b.append(el('kbd', null, k)); b.onclick = fn; return b };
  s.append(btn('Not a book', 'B', () => decideOther('not-a-book', 'not a book')),
           btn('Check in hand', 'H', () => decideOther('in-hand', 'set aside to check in hand')),
           btn('Skip', 'S', skipBook),
           btn('Save & next', '⏎', saveBook, 'primary'));
}

/* ---------- saving and moving on ---------- */
async function attachImages(row){
  for(const which of ['cover', 'spine']){
    const ch = which === 'cover' ? E.cover : E.spine;
    if(ch.type === 'mine' && !ch.m.own) await call('/attach', {row_id: row, name: ch.m.name, kind: which, data: ch.m.crop || ''});
    if(ch.type === 'mine' && ch.m.own && ch.m.recrop) await call('/recrop', {row_id: row, kind: which, data: ch.m.crop});
  }
  if(E.spine.type === 'shelf' && !E.mine.some(m => m.own && m.kind === 'spine' && m.source === 'your shelf photo')){
    const data = await shelfCrop(E.d.spine);
    if(data) await call('/api/attach_data', {row_id: row, kind: 'spine', data, label: 'your shelf photo'});
  }
}
async function saveBook(){
  if(!E.d || E.busy) return;
  if(!E.fields.title){ alert('Add a title first (or press B if it is not a book).'); return }
  E.busy = true; const row = E.d.book.row_id;
  try {
    await attachImages(row);
    const p = await call('/api/save', {row_id: row, cover: E.cover.type, spine: E.spine.type === 'shelf' ? 'mine' : E.spine.type,
      details: {...E.fields, base: E.base, match: E.match, sources: E.src}});
    done(row, 'Saved: ' + E.fields.title, p);
  } catch(e) { alert('Not saved: ' + e.message) } finally { E.busy = false }
}
async function decideOther(decision, label){
  if(!E.d || E.busy) return; E.busy = true; const row = E.d.book.row_id;
  try { await call('/api/decide', {row_id: row, decision, pick_json: ''}); done(row, E.d.book.title + ' → ' + label) }
  catch(e) { alert('Not saved: ' + e.message) } finally { E.busy = false }
}
async function done(row, msg, p){
  E.last = row; toast(msg);
  const nxt = nextInList(row);
  if(p) drawPub(p); else refreshPub();
  if(E.bucket !== 'all') E.list = E.list.filter(x => x.row_id !== row);
  E.hist.push(row);
  if(nxt) { await openBook(nxt); loadList() } else { await loadList(); E.list.length ? openBook(E.list[0].row_id) : drawEmpty() }
}
async function skipBook(){
  if(!E.d) return; const row = E.d.book.row_id;
  if(E.bucket === 'to_review') await call('/api/skip', {row_id: row});
  const nxt = nextInList(row); E.hist.push(row);
  if(nxt) openBook(nxt);
  loadList();
}
async function undoLast(){
  if(!E.last) return; const row = E.last; E.last = null; hideToast();
  await call('/api/undo', {row_id: row}); refreshPub(); await openBook(row); loadList();
}
function back(){ const r = E.hist.pop(); if(r) openBook(r) }
let toastTimer = null;
function toast(msg){ document.getElementById('toastmsg').textContent = msg; document.getElementById('toast').classList.add('open');
  clearTimeout(toastTimer); toastTimer = setTimeout(hideToast, 8000) }
function hideToast(){ document.getElementById('toast').classList.remove('open') }

/* ---------- the spine, cropped from the shelf photo ---------- */
function drawSpineCrop(box, src, b, maxW, maxH){
  const im = new Image(); im.onload = () => {
    const W = im.naturalWidth, H = im.naturalHeight, bw = b[2]-b[0], bh = b[3]-b[1];
    const x0 = Math.max(0, b[0]-bw*0.08), x1 = Math.min(1, b[2]+bw*0.08), y0 = Math.max(0, b[1]-bh*0.02), y1 = Math.min(1, b[3]+bh*0.02);
    const rw = (x1-x0)*W, rh = (y1-y0)*H, flat = rw > rh;           /* a book lying flat: show it wide */
    const k = Math.min((maxW || (flat ? 300 : 116))/rw, (maxH || (flat ? 90 : 196))/rh);
    if(!maxW){ box.style.width = Math.max(60, rw*k + 4) + 'px'; box.style.height = Math.max(60, rh*k + 4) + 'px' }
    const vp = el('div', {class: 'vp'}); vp.style.width = rw*k + 'px'; vp.style.height = rh*k + 'px'; vp.style.position = 'relative'; vp.style.overflow = 'hidden';
    Object.assign(im.style, {position: 'absolute', maxWidth: 'none', width: W*k + 'px', height: H*k + 'px', left: (-x0*W*k) + 'px', top: (-y0*H*k) + 'px'});
    vp.append(im); box.replaceChildren(vp) };
  im.onerror = () => { box.textContent = 'shelf photo not here' };
  im.src = src;
}
function shelfCrop(sp){
  return new Promise(res => { const im = new Image(); im.onload = () => {
    const W = im.naturalWidth, H = im.naturalHeight, b = sp.box;
    const r = {x: b[0]*W, y: b[1]*H, w: (b[2]-b[0])*W, h: (b[3]-b[1])*H};
    if(r.w <= r.h) return res(cropURL(im, r));
    /* lying flat: turn it upright (a quarter turn clockwise), so every spine is stored the same way */
    const sc = Math.min(1, 2400 / r.w), c = document.createElement('canvas');
    c.width = Math.round(r.h*sc); c.height = Math.round(r.w*sc);
    const g = c.getContext('2d'); g.translate(c.width, 0); g.rotate(Math.PI/2);
    g.drawImage(im, r.x, r.y, r.w, r.h, 0, 0, c.height, c.width);
    res(c.toDataURL('image/jpeg', 0.92)) };
    im.onerror = () => res(''); im.src = sp.big });
}

/* ---------- keys ---------- */
document.addEventListener('keydown', e => {
  if(e.target.closest && e.target.closest('input,textarea,select')){ if(e.key === 'Escape') e.target.blur(); return }
  if(document.querySelector('#crop.open, #lb.open, #sv.open')) return;
  if(e.metaKey || e.ctrlKey || e.altKey || !E.d) return;
  const k = e.key;
  if(k === 'Enter'){ e.preventDefault(); saveBook() }
  else if(/^[1-9]$/.test(k)){ if(E.matches[Number(k) - 1]){ e.preventDefault(); useMatch(Number(k) - 1) } }
  else if(k === '0') useSpine();
  else if(k === 's' || k === 'S') skipBook();
  else if(k === 'h' || k === 'H') decideOther('in-hand', 'set aside to check in hand');
  else if(k === 'b' || k === 'B') decideOther('not-a-book', 'not a book');
  else if(k === 'u' || k === 'U') undoLast();
  else if(k === 'ArrowLeft') back();
  else if(k === '/'){ e.preventDefault(); document.getElementById('search').focus() }
});
document.addEventListener('click', e => { const m = document.getElementById('more'); if(m && m.open && !m.contains(e.target)) m.open = false });

(async () => { await refreshPub(); await openBucket('to_review') })();
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
