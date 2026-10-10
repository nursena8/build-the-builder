"""Static checks for a Freya workflow file. No network, standard library only.

    python3 builder/validate.py <workflow.json> <openapi.json>

Prints one line per finding ("ERROR ..." or "WARN ...") and a last line "RESULT: PASS" or "RESULT: FAIL".
Exit code 0 on PASS, 1 on FAIL. Accepts a bare workflow or a freya.export_workflow file ({"workflow": {...}}).
"""
import json, re, sys, collections


def load(path):
    d = json.load(open(path))
    return d["workflow"] if isinstance(d.get("workflow"), dict) and "nodes" in d["workflow"] else d


def tool_defs(wf):
    """Yield (where, tool) for every tool object in the workflow."""
    for t in wf.get("tools") or []:
        yield "workflow.tools", t
    for name, n in (wf.get("nodes") or {}).items():
        for t in n.get("tools") or []:
            yield f"{name}.tools", t
        for t in n.get("pre_actions") or []:
            yield f"{name}.pre_actions", t


def walk_conditions(c):
    if isinstance(c, dict):
        yield c
        for v in c.values():
            yield from walk_conditions(v)
    elif isinstance(c, list):
        for v in c:
            yield from walk_conditions(v)


def openapi_ops(path):
    o = json.load(open(path))
    base = ((o.get("servers") or [{}])[0].get("url") or "").rstrip("/")
    ops = {}
    for p, v in (o.get("paths") or {}).items():
        post = v.get("post") or {}
        schema = (((post.get("requestBody") or {}).get("content") or {}).get("application/json") or {}).get("schema") or {}
        ops[base + p] = {"name": p.strip("/"), "props": schema.get("properties") or {}, "required": schema.get("required") or []}
    return ops


def check(wf, ops):
    out = []
    err = lambda m: out.append("ERROR " + m)
    warn = lambda m: out.append("WARN " + m)
    nodes = wf.get("nodes") or {}
    if not nodes: err("no nodes"); return out
    init = wf.get("initial_node")
    if init not in nodes: err(f"initial_node {init!r} is not a node")

    for name, n in nodes.items():
        nt = n.get("node_type")
        if nt != "conversation" and n.get("tools"):
            err(f"{name}: tools on a {nt} node (tools only work on conversation nodes; use pre_actions)")
        if n.get("passthrough"):
            has_always = bool(n.get("passthrough_default_transition")) or any(
                c.get("operator") == "always" for t in n.get("transitions") or [] for c in walk_conditions(t.get("condition")))
            if not has_always: err(f"{name}: passthrough node without an 'always' transition")
        for t in n.get("transitions") or []:
            if t.get("target_node") not in nodes: err(f"{name}: transition to unknown node {t.get('target_node')!r}")
            for c in walk_conditions(t.get("condition")):
                if isinstance(c.get("operand"), bool): err(f"{name}: boolean operand in a condition (write the string \"true\" and \"True\")")
        if nt == "conversation" and not n.get("transitions") and not n.get("terminal"):
            warn(f"{name}: conversation node without transitions")

    # code snippets
    for where, t in tool_defs(wf):
        fn = (t.get("function") or {})
        if fn.get("name") == "code_exec":
            code = (((fn.get("parameters") or {}).get("properties") or {}).get("code") or {}).get("default")
            if not isinstance(code, str): err(f"{where}: code_exec without a code default"); continue
            if "{{" in code: err(f"{where}: '{{{{' inside code (templates are not resolved in code)")
            try: compile(code, where, "exec")
            except SyntaxError as e: err(f"{where}: code does not compile: {e}")

    # reachability
    rev = collections.defaultdict(set); fwd = collections.defaultdict(set)
    for name, n in nodes.items():
        for t in n.get("transitions") or []:
            if t.get("target_node") in nodes: fwd[name].add(t["target_node"]); rev[t["target_node"]].add(name)
        d = n.get("passthrough_default_transition")
        if isinstance(d, str) and d in nodes: fwd[name].add(d); rev[d].add(name)
    ends = [k for k, n in nodes.items() if n.get("node_type") == "end_call"]
    if not ends: err("no end_call node")
    seen = set(ends); stack = list(ends)
    while stack:
        for p in rev[stack.pop()]:
            if p not in seen: seen.add(p); stack.append(p)
    reach = set(); stack = [init] if init in nodes else []
    while stack:
        x = stack.pop()
        if x in reach: continue
        reach.add(x); stack.extend(fwd[x])
    for k in nodes:
        if k in reach and k not in seen: err(f"{k}: no path to an end_call node")
        if k not in reach: warn(f"{k}: unreachable from initial_node")

    # tools against the openapi
    names_used = set()
    for where, t in tool_defs(wf):
        fn = t.get("function") or {}
        if not str(fn.get("handler", "")).endswith("api_call"): continue
        props = (fn.get("parameters") or {}).get("properties") or {}
        url = (props.get("url") or {}).get("default")
        op = ops.get(url)
        if op is None: err(f"{where}: {fn.get('name')}: url {url!r} is not in the tool API"); continue
        names_used.add(op["name"])
        if fn.get("name") != op["name"]: warn(f"{where}: tool name {fn.get('name')!r} differs from the API operation {op['name']!r}")
        body = ((props.get("body") or {}).get("properties")) or {}
        for k, v in body.items():
            if k not in op["props"]: err(f"{where}: {fn.get('name')}: field {k!r} is not in the API"); continue
            allowed = op["props"][k].get("enum")
            if allowed and isinstance(v.get("enum"), list):
                bad = [x for x in v["enum"] if x not in allowed]
                if bad: err(f"{where}: {fn.get('name')}.{k}: values {bad} are not allowed by the API {allowed}")
        for k in op["required"]:
            if k not in body: warn(f"{where}: {fn.get('name')}: required API field {k!r} is not in the body schema")
    return out


def main(argv):
    if len(argv) != 3: print(__doc__); return 2
    lines = check(load(argv[1]), openapi_ops(argv[2]))
    for l in lines: print(l)
    bad = any(l.startswith("ERROR") for l in lines)
    print("RESULT: " + ("FAIL" if bad else "PASS"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
