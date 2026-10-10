"""Build a Freya phone agent from a bank brief and its tool API.

    python3 builder/build.py <brief_path> <tool_api_path> 2>&1 | tee traces/<name>.log

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
    wd = [str(workdir), str(workdir.resolve())]
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


def prepare_workdir(brief, api):
    work = pathlib.Path(tempfile.mkdtemp(prefix="builder-"))
    (work / "inputs").mkdir(); (work / "out").mkdir(); (work / "tools").mkdir(); (work / "examples").mkdir()
    shutil.copy(brief, work / "inputs" / brief.name); shutil.copy(api, work / "inputs" / api.name)
    shutil.copytree(ROOT / "docs", work / "docs")
    shutil.copy(ROOT / "examples" / "base-agent.json", work / "examples" / "base-agent.json")
    shutil.copy(ROOT / "freya.py", work / "freya.py")
    for f in ("validate.py", "codecheck.py"): shutil.copy(HERE / f, work / "tools" / f)
    skill = work / ".claude" / "skills" / "build-phone-agent"; skill.mkdir(parents=True)
    shutil.copy(HERE / "skill" / "SKILL.md", skill / "SKILL.md")
    return work


def make_prompt(brief, api):
    return (f"Use the build-phone-agent skill. Brief: inputs/{brief.name}. Tool API file: inputs/{api.name}. "
            f"Slot name: {brief.stem}. You have {MAX_SECONDS // 60} minutes in total. Nobody will answer questions.")


async def run_builder(work, prompt):
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


def main(argv):
    dry = "--dry-run" in argv; argv = [a for a in argv if a != "--dry-run"]
    if len(argv) != 3: print(__doc__); return 2
    brief, api = pathlib.Path(argv[1]).resolve(), pathlib.Path(argv[2]).resolve()
    t0 = time.time(); stem = brief.stem
    log("start", f"brief={brief.name} tool_api={api.name} model={MODEL} max_seconds={MAX_SECONDS}")
    work = prepare_workdir(brief, api); log("workdir", str(work))
    prompt = make_prompt(brief, api)
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
        r = subprocess.run([sys.executable, str(HERE / "validate.py"), str(target), str(api)], capture_output=True, text=True)
        for line in r.stdout.splitlines(): log("validate", line)
        d = json.loads(target.read_text()); wf = d.get("workflow", d); log("exported", f"{target} nodes={len(wf.get('nodes', {}))}")
    log("end", f"elapsed_s={time.time() - t0:.0f}")
    return 0 if target.exists() else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
