import test from "node:test";
import assert from "node:assert/strict";
import { bisect, clamp, fmtDelta, fmtInt, fmtTime, groupBy, ledState, nearestIndex, niceTicks, rankBy } from "../../src/mangue_logger/web/static/js/util.js";

test("niceTicks gera passos redondos dentro do intervalo", () => {
  const t = niceTicks(0, 37, 6);
  assert.deepEqual(t, [0, 10, 20, 30]);
  assert.ok(niceTicks(-1.3, 2.9, 5).every((v) => v >= -1.3 && v <= 2.9));
  assert.deepEqual(niceTicks(5, 5), [5]);
  assert.deepEqual(niceTicks(NaN, 1), []);
});

test("bisect / nearestIndex", () => {
  const a = [0, 1, 2, 3, 10];
  assert.equal(bisect(a, 2), 2);
  assert.equal(bisect(a, 2.1), 3);
  assert.equal(nearestIndex(a, 2.4), 2);
  assert.equal(nearestIndex(a, 6), 3);      // 6 está mais perto de 3 (dist 3) que de 10 (dist 4)
  assert.equal(nearestIndex(a, -5), 0);
  assert.equal(nearestIndex(a, 99), 4);
  assert.equal(nearestIndex([], 1), -1);
});

test("formatação de tempo e delta", () => {
  assert.equal(fmtTime(83.456), "1:23.456");
  assert.equal(fmtTime(5.5), "0:05.500");
  assert.equal(fmtTime(-1.25), "-0:01.250");
  assert.equal(fmtDelta(1.2346), "+1.235");
  assert.equal(fmtDelta(-0.5), "-0.500");
  assert.equal(fmtDelta(0.0001), "0.000");
  assert.equal(fmtDelta(NaN), "—");
  assert.equal(fmtInt(12345.6), "12 346");
});

test("rankBy: líder, posições e gaps", () => {
  const r = rankBy([{ v: 10 }, { v: 30 }, { v: 20 }], "v");
  assert.deepEqual(r.map((x) => x.pos), [1, 2, 3]);
  assert.deepEqual(r.map((x) => x.item.v), [30, 20, 10]);
  assert.deepEqual(r.map((x) => x.gap), [0, -10, -20]);
  assert.equal(rankBy([{ v: 3 }, { v: 1 }], "v", false)[0].item.v, 1);
});

test("LEDs de shift light: zonas e preenchimento", () => {
  assert.equal(ledState(0, 15, 0).lit, false);
  assert.equal(ledState(0, 15, 0.5).lit, true);
  assert.equal(ledState(1, 15, 0.5).color, "green");
  assert.equal(ledState(10, 15, 1).color, "red");
  assert.equal(ledState(14, 15, 1).color, "blue");
  assert.equal(ledState(14, 15, 1).lit, true);
});

test("clamp e groupBy", () => {
  assert.equal(clamp(5, 0, 3), 3);
  assert.deepEqual(groupBy([1, 2, 3, 4], (x) => x % 2), { 0: [2, 4], 1: [1, 3] });
});
