// A mock of the bank's services for a Freya phone agent, on Cloudflare Workers. All state lives in one Durable Object, so every
// request sees the same ledger. Routes (under /v1): verify_identity, get_account, create_promise, add_note, schedule_callback,
// transfer_to_agent, close_call (POST, JSON), GET /ledger/<customer_id>, POST /admin/reset {customer_id} with header x-admin-key.
import { CONFIG } from "./config.mjs";
import { CUSTOMERS } from "./customers.mjs";

const json = (obj, status = 200) => new Response(JSON.stringify(obj), { status, headers: { "content-type": "application/json" } });
const fresh = (c) => ({ customer_id: c.customer_id, wrong: 0, verified: {}, closed: false, outcome: null, reason: null,
                         promises: [], notes: [], callbacks: [], transfers: [], calls: [], failCounts: {} });

export class Bank {
  constructor(state, env) { this.state = state; this.env = env; this.data = null; }
  async load() {
    if (this.data) return;
    this.data = (await this.state.storage.get("data")) || {};
    for (const c of CUSTOMERS) if (!this.data[c.customer_id]) this.data[c.customer_id] = fresh(c);
  }
  async save() { await this.state.storage.put("data", this.data); }

  async fetch(request) {
    await this.load();
    const url = new URL(request.url);
    const path = url.pathname.replace(/^\/v1/, "");
    if (request.method === "GET" && path.startsWith("/ledger/")) {
      const rec = this.data[decodeURIComponent(path.slice(8))];
      return rec ? json(rec) : json({ ok: false, error: "unknown customer" }, 404);
    }
    if (request.method === "POST" && path === "/admin/reset") {
      if (request.headers.get("x-admin-key") !== CONFIG.adminKey) return json({ ok: false, error: "forbidden" }, 403);
      const b = await request.json().catch(() => ({}));
      const c = CUSTOMERS.find((x) => x.customer_id === b.customer_id);
      if (!c) return json({ ok: false, error: "unknown customer" }, 404);
      this.data[c.customer_id] = fresh(c); await this.save(); return json({ ok: true });
    }
    if (request.method !== "POST") return json({ ok: false, error: "not found" }, 404);
    const tool = path.slice(1);
    const handler = this.tools[tool];
    if (!handler) return json({ ok: false, error: "not found" }, 404);
    const body = await request.json().catch(() => null);
    if (!body || typeof body !== "object") return json({ ok: false, error: "body must be JSON" });
    const cust = CUSTOMERS.find((x) => x.customer_id === body.customer_id);
    const rec = this.data[body.customer_id];
    if (!cust || !rec) return json({ ok: false, error: "unknown customer" });
    // an injected fault: the first n calls of this tool answer 500 and record nothing
    const fault = (cust.faults || []).find((f) => f.tool === tool);
    if (fault && (rec.failCounts[tool] || 0) < fault.fail_first_n) {
      rec.failCounts[tool] = (rec.failCounts[tool] || 0) + 1; await this.save();
      return json({ ok: false, error: "service unavailable, nothing was recorded" }, 500);
    }
    if (rec.closed) { const r = { ok: false, error: "the call is closed; nothing is accepted after close_call" }; return json(r); }
    const res = handler.call(this, cust, rec, body);
    rec.calls.push({ tool, args: body, result: res, at: Date.now() });
    await this.save();
    return json(res);
  }

  get tools() {
    const verifiedAll = (cust, rec) => CONFIG.identityFields.every((f) => rec.verified[f]);
    const need = (cust, rec) => (verifiedAll(cust, rec) ? null : { ok: false, error: "identity not verified" });
    const productOf = (cust, id) => cust.products.find((p) => p.product_id === id);
    return {
      verify_identity(cust, rec, b) {
        if (!CONFIG.identityFields.includes(b.field)) return { ok: false, error: "field must be " + CONFIG.identityFields.join(" or ") };
        if (rec.wrong >= CONFIG.maxWrong) return { ok: true, verified: false, wrong_answers_left: 0, all_verified: false };
        let ans = String(b.answer ?? "").trim();
        if (b.field === "date_of_birth" && !/^\d{4}-\d{2}-\d{2}$/.test(ans)) return { ok: false, error: "date_of_birth must be YYYY-MM-DD" };   // not counted
        if (b.field === "phone_last4" && !/^\d{4}$/.test(ans)) return { ok: false, error: "phone_last4 must be four digits" };
        const good = ans === String(cust.identity[b.field]);
        if (good) rec.verified[b.field] = true; else rec.wrong += 1;
        return { ok: true, verified: good, wrong_answers_left: Math.max(0, CONFIG.maxWrong - rec.wrong), all_verified: verifiedAll(cust, rec) };
      },
      get_account(cust, rec) { return need(cust, rec) || { ok: true, products: cust.products }; },
      create_promise(cust, rec, b) {
        const n = need(cust, rec); if (n) return n;
        const p = productOf(cust, b.product_id); if (!p) return { ok: false, error: "unknown product_id" };
        if (typeof b.amount !== "number" || !(b.amount > 0)) return { ok: false, error: "amount must be a positive number" };
        if (!/^\d{4}-\d{2}-\d{2}$/.test(String(b.date ?? ""))) return { ok: false, error: "date must be YYYY-MM-DD" };
        if (rec.promises.some((x) => x.product_id === b.product_id)) return { ok: false, error: "a promise is already recorded for this product" };
        const promise = { promise_id: "pr" + (rec.promises.length + 1), product_id: b.product_id, amount: b.amount, date: b.date };
        rec.promises.push(promise); return { ok: true, promise_id: promise.promise_id };
      },
      add_note(cust, rec, b) {
        const n = need(cust, rec); if (n) return n;
        if (!productOf(cust, b.product_id)) return { ok: false, error: "unknown product_id" };
        if (!CONFIG.noteReasons.includes(b.reason)) return { ok: false, error: "reason must be one of " + CONFIG.noteReasons.join(", ") };
        rec.notes.push({ product_id: b.product_id, reason: b.reason, text: b.text ?? null }); return { ok: true };
      },
      schedule_callback(cust, rec, b) {
        if (!/^\d{4}-\d{2}-\d{2}$/.test(String(b.date ?? "")) || !/^\d{2}:\d{2}$/.test(String(b.time ?? ""))) return { ok: false, error: "date must be YYYY-MM-DD and time HH:MM" };
        rec.callbacks.push({ date: b.date, time: b.time }); return { ok: true };
      },
      transfer_to_agent(cust, rec, b) {
        if (!CONFIG.queues.includes(b.queue)) return { ok: false, error: "queue must be one of " + CONFIG.queues.join(", ") };
        rec.transfers.push({ queue: b.queue }); return { ok: true };
      },
      close_call(cust, rec, b) {
        const allowed = CONFIG.outcomeReasons[b.outcome];
        if (allowed === undefined) return { ok: false, error: "outcome must be one of " + Object.keys(CONFIG.outcomeReasons).join(", ") };
        if (Array.isArray(allowed)) {
          if (allowed.length && !allowed.includes(b.reason)) return { ok: false, error: "this outcome needs one of these reasons: " + allowed.join(", ") };
          if (!allowed.length && b.reason) return { ok: false, error: "this outcome takes no reason" };
        }
        rec.closed = true; rec.outcome = b.outcome; rec.reason = b.reason ?? null; return { ok: true };
      },
    };
  }
}

export default {
  async fetch(request, env) {
    const stub = env.BANK.get(env.BANK.idFromName("bank"));
    return stub.fetch(request);
  },
};
