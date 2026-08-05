---
description: Sweep untriaged and unlabeled GitHub issues, assigning type, severity, and milestone
agent: issue-triage
subtask: true
---

# Triage Issues

Needs triage:
!`gh issue list --label needs-triage --state open --limit 50 2>/dev/null`

Unlabeled:
!`gh issue list --search "no:label" --state open --limit 50 2>/dev/null`

## Do this

1. For each candidate, read the body — and the referenced source if the severity is not obvious from the description alone.
2. Assign one `type:`, one `severity:`, and a milestone if a tier fits:
   `gh issue edit <n> --add-label "type:X,severity:Y" --remove-label needs-triage [--milestone "<tier>"]`
3. Report a table: `# | title | type | severity | milestone`.
4. Flag genuinely ambiguous items for the user rather than guessing. A wrongly-severitied issue stops getting looked at, which is worse than an untriaged one.
