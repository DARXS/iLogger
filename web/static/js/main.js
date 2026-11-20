// Shell do app: navegação, barra de runs, gaveta de filtro, upload e roteamento.
import { api, guarded } from "./api.js";
import { $, clear, h, toast } from "./dom.js";
import { applyState, emit, on, refresh, runs, store } from "./store.js";
import { debounce, fmt } from "./util.js";
import overview from "./views/overview.js";
import telemetry from "./views/telemetry.js";
import compare from "./views/compare.js";
import replay from "./views/replay.js";
import engine from "./views/engine.js";
import setups from "./views/setups.js";
import runsView from "./views/runs.js";
import library from "./views/library.js";
import reports from "./views/reports.js";
import settings from "./views/settings.js";

const VIEWS = [overview, telemetry, compare, replay, engine, setups, runsView, library, reports, settings];
const ICONS = {
  overview: "M3 13h4v8H3zM10 3h4v18h-4zM17 9h4v12h-4z",
  telemetry: "M3 17l5-6 4 3 5-8 4 5M3 21h18",
  compare: "M4 6h12M4 12h16M4 18h8M18 4v4M20 10v4M14 16v4",
  replay: "M5 4l14 8-14 8z",
  engine: "M4 10h2l1-2h8l1 2h2v6h-2l-1 2H7l-1-2H4zM9 6V4m6 2V4",
  setups: "M5 20V10m7 10V4m7 16v-7",
  runs: "M4 6h16M4 12h16M4 18h10",
  library: "M4 5c0-1 3-2 8-2s8 1 8 2-3 2-8 2-8-1-8-2zm0 0v14c0 1 3 2 8 2s8-1 8-2V5M4 12c0 1 3 2 8 2s8-1 8-2",
  reports: "M7 3h8l4 4v14H7zM15 3v4h4M10 12h6M10 16h6",
  settings: "M12 8a4 4 0 100 8 4 4 0 000-8zm8 4l2-1-2-4-2 1-2-1-1-2h-4l-1 2-2 1-2-1-2 4 2 1v2l-2 1 2 4 2-1 2 1 1 2h4l1-2 2-1 2 1 2-4-2-1z",
};

let current = null;       // {view, instance}
const root = () => $("#view");

function icon(name) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  const p = document.createElementNS("http://www.w3.org/2000/svg", "path");
  p.setAttribute("d", ICONS[name] || ICONS.overview);
  svg.append(p);
  return svg;
}

function renderNav() {
  const nav = clear($("#nav"));
  for (const v of VIEWS) {
    nav.append(h("button", { class: "nav-item" + (store.view === v.id ? " active" : ""), title: v.title, onClick: () => go(v.id) }, icon(v.id), v.short || v.title));
  }
}

function renderRunbar() {
  const bar = clear($("#runbar"));
  for (const r of runs()) {
    const hidden = store.hidden.has(r.id);
    bar.append(h("div", { class: "run-chip" + (hidden ? " hidden" : ""), style: { "--c": r.color }, title: r.name },
      h("button", { class: "ic ref", title: "Definir como referência", onClick: () => { store.refId = r.id; emit("ref"); renderRunbar(); } }, store.refId === r.id ? "★" : "☆"),
      r.name.replace(/\.csv$/i, ""),
      h("button", { class: "ic", title: hidden ? "Mostrar nos gráficos" : "Ocultar dos gráficos", onClick: () => { hidden ? store.hidden.delete(r.id) : store.hidden.add(r.id); emit("visibility"); renderRunbar(); } }, hidden ? "○" : "●"),
      h("button", { class: "ic", title: "Remover da sessão", onClick: async () => { const s = await guarded(() => api.del(`/api/runs/${r.id}`)); if (s) applyState(s); } }, "✕")));
  }
}

export function go(id) {
  if (!VIEWS.find((v) => v.id === id)) id = "overview";
  location.hash = "#/" + id;
}

async function mount() {
  const id = (location.hash.replace(/^#\//, "") || "overview").split("?")[0];
  const view = VIEWS.find((v) => v.id === id) || VIEWS[0];
  store.view = view.id;
  if (current?.instance?.destroy) current.instance.destroy();
  const el = clear(root());
  renderNav();
  current = { view, instance: null };
  try {
    current.instance = await view.mount(el);
  } catch (e) {
    console.error(e);
    el.append(h("div", { class: "empty" }, h("h2", null, "Algo deu errado"), h("p", { class: "muted" }, e.message)));
    toast(e.message, "error", 7000);
  }
}

// ── upload ──────────────────────────────────────────────────────────────────
export async function loadFiles(files, replace = false) {
  files = [...files];
  const proj = files.find((f) => f.name.endsWith(".mlproj"));
  if (proj) {
    const form = new FormData(); form.append("file", proj, proj.name);
    const res = await guarded(async () => (await fetch("/api/project", { method: "POST", body: form }).then(async (r) => { if (!r.ok) throw new Error((await r.json()).detail); return r.json(); })));
    if (res) { applyState(res.state); toast("Projeto carregado.", "ok"); }
    return;
  }
  const ok = files.filter((f) => /\.csv$/i.test(f.name) || /\.meta\.json$/i.test(f.name));
  if (!ok.length) { toast("Selecione arquivos .csv", "error"); return; }
  document.body.classList.add("loading");
  const res = await guarded(() => api.upload("/api/upload", ok, { replace }));
  document.body.classList.remove("loading");
  if (!res) return;
  applyState(res.state);
  if (res.errors?.length) toast(res.errors.join("\n"), "error", 9000);
  if (res.duplicates?.length) toast(`Já carregada(s): ${res.duplicates.join(", ")}`);
  if (res.added?.length) { toast(`${res.added.length} run(s) carregada(s).`, "ok"); if (store.view === "overview" || !runs().length) go("overview"); }
}

export async function loadDemo() {
  const res = await guarded(() => api.post("/api/demo"));
  if (res) { applyState(res.state); toast("Demonstração carregada (dados sintéticos).", "ok"); go("overview"); }
}

function setupUpload() {
  const input = $("#file-input");
  $("#btn-load").addEventListener("click", () => input.click());
  input.addEventListener("change", () => { if (input.files.length) loadFiles(input.files); input.value = ""; });
  const dz = $("#dropzone");
  let depth = 0;
  window.addEventListener("dragenter", (e) => { e.preventDefault(); depth++; dz.classList.add("on"); });
  window.addEventListener("dragleave", () => { depth = Math.max(0, depth - 1); if (!depth) dz.classList.remove("on"); });
  window.addEventListener("dragover", (e) => e.preventDefault());
  window.addEventListener("drop", (e) => { e.preventDefault(); depth = 0; dz.classList.remove("on"); if (e.dataTransfer?.files?.length) loadFiles(e.dataTransfer.files); });
}

// ── gaveta de filtro ────────────────────────────────────────────────────────
const KINDS = { butterworth: "Butterworth", bessel: "Bessel", chebyshev_type_i: "Chebyshev I", savitzky_golay: "Savitzky-Golay", median: "Mediana", moving_average: "Média móvel" };

function renderDrawer() {
  const d = clear($("#drawer"));
  const f = store.state?.filter;
  if (!f) return;
  const nyq = store.state.nyquist_hz;
  const body = { ...f };
  const push = debounce(async () => {
    const s = await guarded(() => api.put("/api/filter", body));
    if (s) { applyState(s); }
  }, 280);
  const set = (k, v) => { body[k] = v; push(); renderDrawer.pending = true; };
  const slider = (key, label, min, max, step, unit = "", fmtd = 2) => {
    const val = h("span", { class: "mono" }, fmt(body[key], fmtd) + unit);
    const inp = h("input", { type: "range", min, max, step, value: body[key], onInput: (e) => { val.textContent = fmt(+e.target.value, fmtd) + unit; set(key, +e.target.value); } });
    return h("label", { class: "field" }, h("span", { class: "row" }, label, h("span", { class: "spacer" }), val), inp);
  };
  const lp = ["butterworth", "bessel", "chebyshev_type_i"];
  const kindSel = h("select", { onChange: (e) => { body.kind = e.target.value; push(); setTimeout(renderDrawer, 0); } }, ...Object.entries(KINDS).map(([k, v]) => h("option", { value: k, selected: k === body.kind }, v)));
  d.append(h("h3", null, "Filtro de sinal"), h("div", { class: "stack" },
    h("label", { class: "field" }, "Tipo", kindSel),
    lp.includes(body.kind) ? [slider("order", "Ordem", 1, 8, 1, "", 0), slider("cutoff_hz", "Corte", 0.05, +(nyq * 0.95).toFixed(2), 0.05, " Hz"),
      body.kind === "chebyshev_type_i" ? slider("ripple_db", "Ripple", 0.1, 5, 0.1, " dB", 1) : null] : null,
    body.kind === "savitzky_golay" ? [slider("window", "Janela", 5, 61, 2, "", 0), slider("polyorder", "Polinômio", 1, 6, 1, "", 0)] : null,
    body.kind === "median" ? slider("kernel", "Kernel", 3, 41, 2, "", 0) : null,
    body.kind === "moving_average" ? slider("window", "Janela", 2, 61, 1, "", 0) : null,
    slider("accel_cutoff_hz", "Corte da aceleração", 0.1, +(nyq * 0.95).toFixed(2), 0.05, " Hz"),
    h("p", { class: "help" }, `Taxa de amostragem ${fmt(nyq * 2, 0)} Hz · Nyquist ${fmt(nyq, 0)} Hz. Zero-fase (filtfilt): o filtro não atrasa o sinal.`),
    h("button", { class: "btn small", onClick: () => toggleDrawer(false) }, "Fechar")));
}

export function toggleDrawer(force) {
  const d = $("#drawer");
  const open = force ?? !d.classList.contains("open");
  d.classList.toggle("open", open);
  d.setAttribute("aria-hidden", String(!open));
  if (open) renderDrawer();
}

// ── boot ────────────────────────────────────────────────────────────────────
async function boot() {
  setupUpload();
  $("#btn-filter").addEventListener("click", () => toggleDrawer());
  window.addEventListener("hashchange", mount);
  on("state", () => { renderRunbar(); mount(); if ($("#drawer").classList.contains("open") && !renderDrawer.pending) renderDrawer(); renderDrawer.pending = false; });
  on("visibility", () => mount());
  on("ref", () => mount());
  if (!location.hash) history.replaceState(null, "", "#/overview");
  renderNav();
  await guarded(refresh);                     // emite "state" → renderiza runbar + view
  if (!store.state) clear(root()).append(h("div", { class: "empty" }, h("h2", null, "Servidor indisponível")));
}

// Hook de depuração/testes E2E (não faz parte da API pública).
window.mangue = { store, refresh, go, loadDemo, loadFiles };

boot();
