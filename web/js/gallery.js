// Character portrait and card galleries.
import { playerPopup } from './playerui.js?v=8';
import { t } from './i18n.js';
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

function portraitHTML(it, face) {
  const f = face || (it.faces.includes('normal') ? 'normal' : it.faces[0]);
  if (it.body) {
    const [x, y] = it.cut || [0, 0];
    return `<div class="pcomp"><img src="${it.base}.body.png"><img class="face" style="left:${x}px;top:${y}px" src="${it.base}${f ? '.' + f : ''}.png"></div>`;
  }
  return `<div class="pcomp"><img src="${it.base}${f ? '.' + f : ''}.png"></div>`;
}

// Thumbnail composite: face positioned in % of the body image so it scales with the tile.
function thumbHTML(it) {
  const f = it.faces.includes('normal') ? 'normal' : it.faces[0];
  const src = `${it.base}${f ? '.' + f : ''}.png`;
  if (!it.body || !it.bs || !it.cut) return `<img class="pt-full" src="${src}" loading="lazy">`;
  const [bw, bh] = it.bs, [fw] = it.fs || [0];
  const st = `left:${(it.cut[0] / bw) * 100}%;top:${(it.cut[1] / bh) * 100}%;width:${(fw / bw) * 100}%`;
  return `<div class="pthumb"><img src="${it.base}.body.png" loading="lazy"><img class="f" style="${st}" src="${src}" loading="lazy"></div>`;
}

function viewer(html, side, onClose) {
  const v = document.createElement('div');
  v.className = 'viewer';
  v.innerHTML = `<div class="pic"><button class="close">${t('✕ 閉じる')}</button><div class="stagepic">${html}</div></div><div class="splitter" title="${t('ドラッグで幅を調整')}"></div><div class="side">${side}</div>`;
  // draggable divider between picture and info; width remembered per browser
  let sideW = null;
  try { sideW = +localStorage.getItem('dm.sideW') || null; } catch {}
  const applyW = (w) => { if (w) v.style.setProperty('--side-w', `${w}px`); };
  applyW(sideW);
  const spl = v.querySelector('.splitter');
  spl.addEventListener('pointerdown', (e) => {
    e.preventDefault();
    spl.setPointerCapture(e.pointerId);
    const move = (ev) => {
      sideW = Math.max(300, Math.min(window.innerWidth - 240, window.innerWidth - ev.clientX));
      applyW(sideW);
    };
    const up = () => {
      spl.removeEventListener('pointermove', move);
      try { localStorage.setItem('dm.sideW', String(sideW)); } catch {}
      window.dispatchEvent(new Event('resize'));
    };
    spl.addEventListener('pointermove', move);
    spl.addEventListener('pointerup', up, { once: true });
  });
  const close = () => { v.remove(); document.removeEventListener('keydown', key); onClose && onClose(); };
  v._close = close;  // lets the router close it on navigation
  const key = (e) => { if (e.key === 'Escape') close(); };
  v.querySelector('.close').onclick = close;
  document.addEventListener('keydown', key);
  document.body.appendChild(v);
  // scale composite portraits to fit the picture pane
  const fit = () => {
    const pic = v.querySelector('.pic'), sp = v.querySelector('.stagepic');
    const el = sp.firstElementChild;
    if (!el) return;
    sp.style.transform = '';
    const r = pic.getBoundingClientRect(), b = el.getBoundingClientRect();
    if (!b.width) return;
    sp.style.transform = `scale(${Math.min(r.width / b.width, r.height / b.height, v.classList.contains('card-viewer') ? 1.2 : 1.6) * 0.95})`;
  };
  v.querySelectorAll('img').forEach((im) => im.addEventListener('load', fit));
  new ResizeObserver(fit).observe(v);
  return v;
}

export async function renderChars(view, getJSON, code) {
  const groups = await getJSON('data/chars.json');
  if (!code) {
    view.innerHTML = `<h1>${t('立ち絵')}</h1><input class="search" placeholder="${t('キャラ名で検索…')}">
      <div class="thumbs">${groups.map((g) => {
        const it = g.items.find((i) => i.key.endsWith('_normal')) || g.items[0];
        return `<a class="thumb" data-q="${esc(g.name + g.code)}" href="#/chars/${g.code}"><div class="im">${thumbHTML(it)}</div><div class="cap">${esc(g.name)} ・ ${g.items.length}</div></a>`;
      }).join('')}</div>`;
    const inp = view.querySelector('.search');
    inp.oninput = () => view.querySelectorAll('.thumb').forEach((el) => (el.style.display = el.dataset.q.includes(inp.value) ? '' : 'none'));
    return;
  }
  const g = groups.find((x) => x.code === code);
  if (!g) { view.innerHTML = `<p>${t('見つかりません')}</p>`; return; }
  const hasStory = (await getJSON('data/characters.json')).some((c) => c.code === code);
  view.innerHTML = `<div class="crumbs"><a href="#/chars">${t('立ち絵')}</a></div>
    <div class="role-head"><h1>${esc(g.name)}</h1>
      ${hasStory ? `<a class="xlink" href="#/role/${code}">${t('キャラストーリー →')}</a>` : ''}</div>
    <div class="thumbs">${g.items.map((it, i) => {
      return `<div class="thumb" data-i="${i}"><div class="im">${thumbHTML(it)}</div><div class="cap">${esc(it.key.split('.')[1])}</div></div>`;
    }).join('')}</div>`;
  view.querySelector('.thumbs').onclick = (e) => {
    const t = e.target.closest('.thumb');
    if (!t) return;
    const it = g.items[+t.dataset.i];
    let face = it.faces.includes('normal') ? 'normal' : it.faces[0];
    const side = () => `<h3>${esc(it.key.split('.')[1])}</h3><p class="muted">${t('{n} 種類の表情', { n: it.faces.length })}</p>
      <div class="faces">${it.faces.map((f) => `<button class="${f === face ? 'on' : ''}" data-f="${esc(f)}">${esc(f)}</button>`).join('')}</div>`;
    const v = viewer(portraitHTML(it, face), side());
    v.querySelector('.side').onclick = (ev) => {
      const b = ev.target.closest('button[data-f]');
      if (!b) return;
      face = b.dataset.f;
      v.querySelector('.stagepic').innerHTML = portraitHTML(it, face);
      v.querySelector('.side').innerHTML = side();
      v.querySelectorAll('.stagepic img').forEach((im) => im.addEventListener('load', () => window.dispatchEvent(new Event('resize'))));
    };
  };
}

const stars = (n) => '★'.repeat(Math.max(0, Math.min(n || 0, 9)));
const nl = (t) => esc(t).replace(/\r?\n/g, '<br>');

// Stats exactly as the memorial app's キャラ詳細 (max rank): verified against in-app screens.
function cardStats(c, lb, su) {
  const k = c.calc, L = 60 + 4 * lb;
  const sub = su ? k.subl[su - 1] : [0, 0, 0, 0, 0, 0, 0];
  const st = k.base.map((b, i) => {
    const pre = b + k.board[i] + (lb ? k.lb[lb - 1][i] : 0);
    const plus = Math.floor((pre * k.pct[i]) / 10000) + sub[2 + i];
    return { v: pre + plus, plus };
  });
  return { L, hp: k.hp0 + k.hpL[L] + sub[0], mp: k.mp0 + k.mpL[L] + sub[1], st };
}

let GMETA = null;  // grade tables etc. from gacha.json

// [label, image url, animated-effect LWF url (英雄祭 cards only)]
function cardImgs(c) {
  const fx = c.fx || {};
  return [[t('カード|image'), c.img, fx.status_l], [t('全身'), c.big, fx.rectangle], [t('ガチャ'), c.lotteryImg, fx.lottery],
          [t('バストアップ'), c.bust]].filter((x) => x[1]);
}

// Card art with its LWF effect overlay: the effect is authored around the image centre, 1px = 1 image px.
let fxStop = null;
const FXW = 2800, FXH = 3600;
function cardPic(url, fxUrl) {
  if (fxStop) { fxStop(); fxStop = null; }
  if (!fxUrl || typeof LWF === 'undefined') return `<img src="${url}">`;
  setTimeout(() => startFx(fxUrl), 0);
  // effect content reaches ~±1300 x −1700…1000 px around the centre: use a big canvas so nothing is clipped
  return `<div class="fxwrap"><img src="${url}"><canvas class="fxc" width="${FXW}" height="${FXH}"></canvas></div>`;
}
function startFx(fxUrl) {
  const cv = document.querySelector('.viewer .fxc');
  if (!cv) return;
  const wrap = cv.parentNode, img = wrap.querySelector('img');
  const place = () => { cv.style.left = `${(img.naturalWidth - FXW) / 2}px`; cv.style.top = `${(img.naturalHeight - FXH) / 2}px`; };
  if (img.complete) place(); else img.addEventListener('load', place);
  const dir = fxUrl.slice(0, fxUrl.lastIndexOf('/') + 1), file = fxUrl.slice(dir.length);
  let alive = true, lwf = null;
  fxStop = () => { alive = false; try { lwf && lwf.destroy(); } catch (e) {} };
  LWF.useCanvasRenderer();
  LWF.ResourceCache.get().loadLWF({ lwf: file, prefix: dir, stage: cv, worker: false, useBackgroundColor: false, onload: (l) => {
    if (!l || !alive) return;
    lwf = l;
    l.property.moveTo(FXW / 2, FXH / 2);
    let t0 = performance.now();
    const step = (t) => { if (!alive) return; l.exec((t - t0) / 1000); t0 = t; l.render(); requestAnimationFrame(step); };
    requestAnimationFrame(step);
  } });
}
function grade(c, i, v) {
  const t = (c.kind === 'assist' ? GMETA.gradeAssist : GMETA.gradeNormal)[i];
  for (const [g, min] of t) if (v >= min) return g;
  return 12;
}
const gradeImg = (g) => GMETA.gradeIcon ? `<img class="grade" alt="${GMETA.gradeNames[g]}" title="${GMETA.gradeNames[g]}" src="${GMETA.gradeIcon.replace(/evaluation_1\.png$/, `evaluation_${g}.png`)}">` : GMETA.gradeNames[g];

function skillRow(k, showMp) {
  return `<div class="sk"><div class="sk-h">${k.icon ? `<img class="sk-ic" src="${k.icon}">` : ''}${esc(k.name)}${showMp && k.mp ? `<span class="mp">${t('消費MP {n}', { n: k.mp })}</span>` : ''}</div><div class="sk-d">${nl(k.desc)}</div></div>`;
}
function skillHTML(c, lb) {
  if (c.kind === 'assist') {
    const k = c.skills.find((x) => x.slot === (lb === 5 ? 'アシストスキル（限界突破5）' : 'アシストスキル')) || c.skills[0];
    return k ? `<h4>${t('アシストスキル')}</h4>${skillRow(k, false)}` : '';
  }
  const sp = c.skills.filter((x) => x.slot === '必殺技'), tech = c.skills.filter((x) => x.slot === '技');
  return (sp.length ? `<h4>${t('必殺技')}</h4>${sp.map((k) => skillRow(k, false)).join('')}` : '') +
         (tech.length ? `<h4>${t('技')}</h4>${tech.map((k) => skillRow(k, true)).join('')}` : '');
}

function cardSide(c, statNames, lb, su) {
  const imgs = cardImgs(c);
  const hasLb = c.calc.lb.length > 0, hasSub = c.calc.subl.length > 0;
  const s = cardStats(c, lb, su);
  const sel = (name, key, max, cur) => `<div class="lbsel">${name} ${Array.from({ length: max + 1 }, (_, n) => `<button class="${n === cur ? 'on' : ''}" data-${key}="${n}">${n || t('なし')}</button>`).join('')}</div>`;
  const [str, end, dex, agi, mag] = s.st;
  return `
    <div class="card-head">
      <div class="card-title">［${esc(c.title)}］</div>
      <div class="card-name">${esc(c.name)}</div>
      <div class="card-meta">${c.elementIcon ? `<img class="elem" src="${c.elementIcon}" title="${esc(t('{e}属性', { e: t(GMETA.elements[c.element] || '') }))}">` : ''}<span class="stars">${stars(c.rarity)}</span>
        ${c.heroFes ? `<span class="tag herofes">${t('英雄祭')}</span>` : c.limited ? `<span class="tag limited">${t('期間限定')}</span>` : ''}
        <span class="tag">${c.kind === 'adv' ? t('冒険者') : t('アシスト')}</span>
        ${c.type ? `<span class="tag">${esc(t(c.type))}</span>` : ''}
        ${c.affiliation ? `<span class="tag">${esc(c.affiliation)}</span>` : ''}</div>
    </div>
    ${imgs.length > 1 ? `<div class="faces imgsel">${imgs.map(([n, u, fx], i) => `<button class="${i ? '' : 'on'}" data-u="${u}" data-fx="${fx || ''}">${n}</button>`).join('')}</div>` : ''}

    ${c.gacha && c.gacha.art ? `<div class="gacha-btns"><button class="gacha-play" data-op="argo">${t('▶ ガチャ演出')}</button></div>` : ''}
    <h4>${t('ステイタス')} <span class="muted" style="font-weight:400;font-size:12px">${t('熟練度 {a}/{b}', { a: s.L, b: s.L })}</span></h4>
    ${hasSub ? sel(t('英雄昇華'), 'su', c.calc.subl.length, su) : ''}
    ${hasLb ? sel(t('限界突破'), 'lb', 5, lb) : ''}
    <div class="statgrid">
      <table class="stat">
        <tr><th>HP</th><td>${s.hp}</td></tr><tr><th>MP</th><td>${s.mp}</td></tr>
        <tr><th>${t('物攻')}</th><td>${str.v}</td></tr><tr><th>${t('魔攻')}</th><td>${mag.v}</td></tr><tr><th>${t('防御')}</th><td>${end.v}</td></tr>
      </table>
      <table class="stat">
        ${s.st.map((x, i) => `<tr><th>${t(statNames[i])}</th><td class="g">${gradeImg(grade(c, i, x.v))}</td><td>${x.v}</td><td class="plus">(+${x.plus})</td></tr>`).join('')}
      </table>
    </div>
    <p class="note">${t('最大ランク・熟練度最大の値です（記念アプリの「キャラ詳細」と同じ計算）。')}</p>
    ${skillHTML(c, lb)}
    ${c.abilities.length ? `<h4>${t('スキル/発展アビリティ')}</h4>${c.abilities.map((a) => `<div class="sk"><div class="sk-h">${esc(a.name)}</div><div class="sk-d">${nl(a.desc)}</div></div>`).join('')}` : ''}
    ${c.costume ? `<h4>${t('衣装')}</h4><div class="sk"><div class="sk-h">${esc(c.costume.name)}</div><div class="sk-d">${nl(c.costume.desc)}</div></div>` : ''}
    ${c.stories.length ? `<h4>${t('衣装ストーリー')}</h4>${c.stories.map((s) => `<a class="story-link" data-key="${esc(s.novels[0])}" href="#/play/${encodeURIComponent(s.novels[0])}?card=${c.id}">▶ ${esc(s.title)}</a>`).join('')}` : ''}`;
}

// lwf.js takes only http(s) or "/" URLs in imageMap and loads them itself with new Image(), so a texture
// prepared on a canvas is handed over by redirecting that image's src to a blob URL.
const imgRedirect = new Map();
(() => {
  const d = Object.getOwnPropertyDescriptor(HTMLImageElement.prototype, 'src');
  Object.defineProperty(HTMLImageElement.prototype, 'src', {
    configurable: true, enumerable: d.enumerable, get() { return d.get.call(this); },
    set(v) { const u = String(v); for (const [k, blob] of imgRedirect) if (u.endsWith(k)) { v = blob; break; } d.set.call(this, v); },
  });
})();
// The ★4 close-up (cut_06) shows the two crops stacked in lottery_upcut.png in the opposite order to the
// original game (legs first, then chest — checked frame by frame against a recording; the Unity client
// counts texture v from the bottom). Swapping the halves gives the original order and framing.
const swapped = new Map();
function swapHalves(url) {
  if (!swapped.has(url)) {
    swapped.set(url, new Promise((res) => {
      const im = new Image();
      im.onload = () => {
        const c = document.createElement('canvas'), h = im.height / 2;
        c.width = im.width; c.height = im.height;
        const g = c.getContext('2d');
        g.drawImage(im, 0, h, im.width, h, 0, 0, im.width, h);
        g.drawImage(im, 0, 0, im.width, h, 0, h, im.width, h);
        c.toBlob((b) => { if (b) imgRedirect.set(url, URL.createObjectURL(b)); res(); });
      };
      im.onerror = () => res();
      im.src = url;
    }));
  }
  return swapped.get(url);
}

// Drive a gacha-cut LWF (files/lwf/uiLwf/lottery/<name>). lwf.js renders into a fixed 1280x720 off-DOM
// buffer, and each frame we blit that buffer onto the visible canvas sized to the letterbox rect.
// `getRect()` -> {w,h} in CSS px. `map` values must be absolute URLs ("/..."); lwf glues its own prefix
// onto anything else. `scale` shrinks the root (these cuts are authored ~1.6x the 1280x720 stage, so at
// scale 1 the composition overflows and only the centre shows). `onEnd` fires at the last frame.
function lwfCut(canvas, name, map, getRect, onEnd, scale = 1) {
  const dir = (GMETA.gachaCuts || {})[name] || `r/0/files/lwf/uiLwf/lottery/${name}/`;
  const buf = document.createElement('canvas');
  buf.width = 1280; buf.height = 720;
  const ctx = canvas.getContext('2d');
  let alive = true, lwf = null;
  const stop = () => { alive = false; try { lwf && lwf.destroy(); } catch (e) {} };
  // Preload the textures into cache first so lwf's own loads resolve promptly.
  const urls = [dir + name + '.png', ...Object.values(map)];
  Promise.all(urls.map((u) => new Promise((res) => { const im = new Image(); im.onload = im.onerror = res; im.src = u; })))
    .then(startLoad);
  function startLoad() {
    if (!alive) return;
    LWF.useCanvasRenderer();
    LWF.ResourceCache.get().loadLWF({ lwf: name + '.lwf', prefix: dir, stage: buf, worker: false, useBackgroundColor: false,
    imageMap: (n) => map[n] || n,
    onload: (l) => {
      if (!l || !alive) { onEnd && onEnd(null); return; }
      lwf = l;
      const total = (l.rootMovie && l.rootMovie.totalFrames) || 0;
      if (scale !== 1) { try { l.property.scaleTo(scale, scale); } catch (e) {} }
      l.property.moveTo(640, 360);  // the cut is authored around the 1280x720 centre
      const blit = () => {
        const r = getRect(), dpr = window.devicePixelRatio || 1;
        const bw = Math.max(1, Math.round(r.w * dpr)), bh = Math.max(1, Math.round(r.h * dpr));
        if (canvas.width !== bw) canvas.width = bw;
        if (canvas.height !== bh) canvas.height = bh;
        ctx.clearRect(0, 0, bw, bh);
        ctx.drawImage(buf, 0, 0, 1280, 720, 0, 0, bw, bh);
      };
      let t0 = performance.now(), ended = false;
      const step = (t) => {
        if (!alive) return;
        if (!ended) {
          l.exec((t - t0) / 1000); t0 = t; l.render();
          if (total && l.rootMovie.currentFrame >= total - 1) { ended = true; onEnd && onEnd(l); }
        }
        blit();
        requestAnimationFrame(step);  // keep looping RAF but, once ended, freeze on the last frame
      };
      requestAnimationFrame(step);
    } });
  }
  return { stop };
}

// Gacha reveal: opening movie (by rarity) → for ★4, the special starry cut-in (cut_06) → the game's
// own cut_07 card reveal (card art, rarity stars/banner, a name plate with THIS card's name) plus the
// character's gacha-hit voice. Cuts are authored ~1.6x the 1280x720 stage, so lwfCut renders at 0.6.
// Click/Space advances, Esc closes.
function gachaShow(c, opKind) {
  const g = c.gacha, ops = (GMETA.gachaOp || {})[opKind] || [];
  const rar = Math.min(4, Math.max(1, c.rarity || 1));
  const op = ops[Math.min(2, Math.max(0, rar - 2))];
  const abs = (u) => (u && u[0] !== '/' ? '/' + u : u);  // lwf imageMap needs absolute URLs
  const pop = document.createElement('div');
  pop.className = 'gpop';
  pop.innerHTML = `<video class="gop" playsinline></video><canvas class="gcv"></canvas>
    <div class="ghint">${t('クリック / Space で進む ・ Esc で閉じる')}</div>`;
  document.body.appendChild(pop);
  const video = pop.querySelector('.gop'), cv = pop.querySelector('.gcv');
  cv.style.display = 'none';
  let voice = null, cut = null;
  const getRect = () => { const k = Math.min(pop.clientWidth / 1280, pop.clientHeight / 720); return { w: 1280 * k, h: 720 * k }; };
  const fit = () => { const r = getRect(); cv.style.width = r.w + 'px'; cv.style.height = r.h + 'px'; };
  fit(); const ro = new ResizeObserver(fit); ro.observe(pop);
  const close = () => {
    video.pause(); if (voice) voice.pause(); if (music) music.pause(); if (cut) cut.stop();
    pop.remove(); document.removeEventListener('keydown', key, true); ro.disconnect();
  };
  const key = (e) => { if (e.key === 'Escape') { e.stopImmediatePropagation(); close(); } else if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); next(); } };
  document.addEventListener('keydown', key, true);
  const art = abs(g.art);
  const playVoice = () => { if (g.voice && !voice) { voice = new Audio(g.voice); voice.volume = 1; voice.play().catch(() => {}); } };
  // Reveal sequence: opening movie → rarity-foreshadow waveform (cut_03_flash, colour = rarity) →
  // the card's line (cut_04_moji, when its image exists) → ★4: close-up sweep over the card art (cut_06,
  // lottery_upcut.png) → card reveal (cut_07) with name plate. Checked against a recording of the original
  // (10-pull, fqYK1MbRXd8): ★4 has the cut_06 close-up and its fanfare, ★3 / ★2 their own reveal music.
  const se = (GMETA.gachaSe || {}), navi = (GMETA.gachaNavi || {}), fan = (GMETA.gachaFanfare || {});
  const phases = [];
  if (op) phases.push({ video: op });
  // rarity-foreshadow waveform (colour = rarity) with its "appearance" SE + Anya's navi voice
  if (rar >= 2) phases.push({ cut: `argo_gacha_cut_03_flash_${rar}`, map: {}, scale: 0.6, se: rar === 4 ? se.syuppin2 : se.syuppin, navi: navi[rar] });
  // the card's line (台詞) as a vertical-text image on black (cut_04_moji_3 — the only moji cut the 2019
  // client loads; its bg slot keeps the cut's own black). The gacha-hit voice speaks this line, so it starts here.
  if (g.text) phases.push({ cut: 'argo_gacha_cut_04_moji_3', map: { 'lwf_replace_txt_cut04.png': abs(g.text) }, scale: 0.6, voice: true });
  // ★4 close-up: get2 starts here (its quiet 2.6 s intro, then the fanfare runs on under cut_07)
  const upcut = rar === 4 && (GMETA.gachaCuts || {}).argo_gacha_cut_06_4 && (g.upcut || g.art);
  if (upcut) phases.push({ cut: 'argo_gacha_cut_06_4', map: { 'lwf_replace_chara_cut06.png': abs(upcut) }, scale: 0.6, voice: true, music: fan.get2,
    ready: swapHalves(abs(upcut)) });
  const revealMusic = rar === 4 ? (upcut ? null : fan.get3) : rar === 3 ? fan.get1 : rar === 2 ? se.cha : null;
  phases.push({ cut: `argo_gacha_cut_07_${rar}`, music: revealMusic, map: {
    'lwf_replace_chara_cut07.png': art,
    'lwf_replace_chara_flash_cut07.png': g.silhouette ? abs(g.silhouette) : art,
    'lwf_replace_chara_name_cut07.png': g.plate ? abs(g.plate) : `/data/gachaname/${c.id}.png`,
  }, scale: 0.6, voice: true, last: true });

  let idx = -1, seAudio = null, music = null;
  const run = (i) => {
    if (i <= idx || i >= phases.length) return;
    idx = i;
    const ph = phases[i];
    if (ph.voice) playVoice();
    if (ph.se) { try { seAudio = new Audio(ph.se); seAudio.play().catch(() => {}); } catch (e) {} }
    if (ph.navi) { try { const a = new Audio(ph.navi); a.play().catch(() => {}); } catch (e) {} }
    if (ph.music) { try { if (music) music.pause(); music = new Audio(ph.music); music.play().catch(() => {}); } catch (e) {} }
    if (ph.video) {
      if (cut) { cut.stop(); cut = null; }
      cv.style.display = 'none'; video.classList.remove('hidden');
      video.src = ph.video; video.onended = () => run(i + 1); video.onerror = () => run(i + 1);
      video.play().catch(() => run(i + 1));
    } else {
      video.pause(); video.classList.add('hidden'); cv.style.display = '';
      if (cut) cut.stop();
      const start = () => { if (idx === i) cut = lwfCut(cv, ph.cut, ph.map, getRect, ph.last ? null : () => run(i + 1), ph.scale); };
      if (ph.ready) ph.ready.then(start); else start();
    }
  };
  const next = () => (idx >= phases.length - 1 ? close() : run(idx + 1));
  pop.addEventListener('click', next);
  run(0);
}

export async function renderGacha(view, getJSON, openId) {
  const data = await getJSON('data/gacha.json');
  const cards = data.cards, statNames = data.stats;
  GMETA = data;  // needed before the filter chips are built
  const charas = [...new Map(cards.map((c) => [c.chara, c.name.replace(/[（(].*$/, '')])).entries()];
  let kind = 'adv', chara = 'all', rarity = 0, q = '', cat = 'all', elem = 0;
  const catOk = (c) => cat === 'all' || (cat === 'herofes' && c.heroFes) || (cat === 'limited' && c.limited && !c.heroFes)
    || (cat === 'normal' && !c.limited && !c.heroFes) || (cat === 'costume' && c.stories.length);
  const draw = () => {
    const list = cards.filter((c) => (kind === 'all' || c.kind === kind) && (chara === 'all' || c.chara === chara)
      && (!rarity || c.rarity === rarity) && catOk(c) && (!elem || c.element === elem) && (!q || (c.title + c.name).includes(q)));
    view.querySelector('.thumbs').innerHTML = list.map((c) => `<div class="thumb" data-id="${c.id}"><div class="im"><img class="pt-full" src="${c.thumb}" loading="lazy">${c.elementIcon ? `<img class="el-badge" src="${c.elementIcon}" alt="">` : ''}</div><div class="cap"><span class="stars">${stars(c.rarity)}</span>${c.heroFes ? ` <span class="mini herofes">${t('祭')}</span>` : c.limited ? ` <span class="mini limited">${t('限')}</span>` : ''} ${esc(c.title)}<br>${esc(c.name)}</div></div>`).join('');
    view.querySelector('.count').textContent = t('{n} 枚', { n: list.length });
  };
  view.innerHTML = `<h1>${t('カード')}</h1>
    <div class="chips" data-g="kind"><button class="on" data-v="adv">${t('冒険者')}</button><button data-v="assist">${t('アシスト')}</button><button data-v="all">${t('すべて')}</button></div>
    <div class="chips" data-g="rarity"><button class="on" data-v="0">${t('全レア')}</button>${[1, 2, 3, 4].map((n) => `<button data-v="${n}">${stars(n)}</button>`).join('')}</div>
    <div class="chips elems" data-g="elem"><button class="on" data-v="0">${t('全属性')}</button>${Object.entries(GMETA.elements).map(([b, n]) => {
      const ic = cards.find((c) => c.element === +b && c.elementIcon);
      return `<button data-v="${b}" title="${esc(t('{e}属性', { e: t(n) }))}">${ic ? `<img src="${ic.elementIcon}" alt="">` : ''}${esc(t(n))}</button>`;
    }).join('')}</div>
    <div class="chips" data-g="cat"><button class="on" data-v="all">${t('すべて')}</button><button data-v="normal">${t('通常')}</button><button data-v="limited">${t('期間限定')}</button><button data-v="herofes">${t('英雄祭')}</button><button data-v="costume">${t('衣装ストーリーあり')}</button></div>
    <div class="filters"><select class="search chara-sel"><option value="all">${t('全キャラ')}</option>${charas.map(([k, n]) => `<option value="${esc(k)}">${esc(n)}</option>`).join('')}</select>
    <input class="search qbox" placeholder="${t('称号・名前で検索…')}"></div>
    <p class="muted count"></p><div class="thumbs cards"></div>`;
  view.querySelectorAll('.chips').forEach((ch) => ch.addEventListener('click', (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    ch.querySelectorAll('button').forEach((x) => x.classList.toggle('on', x === b));
    if (ch.dataset.g === 'kind') kind = b.dataset.v; else if (ch.dataset.g === 'cat') cat = b.dataset.v;
    else if (ch.dataset.g === 'elem') elem = +b.dataset.v; else rarity = +b.dataset.v;
    draw();
  }));
  view.querySelector('.chara-sel').onchange = (e) => { chara = e.target.value; draw(); };
  view.querySelector('.qbox').oninput = (e) => { q = e.target.value.trim(); draw(); };
  const open = (c) => {
    let lb = 0, su = 0;  // open with no limit break / sublimation selected
    const first = cardImgs(c)[0];
    const v = viewer(cardPic(first[1], first[2]), cardSide(c, statNames, lb, su), () => { if (fxStop) { fxStop(); fxStop = null; } });
    v.classList.add('card-viewer');
    v.querySelector('.side').onclick = async (ev) => {
      const u = ev.target.closest('button[data-u]');
      if (u) {
        v.querySelectorAll('.imgsel button').forEach((x) => x.classList.toggle('on', x === u));
        v.querySelector('.stagepic').innerHTML = cardPic(u.dataset.u, u.dataset.fx);
        v.querySelector('.stagepic img').addEventListener('load', () => window.dispatchEvent(new Event('resize')));
        return;
      }
      const gp = ev.target.closest('.gacha-play');
      if (gp) { gachaShow(c, gp.dataset.op); return; }
      const st = ev.target.closest('.story-link');
      if (st) {
        ev.preventDefault();
        const idx = await getJSON('data/index.json');
        // each costume story's novels are one continuous story → play its segments seamlessly
        const groups = c.stories.map((s) => s.novels);
        playerPopup(st.dataset.key, { list: groups.flat(), segEnd: new Set(groups.map((g) => g[g.length - 1])), titles: idx.titles, getJSON });
        return;
      }
      const l = ev.target.closest('button[data-lb], button[data-su]');
      if (l) {
        if (l.dataset.lb !== undefined) lb = +l.dataset.lb; else su = +l.dataset.su;
        const side = v.querySelector('.side'), top = side.scrollTop;
        side.innerHTML = cardSide(c, statNames, lb, su);
        side.scrollTop = top;
      }
    };
  };
  view.querySelector('.thumbs').onclick = (e) => {
    const t = e.target.closest('.thumb');
    if (t) open(cards.find((x) => x.id === +t.dataset.id));
  };
  draw();
  if (openId) { const c = cards.find((x) => x.id === +openId); if (c) open(c); }
}
