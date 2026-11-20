import { api, guarded } from "../api.js";
import { download, h, toast } from "../dom.js";
import { store } from "../store.js";
import { head, needData, section, select } from "./_shared.js";

const FORMATS = [[".pdf", "📄", "PDF", "Relatório paginado: resumo, tabelas, gráficos e insights."], [".xlsx", "📊", "Excel", "Abas com gráficos nativos, qualidade, CVT e proveniência."],
  [".html", "🌐", "HTML", "Arquivo único, abre no navegador e imprime bem."], [".json", "{ }", "JSON", "Modelo completo e estruturado para integrações."], [".csv", "⬇", "CSV", "Uma linha por amostra, todas as runs."]];
const METRICS = [["vel_max", "Vel. máx"], ["vel_mean", "Vel. média"], ["rpm_max", "RPM máx"], ["rpm_mean", "RPM médio"], ["dist_total", "Distância"]];

export default {
  id: "reports", title: "Relatórios", short: "Relatório",
  async mount(el) {
    if (needData(el)) return;
    const title = h("input", { type: "text", value: "Relatório de Telemetria", style: { width: "100%" } });
    const keys = [["", "— não incluir —"], ...store.state.setup_keys.map((k) => [k, k])];
    let setupKey = "", metric = "vel_mean";
    const opts = () => ({ title: title.value.trim() || "Relatório", setup_key: setupKey, metric });
    el.append(head("Relatórios", "Gere o relatório da sessão com o filtro atual"));
    el.append(h("div", { class: "card" }, h("div", { class: "grid g3" },
      h("label", { class: "field" }, "Título", title),
      h("label", { class: "field" }, "Comparar setups por", select(keys, "", (v) => { setupKey = v; })),
      h("label", { class: "field" }, "Métrica da comparação", select(METRICS, metric, (v) => { metric = v; })))));
    el.append(section("Formatos"));
    const grid = h("div", { class: "grid g3" });
    for (const [ext, ic, name, desc] of FORMATS) {
      const btn = h("button", { class: "btn", onClick: async () => {
        btn.disabled = true; btn.textContent = "Gerando…";
        try {
          const blob = await api.blob("/api/report", { format: ext, ...opts() });
          download(blob, `${opts().title.replace(/\s+/g, "_")}${ext}`);
          toast(`${name} gerado.`, "ok");
        } catch (e) { toast(e.message, "error", 7000); }
        btn.disabled = false; btn.textContent = `Gerar ${name}`;
      } }, `Gerar ${name}`);
      grid.append(h("div", { class: "card report-card" }, h("h4", null, `${ic}  ${name}`), h("span", { class: "help" }, desc), btn));
    }
    el.append(grid);
    el.append(section("Pré-visualização"));
    const frame = h("iframe", { class: "preview", title: "Prévia do relatório" });
    el.append(h("div", { class: "row", style: { marginBottom: "8px" } }, h("button", { class: "btn primary", onClick: async () => {
      const html = await guarded(() => api.text("/api/report/preview", opts()));
      if (html) frame.srcdoc = html;
    } }, "Atualizar prévia"), h("span", { class: "help" }, "Mesmo conteúdo do HTML exportado.")), frame);
  },
};
