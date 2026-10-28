---
name: fix
description: Dispatch coder subagents to fix review feedback (from a `/cc` comment handoff, a `/review` handoff, or the conversation), then auto-run `/review`. To act on inline comments left in `~/.claude/claude-comments.md`, use `/cc` — it reads them and routes here.
allowed-tools: [Agent, Bash, Read, Edit, AskUserQuestion]
---

# Fix Code Review Feedback

Thin wrapper over the `review-loop` agent (`mode: fix-first`). A script parses the returned packet, routes on status, renders it, logs the escape and ask rows, and posts the Aikido replies. You dispatch, run the script, and do what its `ACTION:` lines say.

## Modifiers

- `+fast` / `+deep` — pass through verbatim (semantics in `~/.claude/skills/_shared/modifiers.md`; read it only if you are unsure).

## Instructions

1. **Dispatch the loop** in your first response. `Agent` with `subagent_type: "review-loop"`, `model: "sonnet"`. Pass, verbatim:
   - `mode: fix-first`, `caller: fix`
   - `lane: <lane>` when the args name one (`lane: test-audit` from a test audit); else none
   - the findings, from whichever source applies: `/cc` entries (`path`, `line`, `body`, `id` — highest priority, user-authored), a `/review` handoff block, or the conversation
   - any `handoff:` block (schema: `~/.claude/skills/_shared/handoff-block.md`), `iter=N`, and any `+fast` / `+deep` modifier
   - `no-review` if present — the agent then verifies via the execution gate and returns without a reviewer pass

   Invoked bare, with no findings in args and no handoff: if `~/.claude/claude-comments.md` may hold inline comments, point the user at `/cc` rather than parsing that file here.

2. **Run the script on the returned packet.** Decide the flags before you run it; the script applies the rules. It reads the packet a hook saved, for this session, when the loop handed back. Do not paste it. Running the step again repeats no side effect.

   ```bash
   python3 ~/.claude/scripts/review/review_fix.py packet --skill fix --source <conversation|cc|handoff> [--lane <eng-spec|code|test-audit|other>] \
     [--escape "file=<path>|class=<class>|severity=<high|medium|low>|gate_missed=<review|drift-gate|test-intent|stage|coder|eng-spec>|guard=<type|convention|gotcha|rule|check|none|n-a>|desc=<one line>"]... \
     [--aikido "<path>:<line>=<comment_id>"]...
   ```

   - `--source`: where the findings came from. Escapes log only for `conversation`.
   - `--escape`, one per distinct defect: only when the user reported it in conversation, on code a prior `/review` on this branch already passed, and it is a defect, not a new requirement or a change of direction. Pick `guard` from `~/.claude/skills/_shared/escape-ratchet.md` without pausing. `<class>` is one of the classes in the script's `CLASSES` list (`~/.claude/scripts/review/handback.py`); use `other` when unsure. `lane` is `eng-spec` for an eng-spec doc, else `code`. The script logs it only when the status is `converged` or `deferred` and a `fixed[]` entry names the file. When the user reports the defect after the packet ran, log it later with `python3 ~/.claude/scripts/review/review_fix.py escape --escape "..."`; the script records what it logged, so a repeat logs nothing twice.
   - `--aikido`, one per finding that is an Aikido PR comment (`author` is `aikido-pr-checks[bot]`, or the body carries `@AikidoSec` / `app.aikido.dev`, and it has a `comment_id`). The script posts exactly one reply per comment.

   When the packet's first line is `status: converged` or `status: deferred`, put `~/.claude/scripts/review/review-gate-mark clean` in the same response as a second, parallel Bash call. For any other status, never mark. If the gate denies a `clean` mark, leave the gate dirty, tell the user the reason it gave, and do not retry the mark.

3. **Do what the script printed.** Read the `ACTION:` line:

   - `render-and-finish` → say the text between `BEGIN USER TEXT` and `END USER TEXT` verbatim. Report any `LOGGED / POSTED` failure. If any finding needs architectural rethinking, recommend `/eng-spec`. If the gate mark did not run in parallel, run it now as its own Bash command. State a proposed escape guard in your closing line and apply it on approval.
   - `present-asks` → say the user text, then present each ask with its question and its proposed change, and wait. The script already ran nvim-jump. Never auto-fix an ask. After the answers run `python3 ~/.claude/scripts/review/review_fix.py asks-done <accepted|rejected|modified>[:<note>] ...` (the note is accepted and not stored), one outcome per ask in order. When the script's asks-done line names `--packet <packet_id>`, run it as printed. The script supplies each ask's `finding_id` (the id of the loop's logged ask row); an ask it cannot match is logged under a new id.
   - `ask-user-plan-impact` → call `AskUserQuestion` as printed, then run the `decide` command it names. On `ACTION: redispatch`, re-dispatch with the same arguments plus the lines it printed (both counters kept), then run step 2 again. On `ACTION: discuss`, talk it through, then run the `decide` command that it printed for the outcome.
   - `stop` → present what it printed and wait. When it lists asks, run its printed asks-done line after the user answers. Do NOT re-dispatch. The session is correctly left `dirty`.
   - `stop-no-handback` → the loop ended without handing back. Do what the lines say: the first time, re-dispatch `review-loop` once with the same arguments and run step 2 again; the second time, stop and show the user the loop's final text. Never mark clean.
   - `stop-no-reviewer` → the first time, re-dispatch `review-loop` once with the same arguments, the printed `iter=` line in place of any `iter=` line, and run step 2 again; the second time, stop and tell the user no reviewer ran. Never mark clean.
   - `wait-for-loop` → the loop is waiting on an agent or shell it started in the background. Do not re-dispatch and never mark clean. End the turn; when the review-loop's completion notice arrives, run step 2 again.
   - `stop-parse-failure` or `stop-usage` → the packet or the call was bad. If you ran the gate mark in parallel, run `~/.claude/scripts/review/review-gate-mark dirty`. Show the user the problems. Never guess a missing field.

4. **What stays yours:** deciding the `--escape` and `--aikido` flags, judging the user's answer to an ask, acting on accepted asks, the `/eng-spec` recommendation, and the closing line.

## Arguments

$ARGUMENTS
