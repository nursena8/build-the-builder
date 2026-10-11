"""Check that every numbered rule of the case material has a home in the agent and a test. Standard library only.

    python3 tools/rulecheck.py [work_folder]        (default: the current folder)

Rule ids: the numbered lines ("12. text") of inputs/*.md, inputs/related/*.md and of the text files under inputs/case/.
Home: out/coverage.json, an object whose keys name rules ("12", "5-9", "A5-A10"; ranges are expanded, letters ignored) and whose
      values say which node or code line carries the rule. An empty value is no home. A value that starts with "wording:" marks a rule
      that only the spoken words carry (tone, politeness); it needs no scenario.
Test: out/scenarios.json, where a scenario lists the rules it checks, {"name": ..., "rules": [12, 13], "run": ..., "expect": ...}.
Prints MISSING_COVERAGE <n> and NO_SCENARIO <n> lines, then a summary and "RESULT: PASS" or "RESULT: FAIL".
PASS needs: every rule has a home, and scenarios cover at least 60% of the rules.
"""
import json, pathlib, re, sys

MIN_TESTED = 0.6


def rule_ids(root):
    ids = set()
    files = list((root / "inputs").glob("*.md")) + list((root / "inputs" / "related").glob("*.md"))
    case = root / "inputs" / "case"
    if case.is_dir():
        files += [p for p in case.rglob("*") if p.suffix.lower() in (".md", ".txt") and p.is_file()]
    for f in files:
        try: text = f.read_text(encoding="utf-8", errors="ignore")
        except Exception: continue
        for line in text.splitlines():
            m = re.match(r"^\s*(?:[-*]\s*)?(\d{1,3})\s*[.)]\s+\S", line)
            if m and 1 <= int(m.group(1)) <= 300: ids.add(int(m.group(1)))
    return ids


def expand(key):
    """'12' -> {12}; '5-9' -> {5..9}; 'A5-A10' -> {5..10}; 'B1, B2' -> {1, 2}; 7 -> {7}."""
    s = str(key)
    out = set()
    for a, b in re.findall(r"(\d+)\s*[-–]\s*[A-Za-z]*(\d+)", s):
        if int(a) <= int(b) <= int(a) + 200: out |= set(range(int(a), int(b) + 1))
    out |= {int(n) for n in re.findall(r"\d+", s)}
    return out


def covered(root):
    f = root / "out" / "coverage.json"
    try: d = json.loads(f.read_text(encoding="utf-8"))
    except Exception: return set()
    out = set()
    items = d.items() if isinstance(d, dict) else enumerate(d)
    for k, v in items:
        if isinstance(d, list):
            if isinstance(v, dict): k, v = v.get("rule") or v.get("rules"), v.get("home") or v.get("where") or v.get("node") or v.get("covered_by")
            else: continue
        if v is None or not str(v).strip(): continue
        out |= expand(k)
    return out


def wording_only(root):
    try: d = json.loads((root / "out" / "coverage.json").read_text(encoding="utf-8"))
    except Exception: return set()
    out = set()
    for k, v in (d.items() if isinstance(d, dict) else []):
        if str(v).strip().lower().startswith("wording"): out |= expand(k)
    return out


def tested(root):
    f = root / "out" / "scenarios.json"
    try: sc = json.loads(f.read_text(encoding="utf-8"))
    except Exception: return set()
    out = set()
    for s in sc if isinstance(sc, list) else []:
        r = s.get("rules")
        if r is None: continue
        for x in (r if isinstance(r, list) else [r]): out |= expand(x)
    return out


def main(argv):
    root = pathlib.Path(argv[1]) if len(argv) > 1 else pathlib.Path(".")
    ids = rule_ids(root)
    if not ids:
        print("NO_RULE_IDS the case material has no numbered rules; nothing to check"); print("RESULT: PASS"); return 0
    home, test = covered(root), tested(root) | wording_only(root)
    missing = sorted(ids - home); untested = sorted(ids - test)
    for n in missing: print(f"MISSING_COVERAGE {n}")
    for n in untested: print(f"NO_SCENARIO {n}")
    share = (len(ids) - len(untested)) / len(ids)
    print(f"SUMMARY rules={len(ids)} with_home={len(ids) - len(missing)} with_scenario={len(ids) - len(untested)} ({share:.0%})")
    ok = not missing and share >= MIN_TESTED
    print("RESULT: " + ("PASS" if ok else "FAIL")); return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
