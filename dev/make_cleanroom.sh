#!/usr/bin/env bash
# Build a clean-room copy of the kit for ONE builder run. Allow-list only.
#   ./dev/make_cleanroom.sh <name> <brief.md>
# Result: $CLEANROOM_BASE/<name>  (default ~/builder-cleanrooms/<name>), outside the repo.
# Deliberately NOT copied: dev/, results/, traces/, public-test-set.json, env.sh, .freya-agents.json,
# .personas.json, .git, other briefs, the long notes file. In the hidden run the builder has no matching
# test set, so this measures single-shot generalisation.
set -euo pipefail
[ $# -eq 2 ] || { echo "usage: $0 <name> <brief.md>" >&2; exit 2; }
NAME="$1"; BRIEF="$2"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE="${CLEANROOM_BASE:-$HOME/builder-cleanrooms}"
DEST="$BASE/$NAME"
[ -f "$BRIEF" ] || { echo "brief not found: $BRIEF" >&2; exit 2; }
case "$NAME" in *[!A-Za-z0-9._-]*|"") echo "bad name" >&2; exit 2;; esac
[ ! -e "$DEST" ] || { echo "already exists: $DEST (remove it or pick another name)" >&2; exit 2; }

mkdir -p "$DEST/briefs" "$DEST/tools" "$DEST/traces"
cp -R "$REPO/.claude" "$DEST/.claude"
cp -R "$REPO/docs" "$DEST/docs"
cp -R "$REPO/examples" "$DEST/examples"
cp "$REPO/freya.py" "$REPO/env.example" "$REPO/VERSION" "$REPO/README.md" "$DEST/"
cp "$REPO/tools/openapi.json" "$REPO/tools/run_cases.py" "$REPO/tools/score.py" "$DEST/tools/"
cp "$BRIEF" "$DEST/briefs/$(basename "$BRIEF")"
find "$DEST" -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true

# Self-check: nothing from the forbidden list may be present.
bad=0
for f in dev results public-test-set.json env.sh .freya-agents.json .personas.json .git; do
  if [ -e "$DEST/$f" ]; then echo "FORBIDDEN present: $f" >&2; bad=1; fi
done
n=$(ls "$DEST/briefs" | wc -l | tr -d ' ')
[ "$n" = "1" ] || { echo "briefs/ must hold exactly one brief, found $n" >&2; bad=1; }
for v in FREYA_API_KEY FREYA_BANK_TEAM_KEY GEMINI_API_KEY; do
  val="${!v:-}"
  if [ -n "$val" ] && grep -rIlF -- "$val" "$DEST" >/dev/null 2>&1; then echo "FORBIDDEN: value of $v found in clean room" >&2; bad=1; fi
done
[ "$bad" = 0 ] || exit 1
echo "cleanroom ready: $DEST"
( cd "$DEST" && find . -type f | sort )
