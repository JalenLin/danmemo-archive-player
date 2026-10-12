// DanMemo novel player: executes decoded novelCommand lists on a 1280x720 DOM stage.
// Command numbers are the decrypted enum values (see docs/PROCESS.md "指令對照").

const W = 1280, H = 720;
const POS = { left_end: 160, left: 320, center: 640, right: 960, right_end: 1120 };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const num = (v, d = 0) => (v === undefined || v === '' || isNaN(parseFloat(v)) ? d : parseFloat(v));
const hex = (c, d = '#000') => (/^[0-9a-fA-F]{6}$/.test(c || '') ? '#' + c : d);

function rubyHTML(s) {
  const esc = (t) => t.replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
  return esc(s).replace(/\[r=([^\]]*)\](.*?)\[\/r\]/g, '<ruby>$2<rt>$1</rt></ruby>').replace(/\n/g, '<br>');
}

// Split ruby-marked text into display units for the typewriter (a ruby group types as one unit).
function units(s) {
  const out = [];
  const re = /\[r=([^\]]*)\](.*?)\[\/r\]/g;
  let last = 0, m;
  const plain = (t) => { for (const ch of t) out.push(ch === '\n' ? '<br>' : ch.replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]))); };
  while ((m = re.exec(s))) { plain(s.slice(last, m.index)); out.push(`<ruby>${m[2]}<rt>${m[1]}</rt></ruby>`); last = re.lastIndex; }
  plain(s.slice(last));
  return out;
}

const FRAME = 1000 / 30;  // ms per command in the original engine
// Easing names the scripts pass to moves / zooms (27 a[5], 41 a[3], 23/24/25, 68 a[6]); 'liner' and an empty
// value are linear. CSS curves for Web Animations, functions for the rAF-driven LWF moves.
const EASE_BEZIER = {
  easeInSine: [0.12, 0, 0.39, 0], easeOutSine: [0.61, 1, 0.88, 1], easeInOutSine: [0.37, 0, 0.63, 1],
  easeInQuad: [0.11, 0, 0.5, 0], easeOutQuad: [0.5, 1, 0.89, 1], easeInOutQuad: [0.45, 0, 0.55, 1],
  easeInCubic: [0.32, 0, 0.67, 0], easeOutCubic: [0.33, 1, 0.68, 1], easeInOutCubic: [0.65, 0, 0.35, 1],
  easeInQuart: [0.5, 0, 0.75, 0], easeOutQuart: [0.25, 1, 0.5, 1], easeInOutQuart: [0.76, 0, 0.24, 1],
  easeInQuint: [0.64, 0, 0.78, 0], easeOutQuint: [0.22, 1, 0.36, 1], easeInOutQuint: [0.83, 0, 0.17, 1],
  easeInExpo: [0.7, 0, 0.84, 0], easeOutExpo: [0.16, 1, 0.3, 1], easeInOutExpo: [0.87, 0, 0.13, 1],
  easeInCirc: [0.55, 0, 1, 0.45], easeOutCirc: [0, 0.55, 0.45, 1], easeInOutCirc: [0.85, 0, 0.15, 1],
  easeInBack: [0.36, 0, 0.66, -0.56], easeOutBack: [0.34, 1.56, 0.64, 1], easeInOutBack: [0.68, -0.6, 0.32, 1.6],
};
const isEase = (v) => typeof v === 'string' && (v in EASE_BEZIER || v === 'liner' || v === 'linear');
const cssEase = (v) => (EASE_BEZIER[v] ? `cubic-bezier(${EASE_BEZIER[v].join(',')})` : 'linear');
function easeFn(v) {  // the same curves as functions of t in [0,1]
  const b = EASE_BEZIER[v];
  if (!b) return (t) => t;
  const [x1, y1, x2, y2] = b, B = (a1, a2, t) => 3 * a1 * t * (1 - t) ** 2 + 3 * a2 * t * t * (1 - t) + t ** 3;
  return (x) => { let lo = 0, hi = 1; for (let i = 0; i < 20; i++) { const m = (lo + hi) / 2; if (B(x1, x2, m) < x) lo = m; else hi = m; } return B(y1, y2, (lo + hi) / 2); };
}
export const SKIP_DELAY = 120;  // default ms per line while skipping (user-adjustable)
// true when an effect canvas has nothing visible left (sampled)
// lwf.js drops a URL's cache entry when its last instance is destroyed; a load of that URL still
// waiting for textures then throws inside the library (reading z$Wa of the dropped entry) and never
// calls onload. So destroying an instance waits until no load of its URL is in flight.
const lwfLoading = new Map();   // src → loads in flight
const lwfDeferred = new Map();  // src → instances to destroy once those loads finish
function lwfFree(src, lwf) {
  if (lwfLoading.get(src)) { if (!lwfDeferred.has(src)) lwfDeferred.set(src, []); lwfDeferred.get(src).push(lwf); return; }
  try { lwf.destroy(); } catch (e) {}
}
function lwfLoaded(src) {
  const n = (lwfLoading.get(src) || 1) - 1;
  if (n) { lwfLoading.set(src, n); return; }
  lwfLoading.delete(src);
  const later = lwfDeferred.get(src) || [];
  lwfDeferred.delete(src);
  for (const l of later) lwfFree(src, l);
}

function lwfBlank(c) {
  try { const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; for (let i = 3; i < d.length; i += 64) if (d[i] > 8) return false; return true; } catch (e) { return false; }
}

export class Player {
  constructor(root, opts = {}) {
    this.root = root;
    this.opts = opts;
    this.settings = Object.assign({ bgm: 0.6, se: 0.8, voice: 1.0, textSpeed: 28, autoDelay: 1.2 }, opts.settings || {});
    this.root.innerHTML = `
      <div class="stage">
        <div class="layer" data-l="bg"></div>
        <div class="layer" data-l="mid"></div>
        <div class="layer" data-l="chars"></div>
        <div class="layer" data-l="fg"></div>
        <div class="layer" data-l="fx"></div>
        <div class="layer" data-l="still"></div>
        <div class="layer atext"></div>
        <div class="desc"><div class="desc-bg"></div><div class="desc-text"></div></div>
        <div class="msg hidden"><div class="msg-name"></div><div class="msg-text"></div><div class="msg-next">▼</div></div>
        <div class="titlecard hidden"><div class="tc-sub"></div><div class="tc-title"></div></div>
        <div class="choice hidden"></div>
        <div class="tint"></div>
        <div class="fade"></div>
        <video class="movie hidden" playsinline></video>
      </div>
      <svg width="0" height="0" style="position:absolute"><defs></defs></svg>`;
    this.stage = root.querySelector('.stage');
    this.L = {};
    root.querySelectorAll('.layer[data-l]').forEach((e) => (this.L[e.dataset.l] = e));
    this.msg = root.querySelector('.msg');
    this.msgName = root.querySelector('.msg-name');
    this.msgText = root.querySelector('.msg-text');
    this.desc = root.querySelector('.desc');
    this.descBg = root.querySelector('.desc-bg');
    this.descText = root.querySelector('.desc-text');
    this.fadeEl = root.querySelector('.fade');
    this.tintEl = root.querySelector('.tint');  // 50 ScreenChangeFadeTo / 51 its release — separate from 19/20
    this.titleEl = root.querySelector('.titlecard');
    this.choiceEl = root.querySelector('.choice');
    this.atext = root.querySelector('.atext');
    this.movie = root.querySelector('.movie');
    this.defs = root.querySelector('defs');
    this.auto = false;
    this.skip = false;
    this.log = [];
    this.onLine = opts.onLine || (() => {});
    this._clickWaiters = [];
    this.stage.addEventListener('click', (e) => {
      if (e.target.closest('.choice')) return;
      this.click();
    });
    this.fit();
    this._ro = new ResizeObserver(() => this.fit());
    this._ro.observe(root);
    this.fx = new Map();
    this._last = performance.now();
    const tick = (t) => {
      if (this.stopped === 'dead') return;
      const dt = Math.min(0.1, (t - this._last) / 1000);
      this._last = t;
      for (const f of this.fx.values()) {
        if (f.tw) {
          const p = Math.min(1, (t - f.tw.t0) / f.tw.ms), k = f.tw.ease(p);
          f.x = f.tw.x0 + (f.tw.x1 - f.tw.x0) * k; f.y = f.tw.y0 + (f.tw.y1 - f.tw.y0) * k;
          this.lwfPlace(f);
          if (p >= 1) f.tw = null;
        }
        try { f.lwf.exec(dt); f.lwf.render(); } catch (e) { /* ignore broken effect */ }
      }
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }

  fit() {
    const r = this.root.getBoundingClientRect();
    const s = Math.min(r.width / W, r.height / H) || 1;
    this.stage.style.transform = `translate(-50%,-50%) scale(${s})`;
  }

  // ---------------------------------------------------------------- control
  click() {
    if (this._typing) { this._typing.finish(); return; }
    const w = this._clickWaiters.splice(0);
    w.forEach((f) => f());
  }
  waitClick() {
    if (this.skip) return sleep(this.settings.skipDelay ?? SKIP_DELAY);
    return new Promise((res) => {
      this._clickWaiters.push(res);
      if (this.auto) {
        const v = this.voice;
        // this.hold (UI hidden for a screenshot) keeps AUTO from moving on until it is released
        const go = () => setTimeout(() => { if (this.hold) return go(); const i = this._clickWaiters.indexOf(res); if (i >= 0) { this._clickWaiters.splice(i, 1); res(); } }, this.settings.autoDelay * 1000);
        if (v && !v.paused && !v.ended) v.addEventListener('ended', go, { once: true }); else go();
      }
    });
  }
  setAuto(v) { this.auto = v; if (v) this.click(); }
  setSkip(v) { this.skip = v; if (v) this.click(); }
  d(sec) { return this.skip ? 0 : Math.max(0, sec) * 1000; }
  wait(sec) { const ms = this.d(sec); return ms ? sleep(ms) : Promise.resolve(); }
  bg(c, p) { Promise.resolve(p).catch((e) => console.warn('cmd failed', c, e)); }
  // Opacity transitions don't block the script any more, so they can overlap on one element: a newer
  // one replaces the older, and only the current one (not replaced, not cancelled by a scene reset)
  // pins its end value and runs `done`.
  fadeTo(el, frames, sec, done) {
    el._fade?.cancel();
    const a = el.animate(frames, { duration: this.d(sec) || 1, fill: 'forwards', easing: 'ease-in-out' });
    el._fade = a;
    return a.finished.then(() => {
      if (el._fade !== a) return;
      el._fade = null;
      el.style.opacity = frames[frames.length - 1].opacity; a.cancel();
      if (done) done();
    }, () => {});
  }
  fadeStop(el) { if (el._fade) { el._fade.cancel(); el._fade = null; } }
  anim(el, frames, sec, extra = {}) {
    const ms = this.d(sec);
    const a = el.animate(frames, { duration: ms || 1, fill: 'forwards', easing: 'ease-in-out', ...extra });
    return a.finished.catch(() => {});
  }

  stop() {
    this.stopped = 'dead';
    for (const f of this.fx.values()) this.lwfDestroy(f);
    this.fx.clear();
    this.click();
    this.stopAudio();
    this._ro.disconnect();
  }
  stopAudio() {
    for (const a of [this.bgm, this.voice, ...(this.loops || []), ...(this.ses || []).map((x) => x.a)]) if (a) { a.pause(); a.src = ''; }
    this.bgm = null; this.loops = []; this.ses = [];
  }

  res(key) { return this.novel.res[key]; }

  // ---------------------------------------------------------------- main loop
  async play(novel) {
    this.novel = novel;
    this.stopped = false;
    this.images = {};
    this.chars = {};
    this.loops = [];
    this.ses = this.ses || [];  // SEs still sounding carry over into the next story of a run
    this.peTarget = 'background';
    const cmds = novel.cmds;
    this.jumps = [];  // after a chosen branch A, skip branch B: [{ at: first B command, n: its length }]
    for (this.pc = 0; this.pc < cmds.length; this.pc++) {
      if (this.stopped) return false;
      for (let j; (j = this.jumps.findIndex((x) => x.at === this.pc)) >= 0;) { this.pc += this.jumps[j].n; this.jumps.splice(j, 1); }
      if (this.pc >= cmds.length) break;
      const t0 = performance.now();
      try { await this.exec(cmds[this.pc]); } catch (e) { console.warn('cmd failed', cmds[this.pc], e); }
      // the original engine runs one command per 30fps frame: rapid-fire sequences (e.g. 30 dagger
      // throws of 5 commands each) take ~6s there, not an instant
      const left = FRAME - (performance.now() - t0);
      if (left > 1) await this.wait(left / 1000);
    }
    this.msg.classList.add('hidden');
    for (const a of this.loops) a.pause();
    return true;
  }

  async exec(c) {
    const [t, ...a] = c;
    switch (t) {
      // Image and portrait fades block (checked against the original recording, 45_01: the dialogue box
      // waits for a 1.0 s background crossfade; the black gap before a fade-in includes 6's 0.5 s and 1's
      // 1.0 s — 4.05 s in the original). Character moves / zooms (27, 41) don't: シャクティ's 20 s pan
      // in 45_03 runs on under the following lines.
      case 1: return this.imageShow(a[0], a[1] || 'background', a[2], num(a[3], 0.5));
      case 2: return this.imageHide(a[0], a[2] === 'immediately' ? 0 : num(a[3], 0.5));
      case 3: return this.imageShow(a[0], a[1] || 'foreground', a[2], num(a[3], 0.5));
      case 40: this.imageState(a[0], true); return;
      case 67: return this.imageHide(a[0], 0);
      // image pans/zooms run alongside the following commands (slow camera moves)
      case 23: { const s = this.imageState(a[0]), r = a[4] === 'relative'; this.imageXform(a[0], { x: (r ? s.x : 0) + num(a[1]), y: (r ? s.y : 0) + num(a[2]) }, num(a[3]), a.slice(4).find(isEase)); return; }
      case 24: this.imageXform(a[0], { s: num(a[1], 1) }, num(a[2]), a.slice(3).find(isEase)); return;
      case 25: this.imageXform(a[0], { r: num(a[3]) }, num(a[4]), a.slice(5).find(isEase)); return;

      case 5: return this.charSet(a[0], a[1], POS[a[2]] ?? 640);
      case 36: return this.charAppear(a);
      case 6: return this.charShowHide(a, true);
      case 7: return this.charShowHide(a, false);
      case 39: return this.charFace(a[0], a[1]);
      case 10: return this.charFocus(a[0], a[1]);
      case 27: return this.bg(c, this.charMove(a[0], num(a[1]), num(a[2]), num(a[3]), a[4] !== 'absolute', cssEase(a[5])));
      // reaction nudge: change face and jolt the portrait by (x,y) with an overshoot bounce
      case 8: return this.manpu(a[0], num(a[1]), num(a[2]), a[4]);  // emotion mark [portrait, dx, dy, ?, mark, over]
      case 41: return this.bg(c, this.charScale(a[0], num(a[1], 1), num(a[2]), cssEase(a[3])));
      case 9: return this.charHop(a[0]);
      case 38: { const st = this.charState(a[0]); st.el.style.zIndex = String(1000 + Math.round(num(a[1]))); return; }  // CharacterZOrder
      case 49: return this.charRotate(a[0], num(a[1]), num(a[2]));  // CharacterRotate [portrait, degrees, s]

      case 11: return this.talk(a, true);
      case 12: return this.talk(a, false);
      case 14: return this.selection(a);
      // TalkClose doesn't block: in the original the astrea title (4) starts 1 s (the following 15) into
      // a '29 3.0' narration fade — timed by the logo against the effect's 475 frames
      case 29: this.msg.classList.add('hidden'); return this.bg(c, this.narrClear(num(a[0], 0.3)));
      case 44: return this.descShow(a[0], num(a[1], 0.5), num(a[2], 0.5));
      case 45: return this.narrate(a);
      case 21: return this.titleShow(a[0], a[1]);

      case 15: return this.wait(num(a[0]));
      // 51 releases the 50 tint (221 times the previous screen command is a 50) over a[0] s
      case 51: { const p = this.tint(null, 0, num(a[0])); return a[1] === 'wait' ? p : undefined; }
      // blank seconds = 1.0 (measured in the original: [19] 1.0 s, [20] 1.0 s ×3 in 45_01)
      case 19: return this.fade(hex(a[1], '#000'), 1, num(a[0], 1)).then(() => this.sceneReset());  // a[1]: colour (ffffff ×1284)
      case 20: return this.fade(null, 0, num(a[0], 1));
      // 50 [colour, layer, seconds, opacity, wait]: e.g. "10.0 1.0" = darken over 10 s, "1.0 0.5" = half-dark
      case 50: { const p = this.tint(hex(a[0]), num(a[3], 1), num(a[2]), a[1]); return a[4] === 'wait' ? p : undefined; }
      case 32: { const p = this.flash(hex(a[0], '#fff'), num(a[2]), num(a[3]), num(a[4])); return a[5] === 'no_wait' ? undefined : p; }
      case 52: { const p = this.flash(hex(a[0], '#fff'), num(a[3]), 0, num(a[4]), num(a[2], 1)); return a[5] === 'wait' ? p : undefined; }
      case 16: { const tgt = (a[0] === 'character' || a[0] === 'image') && a[1] ? a[0] + '/' + a[1] : a[0]; return this.quake(tgt, num(a[2], 10), num(a[3], num(a[2], 10)), num(a[4], 0.5)); }  // amp X, amp Y

      case 22: case 31: return this.bgmStart(a[0], num(a[1]));
      case 30: return this.bgmStop(num(a[0], 1));
      case 37: return this.volume(a[0], num(a[1], 1), num(a[2]));
      case 18: return this.se(a[0], num(a[1]));
      case 33: return this.seStop(a[0], num(a[1]), num(a[2], 0.3));  // SeStop: se, delay, fade-out
      case 42: for (const l of this.loops) l.pause(); this.loops = []; return;

      case 64: this.peTarget = a[0] || 'none'; this.peChars = a.slice(1).filter((k) => k && k.startsWith('novel_portrait')); return;
      case 65: { const p = this.peStart(a); return a[0] === 'wait' ? p : undefined; }
      case 66: { const p = this.peEnd(a); return a[0] === 'wait' ? p : undefined; }

      case 60: return this.atextSet(a);
      case 61: return this.atextShow(a);
      case 62: return this.atextMove(a);
      case 63: return this.atextRemove(a[0], num(a[1]));

      case 17: return this.playMovie(a[0], a[1] === 'skip_enable');
      // EffectShow [key, x, y, wait, 'fade', fadeSec, rotation]
      // waits unless 'no_wait' (written out 16,050×, so blank — 688× — is the waiting default; the
      // astrea_record title logo plays in full before the fade-out in the original)
      case 4: { const p = this.lwfOnce(a[0], num(a[1], 640), num(a[2], 360), num(a[6]), a[4] === 'fade' ? num(a[5]) : 0); return a[3] === 'no_wait' ? undefined : p; }
      // EffectHide: ends the scenario effect(s) started by 4 (EffectShow) — 1413/1434 uses follow one
      case 53: { const p = this.effectHide(a[0], a[2] === 'fade' ? num(a[3]) : 0); return a[4] === 'wait' ? p : undefined; }
      case 54: return this.lwfSet(a[0], a[1], num(a[2], 640), num(a[3], 360));
      case 55: { const p = this.lwfShow(a[0], a[1], null, null, num(a[3])); return a[4] === 'wait' ? p : undefined; }
      case 56: { const p = this.lwfHide(a[0], a[1], num(a[3])); return a[4] === 'wait' ? p : undefined; }
      // 54 Set → 58 scale / 59 rotation / 69 z-order / 68 move / 57 flip / 70 parent → 55 Show: properties of
      // the instance Set just made (58 sits between 54 and 55 on the same instance in 930+175 cases)
      case 58: { const f = this.fxGet(a[0], a[1]); if (f) { f.scale = num(a[2], 1); this.lwfPlace(f); } return; }
      case 59: { const f = this.fxGet(a[0], a[1]); if (f) { f.rot = num(a[2]); this.lwfPlace(f); } return; }
      case 68: return this.lwfMove(a);
      // scenario LWF effects (auras, sparkles, explosions). 69 offsets x from centre; 57 shows by
      // label; 70 attaches to a character/image (shown at centre here as a best effort).
      case 69: return this.lwfZ(a[0], a[1], num(a[2]));
      case 57: { const f = this.fxGet(a[0], a[1]); if (f) { f.flipX = a[2] === '1'; f.flipY = a[3] === '1'; this.lwfPlace(f); } return; }
      case 70: return this.lwfParent(a[0], a[1], a[3], a[4]);
      default: return; // 13/28/43/49/71/74: markers, achievements, battle setup — not rendered
    }
  }

  // ---------------------------------------------------------------- images
  layerOf(name) {
    if (name === 'still') return this.L.still;
    if (name === 'foreground') return this.L.fg;
    if (name === 'middle') return this.L.mid;
    return this.L.bg;
  }
  imageState(key, reset) {
    let st = this.images[key];
    if (!st) {
      const el = document.createElement('img');
      el.className = 'img';
      el.style.opacity = 0;
      const src = this.res(key);
      if (src) el.src = src;
      st = this.images[key] = { el, x: 0, y: 0, s: 1, r: 0 };
    }
    if (reset) Object.assign(st, { x: 0, y: 0, s: 1, r: 0 });
    this.applyXform(st);
    return st;
  }
  xf(st) { return `translate(-50%,-50%) translate(${st.x}px,${-st.y}px) scale(${st.s}) rotate(${st.r}deg)`; }
  applyXform(st) { st.el.getAnimations().forEach((a) => a.cancel()); st.el.style.transform = this.xf(st); }
  async imageXform(key, ch, sec, easing) {
    const st = this.imageState(key);
    const from = this.xf(st);
    Object.assign(st, ch);
    const to = this.xf(st);
    st.el.style.transform = to;
    if (sec > 0 && !this.skip) await this.anim(st.el, [{ transform: from }, { transform: to }], sec, { fill: 'none', easing: cssEase(easing) });
  }
  async imageShow(key, layerName, trans, sec) {
    const st = this.imageState(key);
    const layer = this.layerOf(layerName);
    const old = [...layer.children].filter((e) => e !== st.el);
    layer.appendChild(st.el);
    layer._top = st.el;
    const dur = trans === 'immediately' ? 0 : sec;
    await this.fadeTo(st.el, [{ opacity: getComputedStyle(st.el).opacity }, { opacity: 1 }], dur,
      () => old.forEach((e) => e !== layer._top && e.remove()));  // not one that was shown again meanwhile
  }
  async imageHide(key, sec) {
    const st = this.images[key];
    if (!st || !st.el.parentNode) return;
    await this.fadeTo(st.el, [{ opacity: getComputedStyle(st.el).opacity }, { opacity: 0 }], sec, () => st.el.remove());
  }

  // ---------------------------------------------------------------- characters
  charState(key) {
    let st = this.chars[key];
    if (st) return st;
    const info = this.res(key);
    const el = document.createElement('div');
    el.className = 'char';
    el.innerHTML = `<div class="pt"><img class="body"><img class="face"></div>`;
    const body = el.querySelector('.body'), face = el.querySelector('.face');
    if (info && info.body) {
      body.src = info.base + '.body.png';
      face.style.left = (info.cut ? info.cut[0] : 0) + 'px';
      face.style.top = (info.cut ? info.cut[1] : 0) + 'px';
    } else {
      body.remove();
      face.classList.add('full');
    }
    st = this.chars[key] = { key, info, el, face, x: 640, y: 0, s: 1, vis: false, focus: 'auto' };
    el.style.opacity = 0;
    this.L.chars.appendChild(el);
    this.charPlace(st);
    return st;
  }
  charPlace(st) { st.el.style.transform = `translate(${st.x}px,${-st.y}px) scale(${st.s})${st.r ? ` rotate(${st.r}deg)` : ''}`; }
  async charRotate(key, deg, sec) {
    const st = this.charState(key);
    const from = st.el.style.transform;
    st.r = deg; this.charPlace(st);
    if (sec > 0 && !this.skip) await this.anim(st.el, [{ transform: from }, { transform: st.el.style.transform }], sec, { fill: 'none' });
  }
  // emotion marks (漫符): files/icon/novel/manpu_<mark>.png, offset from the face, pop in, then fade
  async manpu(key, dx, dy, mark) {
    const st = this.charState(key), src = this.res('manpu.' + mark);
    if (!src || !st.info) return;
    const im = document.createElement('img');
    im.className = 'manpu'; im.src = src;
    const cut = st.info.cut || [0, 0], fs = st.info.fs || [140, 160];
    im.style.left = (cut[0] + fs[0] / 2 + dx) + 'px'; im.style.top = (cut[1] - dy) + 'px';
    st.el.querySelector('.pt').appendChild(im);
    await this.anim(im, [{ transform: 'translate(-50%,-50%) scale(0.4)', opacity: 0 }, { transform: 'translate(-50%,-50%) scale(1.15)', opacity: 1, offset: 0.6 }, { transform: 'translate(-50%,-50%) scale(1)', opacity: 1 }], 0.3);
    setTimeout(() => this.anim(im, [{ opacity: 1 }, { opacity: 0 }], 0.4).then(() => im.remove()), this.skip ? 0 : 1200);
  }
  charFace(key, face) {
    if (!key || !key.startsWith('novel_portrait')) return;
    const st = this.charState(key);
    const info = st.info;
    if (!info) return;
    let f = face && info.faces.includes(face) ? face : (st.faceName ?? (info.faces.includes('normal') ? 'normal' : info.faces[0]));
    if (f === undefined) return;
    st.faceName = f;
    const src = info.base + (f ? '.' + f : '') + '.png';
    if (!st.face.src.endsWith(src)) st.face.src = src;
  }
  charSet(key, face, x) {
    const st = this.charState(key);
    // CharacterSet re-initialises the portrait: a close-up zoom (41) does not carry over (2391 re-sets
    // happen while still zoomed; the original shows them at normal size)
    st.x = x; st.y = 0; st.s = 1;
    this.charPlace(st);
    this.charFace(key, face);
  }
  async charAppear(a) {
    const [key, face] = a;
    const st = this.charState(key);
    this.charFace(key, face);
    // [key, face, X, '', '', sec] = appear at X; [key, face, fromX, toX, sec, …] = slide fromX→toX.
    // Only a numeric a[3] means a slide; otherwise it's a static appear at a[2] (empty a[3] is not a 0 target).
    // a[5] = fade-in seconds (0.5 / 1.0 / 0.3 / 0 in 6,252 of 12,027 uses); without it the portrait pops in
    let to = num(a[2], 640), from = null, sec = 0;
    const slide = a[3] !== undefined && a[3] !== '' && !isNaN(parseFloat(a[3]));
    if (slide) { from = num(a[2]); to = num(a[3]); sec = num(a[4]); }
    const fade = st.vis ? 0 : num(a[5], 0);
    st.x = from ?? to; this.charPlace(st);
    st.vis = true;
    const fadeIn = fade > 0 ? this.fadeTo(st.el, [{ opacity: 0 }, { opacity: 1 }], fade)
      : (this.fadeStop(st.el), st.el.style.opacity = 1, Promise.resolve());
    await Promise.all([fadeIn, from !== null ? this.charMove(key, to, 0, sec, false) : null]);
  }
  async charShowHide(a, show) {
    const keys = a.filter((s) => s && s.startsWith('novel_portrait'));
    const rest = a.filter((s) => s && !s.startsWith('novel_portrait') && s !== 'none');
    const trans = rest.find((s) => isNaN(parseFloat(s))) || 'fade';
    const sec = trans === 'immediately' ? 0 : num(rest.find((s) => !isNaN(parseFloat(s))), 0.3);
    await Promise.all(keys.map((k) => {
      const st = this.charState(k);
      st.vis = show;
      const frames = show ? [{ opacity: 0 }, { opacity: 1 }] : [{ opacity: 1 }, { opacity: 0 }];
      if (trans === 'slide') {
        const dx = (st.x < 640 ? -1 : 1) * 80;
        frames[show ? 0 : 1].translate = `${dx}px 0`;
        frames[show ? 1 : 0].translate = '0 0';
      }
      return this.fadeTo(st.el, frames, sec);
    }));
  }
  async charMove(key, x, y, sec, relative, easing) {
    const st = this.charState(key);
    const from = st.el.style.transform;
    if (relative) { st.x += x; st.y += y; } else { st.x = x; st.y = y; }
    this.charPlace(st);
    if (sec > 0 && !this.skip) await this.anim(st.el, [{ transform: from }, { transform: st.el.style.transform }], sec, { fill: 'none', easing: easing || 'linear' });
  }
  async charScale(key, s, sec, easing) {
    const st = this.charState(key);
    const from = st.el.style.transform;
    st.s = s; this.charPlace(st);
    if (sec > 0 && !this.skip) await this.anim(st.el, [{ transform: from }, { transform: st.el.style.transform }], sec, { fill: 'none', easing: easing || 'linear' });
  }
  charHop(key) {
    const st = this.charState(key);
    return this.anim(st.el.querySelector('.pt'), [{ translate: '0 0' }, { translate: '0 -40px' }, { translate: '0 0' }, { translate: '0 -25px' }, { translate: '0 0' }], 0.5, { fill: 'none' });
  }
  charFocus(key, mode) {
    const st = this.charState(key);
    st.focus = mode || 'auto';
    if (st.focus !== 'auto') st.el.classList.toggle('dim', st.focus === 'off');
  }
  autoFocus(speaker) {
    for (const st of Object.values(this.chars)) {
      if (st.focus !== 'auto') continue;
      st.el.classList.toggle('dim', !!speaker && st.key !== speaker && st.vis);
    }
  }

  // ---------------------------------------------------------------- text
  typeInto(el, text, onDone) {
    const u = units(text);
    el.innerHTML = u.map((x) => `<span class="u">${x}</span>`).join('');
    const spans = el.querySelectorAll('.u');
    let i = 0;
    return new Promise((res) => {
      let tm = null;
      const finish = () => { clearInterval(tm); spans.forEach((s) => s.classList.add('on')); this._typing = null; res(); };
      if (this.skip || this.settings.textSpeed <= 0) { finish(); return; }
      tm = setInterval(() => { if (i >= spans.length) return finish(); spans[i++].classList.add('on'); }, this.settings.textSpeed);
      this._typing = { finish };
    });
  }
  playVoice(key) {
    if (this.voice) { this.voice.pause(); }
    this.voice = null;
    const src = key && this.res(key);
    if (!src || this.skip) return;
    const v = new Audio(src);
    v.volume = this.settings.voice;
    v.play().catch(() => {});
    this.voice = v;
  }
  async talk(a, waitTap) {
    const [portrait, face, vis, , voice, name, text] = a;
    const isP = portrait && portrait.startsWith('novel_portrait');
    // a[2] blank: the speaker is brought on screen if not there yet. 'off' (19,527 lines with a portrait):
    // leave the portrait as it is — hidden stays hidden (an off-screen speaker), shown stays shown.
    // Checked against the original: リュー shouting with 'off' while zoomed in stays on screen, and the
    // speaker's focus (others dimmed) works the same as on a blank line. Hiding her was wrong.
    let on = false;
    if (isP) {
      this.charFace(portrait, face);
      const st = this.charState(portrait);
      if (vis !== 'off' && !st.vis) { this.fadeStop(st.el); st.vis = true; st.el.style.opacity = 1; }
      on = st.vis;
    }
    this.autoFocus(on ? portrait : null);
    if (this.descText.innerHTML) this.descText.innerHTML = '';
    this.msg.classList.remove('hidden');
    this.msg.classList.toggle('noname', !name);
    this.msgName.textContent = name || '';
    this.msg.classList.remove('ready');
    this.playVoice(voice);
    const entry = { name: name || '', text: text || '', voice: voice && this.res(voice) };
    this.log.push(entry);
    this.onLine(entry);
    await this.typeInto(this.msgText, text || '');
    if (waitTap) { this.msg.classList.add('ready'); await this.waitClick(); }
  }
  // Selection: [textA, lenA, textB, lenB, voices, name]. The next lenA commands are branch A, the lenB after
  // them branch B (checked: B's text lands at +lenA in 451/491 choices); only the picked branch plays.
  async selection(a) {
    const [ta, , tb, , voices, name] = a;
    const lenA = Math.max(0, Math.round(num(a[1]))), lenB = Math.max(0, Math.round(num(a[3])));
    const vs = (voices || '').split(/\s+/).filter(Boolean);
    this.msg.classList.add('hidden');
    this.choiceEl.innerHTML = '';
    this.choiceEl.classList.remove('hidden');
    let pick = 0;
    if (!this.skip) {
      pick = await new Promise((res) => {
        [ta, tb].forEach((t, i) => {
          if (!t) return;
          const b = document.createElement('button');
          b.innerHTML = rubyHTML(t);
          b.onclick = (e) => { e.stopPropagation(); res(i); };
          this.choiceEl.appendChild(b);
        });
      });
    }
    this.choiceEl.classList.add('hidden');
    const text = pick ? tb : ta;
    const voiceKey = vs[pick] ?? vs[0];
    const start = this.pc + 1 + (pick ? lenA : 0), cmds = this.novel.cmds;
    if (pick) this.pc += lenA;  // the loop's pc++ then lands on branch B
    else if (lenB) this.jumps.push({ at: this.pc + 1 + lenA, n: lenB });
    // about half the unvoiced branches open by repeating the choice; don't say it twice
    const first = cmds.slice(start, start + (pick ? lenB : lenA)).find((c) => c[0] === 11 || c[0] === 12 || c[0] === 45);
    const plain = (t) => String(t || '').replace(/\[r=[^\]]*\]|\[\/r\]|\s/g, '');
    if (first && plain(first[first.length - 1]) === plain(text)) return;
    return this.talk(['', '', '', 'middle', voiceKey, name, text], true);
  }
  async descShow(color, alpha, sec) {
    this.descBg.style.background = hex(color, '#000');
    const from = getComputedStyle(this.descBg).opacity;
    await this.anim(this.descBg, [{ opacity: from }, { opacity: alpha }], sec);
    this.descBg.getAnimations().forEach((x) => x.cancel());
    this.descBg.style.opacity = alpha;
    if (alpha === 0) this.descText.innerHTML = '';
  }
  // A full fade-out to black is a scene change: narration text and its dim overlay don't carry over.
  sceneReset() {
    // a full fade-out (19) ends every scenario effect: 4516 effects are never hidden explicitly and
    // are always followed by one (letter_box bars etc. are re-issued after each fade-in)
    for (const f of new Set(this.fx.values())) this.lwfDestroy(f);
    this.fx.clear();
    this.tintEl.getAnimations().forEach((x) => x.cancel()); this.tintEl.style.opacity = 0;
    // ...and clears the stage except the background: portraits still up (23k cases are never hidden or
    // re-shown afterwards) and middle/foreground images. Scripts rebuild the scene before fading in.
    for (const st of Object.values(this.chars)) { st.el.getAnimations().forEach((x) => x.cancel()); st.el.style.opacity = 0; st.vis = false; }
    for (const l of [this.L.mid, this.L.fg]) for (const e of [...l.children]) { e.getAnimations().forEach((x) => x.cancel()); e.remove(); e.style.opacity = 0; }
    this.descText.getAnimations().forEach((x) => x.cancel());
    this.descText.innerHTML = '';
    this.descBg.getAnimations().forEach((x) => x.cancel());
    this.descBg.style.opacity = 0;
    this.msg.classList.add('hidden');
  }
  async narrClear(sec) {
    if (!this.descText.innerHTML) return;
    await this.fadeTo(this.descText, [{ opacity: 1 }, { opacity: 0 }], sec, () => { this.descText.innerHTML = ''; this.descText.style.opacity = ''; });
  }
  async narrate(a) {
    const [color, , pos, , voice, size, text] = a;
    this.msg.classList.add('hidden');
    this.fadeStop(this.descText); this.descText.style.opacity = '';  // a 29 still fading the previous text
    this.descText.style.color = hex(color, '#fff');
    this.descText.style.fontSize = num(size, 30) + 'px';
    this.descText.dataset.pos = pos || 'middle';
    this.playVoice(voice);
    const entry = { name: '', text: text || '', voice: voice && this.res(voice) };
    this.log.push(entry);
    this.onLine(entry);
    await this.typeInto(this.descText, text || '');
    await this.waitClick();
  }
  async titleShow(title, sub) {
    this.titleEl.querySelector('.tc-title').textContent = title || '';
    this.titleEl.querySelector('.tc-sub').textContent = sub || '';
    this.titleEl.classList.remove('hidden');
    await this.anim(this.titleEl, [{ opacity: 0 }, { opacity: 1 }], 0.6);
    await Promise.race([this.wait(2.2), this.waitClick()]);
    await this.anim(this.titleEl, [{ opacity: 1 }, { opacity: 0 }], 0.6);
    this.titleEl.classList.add('hidden');
  }

  // ---------------------------------------------------------------- screen
  // layer as with 64: background = bg + middle images, middle = up to the characters, foreground, effect;
  // the narration, captions and the message box always stay above it
  async tint(color, alpha, sec, layer) {
    if (color) this.tintEl.style.background = color;
    if (layer) {
      const above = { background: this.L.mid, middle: this.L.chars, foreground: this.L.fg }[layer] || this.L.fx;
      if (this.tintEl.previousElementSibling !== above) above.after(this.tintEl);
    }
    const from = getComputedStyle(this.tintEl).opacity;
    await this.anim(this.tintEl, [{ opacity: from }, { opacity: alpha }], sec);
    this.tintEl.getAnimations().forEach((x) => x.cancel());
    this.tintEl.style.opacity = alpha;
  }
  async fade(color, alpha, sec) {
    if (color) this.fadeEl.style.background = color;
    const from = getComputedStyle(this.fadeEl).opacity;
    await this.anim(this.fadeEl, [{ opacity: from }, { opacity: alpha }], sec);
    this.fadeEl.getAnimations().forEach((x) => x.cancel());
    this.fadeEl.style.opacity = alpha;
  }
  async flash(color, tin, hold, tout, peak = 1) {
    const f = document.createElement('div');
    f.className = 'flash';
    f.style.background = color;
    this.stage.insertBefore(f, this.fadeEl);
    await this.anim(f, [{ opacity: 0 }, { opacity: peak }], tin);
    await this.wait(hold);
    await this.anim(f, [{ opacity: peak }, { opacity: 0 }], tout);
    f.remove();
  }
  quake(target, amp, ampY, sec) {
    if (sec === undefined) { sec = ampY; ampY = amp; }
    let el = this.stage;
    if (target && target.startsWith('character')) {
      const k = target.split('/')[1];
      el = (k && this.chars[k]) ? this.chars[k].el.querySelector('.pt') : this.L.chars;
    } else if (target && target.startsWith('image')) {
      const k = target.split('/')[1];
      el = (k && this.images[k]) ? this.images[k].el : this.L.bg;
    } else if (target === 'background') el = this.L.bg;
    const n = Math.max(2, Math.round(sec * 30));
    const frames = [];
    for (let i = 0; i < n; i++) { const k = 1 - i / n; frames.push({ translate: `${(Math.random() * 2 - 1) * amp * k}px ${(Math.random() * 2 - 1) * ampY * k}px` }); }
    frames.push({ translate: '0 0' });
    if (el === this.stage) { el = this.stage.querySelector('[data-l="bg"]').parentNode; }
    const layers = el === this.stage ? Object.values(this.L) : [el];
    return Promise.all(layers.map((l) => this.anim(l, frames, sec, { fill: 'none', easing: 'linear' })));
  }

  // post effects: color_multiplier via SVG feColorMatrix, blur via CSS
  peLayers() {
    const t = this.peTarget;
    if (this.peChars?.length) return this.peChars.map((k) => this.charState(k).el);  // 64 named portraits only
    if (t === 'background') return [this.L.bg, this.L.mid];
    if (t === 'middle') return [this.L.chars];
    if (t === 'background_middle') return [this.L.bg, this.L.mid, this.L.chars];
    if (t === 'background_middle_effect') return [this.L.bg, this.L.mid, this.L.chars, this.L.fx];
    if (t === 'middle_effect') return [this.L.chars, this.L.fx];
    if (t === 'all') return Object.values(this.L);
    return [];
  }
  setFilter(layer, kind, value) {
    layer._pe = layer._pe || {};
    if (value) layer._pe[kind] = value; else delete layer._pe[kind];
    layer.style.filter = Object.values(layer._pe).join(' ');
  }
  async peStart(a) {
    const [, sec, type, p1] = a;
    const layers = this.peLayers();
    if (type === 'blur') layers.forEach((l) => this.setFilter(l, 'blur', `blur(${num(p1, 4) / 2}px)`));
    if (type === 'sepia') layers.forEach((l) => this.setFilter(l, 'sepia', 'sepia(1)'));
    if (type === 'grayscale') layers.forEach((l) => this.setFilter(l, 'grayscale', 'grayscale(1)'));
    if (type === 'color_multiplier' || type === 'custom_color_correction') {
      const [r, g, b] = (p1 || '100:100:100').split(':').map((x) => num(x, 100) / 100);
      layers.forEach((l, i) => {
        const id = `cm-${l.dataset.l}`;
        let f = this.defs.querySelector('#' + id);
        if (!f) { f = document.createElementNS('http://www.w3.org/2000/svg', 'filter'); f.id = id; f.setAttribute('color-interpolation-filters', 'sRGB'); f.innerHTML = '<feColorMatrix type="matrix"/>'; this.defs.appendChild(f); }
        f.firstChild.setAttribute('values', `${r} 0 0 0 0  0 ${g} 0 0 0  0 0 ${b} 0 0  0 0 0 1 0`);
        this.setFilter(l, 'cm', `url(#${id})`);
      });
    }
    await this.wait(num(sec));
  }
  async peEnd(a) {
    const [, sec, type] = a;
    for (const l of Object.values(this.L)) {
      if (type === 'blur' || !type) this.setFilter(l, 'blur', null);
      if (type === 'color_multiplier' || type === 'custom_color_correction' || !type) this.setFilter(l, 'cm', null);
      if (type === 'sepia' || !type) this.setFilter(l, 'sepia', null);
      if (type === 'grayscale' || !type) this.setFilter(l, 'grayscale', null);
    }
    await this.wait(num(sec));
  }

  // animation text (credits, chapter captions)
  atextSet(a) {
    const [id, x, y, anchor, align] = a;
    let el = this.atext.querySelector(`[data-id="${id}"]`);
    if (!el) { el = document.createElement('div'); el.className = 'at'; el.dataset.id = id; this.atext.appendChild(el); }
    el._x = num(x); el._y = num(y);
    el.style.left = 640 + el._x + 'px';
    el.style[anchor === 'top' ? 'top' : 'bottom'] = el._y + 'px';
    el.style.transform = align === 'left' ? 'none' : align === 'right' ? 'translateX(-100%)' : '';
    el.style.textAlign = align === 'left' || align === 'right' ? align : '';
    el.style.opacity = 0;
  }
  async atextShow(a) {
    const [id, color, sec, size, , , text] = a;
    let el = this.atext.querySelector(`[data-id="${id}"]`);
    if (!el) { this.atextSet([id, 0, 300, 'bottom']); el = this.atext.querySelector(`[data-id="${id}"]`); }
    el.style.color = hex(color, '#fff');
    el.style.fontSize = num(size, 30) + 'px';
    el.innerHTML = rubyHTML(text || '');
    await this.anim(el, [{ opacity: 0 }, { opacity: 1 }], num(sec));
    el.getAnimations().forEach((x) => x.cancel()); el.style.opacity = 1;
  }
  async atextMove(a) {
    const [id, dx, dy, sec] = a;
    const el = this.atext.querySelector(`[data-id="${id}"]`);
    if (!el) return;
    const from = `${0}px ${0}px`;
    const to = `${num(dx)}px ${-num(dy)}px`;
    el._mv = this.anim(el, [{ translate: from }, { translate: to }], num(sec), { easing: 'linear' });
  }
  async atextRemove(id, sec) {
    const el = this.atext.querySelector(`[data-id="${id}"]`);
    if (!el) return;
    await this.anim(el, [{ opacity: 1 }, { opacity: 0 }], sec);
    el.remove();
  }

  // ---------------------------------------------------------------- LWF effects (lwf.js, Zlib license)
  lwfLoad(key) {
    const src = this.res(key);
    if (!src || typeof LWF === 'undefined') return Promise.resolve(null);
    const dir = src.slice(0, src.lastIndexOf('/') + 1), file = src.slice(dir.length);
    const canvas = document.createElement('canvas');
    canvas.width = W; canvas.height = H; canvas.className = 'lwfc';
    return new Promise((res) => {
      let done = false;
      const finish = (lwf) => {
        if (done) { if (lwf) lwfFree(src, lwf); return; }  // arrived after the timeout
        done = true; clearTimeout(timer); lwfLoaded(src);
        res(lwf ? { lwf, canvas, key, src, x: 640, y: 360, rot: 0 } : null);
      };
      const timer = setTimeout(() => { if (!done) { console.warn('lwf load timeout', key); done = true; lwfLoaded(src); res(null); } }, 20000);
      lwfLoading.set(src, (lwfLoading.get(src) || 0) + 1);
      try {
        LWF.useCanvasRenderer();
        LWF.ResourceCache.get().loadLWF({
          lwf: file, prefix: dir, stage: canvas, worker: false, useBackgroundColor: false,
          onload: finish,
        });
      } catch (e) { console.warn('lwf', key, e); finish(null); }
    });
  }
  lwfPlace(f) {
    // Every scenario/battle LWF is authored around its origin (object translates span both signs,
    // whatever the stage size), and the game screen is 1280x720: put the origin at (x, y), 1:1.
    f.lwf.property.clear();
    f.lwf.property.moveTo(f.x, H - f.y);
    if (f.rot) f.lwf.property.rotateTo(f.rot);
    const s = f.scale ?? 1;
    if (s !== 1 || f.flipX || f.flipY) f.lwf.property.scaleTo(s * (f.flipX ? -1 : 1), s * (f.flipY ? -1 : 1));
  }
  // LwfZOrder: below 0 the effect goes behind the characters (values like ±200 / ±50, as with 38)
  lwfZ(key, label, z) {
    const f = this.fxGet(key, label);
    if (!f) return;
    f.canvas.style.zIndex = String(Math.round(z) + 1000);
    const layer = z < 0 ? this.L.mid : this.L.fx;
    if (f.canvas.parentNode !== layer) layer.appendChild(f.canvas);
  }
  // LwfParent [lwf, inst, add, image|chara, target]: draw the effect with that image / character (right above it)
  lwfParent(key, label, kind, target) {
    const f = this.fxGet(key, label);
    if (!f) return;
    const host = kind === 'chara' ? this.chars[target]?.el : this.images[target]?.el;
    if (host && host.parentNode) host.parentNode.insertBefore(f.canvas, host.nextSibling);
  }
  lwfDestroy(f) { lwfFree(f.src, f.lwf); f.canvas.remove(); }
  fxId(key, label) { return key + '#' + (label || ''); }
  fxGet(key, label) {
    return this.fx.get(this.fxId(key, label)) || [...this.fx.values()].find((f) => f.key === key);
  }
  async lwfSet(key, label, x, y) {
    const id = this.fxId(key, label);
    const old = this.fx.get(id);
    if (old) { this.lwfDestroy(old); this.fx.delete(id); }
    const f = await this.lwfLoad(key);
    if (!f) return null;
    f.x = x; f.y = y; f.canvas.style.opacity = 0;
    this.lwfPlace(f);
    this.L.fx.appendChild(f.canvas);
    this.fx.set(id, f);
    return f;
  }
  async lwfShow(key, label, x, y, sec, create) {
    let f = this.fx.get(this.fxId(key, label));
    if (!f || create) f = await this.lwfSet(key, label, x ?? 640, y ?? 360);
    if (!f) return;
    await this.anim(f.canvas, [{ opacity: 0 }, { opacity: 1 }], sec);
    f.canvas.getAnimations().forEach((x) => x.cancel()); f.canvas.style.opacity = 1;
  }
  async lwfHide(key, label, sec) {
    const f = this.fxGet(key, label);
    if (!f) return;
    for (const [id, v] of this.fx) if (v === f) this.fx.delete(id);
    await this.anim(f.canvas, [{ opacity: getComputedStyle(f.canvas).opacity }, { opacity: 0 }], sec);
    this.lwfDestroy(f);
  }
  async effectHide(key, sec) {
    const fs = [...new Set([...this.fx.values()].filter((f) => f.key === key))];
    for (const [id, v] of this.fx) if (fs.includes(v)) this.fx.delete(id);
    await Promise.all(fs.map(async (f) => {
      await this.anim(f.canvas, [{ opacity: getComputedStyle(f.canvas).opacity }, { opacity: 0 }], sec);
      this.lwfDestroy(f);
    }));
  }
  async lwfOnce(key, x, y, rot = 0, fadeIn = 0) {
    const id = this.fxId(key, 'once' + Math.random());
    const f = await this.lwfLoad(key);
    if (!f) return;
    f.x = x; f.y = y; f.rot = rot; this.lwfPlace(f);
    // re-issuing an effect replaces earlier copies that have played out and are just holding their
    // last frame (letter_box is re-sent after every cut — 30x in one dagger barrage)
    for (const [i, v] of this.fx) if (v.key === key && !v.lwf.rootMovie?.playing) { this.fx.delete(i); this.lwfDestroy(v); }
    this.L.fx.appendChild(f.canvas);
    this.fx.set(id, f);
    if (fadeIn) this.anim(f.canvas, [{ opacity: 0 }, { opacity: 1 }], fadeIn);
    const total = (f.lwf.rootMovie && f.lwf.rootMovie.totalFrames) || 30;
    const sec = total / (f.lwf.frameRate || 30);
    const drop = () => { if (this.fx.get(id) === f) { this.fx.delete(id); this.lwfDestroy(f); } };
    if (key.startsWith('battle_effect')) setTimeout(drop, sec * 1000 + 100);
    else {
      // scenario effects stay until hidden (53 EffectHide), a fade-out, or — one-shots like dagger /
      // graywind / explosion that end on an empty frame — once they have played out
      f.key = key;
      setTimeout(() => { if (this.fx.get(id) === f && !f.lwf.rootMovie?.playing && lwfBlank(f.canvas)) drop(); }, sec * 1000 + 200);
    }
    await this.wait(sec);
  }
  lwfMove(a) {
    const [key, label, x, y, sec, mode, easing] = a;
    const f = this.fxGet(key, label);
    if (!f) return;
    const x1 = mode === 'relative' ? f.x + num(x) : num(x), y1 = mode === 'relative' ? f.y + num(y) : num(y);
    const ms = this.d(num(sec));
    if (!ms) { f.x = x1; f.y = y1; this.lwfPlace(f); return; }
    f.tw = { t0: performance.now(), ms, x0: f.x, y0: f.y, x1, y1, ease: easeFn(easing) };
  }

  // ---------------------------------------------------------------- audio
  ramp(audio, to, sec) {
    if (!audio) return Promise.resolve();
    to = Math.max(0, Math.min(1, to));
    const from = audio.volume, ms = this.d(sec);
    if (!ms) { audio.volume = to; return Promise.resolve(); }
    const t0 = performance.now();
    return new Promise((res) => {
      const step = (t) => { const k = Math.min(1, (t - t0) / ms); audio.volume = Math.max(0, Math.min(1, from + (to - from) * k)); if (k < 1) requestAnimationFrame(step); else res(); };
      requestAnimationFrame(step);
    });
  }
  bgmStart(key, fadeIn) {
    const src = this.res(key);
    if (!src) return;
    if (this.bgm && this.bgmKey === key && !this.bgm.paused) return;
    if (this.bgm) { const old = this.bgm; this.ramp(old, 0, 0.5).then(() => old.pause()); }
    const a = new Audio(src);
    a.loop = true;
    a.volume = fadeIn > 0 ? 0 : this.settings.bgm;
    a.play().catch(() => {});
    this.bgm = a; this.bgmKey = key; this.bgmLevel = 1;
    if (fadeIn > 0) this.ramp(a, this.settings.bgm, fadeIn);
  }
  async bgmStop(sec) {
    const a = this.bgm;
    this.bgm = null; this.bgmKey = null;
    if (!a) return;
    this.ramp(a, 0, sec).then(() => a.pause());
  }
  volume(target, v, sec) {
    if (target === 'bgm' && this.bgm) { this.bgmLevel = v; return this.ramp(this.bgm, this.settings.bgm * v, sec); }
    if (target && target.startsWith('se.')) {  // the SE started just before (512 uses)
      const live = this.ses.filter((x) => x.key === target);
      live.forEach((x) => { x.level = v; this.ramp(x.a, this.settings.se * v, sec); });
    }
  }
  // SEs play once; a SeStop (33) may cut one short with a fade, VolumeSet (37) may lower it
  se(key, delay) {
    const src = this.res(key);
    if (!src || this.skip) return;
    const a = new Audio(src);
    a.volume = this.settings.se;
    const x = { key, a, level: 1 };
    this.ses.push(x);
    a.onended = () => { this.ses = this.ses.filter((y) => y !== x); };
    x.timer = setTimeout(() => a.play().catch(() => {}), delay * 1000);
  }
  seStop(key, delay, fade) {
    for (const x of this.ses.filter((y) => y.key === key)) {
      this.ses = this.ses.filter((y) => y !== x);
      const stop = () => { clearTimeout(x.timer); if (fade > 0 && !this.skip) this.ramp(x.a, 0, fade).then(() => x.a.pause()); else x.a.pause(); };
      if (delay > 0 && !this.skip) setTimeout(stop, delay * 1000); else stop();
    }
  }

  async playMovie(key, skippable) {
    const src = this.res(key);
    if (!src || !src.endsWith('.mp4') || this.skip) return;
    const v = this.movie;
    v.src = src;
    v.volume = this.settings.bgm;
    v.classList.remove('hidden');
    if (this.bgm) this.bgm.pause();
    await new Promise((res) => {
      v.onended = res;
      v.onerror = res;
      this._clickWaiters.push(res);
      v.play().catch(res);
    });
    v.pause();
    v.classList.add('hidden');
    if (this.bgm) this.bgm.play().catch(() => {});
  }
}

export { rubyHTML };
