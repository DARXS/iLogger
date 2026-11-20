import { api, guarded } from "../api.js";
import { Chart, Sync } from "../chart.js";
import { h, toast } from "../dom.js";
import { emit, store, visibleRuns } from "../store.js";
import { debounce, fmt, fmtInt } from "../util.js";
import { PHASE_COLORS, head, legend, needData, seg } from "./_shared.js";

const CHANNELS = {
  vel: { label: "Velocidade", unit: "km/h", raw: "vel_raw", d: 1, h: 240 },
  rpm: { label: "RPM", unit: "rpm", raw: "rpm_raw", d: 0, h: 210 },
  acel: { label: "Aceleração", unit: "m/s²", d: 2, h: 180 },
};
const LS = "mangue.telemetry";
const saved = () => { try { return JSON.parse(localStorage.getItem(LS) || "{}"); } catch { return {}; } };
const persist = (o) => localStorage.setItem(LS, JSON.stringify(o));

export default {
  id: "telemetry", title: "Telemetria", short: "Telem.",
  async mount(el) {
    if (needData(el)) return;
    const runs = visibleRuns();
    if (!runs.length) { el.append(h("div", { class: "empty" }, h("h2", null, "Todas as runs estão ocultas"), h("p", null, "Use o ● na barra superior para mostrá-las."))); return; }
    const prefs = { channels: ["vel", "rpm", "acel"], raw: false, math: [], ...saved() };
    const xAxis = store.xAxis;
    const sync = new Sync();
    const charts = {};            // id → {chart, kind}
    const body = h("div");
    const readTable = h("div");
    let cleanup = false;

    const xUnit = xAxis === "time" ? "s" : "m";
    const idList = runs.map((r) => r.id);

    const rebuild = async () => {
      body.replaceChildren();
      Object.values(charts).forEach((c) => c.chart.destroy?.());
      for (const k of Object.keys(charts)) delete charts[k];
      const chans = [...new Set([...prefs.channels, ...(prefs.raw ? ["vel_raw", "rpm_raw"] : [])])];
      const data = await guarded(() => api.get("/api/series", { runs: idList.join(","), channels: chans.join(","), x: xAxis, max_points: 1800 }));
      if (!data || cleanup) return;
      const first = Object.values(data.runs)[0];
      sync.extent = null; sync.view = null;
      sync.setExtent(Math.min(...Object.values(data.runs).map((r) => r.x[0])), Math.max(...Object.values(data.runs).map((r) => r.x[r.x.length - 1])));
      sync.view = [...sync.extent];
      let n = 0;
      for (const ch of prefs.channels) {
        const info = CHANNELS[ch];
        const c = new Chart(body, { title: info.label, unit: info.unit, height: info.h, sync, interactive: true, xFmt: (v) => (xAxis === "dist" ? fmtInt(v) : fmt(v, v % 1 ? 1 : 0)), xLabel: n === prefs.channels.length - 1 && !prefs.math.length ? `${xAxis === "time" ? "tempo" : "distância"} (${xUnit})` : "" });
        charts[ch] = { chart: c, kind: ch };
        n++;
      }
      setLayers(data);
      // faixa de fases (só no eixo do tempo): referência
      if (xAxis === "time") {
        const refId = idList.includes(store.refId) ? store.refId : idList[0];
        const ph = await guarded(() => api.get(`/api/phases/${refId}`));
        if (ph && !cleanup) {
          const strip = new Chart(body, { title: "Fases de condução (referência)", height: 62, sync, interactive: true, yMin: 0, yMax: 1, yFmt: () => "", margin: { l: 58, r: 14, t: 6, b: 6 } });
          strip.setLayers(ph.map((p) => ({ type: "xband", from: p.t0, to: p.t1, color: PHASE_COLORS[p.phase], alpha: 0.85 })));
          charts._phases = { chart: strip, kind: "phases" };
        }
      }
      for (const m of prefs.math) await addMath(m);
      sync.schedule();
    };

    const setLayers = (data) => {
      for (const { chart, kind } of Object.values(charts)) {
        if (!CHANNELS[kind]) continue;
        const layers = [];
        for (const r of runs) {
          const d = data.runs[r.id];
          if (!d) continue;
          layers.push({ type: "line", id: r.id, name: r.name, color: r.color, x: d.x, y: d[kind], width: store.refId === r.id ? 2.2 : 1.6 });
          if (prefs.raw && CHANNELS[kind].raw) layers.push({ type: "line", id: r.id + "_raw", name: r.name + " (bruto)", color: r.color, x: d.x, y: d[CHANNELS[kind].raw], width: 1, alpha: 0.28 });
        }
        chart.setLayers(layers);
      }
    };

    async function addMath(m) {
      const res = await guarded(() => api.post("/api/math", { runs: idList, expression: m.expr, x_axis: xAxis }));
      if (!res) { prefs.math = prefs.math.filter((x) => x !== m); persist(prefs); return; }
      const c = new Chart(body, { title: m.name, unit: "f(x)", height: 150, sync, interactive: true });
      c.setLayers(runs.filter((r) => res.runs[r.id]).map((r) => ({ type: "line", id: r.id, name: r.name, color: r.color, x: res.runs[r.id].x, y: res.runs[r.id].y })));
      charts["math:" + m.name] = { chart: c, kind: "math" };
    }

    // zoom → rebusca resolução da janela
    const refetch = debounce(async () => {
      if (!sync.view || cleanup) return;
      const [x0, x1] = sync.view;
      const chans = [...new Set([...prefs.channels, ...(prefs.raw ? ["vel_raw", "rpm_raw"] : [])])];
      const data = await guarded(() => api.get("/api/series", { runs: idList.join(","), channels: chans.join(","), x: xAxis, x0, x1, max_points: 1800 }));
      if (data && !cleanup) { setLayers(data); sync.schedule(); }
    }, 160);
    sync.on("view", refetch);

    // leituras no cursor
    const renderReadouts = (x) => {
      const rows = runs.map((r) => {
        const cells = prefs.channels.map((ch) => {
          const c = charts[ch]?.chart;
          const v = x == null || !c ? null : c.valuesAt(x).find((q) => q.id === r.id)?.value;
          return h("div", null, h("span", { class: "muted", style: { fontSize: "10px" } }, CHANNELS[ch].label.slice(0, 4).toUpperCase()), h("div", { class: "val" }, v == null ? "—" : fmt(v, CHANNELS[ch].d)));
        });
        return h("div", { class: "readout-row", style: { "--c": r.color, gridTemplateColumns: "10px 1fr" } }, h("i"), h("div", null, h("div", { style: { fontWeight: 700, marginBottom: "2px" } }, r.name.replace(/\.csv$/i, "")), h("div", { style: { display: "grid", gridTemplateColumns: `repeat(${cells.length},1fr)`, gap: "6px" } }, cells)));
      });
      readTable.replaceChildren(h("div", { class: "mono", style: { fontSize: "13px", marginBottom: "6px" } }, x == null ? "passe o mouse no gráfico" : `${xAxis === "time" ? "t" : "d"} = ${fmt(x, xAxis === "time" ? 2 : 0)} ${xUnit}`), ...rows);
    };
    sync.on("cursor", renderReadouts);
    renderReadouts(null);

    // ── cabeçalho / controles ────────────────────────────────────────────────
    const chBtns = Object.entries(CHANNELS).map(([k, v]) => h("button", { class: "chip" + (prefs.channels.includes(k) ? " on" : ""), onClick: (e) => {
      prefs.channels = prefs.channels.includes(k) ? prefs.channels.filter((c) => c !== k) : [...prefs.channels, k].sort((a, b) => Object.keys(CHANNELS).indexOf(a) - Object.keys(CHANNELS).indexOf(b));
      if (!prefs.channels.length) prefs.channels = [k];
      persist(prefs); e.target.classList.toggle("on"); rebuild();
    } }, v.label));
    const rawBtn = h("button", { class: "chip" + (prefs.raw ? " on" : ""), title: "Mostra o sinal bruto (sem filtro) em transparência", onClick: (e) => { prefs.raw = !prefs.raw; persist(prefs); e.target.classList.toggle("on"); rebuild(); } }, "Bruto");
    const exprIn = h("input", { type: "text", placeholder: "ex.: rpm / (vel + 1)", style: { width: "220px" } });
    const nameIn = h("input", { type: "text", placeholder: "nome", style: { width: "110px" } });
    const mathChips = () => prefs.math.map((m) => h("button", { class: "chip on", title: m.expr + " (clique para remover)", onClick: () => { prefs.math = prefs.math.filter((x) => x !== m); persist(prefs); rebuild(); render(); } }, "ƒ " + m.name));
    const mathBox = h("div", { class: "row wrap" });
    const render = () => mathBox.replaceChildren(...mathChips());
    render();
    el.append(head("Telemetria", "Cursor e zoom sincronizados · roda para zoom · arraste para mover · duplo clique reseta",
      seg([["time", "Tempo"], ["dist", "Distância"]], xAxis, (v) => { store.xAxis = v; emit("ref"); }),
      h("button", { class: "btn small", onClick: () => sync.reset() }, "↺ Resetar zoom")));
    el.append(h("div", { class: "row wrap", style: { marginBottom: "10px" } }, ...chBtns, rawBtn, h("span", { class: "muted" }, "│"),
      exprIn, nameIn, h("button", { class: "btn small", onClick: async () => {
        const expr = exprIn.value.trim(); if (!expr) return;
        const m = { expr, name: nameIn.value.trim() || "ƒ" + (prefs.math.length + 1) };
        prefs.math.push(m); persist(prefs); render(); exprIn.value = nameIn.value = "";
        await rebuild();
      } }, "＋ Canal matemático"), mathBox));
    el.append(h("div", { class: "help", style: { marginBottom: "8px" } }, "Variáveis: ", h("code", null, "vel rpm acel dist tempo vel_raw rpm_raw"), " · funções: ", h("code", null, "sqrt abs log exp clip diff cumsum grad where mean …")));
    el.append(h("div", { class: "grid g-side" }, h("div", null, legend(runs), h("div", { style: { height: "8px" } }), body), h("div", { class: "card readouts" }, h("div", { class: "section-title", style: { marginTop: 0 } }, "Leituras no cursor"), readTable)));
    await rebuild();
    return { destroy() { cleanup = true; Object.values(charts).forEach((c) => c.chart.destroy?.()); } };
  },
};
