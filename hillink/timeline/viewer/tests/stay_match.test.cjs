// 10/16 QA · 연박 집계(v4.1 기본 조건 전용)가 다른 조건 하루에 붙지 않는지 — report.js 의 stayMatch 와 app.js 의 stayBreakfast
const fs = require("fs"), path = require("path"), vm = require("vm"), test = require("node:test"), assert = require("node:assert");
const S = JSON.parse(fs.readFileSync(path.join(__dirname, "../static/stay_day.json"), "utf8"));
const src = f => fs.readFileSync(path.join(__dirname, "../static", f), "utf8");
const grab = (code, name) => { const i = code.indexOf("function " + name + "("); let d = 0, j = code.indexOf("{", i); for (; j < code.length; j++) { if (code[j] === "{") d++; else if (code[j] === "}" && --d === 0) break; } return code.slice(i, j + 1); };
const ctx = { STAYDAY: S }; vm.createContext(ctx);
vm.runInContext(grab(src("report.js"), "stayMatch") + "\n" + grab(src("app.js"), "stayBreakfast"), ctx);
const base = S.base_keys.find(k => k.startsWith("2026-10-10_"));
const D = (key, extra) => Object.assign({ key, date: key.slice(0, 10), model_ver: S.model_ver, input_ver: S.input_ver }, extra || {});
test("기본 v4.1 하루에는 연결", () => { assert.ok(ctx.stayMatch(D(base))); assert.ok(ctx.stayBreakfast("2026-10-11", D(base))); });
test("좌석 338 · 변칙 · 다른 조정값 키에는 연결 안 함", () => {
  for (const k of [base.replace("_s100_", "_s100_bs338-"), base.replace("_s100_", "_s100_an1-"), base.replace("bn0.16", "bn0.2")]) {
    assert.ok(!ctx.stayMatch(D(k))); assert.strictEqual(ctx.stayBreakfast("2026-10-11", D(k)), null);
  }
});
test("입력 · 모델 버전이 다르면 연결 안 함", () => {
  assert.ok(!ctx.stayMatch(D(base, { input_ver: "7a75c6d2" }))); assert.strictEqual(ctx.stayBreakfast("2026-10-11", D(base, { input_ver: "7a75c6d2" })), null);
  assert.ok(!ctx.stayMatch(D(base, { model_ver: "deadbeef" })));
});
