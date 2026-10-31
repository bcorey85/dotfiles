---
type: "Change"
change_type: "changed"
title: "Global rule: cap test workers and run one heavy job at a time"
description: "The global CLAUDE.md gains a Machine Load section: cap test-runner workers at 2 in the repo config, run one heavy job at a time, check free memory first, and read the kernel log after a crash."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-25T20:42:39-05:00"}
seq: 16
kind: "user-rule"
components: ["rule/global-claude-md"]
evidence: ["judgment"]
watches: []
test: ""
asked: "2026-10-25: that has happened MANY times. you need to add claude.md rules - dont run the system out of memory or CPU with uncheck vitest etc"
proof: []
unmeasured: ""
---

## Change

`claude/.claude/CLAUDE.md` gains a `## Machine Load` section after Quality Checks, with four rules:

- Cap test-runner workers at 2 in the repo's own config file (vitest, jest, playwright, pytest-xdist), since a flag
  or env var does not reach sessions a script or bench starts.
- Run one test suite, build or bench run at a time; bench arms run one at a time.
- Check free memory before a heavy run; under 8 GB available, wait and report what holds it.
- After a crash or OOM kill, read the previous boot's kernel log before rerunning, and fix the cause first.

## Evidence

On 2026-10-25 at 20:12 the kernel OOM killer fired on home-pc (30 GB, 16 CPUs) and the machine went down. The
final dump held 26.6 GB resident: about 17 GB in about 20 vitest workers from two uncapped runs of a bench
substrate's backend suite, 7.2 GB in 112 `MainThread` processes, 1.9 GB in Claude sessions. The bench session had
tried an env-var cap, which vitest ignored. An earlier OOM kill run hit the same boot on 2026-10-24 at 22:42. The
user reports it has happened many times.

## Result

The section adds 9 lines; the file stays under the 150-line target. The bench substrate now carries
`test.maxWorkers: 2` in `backend/vitest.config.ts`, and its clean suite passes 311/311 in 91 s with 2 workers.

Moved the same day. The user, 2026-10-25: "it should NOT be in my global claude md". The section is deleted from
`claude/.claude/CLAUDE.md`; the same rules now live in `~/agent-evals/CLAUDE.md`, scoped to bench substrates,
where the crash came from.

## Watch

None. No intake number reads memory pressure or OOM kills. If crashes continue, the next step is a hook that refuses
a test command in a repo whose runner config sets no worker cap.

## Back-out

Delete the `## Machine Load` section.
