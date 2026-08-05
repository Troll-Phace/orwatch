---
description: Log a discovered defect, limitation, or tech-debt item as a classified GitHub issue. Use the moment something is found and deferred.
agent: issue-triage
subtask: true
---

# Log Issue

Finding: $ARGUMENTS

## Do this

1. Derive search keywords from the finding.
2. Dedup: `gh issue list --search "<keywords>" --state all`. If a match exists, comment the new context onto it and stop — report the existing number.
3. Classify: exactly one `type:` and exactly one `severity:` label.
4. Choose a milestone if a current breakpoint tier fits; otherwise add `needs-triage`.
5. Create the issue with a body covering: what / where (file:symbol) / repro or observation / what "fixed" looks like as a verifiable outcome.
6. Report the issue number and its classification.

Never close an issue here.
