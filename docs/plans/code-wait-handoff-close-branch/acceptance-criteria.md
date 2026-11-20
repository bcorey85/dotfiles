# Acceptance criteria

- **AC1** — `code_wait.py agent` returns only a report written after the current wait started (or after the phase it was asked about began), never a stale report from an earlier phase of the same agent. (Phase 1)
- **AC2** — A test covers an agent that reports twice: waiting for the second phase blocks until the second report exists. (Phase 1)
- **AC3** — A phase's review never starts on the hand-off text of an earlier phase: a phase start moves the last hand-off aside, and a review start with no hand-off file fails loudly. (Phase 2)
- **AC4** — A close-branch run in a scratch repo with one staged and one unstaged file ends with the same `git diff --cached --name-only`, and the skill's steps and description agree. (Phase 3)
- **AC5** — The code-fork / /code skill final-report template names the remaining git step without writing a user-facing command, and a fixture run of a /code fork shows no `!` git line in its report. (Phase 4)
- **AC6** — `bash tests/run.sh` passes (apart from `test_rule_anchors`, which fails on master).
