import { renderChars, renderGacha } from './gallery.js?v=10';
import { mountPlayer, readSet, store } from './playerui.js?v=8';
import { t, period, lang, setLang, LANGS, applyStatic } from './i18n.js';

const view = document.getElementById('view');
const cache = {};
const getJSON = async (u) => (cache[u] ??= fetch(u).then((r) => { if (!r.ok) throw new Error(u + ' ' + r.status); return r.json(); }));
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

let player = null;
function leavePlayer() {
  if (player) { player.stop(); player = null; }
  document.body.classList.remove('playing');
}

async function route() {
  leavePlayer();
  // overlays (card / portrait viewers) belong to the page we're leaving
  document.querySelectorAll('.viewer').forEach((v) => (v._close ? v._close() : v.remove()));
  document.querySelectorAll('.vpop').forEach((v) => { v.querySelector('video')?.pause(); v.remove(); });
  document.querySelectorAll('.ppop').forEach((v) => (v._close ? v._close() : v.remove()));
  const h = location.hash.replace(/^#\/?/, '');
  const [path, query] = h.split('?');
  const parts = path.split('/').filter(Boolean).map(decodeURIComponent);
  const q = new URLSearchParams(query || '');
  document.querySelectorAll('.top nav a').forEach((a) => a.classList.toggle('on', a.getAttribute('href') === '#/' + (parts[0] || '')));
  window.scrollTo(0, 0);
  try {
    if (!parts.length) return home();
    if (parts[0] === 'story' && parts.length === 1) return storyCats();
    if (parts[0] === 'story' && parts.length === 2) return storyCat(+parts[1]);
    if (parts[0] === 'story' && parts.length === 3) return adventure(+parts[1], +parts[2]);
    if (parts[0] === 'album' && parts.length <= 2) return albumList(parts[1]);
    if (parts[0] === 'album' && parts.length === 3) return albumEpisode(parts[1], +parts[2]);
    if (parts[0] === 'role' && parts.length === 1) return roleList();
    if (parts[0] === 'role' && parts.length === 2) return roleDetail(parts[1]);
    if (parts[0] === 'others') return others(parts[1]);
    if (parts[0] === 'play') return play(parts[1], q);
    if (parts[0] === 'chars') return renderChars(view, getJSON, parts[1]);
    if (parts[0] === 'gacha') return renderGacha(view, getJSON, parts[1]);
    if (parts[0] === 'movies') return movies();
    if (parts[0] === 'notices') return notices(parts[1]);
    if (parts[0] === 'credits') {
      view.innerHTML = `<div class="crumbs"><a href="#/">${t('ホーム')}</a></div><h1>${t('エンドクレジット')}</h1>
        <video controls style="width:100%;max-height:75vh;background:#000;border-radius:10px" src="${(await getJSON('data/index.json')).ui?.credits || ''}"></video>`;
      return;
    }
    view.innerHTML = `<p>${t('見つかりません')}</p>`;
  } catch (e) {
    view.innerHTML = `<p class="muted">${t('読み込みに失敗しました：{e}', { e: esc(e.message) })}<br>${t('先に {cmd} を実行して web/data を作成してください。', { cmd: '<code>tools/build_web.py</code>' })}</p>`;
    console.error(e);
  }
}
window.addEventListener('hashchange', route);
// interface language: header picker; re-render the current page in the new language
const langSel = document.querySelector('.top .lang');
if (langSel) {
  langSel.innerHTML = Object.entries(LANGS).map(([k, n]) => `<option value="${k}"${k === lang ? ' selected' : ''}>${n}</option>`).join('');
  langSel.onchange = () => { setLang(langSel.value); applyStatic(); route(); };
}
applyStatic();
getJSON('data/album.json').then((al) => { if (!hasAlbum(al)) document.querySelector('.top nav a[href="#/album"]')?.remove(); }).catch(() => {});

// ------------------------------------------------------------------ pages
async function home() {
  const idx = await getJSON('data/index.json');
  const al = await getJSON('data/album.json').catch(() => null);
  const mv = await getJSON('data/movies.json').catch(() => []);
  const n = Object.keys(idx.titles).length;
  view.innerHTML = `
    <h1>${t('ダンまち〜メモリア・フレーゼ〜 アーカイブ')}</h1>
    <p class="muted">${t('シナリオ {n} 本 ・ 既読 {r}', { n: n.toLocaleString(), r: readSet.size.toLocaleString() })}</p>
    <div class="home-hero">${[
      ['#/story', 'ストーリー', idx.ui?.menu1],
      hasAlbum(al) && ['#/album', 'アルバム', al.anniversary?.[0]?.banner || al.event?.[0]?.banner, 'background-position:right center'],
      ['#/role', 'キャラストーリー', idx.ui?.chars, 'background-position:center 20%'],
      ['#/chars', '立ち絵', idx.ui?.chars, 'background-position:center 20%'],
      ['#/gacha', 'カード', idx.ui?.cards],
      mv.length && ['#/movies', 'ムービー', mv[0].items[0]?.poster],
      idx.ui?.credits && ['#/credits', 'エンドクレジット', idx.ui?.credits_bg],
      ['#/others', 'その他のシナリオ', idx.ui?.menu2],
    ].filter(Boolean).map(([href, label, img, extra]) =>
      `<a href="${href}" style="${img ? `background-image:url(${img});` : ''}${extra || ''}"><span>${t(label)}</span></a>`).join('')}
    </div>`;
}

// ------------------------------------------------------------------ ムービー
// The cutscene movies the stories play (e.g. the 6th-anniversary SO12 movies), each with the episode(s) it
// belongs to: watch it alone in the popup, or jump to the episode.
async function movies() {
  const groups = await getJSON('data/movies.json');
  const dur = (s) => (s ? `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, '0')}` : '');
  view.innerHTML = `<div class="crumbs"><a href="#/">${t('ホーム')}</a></div><h1>${t('ムービー')}</h1>` + groups.map((g) => `
    <h2>${esc(t(g.title))}</h2>
    <div class="movies">${g.items.map((m, i) => `
      <div class="movie-card">
        <a class="poster" href="#" data-video="${esc(m.src)}" data-title="${esc(t(g.title) + ' #' + (i + 1))}" style="${m.poster ? `background-image:url(${m.poster})` : ''}">
          <span class="num">#${i + 1}</span>${m.duration ? `<span class="dur">${dur(m.duration)}</span>` : ''}<span class="play">▶</span></a>
        <div class="body"><div class="s">${t('登場するお話')}</div>${m.novels.map((n) => `
          <a class="ep" href="#/play/${encodeURIComponent(n.key)}">${esc(n.title)}</a>`).join('')}</div>
      </div>`).join('')}</div>`).join('');
}

// Play a video in a popup over the current page (Esc / ✕ / backdrop click closes it).
function videoPopup(src, title) {
  if (!src) return;
  const pop = document.createElement('div');
  pop.className = 'vpop';
  pop.innerHTML = `<div class="vtitle">${esc(title || '')}</div><button class="close">${t('✕ 閉じる')}</button><video controls autoplay playsinline src="${src}"></video>`;
  const close = () => { pop.querySelector('video').pause(); pop.remove(); document.removeEventListener('keydown', key); };
  const key = (e) => { if (e.key === 'Escape') close(); };
  pop.addEventListener('click', (e) => { if (e.target === pop || e.target.closest('.close')) close(); });
  document.addEventListener('keydown', key);
  document.body.appendChild(pop);
}
document.addEventListener('click', (e) => {
  const a = e.target.closest('[data-video]');
  if (!a || !a.dataset.video) return;
  e.preventDefault();
  videoPopup(a.dataset.video, a.dataset.title);
});

async function storyCats() {
  const idx = await getJSON('data/index.json');
  view.innerHTML = `<h1>${t('ストーリー')}</h1><div class="grid">${idx.tree.map((c, i) => {
    const eps = c.adventures.reduce((s, a) => s + a.episodes.length, 0);
    const alb = c.adventures.reduce((s, a) => s + (a.album?.length || 0), 0);
    return `<a class="card" href="#/story/${i}"><div class="t">${esc(t(c.name))}</div><div class="s">${t('{a} 冒険 ・ {e} 話', { a: c.adventures.length, e: eps })}${alb ? t(' ・ アルバム {n}', { n: alb }) : ''}</div></a>`;
  }).join('')}</div>`;
}

function novelsOf(adv) { return adv.episodes.flatMap((e) => e.stages.flatMap((s) => s.novels)); }
// Each stage's novels are segments of one continuous story → one playback group (play seamlessly).
function groupsOf(adv) { return adv.episodes.flatMap((e) => e.stages.map((s) => s.novels)); }
const segEndOf = (groups) => new Set(groups.map((g) => g[g.length - 1]));

async function storyCat(ci) {
  const idx = await getJSON('data/index.json');
  const c = idx.tree[ci];
  view.innerHTML = `<div class="crumbs"><a href="#/story">${t('ストーリー')}</a></div><h1>${esc(t(c.name))}</h1>
    <input class="search" placeholder="${t('タイトルで検索…')}">
    <div class="grid">${c.adventures.map((a, ai) => {
      const ns = novelsOf(a); const r = ns.filter((k) => readSet.has(k)).length;
      const alb = a.album?.length ? t(' ・ アルバム {n}', { n: a.album.length }) : '';
      return `<a class="card ${ns.length && r === ns.length ? 'read' : ''}" href="#/story/${ci}/${ai}" data-q="${esc(a.title + ' ' + a.episodes.map((e) => e.title + e.sub).join(' ') + ' ' + (a.album || []).map((l) => l.title).join(' '))}">
        <div class="t">${esc(t(a.title))}</div><div class="s">${t('{e} 話', { e: a.episodes.length })}${ns.length ? ' ・ ' + t('{r}/{n} 既読', { r, n: ns.length }) : ''}${alb}</div></a>`;
    }).join('')}</div>`;
  const inp = view.querySelector('.search');
  inp.oninput = () => view.querySelectorAll('.card').forEach((el) => (el.style.display = el.dataset.q.includes(inp.value) ? '' : 'none'));
}

async function adventure(ci, ai) {
  const idx = await getJSON('data/index.json');
  const c = idx.tree[ci], a = c.adventures[ai];
  const list = novelsOf(a);
  const ctx = `cat=${ci}&adv=${ai}`;
  view.innerHTML = `<div class="crumbs"><a href="#/story">${t('ストーリー')}</a> › <a href="#/story/${ci}">${esc(t(c.name))}</a></div>
    <h1>${esc(t(a.title))}</h1>
    ${a.album?.length ? `<div class="album-links"><span class="muted">${t('アルバム収録：')}</span>
      ${a.album.map((l) => `<a class="xlink" href="#/album/${l.sec}/${l.i}">${esc(l.title)} →</a>`).join('')}</div>` : ''}
    ${a.episodes.map((e, ei) => {
      const first = e.stages[0].novels[0];
      return `<details class="episode" ${a.episodes.length <= 3 ? 'open' : ''}>
        <summary>${e.banner ? `<img class="ep-banner" src="${e.banner}" alt="" loading="lazy">` : ''}<span class="tx"><span class="t">${esc(e.title)}</span><span class="s">${esc(e.sub)}</span>${e.reruns ? `<span class="tag" title="${t('同じ内容の復刻をまとめました')}">${t('復刻あり')}</span>` : ''}${period(e.start, e.end) ? `<span class="pd">${period(e.start, e.end)}</span>` : ''}</span>
          <a class="play-all" href="#/play/${encodeURIComponent(first)}?${ctx}">${t('▶ この話を再生')}</a></summary>
        <div class="stages">${noticeLinks(e.notices)}${e.stages.map((s, si) => `
          <div class="stage-row"><span class="n">${si + 1}</span>
            <a href="#/play/${encodeURIComponent(s.novels[0])}?${ctx}">${esc(s.title || idx.titles[s.novels[0]] || s.novels[0])}</a>
            <span class="parts">${s.novels.length > 1 ? s.novels.map((k, ki) => `<a class="${readSet.has(k) ? 'read' : ''}" href="#/play/${encodeURIComponent(k)}?${ctx}" title="${esc(idx.titles[k] || k)}">${ki + 1}</a>`).join('') : (readSet.has(s.novels[0]) ? '<span class="muted">既読</span>' : '')}</span>
          </div>`).join('')}</div></details>`;
    }).join('')}`;
  view.querySelectorAll('.play-all').forEach((el) => el.addEventListener('click', (ev) => ev.stopPropagation()));
  void list;
}

// preview / home-base novels the game played at start-up around an event (data: ep.notices)
const noticeLinks = (ns, ctx) => (ns?.length ? `<div class="notices"><span class="muted">${t('予告・拠点ノベル')}</span>${ns.map((n) =>
  `<a class="${readSet.has(n.key) ? 'read' : ''}" href="#/play/${encodeURIComponent(n.key)}${ctx ? `?${ctx}` : ''}">${esc(n.title)}</a>`).join('')}</div>` : '');

// ------------------------------------------------------------------ アルバム (the offline app's album)
const ALBUM = { anniversary: '周年ストーリー', event: 'イベントストーリー', extra: 'その他のイベント', advent: '降臨イベント', rerun: '復刻イベント' };
// run dates: period() in i18n.js (the app's wording, message home_quest_event_open_period, in Japanese)
const albumNovels = (x) => x.stages.flatMap((s) => s.novels);
// the album exists only in the JP offline app's data; builds from other app data have none
const hasAlbum = (al) => !!(al && (al.anniversary?.length || al.event?.length));

async function albumList(sec) {
  const al = await getJSON('data/album.json');
  if (!hasAlbum(al)) { view.innerHTML = `<h1>${t('アルバム')}</h1><p class="muted">${t('このデータにはアルバムがありません。')}</p>`; return; }
  if (!ALBUM[sec]) sec = 'anniversary';
  view.innerHTML = `<h1>${t('アルバム')}</h1>
    <div class="tabs">${Object.entries(ALBUM).map(([k, n]) => `<a class="${k === sec ? 'on' : ''}" href="#/album/${k}">${t(n)}</a>`).join('')}</div>
    ${sec === 'extra' || sec === 'advent' ? `<p class="muted">${t('メモリアルアプリのアルバムに収録されていない、開催期間のあるイベント（新しい順）。')}</p>`
      : sec === 'rerun' ? `<p class="muted">${t('内容が初回と異なる復刻イベント（新しい順）。')}</p>` : ''}
    <div class="album">${(al[sec] || []).map((x, i) => {
      const ns = albumNovels(x), r = ns.filter((k) => readSet.has(k)).length, p = period(x.start, x.end);
      return `<a class="banner ${r === ns.length ? 'read' : ''}" href="#/album/${sec}/${i}" title="${esc(x.title)}">
        ${x.banner ? `<img src="${x.banner}" alt="${esc(x.title)}" loading="lazy">` : `<span class="nob">${esc(x.title)}</span>`}
        ${p ? `<span class="period">${p}</span>` : ''}${r === ns.length ? `<span class="done">${t('既読')}</span>` : ''}</a>`;
    }).join('')}</div>`;
}

async function albumEpisode(sec, i) {
  const [al, idx] = await Promise.all([getJSON('data/album.json'), getJSON('data/index.json')]);
  const x = al[sec]?.[i];
  if (!x) { view.innerHTML = `<p>${t('見つかりません')}</p>`; return; }
  const ctx = `alb=${sec}&i=${i}`;
  const p = period(x.start, x.end);
  view.innerHTML = `<div class="crumbs"><a href="#/album/${sec}">${t('アルバム')} › ${t(ALBUM[sec])}</a></div>
    <div class="album-head">${x.banner ? `<img src="${x.banner}" alt="">` : ''}
      <div><h1>${esc(x.title)}</h1>${p ? `<div class="muted">${p}</div>` : ''}
        <div class="album-tools"><a class="play-all" href="#/play/${encodeURIComponent(x.stages[0].novels[0])}?${ctx}">${t('▶ 最初から再生')}</a>
          <label><input type="checkbox" data-cont ${store.get('dm.albumCont', true) ? 'checked' : ''}> ${t('ストーリー連続再生')}</label></div></div></div>
    ${noticeLinks(x.notices)}<div class="stages flat">${x.stages.map((s, si) => `
      <div class="stage-row"><span class="n">STORY ${si + 1}</span>
        <a href="#/play/${encodeURIComponent(s.novels[0])}?${ctx}">${esc(s.title || idx.titles[s.novels[0]] || s.novels[0])}</a>
        <span class="parts">${s.novels.length > 1 ? s.novels.map((k, ki) => `<a class="${readSet.has(k) ? 'read' : ''}" href="#/play/${encodeURIComponent(k)}?${ctx}" title="${esc(idx.titles[k] || k)}">${ki + 1}</a>`).join('') : (readSet.has(s.novels[0]) ? '<span class="muted">既読</span>' : '')}</span>
      </div>`).join('')}</div>`;
  view.querySelector('[data-cont]').onchange = (e) => store.set('dm.albumCont', e.target.checked);
}

// ------------------------------------------------------------------ キャラストーリー (per-character stories)
async function roleList() {
  const cs = await getJSON('data/characters.json');
  view.innerHTML = `<h1>${t('キャラストーリー')}</h1>
    <p class="muted">${t('キャラクターごとの衣装エピソード・キャラクエスト・ふれあい・ボイス。')}</p>
    <input class="search" placeholder="${t('キャラ名で検索…')}">
    <div class="thumbs role-grid">${cs.map((c) => {
      const parts = [];
      if (c.costumes.length) parts.push(t('衣装 {n}', { n: c.costumes.length }));
      if (c.quest) parts.push(t('キャラクエ'));
      if (c.fureai) parts.push(t('ふれあい'));
      if (c.present?.length) parts.push(t('バレンタイン'));
      if (c.voices) parts.push(t('ボイス {n}', { n: c.voices }));
      return `<a class="thumb" data-q="${esc(c.name + ' ' + c.short + ' ' + c.code)}" href="#/role/${encodeURIComponent(c.code)}">
        <div class="im"${c.img ? ` style="background-image:url(${c.img});background-size:cover;background-position:center 15%"` : ''}></div>
        <div class="cap"><b>${esc(c.short)}</b><br>${parts.join(' ・ ')}</div></a>`;
    }).join('')}</div>`;
  const inp = view.querySelector('.search');
  inp.oninput = () => view.querySelectorAll('.thumb').forEach((el) => (el.style.display = el.dataset.q.includes(inp.value) ? '' : 'none'));
}

// episode list for キャラクエ / ふれあい (same shape as an adventure)
function epBlock(adv, ctx, idx, label) {
  if (!adv) return '';
  return `<h2 class="role-sec">${label}</h2>` + adv.episodes.map((e) => {
    const first = e.stages[0].novels[0];
    return `<details class="episode" open>
      <summary><span class="t">${esc(e.title)}</span><span class="s">${esc(e.sub)}</span>
        <a class="play-all" href="#/play/${encodeURIComponent(first)}?${ctx}">${t('▶ 再生')}</a></summary>
      <div class="stages">${e.stages.map((s, si) => `
        <div class="stage-row"><span class="n">${si + 1}</span>
          <a href="#/play/${encodeURIComponent(s.novels[0])}?${ctx}">${esc(s.title || idx.titles[s.novels[0]] || s.novels[0])}</a>
          <span class="parts">${s.novels.length > 1 ? s.novels.map((k, ki) => `<a class="${readSet.has(k) ? 'read' : ''}" href="#/play/${encodeURIComponent(k)}?${ctx}" title="${esc(idx.titles[k] || k)}">${ki + 1}</a>`).join('') : (readSet.has(s.novels[0]) ? '<span class="muted">既読</span>' : '')}</span>
        </div>`).join('')}</div></details>`;
  }).join('');
}

async function roleDetail(code) {
  const [cs, idx, groups] = await Promise.all([getJSON('data/characters.json'), getJSON('data/index.json'), getJSON('data/chars.json')]);
  const c = cs.find((x) => x.code === code);
  if (!c) { view.innerHTML = `<p>${t('見つかりません')}</p>`; return; }
  const enc = encodeURIComponent(code);
  const hasPortrait = groups.some((g) => g.code === code);
  const cos = c.costumes.length ? `<h2 class="role-sec">${t('衣装エピソード')} <span class="muted">${c.costumes.length}</span></h2>
    <div class="thumbs cards cos-grid">${c.costumes.map((co) => {
      const ns = co.stories.flatMap((s) => s.novels);
      const r = ns.filter((k) => readSet.has(k)).length;
      return `<a class="thumb ${r && r === ns.length ? 'read' : ''}" href="#/play/${encodeURIComponent(ns[0])}?role=${enc}&cos=${co.id}">
        <div class="im"${co.thumb ? ` style="background-image:url(${co.thumb});background-size:cover;background-position:center 20%"` : ''}></div>
        <div class="cap"><b>${esc(co.title)}</b><br>★${co.rarity} ・ ${t('{r}/{n} 既読', { r, n: ns.length })}</div></a>`;
    }).join('')}</div>` : '';
  const p = c.profile || {};
  const prof = [p.title && `<b>${esc(p.title)}</b>`, p.race, p.age && t('{n}歳', { n: p.age }), p.height && `${esc(p.height)}`, p.cv && `CV: ${esc(p.cv)}`].filter(Boolean);
  view.innerHTML = `<div class="crumbs"><a href="#/role">${t('キャラストーリー')}</a></div>
    <div class="role-head"><h1>${esc(c.name)}</h1>
      ${hasPortrait ? `<a class="xlink" href="#/chars/${enc}">${t('立ち絵 →')}</a>` : ''}</div>
    ${prof.length ? `<p class="role-prof">${prof.join(' ・ ')}</p>` : ''}${p.desc ? `<details class="role-desc"><summary>${t('プロフィール')}</summary><p>${esc(p.desc)}</p></details>` : ''}
    ${cos}
    ${epBlock(c.quest, `role=${enc}&q=quest`, idx, t('キャラクエスト'))}
    ${epBlock(c.fureai, `role=${enc}&q=fureai`, idx, t('ふれあい'))}
    ${c.present?.length ? `<h2 class="role-sec">${t('バレンタイン企画')}</h2>` + c.present.map((n) =>
      `<a class="card ep-row ${readSet.has(n.key) ? 'read' : ''}" href="#/play/${encodeURIComponent(n.key)}?role=${enc}"><div class="t">${esc(n.title)}</div>${period(n.start, n.end) ? `<div class="s">${period(n.start, n.end)}</div>` : ''}</a>`).join('') : ''}
    <div class="voices-sec"></div>`;
  view.querySelectorAll('.play-all').forEach((el) => el.addEventListener('click', (ev) => ev.stopPropagation()));
  if (c.voices) voiceList(view.querySelector('.voices-sec'), (await getJSON('data/voices.json'))[code] || []);
}

// Home / town / system voice lines of one character: category chips, grouped by who they're spoken to.
let voiceAudio = null;
function voiceList(box, items) {
  const cats = [...new Set(items.map((i) => i.cat))];
  let cat = cats[0];
  const draw = () => {
    const list = items.filter((i) => i.cat === cat);
    const groups = [...new Set(list.map((i) => i.to || ''))];
    box.querySelector('.vlist').innerHTML = groups.map((g) => `${g ? `<h3 class="vto">${esc(t(g))}</h3>` : ''}` +
      list.filter((i) => (i.to || '') === g).map((i) => `<div class="vline">
        ${i.voice ? `<button class="vplay" data-src="${esc(i.voice)}" title="${t('再生')}">▶</button>` : `<span class="vplay off" title="${t('音声なし')}">—</span>`}
        ${i.sub ? `<span class="vsub">${esc(t(i.sub))}</span>` : ''}
        <span class="vtext">${i.text ? esc(i.text).replace(/\[r=([^\]]*)\]([^\[]*)\[\/r\]/g, '$2').replace(/\n/g, '<br>') : `<span class="muted">${t('（テキストなし）')}</span>`}</span></div>`).join('')).join('');
  };
  box.innerHTML = `<h2 class="role-sec">${t('ボイス')} <span class="muted">${items.length}</span></h2>
    <div class="chips vcats">${cats.map((k) => `<button data-v="${esc(k)}"${k === cat ? ' class="on"' : ''}>${esc(t(k))} <span class="muted">${items.filter((i) => i.cat === k).length}</span></button>`).join('')}</div>
    <div class="vlist"></div>`;
  box.querySelector('.vcats').addEventListener('click', (e) => {
    const b = e.target.closest('button'); if (!b) return;
    cat = b.dataset.v; box.querySelectorAll('.vcats button').forEach((x) => x.classList.toggle('on', x === b)); draw();
  });
  box.addEventListener('click', (e) => {
    const b = e.target.closest('.vplay[data-src]'); if (!b) return;
    if (voiceAudio) { voiceAudio.pause(); document.querySelectorAll('.vplay.playing').forEach((x) => x.classList.remove('playing')); }
    voiceAudio = new Audio(b.dataset.src); b.classList.add('playing');
    voiceAudio.onended = () => b.classList.remove('playing');
    voiceAudio.play().catch(() => b.classList.remove('playing'));
  });
  draw();
}

// preview / home-base novels that belong to no single event (anime-episode countdowns, new year, features…)
const noticeTitle = (g) => (g === 'misc' ? t('拠点ノベル・予告') : t('アニメ{n}期 放映前ノベル', { n: g.replace('anime', '') }));
async function notices(g = 'misc') {
  const all = await getJSON('data/notices.json');
  const ns = (Array.isArray(all) ? (g === 'misc' ? all : []) : all[g]) || [];
  view.innerHTML = `<div class="crumbs"><a href="#/others">${t('その他')}</a></div><h1>${noticeTitle(g)}</h1>
    <p class="muted">${g === 'misc' ? t('起動時に期間限定で流れたノベルのうち、特定のイベントに属さないもの（日付順）。') : t('TVアニメの各話放送前に起動時に流れたノベル（日付順）。')}</p>
    <div class="stages flat">${ns.map((n) => `<div class="stage-row"><span class="n">${n.start ? period(n.start, n.end, true) : ''}</span>
      <a class="${readSet.has(n.key) ? 'read' : ''}" href="#/play/${encodeURIComponent(n.key)}?notices=${encodeURIComponent(g)}">${esc(n.title)}</a></div>`).join('')}</div>`;
}

async function others(group) {
  const [o, idx, nall] = await Promise.all([getJSON('data/others.json'), getJSON('data/index.json'), getJSON('data/notices.json').catch(() => ({}))]);
  const ngroups = Array.isArray(nall) ? { misc: nall } : nall;
  if (!group) {
    const label = (g) => t({ nextnotice: '次回予告', co_touch: 'ふれあい反応 1', co02_touch: 'ふれあい反応 2', co03_touch: 'ふれあい反応 3', main_quest: 'メイン（未分類）', tutorial: 'チュートリアル' }[g] || g);
    view.innerHTML = `<h1>${t('その他のシナリオ')}</h1><p class="muted">${t('ストーリー一覧に含まれないシナリオ（キー名で分類）。')}</p>
      <input class="search" placeholder="${t('絞り込み…')}">
      <div class="grid">${Object.entries(ngroups).filter(([, v]) => v.length).map(([g, v]) => `<a class="card" data-q="${esc(noticeTitle(g))}" href="#/notices/${g}"><div class="t">${noticeTitle(g)}</div><div class="s">${t('{n} 本', { n: v.length })} ・ ${t('日付順')}</div></a>`).join('')}${Object.entries(o).map(([g, ks]) => `<a class="card" data-q="${esc(g + ' ' + label(g))}" href="#/others/${encodeURIComponent(g)}"><div class="t">${esc(label(g))}</div><div class="s">${t('{n} 本', { n: ks.length })}</div></a>`).join('')}</div>`;
    const inp = view.querySelector('.search');
    inp.oninput = () => view.querySelectorAll('.card').forEach((el) => (el.style.display = el.dataset.q.includes(inp.value) ? '' : 'none'));
    return;
  }
  const ks = o[group] || [];
  view.innerHTML = `<div class="crumbs"><a href="#/others">${t('その他')}</a></div><h1>${esc(group)}</h1>
    <div class="grid">${ks.map((k) => `<a class="card ${readSet.has(k) ? 'read' : ''}" href="#/play/${encodeURIComponent(k)}?others=${encodeURIComponent(group)}"><div class="t">${esc(idx.titles[k] || k)}</div><div class="s">${esc(k)}</div></a>`).join('')}</div>`;
}

// ------------------------------------------------------------------ player page
async function play(key, q) {
  const idx = await getJSON('data/index.json');
  let list = [key], back = '#/story', groups = null;
  if (q.has('cat')) {
    const ci = +q.get('cat'), ai = +q.get('adv');
    groups = groupsOf(idx.tree[ci].adventures[ai]);
    back = `#/story/${ci}/${ai}`;
  } else if (q.has('alb')) {
    const al = await getJSON('data/album.json');
    const x = al[q.get('alb')]?.[+q.get('i')];
    // ストーリー連続再生 on: the whole episode is one segment (no end card between stories)
    if (x) groups = store.get('dm.albumCont', true) ? [albumNovels(x)] : x.stages.map((s) => s.novels);
    back = `#/album/${q.get('alb')}/${q.get('i')}`;
  } else if (q.has('card')) {
    const g = await getJSON('data/gacha.json');
    const c = g.cards.find((x) => x.id === +q.get('card'));
    groups = c ? c.stories.map((s) => s.novels) : null;
    back = `#/gacha/${q.get('card')}`;
  } else if (q.has('notices')) {
    back = `#/notices/${encodeURIComponent(q.get('notices'))}`;
  } else if (q.has('others')) {
    const o = await getJSON('data/others.json');
    list = o[q.get('others')] || [key];  // independent scenarios — each its own segment
    back = `#/others/${encodeURIComponent(q.get('others'))}`;
  } else if (q.has('role')) {
    const cs = await getJSON('data/characters.json');
    const c = cs.find((x) => x.code === q.get('role'));
    if (c) {
      if (q.has('cos')) {
        const co = c.costumes.find((x) => x.id === +q.get('cos'));
        if (co) groups = co.stories.map((s) => s.novels);
      } else if (q.get('q') === 'quest' && c.quest) groups = groupsOf(c.quest);
      else if (q.get('q') === 'fureai' && c.fureai) groups = groupsOf(c.fureai);
    }
    back = `#/role/${encodeURIComponent(q.get('role'))}`;
  }
  const segEnd = groups ? segEndOf(groups) : null;
  if (groups) list = groups.flat();
  document.body.classList.add('playing');
  player = mountPlayer(view, key, {
    list, segEnd, titles: idx.titles, getJSON,
    onExit: () => (location.hash = back),
    onNext: (k) => (location.hash = `#/play/${encodeURIComponent(k)}?${q.toString()}`),
  });
}

route();
