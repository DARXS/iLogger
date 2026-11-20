// Peças de UI compartilhadas entre as views.
import { h } from "../dom.js";
import { go, loadDemo } from "../main.js";
import { hasData, runs, store } from "../store.js";

export const PHASE_COLORS = { "aceleração": "#00d26a", "estabilização": "#ffd60a", "frenagem": "#e10600" };
export const LEVEL_LABEL = { critical: "Crítico", warning: "Atenção", good: "OK", info: "Info" };

export function head(title, sub, ...actions) {
  return h("div", { class: "view-head" }, h("h1", null, title), sub ? h("span", { class: "sub" }, sub) : null, h("span", { class: "spacer" }), ...actions);
}

/** Se não há dados, desenha o estado vazio e devolve true. */
export function needData(el, minRuns = 1, msg = "") {
  if (hasData() && runs().length >= minRuns) return false;
  el.append(h("div", { class: "empty" },
    h("h2", null, hasData() ? "Precisa de mais runs" : "Sem dados na sessão"),
    h("p", null, msg || (hasData() ? `Esta tela compara runs: carregue pelo menos ${minRuns}.` : "Arraste CSVs para a janela, use ＋ Carregar ou experimente a demonstração.")),
    h("div", { class: "row", style: { justifyContent: "center" } },
      h("button", { class: "btn primary", onClick: () => document.getElementById("btn-load").click() }, "＋ Carregar CSVs"),
      h("button", { class: "btn", onClick: loadDemo }, "▶ Carregar demonstração"))));
  return true;
}

export function kpi(label, value, unit, color) {
  return h("div", { class: "kpi", style: color ? { "--c": color } : null }, h("div", { class: "l" }, label), h("div", null, h("span", { class: "v" }, value), unit ? h("span", { class: "u" }, unit) : null));
}

export function section(text) { return h("div", { class: "section-title" }, text); }

export function legend(rs) {
  return h("div", { class: "legend" }, rs.map((r) => h("span", null, h("i", { style: { background: r.color } }), r.name.replace(/\.csv$/i, ""), store.refId === r.id ? " ★" : "")));
}

export function finding(f) {
  return h("div", { class: `finding ${f.level}` }, h("b", null, f.title), h("span", null, f.body));
}

export function phasebar(phases) {
  return h("div", { class: "phasebar", title: Object.entries(phases || {}).map(([k, v]) => `${k}: ${v["percent_%"]}%`).join(" · ") },
    ["aceleração", "estabilização", "frenagem"].map((k) => h("i", { style: { width: `${phases?.[k]?.["percent_%"] ?? 0}%`, background: PHASE_COLORS[k] } })));
}

export function select(options, value, onChange) {
  return h("select", { onChange: (e) => onChange(e.target.value) }, options.map(([v, l]) => h("option", { value: v, selected: v === value }, l)));
}

export function seg(options, value, onChange) {
  const box = h("div", { class: "seg" });
  const draw = (cur) => { box.replaceChildren(...options.map(([v, l]) => h("button", { class: v === cur ? "on" : "", onClick: () => { onChange(v); draw(v); } }, l))); };
  draw(value);
  return box;
}

export const goto = go;
