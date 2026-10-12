// Player page UI (toolbar, keys, log, end card) shared by the full-page player and popups.
import { Player, rubyHTML, SKIP_DELAY } from './player.js?v=9';
import { t } from './i18n.js';

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

// per-viewer conveniences (read marks, settings): browser storage, guarded
// The Android app's "keep screen on" (player settings): 'play' while a story plays (default), 'always', 'off'
export function keepScreen(playing) {
  const mode = store.get('dm.keepScreen', 'play');
  window.DanMemoApp?.setKeepScreenOn?.(mode === 'always' || (mode === 'play' && playing));
}

export const store = {
  get(k, d) { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch {} },
};
export const readSet = new Set(store.get('dm.read', []));
export const markRead = (k) => { readSet.add(k); store.set('dm.read', [...readSet]); };

// message box look (per viewer): the original is a translucent dark-gray band
const BOX = { msgColor: '#1e1e1e', msgAlpha: 0.6, skipDelay: SKIP_DELAY };
function applyBox(rootEl, st) {
  const c = st.msgColor ?? BOX.msgColor, a = st.msgAlpha ?? BOX.msgAlpha;
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16) || 0);
  rootEl.style.setProperty('--msg-bg', `rgba(${r},${g},${b},${a})`);
  rootEl.style.setProperty('--msg-name-bg', `rgba(${r},${g},${b},${Math.min(1, a + 0.25)})`);
}

// LOG toggles: a second press (or Esc) closes the open log instead of stacking another one
function showLog(rootEl, p, onClose) {
  const open = rootEl.querySelector('.logpane');
  if (open) { open._close(); return; }
  const pane = document.createElement('div');
  pane._close = () => { pane.remove(); onClose && onClose(); };
  pane.className = 'logpane';
  pane.innerHTML = `<button class="vb" style="position:sticky;top:0;float:right;width:auto;padding:0 12px">${t('閉じる')}</button>` +
    p.log.map((l, i) => `<div class="row"><div class="nm">${esc(l.name)}</div><div>${rubyHTML(l.text)}</div>${l.voice ? `<button class="vb" data-i="${i}">♪</button>` : '<span></span>'}</div>`).join('');
  pane.addEventListener('click', (e) => {
    e.stopPropagation();
    const b = e.target.closest('button');
    if (!b) return;
    if (b.dataset.i) { const a = new Audio(p.log[+b.dataset.i].voice); a.volume = p.settings.voice; a.play(); } else pane._close();
  });
  rootEl.appendChild(pane);
  pane.scrollTop = pane.scrollHeight;
}

/**
 * Mount the player UI into `container` and play `key`.
 * opts: { list: [keys] (for 次へ), titles: {key: title}, getJSON, exitLabel,
 *         onExit(): leave (back button / Esc), onNext(key)?: open another novel (default: remount here) }
 * Returns { stop() }.
 */
export function mountPlayer(container, key, opts) {
  const ctl = { player: null, stopped: false };
  const titles = opts.titles || {};
  const list = opts.list && opts.list.length ? opts.list : [key];

  const detachKeys = [];
  const cleanup = () => {
    detachKeys.splice(0).forEach((f) => f());
    if (ctl.player) ctl.player.stop();
    ctl.player = null;
  };
  ctl.stop = () => { ctl.stopped = true; cleanup(); container.innerHTML = ''; keepScreen(false); };

  // the browser's full screen (hides Chrome's address bar and the phone's status bar); the Android app is
  // full screen already
  const canFullscreen = () => document.fullscreenEnabled && !/DanMemoApp/.test(navigator.userAgent);
  const toggleFullscreen = () => {
    if (document.fullscreenElement) return document.exitFullscreen().catch(() => {});
    document.documentElement.requestFullscreen({ navigationUI: 'hide' })
      .then(() => screen.orientation?.lock?.('landscape').catch(() => {}))
      .catch(() => {});
  };

  const open = async (k) => {
    cleanup();
    const novel = await opts.getJSON(`data/novel/${encodeURIComponent(k)}.json`);
    if (ctl.stopped) return;
    const settings = store.get('dm.settings', {});
    container.innerHTML = `<div class="player-wrap">
      <div class="player-bar">
        <button data-a="exit">${esc(opts.exitLabel || t('← 目録'))}</button>
        <span class="ttl">${esc(novel.title || k)}</span>
        <button data-a="auto">AUTO</button><button data-a="skip">SKIP</button><button data-a="log">LOG</button><button data-a="hide" title="${t('テキストボックスを隠す（スクリーンショット用・H／右クリック）')}">${t('非表示')}</button>
        <label class="muted">BGM <input type="range" min="0" max="1" step="0.05" data-v="bgm" value="${settings.bgm ?? 0.6}"></label>
        <label class="muted">${t('ボイス')} <input type="range" min="0" max="1" step="0.05" data-v="voice" value="${settings.voice ?? 1}"></label>
        <button data-a="box">${t('設定')}</button>${canFullscreen() ? `<button data-a="fs" title="${t('全画面')}">⛶</button>` : ''}
      </div>
      <div class="boxpanel hidden">
        <label>${t('色')} <input type="color" data-box="msgColor" value="${settings.msgColor ?? BOX.msgColor}"></label>
        <label>${t('不透明度')} <input type="range" min="0" max="1" step="0.05" data-box="msgAlpha" value="${settings.msgAlpha ?? BOX.msgAlpha}"></label>
        <label>${t('SKIP 間隔')} <input type="range" min="30" max="500" step="10" data-box="skipDelay" value="${settings.skipDelay ?? SKIP_DELAY}"> <span data-skipv>${((settings.skipDelay ?? SKIP_DELAY) / 1000).toFixed(2)}</span> ${t('秒')}</label>
        <button data-box-reset>${t('デフォルト')}</button>${window.DanMemoApp?.setKeepScreenOn ? `
        <label>${t('画面を常にオン')} <select data-keep>${[['play', '再生中'], ['always', '常に'], ['off', 'しない']].map(([v, l]) =>
          `<option value="${v}"${store.get('dm.keepScreen', 'play') === v ? ' selected' : ''}>${t(l)}</option>`).join('')}</select></label>` : ''}
      </div>
      <div class="player-root"></div>${gapNote(novel.gaps)}</div>`;
    const rootEl = container.querySelector('.player-root');
    const note = container.querySelector('.gapnote');
    if (note) { note.onclick = () => note.remove(); setTimeout(() => note.remove(), 9000); }
    const bar = container.querySelector('.player-bar');
    const panel = container.querySelector('.boxpanel');
    applyBox(rootEl, settings);
    panel.addEventListener('input', (e) => {
      const k = e.target.dataset.box;
      if (!k) return;
      settings[k] = k === 'msgColor' ? e.target.value : +e.target.value;
      if (k === 'skipDelay') panel.querySelector('[data-skipv]').textContent = (settings[k] / 1000).toFixed(2);
      store.set('dm.settings', { ...store.get('dm.settings', {}), [k]: settings[k] });
      if (ctl.player) ctl.player.settings[k] = settings[k];  // the Player keeps its own copy
      applyBox(rootEl, settings);
    });
    keepScreen(true);
    const keepSel = panel.querySelector('[data-keep]');
    if (keepSel) keepSel.onchange = () => { store.set('dm.keepScreen', keepSel.value); keepScreen(true); };
    panel.querySelector('[data-box-reset]').onclick = () => {
      Object.assign(settings, BOX);
      if (ctl.player) Object.assign(ctl.player.settings, BOX);
      store.set('dm.settings', { ...store.get('dm.settings', {}), ...BOX });
      panel.querySelector('[data-box=msgColor]').value = BOX.msgColor;
      panel.querySelector('[data-box=msgAlpha]').value = BOX.msgAlpha;
      panel.querySelector('[data-box=skipDelay]').value = BOX.skipDelay;
      panel.querySelector('[data-skipv]').textContent = (BOX.skipDelay / 1000).toFixed(2);
      applyBox(rootEl, settings);
    };
    const p = (ctl.player = window.__p = new Player(rootEl, { settings }));
    if (store.get('dm.auto', false)) { p.setAuto(true); bar.querySelector('[data-a=auto]').classList.add('on'); }

    // Hold left Ctrl to skip (like PC visual novels); the SKIP button stays a toggle.
    const skipBtn = bar.querySelector('[data-a=skip]');
    // the SKIP toggle lasts across the continuous playback of several novels (a new Player each)
    let ctrlHeld = false;
    if (ctl.skipToggled) { p.setSkip(true); skipBtn.classList.add('on'); }
    const setHold = (on) => {
      if (ctrlHeld === on) return;
      ctrlHeld = on;
      const want = on || ctl.skipToggled;
      if (p.skip !== want) p.setSkip(want);
      skipBtn.classList.toggle('on', want);
    };
    // 非表示: hide the message window for screenshots. While hidden, a click / Space / Enter only brings
    // it back (never advances) and AUTO is paused so the scene stays put.
    const hideBtn = bar.querySelector('[data-a=hide]');
    let hidden = false;
    const setHidden = (on) => {
      if (hidden === on) return;
      hidden = on;
      rootEl.classList.toggle('ui-hidden', on);
      hideBtn.classList.toggle('on', on);
      p.hold = on;
    };
    rootEl.addEventListener('click', (e) => { if (hidden) { e.stopPropagation(); setHidden(false); } }, true);
    rootEl.addEventListener('contextmenu', (e) => { e.preventDefault(); setHidden(!hidden); });
    bar.addEventListener('click', (e) => {
      const b = e.target.closest('button[data-a]');
      if (!b) return;
      const a = b.dataset.a;
      if (a === 'exit') opts.onExit();
      if (a === 'auto') { p.setAuto(!p.auto); b.classList.toggle('on', p.auto); store.set('dm.auto', p.auto); }
      if (a === 'skip') { p.setSkip(!p.skip); ctl.skipToggled = p.skip; b.classList.toggle('on', p.skip); }
      if (a === 'log') { showLog(rootEl, p, () => b.classList.remove('on')); b.classList.toggle('on', !!rootEl.querySelector('.logpane')); }
      if (a === 'hide') setHidden(!hidden);
      if (a === 'box') { panel.classList.toggle('hidden'); b.classList.toggle('on', !panel.classList.contains('hidden')); }
      if (a === 'fs') toggleFullscreen();
    });
    // Phones held sideways (short screens): the bar floats over the stage and fades after a few seconds; a tap
    // along the top edge (or the mouse there) brings it back.
    const wrap = container.querySelector('.player-wrap');
    const shortScreen = window.matchMedia('(max-height: 560px)');
    let idleT = 0;
    const wake = () => {
      wrap.classList.remove('bar-idle');
      clearTimeout(idleT);
      if (shortScreen.matches) idleT = setTimeout(() => { if (panel.classList.contains('hidden')) wrap.classList.add('bar-idle'); }, 3000);
    };
    wake();
    bar.addEventListener('pointerdown', wake);
    rootEl.addEventListener('click', (e) => {
      if (wrap.classList.contains('bar-idle') && e.clientY - rootEl.getBoundingClientRect().top < 48) { e.stopPropagation(); wake(); }
    }, true);
    wrap.addEventListener('mousemove', (e) => { if (e.clientY < 60) wake(); });
    detachKeys.push(() => clearTimeout(idleT));
    bar.querySelectorAll('input[data-v]').forEach((inp) => (inp.oninput = () => {
      p.settings[inp.dataset.v] = +inp.value;
      if (inp.dataset.v === 'bgm' && p.bgm) p.bgm.volume = +inp.value * (p.bgmLevel ?? 1);
      store.set('dm.settings', { ...store.get('dm.settings', {}), [inp.dataset.v]: +inp.value });
    }));
    // capture phase so Esc closes only the player (not a card viewer underneath)
    const onKey = (e) => {
      if (e.code === 'ControlLeft') { setHold(true); return; }
      if (e.target.closest && e.target.closest('input')) return;
      const log = rootEl.querySelector('.logpane');
      if (log && e.key === 'Escape') { e.preventDefault(); e.stopImmediatePropagation(); log._close(); return; }
      if (log) { if (e.key === ' ' || e.key === 'Enter') e.preventDefault(); return; }  // keys don't drive the story (or a focused button) while the log is open
      if (e.key === 'h' || e.key === 'H') { setHidden(!hidden); return; }
      if (hidden && (e.key === ' ' || e.key === 'Enter' || e.key === 'Escape')) { e.preventDefault(); e.stopImmediatePropagation(); setHidden(false); return; }
      if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); p.click(); }
      if (e.key === 'Escape') { e.stopImmediatePropagation(); opts.onExit(); }
    };
    const onKeyUp = (e) => { if (e.code === 'ControlLeft') setHold(false); };
    const onBlur = () => setHold(false);  // releasing Ctrl outside the window must not leave skip on
    document.addEventListener('keydown', onKey, true);
    document.addEventListener('keyup', onKeyUp, true);
    window.addEventListener('blur', onBlur);
    detachKeys.push(() => {
      document.removeEventListener('keydown', onKey, true);
      document.removeEventListener('keyup', onKeyUp, true);
      window.removeEventListener('blur', onBlur);
    });

    const done = await p.play(novel);
    if (!done || ctl.player !== p) return;
    markRead(k);
    const pos = list.indexOf(k);
    const next = pos >= 0 && pos + 1 < list.length ? list[pos + 1] : null;
    // Continuous playback: a single story split into segments (the novels of one stage / one
    // costume story) flows straight on. The end card only appears at a segment boundary — a key
    // listed in opts.segEnd — or at the very end. Without segEnd every novel is its own segment.
    if (next && opts.segEnd && !opts.segEnd.has(k)) return open(next);
    const end = document.createElement('div');
    end.className = 'endcard';
    end.innerHTML = `<div style="color:var(--gold-2);font-size:20px">${esc(novel.title || k)}</div>
      ${next ? `<button data-n>${t('次へ：{t}', { t: esc(titles[next] || next) })}</button>` : `<div class="muted">${t('最後のシナリオです')}</div>`}
      <button data-r>${t('もう一度')}</button><button data-x>${esc(opts.exitLabel || t('目録へ'))}</button>`;
    rootEl.appendChild(end);
    const goNext = () => (opts.onNext ? opts.onNext(next) : open(next));
    if (next) {
      end.querySelector('[data-n]').onclick = goNext;
      if (p.auto) setTimeout(() => { if (ctl.player === p) goNext(); }, 1500);
    }
    end.querySelector('[data-r]').onclick = () => open(k);
    end.querySelector('[data-x]').onclick = () => opts.onExit();
  };
  open(key);
  return ctl;
}

/** "画像 2 ・ ボイス 5": what a story lacks (build_web.py's gaps: assets no configured source has) */
export function gapList(g) {
  const L = [['img', '画像 {n}'], ['movie', '動画 {n}'], ['chara', '立ち絵 {n}'], ['fx', 'エフェクト {n}'], ['voice', 'ボイス {n}'], ['sound', 'BGM・効果音 {n}']];
  return L.filter(([k]) => g && g[k]).map(([k, s]) => t(s, { n: g[k] })).join(' ・ ');
}
// a notice over the stage at the start of a story some of whose pictures / movies / portraits / effects are lost
function gapNote(g) {
  if (!g || !['img', 'movie', 'chara', 'fx'].some((k) => g[k])) return '';
  return `<div class="gapnote">${esc(t('このシナリオの素材の一部は、現存するどのデータにも含まれていないため表示されません：{list}', { list: gapList(g) }))}</div>`;
}

/** Play in a full-screen popup over the current page; closing returns to it. */
export function playerPopup(key, opts) {
  const pop = document.createElement('div');
  pop.className = 'ppop';
  document.body.appendChild(pop);
  const close = () => { ctl.stop(); pop.remove(); opts.onClose && opts.onClose(); };
  const ctl = mountPlayer(pop, key, { ...opts, exitLabel: t('✕ 閉じる'), onExit: close });
  pop._close = close;
  return ctl;
}
