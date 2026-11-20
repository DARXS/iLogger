import { api } from "../api.js";
import { h } from "../dom.js";
import { store } from "../store.js";
import { fmt, fmtInt, rankBy } from "../util.js";
import { finding, head, kpi, needData, phasebar, section } from "./_shared.js";

function spark(spec, color) {
  const c = h("canvas", { class: "spark", width: 240, height: 52 });
  const ctx = c.getContext("2d");
  const { t, v } = spec;
  if (v.length > 1) {
    const hi = Math.max(...v, 1), t1 = t[t.length - 1] || 1;
    ctx.strokeStyle = color; ctx.lineWidth = 2; ctx.beginPath();
    v.forEach((y, i) => { const px = (t[i] / t1) * 236 + 2, py = 48 - (y / hi) * 44; i ? ctx.lineTo(px, py) : ctx.moveTo(px, py); });
    ctx.stroke();
  }
  return c;
}

export default {
  id: "overview", title: "Visão geral", short: "Visão",
  async mount(el) {
    if (needData(el)) return;
    const data = await api.get("/api/overview");
    const runs = data.runs.map((r) => ({ ...r, vel_mean: r.stats_by_id.vel_mean, vel_max: r.stats_by_id.vel_max, rpm_max: r.stats_by_id.rpm_max, dist: r.stats_by_id.dist_total, dur: r.stats_by_id.duration }));
    const best = [...runs].sort((a, b) => b.vel_max - a.vel_max)[0];
    el.append(head("Visão geral", `${runs.length} run(s) · ${data.filter}`));

    el.append(h("div", { class: "kpis" },
      kpi("Vel. máx da sessão", fmt(best.vel_max), "km/h", best.color),
      kpi("RPM máx", fmtInt(Math.max(...runs.map((r) => r.rpm_max))), "rpm", "#ff8000"),
      kpi("Distância total", fmtInt(runs.reduce((s, r) => s + r.dist, 0)), "m", "#27f4d2"),
      kpi("Alertas", String(data.insights.filter((i) => i.level === "critical" || i.level === "warning").length), "", "#ffd60a")));

    el.append(section("Resumo da sessão"));
    el.append(h("div", { class: "card accent" }, h("ul", { style: { margin: 0, paddingLeft: "18px" } }, data.summary.map((s) => h("li", null, s)))));

    el.append(section("Ranking por velocidade média"));
    const ranked = rankBy(runs, "vel_mean");
    const tbody = h("tbody");
    for (const { item: r, pos, gap } of ranked) {
      tbody.append(h("tr", { style: { "--c": r.color } },
        h("td", { class: "pos" }, pos),
        h("td", { class: "name" }, h("span", { class: "bar" }), r.name.replace(/\.csv$/i, "")),
        h("td", null, r.quality_warnings.length ? h("span", { class: "badge warn", title: r.quality_warnings.join("\n") }, `${r.quality_warnings.length} aviso(s)`) : h("span", { class: "badge ok" }, "dados ok"),
          " ", r.tags.map((t) => h("span", { class: "badge tag" }, t)), " ", Object.entries(r.setup).map(([k, v]) => h("span", { class: "badge" }, `${k}=${v}`))),
        h("td", null, fmt(r.vel_mean)),
        h("td", { class: "gap" + (pos === 1 ? " lead" : "") }, pos === 1 ? "LÍDER" : fmt(gap)),
        h("td", null, fmt(r.vel_max)), h("td", null, fmtInt(r.rpm_max)), h("td", null, fmtInt(r.dist)), h("td", null, fmt(r.dur) + " s"),
        h("td", null, phasebar(r.phases)), h("td", null, spark(r.spark, r.color))));
    }
    el.append(h("div", { class: "card", style: { padding: 0, overflowX: "auto" } }, h("table", { class: "tower" },
      h("thead", null, h("tr", null, ["#", "Run", "Dados", "Vel. média", "Gap", "Vel. máx", "RPM máx", "Dist. (m)", "Duração", "Fases", "Perfil"].map((x) => h("th", null, x)))), tbody)));

    el.append(section("Insights"));
    const levels = new Set();
    const list = h("div");
    const counts = Object.fromEntries(["critical", "warning", "good", "info"].map((l) => [l, data.insights.filter((i) => i.level === l).length]));
    const chips = h("div", { class: "row wrap", style: { marginBottom: "10px" } });
    const draw = () => {
      list.replaceChildren(...data.insights.filter((i) => !levels.size || levels.has(i.level)).slice(0, 120).map(finding));
      chips.replaceChildren(...[["critical", "Crítico"], ["warning", "Atenção"], ["good", "OK"], ["info", "Info"]].map(([l, n]) =>
        h("button", { class: "chip" + (levels.has(l) ? " on" : ""), onClick: () => { levels.has(l) ? levels.delete(l) : levels.add(l); draw(); } }, `${n} ${counts[l]}`)));
    };
    draw();
    el.append(chips, list);
  },
};
