import { api, guarded } from "../api.js";
import { Chart, Sync } from "../chart.js";
import { h } from "../dom.js";
import { emit, runById, store, visibleRuns } from "../store.js";
import { fmt, fmtDelta, fmtInt, fmtTime } from "../util.js";
import { head, legend, needData, section, select, seg } from "./_shared.js";

const SECTOR_NAMES = { purple: "Melhor do setor (todas as runs)", green: "Mais rápida que a referência", yellow: "Mais lenta que a referência" };

export default {
  id: "compare", title: "Comparar", short: "Comparar",
  async mount(el) {
    const runs = visibleRuns();
    if (needData(el, 2, "Carregue pelo menos duas runs (e mantenha-as visíveis) para comparar tempo por distância, como na análise de voltas da F1.")) return;
    if (runs.length < 2) { el.append(h("div", { class: "empty" }, h("h2", null, "Mostre pelo menos 2 runs"), h("p", null, "Use o ● na barra superior."))); return; }
    const ref = runs.find((r) => r.id === store.refId) ? store.refId : runs[0].id;
    store.refId = ref;
    const nSectors = +(sessionStorage.getItem("mangue.sectors") || 20);
    const data = await guarded(() => api.get("/api/compare", { runs: runs.map((r) => r.id).join(","), ref, sectors: nSectors }));
    if (!data) return;
    const sync = new Sync();
    sync.setExtent(0, data.dist_total);
    sync.view = [0, data.dist_total];
    const charts = [];
    const refRun = runById(ref);

    el.append(head("Comparar", `Δ tempo × distância · referência ★ ${refRun.name.replace(/\.csv$/i, "")}`,
      h("label", { class: "row muted" }, "Referência", select(runs.map((r) => [r.id, r.name.replace(/\.csv$/i, "")]), ref, (v) => { store.refId = v; emit("ref"); })),
      seg([["10", "10 setores"], ["20", "20"], ["30", "30"]], String(nSectors), (v) => { sessionStorage.setItem("mangue.sectors", v); emit("ref"); })));

    // cards de tempo final (como o gap de uma volta)
    const byDelta = [...data.runs].sort((a, b) => a.final_delta - b.final_delta);
    el.append(h("div", { class: "kpis" }, byDelta.map((r, i) => {
      const run = runById(r.id);
      return h("div", { class: "kpi", style: { "--c": run.color } }, h("div", { class: "l" }, `${i + 1}º · ${run.name.replace(/\.csv$/i, "")}`),
        h("div", null, h("span", { class: "v" }, fmtTime(r.time_at_end)), h("span", { class: "u" }, r.id === ref ? "referência" : fmtDelta(r.final_delta) + " s")));
    })));

    el.append(section(`Mini-setores (${data.sectors} × ${fmt(data.dist_total / data.sectors, 0)} m)`));
    const sec = h("div", { class: "card sectors" });
    for (const r of data.runs) {
      const run = runById(r.id);
      sec.append(h("div", { class: "sector-row" }, h("div", { style: { fontWeight: 700, borderLeft: `4px solid ${run.color}`, paddingLeft: "8px" } }, run.name.replace(/\.csv$/i, "")),
        h("div", { class: "tiles" }, r.sector_colors.map((c, i) => h("div", { class: `tile ${c}`, title: `Setor ${i + 1} · ${fmt(r.sector_times[i], 3)} s · ${SECTOR_NAMES[c]}` }))),
        h("div", { class: "mono " + (r.final_delta > 0 ? "delta-pos" : r.final_delta < 0 ? "delta-neg" : "muted"), style: { textAlign: "right" } }, r.id === ref ? "REF" : fmtDelta(r.final_delta) + " s")));
    }
    sec.append(h("div", { class: "row wrap help", style: { marginTop: "6px" } }, ["purple", "green", "yellow"].map((c) => h("span", null, h("span", { class: `tile ${c}`, style: { display: "inline-block", width: "14px", height: "10px", marginRight: "6px", verticalAlign: "middle" } }), SECTOR_NAMES[c]))));
    el.append(sec);

    el.append(section("Traços sobre a distância"), legend(runs));
    const box = h("div", { style: { marginTop: "8px" } });
    el.append(box);
    const mk = (title, unit, h_, key, opts = {}) => {
      const c = new Chart(box, { title, unit, height: h_, sync, interactive: true, xFmt: (v) => fmtInt(v), ...opts });
      c.setLayers([...(opts.zero ? [{ type: "hline", value: 0, color: "#ffffff55", dash: [] }] : []),
        ...data.runs.map((r) => ({ type: "line", id: r.id, name: runById(r.id).name, color: runById(r.id).color, x: data.dist, y: r[key], width: r.id === ref ? 2.4 : 1.6, fill: opts.fill && r.id !== ref }))]);
      charts.push(c);
      return c;
    };
    mk("Δ tempo vs referência", "s (acima = mais lenta)", 230, "delta", { zero: true });
    mk("Velocidade", "km/h", 190, "speed");
    mk("RPM", "rpm", 160, "rpm", { xLabel: "distância (m)" });
    return { destroy() { charts.forEach((c) => c.destroy()); } };
  },
};
