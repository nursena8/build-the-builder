"""Write submission.json for the final run.

    python3 dev/make_submission.py --team "<team>" --member "Name <email>" [--member ...] --mock-url https://... --workflow submission/<case>.workflow.json --trace traces/final.log

Fills repo (from `git remote get-url origin`), commit (from `git rev-parse --short HEAD`) and the run command. Check that the commit contains the export and the trace
(`git status` clean) before you send the file. Prints the JSON; writes ./submission.json (not committed by default: send it by e-mail)."""
import argparse, json, pathlib, re, subprocess, sys

ap = argparse.ArgumentParser()
ap.add_argument("--team", required=True); ap.add_argument("--member", action="append", required=True, help='"Name <email>"')
ap.add_argument("--mock-url", required=True); ap.add_argument("--workflow", required=True); ap.add_argument("--trace", required=True)
ap.add_argument("--run-command", default="python3 builder/build.py {case_folder} {mock_url}")
a = ap.parse_args()
sh = lambda *c: subprocess.run(c, capture_output=True, text=True).stdout.strip()
members = []
for m in a.member:
    mm = re.match(r"\s*(.*?)\s*<(.+?)>\s*$", m)
    members.append({"name": mm.group(1), "email": mm.group(2)} if mm else {"name": m, "email": ""})
repo = re.sub(r"\.git$", "", sh("git", "remote", "get-url", "origin"))
out = {"team": a.team, "members": members, "repo": repo, "commit": sh("git", "rev-parse", "--short", "HEAD"), "run_command": a.run_command,
       "workflow": a.workflow, "trace": a.trace, "mock_url": a.mock_url}
problems = []
for k in ("workflow", "trace"):
    if not pathlib.Path(out[k]).is_file(): problems.append(f"{k} file {out[k]} does not exist")
if sh("git", "status", "--porcelain"): problems.append("working tree not clean: commit the export and the trace, then rerun this script so the hash is right")
if sh("git", "ls-files", out["workflow"]) == "": problems.append("the workflow export is not committed")
if sh("git", "ls-files", out["trace"]) == "": problems.append("the trace is not committed")
if sh("git", "log", "origin/main..HEAD", "--oneline"): problems.append("commits not pushed to origin")
pathlib.Path("submission.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
print(json.dumps(out, indent=2, ensure_ascii=False))
for p in problems: print("PROBLEM:", p, file=sys.stderr)
sys.exit(1 if problems else 0)
