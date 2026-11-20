import { api, guarded } from "../api.js";
import { Chart, Sync } from "../chart.js";
import { h } from "../dom.js";
import { runs, store } from "../store.js";
import { fmt, fmtInt, fmtTime, ledState, nearestIndex } from "../util.js";
import { head, needData, select, seg } from "./_shared.js";

const N_LEDS = 15;

export default {
  id: "replay", title: "Replay", short: "Replay",
  async mount(el) {
    if (needData(el)) return;
    const all = runs();
    let rid = all.find((r) => r.id === store.refId)?.id ?? all[0].id;
    const data = await guarded(() => api.get("/api/series", { runs: rid, channels: "vel,rpm,acel,dist", x: "time", max_points: 8000 }));
    if (!data) return;
    const d = data.runs[rid];
    const run = all.find((r) => r.id === rid);
    const T = d.x[d.x.length - 1];
    const rpmMax = Math.max(...d.rpm, 1), accMax = Math.max(6, ...d.acel.map(Math.abs));
    let t = 0, playing = false, speed = 1, last = 0, raf = 0, alive = true;

    const speedEl = h("div", { class: "big-speed mono" }, "0");
    const leds = h("div", { class: "leds" }, Array.from({ length: N_LEDS }, () => h("div", { class: "led" })));
    const rpmEl = h("b", null, "0"), distEl = h("b", null, "0"), timeEl = h("b", null, "0:00.000"), phaseEl = h("b", null, "—");
    const gneg = h("i", { style: { right: "50%", background: "#e10600" } }), gpos = h("i", { style: { left: "50%", background: "#00d26a" } });
    const gbar = h("div", { class: "gbar" }, gneg, gpos, h("i", { class: "mid" }));
    const gTxt = h("span", { class: "mono muted" }, "0.00 g");
    const scrub = h("input", { type: "range", min: 0, max: T, step: 0.01, value: 0, onInput: (e) => { t = +e.target.value; frame(); } });
    const playBtn = h("button", { class: "btn primary", onClick: () => toggle() }, "▶ Play");

    const sync = new Sync();
    sync.setExtent(0, T); sync.view = [0, T];
    const traces = h("div");
    const charts = [["vel", "Velocidade", "km/h", 130], ["rpm", "RPM", "rpm", 120], ["acel", "Aceleração", "m/s²", 120]].map(([k, title, unit, hh]) => {
      const c = new Chart(traces, { title, unit, height: hh, sync, interactive: false, showCursor: true });
      c.setLayers([{ type: "line", id: rid, color: run.color, x: d.x, y: d[k], width: 1.8 }]);
      return c;
    });

    function frame() {
      const i = nearestIndex(d.x, t);
      const v = d.vel[i], r = d.rpm[i], a = d.acel[i];
      speedEl.textContent = fmtInt(v);
      const pct = r / rpmMax;
      [...leds.children].forEach((led, k) => { const s = ledState(k, N_LEDS, pct); led.className = `led ${s.lit ? "lit " + s.color : ""}`; });
      rpmEl.textContent = fmtInt(r);
      distEl.textContent = fmtInt(d.dist[i]);
      timeEl.textContent = fmtTime(t);
      const g = Math.max(-1, Math.min(1, a / accMax));
      gpos.style.width = g > 0 ? `${g * 50}%` : "0"; gneg.style.width = g < 0 ? `${-g * 50}%` : "0";
      gTxt.textContent = `${fmt(a / 9.81, 2)} g`;
      phaseEl.textContent = a > 1 ? "ACELERANDO" : a < -1 ? "FREANDO" : "ESTÁVEL";
      phaseEl.style.color = a > 1 ? "var(--green)" : a < -1 ? "var(--red)" : "var(--yellow)";
      scrub.value = t;
      sync.setCursor(t);
    }
    function loop(ts) {
      if (!alive) return;
      if (playing) {
        if (last) t += ((ts - last) / 1000) * speed;
        if (t >= T) { t = T; toggle(false); }
        frame();
      }
      last = ts;
      raf = requestAnimationFrame(loop);
    }
    function toggle(force) {
      playing = force ?? !playing;
      if (playing && t >= T) t = 0;
      playBtn.textContent = playing ? "❚❚ Pausa" : "▶ Play";
      last = 0;
    }

    el.append(head("Replay", "Painel de bordo reproduzindo a run (RPM em LEDs, como o volante da F1)",
      h("label", { class: "row muted" }, "Run", select(all.map((r) => [r.id, r.name.replace(/\.csv$/i, "")]), rid, (v) => { store.refId = v; import("../store.js").then((m) => m.emit("ref")); })),
      seg([["0.5", "0.5×"], ["1", "1×"], ["2", "2×"], ["4", "4×"]], "1", (v) => { speed = +v; })));
    el.append(h("div", { class: "dash" },
      h("div", { class: "dash-main", style: { borderTop: `3px solid ${run.color}` } },
        h("div", { class: "row" }, speedEl, h("div", { class: "big-unit" }, "KM/H")), leds,
        h("div", { class: "row muted mono" }, "RPM ", rpmEl),
        h("div", { style: { marginTop: "18px" } }, h("div", { class: "row", style: { marginBottom: "6px" } }, h("span", { class: "muted" }, "FREIO ◀"), h("span", { class: "spacer" }), gTxt, h("span", { class: "spacer" }), h("span", { class: "muted" }, "▶ ACELERA")), gbar),
        h("div", { class: "stat-line" }, h("div", null, h("span", null, "Tempo"), timeEl), h("div", null, h("span", null, "Distância (m)"), distEl), h("div", null, h("span", null, "Fase"), phaseEl))),
      h("div", null, traces)));
    el.append(h("div", { class: "row", style: { marginTop: "12px" } }, playBtn, scrub));
    frame();
    raf = requestAnimationFrame(loop);
    return { destroy() { alive = false; cancelAnimationFrame(raf); charts.forEach((c) => c.destroy()); } };
  },
};
