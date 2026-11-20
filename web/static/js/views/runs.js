import { api, guarded } from "../api.js";
import { h, toast } from "../dom.js";
import { applyState, runs } from "../store.js";
import { fmt } from "../util.js";
import { head, needData } from "./_shared.js";

const SUGGESTED = ["rpm_baixa", "rpm_alta", "peso_cvt", "mola", "rampa", "piloto", "pista"];

export default {
  id: "runs", title: "Runs", short: "Runs",
  async mount(el) {
    if (needData(el)) return;
    const list = runs();
    let sel = sessionStorage.getItem("mangue.runsel");
    if (!list.find((r) => r.id === sel)) sel = list[0].id;
    el.append(head("Runs", "Qualidade dos dados e metadados (gravados ao lado do CSV)"));
    const tbody = h("tbody");
    const editor = h("div", { class: "card accent" });

    const select = (id) => { sel = id; sessionStorage.setItem("mangue.runsel", id); drawTable(); drawEditor(); };
    const drawTable = () => tbody.replaceChildren(...list.map((r) => h("tr", { class: r.id === sel ? "sel" : "", style: { cursor: "pointer" }, onClick: () => select(r.id) },
      h("td", null, h("span", { style: { display: "inline-block", width: "4px", height: "16px", background: r.color, marginRight: "8px", verticalAlign: "middle" } }), r.name),
      h("td", { class: "mono" }, r.n_samples), h("td", { class: "mono" }, fmt(r.duration_s) + " s"),
      h("td", null, r.quality.ok ? h("span", { class: "badge ok" }, "ok") : h("span", { class: "badge warn", title: r.quality.warnings.join("\n") }, `${r.quality.warnings.length} aviso(s)`)),
      h("td", null, r.meta.tags.map((t) => h("span", { class: "badge tag" }, t))),
      h("td", { class: "muted" }, Object.entries(r.meta.setup).map(([k, v]) => `${k}=${v}`).join(" · ")))));

    function drawEditor() {
      const r = list.find((x) => x.id === sel);
      const rows = Object.entries(r.meta.setup).map(([k, v]) => [k, v]);
      const kvBox = h("div");
      const drawKv = () => kvBox.replaceChildren(...rows.map((row, i) => h("div", { class: "kv" },
        h("input", { type: "text", value: row[0], placeholder: "chave", onInput: (e) => { row[0] = e.target.value; } }),
        h("input", { type: "text", value: row[1], placeholder: "valor", onInput: (e) => { row[1] = e.target.value; } }),
        h("button", { class: "btn small danger", title: "Remover", onClick: () => { rows.splice(i, 1); drawKv(); } }, "✕"))));
      drawKv();
      const tags = h("input", { type: "text", value: r.meta.tags.join(", "), placeholder: "enduro, cvt-teste" });
      const notes = h("textarea", { rows: 4, value: r.meta.notes, placeholder: "Condições da pista, ajustes…" });
      const collect = () => ({ setup: Object.fromEntries(rows.filter(([k, v]) => k.trim() && String(v).trim())), tags: tags.value.split(",").map((t) => t.trim()).filter(Boolean), notes: notes.value });
      const save = async (all) => {
        const body = collect();
        const targets = all ? list : [r];
        let s;
        for (const t of targets) s = await guarded(() => api.put(`/api/runs/${t.id}/meta`, all && t !== r ? { ...body, notes: t.meta.notes } : body));
        if (s) { toast(all ? "Metadados aplicados a todas as runs." : "Metadados salvos.", "ok"); applyState(s); }
      };
      editor.replaceChildren(
        h("h3", { style: { margin: "0 0 4px" } }, r.name), r.quality.warnings.map((w) => h("div", { class: "finding warning" }, h("span", null, w))),
        h("div", { class: "section-title" }, "Setup do veículo"), kvBox,
        h("div", { class: "row" }, h("button", { class: "btn small", onClick: () => { rows.push(["", ""]); drawKv(); } }, "＋ Campo"),
          h("button", { class: "btn small", onClick: () => { for (const k of SUGGESTED) if (!rows.some((x) => x[0] === k)) rows.push([k, ""]); drawKv(); } }, "Campos sugeridos")),
        h("div", { class: "section-title" }, "Tags"), tags, h("div", { class: "section-title" }, "Notas"), notes,
        h("div", { class: "row", style: { marginTop: "12px" } }, h("button", { class: "btn primary", onClick: () => save(false) }, "💾 Salvar"), h("button", { class: "btn", onClick: () => save(true) }, "Aplicar setup/tags a todas")));
    }
    drawTable(); drawEditor();
    el.append(h("div", { class: "grid g-side" },
      h("div", { class: "card", style: { padding: 0, overflowX: "auto", alignSelf: "start" } }, h("table", { class: "table" }, h("thead", null, h("tr", null, ["Run", "Amostras", "Duração", "Qualidade", "Tags", "Setup"].map((x) => h("th", null, x)))), tbody)), editor));
  },
};
