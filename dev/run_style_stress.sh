#!/usr/bin/env bash
# Remaining Adım 7 style runs, sequential, one simulation at a time. Run in Sena's terminal from the repo root.
# Already done by Claude Code: A pieces, A corrects, A talkative.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
source env.sh; source .venv/bin/activate
A=43448089-96e4-45b9-96dd-53d57a5474e8; B=df3d0722-9d83-48a2-85a5-a0fb817aef3a
run() { # agent brief style tag
  echo "== $4 $3 =="
  python3 tools/run_cases.py "$1" --brief "$2" --style "$3" --reps 1 --out "results/new-$4-style-$3.json" 2>&1 | tee "dev/new-$4-style-$3.log"
  [ "${PIPESTATUS[0]}" = 0 ] || { echo "STOPPED at $4 $3" >&2; exit 1; }
}
run $A A asks_back a
run $A A in_words a
for s in pieces corrects talkative asks_back in_words; do run $B B $s b; done
echo "style runs finished"
