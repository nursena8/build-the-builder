"""Build the Python text of a Freya code node: spec constants + the tested helpers in cal.py + the node's own body.

    import sys; sys.path.insert(0, "lib")
    from snippets import code
    node_code = code(BODY, spec_subset)      # BODY may use SPEC[...] and every function of cal.py

The result is a string for the `code` default of a code_exec action. SPEC is the dict you pass (JSON-safe).
"""
import json, pathlib

_HERE = pathlib.Path(__file__).resolve().parent
LIB = (_HERE / "cal.py").read_text()


def _defs():
    """Top-level pieces of cal.py: [(names defined, source text, names it uses)]."""
    import ast
    tree = ast.parse(LIB); out = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)): continue
        seg = ast.get_source_segment(LIB, node)
        # keep the comment lines right above a definition out; they are not needed in a code node
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)): defined = {node.name}
        elif isinstance(node, ast.Assign): defined = {t.id for t in node.targets if isinstance(t, ast.Name)}
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute) and isinstance(node.value.func.value, ast.Name):
            defined = {node.value.func.value.id}      # `_ORD.update({...})` belongs with `_ORD`
        else: defined = set()
        used = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
        out.append((defined, seg, used))
    return out


def pruned_lib(body):
    """The part of cal.py that `body` uses, with what that part needs. A code node that pastes all of cal.py carries about
    20 KB it does not use, and a large code node makes every turn slower (measured on the platform)."""
    import re as _re
    defs = _defs()
    need = {w for w in _re.findall(r"[A-Za-z_][A-Za-z_0-9]*", body)}
    keep = set(); changed = True
    while changed:
        changed = False
        for i, (defined, seg, used) in enumerate(defs):
            if i in keep or not (defined & need): continue
            keep.add(i); need |= used; changed = True
    return "import datetime, re\n\n" + "\n\n".join(defs[i][1] for i in sorted(keep))


def code(body, spec=None, prune=True):
    """The text of a code node: SPEC, the helpers of cal.py that `body` uses (all of them with prune=False), then `body`."""
    lib = pruned_lib(body) if prune else LIB
    return "import json\nSPEC = json.loads(" + repr(json.dumps(spec or {})) + ")\n" + lib + "\n" + body


def close_pre_process(fallback=None, outcome_var="outcome", reason_var="reason", customer_var="customer_id"):
    """`pre_process_code` text for the closing tool. The model fills tool arguments itself and may write free text
    ("customer refused ...") into `reason`; this hook overwrites outcome, reason and customer_id from the code-computed
    variables named by `outcome_var`, `reason_var`, `customer_var` (the names the tool's body defaults use, e.g. {{close_outcome}}).
    When no path set the outcome, `fallback` (outcome, reason), the brief's own failure pair, is sent; with `fallback=None` the body is left as the model wrote it."""
    return ("try:\n"
            "    b = config.get('body')\n"
            "    o = str(vars.get(%r) or '').strip()\n"
            "    r = str(vars.get(%r) or '').strip()\n"
            "    if not o and %r:\n"
            "        o, r = %r\n"
            "    if isinstance(b, dict) and o:\n"
            "        b['outcome'] = o\n"
            "        b['customer_id'] = str(vars.get(%r) or b.get('customer_id') or '')\n"
            "        if o in ('promise', 'paid'):\n"
            "            b.pop('reason', None)\n"
            "        else:\n"
            "            b['reason'] = r\n"
            "except Exception:\n"
            "    pass\n" % (outcome_var, reason_var, bool(fallback), tuple(fallback or ('', '')), customer_var))


def loop_guard(fallback_key, limit=40):
    """Code text for the top of the main step node. `vars['loops']` counts every pass; past `limit` the call closes with
    the brief's failure outcome instead of cycling until the platform's maximum duration. Paste it inside the node's main function (it uses `return`); needs `close(key, say)` from the node. A timeout safety net only. `fallback_key` is the key, in the node's outcome table, of the brief's closest failure outcome (for example the one for a tool that keeps failing)."""
    return ("vars['loops'] = int(vars.get('loops') or 0) + 1\n"
            "if vars['loops'] > %d and vars.get('st') != 'closed':\n"
            "    return close(%r, 'I am sorry, I cannot continue this call.')\n" % (limit, fallback_key))
