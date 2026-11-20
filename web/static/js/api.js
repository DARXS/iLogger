// Cliente HTTP da API local.
import { toast } from "./dom.js";

async function request(method, path, { params, body, form, raw } = {}) {
  let url = path;
  if (params) {
    const q = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== "") q.set(k, v);
    const s = q.toString();
    if (s) url += (url.includes("?") ? "&" : "?") + s;
  }
  const init = { method, headers: {} };
  if (body !== undefined) { init.body = JSON.stringify(body); init.headers["Content-Type"] = "application/json"; }
  if (form) init.body = form;
  const res = await fetch(url, init);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch { /* corpo não-JSON */ }
    const err = new Error(detail);
    err.status = res.status;
    throw err;
  }
  if (raw) return res;
  return res.json();
}

export const api = {
  get: (path, params) => request("GET", path, { params }),
  post: (path, body) => request("POST", path, { body }),
  put: (path, body) => request("PUT", path, { body }),
  del: (path) => request("DELETE", path),
  upload: (path, files, params) => {
    const form = new FormData();
    for (const f of files) form.append("files", f, f.name);
    return request("POST", path, { form, params });
  },
  blob: async (path, params) => (await request("GET", path, { params, raw: true })).blob(),
  text: async (path, params) => (await request("GET", path, { params, raw: true })).text(),
};

/** Executa uma chamada e mostra erro como toast (retorna undefined se falhar). */
export async function guarded(fn) {
  try { return await fn(); } catch (e) { toast(e.message || String(e), "error", 6000); return undefined; }
}
