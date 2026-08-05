#!/usr/bin/env bash
# retier.sh — Agentic Framework 2.1-OC
#
# Swap the model bound to a tier across every agent definition at once.
# Tiering is the whole point of 2.1-OC: model choice should be one edit,
# not nine.
#
# Usage:
#   bash .opencode/scripts/retier.sh WORKHORSE openrouter/qwen/qwen3-coder-next
#   bash .opencode/scripts/retier.sh --list
#
# After running, update provider.openrouter.models in opencode.jsonc with the
# new slug's provider allowlist, then run preflight.sh.

set -euo pipefail
AGENTS=".opencode/agents"

# NOTE: a function, not an associative array — `declare -A` is bash 4+ and
# macOS ships bash 3.2.
tier_agents() {
  case "$1" in
    DEEP)      echo "architect specialist" ;;
    ANCHOR)    echo "orchestrator code-reviewer" ;;
    WORKHORSE) echo "backend-dev frontend-dev test-engineer issue-triage researcher" ;;
    *)         echo "" ;;
  esac
}

if [ "${1:-}" = "--list" ] || [ "$#" -lt 2 ]; then
  echo "Tier bindings:"
  for t in DEEP ANCHOR WORKHORSE; do
    printf '  %-10s ' "$t"
    for a in $(tier_agents "$t"); do
      f="$AGENTS/$a.md"
      [ -f "$f" ] || continue
      printf '%s=%s  ' "$a" "$(grep -m1 '^model:' "$f" | sed 's/^model:[[:space:]]*//')"
    done
    echo
  done
  echo
  echo "Usage: bash $0 <DEEP|ANCHOR|WORKHORSE> <provider/model-slug>"
  exit 0
fi

TIER="$1"; NEW="$2"
AGENT_LIST="$(tier_agents "$TIER")"
[ -n "$AGENT_LIST" ] || { echo "Unknown tier: $TIER (DEEP|ANCHOR|WORKHORSE)"; exit 1; }

for a in $AGENT_LIST; do
  f="$AGENTS/$a.md"
  [ -f "$f" ] || { echo "  skip  $a (no file)"; continue; }
  old="$(grep -m1 '^model:' "$f" | sed 's/^model:[[:space:]]*//')"
  # Only the frontmatter's first `model:` line — never body text.
  awk -v new="$NEW" '
    /^---$/ { d++ }
    d==1 && /^model:/ && !done { print "model: " new; done=1; next }
    { print }
  ' "$f" > "$f.tmp" && mv "$f.tmp" "$f"
  echo "  $a: $old -> $NEW"
done

echo
cat <<EOF

This rewrote the agent files only. Also update opencode.jsonc:
  1. Add "$NEW" under provider.openrouter.models with a VERIFIED
     endpoint allowlist (require_parameters + allow_fallbacks:false + order).
  2. If you re-tiered ANCHOR, update the top-level "model".
     If you re-tiered WORKHORSE, update "small_model" too.
  3. Update the TIER MAP comment block at the top of the file.
Then: bash .opencode/scripts/preflight.sh
EOF
