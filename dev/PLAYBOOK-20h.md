# 20:00-23:00 playbook (Istanbul). Final closes 23:00 (20:00 UTC); email submission.json by 22:30.

Page (Submit tab, seen 2026-10-11): ONE case, "Card statement debt", in Turkish. Steps: (1) download the zip at 20:00, read BRIEF.md first, README.md says what each
document is; (2) WRITE OUR MOCK of the bank's services on Cloudflare Workers from the service contract and the test customers, deploy it BEFORE running the builder, keep it
running until results are out; (3) run `python3 builder/build.py <case_folder> <mock_url> 2>&1 | tee traces/<case>.log`, may run more than once, submit ONE run's agent + trace,
do not edit it after the run; (4) export with freya.export_workflow, commit the file with the trace; (5) email submission.json (team, members, repo, commit, run_command,
workflow, trace, mock_url) before 20:00 UTC. The trace is read, not scored. After the case opens: fix bugs only, never write case content into the builder.

## Before 20:00 (done)
- Repo https://github.com/nursena8/build-the-builder is public; builder code committed and pushed.
- Mock template in mock/ (worker.mjs, config.mjs, customers.mjs, wrangler.toml); `node mock/test_mock.mjs` = ALL PASS.
- Cloudflare login: `npx wrangler login` (user).

## 20:00 - 20:40 mock
1. Unzip OUTSIDE the repo (do not commit case files). Read BRIEF.md, README.md, the service contract and the test customers.
2. Edit mock/config.mjs (identity fields, outcome/reason table, queues, note reasons) and mock/customers.mjs (test customers) from the documents; adjust worker.mjs routes/fields if the
   contract differs (paths, field names, error texts). `node mock/test_mock.mjs` adapted until ALL PASS.
3. `cd mock && npx wrangler deploy` -> mock_url. curl it once per tool.
## 20:40 - 22:15 builder runs
4. From a clean tree at the pushed commit: `python3 builder/build.py <case_folder> <mock_url> 2>&1 | tee traces/<case>.log`.
5. Read the trace: all inputs converted, `rulecheck_final PASS`, `chat_probe ok`, validate PASS, >=30 `codecheck PASS`, no `remaining_error`. If not, rerun (builds vary).
6. Talk to the agent against the mock: the test customers via simulation (personas in Turkish) if time allows; check the mock's ledger for the outcome.
7. Stop at the first good run. Export is in submission/<case>.workflow.json; commit it with the trace (builder code unchanged), push.
## 22:15 - 22:30
8. Fill submission.json (commit hash = the commit with the export and trace, builder code identical to the run's), email it. Keep the mock deployed.

## Never
- Do not write anything from the final case into builder code, skill or lib. Do not edit the exported agent by hand after the run.
