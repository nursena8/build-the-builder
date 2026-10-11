"""Static checks for a Freya workflow file. No network, standard library only.

    python3 builder/validate.py <workflow.json> <openapi.json>

Prints one line per finding ("ERROR ..." or "WARN ...") and a last line "RESULT: PASS" or "RESULT: FAIL".
Exit code 0 on PASS, 1 on FAIL. Accepts a bare workflow or a freya.export_workflow file ({"workflow": {...}}).
"""
import json, os, re, sys, collections, urllib.parse


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
    if path in (None, "-"): return {}
    o = json.load(open(path))
    base = ((o.get("servers") or [{}])[0].get("url") or "").rstrip("/")
    ops = {}
    for p, v in (o.get("paths") or {}).items():
        post = v.get("post") or {}
        schema = (((post.get("requestBody") or {}).get("content") or {}).get("application/json") or {}).get("schema") or {}
        resp = ((((post.get("responses") or {}).get("200") or {}).get("content") or {}).get("application/json") or {}).get("schema") or {}
        ops[base + p] = {"name": p.strip("/"), "props": schema.get("properties") or {}, "required": schema.get("required") or [], "resp": resp}
    return ops


def resolve_resp(path, node, ops):
    """The OpenAPI type ('array', 'object', 'string' ...) a response_mapping path ends on, or None when unknown."""
    url = None
    for a in node.get("pre_actions") or []:
        fn = a.get("function") or {}
        url = (((fn.get("parameters") or {}).get("properties") or {}).get("url") or {}).get("default") or url
    op = ops.get(url)
    if not op or not path: return None
    cur = op["resp"]
    for part in str(path).split(".")[1:] if str(path).startswith("data") else str(path).split("."):
        if part.isdigit():
            cur = cur.get("items") or {}
        else:
            cur = (cur.get("properties") or {}).get(part)
            if cur is None: return None
    return cur.get("type")


def check(wf, ops):
    out = []
    err = lambda m: out.append("ERROR " + m)
    warn = lambda m: out.append("WARN " + m)
    nodes = wf.get("nodes") or {}
    if not nodes: err("no nodes"); return out
    init = wf.get("initial_node")
    if init not in nodes: err(f"initial_node {init!r} is not a node")

    # a list mapping is fine when some code rebuilds the items from the flattened '<name>.<i>.<field>' variables
    list_reader = False
    for _w, _t in tool_defs(wf):
        _c = ((((_t.get("function") or {}).get("parameters") or {}).get("properties") or {}).get("code") or {}).get("default") or ""
        if "items_from_vars" in _c or "items_from_keys" in _c or re.search(r"\\\\\.\(\\\\d\+\)\\\\\.", _c) or "(\\d+)\\." in _c: list_reader = True
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
        for rm in n.get("response_mapping") or []:
            hit = resolve_resp(rm.get("path"), n, ops)
            if hit in ("array", "object") and not list_reader:
                err(f"{name}: response_mapping {rm.get('path')!r} points at a {hit}; the platform stores only single values, as flattened paths such as 'data.products.0.past_due'. Map each field you need for item 0, 1, 2 ... separately")
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

    # an extraction variable with a fixed list of values rejects any other value written by code (for example '')
    enums = {}
    for name, n in nodes.items():
        for e in n.get("extraction_schema") or []:
            if e.get("enum_values"): enums.setdefault(e.get("name"), set()).update(e["enum_values"])
    if enums:
        scopes = list(nodes.items()) + list((wf.get("global_nodes") or {}).items())
        for name, n in scopes:
            for t in n.get("pre_actions") or []:
                code = ((((t.get("function") or {}).get("parameters") or {}).get("properties") or {}).get("code") or {}).get("default") or ""
                for m in re.finditer(r"vars\[['\"](\w+)['\"]\]\s*=\s*(['\"])(.*?)\2", code):
                    if m.group(1) in enums and m.group(3) not in enums[m.group(1)]:
                        err(f"{name}: code writes {m.group(3)!r} to extraction variable {m.group(1)!r}; it accepts only {sorted(enums[m.group(1)])}. Add a neutral value such as 'none' to the enum and reset to that")

    # a global (intent) node is checked after every transition, so it also fires while a code node runs and then
    # re-enters the previous node, re-running its counters
    for gname, g in (wf.get("global_nodes") or {}).items():
        cond = g.get("condition") or {}
        if cond.get("operator") != "matches_intent": continue
        excl = set(g.get("excluded_nodes") or [])
        loose = sorted(k for k, n in nodes.items() if n.get("node_type") != "conversation" and k not in excl)
        if loose:
            err(f"global node {gname}: not excluded from {len(loose)} non-conversation nodes (e.g. {', '.join(loose[:4])}); one customer sentence can fire it while a counting node runs and the counter runs twice")

    # the extraction model does not know the call's date: a field that asks it for a calendar date resolves "tomorrow" from the real clock
    for name, n in nodes.items():
        for e in n.get("extraction_schema") or []:
            desc = str(e.get("description") or "")
            if e.get("type") == "date" or re.search(r"YYYY-MM-DD|ISO[ -]?8601|calendar date", desc, re.I):
                if not e.get("enum_values") and re.search(r"date|day", str(e.get("name")), re.I):
                    err(f"{name}: extraction field {e.get('name')!r} asks the model for a calendar date; extract the customer's words as text and resolve them in code from now (lib/cal.py resolve_phrase)")

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

    # a tool that runs at the end of the call is filled in by the model: free text in `reason` is rejected by the bank
    # and the call never closes. Its fields must be overwritten from code variables in pre_process_code.
    for where, t in tool_defs(wf):
        fn = t.get("function") or {}
        if not str(fn.get("handler", "")).endswith("api_call") or not (t.get("config") or {}).get("alwaysRunsAt"): continue
        body = ((((fn.get("parameters") or {}).get("properties") or {}).get("body") or {}).get("properties")) or {}
        hook = t.get("pre_process_code") or ""
        loose = [k for k, v in body.items() if "{{" in str(v.get("default")) and not re.search(r"\[['\"]%s['\"]\]" % re.escape(k), hook)]
        if loose:
            err(f"{where}: {fn.get('name')} runs at the end of the call but pre_process_code does not set {loose} from code variables; the model writes them itself (free text such as 'customer refused ...' is rejected by the bank and the call never closes). Use snippets.close_pre_process()")

    # every pass through the main loop must be counted so a stuck call closes by itself instead of running to the maximum duration
    all_code = []
    for where, t in tool_defs(wf):
        fn = t.get("function") or {}
        if fn.get("name") == "code_exec":
            all_code.append((((fn.get("parameters") or {}).get("properties") or {}).get("code") or {}).get("default") or "")
    if all_code and not any(re.search(r"vars\[['\"]loops['\"]\]\s*=", c) for c in all_code):
        warn("no loop guard: no code node counts passes in vars['loops'] and closes past a limit; a refusal or a repeated request can cycle until the maximum duration. Add snippets.loop_guard() to the main step code")

    # a bank tool placed on a conversation node is called by the model, which fills its arguments itself and can leave them out
    # (seen live: verify_identity called with only customer_id, three calls out of three failed). Bank tools run in api_request nodes
    # (pre_actions) with every argument taken from a variable that code set; only the closing tool is workflow-level (its hook sets the body).
    for name, n in nodes.items():
        for t in n.get("tools") or []:
            fn = t.get("function") or {}
            if str(fn.get("handler", "")).endswith("api_call"):
                err(f"{name}: bank tool {fn.get('name')} is on a conversation node, so the model fills its arguments (seen live: called with no field or answer, every call failed). Put it in an api_request node's pre_actions with each body field as a {{{{variable}}}} that code set")

    # a call that starts on a conversation node with an unconditional transition did not start at all (seen live: the chat route
    # timed out after 60 s and every simulated call ended with no tool call). Start on a passthrough code node that sets the first sentence.
    n0 = nodes.get(init) or {}
    if n0.get("node_type") == "conversation" and any(c.get("operator") == "always" for t in n0.get("transitions") or [] for c in walk_conditions(t.get("condition"))):
        err(f"initial node {init!r} is a conversation node with an 'always' transition; the call does not start. Make the initial node a passthrough code node (it sets the first sentence) that leads to the talk node")

    # tools against the openapi
    names_used = set()
    for where, t in tool_defs(wf):
        fn = t.get("function") or {}
        if not str(fn.get("handler", "")).endswith("api_call"): continue
        props = (fn.get("parameters") or {}).get("properties") or {}
        url = (props.get("url") or {}).get("default")
        mock = os.environ.get("MOCK_URL", "").strip()
        if mock and url and urllib.parse.urlparse(str(url)).netloc != urllib.parse.urlparse(mock).netloc:
            err(f"{where}: {fn.get('name')}: url {url!r} is not on the bank's base URL {mock} (every tool call goes to it)")
        if not ops: continue
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
    ops = openapi_ops(argv[2])
    lines = check(load(argv[1]), ops)
    if not ops: lines.append("WARN no tool API file: tool fields and allowed values were not checked against an API")
    for l in lines: print(l)
    bad = any(l.startswith("ERROR") for l in lines)
    print("RESULT: " + ("FAIL" if bad else "PASS"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
