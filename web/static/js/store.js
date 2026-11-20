// Estado global mínimo + eventos.
import { api } from "./api.js";

export const store = {
  state: null,            // /api/state
  hidden: new Set(),      // runs ocultas nos gráficos
  refId: null,            // run de referência (delta, setores)
  xAxis: "time",          // "time" | "dist"
  view: "overview",
};

const bus = new EventTarget();
export const on = (name, fn) => { bus.addEventListener(name, (e) => fn(e.detail)); };
export const emit = (name, detail) => bus.dispatchEvent(new CustomEvent(name, { detail }));

export function applyState(s) {
  store.state = s;
  const ids = s.runs.map((r) => r.id);
  if (!ids.includes(store.refId)) store.refId = ids[0] ?? null;
  for (const id of [...store.hidden]) if (!ids.includes(id)) store.hidden.delete(id);
  emit("state", s);
}

export async function refresh() {
  applyState(await api.get("/api/state"));
}

export const runs = () => store.state?.runs ?? [];
export const visibleRuns = () => runs().filter((r) => !store.hidden.has(r.id));
export const runById = (id) => runs().find((r) => r.id === id);
export const hasData = () => runs().length > 0;
