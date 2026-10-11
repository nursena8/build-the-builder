# Mock of the bank's services (Cloudflare Workers)

The final case needs OUR mock of the bank's services: the organizers' simulated customers talk to our agent, its tools call this mock.
Template data-driven by two files; everything else stays as it is.

1. `config.mjs`: identity fields, wrong-answer limit, outcome -> reasons table, note reasons, queues. Copy them from the service contract.
2. `customers.mjs`: the test customers from the zip (customer_id, identity answers, products; `faults` make a tool answer 500 first).
3. `node mock/test_mock.mjs` must print ALL PASS (local, no network).
4. Deploy (needs a Cloudflare login once: `npx wrangler login`):  `cd mock && npx wrangler deploy`  -> prints https://<name>.<subdomain>.workers.dev
   Without a login: `npx wrangler deploy --temporary` deploys to a temporary preview account (may expire: not for the final).
5. Check: `curl -s -X POST <url>/v1/verify_identity -H 'content-type: application/json' -d '{"customer_id":"<id>","field":"phone_last4","answer":"0000"}'`.
   Ledger of a customer: `GET <url>/v1/ledger/<customer_id>`. Reset one: `POST <url>/v1/admin/reset` with header `x-admin-key` (config.mjs).
Keep it deployed until the results are out. Paths are `/v1/<tool name>`; change `worker.mjs` routes if the service contract differs.
