# 20:00-23:00 playbook (Istanbul). Deadline 23:00; email submission.json by 22:00.

The page shows two forms (checked 2026-10-11): (a) `python3 builder/build.py briefs/hidden-1.md briefs/hidden-1.openapi.json` with two workflows and two traces (hidden-1, hidden-2); (b) a Turkish case folder + mock URL: `python3 builder/build.py {case_folder} {mock_url}`. build.py runs both. Use whatever the Submit tab says at 20:00.

## Before 20:00 (done by the user)
- Everything committed and pushed; `git status` clean; remember the commit hash. Builder code frozen from here.
- `source .venv/bin/activate && source env.sh` in the terminal you will use. `pip install -r builder/requirements.txt` done.
- Cloudflare account + `wrangler login` ready IF the mock has to be deployed by us (ask support / read the Submit tab).
- Support answers: does the zip contain an OpenAPI file or only a service contract? Is the mock ours to deploy?

## At 20:00
1. Download the zip, unzip to a folder OUTSIDE the repo or into an ignored path (do not commit the case files).
2. Deploy / get the mock; note `mock_url`. Check it answers (curl its root or a tool path once).
3. From the clean tree at the pushed commit:
   `python3 builder/build.py <case_folder> <mock_url> 2>&1 | tee traces/<case>.log`
4. Read the trace (also: the number of `codecheck PASS` lines; a build with fewer than ~30 scenarios was rushed: rerun): every input file `converted`/`text` (or `pdf`), no `converted failed`, `validate RESULT: PASS`, `codecheck RESULT: PASS`, no `remaining_error`, `saved_agent` and `exported` lines present.
5. Run the Turkish check on the new agent (simulation with Turkish customers; the test customers from the zip must be in your mock):
   `python3 tools/run_cases.py <agent_id> --brief A --lang tr` only fits the practice cases; for the final case use the zip's test customers.
6. If the run is bad (crash, FAIL, empty spec): a crash in docconv/build.py may be fixed (README allows parser fixes, no case content), commit, rerun. Each run is a fresh sample; about three fit. Stop at the first good run (earlier submission and shorter build time break ties).
7. Fill `dev/submission.draft.json` -> `submission.json` (team, members, repo, commit, run_command, workflow, trace, mock_url). Commit the export and trace; the builder code must be identical to the run's commit. Email by 22:00.

## Never
- Do not write anything from the final case into builder code, skill, or lib.
- Do not edit the exported agent by hand after the run.
