import { api, guarded } from "../api.js";
import { download, h, toast } from "../dom.js";
import { loadFiles } from "../main.js";
import { applyState, store } from "../store.js";
import { head, section } from "./_shared.js";

const SENSOR = [["tire_radius_m", "Raio do pneu (m)", "number"], ["disc_holes", "Furos do disco de freio", "number"], ["window_samples", "Amostras por janela", "number"],
  ["window_dt_s", "Duração da janela (s)", "number"], ["rpm_pulses_per_rev", "Pulsos por volta (RPM)", "number"], ["rpm_column", "Coluna do RPM no CSV", "text"], ["speed_column", "Coluna da velocidade no CSV", "text"]];
const RULES = [["hard_brake_ms2", "Frenagem brusca (m/s²)"], ["hard_accel_ms2", "Aceleração violenta (m/s²)"], ["rpm_util_good", "Utilização de RPM boa (0–1)"], ["rpm_spike", "Salto de RPM (rpm/amostra)"],
  ["rpm_spike_count", "Saltos para alertar"], ["anomaly_z", "Z-score de anomalia"], ["phase_accel_thr", "Limiar de aceleração (fases)"], ["phase_brake_thr", "Limiar de frenagem (fases)"],
  ["cvt_hold_cv_warn_pct", "CV% do RPM sustentado (alerta CVT)"], ["cvt_min_speed_kmh", "Velocidade mínima do CVT (km/h)"]];

export default {
  id: "settings", title: "Config", short: "Config",
  async mount(el) {
    const st = store.state;
    const p = JSON.parse(JSON.stringify(st.profile));
    el.append(head("Configuração", `Mangue Logger v${st.version}`));

    const num = (obj, k, type = "number") => h("input", { type: type === "number" ? "number" : "text", step: "any", value: obj[k], onInput: (e) => { obj[k] = type === "number" ? +e.target.value : e.target.value; } });
    const band = p.power_band_rpm ?? [null, null];
    const bandLo = h("input", { type: "number", value: band[0] ?? "", placeholder: "mín" }), bandHi = h("input", { type: "number", value: band[1] ?? "", placeholder: "máx" });
    el.append(section("Perfil do veículo"));
    el.append(h("div", { class: "card accent" },
      h("label", { class: "field", style: { maxWidth: "340px" } }, "Nome", h("input", { type: "text", value: p.name, onInput: (e) => { p.name = e.target.value; } })),
      h("div", { class: "section-title" }, "Sensor (como as contagens viram RPM e velocidade)"),
      h("div", { class: "grid g3" }, SENSOR.map(([k, l, t]) => h("label", { class: "field" }, l, num(p.sensor, k, t)))),
      h("p", { class: "help" }, "Padrão: f1 = RPM e f2 = velocidade. Para CSVs antigos, inverta as colunas."),
      h("div", { class: "section-title" }, "Regras dos insights"),
      h("div", { class: "grid g3" }, RULES.map(([k, l]) => h("label", { class: "field" }, l, num(p.rules, k)))),
      h("div", { class: "section-title" }, "Faixa de potência do motor (opcional)"),
      h("div", { class: "row" }, bandLo, h("span", null, "–"), bandHi, h("span", { class: "help" }, "Ex.: a faixa em que o motor entrega mais potência. Vazio desativa a análise.")),
      h("div", { class: "row", style: { marginTop: "14px" } }, h("button", { class: "btn primary", onClick: async () => {
        p.power_band_rpm = bandLo.value !== "" && bandHi.value !== "" ? [+bandLo.value, +bandHi.value] : null;
        const s = await guarded(() => api.put("/api/profile", p));
        if (s) { applyState(s); toast("Perfil aplicado — runs recarregadas com o novo sensor.", "ok"); }
      } }, "Aplicar perfil"), h("span", { class: "help" }, "As runs da sessão são relidas com o novo sensor."))));

    // setup global + observações
    const info = Object.entries(st.setup_info || {}).map(([k, v]) => [k, v]);
    const kv = h("div"); const obs = h("textarea", { rows: 3, value: st.observations || "", placeholder: "Condições do teste, ajustes…", style: { width: "100%" } });
    const draw = () => kv.replaceChildren(...info.map((r, i) => h("div", { class: "kv" }, h("input", { type: "text", value: r[0], onInput: (e) => { r[0] = e.target.value; } }), h("input", { type: "text", value: r[1], onInput: (e) => { r[1] = e.target.value; } }), h("button", { class: "btn small danger", onClick: () => { info.splice(i, 1); draw(); } }, "✕"))));
    draw();
    el.append(section("Setup global e observações do relatório"));
    el.append(h("div", { class: "card" }, kv, h("div", { class: "row", style: { marginBottom: "8px" } }, h("button", { class: "btn small", onClick: () => { info.push(["", ""]); draw(); } }, "＋ Campo")), obs,
      h("div", { style: { marginTop: "10px" } }, h("button", { class: "btn", onClick: async () => {
        const s = await guarded(() => api.put("/api/session", { setup_info: Object.fromEntries(info.filter(([k, v]) => k.trim() && String(v).trim())), observations: obs.value }));
        if (s) { applyState(s); toast("Salvo.", "ok"); }
      } }, "Salvar"))));

    el.append(section("Sessão"));
    const pf = h("input", { type: "file", accept: ".mlproj", hidden: true, onChange: (e) => { if (e.target.files[0]) loadFiles([e.target.files[0]]); } });
    el.append(h("div", { class: "row wrap" }, pf,
      h("button", { class: "btn", onClick: async () => { try { download(await api.blob("/api/project"), "sessao.mlproj"); } catch (e) { toast(e.message, "error"); } } }, "💾 Exportar projeto (.mlproj)"),
      h("button", { class: "btn", onClick: () => pf.click() }, "📂 Importar projeto"),
      h("button", { class: "btn danger", onClick: async () => { const s = await guarded(() => api.del("/api/runs")); if (s) { applyState(s); toast("Sessão limpa."); } } }, "Limpar sessão")));
  },
};
