import { api, guarded } from "../api.js";
import { Chart } from "../chart.js";
import { h } from "../dom.js";
import { runs, store } from "../store.js";
import { fmt, fmtInt } from "../util.js";
import { emit } from "../store.js";
import { head, kpi, needData, section, select } from "./_shared.js";

export default {
  id: "engine", title: "Motor / CVT", short: "Motor",
  async mount(el) {
    if (needData(el)) return;
    const all = runs();
    const rid = all.find((r) => r.id === store.refId)?.id ?? all[0].id;
    const run = all.find((r) => r.id === rid);
    const d = await guarded(() => api.get(`/api/engine/${rid}`, { bins: 36 }));
    if (!d) return;
    const charts = [];
    el.append(head("Motor / CVT", "Como o CVT mantém o motor na rotação certa",
      h("label", { class: "row muted" }, "Run", select(all.map((r) => [r.id, r.name.replace(/\.csv$/i, "")]), rid, (v) => { store.refId = v; emit("ref"); }))));

    const c = d.cvt;
    el.append(h("div", { class: "kpis" },
      kpi("RPM de saída", c?.launch_rpm ? fmtInt(c.launch_rpm) : "—", "rpm", run.color),
      kpi("RPM sustentado", c?.hold_rpm ? fmtInt(c.hold_rpm) : "—", "rpm", "#ff8000"),
      kpi("Estabilidade (CV)", c?.hold_cv_pct != null ? fmt(c.hold_cv_pct) : "—", "%", c?.hold_cv_pct > 8 ? "#ffd60a" : "#00d26a"),
      kpi("Faixa de potência", d.power_band?.pct_total != null ? fmt(d.power_band.pct_total, 0) : "—", d.power_band ? `% (${d.power_band.band[0]}–${d.power_band.band[1]})` : "configure no perfil", "#27f4d2")));

    el.append(section("CVT — RPM × velocidade"));
    const box1 = h("div"); el.append(box1);
    const cv = new Chart(box1, { title: "RPM por velocidade", unit: "mediana · P10–P90", height: 320, xLabel: "km/h" });
    const layers = [{ type: "scatter", x: d.scatter.vel, y: d.scatter.rpm, color: run.color, alpha: 0.35, size: 2.2 }];
    if (c) {
      layers.push({ type: "band", x: c.speed, y0: c.p10, y1: c.p90, color: "#00d26a", alpha: 0.2 });
      layers.push({ type: "line", x: c.speed, y: c.median, color: "#ff8000", width: 3 });
      if (c.hold_rpm) layers.push({ type: "hline", value: c.hold_rpm, color: "#ffffff66" });
    }
    // scatter precisa estar ordenado em x para o recorte; o motor de gráfico ordena por varredura simples
    cv.setLayers(layers); charts.push(cv);
    if (!c) el.append(h("p", { class: "help" }, "Poucas amostras em movimento para estimar a curva do CVT."));

    el.append(section("Tempo por faixa de RPM"));
    const g2 = h("div", { class: "grid g2" }); el.append(g2);
    const a = new Chart(g2, { title: "Tempo por faixa de RPM", unit: "s", height: 230, xLabel: "rpm" });
    const w = d.rpm_hist.centers.length > 1 ? d.rpm_hist.centers[1] - d.rpm_hist.centers[0] : 1;
    const pb = d.power_band;
    a.setLayers([...(pb ? [{ type: "xband", from: pb.band[0], to: pb.band[1], color: "#27f4d2", alpha: 0.12 }] : []),
      { type: "bars", x: d.rpm_hist.centers, y: d.rpm_hist.seconds, color: run.color, fillRatio: 0.9 }]);
    const b = new Chart(g2, { title: "Tempo por faixa de velocidade", unit: "s", height: 230, xLabel: "km/h" });
    b.setLayers([{ type: "bars", x: d.vel_hist.centers, y: d.vel_hist.seconds, color: "#3b82f6", fillRatio: 0.9 }]);
    charts.push(a, b);
    void w;

    el.append(section("Espectro do RPM"));
    const fbox = h("div"); el.append(fbox);
    const f = new Chart(fbox, { title: "FFT do RPM", unit: "magnitude", height: 190, xLabel: "Hz" });
    f.setLayers([{ type: "line", x: d.rpm_fft.freq, y: d.rpm_fft.mag, color: "#b388ff", width: 1.6, fill: true }]);
    charts.push(f);
    el.append(h("p", { class: "help" }, "Picos no espectro do RPM indicam oscilações periódicas (por exemplo, o CVT pendulando)."));

    const gears = Object.entries(d.gears || {});
    if (gears.length) {
      el.append(section("Relações estimadas (picos de RPM/velocidade)"));
      el.append(h("div", { class: "card" }, h("table", { class: "table" }, h("thead", null, h("tr", null, ["Relação", "RPM por km/h", "km/h a 1000 rpm", "Amostras", "Frequência"].map((x) => h("th", null, x)))),
        h("tbody", null, gears.map(([k, g]) => h("tr", null, h("td", null, k), h("td", { class: "mono" }, g.ratio_rpm_kmh), h("td", { class: "mono" }, g.vel_por_1000rpm), h("td", { class: "mono" }, g.amostras), h("td", { class: "mono" }, g["freq_%"] + "%")))))));
    }
    return { destroy() { charts.forEach((c) => c.destroy()); } };
  },
};
