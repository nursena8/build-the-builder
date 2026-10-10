"""Run the code nodes of a workflow offline, on made-up call variables, and compare the result with what the brief says.

    python3 builder/codecheck.py <workflow.json> <scenarios.json>

scenarios.json is a list of objects:
  {"name": "late band, 14 days",
   "run": ["prepare", "account_facts"],              # code nodes to run in this order; vars carry over
   "vars": {"now": "2026-10-14T11:00", "...": "..."},  # starting variables (what the platform would supply)
   "expect": {"deadline": "2026-10-23",               # exact string/number match
              "facts": {"contains": "late band"},     # substring match
              "outcome": {"not_empty": true}}}
The author of the scenarios computes the expected values by hand from the brief, not by reading the code under test.
Prints PASS/FAIL per scenario and "RESULT: PASS" or "RESULT: FAIL". Exit code 0 only if every scenario passes.
"""
import json, sys, traceback


def load(path):
    d = json.load(open(path))
    return d["workflow"] if isinstance(d.get("workflow"), dict) and "nodes" in d["workflow"] else d


def node_codes(wf, name):
    n = (wf.get("nodes") or {}).get(name)
    if n is None: raise KeyError("no node " + name)
    codes = []
    for t in n.get("pre_actions") or []:
        fn = t.get("function") or {}
        if fn.get("name") == "code_exec":
            codes.append((((fn.get("parameters") or {}).get("properties") or {}).get("code") or {}).get("default") or "")
    return codes


def run_scenario(wf, sc):
    vars_ = dict(sc.get("vars") or {})
    for node in sc.get("run") or []:
        for code in node_codes(wf, node):
            exec(compile(code, node, "exec"), {"vars": vars_})
    bad = []
    for k, want in (sc.get("expect") or {}).items():
        got = vars_.get(k)
        if isinstance(want, dict):
            if "contains" in want and want["contains"] not in str(got): bad.append(f"{k}: {want['contains']!r} not in {str(got)[:120]!r}")
            if want.get("not_empty") and not got: bad.append(f"{k}: empty")
        elif str(got) != str(want): bad.append(f"{k}: expected {want!r}, got {got!r}")
    return bad


def main(argv):
    if len(argv) != 3: print(__doc__); return 2
    wf = load(argv[1]); scs = json.load(open(argv[2])); failed = 0
    for sc in scs:
        try: bad = run_scenario(wf, sc)
        except Exception: bad = ["exception: " + traceback.format_exc(limit=1).strip().splitlines()[-1]]
        print(("PASS " if not bad else "FAIL ") + sc.get("name", "?") + ("" if not bad else " | " + "; ".join(bad)))
        failed += bool(bad)
    print("RESULT: " + ("FAIL" if failed else "PASS"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
