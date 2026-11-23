---
name: test-audit
description: The cross-phase test gate: culls test spam and sweeps weak or absent assertions against the plan at branch scope; routes findings to /fix, hands its receipt to /branch-recap. `review [be|fe|fs|branch] [focus]` instead reviews a test suite for coverage gaps, weak assertions and stale tests. Use for "test audit", "review the tests", "test suite health", "coverage check", "cull the branch's tests".
allowed-tools: [Bash, Read, Glob, Grep, Agent, Skill]
---

# Test audit — the cross-phase test gate

The third closing phase — the one test question no phase answers locally: do the branch's tests, taken whole, pin intent without spam or loose oracles? Bug-pinning is not run here. Cull + weak only.

If `$ARGUMENTS` starts with `review`, run **Review mode** below and skip the rest. Otherwise run the audit.

Output: findings to `/fix`, a flywheel log row, a receipt line for `/branch-recap`.

## The audit

Dispatch `test-intent-reviewer` (pinned; omit `model`) — **cull + weak scope** (`scope: cull` in its contract).

Hand it branch diff + oracle (spec + AC). Cull and WEAK findings → `/fix`, with `lane: test-audit` in its args. Then run the execution gate once, after the last change, unless that change came through `/fix`: its loop already ran the gate.

**`REQUIRES-MUTATION` → `mutation-tester`, not `/fix`.** Dispatch with the named mutation (pinned; omit `model`); resolve the cull only after. Never resolve by judgement — unrouted stays open and reported open. Several → dispatch SEQUENTIALLY (global lock; concurrent runs abort).

Verdicts are defined in `mutation-tester.md` — read them there, never restate. Only KILLED (test earns its place) and SURVIVED (cull stands) settle the cull. The other two misread as:

- **EQUIVALENT** is not a survivor. The mutant is unobservable, so the cull question was
  malformed and no test could ever settle it. Do **not** commission coverage to chase it.
- **INDETERMINATE** is still open. Report it open; do not downgrade it to a pass.

Receipt line (hand to `/branch-recap`): `test audit: <n> culled, <n> weak of <N> plan promises walked | clean | skipped — no test files`.

## Logging

Log the firing (non-blocking; skip if audit skipped):

```bash
~/.claude/skills/review/log-review-metrics \
  lane=test-audit \
  test_intent_ran=1 test_intent=<n findings> tests_added=<the auditor's Tests added header> culled=<n> weak=<n> \
  requires_mutation=<n> mutation_equivalent=<n of those the tester ruled EQUIVALENT> \
  mutation_open=<n still INDETERMINATE or unrouted> \
  result=<clean|findings>
```

Then log the per-finding rows with `gate=test-intent-reviewer lane=test-audit scope=branch-exit`, after dispositions are known (`actioned` real, not predicted). Zero-finding audits still log `kind=run`.

```bash
# Each row is its own plain Bash call by this path: no $HOME, variable, array or $(...).
# Repeat iter on every call. The script adds repo and branch itself.
# Single-quote every argument that holds a path, as written below.
# When the reviewed repo is not your cwd, add 'root=<its absolute path>' to every call; the script runs there.

# ONE run row.
~/.claude/skills/review/log-review-finding kind=run lane=test-audit scope=branch-exit iter=<N> \
  gate=test-intent-reviewer n_findings=<n> diff_base=<ref> result=<PASS|PASS_WITH_WARNINGS|NEEDS_CHANGES|NOT_DISPATCHED>

# ONE finding row per finding.
~/.claude/skills/review/log-review-finding kind=finding lane=test-audit scope=branch-exit iter=<N> \
  gate=test-intent-reviewer disposition=<fix|ask|nit> [blocker=yes] \
  class=<bug|smell|duplication|complexity|plan-drift|test-gap|weak-assertion|security|perf|correctness|docs|other> \
  <'file=<path>' line=<n>|file=unlocated> actioned=<fixed|skipped_fp|deferred|ask|none>
# Prints finding_id=<id>.
```

- `class=` uses the escape vocabulary. Do not invent values — unknown ones store as `other` and are counted in the yield header.
- **`other` is a last resort.** Reach for `docs` when the prose is wrong about the code (stale comment, wrong quantity, contradicting doc, over-cap volume).
- **`result=` is the gate's verdict, one of the four tokens above, with underscores.** The tool refuses any other value. Use `PASS` clean/intent-aligned, `NEEDS_CHANGES` gaps/residue, `NOT_DISPATCHED` surface-unmatched.
- **`desc=` is accepted and never stored.** Leave it off new calls. A call that carries text passes `desc=-` and the text in a quoted heredoc (`<<'DESC'`), never inside the argument.
- **Asks:** log an `actioned=ask` finding row with the same `file=` and `line=` as the ask's `file_line`. The caller reads the printed `finding_id=<id>` from the transcript and logs the outcome under it with `ask_outcome=`, which supersedes the ask row. The writer refuses an ask outcome with no `finding_id`.
- Full field reference lives in the script's header.
- The metrics row above takes no diff field.
- Each finding row passes the test `file=` and `line=` the auditor's finding names. A finding that names only a plan promise, such as an `absent` WEAK, passes `file=unlocated` and no line. Never guess a file.

## Review mode: `review [be|fe|fs|branch] [focus]`

Ad-hoc suite review, off the closing pipeline. Dispatch `test-reviewer` (omit `model`; frontmatter pins Sonnet).

1. Take the modifier: `be`/`backend`, `fe`/`frontend`, `fs`/`fullstack` or `branch`. Any text after it is a focus area passed to the agent.
2. With no modifier, classify the diff and untracked files as fe or be per the project layout (CLAUDE.md if unclear): only fe is `frontend`, only be is `backend`, both is `fullstack`, ambiguous means ask.
3. Dispatch `frontend` or `backend` as one agent, `fullstack` as two in parallel. `branch` is one agent with scope `branch` (it diffs the merge-base itself) and reviews only branch-added or modified tests plus a cull check. Never run `branch` on a pipeline branch: this audit already judges those tests.
4. Present the report and ask about dispatching coders for fixes. Log nothing.

## What NOT to do

- **Never edit code or tests** — findings route to `/fix`; this phase dispatches.
- **Never `git add`, commit, or open a PR** — residue + recap are `/branch-recap`'s.
- **No bug-pinning half** — `scope: cull` only.

## Arguments

$ARGUMENTS
