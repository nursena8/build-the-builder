#!/usr/bin/env bash
# One command, run from the repo root in Sena's terminal:
#   ./dev/run_mutant_pipeline.sh
# 1 clean room  2 SDK builder (Sonnet, in the clean room)  3 read agent_id  4 score mutant cases  5 score extra cases
# Stops at the first failing step and says which one. Uses real Freya/Gemini-free calls only through the kit tools.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
REPO="$(pwd)"
NAME="${1:-mutant-1}"
CR="${CLEANROOM_BASE:-$HOME/builder-cleanrooms}/$NAME"
fail() { echo; echo "STOPPED at step $1: $2" >&2; exit 1; }

[ -f env.sh ] && [ -f .venv/bin/activate ] || fail 0 "env.sh or .venv missing in $REPO"
# shellcheck disable=SC1091
source env.sh
# shellcheck disable=SC1091
source .venv/bin/activate
mkdir -p dev

echo "== step 1: clean room =="
./dev/make_cleanroom.sh "$NAME" dev/mutant/brief-a-mutant.md 2>&1 | tee dev/mutant-1-cleanroom.log
[ "${PIPESTATUS[0]}" = 0 ] || fail 1 "make_cleanroom.sh failed (see dev/mutant-1-cleanroom.log)"

echo "== step 2: SDK builder in the clean room (BUILDER_MODEL=claude-sonnet-5-5) =="
( cd "$CR" && unset ANTHROPIC_API_KEY && BUILDER_MODEL=claude-sonnet-5-5 python3 examples/agent_builder.py briefs/brief-a-mutant.md ) 2>&1 | tee "$CR/build.log" | tee dev/mutant-2-build.log
[ "${PIPESTATUS[0]}" = 0 ] || fail 2 "agent_builder.py failed (see $CR/build.log)"

echo "== step 3: agent_id from the clean room's slot file =="
[ -f "$CR/.freya-agents.json" ] || fail 3 "$CR/.freya-agents.json not created: the builder saved no agent"
AGENT_ID="$(python3 - "$CR/.freya-agents.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
slots = [(k, v) for k, v in d.items() if isinstance(v, dict) and v.get("agent_id")]
if not slots: sys.exit(1)
for k, v in slots: print("slot", k, v["agent_id"], file=sys.stderr)
print(slots[-1][1]["agent_id"])
PY
)" || fail 3 "no agent_id in slot file"
echo "agent_id: $AGENT_ID (last slot; all slots listed above)" | tee dev/mutant-3-agent.log

echo "== step 4: mutant cases, reps 3 =="
python3 tools/run_cases.py "$AGENT_ID" --cases dev/mutant/cases-mutant.json --brief A --reps 3 --out results/mutant-reps3.json 2>&1 | tee dev/mutant-4-reps3.log
[ "${PIPESTATUS[0]}" = 0 ] || fail 4 "run_cases on cases-mutant.json failed (see dev/mutant-4-reps3.log)"

echo "== step 5: mutant extra cases, reps 3 =="
python3 tools/run_cases.py "$AGENT_ID" --cases dev/mutant/cases-mutant-extra.json --brief A --reps 3 --out results/mutant-extra-reps3.json 2>&1 | tee dev/mutant-5-extra-reps3.log
[ "${PIPESTATUS[0]}" = 0 ] || fail 5 "run_cases on cases-mutant-extra.json failed (see dev/mutant-5-extra-reps3.log)"

echo; echo "pipeline finished. Logs: dev/mutant-*.log, results/mutant-reps3.json, results/mutant-extra-reps3.json"
