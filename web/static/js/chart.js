// Motor de gráficos em canvas: linhas, dispersão, bandas, barras, pontos com barra de erro,
// cursor/zoom/pan sincronizados entre gráficos (estilo ferramentas de telemetria de F1).
import { bisect, clamp, decimals, nearestIndex, niceTicks } from "./util.js";
import { h } from "./dom.js";

const css = (name, fallback) => getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;

/** Estado compartilhado entre gráficos: cursor (x) e janela visível (view). */
export class Sync {
  constructor() {
    this.cursor = null;
    this.view = null;
    this.extent = null;
    this.charts = new Set();
    this._raf = 0;
    this._l = { view: [], cursor: [] };
  }
  add(c) { this.charts.add(c); }
  remove(c) { this.charts.delete(c); }
  on(evt, fn) { this._l[evt].push(fn); }
  setExtent(e0, e1) {
    this.extent = [e0, e1];
    if (!this.view || this.view[0] < e0 - 1e-9 && this.view[1] < e0 || this.view[0] > e1) this.view = [e0, e1];
  }
  setCursor(x) {
    this.cursor = x;
    this.schedule();
    this._l.cursor.forEach((f) => f(x));
  }
  setView(x0, x1, user = false) {
    if (!this.extent) return;
    const [e0, e1] = this.extent;
    const span = Math.max(1e-9, Math.min(x1 - x0, e1 - e0));
    x0 = clamp(x0, e0, e1 - span);
    this.view = [x0, x0 + span];
    this.schedule();
    if (user) this._l.view.forEach((f) => f(this.view));
  }
  reset() { if (this.extent) this.setView(this.extent[0], this.extent[1], true); }
  schedule() {
    if (this._raf) return;
    this._raf = requestAnimationFrame(() => { this._raf = 0; for (const c of this.charts) c.draw(); });
  }
}

export class Chart {
  /**
   * opts: {title, unit, height, sync, interactive, yMin, yMax, xLabel, categories, xFmt, yFmt,
   *        margin:{l,r,t,b}, legend:true}
   */
  constructor(parent, opts = {}) {
    this.o = { height: 170, interactive: false, margin: { l: 58, r: 14, t: 12, b: 24 }, ...opts };
    this.layers = [];
    this.canvas = h("canvas");
    this.titleEl = h("span", { class: "chart-title" }, this.o.title ?? "");
    this.unitEl = h("span", { class: "chart-unit" }, this.o.unit ?? "");
    this.readout = h("span", { class: "chart-readout" });
    this.head = h("div", { class: "chart-head" }, this.titleEl, this.unitEl, this.readout);
    this.el = h("div", { class: "chart", style: { height: this.o.height + "px" } }, this.o.title ? this.head : null, h("div", { class: "chart-body" }, this.canvas));
    this.body = this.el.querySelector(".chart-body");
    parent.append(this.el);
    this.ctx = this.canvas.getContext("2d");
    this.sync = this.o.sync || null;
    this.sync?.add(this);
    this._drag = null;
    this._ro = new ResizeObserver(() => this.draw());
    this._ro.observe(this.body);
    if (this.o.interactive && this.sync) this._bind();
    this.draw();
  }

  destroy() { this._ro.disconnect(); this.sync?.remove(this); this.el.remove(); }
  setLayers(layers) { this.layers = layers; this.draw(); }

  // ── escalas ──────────────────────────────────────────────────────────────
  _xDomain() {
    if (this.sync?.view) return this.sync.view;
    if (this.o.categories) return [-0.6, this.o.categories.length - 0.4];
    let lo = Infinity, hi = -Infinity;
    for (const l of this.layers) {
      if (!l.x) continue;
      for (const x of l.x) { if (x < lo) lo = x; if (x > hi) hi = x; }
    }
    if (!isFinite(lo)) return [0, 1];
    if (lo === hi) return [lo - 1, hi + 1];
    const pad = (hi - lo) * 0.02;
    return [lo - pad, hi + pad];
  }

  _yDomain(x0, x1) {
    if (this.o.yMin !== undefined && this.o.yMax !== undefined) return [this.o.yMin, this.o.yMax];
    let lo = Infinity, hi = -Infinity;
    const take = (v) => { if (v < lo) lo = v; if (v > hi) hi = v; };
    for (const l of this.layers) {
      if (l.type === "hline") { take(l.value); continue; }
      if (!l.x) continue;
      const unsorted = l.type === "scatter";   // dispersão não é ordenada em x
      const a = unsorted ? 0 : Math.max(0, bisect(l.x, x0) - 1);
      const b = unsorted ? l.x.length : Math.min(l.x.length, bisect(l.x, x1) + 1);
      for (let i = a; i < b; i++) {
        if (l.type === "band") { take(l.y0[i]); take(l.y1[i]); }
        else if (l.type === "points") { take(l.y[i] - (l.err?.[i] ?? 0)); take(l.y[i] + (l.err?.[i] ?? 0)); }
        else if (l.type === "bars") { take(l.y[i]); take(0); }
        else if (l.y[i] !== null && !Number.isNaN(l.y[i])) take(l.y[i]);
      }
    }
    if (this.o.yMin !== undefined) lo = this.o.yMin;
    if (this.o.yMax !== undefined) hi = this.o.yMax;
    if (!isFinite(lo)) return [0, 1];
    if (hi - lo < 1e-9) { lo -= 1; hi += 1; }
    const pad = (hi - lo) * 0.07;
    return [this.o.yMin !== undefined ? lo : lo - pad, this.o.yMax !== undefined ? hi : hi + pad];
  }

  // ── desenho ──────────────────────────────────────────────────────────────
  draw() {
    const w = this.body.clientWidth, hh = this.body.clientHeight;
    if (w < 10 || hh < 10) return;
    const dpr = window.devicePixelRatio || 1;
    if (this.canvas.width !== Math.round(w * dpr) || this.canvas.height !== Math.round(hh * dpr)) {
      this.canvas.width = Math.round(w * dpr);
      this.canvas.height = Math.round(hh * dpr);
      this.canvas.style.width = w + "px";
      this.canvas.style.height = hh + "px";
    }
    const ctx = this.ctx;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, hh);
    const m = this.o.margin;
    const pw = w - m.l - m.r, ph = hh - m.t - m.b;
    this.plot = { l: m.l, t: m.t, w: pw, h: ph };
    const [x0, x1] = this._xDomain();
    const [y0, y1] = this._yDomain(x0, x1);
    this.dom = { x0, x1, y0, y1 };
    const X = (x) => m.l + ((x - x0) / (x1 - x0)) * pw;
    const Y = (y) => m.t + ph - ((y - y0) / (y1 - y0)) * ph;
    this.X = X; this.Y = Y;
    const grid = css("--grid", "#23232b"), axis = css("--axis", "#8a8a98");
    ctx.font = "10.5px ui-monospace, SFMono-Regular, Consolas, monospace";
    ctx.lineWidth = 1;

    // grade + eixos
    const yt = niceTicks(y0, y1, Math.max(3, Math.floor(ph / 30)));
    const ydec = yt.length > 1 ? decimals(yt[1] - yt[0]) : 0;
    ctx.textAlign = "right"; ctx.textBaseline = "middle";
    for (const v of yt) {
      const py = Math.round(Y(v)) + 0.5;
      ctx.strokeStyle = grid; ctx.beginPath(); ctx.moveTo(m.l, py); ctx.lineTo(m.l + pw, py); ctx.stroke();
      ctx.fillStyle = axis;
      ctx.fillText(this.o.yFmt ? this.o.yFmt(v) : v.toFixed(ydec), m.l - 6, py);
    }
    ctx.textAlign = "center"; ctx.textBaseline = "top";
    const xt = this.o.categories ? this.o.categories.map((_, i) => i) : niceTicks(x0, x1, Math.max(3, Math.floor(pw / 90)));
    const xdec = xt.length > 1 ? decimals(xt[1] - xt[0]) : 0;
    for (const v of xt) {
      if (v < x0 - 1e-9 || v > x1 + 1e-9) continue;
      const px = Math.round(X(v)) + 0.5;
      ctx.strokeStyle = grid; ctx.beginPath(); ctx.moveTo(px, m.t); ctx.lineTo(px, m.t + ph); ctx.stroke();
      ctx.fillStyle = axis;
      const label = this.o.categories ? this.o.categories[v] : (this.o.xFmt ? this.o.xFmt(v) : v.toFixed(xdec));
      ctx.fillText(label, px, m.t + ph + 6);
    }
    ctx.strokeStyle = css("--axis-line", "#3a3a46");
    ctx.beginPath(); ctx.moveTo(m.l + 0.5, m.t); ctx.lineTo(m.l + 0.5, m.t + ph); ctx.lineTo(m.l + pw, m.t + ph + 0.5); ctx.stroke();

    // camadas (recortadas à área de plotagem)
    ctx.save();
    ctx.beginPath(); ctx.rect(m.l, m.t, pw, ph); ctx.clip();
    for (const l of this.layers) this._layer(ctx, l, X, Y, x0, x1);
    ctx.restore();

    if (this.o.xLabel) {
      ctx.fillStyle = axis; ctx.textAlign = "right"; ctx.textBaseline = "bottom";
      ctx.fillText(this.o.xLabel, w - 4, hh - 1);
    }
    this._cursor(ctx);
  }

  _layer(ctx, l, X, Y, x0, x1) {
    const color = l.color || "#fff";
    ctx.globalAlpha = l.alpha ?? 1;
    if (l.type === "line") {
      const a = Math.max(0, bisect(l.x, x0) - 1), b = Math.min(l.x.length, bisect(l.x, x1) + 1);
      ctx.strokeStyle = color; ctx.lineWidth = l.width ?? 1.6; ctx.lineJoin = "round";
      ctx.setLineDash(l.dash || []);
      ctx.beginPath();
      let pen = false;
      for (let i = a; i < b; i++) {
        const y = l.y[i];
        if (y === null || Number.isNaN(y)) { pen = false; continue; }
        const px = X(l.x[i]), py = Y(y);
        if (pen) ctx.lineTo(px, py); else { ctx.moveTo(px, py); pen = true; }
      }
      ctx.stroke(); ctx.setLineDash([]);
      if (l.fill && b > a) {
        ctx.lineTo(X(l.x[b - 1]), Y(Math.max(this.dom.y0, 0))); ctx.lineTo(X(l.x[a]), Y(Math.max(this.dom.y0, 0))); ctx.closePath();
        ctx.globalAlpha = (l.alpha ?? 1) * 0.12; ctx.fillStyle = color; ctx.fill();
      }
    } else if (l.type === "scatter") {
      ctx.fillStyle = color;
      const r = l.size ?? 1.6;
      for (let i = 0; i < l.x.length; i++) {
        if (l.x[i] < x0 || l.x[i] > x1) continue;
        ctx.fillRect(X(l.x[i]) - r / 2, Y(l.y[i]) - r / 2, r, r);
      }
    } else if (l.type === "band") {
      ctx.fillStyle = color; ctx.beginPath();
      for (let i = 0; i < l.x.length; i++) { const px = X(l.x[i]), py = Y(l.y1[i]); i ? ctx.lineTo(px, py) : ctx.moveTo(px, py); }
      for (let i = l.x.length - 1; i >= 0; i--) ctx.lineTo(X(l.x[i]), Y(l.y0[i]));
      ctx.closePath(); ctx.fill();
    } else if (l.type === "bars") {
      const bw = Math.abs(X(l.x[1] ?? l.x[0] + 1) - X(l.x[0])) * (l.fillRatio ?? 0.86) || 8;
      for (let i = 0; i < l.x.length; i++) {
        const c = l.colors ? l.colors[i] : color;
        ctx.fillStyle = c;
        const top = Y(l.y[i]), base = Y(0);
        ctx.fillRect(X(l.x[i]) - bw / 2, Math.min(top, base), bw, Math.abs(base - top));
      }
    } else if (l.type === "points") {
      for (let i = 0; i < l.x.length; i++) {
        const px = X(l.x[i]), py = Y(l.y[i]);
        if (l.err) {
          ctx.strokeStyle = "#e8e8ee"; ctx.lineWidth = 2;
          ctx.beginPath(); ctx.moveTo(px, Y(l.y[i] - l.err[i])); ctx.lineTo(px, Y(l.y[i] + l.err[i]));
          ctx.moveTo(px - 8, Y(l.y[i] - l.err[i])); ctx.lineTo(px + 8, Y(l.y[i] - l.err[i]));
          ctx.moveTo(px - 8, Y(l.y[i] + l.err[i])); ctx.lineTo(px + 8, Y(l.y[i] + l.err[i])); ctx.stroke();
        }
        ctx.fillStyle = l.colors ? l.colors[i] : color;
        ctx.beginPath(); ctx.arc(px, py, l.size ?? 5, 0, 7); ctx.fill();
      }
    } else if (l.type === "hline") {
      ctx.strokeStyle = color; ctx.lineWidth = l.width ?? 1; ctx.setLineDash(l.dash || [4, 4]);
      const py = Math.round(Y(l.value)) + 0.5;
      ctx.beginPath(); ctx.moveTo(this.plot.l, py); ctx.lineTo(this.plot.l + this.plot.w, py); ctx.stroke(); ctx.setLineDash([]);
    } else if (l.type === "vline") {
      ctx.strokeStyle = color; ctx.lineWidth = l.width ?? 1; ctx.setLineDash(l.dash || [4, 4]);
      const px = Math.round(X(l.value)) + 0.5;
      ctx.beginPath(); ctx.moveTo(px, this.plot.t); ctx.lineTo(px, this.plot.t + this.plot.h); ctx.stroke(); ctx.setLineDash([]);
    } else if (l.type === "xband") {   // faixa vertical (ex.: faixa de potência)
      ctx.fillStyle = color;
      ctx.fillRect(X(l.from), this.plot.t, X(l.to) - X(l.from), this.plot.h);
    }
    ctx.globalAlpha = 1;
  }

  _cursor(ctx) {
    const cx = this.sync?.cursor;
    if (cx === null || cx === undefined || !(this.o.showCursor ?? this.o.interactive)) return;
    const { x0, x1 } = this.dom;
    if (cx < x0 || cx > x1) return;
    const px = Math.round(this.X(cx)) + 0.5;
    ctx.strokeStyle = css("--cursor", "#ffffff99"); ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(px, this.plot.t); ctx.lineTo(px, this.plot.t + this.plot.h); ctx.stroke();
    for (const l of this.layers) {
      if (l.type !== "line" || !l.x.length) continue;
      const i = nearestIndex(l.x, cx);
      const y = l.y[i];
      if (y === null || Number.isNaN(y)) continue;
      ctx.fillStyle = l.color; ctx.strokeStyle = "#0b0b0e"; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(this.X(l.x[i]), this.Y(y), 3.6, 0, 7); ctx.fill(); ctx.stroke();
    }
  }

  /** Valores de cada camada de linha no x dado (para painéis de leitura). */
  valuesAt(x) {
    return this.layers.filter((l) => l.type === "line" && l.x.length).map((l) => {
      const i = nearestIndex(l.x, x);
      return { id: l.id, color: l.color, name: l.name, value: l.y[i], x: l.x[i] };
    });
  }

  // ── interação ────────────────────────────────────────────────────────────
  _px(e) { const r = this.canvas.getBoundingClientRect(); return e.clientX - r.left; }
  _xAt(px) { const { x0, x1 } = this.dom; return x0 + ((px - this.plot.l) / this.plot.w) * (x1 - x0); }

  _bind() {
    const c = this.canvas;
    c.style.touchAction = "none";
    c.addEventListener("pointermove", (e) => {
      const px = this._px(e);
      if (this._drag) {
        const dx = (px - this._drag.px) / this.plot.w * (this._drag.v1 - this._drag.v0);
        this.sync.setView(this._drag.v0 - dx, this._drag.v1 - dx, false);
        return;
      }
      if (px >= this.plot.l && px <= this.plot.l + this.plot.w) this.sync.setCursor(this._xAt(px));
    });
    c.addEventListener("pointerleave", () => { if (!this._drag) this.sync.setCursor(null); });
    c.addEventListener("pointerdown", (e) => {
      if (e.button !== 0) return;
      c.setPointerCapture(e.pointerId);
      this._drag = { px: this._px(e), v0: this.dom.x0, v1: this.dom.x1 };
      c.style.cursor = "grabbing";
    });
    const end = () => {
      if (this._drag) { this._drag = null; c.style.cursor = ""; this.sync._l.view.forEach((f) => f(this.sync.view)); }
    };
    c.addEventListener("pointerup", end);
    c.addEventListener("pointercancel", end);
    c.addEventListener("wheel", (e) => {
      e.preventDefault();
      const px = this._px(e), xc = this._xAt(px);
      const k = e.deltaY < 0 ? 0.8 : 1.25;
      const { x0, x1 } = this.dom;
      this.sync.setView(xc - (xc - x0) * k, xc + (x1 - xc) * k, true);
    }, { passive: false });
    c.addEventListener("dblclick", () => this.sync.reset());
  }
}
