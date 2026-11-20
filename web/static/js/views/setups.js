import { api, guarded } from "../api.js";
import { Chart } from "../chart.js";
import { h } from "../dom.js";
import { emit, runs, store } from "../store.js";
import { fmt } from "../util.js";
import { head, needData, section, select } from "./_shared.js";

const METRICS = [["vel_max", "Vel. máx"], ["vel_mean", "Vel. média"], ["rpm_max", "RPM máx"], ["rpm_mean", "RPM médio"], ["acel_max", "Acel. máx"], ["dist_total", "Distância"], ["duration", "Duração"]];
const COLORS = ["#27f4d2", "#ff8000", "#e10600", "#3b82f6", "#ffd60a", "#52e252", "#ff87bc", "#b388ff"];

export default {
  id: "setups", title: "Setups", short: "Setups",
  async mount(el) {
    if (needData(el)) return;
    const keys = store.state.setup_keys;
    el.append(head("Comparar setups", "Os ajustes mudaram o resultado ou foi acaso? Teste de Welch com IC 95%"));
    if (!keys.length) {
      el.append(h("div", { class: "empty" }, h("h2", null, "Sem metadados de setup"), h("p", null, "Preencha o setup das runs (ex.: peso_cvt, mola) na tela Runs. Repita cada setup ao menos 2 vezes para ter significância."),
        h("button", { class: "btn primary", onClick: () => { location.hash = "#/runs"; } }, "Editar metadados")));
      return;
    }
    const sk = sessionStorage.getItem("mangue.setupkey");
    const key = keys.includes(sk) ? sk : keys[0];
    const metric = sessionStorage.getItem("mangue.setupmetric") || "vel_mean";
    const res = await guarded(() => api.get("/api/setups", { key, metric }));
    el.append(h("div", { class: "row wrap", style: { marginBottom: "12px" } },
      h("label", { class: "row muted" }, "Agrupar por", select(keys.map((k) => [k, k]), key, (v) => { sessionStorage.setItem("mangue.setupkey", v); emit("ref"); })),
      h("label", { class: "row muted" }, "Métrica", select(METRICS, metric, (v) => { sessionStorage.setItem("mangue.setupmetric", v); emit("ref"); }))));
    if (!res) return;
    const names = Object.keys(res.groups);
    if (!names.length) { el.append(h("p", { class: "muted" }, `Nenhuma run tem o campo “${key}”.`)); return; }
    const box = h("div"); el.append(box);
    const c = new Chart(box, { title: METRICS.find((m) => m[0] === metric)[1], unit: `por ${key}`, height: 330, categories: names });
    const layers = [];
    names.forEach((g, i) => {
      const vals = res.groups[g];
      layers.push({ type: "points", x: vals.map((_, j) => i + (j - (vals.length - 1) / 2) * 0.07), y: vals, color: COLORS[i % COLORS.length], size: 6 });
      layers.push({ type: "points", x: [i], y: [res.summary[g].mean], err: [res.summary[g].std], color: "#ffffff", size: 3 });
    });
    c.setLayers(layers);
    el.append(section("Resultados"));
    el.append(h("div", { class: "card" }, h("table", { class: "table" }, h("thead", null, h("tr", null, ["Grupo", "n", "Média", "Desvio"].map((x) => h("th", null, x)))),
      h("tbody", null, names.map((g) => h("tr", null, h("td", null, g), h("td", { class: "mono" }, res.summary[g].n), h("td", { class: "mono" }, fmt(res.summary[g].mean, 2)), h("td", { class: "mono" }, fmt(res.summary[g].std, 2))))))));
    el.append(section("Testes de significância"));
    for (const [g, t] of Object.entries(res.tests)) {
      el.append(h("div", { class: `finding ${t == null ? "info" : t.significant ? "good" : "warning"}` }, h("b", null, `${res.baseline} × ${g}`),
        h("span", null, t == null ? "Repetições insuficientes: precisa de n ≥ 2 em cada grupo." :
          `Δ = ${fmt(t.diff, 2)} · IC95% [${fmt(t.ci95[0], 2)}, ${fmt(t.ci95[1], 2)}] · p = ${t.p.toFixed(4)} · d de Cohen = ${fmt(t.cohens_d, 2)} → ${t.significant ? "diferença significativa" : "sem evidência de diferença"}`)));
    }
    return { destroy() { c.destroy(); } };
  },
};
