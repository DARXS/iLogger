// Funções puras (sem DOM) — testáveis com `node --test`.

export const clamp = (v, a, b) => Math.min(b, Math.max(a, v));

/** Primeiro índice i com arr[i] >= x (arr ordenado). */
export function bisect(arr, x) {
  let lo = 0, hi = arr.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (arr[mid] < x) lo = mid + 1; else hi = mid;
  }
  return lo;
}

export function nearestIndex(arr, x) {
  if (!arr.length) return -1;
  const i = bisect(arr, x);
  if (i <= 0) return 0;
  if (i >= arr.length) return arr.length - 1;
  return (x - arr[i - 1] <= arr[i] - x) ? i - 1 : i;
}

function niceNum(range, round) {
  const exp = Math.floor(Math.log10(range));
  const f = range / Math.pow(10, exp);
  let nf;
  if (round) nf = f < 1.5 ? 1 : f < 3 ? 2 : f < 7 ? 5 : 10;
  else nf = f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10;
  return nf * Math.pow(10, exp);
}

/** Ticks "bonitos" entre min e max. */
export function niceTicks(min, max, count = 6) {
  if (!isFinite(min) || !isFinite(max)) return [];
  if (max === min) return [min];
  const range = niceNum(max - min, false);
  const step = niceNum(range / Math.max(1, count - 1), true);
  const start = Math.ceil(min / step - 1e-9) * step;
  const out = [];
  for (let v = start; v <= max + step * 1e-9; v += step) out.push(Math.abs(v) < step * 1e-9 ? 0 : +v.toPrecision(12));
  return out;
}

export function decimals(step) {
  if (!step || !isFinite(step)) return 0;
  return clamp(Math.ceil(-Math.log10(step)) + (step < 1 ? 0 : 0), 0, 6);
}

export function fmt(v, d = 1) {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return Number(v).toFixed(d);
}

export function fmtInt(v) {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return Math.round(v).toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ");
}

/** 83.456 → "1:23.456" */
export function fmtTime(s) {
  if (s === null || s === undefined || Number.isNaN(s)) return "—";
  const sign = s < 0 ? "-" : "";
  s = Math.abs(s);
  const m = Math.floor(s / 60);
  const rest = s - m * 60;
  return `${sign}${m}:${rest.toFixed(3).padStart(6, "0")}`;
}

/** Delta com sinal explícito: +1.234 / -0.500 / 0.000 */
export function fmtDelta(s, d = 3) {
  if (s === null || s === undefined || Number.isNaN(s)) return "—";
  if (Math.abs(s) < Math.pow(10, -d) / 2) return (0).toFixed(d);
  return (s > 0 ? "+" : "") + s.toFixed(d);
}

/** Ranking por métrica (maior = melhor). Devolve [{item, pos, gap}] */
export function rankBy(items, key, higherIsBetter = true) {
  const sorted = [...items].sort((a, b) => (higherIsBetter ? b[key] - a[key] : a[key] - b[key]));
  const lead = sorted.length ? sorted[0][key] : 0;
  return sorted.map((item, i) => ({ item, pos: i + 1, gap: item[key] - lead }));
}

/** Cor de LED de "shift lights" para i-ésimo de n, dado o percentual de RPM (0..1). */
export function ledState(i, n, pct) {
  const lit = i < Math.round(pct * n);
  const zone = i / n;
  const color = zone < 0.5 ? "green" : zone < 0.8 ? "red" : "blue";
  return { lit, color };
}

export function debounce(fn, ms) {
  let t;
  return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

export function groupBy(arr, fn) {
  const m = {};
  for (const x of arr) (m[fn(x)] ||= []).push(x);
  return m;
}
