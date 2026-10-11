"""Deterministic repairs for known structural bugs in a Freya workflow. No model, no network.

    python3 builder/autofix.py <workflow.json> [out.json]

fix(workflow) -> (workflow, [change descriptions]). Idempotent. Accepts a bare workflow or {"workflow": {...}}.
What it repairs (each one was seen in a real call transcript):
  1. A global intent node must not fire while a code/api/end node runs: add every non-conversation node
     to its excluded_nodes (otherwise one customer sentence is counted twice by a counter node).
  2. An extraction variable with a fixed list of values rejects any other value written by code (for example '').
     Add the neutral value 'none' to the list and write 'none' instead.
  4. The tool that runs at the end of the call gets maxRetries 2 (a failed close wrote nothing; the tool API says it may be repeated).
  3. A tool that runs at the end of the call is filled in by the model, which writes free text into `reason`.
     Give it pre_process_code that sets its body fields from the code variables (see lib/snippets.close_pre_process).
"""
import copy, json, pathlib, re, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "lib"))
import snippets

NEUTRAL = "none"
WRITE = re.compile(r"(vars\[['\"](\w+)['\"]\]\s*=\s*)(['\"])(.*?)\3")


def unwrap(d):
    return (d["workflow"], True) if isinstance(d.get("workflow"), dict) and "nodes" in d["workflow"] else (d, False)


def _code_slots(node):
    """Yield (action dict, parameters.properties.code dict) for every code_exec in a node's pre_actions."""
    for a in node.get("pre_actions") or []:
        fn = a.get("function") or {}
        if fn.get("name") == "code_exec":
            c = (((fn.get("parameters") or {}).get("properties") or {}).get("code"))
            if isinstance(c, dict) and isinstance(c.get("default"), str): yield c


def fix(d):
    wf, wrapped = unwrap(copy.deepcopy(d)); changes = []
    nodes = wf.get("nodes") or {}
    # 1. global intent nodes
    non_conv = sorted(k for k, n in nodes.items() if n.get("node_type") != "conversation")
    for gname, g in (wf.get("global_nodes") or {}).items():
        if (g.get("condition") or {}).get("operator") != "matches_intent": continue
        excl = list(g.get("excluded_nodes") or []); add = [k for k in non_conv if k not in excl]
        if add:
            g["excluded_nodes"] = excl + add; changes.append(f"global {gname}: excluded {len(add)} non-conversation nodes")
    # 2. enum-valued extraction variables
    enums = {}
    for n in nodes.values():
        for e in n.get("extraction_schema") or []:
            if e.get("enum_values"): enums.setdefault(e["name"], []).append(e)
    for name, es in enums.items():
        for e in es:
            if NEUTRAL not in e["enum_values"]:
                e["enum_values"] = list(e["enum_values"]) + [NEUTRAL]
                e["description"] = (e.get("description") or "").rstrip() + f" {NEUTRAL}: nothing relevant to this question was said."
                changes.append(f"extraction {name}: added value '{NEUTRAL}'")
    allowed = {k: set(v for e in es for v in e["enum_values"]) for k, es in enums.items()}
    scopes = list(nodes.items()) + list((wf.get("global_nodes") or {}).items())
    for nname, n in scopes:
        for c in _code_slots(n):
            def rep(m):
                var, val = m.group(2), m.group(4)
                if var in allowed and val not in allowed[var]:
                    changes.append(f"{nname}: vars['{var}'] = '{val}' -> '{NEUTRAL}'")
                    return m.group(1) + m.group(3) + NEUTRAL + m.group(3)
                return m.group(0)
            c["default"] = WRITE.sub(rep, c["default"])
    # 3. closing tool
    for t in wf.get("tools") or []:
        fn = t.get("function") or {}
        if not (t.get("config") or {}).get("alwaysRunsAt") or not str(fn.get("handler", "")).endswith("api_call"): continue
        body = ((((fn.get("parameters") or {}).get("properties") or {}).get("body") or {}).get("properties")) or {}
        names = {}
        for f in ("outcome", "reason", "customer_id"):
            m = re.fullmatch(r"\{\{\s*([\w.]+)\s*\}\}", str((body.get(f) or {}).get("default") or ""))
            if m: names[f] = m.group(1)
        if len(names) == 3 and "b['outcome'] =" not in (t.get("pre_process_code") or ""):
            t["pre_process_code"] = snippets.close_pre_process(outcome_var=names["outcome"], reason_var=names["reason"], customer_var=names["customer_id"])
            changes.append(f"{fn.get('name')}: pre_process_code sets outcome, reason, customer_id from the variables {sorted(names.values())}")
    for t in wf.get("tools") or []:
        if (t.get("config") or {}).get("alwaysRunsAt") and str((t.get("function") or {}).get("handler", "")).endswith("api_call") \
                and int((t.get("config") or {}).get("maxRetries") or 0) < 2:
            t.setdefault("config", {})["maxRetries"] = 2; changes.append(f"{(t.get('function') or {}).get('name')}: maxRetries 2 (a failed close is safe to repeat)")
    return ({**d, "workflow": wf} if wrapped else wf), changes


if __name__ == "__main__":
    if len(sys.argv) < 2: print(__doc__); sys.exit(2)
    d = json.load(open(sys.argv[1])); out, ch = fix(d)
    for c in ch: print("FIX", c)
    print(f"RESULT: {len(ch)} change(s)")
    if len(sys.argv) > 2: json.dump(out, open(sys.argv[2], "w"), indent=1)
