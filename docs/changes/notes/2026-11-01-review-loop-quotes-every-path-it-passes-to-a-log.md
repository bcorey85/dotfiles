---
type: "Change"
change_type: "fixed"
title: "Review loop quotes every path it passes to a log or script call"
description: "A review of a repo with dynamic route folders (`app/[id]/route.ts`) logs each finding on the first call: the loop's log and script templates single-quote every path, so zsh no longer fails the call with \"no matches found\" and costs a retry."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-01T00:21:33-05:00"}
seq: 419
kind: "fix"
components: ["agent/review-loop", "shared/finding-log", "skill/code"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_log_review_finding.py::TestAuditRowTest::test_a_finding_logged_under_zsh_as_the_log_rule_writes_it_takes_a_bracketed_path"
asked: ""
proof: []
unmeasured: ""
---

## Change

- The finding-log rule writes `'file=<path>'` and `'root=<path>'` in single quotes, and says why: zsh reads `[ ] * ?`
  in an unquoted path as a glob.
- The review-loop agent quotes `root=` on review-scope, `cd '<ROOT>'`, the logger's `root=`, and the full check's
  root, log and plan paths, and tells the loop to single-quote every path it passes to a command.
- The /code skill's ask-outcome log call quotes `file=`.

## Evidence

judgment: in a headless bench run on a Next.js tree, every review-loop log call with an `[id]` path failed with zsh
"no matches found" and needed a quoted retry, 14 times in one session.

## Result

The named test fills the `file=` argument exactly as the finding-log rule writes it with `app/[id]/route.ts` and
runs the logger under zsh. On the old rule it fails with `zsh:1: no matches found: file=app/[id]/route.ts`; on the
new one it exits 0 and the row keeps the path. A second test,
`PathQuotingTest::test_every_path_the_review_loop_templates_pass_to_a_command_is_single_quoted`, fails on all three
old files and passes on the new ones. `test_log_review_finding`: 24 tests OK; the 7 modules that read the edited
prose: 666 tests OK; ruff clean.

## Watch

None. A glob failure shows as a failed log call in the session that hits it.

## Back-out

Revert the quotes in `skills/_shared/finding-log.md`, `agents/review-loop.md` and `skills/code/SKILL.md`, and the
two tests.
