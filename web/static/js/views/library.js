import { api, guarded } from "../api.js";
import { h, toast } from "../dom.js";
import { applyState } from "../store.js";
import { debounce, fmt } from "../util.js";
import { head } from "./_shared.js";

export default {
  id: "library", title: "Biblioteca", short: "Biblioteca",
  async mount(el) {
    const q = h("input", { type: "text", placeholder: "🔍 Nome ou notas…", style: { flex: 1 } });
    const tag = h("input", { type: "text", placeholder: "Tag", style: { width: "130px" } });
    const setup = h("input", { type: "text", placeholder: "Setup (mola=dura)", style: { width: "200px" } });
    const tbody = h("tbody"); const count = h("span", { class: "muted" });
    const chosen = new Set();
    let items = [];
    const draw = () => {
      tbody.replaceChildren(...items.map((r) => h("tr", { class: chosen.has(r.id) ? "sel" : "" },
        h("td", null, h("input", { type: "checkbox", checked: chosen.has(r.id), disabled: !r.exists, onChange: (e) => { e.target.checked ? chosen.add(r.id) : chosen.delete(r.id); draw(); } })),
        h("td", { style: { color: r.exists ? "" : "var(--faint)" } }, r.name, r.exists ? "" : " (arquivo ausente)"),
        h("td", { class: "mono" }, new Date(r.added_at * 1000).toLocaleString("pt-BR")), h("td", { class: "mono" }, fmt(r.duration_s) + " s"),
        h("td", { class: "mono" }, fmt(r.vel_max)), h("td", { class: "mono" }, Math.round(r.rpm_max)),
        h("td", null, r.tags.map((t) => h("span", { class: "badge tag" }, t))), h("td", { class: "muted" }, Object.entries(r.setup).map(([k, v]) => `${k}=${v}`).join(" · ")))));
    };
    const load = async () => {
      const res = await guarded(() => api.get("/api/library", { q: q.value, tag: tag.value, setup: setup.value }));
      if (!res) return;
      items = res.items; count.textContent = `${items.length} de ${res.total} run(s)`; draw();
    };
    const dl = debounce(load, 220);
    [q, tag, setup].forEach((i) => i.addEventListener("input", dl));
    const open = async (replace) => {
      if (!chosen.size) { toast("Selecione runs na lista."); return; }
      const res = await guarded(() => api.post("/api/library/open", { ids: [...chosen], replace }));
      if (res) { applyState(res.state); toast(`${res.added.length} run(s) aberta(s).`, "ok"); location.hash = "#/overview"; }
    };
    el.append(head("Biblioteca", "Todas as runs que você já carregou — busque por nome, tag ou setup"));
    el.append(h("div", { class: "row", style: { marginBottom: "10px" } }, q, tag, setup));
    el.append(h("div", { class: "card", style: { padding: 0, overflowX: "auto" } }, h("table", { class: "table" }, h("thead", null, h("tr", null, ["", "Run", "Adicionada", "Duração", "Vel. máx", "RPM máx", "Tags", "Setup"].map((x) => h("th", null, x)))), tbody)));
    el.append(h("div", { class: "row", style: { marginTop: "10px" } }, count, h("span", { class: "spacer" }),
      h("button", { class: "btn danger", onClick: async () => { for (const id of chosen) await guarded(() => api.del(`/api/library/${id}`)); chosen.clear(); load(); } }, "Remover da biblioteca"),
      h("button", { class: "btn", onClick: () => open(false) }, "Adicionar à sessão"), h("button", { class: "btn primary", onClick: () => open(true) }, "▶ Abrir (substitui a sessão)")));
    await load();
  },
};
