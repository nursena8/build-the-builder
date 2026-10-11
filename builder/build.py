"""Build a Freya phone agent from a bank's case material.

    python3 builder/build.py <case_folder> <mock_url> 2>&1 | tee traces/<name>.log     (a folder of documents + the bank's base URL)
    python3 builder/build.py <brief_path> <tool_api_path> 2>&1 | tee traces/<name>.log (a brief file + its tool API file)

What it does: copies the brief, the tool API, the docs and the skill into a fresh temporary folder, runs Claude
(Claude Agent SDK) there with the build-phone-agent skill, then exports the saved workflow to
submission/<name>.workflow.json and copies what the builder generated to runs/<name>/.
Every line printed here is the trace: timestamped, with known key values replaced by ***.
Keys come from the environment only: FREYA_API_KEY, FREYA_BANK_TEAM_KEY, and ANTHROPIC_API_KEY (or a Claude login).
Settings (environment): BUILDER_MODEL (default claude-opus-5-5), BUILD_MAX_SECONDS (default 1500).
Use --dry-run to prepare the folder and print the plan without calling Claude or Freya.
"""
import asyncio, dataclasses, json, os, pathlib, re, shutil, sys, tempfile, time

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
SECRET_VARS = ("FREYA_API_KEY", "FREYA_BANK_TEAM_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY")
MAX_SECONDS = int(os.environ.get("BUILD_MAX_SECONDS", "1500"))
MODEL = os.environ.get("BUILDER_MODEL", "claude-opus-5-5")


def scrub(text):
    for v in SECRET_VARS:
        val = os.environ.get(v, "")
        if len(val) >= 8: text = text.replace(val, "***")
    return text


def log(kind, text=""):
    line = f"[{time.strftime('%Y-%m-%dT%H:%M:%S%z')}] {kind}" + (f" {text}" if text else "")
    print(scrub(line), flush=True)


# ---- keep the builder inside its folder -------------------------------------------------------------------------
BASH_DENY = [r"\bfind\s+(/|~|\$HOME)", r"(^|[\s'\"=])~/", r"\$HOME", r"/Users/", r"/home/", r"\bcd\s+(/|\.\.)", r"\.\./"]


def guard(tool, tool_input, workdir):
    """Return a reason string if the call leaves the work folder, else None."""
    wd = sorted({str(workdir), str(workdir.resolve())}, key=len, reverse=True)  # longest first: /private/var/... before /var/...
    if tool == "Bash":
        cmd = tool_input.get("command", "")
        for w in wd: cmd = cmd.replace(w, "")
        for pat in BASH_DENY:
            if re.search(pat, cmd): return "Stay inside the work folder. Everything you need is in it; nobody will answer questions."
    elif tool in ("Read", "Write", "Edit", "Glob", "Grep"):
        p = tool_input.get("file_path") or tool_input.get("path")
        if p:
            q = pathlib.Path(p); q = q if q.is_absolute() else workdir / q
            try: q.resolve().relative_to(workdir.resolve())
            except ValueError: return "That path is outside the work folder."
    return None


def slug(name):
    import unicodedata
    t = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", t).strip("-._") or "case"


def find_openapi(folder):
    """An OpenAPI/Swagger file inside the case folder (first match), else None."""
    for f in sorted(pathlib.Path(folder).rglob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(d, dict) and isinstance(d.get("paths"), dict) and (d.get("openapi") or d.get("swagger")): return f
        except Exception:
            pass
    return None


def fetch_openapi(mock_url):
    """GET <mock_url>/openapi.json (the team's own mock). Returns the parsed dict or None."""
    import urllib.request
    for suffix in ("/openapi.json", "/v1/openapi.json", "/"):
        try:
            req = urllib.request.Request(mock_url.rstrip("/") + suffix, headers={"User-Agent": "Mozilla/5.0 (builder)"})
            with urllib.request.urlopen(req, timeout=15) as r:
                d = json.loads(r.read().decode("utf-8"))
            if isinstance(d, dict) and isinstance(d.get("paths"), dict): return d
        except Exception:
            continue
    return None


def prepare_workdir(case, api, mock_url=None):
    """case: a brief file or a folder of documents. api: a tool API file or None. mock_url: the bank's base URL or None."""
    import docconv
    work = pathlib.Path(tempfile.mkdtemp(prefix="builder-"))
    (work / "inputs").mkdir(); (work / "out").mkdir(); (work / "tools").mkdir(); (work / "examples").mkdir()
    notes = []
    if case.is_dir():
        report = docconv.convert_folder(case, work / "inputs" / "case")
        for rel, status, note in report: notes.append(f"{status} {rel} {note}".strip())
    else:
        shutil.copy(case, work / "inputs" / case.name)
        # a brief may build on another brief ("Every rule of Brief A applies"): the other briefs in the same folder go in as related files
        text = case.read_text(encoding="utf-8", errors="ignore").lower()
        def mentioned(p):   # only a brief that names another brief ("Brief A", "hidden-1") gets that one as a related file
            stem = p.stem.lower()
            return any(x in text for x in {stem, stem.replace("-", " "), stem.replace("-", "_")})
        rel = [p for p in sorted(case.parent.glob("*.md")) if p.resolve() != case.resolve() and p.stat().st_size < 60000 and mentioned(p)][:4]
        WORK_RELATED[0] = bool(rel)
        if rel:
            (work / "inputs" / "related").mkdir()
            for p in rel: shutil.copy(p, work / "inputs" / "related" / p.name)
    api_text = None
    if api is not None:
        api_text = json.loads(api.read_text(encoding="utf-8"))
    elif case.is_dir():
        f = find_openapi(case)
        if f is not None: api_text = json.loads(f.read_text(encoding="utf-8")); notes.append(f"tool API file found in the folder: {f.name}")
    if api_text is None and case.is_dir():  # a YAML tool API cannot be read with the standard library: hand it to the builder as it is
        for f in sorted(case.rglob("*.y*ml")):
            if f.suffix.lower() in (".yaml", ".yml") and re.search(r"^(openapi|swagger)\s*:", f.read_text(encoding="utf-8", errors="ignore")[:2000], re.M):
                shutil.copy(f, work / "inputs" / "openapi.yaml"); notes.append(f"tool API file (YAML) found in the folder: {f.name}; checks against it are skipped")
                global YAML_API; YAML_API = True
                break
    if api_text is None and mock_url:
        api_text = fetch_openapi(mock_url)
        if api_text is not None: notes.append(f"tool API fetched from {mock_url}")
    if api_text is not None:
        if mock_url:  # every tool call goes to the team's own mock
            api_text["servers"] = [{"url": mock_url.rstrip("/")}]
        (work / "inputs" / "openapi.json").write_text(json.dumps(api_text, ensure_ascii=False, indent=1), encoding="utf-8")
    else:
        notes.append("no tool API file: derive the tools from the documents")
    if mock_url: (work / "inputs" / "mock_url.txt").write_text(mock_url.strip(), encoding="utf-8")
    shutil.copytree(ROOT / "docs", work / "docs")
    shutil.copy(ROOT / "examples" / "base-agent.json", work / "examples" / "base-agent.json")
    shutil.copy(ROOT / "freya.py", work / "freya.py")
    for f in ("validate.py", "codecheck.py", "rulecheck.py"): shutil.copy(HERE / f, work / "tools" / f)
    shutil.copytree(HERE / "lib", work / "lib", ignore=shutil.ignore_patterns("__pycache__"))
    skill = work / ".claude" / "skills" / "build-phone-agent"; skill.mkdir(parents=True)
    shutil.copy(HERE / "skill" / "SKILL.md", skill / "SKILL.md")
    return work, notes, (work / "inputs" / "openapi.json" if api_text is not None else None)


def make_prompt(case, slot, has_api, mock_url):
    if case.is_dir():
        what = ("Case materials: the folder inputs/case/ (the bank's documents; a document such as a .docx or .xlsx has a converted .txt or .csv copy next to it; "
                "read PDFs with the Read tool). Read every file.")
    else:
        what = f"Brief: inputs/{case.name}."
    api = ("Tool API file: inputs/openapi.json." if has_api else
           ("Tool API file (YAML): inputs/openapi.yaml; read it, copy tool names, paths, fields and allowed values exactly (the API checks are skipped)." if YAML_API else
            "There is no tool API file: derive the tools, their fields and allowed values from the documents."))
    mock = f" The bank's base URL is {mock_url}: every tool call goes to it." if mock_url else ""
    rel = (" The brief refers to another brief; it is in inputs/related/. Follow it as if its rules were part of the brief, the referring brief's rules replacing the other's where it says so."
           if (not case.is_dir() and (WORK_RELATED and WORK_RELATED[0])) else "")
    return (f"Use the build-phone-agent skill. {what} {api}{mock} Slot name: {slot}. You have {MAX_SECONDS // 60} minutes in total. Nobody will answer questions.{rel}")


async def run_builder(work, prompt, purpose="build the phone agent from the brief with the build-phone-agent skill"):
    log("model_call", f"model={MODEL} purpose={purpose}")
    from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, HookMatcher, ResultMessage, TextBlock, ToolUseBlock, query

    async def pre_tool(input_data, tool_use_id, context):
        why = guard(input_data.get("tool_name"), input_data.get("tool_input") or {}, work)
        if why:
            log("guard", f"denied {input_data.get('tool_name')}: {why}")
            return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": why}}
        return {}

    options = ClaudeAgentOptions(
        cwd=work, model=MODEL, skills=["build-phone-agent"], setting_sources=["project"],
        allowed_tools=["Read", "Write", "Edit", "Glob", "Grep", "Bash"], permission_mode="dontAsk", max_turns=150,
        hooks={"PreToolUse": [HookMatcher(matcher="Bash|Read|Write|Edit|Glob|Grep", hooks=[pre_tool])]},
        env={"BASH_DEFAULT_TIMEOUT_MS": "900000", "BASH_MAX_TIMEOUT_MS": "1200000", "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "1"},
    )
    result = {"turns": 0, "cost": 0.0}
    async for m in query(prompt=prompt, options=options):
        if isinstance(m, AssistantMessage):
            for b in m.content:
                if isinstance(b, TextBlock): log("say", b.text.replace("\n", " ")[:400])
                elif isinstance(b, ToolUseBlock): log(f"tool {b.name}", str(b.input).replace("\n", " ")[:200])
        elif isinstance(m, ResultMessage):
            result = {"turns": m.num_turns, "cost": m.total_cost_usd or 0.0}
    return result


def pick_slot(work, stem):
    f = work / ".freya-agents.json"
    if not f.exists(): return None, None
    state = json.loads(f.read_text()); slots = [(k, v) for k, v in state.items() if isinstance(v, dict) and v.get("workflow_id")]
    if not slots: return None, None
    for k, v in slots:
        if k == stem: return k, v
    return slots[-1]


def export_with_retry(workflow_id, path):
    sys.path.insert(0, str(ROOT)); import freya
    for i, wait in enumerate((0, 5, 15, 30)):
        time.sleep(wait)
        try: return freya.export_workflow(workflow_id, str(path))
        except Exception as e:
            log("export_retry", f"attempt {i + 1}: {scrub(str(e))[:160]}")
    return None



FIX_ROUNDS = int(os.environ.get("BUILD_FIX_ROUNDS", "2"))


def local_workflow_path(work, stem):
    f = work / "out" / f"{stem}.workflow.json"
    if f.exists(): return f
    c = sorted((work / "out").glob("*.workflow.json"))
    return c[0] if c else None


MOCK_URL = None
YAML_API = False
WORK_RELATED = [False]


def run_validate(path, api):
    import subprocess
    env = dict(os.environ)
    if MOCK_URL: env["MOCK_URL"] = MOCK_URL
    return subprocess.run([sys.executable, str(HERE / "validate.py"), str(path), str(api) if api else "-"], capture_output=True, text=True, env=env)


def static_check(work, stem, api):
    """Apply the deterministic repairs in memory, then run the static validator. Returns (path, fixed workflow, changes, ERROR lines)."""
    import subprocess, tempfile
    sys.path.insert(0, str(HERE)); import autofix
    f = local_workflow_path(work, stem)
    if f is None: return None, None, [], []
    fixed, changes = autofix.fix(json.loads(f.read_text()))
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="chk-")) / "w.json"; tmp.write_text(json.dumps(fixed))
    r = run_validate(tmp, api)
    return f, fixed, changes, [l for l in r.stdout.splitlines() if l.startswith("ERROR")]


AUDIT_ROUNDS = int(os.environ.get("BUILD_AUDIT_ROUNDS", "2"))


def chat_probe(workflow_id):
    """One chat turn against the saved workflow (README: 'a workflow that cannot start a call'). Returns (ok, seconds, detail).
    Any answer is a pass, even the unfilled '{{say}}' of a workflow that starts with a code step (the chat route skips it)."""
    sys.path.insert(0, str(ROOT)); import freya, threading
    box = {}
    def go():
        try:
            box["r"] = freya.api("POST", "/api/v2/chat/message", {"workflowId": workflow_id, "message": "Hello?",
                                 "customerVariables": {"customer_id": "c_probe", "first_name": "Test", "last_name": "Customer", "title": "Mr", "now": "2026-10-14T11:00"}})
        except Exception as e:
            box["e"] = scrub(str(e))[:160]
    t0 = time.time(); th = threading.Thread(target=go, daemon=True); th.start(); th.join(75)
    dt = time.time() - t0
    if "r" in box: return True, dt, str(box["r"])[:100]
    return False, dt, box.get("e") or "no answer in 75 s"


def probe_prompt(detail):
    return ("The saved workflow cannot start a call: one chat turn against it failed (" + detail + "). Every working agent starts on a passthrough code node "
            "(the initial node) that sets the first sentence and leads to a talk node whose fixed text is {{say}}; a conversation node as the initial node "
            "with an 'always' transition hangs. Fix the generator so the initial node is such a code node, regenerate, run tools/validate.py and "
            "tools/codecheck.py, and save again. Do not rewrite what already works.")


def run_rulecheck(work):
    import subprocess
    r = subprocess.run([sys.executable, str(HERE / "rulecheck.py"), str(work)], capture_output=True, text=True)
    lines = (r.stdout + r.stderr).splitlines()
    return any(l.strip() == "RESULT: PASS" for l in lines), lines


def audit_prompt(lines):
    gaps = [l for l in lines if l.startswith(("MISSING_COVERAGE", "NO_SCENARIO"))]
    summary = [l for l in lines if l.startswith("SUMMARY")]
    return ("Audit round. `python3 tools/rulecheck.py` lists rules of the case material that the agent does not carry or does not test.\n"
            + "\n".join(summary + gaps[:80]) + "\n"
            "For each listed rule: find where the workflow carries it (name the node or code line in `out/coverage.json`, a rule that only the "
            "spoken words carry gets the value \"wording: ...\"). If nothing carries it, implement it in the generator, regenerate and save with freya.save_workflow. "
            "Then add a scenario to `out/scenarios.json` for the rule, with `\"rules\": [<numbers>]` in it and expected values you work out by hand from the case material, "
            "and tag the scenarios you already have with the rules they check. Run tools/validate.py, tools/codecheck.py and tools/rulecheck.py until they pass, and save again. "
            "Do not rewrite what already works.")


def fix_prompt(errors):
    return ("Your workflow has static errors. Fix out/gen.py (or the files it reads), regenerate the workflow, run "
            "tools/validate.py and tools/codecheck.py until both pass, and save it again with freya.save_workflow. "
            "Do not rewrite what already works. Errors:\n" + "\n".join(errors[:25]))


def save_with_retry(slot, wf, work):
    sys.path.insert(0, str(ROOT)); import freya
    for i, wait in enumerate((0, 5, 15, 30)):
        time.sleep(wait)
        try: return freya.save_workflow(slot, wf, state_file=str(work / ".freya-agents.json"))
        except Exception as e: log("save_retry", f"attempt {i + 1}: {scrub(str(e))[:160]}")
    return None


def main(argv):
    global MOCK_URL
    dry = "--dry-run" in argv; argv = [a for a in argv if a != "--dry-run"]
    if len(argv) != 3: print(__doc__); return 2
    case = pathlib.Path(argv[1]).resolve()
    arg2 = argv[2]
    mock_url = arg2.strip() if re.match(r"https?://", arg2.strip()) else None
    api = None if mock_url else pathlib.Path(arg2).resolve()
    MOCK_URL = mock_url
    t0 = time.time(); stem = slug(case.name if case.is_dir() else case.stem)
    log("start", f"{'case_folder' if case.is_dir() else 'brief'}={case.name} " + (f"mock_url={mock_url}" if mock_url else f"tool_api={api.name}") + f" model={MODEL} max_seconds={MAX_SECONDS}")
    stale = ROOT / "submission" / f"{stem}.workflow.json"
    if stale.exists() and not dry:
        stale.unlink(); log("cleanup", f"removed the export of an earlier run: {stale.name}")  # a failed run must not report an old file as its own
    work, notes, api = prepare_workdir(case, api, mock_url); log("workdir", str(work))
    for n in notes: log("input", n)
    prompt = make_prompt(case, stem, api is not None, mock_url)
    if dry:
        log("dry-run", "prompt: " + prompt); log("dry-run", "files: " + ", ".join(sorted(str(p.relative_to(work)) for p in work.rglob("*") if p.is_file())))
        return 0
    try:
        res = asyncio.run(asyncio.wait_for(run_builder(work, prompt), MAX_SECONDS))
        log("builder_done", f"turns={res['turns']} cost_usd={res['cost']:.2f}")
    except asyncio.TimeoutError:
        log("timeout", f"stopped after {MAX_SECONDS} s; exporting what was saved")
    except Exception as e:
        log("builder_error", scrub(str(e))[:300])

    # feedback loop: errors the repairs cannot fix go back to the builder while time remains
    for rnd in range(FIX_ROUNDS):
        left = MAX_SECONDS - (time.time() - t0)
        f, fixed, changes, errs = static_check(work, stem, api)
        if not errs or left < 240: break
        log("fix_round", f"{rnd + 1}: {len(errs)} error(s) left after repairs; {int(left)} s left")
        for e in errs[:8]: log("fix_error", e[:200])
        try:
            res = asyncio.run(asyncio.wait_for(run_builder(work, fix_prompt(errs), "fix the static errors the checks found"), left - 60))
            log("fix_round_done", f"turns={res['turns']} cost_usd={res['cost']:.2f}")
        except asyncio.TimeoutError:
            log("timeout", "fix round stopped by the time limit"); break
        except Exception as e:
            log("builder_error", scrub(str(e))[:300]); break
    # rule audit: every numbered rule needs a home in the agent and a scenario that tests it; the builder gets rounds to close the gaps
    for rnd in range(AUDIT_ROUNDS):
        left = MAX_SECONDS - (time.time() - t0)
        ok, lines = run_rulecheck(work)
        for l in lines[-6:]: log("rulecheck", l[:200])
        if ok or left < 480: break
        log("audit_round", f"{rnd + 1}: {len([l for l in lines if l.startswith(('MISSING', 'NO_SCENARIO'))])} rule gap(s); {int(left)} s left")
        try:
            res = asyncio.run(asyncio.wait_for(run_builder(work, audit_prompt(lines), "audit every rule of the case material against the workflow and its tests"), left - 120))
            log("audit_round_done", f"turns={res['turns']} cost_usd={res['cost']:.2f}")
        except asyncio.TimeoutError:
            log("timeout", "audit round stopped by the time limit"); break
        except Exception as e:
            log("builder_error", scrub(str(e))[:300]); break
    ok, lines = run_rulecheck(work)
    for l in lines: log("rulecheck_final", l[:200]) if l.startswith(("SUMMARY", "RESULT", "MISSING", "NO_RULE")) else None
    # the audit may have changed the workflow: the static errors get one more look
    f, fixed, changes, errs = static_check(work, stem, api)
    left = MAX_SECONDS - (time.time() - t0)
    if errs and left > 300:
        log("fix_round", f"after the audit: {len(errs)} error(s) left; {int(left)} s left")
        try:
            res = asyncio.run(asyncio.wait_for(run_builder(work, fix_prompt(errs), "fix the static errors the checks found"), left - 90))
            log("fix_round_done", f"turns={res['turns']} cost_usd={res['cost']:.2f}")
        except asyncio.TimeoutError:
            log("timeout", "fix round stopped by the time limit")
        except Exception as e:
            log("builder_error", scrub(str(e))[:300])
    # live start check: one chat turn on the saved agent
    slotp, infop = pick_slot(work, stem)
    if infop:
        ok, secs, detail = chat_probe(infop["workflow_id"])
        log("chat_probe", f"{'ok' if ok else 'FAIL'} {secs:.1f}s {detail}")
        left = MAX_SECONDS - (time.time() - t0)
        if not ok and left > 300:
            log("fix_round", f"the saved workflow cannot start a call; {int(left)} s left")
            try:
                res = asyncio.run(asyncio.wait_for(run_builder(work, probe_prompt(detail), "fix a workflow that cannot start a call"), left - 120))
                log("fix_round_done", f"turns={res['turns']} cost_usd={res['cost']:.2f}")
                slotp, infop = pick_slot(work, stem)
                ok, secs, detail = chat_probe(infop["workflow_id"]); log("chat_probe", f"{'ok' if ok else 'FAIL'} {secs:.1f}s {detail}")
            except asyncio.TimeoutError:
                log("timeout", "start-fix round stopped by the time limit")
            except Exception as e:
                log("builder_error", scrub(str(e))[:300])
    # final deterministic repairs, saved to the platform
    f, fixed, changes, errs = static_check(work, stem, api)
    if f is not None and changes:
        for c in changes: log("autofix", c)
        f.write_text(json.dumps(fixed, indent=1))
        slot0, info0 = pick_slot(work, stem)
        if info0 and save_with_retry(slot0, fixed, work): log("autofix_saved", f"slot={slot0}")
        else: log("autofix_not_saved", "kept the repaired file locally")
    for e in errs: log("remaining_error", e[:200])

    runs = ROOT / "runs" / stem; subm = ROOT / "submission"; runs.mkdir(parents=True, exist_ok=True); subm.mkdir(exist_ok=True)
    for p in (work / "out").glob("*"):
        if p.is_file(): shutil.copy(p, runs / p.name)
    slot, info = pick_slot(work, stem)
    target = subm / f"{stem}.workflow.json"
    if info:
        log("saved_agent", f"slot={slot} workflow_id={info['workflow_id']} agent_id={info.get('agent_id')}")
        if not export_with_retry(info["workflow_id"], target):
            local = work / "out" / f"{stem}.workflow.json"
            if local.exists(): shutil.copy(local, target); log("export_fallback", f"copied the builder's local file to {target}")
    else:
        log("no_agent", "the builder did not save a workflow")
    if target.exists():
        import subprocess
        r = run_validate(target, api)
        for line in r.stdout.splitlines(): log("validate", line)
        d = json.loads(target.read_text()); wf = d.get("workflow", d)
        n_tools = len(wf.get("tools") or []) + sum(len(n.get("tools") or []) + len(n.get("pre_actions") or []) for n in (wf.get("nodes") or {}).values())
        log("exported", f"{target} nodes={len(wf.get('nodes', {}))} tools={n_tools}")
        sc = work / "out" / "scenarios.json"
        if sc.exists():
            r = subprocess.run([sys.executable, str(HERE / "codecheck.py"), str(target), str(sc)], capture_output=True, text=True)
            for line in (r.stdout + r.stderr).splitlines(): log("codecheck", line[:300])
        else:
            log("codecheck", "no out/scenarios.json from the builder; arithmetic scenarios were not run")
    log("end", f"elapsed_s={time.time() - t0:.0f}")
    return 0 if target.exists() else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
