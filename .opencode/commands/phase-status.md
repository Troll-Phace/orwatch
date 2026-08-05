---
description: Project status dashboard — phase state, open issue backlog, git history, and test health
agent: orchestrator
---

# Project Status

## Phase state
!`cat .opencode/state/progress.md 2>/dev/null || echo "No progress file yet."`

## Open issue backlog
!`gh issue list --state open --limit 40 --json number,title,labels,milestone --template '{{range .}}#{{.number}} {{.title}} [{{range .labels}}{{.name}} {{end}}]{{"\n"}}{{end}}' 2>/dev/null || echo "gh unavailable or not authenticated."`

## Milestone progress
!`gh api repos/{owner}/{repo}/milestones --jq '.[] | "\(.number)  \(.title)  open:\(.open_issues) closed:\(.closed_issues)"' 2>/dev/null || echo "No milestones."`

## Recent commits
!`git log --oneline -15 2>/dev/null`

## Working tree
!`git status --short 2>/dev/null`

## Deferred markers in source
!`rg -n "TODO|FIXME|HACK|XXX" --stats -g '!.venv' -g '!__pycache__' -g '!snapshots' 2>/dev/null | tail -12`

## Tool-call failures logged this project
!`wc -l .opencode/state/tool-errors.jsonl 2>/dev/null || echo "0 (telemetry plugin has recorded nothing)"`

## Do this

Summarise the above into: current phase and its remaining tasks, backlog shape by severity, anything blocking, and the single next action. Keep it under 20 lines. Do not restate the raw output.
