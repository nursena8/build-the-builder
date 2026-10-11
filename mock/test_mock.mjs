// node mock/test_mock.mjs : runs the worker against a fake Durable Object (in memory)
import worker, { Bank } from "./worker.mjs";
const store = new Map();
const state = { storage: { get: async (k) => store.get(k), put: async (k, v) => { store.set(k, JSON.parse(JSON.stringify(v))); } } };
const bank = new Bank(state, {});
const env = { BANK: { idFromName: () => "x", get: () => ({ fetch: (r) => bank.fetch(r) }) } };
const call = async (path, body, method = "POST", headers = {}) => {
  const r = await worker.fetch(new Request("https://m.example/v1/" + path, { method, headers: { "content-type": "application/json", ...headers }, body: method === "POST" ? JSON.stringify(body) : undefined }), env);
  return { status: r.status, body: await r.json() };
};
let bad = 0;
const eq = (label, got, want) => { const ok = JSON.stringify(got) === JSON.stringify(want); if (!ok) bad++; console.log(ok ? "PASS" : "FAIL", label, ok ? "" : JSON.stringify(got) + " != " + JSON.stringify(want)); };

const id = "c_demo_2";
eq("account needs identity", (await call("get_account", { customer_id: id })).body, { ok: false, error: "identity not verified" });
eq("bad field", (await call("verify_identity", { customer_id: id, field: "x", answer: "1" })).body.ok, false);
eq("unreadable date not counted", (await call("verify_identity", { customer_id: id, field: "date_of_birth", answer: "23 Feb" })).body.ok, false);
eq("wrong answer counts", (await call("verify_identity", { customer_id: id, field: "date_of_birth", answer: "1990-01-01" })).body, { ok: true, verified: false, wrong_answers_left: 2, all_verified: false });
eq("right dob", (await call("verify_identity", { customer_id: id, field: "date_of_birth", answer: "1989-02-23" })).body, { ok: true, verified: true, wrong_answers_left: 2, all_verified: false });
eq("right phone", (await call("verify_identity", { customer_id: id, field: "phone_last4", answer: "9904" })).body, { ok: true, verified: true, wrong_answers_left: 2, all_verified: true });
eq("account", (await call("get_account", { customer_id: id })).body.products.length, 1);
const f = await call("create_promise", { customer_id: id, product_id: "p1", amount: 365, date: "2026-10-16" });
eq("fault: first promise 500", [f.status, f.body.ok], [500, false]);
eq("second promise ok", (await call("create_promise", { customer_id: id, product_id: "p1", amount: 365, date: "2026-10-16" })).body, { ok: true, promise_id: "pr1" });
eq("one per product", (await call("create_promise", { customer_id: id, product_id: "p1", amount: 100, date: "2026-10-16" })).body.ok, false);
eq("unknown product", (await call("create_promise", { customer_id: id, product_id: "p9", amount: 1, date: "2026-10-16" })).body.error, "unknown product_id");
eq("close wrong reason", (await call("close_call", { customer_id: id, outcome: "not_verified", reason: "customer refused" })).body.error, "this outcome needs one of these reasons: failed, declined");
eq("close promise", (await call("close_call", { customer_id: id, outcome: "promise" })).body, { ok: true });
eq("nothing after close", (await call("add_note", { customer_id: id, product_id: "p1", reason: "refused" })).body.ok, false);
const led = (await call("ledger/" + id, null, "GET")).body;
eq("ledger", [led.outcome, led.promises.length, led.closed], ["promise", 1, true]);
eq("reset forbidden", (await call("admin/reset", { customer_id: id })).status, 403);
eq("reset", (await call("admin/reset", { customer_id: id }, "POST", { "x-admin-key": "change-me" })).body, { ok: true });
eq("fresh again", (await call("ledger/" + id, null, "GET")).body.closed, false);
// lock after three wrong
const id1 = "c_demo_1";
for (let i = 0; i < 3; i++) await call("verify_identity", { customer_id: id1, field: "phone_last4", answer: "0000" });
eq("locked after 3 wrong", (await call("verify_identity", { customer_id: id1, field: "phone_last4", answer: "2219" })).body.wrong_answers_left, 0);
console.log(bad ? bad + " FAILED" : "ALL PASS"); process.exit(bad ? 1 : 0);
