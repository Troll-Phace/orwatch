#!/usr/bin/env bash
# preflight.sh — Agentic Framework 2.1-OC
#
# Verifies that every model pinned in opencode.json(c) still advertises
# tool calling on the providers you allowlisted.
#
# This exists because tool support on OpenRouter is a property of the
# ENDPOINT, not the model. The same model ID fans out across providers with
# non-uniform capability, and that capability changes without notice. With
# `require_parameters: false` a tools-bearing request routed to a tool-less
# endpoint returns prose and no tool_calls — an agent that silently stops
# calling tools, with no error anywhere.
#
# No API key required; the endpoints API is public.
#
# Usage:
#   bash .opencode/scripts/preflight.sh
#   bash .opencode/scripts/preflight.sh moonshotai/kimi-k3 qwen/qwen3.8-max
#
# Exit codes: 0 = all pinned models healthy, 1 = at least one failure.

set -uo pipefail

CONFIG=""
for c in opencode.jsonc opencode.json .opencode/opencode.json; do
  [ -f "$c" ] && CONFIG="$c" && break
done

# Models: from argv, else parsed out of the config's provider.openrouter.models keys.
if [ "$#" -gt 0 ]; then
  MODELS=("$@")
elif [ -n "$CONFIG" ]; then
  # Read the openrouter model keys out of JSONC.
  # NOTE: comment stripping must be string-aware — a naive s://.*:: also
  # eats the "//" in "https://opencode.ai/config.json".
  # NOTE: a while-read loop, not `mapfile` — mapfile is bash 4+ and macOS
  # ships bash 3.2.
  MODELS=()
  while IFS= read -r _m; do
    [ -n "$_m" ] && MODELS+=("$_m")
  done < <(python3 - "$CONFIG" <<'PY' 2>/dev/null
import json, re, sys

raw = open(sys.argv[1], encoding="utf-8").read()

out, i, n = [], 0, len(raw)
in_str = esc = False
while i < n:
    c = raw[i]
    if in_str:
        out.append(c)
        if esc:            esc = False
        elif c == "\\":    esc = True
        elif c == '"':     in_str = False
        i += 1
        continue
    if c == '"':
        in_str = True; out.append(c); i += 1; continue
    if c == "/" and i + 1 < n and raw[i + 1] == "/":
        while i < n and raw[i] != "\n":
            i += 1
        continue
    if c == "/" and i + 1 < n and raw[i + 1] == "*":
        i += 2
        while i + 1 < n and not (raw[i] == "*" and raw[i + 1] == "/"):
            i += 1
        i += 2
        continue
    out.append(c); i += 1

text = re.sub(r",(\s*[}\]])", r"\1", "".join(out))
try:
    cfg = json.loads(text)
except Exception:
    raise SystemExit(0)

for m in (cfg.get("provider", {}).get("openrouter", {}).get("models", {}) or {}):
    print(m)
PY
  )
else
  MODELS=()
fi

if [ "${#MODELS[@]}" -eq 0 ]; then
  echo "preflight: no models found (pass slugs as arguments, or add them to"
  echo "           provider.openrouter.models in opencode.jsonc)"
  exit 1
fi

command -v curl >/dev/null 2>&1 || { echo "preflight: curl not found"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "preflight: python3 not found"; exit 1; }

echo "Agentic Framework 2.1-OC — endpoint capability preflight"
echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ')  ·  ${#MODELS[@]} model(s)  ·  config: ${CONFIG:-none}"
echo "An endpoint counts as tool-capable only if it advertises BOTH 'tools' and"
echo "'tool_choice'. so=y/N is structured_outputs support."
echo

FAIL=0

for slug in "${MODELS[@]}"; do
  [ -z "$slug" ] && continue
  body="$(curl -sS --max-time 25 "https://openrouter.ai/api/v1/models/${slug}/endpoints" 2>/dev/null)"

  if [ -z "$body" ]; then
    printf '  \033[31mFAIL\033[0m  %s — could not reach the OpenRouter API\n' "$slug"
    FAIL=1
    continue
  fi

  # NOTE: body goes through the environment, not stdin — a heredoc-supplied
  # program and a piped payload cannot both occupy stdin.
  out="$(MODEL="$slug" BODY="$body" python3 <<'PY'
import json, os

slug = os.environ["MODEL"]
try:
    data = json.loads(os.environ["BODY"]).get("data") or {}
except Exception:
    print(f"FAIL|{slug}|unparsable response (is the slug correct?)")
    raise SystemExit(0)

eps = data.get("endpoints") or []
if not eps:
    print(f"FAIL|{slug}|slug resolves but exposes ZERO live endpoints "
          f"(this is what every :free variant does)")
    raise SystemExit(0)

with_tools, without_tools = [], []
for e in eps:
    sp = set(e.get("supported_parameters") or [])
    tag = e.get("tag") or e.get("provider_name") or "?"
    pricing = e.get("pricing") or {}
    try:
        pin = float(pricing.get("prompt") or 0) * 1e6
        pout = float(pricing.get("completion") or 0) * 1e6
    except Exception:
        pin = pout = 0.0
    rec = {
        "tag": tag,
        "tools": "tools" in sp and "tool_choice" in sp,
        "so": "structured_outputs" in sp,
        "maxout": e.get("max_completion_tokens"),
        "quant": e.get("quantization") or "?",
        "in": pin, "out": pout,
    }
    (with_tools if rec["tools"] else without_tools).append(rec)

if not with_tools:
    print(f"FAIL|{slug}|NO endpoint advertises tools — every agent bound to "
          f"this model will silently receive prose instead of tool calls")
    raise SystemExit(0)

status = "WARN" if len(with_tools) == 1 else "OK"
note = ""
if len(with_tools) == 1:
    note = "only ONE tool-capable endpoint — no failover"

print(f"{status}|{slug}|{note}")
for r in sorted(with_tools, key=lambda r: r["in"]):
    mo = r["maxout"] if r["maxout"] else "—"
    print(f"    ok   {r['tag']:<24} ${r['in']:.2f}/${r['out']:.2f}  "
          f"maxout={mo}  quant={r['quant']}  so={'y' if r['so'] else 'N'}")
for r in without_tools:
    print(f"    NO-TOOLS  {r['tag']:<20} ${r['in']:.2f}/${r['out']:.2f}   "
          f"<- exclude from provider.order")
PY
)"

  first="$(printf '%s' "$out" | head -1)"
  rest="$(printf '%s' "$out" | tail -n +2)"
  st="${first%%|*}"
  tail_="${first#*|}"
  name="${tail_%%|*}"
  msg="${tail_#*|}"

  case "$st" in
    OK)   printf '  \033[32m OK \033[0m  %s\n' "$name" ;;
    WARN) printf '  \033[33mWARN\033[0m  %s — %s\n' "$name" "$msg" ;;
    *)    printf '  \033[31mFAIL\033[0m  %s — %s\n' "$name" "$msg"; FAIL=1 ;;
  esac
  [ -n "$rest" ] && printf '%s\n' "$rest"
  echo
done

if [ "$FAIL" -ne 0 ]; then
  echo "PREFLIGHT FAILED — fix provider.order / require_parameters in your config"
  echo "before running an agentic phase. See docs/SPEC.md §4.6."
  exit 1
fi

echo "Preflight clean. Reminder: 'order' alone does not restrict routing —"
echo "keep allow_fallbacks:false and require_parameters:true alongside it."
exit 0
