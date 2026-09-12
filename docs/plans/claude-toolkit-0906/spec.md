# Implementation Plan — Mechanize the Claude toolkit (claude-toolkit-0906)

> Ticket: ./00-ticket.md · Research: ./02-research.md · Decisions: ./03-decisions.md

## Overview

Convert six prose rules in `claude/.claude/CLAUDE.md` and `skills/coder-core/SKILL.md` into deterministic hooks, relocate two sections that cannot be mechanized (Orchestration → a SessionStart-injected file; Communication → a Claude Code Output Style), fix the fail-open defect in the two hand-written PreToolUse gates, and close the propagation sweep. Nine vertical phases, each leaving the toolkit registered, working, and independently checkable.

**Ticket vs. research.** The ticket names `coder*.md` and `code-reviewer*.md` as primary surfaces. The research and the ledger together show almost nothing in those two agent bodies is mechanizable: the handoff-line contract (`BEHAVIOR:`/`WHY:`/`REVIEW:`) can never be gated because no hook ever sees a subagent's report, and the reviewer's Do/Do-NOT-Flag lists are judgment by construction. The mechanizable content those agents rely on lives in `coder-core` and in `settings.json`. So `coder.md`, `coder-deep.md`, `code-reviewer.md` and `code-reviewer-deep.md` receive **no rule changes at all** in this plan (decisions 10 and 11 closed both apparent inconsistencies as justified differences; the sole edit to any of the four is a one-phrase dangling-pointer deletion in both `code-reviewer.md` copies — decision 28); the work lands in `coder-core`, `CLAUDE.md`, `settings.json`, and six scripts. That is a real divergence from the ticket's framing and is stated rather than papered over.

## Data Models

No database. The equivalent persistent state is on-disk, and two new shapes are introduced.

**Quality-check cap state** (new) — `~/.claude/state/quality-check/<session_id>/`

| Path                    | Content                                                                     | Written by                                    | Read by                 |
| ----------------------- | --------------------------------------------------------------------------- | --------------------------------------------- | ----------------------- |
| `<session>/edits`       | empty marker; only its mtime is read                                        | Write/Edit branch, PostToolUse                | Bash branch             |
| `<session>/run-<cksum>` | empty marker; mtime = when that normalized command last ran **in that cwd** | Bash branch, PostToolUse / PostToolUseFailure | Bash branch, PreToolUse |

`<cksum>` is `printf '%s\n%s' "$normalized" "$cwd" | cksum | awk '{print $1}'` — POSIX `cksum`, not `sha256sum`, because macOS lacks the latter (repo is cross-platform). `cwd` comes from the hook payload and separates parallel coders in different worktrees (decision 42). Collision risk is irrelevant: a collision denies a distinct command once, which the batch-fix message already tells the caller how to clear.

Pruning: `find "$HOME/.claude/state/quality-check" -mindepth 1 -mtime +2 -delete 2>/dev/null || true` on every invocation, mirroring `review-commit-gate.sh:63`.

**Review-gate state** (existing, unchanged) — `~/.claude/state/review-gate/<session_id>` and `<session_id>.skip`.

**Telemetry schema change** — `~/.claude/review-findings.jsonl` rows go from `schema_version=2` to `3`. Meaning change: `blocker` may now be set by the tool rather than only by the caller (decision 9). `~/.claude/review-escapes.jsonl` (`log-escape`) stays at `2` — it has no `fix_induced` field.

## Hook Contracts

Deny-tier mechanics are event-determined and non-negotiable (decision 5):

| Tier           | Event        | Mechanism                                                                                                                             | Exit |
| -------------- | ------------ | ------------------------------------------------------------------------------------------------------------------------------------- | ---- |
| deny           | PreToolUse   | `{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"<text>"}}` on **stdout** | 0    |
| block          | PostToolUse  | message on **stderr** (no `permissionDecision` field exists)                                                                          | 2    |
| warn           | either       | message on stderr                                                                                                                     | 0    |
| context inject | SessionStart | `{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"<text>"}}` on stdout                                      | 0    |

Every PreToolUse gate in this plan: `CLAUDE_SKIP_HOOKS` checked first (exit 0), a fail-closed **`EXIT` trap** emitting the deny JSON, `command -v jq >/dev/null || exit 0` fail-open when jq is absent.

**The trap is `EXIT`, not `ERR`, and the flags are `set -Eeuo pipefail`** (decision 40). An `ERR` trap alone does not fail closed:

- Without `set -E` bash does not run an `ERR` trap for a failure inside a shell function, a command substitution, or a subshell — exactly where `deny()` and Phase 3's shared normalize function live. The script just exits 1.
- `set -u` on an unbound variable exits 1 **without** running the `ERR` trap at all, even with `set -E`.

A PreToolUse hook exiting 1 with empty stdout is a non-blocking error — the tool proceeds. So the two likeliest bugs a coder introduces editing these scripts (a typo'd variable, a failure inside a helper) would fail **open**, which is the behavior Phase 1 exists to remove and AC6's second clause names. Phase 1's risk paragraph reasons only about a _syntax_ error, which happens to exit 2 and therefore does block — that coincidence is what hides the hole. The shared shape:

```bash
set -Eeuo pipefail
emitted=0
deny() { emitted=1; jq -cn --arg r "$1" '…'; exit 0; }
fail_closed() {
  local rc=$?
  if (( rc != 0 && emitted == 0 )); then deny "internal error (exit $rc) — failing closed"; fi
  return 0
}
trap fail_closed EXIT
```

The `if`/`fi` and the explicit `return 0` are load-bearing: written as `(( … )) && deny …`, the arithmetic is false on every allow path, `(( ))` then returns status 1 as the function's last command, and the script exits 1 from the trap. `EXIT` fires on every termination path — `ERR`, `set -u`, `set -e`, an explicit `exit 1` — and the `rc != 0` guard means normal allow paths (`exit 0`) emit nothing. Where a gate deliberately fails **open** (`quality-check-cap`'s state errors, decision 18; every `command -v jq || exit 0`), the path already exits 0 and the trap is silent by construction. `quality-check-cap` additionally guards on `$evt`: its `PostToolUse` invocation must never emit a PreToolUse-shaped decision, so `fail_closed` there is `[[ "$evt" == PostToolUse ]] && return 0` first.

New and changed registrations:

| Script                             | Event        | Matcher                                  | Tier                       |
| ---------------------------------- | ------------ | ---------------------------------------- | -------------------------- |
| `shell-write-gate.sh` (new)        | PreToolUse   | `Bash`                                   | deny                       |
| `quality-check-cap.sh` (new)       | PreToolUse   | `Bash`                                   | deny (never records)       |
| `quality-check-cap.sh` (new)       | PostToolUse  | `Bash`                                   | record-only (never denies) |
| `quality-check-cap.sh` (new)       | PreToolUse   | `(Write\|Edit\|MultiEdit\|NotebookEdit)` | allow-only (counter bump)  |
| `emit-orchestration.sh` (new)      | SessionStart | `startup\|resume\|clear\|compact`        | context inject             |
| `git-discipline-gate.sh` (changed) | PreToolUse   | `Bash`                                   | exit-2 → deny JSON         |
| `review-commit-gate.sh` (changed)  | PreToolUse   | `Bash`                                   | exit-2 → deny JSON         |
| `dead-prose-gate.sh` (changed)     | PostToolUse  | `Write\|Edit`                            | warn (unchanged tier)      |

## Reuse Map

**Reused as-is:**

- `claude/.claude/scripts/review-commit-gate.sh:56-66` — the session-state pattern (`$HOME/.claude/state/<gate>/<session_id>`, `mkdir -p`, `find -mtime +2 -delete`). `quality-check-cap.sh` copies this verbatim rather than inventing a state layout.
- `claude/.claude/scripts/git-discipline-gate.sh:33` — the current-branch lookup, for the worktree-prefix rule (decision 7 item 1). Corrected implementation, see Deviations.
- `claude/.claude/scripts/git-discipline-gate.sh:35` — `grep -qsi 'direct-edit repo' CLAUDE.md` exemption. It is scoped to the **main/master rule only** and stays that way: the worktree-prefix rule lands in the same script but outside that exemption, because an unrenamed `worktree-` branch is wrong in a direct-edit repo too. The two rules share the script and the branch lookup, not the exemption.
- `claude/.claude/scripts/warn-skip-hooks.sh:7` — the working precedent for JSON-on-stdout at SessionStart; `emit-orchestration.sh` follows its shape.
- `claude/.claude/scripts/dead-prose-gate.sh` — existing PostToolUse registration and `.claude/(agents|skills)` file-scope filter; the portability check (decision 7 item 2) is a second `grep` block inside it, **no new script, no new registration**.
- `claude/.claude/skills/_shared/finding-log.md:40` — the already-written specification of the `fix_induced=bug ⇒ blocker` rule; phase 6 implements exactly it and edits nothing about its meaning.
- `claude/.claude/skills/review/log-review-finding:120-129,141-153` — the existing validation-block idiom (`jq -r` field read, `case` on the value, mutate `$json` with `jq -c`); the promotion is one more block in that style.
- `claude/.claude/scripts/claude-doctor.sh:114-153` — the agent-frontmatter scan loop; the `*-deep` and reviewer-calibration checks extend that loop rather than opening a new pass over `agents/*.md`.
- `claude/.claude/scripts/claude-doctor.sh:81-92` — the `for pair in "script:label"` registration-check idiom; new expected registrations are added as entries in that list.
- `omp/.omp/agent/hooks/pre/claude-security-bridge.ts:59-75` — the `PRE_TOOL_GATES` map. Both new PreToolUse gates are added there, each in the phase that creates it.

**New units introduced:**

- `scripts/quality-check-cap.sh` — no existing script correlates a Bash invocation with an edit counter; `review-commit-gate.sh` is the closest and correlates a _dispatch_ with a commit, a different key and a different event pair.
- `scripts/shell-write-gate.sh` — `bash-safety-gate.sh` is the only command-string gate and is off-limits (CB-generated, no generator; ledger Constraints). No hand-written command-string gate exists to extend.
- `scripts/emit-orchestration.sh` — `warn-skip-hooks.sh` emits `systemMessage`, not `additionalContext`, and is conditional on an env var; there is no existing file-to-context injector.
- `orchestration.md`, `output-styles/laconic.md` — content files, not code.

## Deviations from existing patterns

1. **`git-discipline-gate.sh` branch lookup changes from `git rev-parse --abbrev-ref HEAD` to `git symbolic-ref --short -q HEAD`.** Verified live (evidence class: **exercised**): on a repo with no commits, `rev-parse --abbrev-ref HEAD` prints the literal string `HEAD` and exits 128, so the existing main/master check silently never fires on an unborn branch and the new `worktree-` check would inherit the same hole. `symbolic-ref --short -q` returns the branch name on an unborn branch and empty on detached HEAD, which is the correct answer in both cases. The ledger (decision 7) says "the branch lookup already exists in that script" — it does, and it is wrong; this is a correctness fix inside the reuse, not a new mechanism.
2. **`quality-check-cap.sh` does not fail closed on state errors, and its `EXIT` trap denies on the Bash PreToolUse branch only.** The tier rule from decision 5 mandates a fail-closed trap on PreToolUse gates; this gate takes two documented exemptions. (a) The Write/Edit marker branch has no deny semantics — failing closed there would deny every file edit in the session over a bookkeeping error — so `fail_closed` returns 0 for that `tool`. (b) Every state-directory operation is `|| exit 0` (decision 18): this gate enforces a productivity rule, not a security rail, and an unwritable state directory failing closed would deny _every_ quality-check command, not just repeats. Those paths exit 0, so the `rc != 0` guard keeps the trap silent without a special case. The trap still denies on the Bash branch for any other failure — **on the PreToolUse event only**; the PostToolUse recording branch has no deny semantics either, so `fail_closed` returns 0 there (decision 37). `git-discipline-gate.sh` and `review-commit-gate.sh` keep the unqualified fail-closed behaviour — the distinction is what the gate protects.
3. **Quality-check detection is anchored to the start of a command segment.** Not in the ledger; forced by the use/mention problem the ledger itself documents (decision 8's `git commit`-in-prose incident). Without anchoring, `jq -n --arg c "npm test" ...` registers a run of `npm test`. Anchoring makes the token have to _be_ the command, which is also the rule's actual meaning.

## Phase Status

- [x] Phase 1 — Fail-closed migration of the two hand-written PreToolUse gates, plus the worktree-prefix rule (risk: high)
- [x] Phase 2 — `shell-write-gate.sh`: close the shell-write bypass (risk: high)
- [x] Phase 3 — `quality-check-cap.sh`: the 2-run cap on a no-edit-between-runs boundary (risk: high)
- [x] Phase 4 — Orchestration leaves `CLAUDE.md` (risk: high)
- [x] Phase 5 — Laconic Output Style, and `caveman` removed (risk: high)
- [x] Phase 6 — `fix_induced=bug` auto-promotes to `blocker` (risk: low)
- [x] Phase 7 — Portability warn, and the Git section relocates to `rules/git.md` (risk: high)
- [x] Phase 8 — `claude-doctor.sh` structural checks (risk: low)
- [x] Phase 9 — Propagation sweep and the opencode `code-reviewer.md` port (risk: high)

## Implementation Steps

### Phase 1 — Fail-closed migration of the two hand-written PreToolUse gates, plus the worktree-prefix rule

Implements decisions 5 and 7 item 1. Sequenced first because both gates currently fail **open**: a bug in either silently permits an unreviewed commit or a commit on `main`. Doing it first also means every later phase's own commits run under the corrected gates.

**Self-gating risk — real, and this is where it lives.** `review-commit-gate.sh` mediates every `git commit` in this repo. After this edit its `EXIT` trap fails closed, so **any** non-zero exit in the edited script — a syntax error, an unbound variable, a failed helper — denies all commits until fixed. That is wider than the old `ERR`-only reading and is the intended behaviour (decision 40). Mitigation, in order: (a) run the Phase 1 automated verification **before** attempting any commit; (b) `bash -n <script>` both files as a pre-flight; (c) this repo is `direct-edit repo`, so `git-discipline-gate`'s main-branch rule is exempt here and cannot compound the failure; (d) if the gate does jam, the recovery is fixing the script — not `CLAUDE_SKIP_HOOKS`, which disarms the credential and force-push rails too.

**File**: `claude/.claude/scripts/git-discipline-gate.sh`

- **Change `set -euo pipefail` to `set -Eeuo pipefail`** (decision 40), then add `[[ -n "${CLAUDE_SKIP_HOOKS:-}" ]] && exit 0`.
- Add the `emitted`/`deny()`/`fail_closed`/`trap … EXIT` block from Hook Contracts verbatim, with the message `[git-discipline-gate] internal error (exit <rc>) — failing closed. Report this to the user.`
- Replace all three `echo ... >&2; exit 2` sites with `deny "<same message>"`. Message text is unchanged.
- **Close the parse fail-open at line 17.** `cmd=$(jq -r '.tool_input.command // ""' 2>/dev/null) || exit 0` allows the command whenever the hook JSON fails to parse — the trap cannot reach it, because the `|| exit 0` makes the exit status zero. It becomes `cmd=$(jq -r '.tool_input.command // ""' 2>/dev/null) || deny "hook input did not parse — failing closed. Report this to the user."`. The `command -v jq || exit 0` line above it stays fail-open by design (decision 40): a missing interpreter is an environment gap, a malformed payload is not.
- Replace `branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)` with `branch=$(git symbolic-ref --short -q HEAD 2>/dev/null || true)`, and hoist it above the commit check so the new rule can use it.
- New rule, after the `--amend` rule and **outside the `direct-edit repo` exemption** (that exemption guards the main/master rule only): if the command matches `\bgit\s+(commit|push)\b` **and** `$branch` matches `^worktree-`, deny with: `[git-discipline-gate] branch '<branch>' still carries the auto-generated worktree- prefix. Rename it to the plain TICKET-NUM-desc form and push it with -u first, then retry.`
- Update the header comment: the numbered rule list goes to four items, **and** the closing line `Blocks with exit 2 (stderr is fed back to the model). Fails open when jq is missing…` becomes `Denies via PreToolUse decision JSON. Fails closed on internal error; fails open when jq is missing.` — after this phase the exit-2 sentence describes behaviour the script no longer has. No rationale prose (house rule).

**File**: `claude/.claude/scripts/review-commit-gate.sh`

- **Change `set -euo pipefail` to `set -Eeuo pipefail`** (decision 40), then add `[[ -n "${CLAUDE_SKIP_HOOKS:-}" ]] && exit 0`.
- Add the same `emitted`/`deny()`/`fail_closed`/`trap … EXIT` block. Declare `evt=""` **before** the `jq` parse and make `fail_closed` return early on `[[ "$evt" == PostToolUse ]]` — the trap must not emit a PreToolUse decision on a PostToolUse event, and a failure during the arm step has no deny semantics. Initialising `evt=""` means a failure _during_ `input=$(cat)` on a PostToolUse invocation would still take the deny branch; that is harmless (PostToolUse ignores `permissionDecision` and the exit is 0) but note it in the script comment rather than leaving the next reader to rediscover it.
- Replace the one `echo ... >&2; exit 2` with `deny "<same message>"`.
- Leave the state machine, the skip-marker semantics, and the header untouched.

**File**: `omp/.omp/agent/hooks/pre/claude-security-bridge.ts`

- Header comment only, two edits, no code change this phase:
  - Delete the `mechanical-check-gate.sh` paragraph under "Deliberately skipped" (the script does not exist — ledger Constraints, architect correction 4).
  - Line 25 reads `spec-budget-gate / stub-guard / log-* / notify / formatters — not security.` Drop `stub-guard / ` from that list. It is the **second** `stub-guard` site (decision 32); Phase 2 deletes the first (`CLAUDE.md:62`) and Phase 9's regex matches both, so leaving this one makes the sweep print FAIL.

#### Automated Verification:

```bash
# The literal trigger words are split so this command's own string does not
# trip the gate under test (git-discipline-gate regexes the full command string).
c="git st""ash"; jq -n --arg c "$c" '{tool_input:{command:$c}}' > /tmp/gd1.json
bash ~/.claude/scripts/git-discipline-gate.sh < /tmp/gd1.json \
  | jq -e '.hookSpecificOutput.permissionDecision == "deny"'

# The trap actually fails closed — the property Phase 1 exists to deliver.
# Feed malformed JSON so the jq parse fails inside a command substitution:
# without set -E and an EXIT trap this exits 1 with empty stdout and the tool PROCEEDS.
echo 'not json' | bash ~/.claude/scripts/git-discipline-gate.sh \
  | jq -e '.hookSpecificOutput.permissionDecision == "deny"'
echo 'not json' | bash ~/.claude/scripts/review-commit-gate.sh \
  | jq -e '.hookSpecificOutput.permissionDecision == "deny"'
# and the flags are present in both, or the trap silently misses functions and subshells
grep -q 'set -Eeuo pipefail' ~/.claude/scripts/git-discipline-gate.sh
grep -q 'set -Eeuo pipefail' ~/.claude/scripts/review-commit-gate.sh
```

```bash
d=$(mktemp -d); git -C "$d" init -q -b worktree-foo
c="git com""mit -m x"; jq -n --arg c "$c" '{tool_input:{command:$c}}' > /tmp/gd2.json
( cd "$d" && bash ~/.claude/scripts/git-discipline-gate.sh < /tmp/gd2.json ) \
  | jq -e '.hookSpecificOutput.permissionDecisionReason | test("worktree-")'
```

```bash
mkdir -p ~/.claude/state/review-gate && echo dirty > ~/.claude/state/review-gate/rcg-probe
c="git com""mit -m x"
jq -n --arg c "$c" '{hook_event_name:"PreToolUse",session_id:"rcg-probe",tool_input:{command:$c}}' > /tmp/rcg.json
bash ~/.claude/scripts/review-commit-gate.sh < /tmp/rcg.json \
  | jq -e '.hookSpecificOutput.permissionDecision == "deny"'
```

```bash
bash -n ~/.claude/scripts/git-discipline-gate.sh && bash -n ~/.claude/scripts/review-commit-gate.sh
```

All three `jq -e` commands fail today: the current scripts write to stderr and exit 2, so stdout is empty and `jq -e` exits non-zero. The worktree probe additionally has no matching rule today.

#### Manual Verification:

- Make a trivial edit in this repo and commit. It must succeed (this repo is `direct-edit repo`, no coder dispatched). If it is denied, the trap or the exemption grep regressed — do not proceed to Phase 2.

### Phase 2 — `shell-write-gate.sh`: close the shell-write bypass

Implements decision 4. Independent of Phase 1.

**File**: `claude/.claude/scripts/shell-write-gate.sh` (new, `chmod +x`)

- Standard preamble: `set -Eeuo pipefail`, `command -v jq >/dev/null || exit 0`, and the `emitted`/`deny()`/`fail_closed`/`trap … EXIT` block from Hook Contracts (decision 40). Session-launch skip: `[[ -n "${CLAUDE_SKIP_HOOKS:-}" ]] && exit 0`.
- `cmd=$(jq -r '.tool_input.command // ""')`; empty → exit 0.
- **Narrow escape, in band** (decision 38, replacing decision 17's `CLAUDE_SKIP_SHELL_WRITE`): immediately after reading `$cmd`, `grep -qF '#skip-shell-write-gate' <<<"$cmd" && exit 0`. The escape is a trailing comment on the command itself — `printf x >> tracked.txt  #skip-shell-write-gate` — because a PreToolUse hook is spawned by Claude Code in Claude Code's own environment **before** the command runs: an env-var prefix on the denied command is inert text inside `.tool_input.command` and never reaches the hook process. A shell comment is the only channel that carries per-command intent into a PreToolUse gate.
- Fast path: `grep -qE '(-[a-zA-Z]*i|inplace|>|tee)' <<<"$cmd" || exit 0`. The `[a-zA-Z]*` is required — a literal `-i` does not match `sed -ri` or `perl -pi`, and a fast path that misses them makes the deny rules below unreachable for exactly the forms most likely to be used.
- Split `$cmd` into segments on `|`, `||`, `&&`, `;`, newline. Trim each.
- **In-place editors (unconditional deny).** For each segment, after stripping a leading `time ` / `env VAR=val ` prefix, deny if the segment's command word is `sed`/`gsed` and the segment contains `(^|[[:space:]])-[a-zA-Z]*i([[:space:]]|$|\.|')`, or command word is `perl` with a `-[a-zA-Z]*i` flag and `-p` or `-n`, or command word is `awk`/`gawk` with `-i[[:space:]]*inplace`. Message: `[shell-write-gate] in-place editing of <target> bypasses the Write/Edit hook pipeline and leaves no reviewable diff. Use the Write or Edit tool.` — **`<target>` is required** (AC3 says the denial names the file, for in-place editors as well as redirects): take the segment's last non-flag, non-script argument, and fall back to the literal segment text when no argument parses out.
- **Redirection and `tee` (deny only when the target is git-tracked).** From the whole command, extract candidate targets with a redirection regex plus a `tee` regex. For each: strip the operator/`tee`/`-a` prefix, strip surrounding quotes, skip empty, skip anything starting `&`, skip `/dev/*`, expand a leading `~` to `$HOME`. Then `git -C "$(dirname -- "$t")" ls-files --error-unmatch -- "$(basename -- "$t")" >/dev/null 2>&1` — on success, deny with `[shell-write-gate] <target> is git-tracked. Shell writes bypass the Write/Edit hook pipeline (formatters, safety gate) and leave no reviewable diff. Use the Write or Edit tool.`
- **Both deny messages end with** ` If this deny is wrong (a > inside a quoted string or heredoc, an unrecognized wrapper), re-run the command with a trailing #skip-shell-write-gate comment — it disarms this gate for that one command.` (decisions 34 and 38.)
- **The model may not add that comment on its own initiative.** `## Safety Rails`' stop-and-report rule governs: a deny is reported to the user, and only the user authorizes the escape. This is a rule, not a mechanism — the gate cannot tell who appended the token.
- Untracked targets, new files, `/tmp/*`, and build output all pass. `/tmp/check.log` (required by Phase 3) is untracked by construction.

**File**: `claude/.claude/settings.json` — append to the existing `PreToolUse` / `Bash` hooks array, after `review-commit-gate.sh`: `bash ~/.claude/scripts/shell-write-gate.sh`.

**File**: `omp/.omp/agent/hooks/pre/claude-security-bridge.ts` — add `"shell-write-gate.sh"` to `PRE_TOOL_GATES.bash.gates`, and name it in the header's "Covered gates" `PreToolUse(Bash)` line. **Same phase, or it does not exist under omp.**

**File**: `claude/.claude/CLAUDE.md` — **narrow** the first bullet of `## Tools`, do not delete it. The gate denies only when `git ls-files --error-unmatch` succeeds, so creating a **new** file from the shell (`cat > src/thing.ts <<EOF`, `printf … > newfile`) is untracked, allowed by the gate, and would be covered by no rule at all if the bullet went away — the heredoc case the bullet names first, and the one where bypassing the formatter and stub-guard pipeline costs most, because there is no prior version to diff against. The tracked-file half is mechanized and comes out; the new-file half stays as prose. The bullet becomes: `- Creating a NEW file from the shell (heredoc, redirection) bypasses the Write/Edit hook pipeline — use Write. Writes to files already tracked are denied by shell-write-gate.` The dead "stub-guard" reference goes with the deleted half. Add "shell writes to tracked files" to `## Safety Rails`' blocked list, and add `shell-write-gate` to that paragraph's script list.

**Do not put `quality-check-cap` in that same list** (decision 35, and Phase 3 follows the same rule). `## Safety Rails` says "never work around a block … report it to the user and stop", which is right for a security rail and wrong for a productivity gate whose own deny message tells you to fix and re-run — the Deviations section already classes `quality-check-cap` as the latter. Instead add a **separate line** below that paragraph, naming **only this phase's gate** — Phase 3 appends its own to the same line when it lands, and a phase never writes a token for a gate that does not exist yet: `Workflow gates (advisory, not rails — their deny message says what to do next, and each has a narrow escape you append to the command as a comment, on the user's say-so): shell-write-gate (#skip-shell-write-gate).` **Name the tokens, never `CLAUDE_SKIP_*`** (decision 38) — an env variable cannot reach a PreToolUse hook, so a CLAUDE.md line advertising one would instruct the model, at the exact moment of a false deny, to retry with something no gate reads. `shell-write-gate` is named in both places deliberately: it enforces a real bypass of the hook pipeline _and_ has a routine false-positive case with a narrow escape.

#### Automated Verification:

The probe must contain a literal `>>` and a literal `sed -i`, which this gate is designed to deny in the _probing_ command itself. Put the probe in a file and run the file — the gate then sees only `bash /tmp/swg-probe.sh`, which is clean.

Write `/tmp/swg-probe.sh` (via the Write tool) with exactly:

```bash
#!/usr/bin/env bash
set -u
G=~/.claude/scripts/shell-write-gate.sh
tracked="$HOME/dotfiles/README.md"
jq -n --arg c "echo hi >> $tracked" '{tool_input:{command:$c}}' > /tmp/swg1.json
jq -n --arg c "echo hi > /tmp/scratch.log" '{tool_input:{command:$c}}' > /tmp/swg2.json
jq -n --arg c "sed -i 's/a/b/' $tracked" '{tool_input:{command:$c}}' > /tmp/swg3.json
bash "$G" < /tmp/swg1.json | jq -e '.hookSpecificOutput.permissionDecision=="deny"' >/dev/null || { echo "FAIL: tracked redirect not denied"; exit 1; }
[ -z "$(bash "$G" < /tmp/swg2.json)" ] || { echo "FAIL: scratch redirect denied"; exit 1; }
bash "$G" < /tmp/swg3.json | jq -e '.hookSpecificOutput.permissionDecision=="deny"' >/dev/null || { echo "FAIL: sed -i not denied"; exit 1; }
echo OK
```

then:

```bash
bash /tmp/swg-probe.sh
```

Expected `OK`. Today it prints `FAIL: tracked redirect not denied` — the script does not exist, so `bash "$G"` errors and the `jq -e` fails.

```bash
jq -e '[.hooks.PreToolUse[] | select(.matcher=="Bash") | .hooks[].command] | any(test("shell-write-gate"))' ~/.claude/settings.json
grep -q 'shell-write-gate.sh' ~/dotfiles/omp/.omp/agent/hooks/pre/claude-security-bridge.ts
# narrow escape is IN BAND — it must travel inside the command, not the environment (decision 38)
jq -n '{hook_event_name:"PreToolUse",tool_name:"Bash",tool_input:{command:"echo x >> claude/.claude/CLAUDE.md  #skip-shell-write-gate"}}' > /tmp/swg2.json
test -z "$(bash ~/.claude/scripts/shell-write-gate.sh < /tmp/swg2.json)"
# and the env form must NOT be what the message advertises — no gate reads it
grep -q 'CLAUDE_SKIP_SHELL_WRITE' ~/.claude/scripts/shell-write-gate.sh && echo "FAIL: inert env escape" || echo OK
```

#### Manual Verification:

- **In a fresh session** (hooks are snapshotted at session start; a registration this phase adds does not fire in the session that added it). Ask the session to append a line to a tracked file with `>>`. Expect a deny naming the file, and the model routing to Edit.
- Run any ordinary `cmd > /tmp/x.log` and any `git diff > /tmp/d.patch`. Both must pass.

### Phase 3 — `quality-check-cap.sh`: the 2-run cap on a no-edit-between-runs boundary

Implements decision 1.

**File**: `claude/.claude/scripts/quality-check-cap.sh` (new, `chmod +x`)

- Preamble as Phase 2: `[[ -n "${CLAUDE_SKIP_HOOKS:-}" ]] && exit 0`, and this gate's own in-band escape token `#skip-quality-cap`, tested against `$cmd` on the Bash branch (decision 38 — see Phase 2 for why an env variable cannot work here). The token is stripped before normalization so it never changes the key. Read the whole payload once **into a variable**, as `review-commit-gate.sh` does — `input=$(cat)`, then every parse is `jq -r '…' <<<"$input"`. Stdin is consumed by the first read, so a second bare `jq` on stdin returns nothing and the Bash branch would never deny. `tool=$(jq -r '.tool_name // ""' <<<"$input")`, `session=$(jq -r '.session_id // "unknown"' <<<"$input")`, `evt=$(jq -r '.hook_event_name // ""' <<<"$input")`.
- `root="$HOME/.claude/state/quality-check"; dir="$root/$session"`. **State setup fails open** (decision 18): `mkdir -p "$dir" 2>/dev/null || exit 0`, and every subsequent state read/write is `|| exit 0` rather than trap-denied. Prune `find "$root" -mindepth 1 -mtime +2 -delete 2>/dev/null || true`.
- **Branch A — `tool` is `Write`/`Edit`/`MultiEdit`/`NotebookEdit`:** `touch "$dir/edits"; exit 0`. Never denies; `fail_closed` returns 0 for this `tool` (see Deviations).

  **A marker file, not a counter** (decision 39). A read-modify-write counter (`n=$(cat …); echo $((n+1)) > …`) sits on the hot Write/Edit path, where Claude Code dispatches parallel Edit calls that each spawn their own hook process. Two concurrent increments drop one; a dropped increment leaves the counter equal to the stamp, which is a **false deny** reading `nothing has been edited since` when something was — the same false-deny-on-a-lie class decision 37 was written to remove, surviving in the other half of the state machine. `touch` is idempotent and races harmlessly.

- **Branch B — `tool` is `Bash`. Split across two events** (decision 37): PreToolUse **reads and denies but never records**; PostToolUse **records but never denies**. The segment-matching and normalization below are shared by both — factor them into one function and branch on `$evt` only at the last step. A command is recorded when it has actually run, never when it was merely attempted.
  - `cmd=$(jq -r '.tool_input.command // ""' <<<"$input")`; empty → exit 0.
  - Split on `|`, `||`, `&&`, `;`, newline. For each segment: trim; strip a leading run of `time `, **bare `[A-Za-z_][A-Za-z0-9_]*=[^ ]* ` assignments**, `env [A-Za-z_][A-Za-z0-9_]*=[^ ]* `, `npx `, `pnpm exec `, `yarn dlx `, `bunx `.

    The **bare** assignment form is not optional. Stripping `env FOO=1 ` but not `FOO=1 ` leaves any env prefix as a silent, undocumented bypass of the whole gate — `FOO=1 npm test` stops anchor-matching and is never capped.

  - Match the segment **anchored at its start** against the quality-check table: `(npm|pnpm|yarn|bun) (run )?(test|lint|typecheck|type-check|check|build)`, `jest`, `vitest`, `pytest`, `tsc`, `eslint`, `ruff`, `mypy`, `go (test|vet)`, `golangci-lint`, `cargo (test|clippy|check)`, `make (test|lint|check|typecheck)`, `(bundle exec )?rspec`, `phpunit`, `dotnet test`, `mvn test`, `gradle test`, `shellcheck`, `luacheck`, `stylua`.
  - Non-matching segment → skip.
  - Normalize a matching segment: delete `2>&1`, delete any `>>?[[:space:]]*[^[:space:]]+`, collapse runs of whitespace, trim. (Pipe suffixes are already gone via segmentation — this is what makes `npm test`, `npm test | tail -5`, and `npm test > /tmp/check.log 2>&1` one key.)
  - `key=$(printf '%s\n%s' "$norm" "$(jq -r '.cwd // ""' <<<"$input")" | cksum | awk '{print $1}')` — **the working directory is part of the key** (decision 42). PreToolUse hooks fire on subagent tool calls, and the orchestration rules explicitly sanction parallel coders in separate worktrees. Keying on the command alone would make coder B's first `npm test` deny because coder A already ran it in a different tree. The `edits` marker stays per-session and undimensioned: an edit anywhere in the session unlocking a re-run is the fail-open direction this gate already accepts, and per-cwd edit markers would mean an orchestrator edit never unlocks a coder's run.
  - **On `evt` = `PostToolUse`:** `touch "$dir/run-$key"`, continue to the next segment, `exit 0` at the end. This branch never denies and never emits a decision — a PostToolUse hook has no deny semantics for a command that already ran, and the whole point of recording here is that it ran.
  - **On `evt` = `PreToolUse`:** if `[[ "$dir/run-$key" -nt "$dir/edits" ]]` — the command last ran more recently than the last edit — deny (Pattern H — the instruction is in the message): `[quality-check-cap] '<norm>' already ran this session and nothing has been edited since. Re-running unchanged code cannot produce a different result. Redirect the failing run to /tmp/check.log, read the WHOLE log, fix every failure in one batch, then run it once more. If it still fails after that batch fix, stop and ask the user. If this deny is wrong, re-run the command with a trailing #skip-quality-cap comment — it disarms this gate for that one command.`

  The escape clause is part of the message, not optional (decisions 34 and 38). `CLAUDE_SKIP_HOOKS` also disarms the credential-read and force-push rails, so the narrow escape is what keeps a routine false deny off the session-wide bypass; the deny message is the only moment the user needs it. As in Phase 2, the model reports the deny and the user authorizes the token.
  - Otherwise continue to the next segment. Exit 0 if no segment denied. **Nothing is written on this event** — that is the whole of decision 37.

**Edit marking moved to PostToolUse.** On PreToolUse a Write the user rejects still touched `edits` — only a fail-open (a wasted re-run, never a false deny), but recording an edit that never landed made the two halves of the cap inconsistent. Both markers now move only after the tool actually ran, at the cost of one extra bridge branch.

**`-nt` granularity is the accepted cost** (decision 39). On a filesystem with 1-second mtime resolution, an edit and a run landing in the same second compare as not-newer and the run is allowed — a fail-open in a one-second window, the direction this design already declares it wants ("Deliberate bias toward allowing"). ext4, btrfs and APFS are nanosecond, so this is theoretical on all four supported platforms. Bash `[[ a -nt b ]]` is **true** when `a` exists and `b` does not, which gives the intended shape for free: on a fresh session the first PreToolUse finds no `run-<key>` and allows; PostToolUse touches it; the second PreToolUse finds `run-<key>` with no `edits` yet and denies.

**File**: `claude/.claude/settings.json` — append `bash ~/.claude/scripts/quality-check-cap.sh` to four arrays: `PreToolUse`/`Bash` (after `shell-write-gate.sh`), a new `PostToolUse`/`(Write|Edit|MultiEdit|NotebookEdit)` entry, and `PostToolUse`/`Bash` plus `PostToolUseFailure`/`Bash` entries (decision 37 — the recording half; Claude Code fires `PostToolUseFailure`, not `PostToolUse`, on a non-zero exit).

**File**: `omp/.omp/agent/hooks/pre/claude-security-bridge.ts` — two changes, same phase:

- Add `"quality-check-cap.sh"` to `PRE_TOOL_GATES.bash.gates` only — the edit marker is recorded on `tool_result`, not before the edit.
- **Extend the existing `pi.on("tool_result", …)` handler** (currently `claude-security-bridge.ts:261-281`, which returns early on `event.toolName !== "task" || event.isError`). First **hoist `const cwd = ctx?.cwd ?? process.cwd();` to the top of the handler** — it is currently declared after both early returns (`claude-security-bridge.ts:265`), so a branch placed above them cannot see it. Then add a `bash` branch **before** that early return: `runGate("quality-check-cap.sh", { hook_event_name: "PostToolUse", session_id: SESSION_ID, tool_name: "Bash", tool_input: { command: event.input?.command ?? "" } }, cwd)`. The command key is `input.command` — the same field `PRE_TOOL_GATES.bash` already forwards as `tool_input.command` for the PreToolUse gates. Add a second branch for the edit marker: on a non-error `write`/`edit`/`ast_edit` result, run the same gate with `tool_name` mapped to `Write`/`Edit` and an empty `tool_input`.

  **This branch must NOT test `event.isError`.** Copying the task handler's `isError` guard is the natural mistake and it inverts the gate: the cap exists to stop a re-run of a **failing** check, so filtering out errored results means a failing `npm test` is never stamped, the PreToolUse half never denies, and the cap is a no-op under omp — the exact AC14 failure this branch is here to prevent. A passing check is rarely re-run, so the error case is the only one that matters.

- Update the header's "Covered gates" block, including a `PostToolUse(Bash)  quality-check-cap.sh` line.

**File**: `claude/.claude/CLAUDE.md` — in `## Quality Checks & Failure Budget`: delete the "max TWO runs per task…" bullet entirely (mechanized; the batch-fix instruction now ships in the deny message). Keep the opening sentence. Reword the remaining bullet to stand alone: `- Any other failing approach: max 3 attempts, then stop and ask.` **Append** `quality-check-cap (#skip-quality-cap)` to the **workflow-gates** line Phase 2 introduces below `## Safety Rails` — that line names only `shell-write-gate` until this phase lands. Not the rails script list itself (decision 35).

**File**: `claude/.claude/skills/coder-core/SKILL.md` — delete the `## Quality Check Cap (HARD RULE)` heading and the rule statement; the deny message carries what the coder needs at the moment it needs it. **One clause survives the deletion** (decision 33) — the variant-gaming clause, which is _not_ mechanized: decision 1's own trade-off states the normalizer is a maintained list stripping only pipe suffixes, `2>&1` and `> file`, so argument variation cksums differently and silently unlocks a free run. That is the gate's known blind spot and the clause is the only thing covering it. **It is not kept in place** — its single home is Implementation Workflow step 2, written out below; there is no second copy under the deleted heading.

**The clause's only home is Implementation Workflow step 2** — leaving it where the heading was orphans it at the tail of `## Reuse Before You Write (HARD RULE)`, an unrelated rule. Step 2 currently reads `**Verify your work** — run quality checks per the Quality Check Cap below`, which dangles anyway. One edit closes the pointer and rehomes the residual; step 2 becomes:

`2. **Verify your work** — run the project's quality checks. Variants of the same check (extra flags, an added path arg, "run test" vs "test") are the same command — do not vary one to buy another run.`

**Dangling `2-run cap` pointers** (decision 28) — this phase deletes the rule those five sites point at, so each loses the phrase in the same phase. Every one is a pointer deletion inside an existing sentence or list, not a rule change:

- `claude/.claude/agents/test-writer.md:44-45` and `opencode/.config/opencode/agents/test-writer.md:44-45` — `**Run the suite** (subject to the quality-check 2-run cap in \`~/.claude/CLAUDE.md\`) and read the failures.`becomes`**Run the suite** and read the failures.`(the opencode copy is byte-identical apart from the`AGENTS.md` path, which the deletion removes anyway).
- `claude/.claude/agents/code-reviewer.md:120` and `opencode/.config/opencode/agents/code-reviewer.md:121` — drop `, 2-run cap on quality checks` from the parenthesised generic-rules list. Nothing else on the line changes. This is the one place this plan touches a `code-reviewer.md` body, and it is deliberately narrow: the no-edit boundary in decision 8 covers _rules_, and the repo's propagation sweep obliges the fix regardless (decision 28).
- `claude/.claude/skills/deps/SKILL.md:35` — `Quality checks (2-run cap).` becomes `Quality checks.`

#### Automated Verification (pointer sweep):

```bash
git -C ~/dotfiles grep -in '2-run cap' -- claude omp opencode && echo "FAIL: dangling pointer" || echo OK
```

Fails today: **seven** tracked sites carry the phrase — the five listed above plus `CLAUDE.md:72` (removed by this phase's own reword) and `coder-core/SKILL.md:57` (removed with the `## Quality Check Cap` section). Count verified with `git grep -c '2-run cap' -- claude opencode`; every one is owned by this phase.

#### Automated Verification:

```bash
S="qc-probe-$$"
jq -n --arg s "$S" '{hook_event_name:"PreToolUse",session_id:$s,tool_name:"Bash",tool_input:{command:"npm test"}}' > /tmp/qc1.json
jq -n --arg s "$S" '{hook_event_name:"PreToolUse",session_id:$s,tool_name:"Bash",tool_input:{command:"npm test 2>&1 | tail -5"}}' > /tmp/qc2.json
jq -n --arg s "$S" '{hook_event_name:"PreToolUse",session_id:$s,tool_name:"Edit",tool_input:{file_path:"/tmp/x.ts"}}' > /tmp/qc3.json
# the recording half — same command, PostToolUse (decision 37)
jq -n --arg s "$S" '{hook_event_name:"PostToolUse",session_id:$s,tool_name:"Bash",tool_input:{command:"npm test"}}' > /tmp/qc4.json
G=~/.claude/scripts/quality-check-cap.sh
test -z "$(bash $G < /tmp/qc1.json)"                                              # 1st attempt allowed
test -z "$(bash $G < /tmp/qc1.json)"                                              # STILL allowed — PreToolUse records nothing
bash $G < /tmp/qc4.json; test -z "$(bash $G < /tmp/qc4.json)"                     # it ran; PostToolUse records, never denies
bash $G < /tmp/qc2.json | jq -e '.hookSpecificOutput.permissionDecision=="deny"'  # now denied; pipe-variant is the same command
bash $G < /tmp/qc3.json                                                           # an edit lands
test -z "$(bash $G < /tmp/qc1.json)"                                              # re-run now allowed
bash $G < /tmp/qc4.json                                                           # arm the deny again, via the run event
jq -n --arg s "$S" '{hook_event_name:"PreToolUse",session_id:$s,tool_name:"Bash",tool_input:{command:"npm test  #skip-quality-cap"}}' > /tmp/qc5.json
test -z "$(bash $G < /tmp/qc5.json)"                                              # narrow escape is IN BAND, decision 38
grep -q 'CLAUDE_SKIP_QUALITY_CAP' $G && echo "FAIL: inert env escape" || echo OK
jq -n --arg s "$S" '{hook_event_name:"PreToolUse",session_id:$s,tool_name:"Bash",tool_input:{command:"FOO=1 npm test"}}' > /tmp/qc6.json
bash $G < /tmp/qc6.json | jq -e '.hookSpecificOutput.permissionDecision=="deny"'  # bare env prefix is NOT a bypass
test -z "$(HOME=/nonexistent-probe bash $G < /tmp/qc2.json)"                      # unwritable state fails OPEN, decision 18
```

Line 2 is the ALT's whole point and the one line that fails against the single-event design: a command that was attempted but never ran must not arm the deny.

Fails today: the script does not exist, so line 1's `test -z` sees a `No such file` error and a non-zero exit.

```bash
jq -e '[.hooks.PreToolUse[] | select(.matcher | test("Write")) | .hooks[].command] | any(test("quality-check-cap"))' ~/.claude/settings.json
# 4 map entries (bash, write, edit, ast_edit) plus header lines — >= 4, not == 4
test "$(grep -c 'quality-check-cap.sh' ~/dotfiles/omp/.omp/agent/hooks/pre/claude-security-bridge.ts)" -ge 5
# the omp recording half exists, or the cap is a no-op under omp (decision 37, AC14)
grep -q 'quality-check-cap.sh' <(sed -n '/pi.on("tool_result"/,/^  });/p' ~/dotfiles/omp/.omp/agent/hooks/pre/claude-security-bridge.ts)
# ...and it does not filter out failing runs, which are the only ones that matter
test "$(sed -n '/pi.on("tool_result"/,/quality-check-cap.sh/p' ~/dotfiles/omp/.omp/agent/hooks/pre/claude-security-bridge.ts | grep -c 'isError')" -eq 0
# the DENY half's own registration — every functional probe above runs the script directly and passes without it
jq -e '[.hooks.PreToolUse[] | select(.matcher=="Bash") | .hooks[].command] | any(test("quality-check-cap"))' ~/.claude/settings.json
jq -e '[.hooks.PostToolUse[] | select(.matcher | test("Bash")) | .hooks[].command] | any(test("quality-check-cap"))' ~/.claude/settings.json
grep -q 'Quality Check Cap' ~/.claude/skills/coder-core/SKILL.md && echo "FAIL: section still present" || echo OK
```

#### Manual Verification:

- **In a fresh session** (hooks are snapshotted at session start; the three registrations this phase adds do not fire in the session that added them). Run a project's test command twice with no intervening edit. Second run denied, message names `/tmp/check.log` and the batch fix.
- **The same two runs under omp** — start an omp session, run a project's check twice with no edit between, confirm the second is denied. This is the **only** behavioural check of AC14 anywhere in the plan; every automated check is a grep over the bridge source and passes even if omp emits no bash `tool_result` at all (see External Contracts). A failure here means the recording half never fires and the cap is a no-op under omp — do not mark the phase done on the greps alone.
- Edit a file, run it again. Allowed.

### Phase 4 — Orchestration leaves `CLAUDE.md`

Implements decisions 2 and 3.

**File**: `claude/.claude/orchestration.md` (new) — the current `CLAUDE.md:41-58` verbatim (the `### Delegation` and `### Workflow Routing` subsections), under a top-level `# Orchestration` heading. **Not** `# Orchestration (main session only)`: Phase 9's sweep regexes that exact string as a retired term, so reusing it here makes the sweep unpassable forever (the defect class decision 20 removed). The qualifier was load-bearing only inside `CLAUDE.md`, where subagents also read the file; this file reaches nothing but the main session. Drop the `**Subagents: this entire section binds…skip it**` banner — no subagent receives this file, so the disclaimer is dead on arrival.

**File**: `claude/.claude/scripts/emit-orchestration.sh` (new, `chmod +x`)

```bash
#!/usr/bin/env bash
set -euo pipefail
command -v jq >/dev/null || exit 0
f="$HOME/.claude/orchestration.md"
if [[ -r "$f" ]]; then
  jq -Rs '{hookSpecificOutput:{hookEventName:"SessionStart",additionalContext:.}}' "$f"
else
  # Decision 19: a missing file must not fail silently — the session would run
  # with no routing rules and nothing would say so until a doctor pass.
  jq -cn '{hookSpecificOutput:{hookEventName:"SessionStart",additionalContext:"WARNING: ~/.claude/orchestration.md is missing or unreadable. Workflow-routing rules are NOT loaded this session. Tell the user before routing any work."}}'
fi
```

**File**: `claude/.claude/settings.json` — new `SessionStart` block, matcher `"startup|resume|clear|compact"`, one hook `bash ~/.claude/scripts/emit-orchestration.sh`. **All four sources, none optional** (decision 31): `compact` or the routing rules vanish at the first compaction of a long session; `clear` or they vanish on every `/clear`, which is the more frequent of the two. The two SessionStart blocks already in `settings.json` use match-all matchers — `""` (`warn-skip-hooks.sh`, `calibration-guard.sh`) and `"*"` (`herdr-agent-state.sh`) — so this plan is the first to enumerate sources here. An enumeration that omits a source is a silent hole, and AC7 names none of them.

`additionalContext` is **appended to** the session's context, not merged with or overriding any CLAUDE.md — a project CLAUDE.md that contradicts a routing rule is still in context and still wins by the Precedence section's own ordering (project CLAUDE.md > global). Relocating the Orchestration section out of the global file does not change where it sits in that order; nothing in this plan gives injected context precedence it did not have as global-CLAUDE.md prose.

**File**: `claude/.claude/CLAUDE.md` — delete `## Orchestration (main session only)` (lines 37-58). Add a two-line `## Where the rest lives` section: orchestration and workflow routing → `~/.claude/orchestration.md`, injected at session start, main session only.

**File**: `claude/.claude/skills/coder-core/SKILL.md:16` — delete the first clause (`Skip the ## Orchestration … not you.`); keep the rest of the line verbatim: `Do not re-delegate coding, and do not run /review or spawn a reviewer; your REVIEW: handoff line (below) is the only review signal you produce.`

**File**: `claude/.claude/agents/test-writer.md:58` — replace with `- **Never dispatch agents.**` (the sentence referencing CLAUDE.md's Orchestration section is deleted).

**File**: `opencode/.config/opencode/agents/test-writer.md:58` — the same dangling reference, pointing at `AGENTS.md` (the symlink to this same `CLAUDE.md`), so it dangles for the same reason and dies in the same phase (decision 27). Replace with `- **Never dispatch agents** (the tool is \`Task\`).` — the tool-name clause is an opencode adaptation and stays.

**opencode:** knowingly not compensated (decision 3). `opencode/.config/opencode/AGENTS.md` is a symlink to this same `CLAUDE.md`, so opencode's main agent loses the routing rules. No opencode-side hook is built.

#### Automated Verification:

```bash
test -f ~/.claude/orchestration.md
bash ~/.claude/scripts/emit-orchestration.sh | jq -e '.hookSpecificOutput.additionalContext | test("Workflow Routing")'
# missing-file half warns rather than exiting silently (decision 19)
HOME=/nonexistent-probe bash ~/.claude/scripts/emit-orchestration.sh \
  | jq -e '.hookSpecificOutput.additionalContext | test("WARNING")'
jq -e '[.hooks.SessionStart[] | select(.matcher | test("clear") and test("compact")) | .hooks[].command] | any(test("emit-orchestration"))' ~/.claude/settings.json
grep -q 'Orchestration (main session only)' ~/.claude/CLAUDE.md && echo "FAIL: still in CLAUDE.md" || echo OK
grep -q 'Skip the `## Orchestration' ~/.claude/skills/coder-core/SKILL.md && echo "FAIL: skip line remains" || echo OK
# both test-writer copies, not just the claude one (decision 27)
git -C ~/dotfiles grep -n '## Orchestration' -- claude omp opencode && echo "FAIL: dangling reference" || echo OK
```

All six fail today.

#### Manual Verification:

- Start a fresh session and ask "which lane do I use for cleanup on pre-existing repo debt?" The `/refactor audit <dir>` answer must be available without reading any file.
- Dispatch any subagent and confirm from its behaviour/report that it did not receive the routing rules (expected, and the point).

### Phase 5 — Laconic Output Style, and `caveman` removed

Implements decisions 12, 13, 14. `~/.claude` is a whole-directory symlink into the stow package, so a new `output-styles/` directory appears live with no `install/stow` change.

**Scope change this phase makes, stated the way Phase 4 states its own** (decision 41): an Output Style rewrites the **main session's** system prompt. A subagent receives its own agent file plus `CLAUDE.md` — not the active output style. Today every coder, reviewer and researcher reads the ten laconic paragraphs because they sit in `CLAUDE.md`; after this phase none of them do. This is accepted, not overlooked: agent bodies carry their own report formats, and the Communication rules were written for chat prose. It matters for AC17, whose kill condition ("did prose visibly get terser?") will be judged in a session where the subagents that produce much of the prose have stopped receiving the directive — judge the main session's own output, not agent reports.

**File**: `claude/.claude/output-styles/laconic.md` (new)

```
---
name: Laconic
description: Shortest correct answer. Verdict first, no preamble, no closing summary.
keep-coding-instructions: true
---
```

**`keep-coding-instructions: true` is load-bearing and must not be dropped** (decision 29). Selecting a custom output style _replaces_ Claude Code's built-in software-engineering system prompt unless this key is set — the key exists only because the default is to drop it. This style relocates a prose-style directive; it is not a role change, so the coding instructions must survive. Evidence class **exercised-by-precedent**: the only output style installed on this machine, `~/.claude/plugins/marketplaces/simple-english/output-styles/simple-english.md:4`, is a prose-only style and carries the flag for exactly this reason. Every automated check in this phase passes with or without the key, and AC17 only asks whether prose got terser — so the failure is silent and session-wide, and the plan is the only thing that can prevent it.

Body = `CLAUDE.md:11-32` verbatim (the laconic paragraphs, starting `Laconic mode. Answer in as few words…` and ending with the `Never refer to a decision or phase by number` paragraph).

**File**: `claude/.claude/settings.json`

- Add top-level `"outputStyle": "Laconic"` (must match the frontmatter `name`).
- Delete `"caveman@caveman": true` from `enabledPlugins`.
- Delete the entire `caveman` object from `extraKnownMarketplaces`.
- `simple-english@simple-english` stays enabled for its skill and is never selected as the style.

**File**: `claude/.claude/CLAUDE.md` — delete `## Communication` (lines 7-32). Add to `## Where the rest lives`: prose style → the `Laconic` output style.

**File**: `claude/.claude/skills/brief/SKILL.md:81-82` — the `## Boundaries` section names the plugin this phase deletes. The sentence is **wrapped across two lines** (`:81` ends `…decides what exists` and `:82` is the single word `at all.`), so replace **both** lines with the one line `This skill decides what exists at all, not how it is worded.` A line-81-only replacement leaves an orphan `at all.` behind, and this phase's `git grep -in caveman` still passes. Leave line 80 untouched. Without this edit the plugin is gone while a live skill still documents composing with it (decision 23).

**Kill condition**, recorded here and nowhere else (it is rationale, so it does not go in any agent or skill body): if the style does not visibly change output in normal use, the next pass deletes the directive rather than relocating it a fourth time.

#### Automated Verification:

```bash
jq -e '.outputStyle == "Laconic"' ~/.claude/settings.json
jq -e '.enabledPlugins | has("caveman@caveman") | not' ~/.claude/settings.json
jq -e '.extraKnownMarketplaces | has("caveman") | not' ~/.claude/settings.json
test -f ~/.claude/output-styles/laconic.md
# decision 29: without this key the built-in coding system prompt is silently dropped
grep -q '^keep-coding-instructions: true$' ~/.claude/output-styles/laconic.md
grep -q '^## Communication' ~/.claude/CLAUDE.md && echo "FAIL" || echo OK
# git grep -i, NOT grep -rn: tracked files only (the untracked skill-usage.jsonl
# logs every past `caveman` invocation and always will), and case-INSENSITIVE —
# the prose reference in brief/SKILL.md capitalizes it (decision 23).
git -C ~/dotfiles grep -in caveman -- claude opencode omp && echo "FAIL: caveman reference remains" || echo OK
```

#### Manual Verification:

- Restart Claude Code. `/output-style` lists `Laconic` and shows it active.
- No caveman persona text in the session-start banner; `/caveman` is gone from the command list.

### Phase 6 — `fix_induced=bug` auto-promotes to `blocker`

Implements decision 9.

**File**: `claude/.claude/skills/review/log-review-finding`

- `SCHEMA_VERSION=2` → `3` (line 90).
- Inside the existing `if [ "$kind" = finding ]` block (after the `class` validation), add:

  ```bash
  if [ "$(jq -r '.fix_induced // ""' <<< "$json")" = bug ]; then
    json=$(jq -c '.blocker = "yes"' <<< "$json")
  fi
  ```

- Header comment: line 51's `blocker=yes|no  (optional, 'fix' only)` gains `— set automatically when fix_induced=bug`; the `fix_induced` line (75) states the promotion is applied by this script.

**File**: `claude/.claude/skills/_shared/finding-log.md:40` — reword so the doc and the tool cannot disagree: `**fix_induced=bug** — the tool sets blocker=yes; a loop-introduced bug cannot defer. Set actioned=fixed.`

`scripts/log-escape` is untouched and stays at `schema_version=2` — it has no `fix_induced` field.

**File**: `claude/.claude/skills/audit/review.md:11` — the sentence `Every live row carries `schema_version`(currently`2`)` is **already false before this phase** (`log-spec-run` writes `1`; `log-scan`, `log-review-metrics`, `log-review-finding` and `log-escape` write `2`) and this phase makes it false a second way. Replace the parenthetical with a per-source statement: `Every live row carries a `schema_version`, and the current version differs by source — check the writing script rather than assuming one number across all four logs.` The archive-filter sentence that follows is unchanged and still correct.

#### Automated Verification:

```bash
REVIEW_FINDINGS_FILE=/tmp/rf-probe.jsonl bash ~/.claude/skills/review/log-review-finding \
  kind=finding gate=code-reviewer class=bug fix_induced=bug disposition=fix actioned=fixed desc="probe" >/dev/null
jq -e 'select(.desc=="probe") | .blocker=="yes" and .schema_version==3' /tmp/rf-probe.jsonl
```

Fails today: `blocker` is absent and `schema_version` is 2.

#### Manual Verification:

- Confirm any `/audit review` query that aggregates blockers across history filters on `schema_version` or knowingly mixes eras.

### Phase 7 — Portability warn, and the Git section relocates to `rules/git.md`

Implements decision 7 item 2 and the band-2 half of decision 6.

**File**: `claude/.claude/scripts/dead-prose-gate.sh`

- **Split the single early-exit line into two scopes.** Today one line does both jobs: `echo "$FILE" | grep -qE '\.claude/(agents|skills)/.*\.md$' || exit 0` is simultaneously the file filter and the rationale check's scope. Widening it in place would silently extend the rationale check to `commands/`, which the ledger does not authorize. So: the early exit widens to `\.claude/(agents|skills|commands)/.*\.md$` (portability applies to all three), and the rationale `HITS` block gains its own guard — run it only when `$FILE` also matches `\.claude/(agents|skills)/.*\.md$`. Two checks, two scopes, one file filter.
- New block after the existing one: `PORT=$(grep -nE '/Users/|/home/[a-z]|\bdotfiles\b' "$FILE" 2>/dev/null)`. If non-empty, warn on stderr: `dead-prose-gate: hardcoded path or repo name in <basename> — agents, skills and commands must be portable across WSL/Ubuntu/macOS/Arch:` (**not** "rules": the early exit does not match `rules/`, and this phase writes new content into `rules/git.md`, so naming a scope the check does not have would misreport what was verified). followed by the indented hits. Warn tier, `exit 0` unchanged.

**File**: `claude/.claude/rules/git.md` — append the two bullets moved out of `CLAUDE.md`: "Keep diffs focused: one logical change per task." and the worktree-prefix rule (rename to `TICKET-NUM-desc`, then `git push -u origin <branch>` before doing any work). `paths: []` means this file loads unconditionally, so this is consolidation of the git conventions into their single home, **not** a token saving — the ledger's D5 designates `rules/` as the band-2 destination and `git.md` was already the sole home of the naming convention.

**File**: `claude/.claude/CLAUDE.md` — delete the whole `## Git` section: bullet 1 moves to `rules/git.md`, bullet 2 duplicates `## Safety Rails`, bullet 3 moves to `rules/git.md` (its enforcement half landed in Phase 1). **Add to `## Where the rest lives`**: git conventions → `~/.claude/rules/git.md`. AC8 requires every removed section to leave a pointer, and this is the third and last one (decision 24).

#### Automated Verification:

```bash
mkdir -p ~/.claude/agents
printf 'Read /home/someone/thing.md for details.\n' > ~/.claude/agents/zz-portprobe.md
jq -n '{tool_input:{file_path:"'"$HOME"'/.claude/agents/zz-portprobe.md"}}' > /tmp/dp.json
bash ~/.claude/scripts/dead-prose-gate.sh < /tmp/dp.json 2>&1 | grep -q 'hardcoded path'
```

Fails today (no such check). Delete `~/.claude/agents/zz-portprobe.md` afterwards with `git -C ~/dotfiles clean -f claude/.claude/agents/zz-portprobe.md`. Write/Edit cannot delete a file and bare `git clean` is a no-op without `-f`; if the probe survives, Phase 8's doctor errors on its missing frontmatter and Success Criterion 1 fails. The same applies to Phase 8's own `~/.claude/rules/zz-probe.md`.

```bash
grep -q 'worktree-' ~/.claude/rules/git.md
grep -q '^## Git$' ~/.claude/CLAUDE.md && echo "FAIL: Git section remains" || echo OK
```

#### Manual Verification:

- Edit any agent file to contain `/Users/someone/` and confirm the warning appears without blocking the write.

### Phase 8 — `claude-doctor.sh` structural checks

Implements decision 6's doctor pass, decision 11's `*-deep` rule, and the two doctor mitigations the ledger names in the trade-off blocks of decisions 2 and 10. Pattern G: structural properties that are not per-tool-call events belong in the doctor, not a hook.

**File**: `claude/.claude/scripts/claude-doctor.sh`

- Section 2b: add expected registrations to the `for pair in ...` list — `emit-orchestration.sh:orchestration context injection`, `shell-write-gate.sh:shell-write bypass gate`, `quality-check-cap.sh:quality-check repeat-run cap`. **Not** the phrase `2-run cap` (decision 30): `claude-doctor.sh` lives under `claude/`, which is inside the scope of Phase 3's and Phase 9's `git grep -in '2-run cap' -- claude omp opencode` checks, so that label would make both of them print FAIL against a correct tree and send the coder hunting a dangling reference this plan told them to create.
- New check inside the existing `agents/*.md` loop (section 4):
  - `*-deep.md` shape: body line count (everything after the closing `---`, blank lines excluded) > 15 **and** no line matching `Read .*\.claude/agents/` → `print_warn "agents/$base.md: deep variant body is $n lines and does not delegate — bodies over 15 lines must Read their base agent"`.
  - **No reviewer-calibration-reference check** (decision 26). Seven of the thirteen `*reviewer*.md` agents legitimately carry no such reference — the five `*-deep` variants delegate calibration transitively by reading their base agent, and `plan-reviewer`/`test-reviewer`/`test-intent-reviewer` are not calibration-style reviewers at all — so a "must reference" warn fires permanently on healthy files, which this phase's own manual step calls a defect. No property in the tree discriminates the six that must carry it from the seven that must not, so the check would need a hand-maintained allowlist. `calibration-refs-guard.sh` already covers the regression that actually happened (an agent naming a heading the calibration file no longer has).
- **Replacing it, in new section 4d** (whole-tree, so no allowlist): if `agents/*reviewer*.md` yields **zero** files containing `reviewer-calibration.md` → `print_warn "no reviewer agent references reviewer-calibration.md — calibration-refs-guard.sh is now a no-op"`. This is the failure decision 10's trade-off names — a future reader converting the reviewers to a `skills:` preload and silently disabling the guard — and it is the half of that mitigation that has an oracle. A per-file "this one lost its reference" warn does not.
- New section 4b, `rules/` validation: for each `rules/*.md` — error if the file has no `---` frontmatter block; error if the frontmatter has no `paths:` key; error if the body (after frontmatter) has no non-blank line. Content is **not** linted (decision 6: ESLint/tsc own those rules).
- New section 4c, orchestration wiring: `orchestration.md` exists **and** `emit-orchestration.sh` appears in the settings blob → success; otherwise `print_warn "orchestration rules are not wired — the main session will silently have no routing rules"`.
- No `GENERATED`-marker check (decision 15: a warn that fires forever for a state nobody intends to fix trains the reader to skim doctor output).

#### Automated Verification:

```bash
bash ~/.claude/scripts/claude-doctor.sh > /tmp/doctor.log 2>&1; echo "exit=$?"
grep -q 'rules/' /tmp/doctor.log
grep -qi 'orchestration' /tmp/doctor.log
grep -q 'registered: scripts/quality-check-cap.sh' /tmp/doctor.log
# 4d: present in the script, AND silent on a healthy tree (decision 36 — the silence
# check alone passes identically whether 4d was implemented or skipped)
grep -q 'calibration-refs-guard.sh is now a no-op' ~/.claude/scripts/claude-doctor.sh
grep -q 'calibration-refs-guard.sh is now a no-op' /tmp/doctor.log && echo "FAIL: warns on healthy tree" || echo OK
```

The `rules/`, orchestration, `quality-check-cap` registration and 4d-present lines all fail today (no such checks exist); the 4d silence line passes today and after, and is a regression guard, not an implementation check. Doctor must exit 0 (warnings allowed, errors not).

```bash
printf 'no frontmatter here\n' > ~/.claude/rules/zz-probe.md
bash ~/.claude/scripts/claude-doctor.sh > /tmp/doctor2.log 2>&1; echo "exit=$? (expect 1)"
grep -q 'zz-probe' /tmp/doctor2.log
```

Delete `~/.claude/rules/zz-probe.md` afterwards.

#### Manual Verification:

- Read `/tmp/doctor.log` end to end once. Any warning that is permanent and unfixable is a defect in this phase — remove that check rather than living with the noise.

### Phase 9 — Propagation sweep and the opencode `code-reviewer.md` port

Implements decision 16, and the repo's mandatory toolkit-edit propagation sweep. **Last**, after every claude-side edit has landed, so the reconciliation happens once.

1. **Grep sweep** — for each name this plan changed or deleted, sweep the repo with `git grep` (tracked files only — see the verification block for why `grep -r` is wrong here) and update every consumer: `Orchestration (main session only)`, `## Orchestration`, `Quality Check Cap`, `2-run cap`, `## Communication`, `caveman`, `schema_version`, `git-discipline-gate`, `review-commit-gate`, `stub-guard`. Known consumers already handled in earlier phases: `coder-core/SKILL.md:16`, **both** `test-writer.md:58` copies (claude and opencode — decision 27; the claude one alone is not the whole consumer set), the five `2-run cap` sites in Phase 3, `finding-log.md:40`, the omp bridge header. Fix any residual dangling reference found — including `scripts/agent-model-guard.sh:26`, which cites a `Behavior §` of CLAUDE.md that does not exist. It becomes `# See ~/.claude/orchestration.md — "Agent model discipline".`, the file Phase 4 creates and the section that now carries the rule; do not leave the replacement to coder judgment.
2. **opencode port — verify only; the drift this step was written for is already gone** (decision 22). Commit `0db6d3ee` ("agent trim pass 2") landed **during planning** and synced both copies: the claude copy is 127 lines, the opencode copy 128, both last touched in that same commit, and the opencode side already carries the comment-density rule and the broadened vocabulary rule (tracker references only, not phase numbers, decision IDs, plan paths, or agent provenance). The research this step rested on described the pre-`0db6d3ee` tree and no longer holds.

   So: **diff the two files and confirm every remaining difference is a deliberate adaptation.** Port a hunk only if the diff shows real drift. The adaptations that must survive: `model: opencode-go/mimo-v2.5`, `mode: subagent`, `permission: edit: deny`, hex `color: "#06b6d4"`, `CLAUDE.md` → `AGENTS.md` in all references, and the explicit "Skip its **Persistent Memory** section — opencode agents have no memory directory" clause on the calibration line. This plan's only edit to either `code-reviewer.md` is Phase 3's one-phrase `2-run cap` deletion, applied to both copies symmetrically, so a no-op here is still the expected outcome — not a skipped step.

3. **Inheriting variants** — `code-reviewer-deep.md` delegates by reference and needs no edit; `coder-deep.md` preloads `coder-core` and inherits the Phase 3/4 edits automatically; `coder.md` is unchanged. opencode auto-loads `~/.claude/skills/`, so its coders receive the edited `coder-core` with no port.
4. **Knowingly skipped on the opencode side** — the Orchestration relocation (decision 3: accepted loss, no compensation built), the Laconic output style (no opencode equivalent surface), and all new/changed hook registrations except those the bridge mediates (already done in their own phases).

#### Automated Verification:

```bash
# git grep, NOT grep -r: the live ~/.claude tree carries append-only runtime state
# (file-history/ snapshots, history.jsonl, security-hook-block-log.jsonl,
# settings.json.bak) that quotes these strings by design and gains more matches on
# every session — including the coder's own runs of these commands. All of it is
# untracked or gitignored, so restricting to tracked files excludes it structurally
# instead of by an exclusion list that goes stale (decision 20).
# Every term in step 1's sweep list is checked here. A term named in the prose but
# absent from this regex is a term nothing verifies (decision 25).
git -C ~/dotfiles grep -inE 'Orchestration \(main session only\)|## Orchestration|Quality Check Cap|2-run cap|stub-guard|mechanical-check-gate|caveman|## Communication' \
  -- claude omp opencode && echo "FAIL: dangling reference" || echo OK
# schema_version, git-discipline-gate and review-commit-gate are swept by hand in
# step 1 but deliberately NOT regexed: all three legitimately survive the change
# (the schema key stays, both gates keep their names), so a match is not a defect.
grep -q 'comment' ~/dotfiles/opencode/.config/opencode/agents/code-reviewer.md
grep -q 'AGENTS.md' ~/dotfiles/opencode/.config/opencode/agents/code-reviewer.md
grep -q 'Persistent Memory' ~/dotfiles/opencode/.config/opencode/agents/code-reviewer.md
grep -q 'CLAUDE.md' ~/dotfiles/opencode/.config/opencode/agents/code-reviewer.md && echo "FAIL: CLAUDE.md leaked into port" || echo OK
bash ~/.claude/scripts/claude-doctor.sh >/dev/null 2>&1; echo "doctor exit=$? (expect 0)"
```

The first grep fails today (`Orchestration (main session only)` is live in two files, `## Orchestration` in four, `2-run cap` in **seven** (one occurrence in each of seven tracked files — the same count Phase 3 states, verified with `git grep -c '2-run cap' -- claude opencode`), `stub-guard` in **two** — `CLAUDE.md:60` and `claude-security-bridge.ts:25`, both owned by earlier phases, decision 32 — `mechanical-check-gate` in the bridge). `Orchestration (main session only)` stays in the regex and the new `# Orchestration` heading in Phase 4 does not match it — a single `#` is why. Adding the bare `## Orchestration` alternative is safe for the same reason.

#### Manual Verification:

- Diff the two `code-reviewer.md` files side by side and confirm every remaining difference is a deliberate adaptation, not drift.

## Plan Deviations

### D1 — Phase 2's premise rejected; formatters move to a `Stop` hook (user decision, mid-Phase-2)

**Assumed by the plan.** Decision 4 justified `shell-write-gate` on two grounds: shell writes bypass the Write/Edit hook pipeline, and they "leave no reviewable diff."

**Found.** Both grounds are weaker than the plan assumed, verified against the live hook registry:

1. `bash-safety-gate` independently covers the protected-path cases `write-edit-safety-gate` covers — `sed_inplace_protected`, `tee_redirect_protected`, `scripted_write_protected`, `curl/wget_download_write` (shell profiles, `~/.ssh`, git credentials, cloud credential dirs). Routing edits through Bash costs nothing on the security axis.
2. The "no reviewable diff" ground does not hold for this user's workflow: review happens on `git diff` at the end of a change, not on the in-transcript diff. What is actually lost is the `Write|Edit` PostToolUse set — `prettier-hook.sh`, `eslint-hook.sh`, `comment-bloat-gate`, `dead-prose-gate`, `claudemd-linecount`, `calibration-refs-guard` — plus the `PreToolUse` `spec-budget-gate` / `test-ownership-gate` / `test-edit-telemetry`. All quality/discipline, none security.

**Decision (user).** Move formatting to a `Stop` hook that operates on the turn's changed set instead of gating shell writes. A Stop hook batches (one formatter invocation per turn, not per edit), covers files written by any means including shell, and cannot fire mid-turn and invalidate an `old_string` the model is about to match. Known limits: it does not fire on an interrupted turn, and post-hoc reformatting leaves the model's context holding pre-format content until the next read.

**What changes.**

- New: `claude/.claude/scripts/format-changed.sh`, registered on both `UserPromptSubmit` and `Stop`. `UserPromptSubmit` snapshots the dirty set (tracked diffs vs `HEAD` + untracked) as `<blob-hash> <path>` lines under `~/.claude/state/format-changed/<session>-<repo-cksum>`. `Stop` formats only paths new to the dirty set or whose hash moved — the turn's own changes — so pre-existing hand edits are never reformatted. No snapshot means nothing is formatted. The changed set is grouped by extension, then oxlint/eslint `--fix` and oxfmt/prettier each run once over the batch. The script is silent and always exits 0: `UserPromptSubmit` stdout is injected as context, and a blocking Stop hook re-invokes the model.
- `shell-write-gate.sh` ships after all (user decision): the remaining shell-write bypass is the Write/Edit-only gates, and `test-ownership-gate` is critical. Added rule 0: for any `agent_type`, every redirect/tee target and every argument of an in-place editor, `rm`/`unlink`/`mv`/`cp`/`install`/`truncate`/`touch`/`ln`/`dd`/`patch`, or `git rm|mv|checkout|restore|apply` is resolved against `cwd` and piped to `test-ownership-gate.sh` as a synthetic `Write`. That check runs before, and is not disarmed by, `#skip-shell-write-gate`. It covers new (untracked) test files and test deletion, which rules 1–2 do not. Probe: 17/17 (coder denied on new-file heredoc, `>>`, `rm`, `git rm`, `mv`, `tee`, `cp`, and escaped `sed -i`; allowed on `sed -n`, a `/tmp` log redirect, and a non-test file; main session and test-writer unaffected). Known gap: the omp bridge sends no `agent_type`, so test ownership is enforced under Claude Code only — the same as `test-ownership-gate` itself.
- `prettier-hook.sh` / `eslint-hook.sh` registrations removed (user decision) — `format-changed.sh` supersedes them.
- The `CLAUDE.md` edits Phase 2 made (Tools bullet narrowed, Safety Rails list extended, advisory Workflow-gates line) reference `shell-write-gate` and must be revisited with its fate.
- Downstream phases are unreviewed against this deviation.

**Settings.** The Phase 2 registration and this deviation's `Stop`/`UserPromptSubmit` registrations are applied.

## Constraints

- **No hook can ever see a subagent's report.** PostToolUse(Agent) fires at launch with a metadata stub. `coder-core`'s handoff-line block is permanently prose-only — a ceiling, not a gap.
- **Moving content out of CLAUDE.md removes it from every subagent's context.** SessionStart output is not propagated to subagents. `opencode/.config/opencode/AGENTS.md` is a symlink to `claude/.claude/CLAUDE.md` with no translation layer.
- **Any new PreToolUse gate must be added to `PRE_TOOL_GATES`** in the omp bridge or it silently does not exist under omp.
- **The three CB-generated scripts are off-limits** (`bash-safety-gate.sh`, `block-credential-read.sh`, `write-edit-safety-gate.sh`). No generator is reachable; their `GENERATED — do not edit directly` header is stale and stays stale (decision 15).
- **`CLAUDE_SKIP_HOOKS` is not currently honored by the hand-written tier.** Phases 1–3 add the check to the four scripts they touch; the remaining hand-written gates keep the gap.
- **`CLAUDE_SKIP_HOOKS` is session-wide and disarms the credential-read and force-push rails.** It is never the right unblock for a false deny on a productivity gate. The two new gates each carry a narrow **in-band escape token** instead (`#skip-quality-cap`, `#skip-shell-write-gate` — decision 38; an env variable cannot reach a PreToolUse hook, which is why decision 17's variables were replaced); the security gates deliberately get no narrow escape (decision 17).
- **`calibration-refs-guard.sh` greps reviewer agents for the literal prose line** naming `reviewer-calibration.md`. Replacing that prose with a `skills:` preload silently disables the guard (decision 10 rejected the preload for this reason).
- **`class=` enum is hand-duplicated** between `log-escape` and `log-review-finding`. No shared source; a change touches both.
- **The entire `claude/.claude/` tree is live-symlinked via GNU Stow.** Every edit takes effect immediately in the running session, including the hooks gating the implementer's own tooling.
- **House rule binding this plan's output**: no rationale in agent/skill bodies. Rationale goes in commit messages.

## External Contracts

- **Claude Code hook API** — `PreToolUse` deny requires `hookSpecificOutput.permissionDecision` on stdout with exit 0; `PostToolUse` has no such field and blocks via stderr + exit 2; `SessionStart` injects via `hookSpecificOutput.additionalContext`. Violating the event/mechanism pairing produces a hook that silently does nothing. Evidence class: **exercised** (the existing gates use both forms today).
- **Claude Code Output Styles** — exclusive, one active at a time; `outputStyle` in settings must match the style file's frontmatter `name` exactly or the style silently does not apply. Evidence class: **declared-only** (docs plus the installed `simple-english` example). Phase 5's manual verification is the exercising step and must not be skipped.
- **Claude Code `rules/*.md`** — path-scoped files load when Claude reads a matching file; a file with no `paths` key or `paths: []` loads unconditionally. Evidence class: **exercised** (`rules/git.md` was observed injected verbatim into a subagent dispatch).
- **omp (Oh My Pi) hook bridge** — `claude-security-bridge.ts` shells out to these scripts and depends on the stdin/stdout contract (hook JSON in; `permissionDecision` JSON or exit-2 out). Phases 1–3 preserve it; the Phase 1 migration from exit-2 to deny-JSON is exactly the shape the bridge already handles for the CB gates.
- **git plumbing** — `git symbolic-ref --short -q HEAD` returns the branch on an unborn branch and empty on detached HEAD; `git ls-files --error-unmatch` exits non-zero for untracked paths. Evidence class: **exercised**.
- **omp emits a `tool_result` event for the `bash` tool, with the command in `event.input.command`.** This is what Phase 3's recording half rides on. Evidence class: **declared-only** — `claude-security-bridge.ts:258-282` handles only `toolName === "task"`, and no script in this tree reads a bash `tool_result`; the field name is inferred from `PRE_TOOL_GATES.bash` forwarding `event.input` as `tool_input` on a _different_ event. Every AC14 automated check is a grep over TypeScript and passes whether or not this holds, so **the manual omp step below is the only thing that can falsify it** — if omp emits no bash `tool_result`, or names the field differently, the cap's recording half is a no-op under omp and the PreToolUse half never denies. Upgrade to exercised by running that step before the phase is called done.
- **POSIX `cksum`** — used instead of `sha256sum`, absent on macOS. Evidence class: **declared-only** for the macOS half; the repo is cross-platform by mandate and no macOS machine was available to exercise it.
- **Internal invariant — telemetry identity**: `review-findings.jsonl` rows are keyed by nothing; consumers filter on `schema_version`. Bumping 2→3 means blocker counts are not comparable across the boundary.

## Approaches Considered and Not Taken

1. **One consolidated mega-gate** instead of separate scripts. Destroys per-gate granularity in the omp `PRE_TOOL_GATES` map, makes one bug fail everything closed at once, and produces block messages the model cannot act on because they do not name which rule fired.
2. **A model-judged gate** (SubagentStop → haiku grader over the coder's report). Reintroduces a model as the oracle for a rule the ticket exists to make deterministic, costs a dispatch per coder, and is unbuildable anyway: the report is never in the hook payload.
3. **Deleting `rules/*.md` as unread convention docs.** Refuted on direct evidence — `rules/git.md` was injected verbatim into a subagent's context. Deleting them would lose the branch/commit/PR naming convention outright and remove the cheapest available home for relocated prose.
4. **Moving CLAUDE.md content into auto-memory.** Auto-memory is not enabled and is not a rules-precedence surface; the content would sit outside the precedence chain CLAUDE.md's first section defines.
5. **Session-scoped run counter for the 2-run cap** (deny on the third run). Cheapest to build and a direct copy of `review-commit-gate.sh`, but the granularity is wrong: a multi-phase `/code` session legitimately runs `npm test` once per phase, and the only unblock for a denied _correct_ run is `CLAUDE_SKIP_HOOKS` — session-wide, disarming the credential and force-push rails to let one passing test through.
6. **Deny all shell redirection outside `/tmp`.** Fires on `jq ... > out.json`, generated-file workflows and ordinary build steps many times a day, training the user to run permanently with hooks disabled.
7. **Migrating every gate to stderr + exit 2** for uniformity. Discards the fail-closed `EXIT` trap that is the whole safety property, and cannot apply to the three CB-generated scripts, so it produces a split anyway.
8. **An Output Style for the Orchestration rules** instead of a SessionStart hook. Output styles are exclusive; spending the single slot on a delivery mechanism a hook already provides would permanently lock out the Laconic style.
9. **Converting `_shared/reviewer-calibration.md` into a real skill** and preloading it into all 11 reviewer agents. Saves one tool call per dispatch and silently disables `calibration-refs-guard.sh`, which finds its references by grepping for the prose line — it would report nothing and exit 0 rather than failing loudly.
10. **Normalizing the `*-deep` agents on one inheritance pattern.** Delegation for `coder-deep` spends a Read to deduplicate four lines whose drift risk is nil; duplication for `code-reviewer-deep` reproduces the exact 118-line divergence already observed on the opencode side.
11. **Gating the plain-language vocabulary ban** at deny or warn tier. Fires on _correct_ code (`canary`, `sidecar` are the right nouns in Kubernetes work); the deny version's routine unblock is disarming the whole security rail, and the warn version trains the reader to ignore a script that also carries the rationale checks.
12. **Amending or doctor-checking the stale `GENERATED` marker.** Correct on the merits and rejected on scope and noise: it edits three security-gate files a prose ticket never named, and a doctor warn firing forever on a state nobody intends to fix trains the user to skim doctor output.
13. **Deferring the opencode `code-reviewer.md` port to a separate ticket.** The port would then have to reconcile the August drift _and_ everything this plan changes; deferring a sweep is what produced the current two-generation gap.

## Edge Cases & Error Scenarios

**The toolkit gating itself.** Real, and it bit during planning:

- `bash-safety-gate` denies `printf '{...}' | bash <script>` as pipe-to-shell. Every verification above uses `bash <script> < file`.
- `bash-safety-gate` denies `rm -rf` on a temp directory. Probes leave their temp dirs behind rather than cleaning up.
- `git-discipline-gate` regexes the full command string, so a probe whose _argument_ contains `git stash` is denied. Probes split the literal (`"git st""ash"`).
- After Phase 2, a probe containing a literal `>>` to a tracked path or a literal `sed -i` is denied by the gate under test. Phase 2's probe therefore lives in `/tmp/swg-probe.sh` and is invoked as `bash /tmp/swg-probe.sh`.
- After Phase 3, an unanchored detector would have matched `npm test` inside a `jq --arg`. Segment-start anchoring prevents this for probes and for real work alike.
- **A verification command denied by the gate it is testing is the gate working.** Record it and re-verify via the temp-script form. Never `CLAUDE_SKIP_HOOKS`.

**Phase 1, fail-closed traps on live gates.** `review-commit-gate.sh` mediates every `git commit`; a syntax error after the trap is added denies all commits. Pre-flight `bash -n` both files, run the Phase 1 verification before any commit, and recover by fixing the script.

**Quality-check cap:**

- _No-op re-run of a passing command_ — denied. Intended: the rule caps runs, not failures.
- _Multi-phase `/code` session_ — a legitimate per-phase test run always follows edits, so the counter has advanced and the run is allowed.
- _Edits that are not code_ — a Write to `/tmp` or a docs file bumps the counter and unlocks a re-run. Deliberate bias toward allowing.
- _Normalization miss_ — a check command wrapped in a form the strip list does not handle (`bash -c "npm test"`, a shell function, `xargs`) hashes distinctly and gets a free extra run. Strong filter, not a proof.
- _`unknown` session id_ — a payload with no `session_id` shares one state directory across sessions. Bounded by the 2-day prune.
- _Parallel coders in one session_ — subagent tool calls fire these hooks too, and `cwd` is in the run key (decision 42), so two coders in separate worktrees no longer collide on `run-<key>`. They still **share** the per-session `edits` marker, so coder B's edit can unlock coder A's re-run. Accepted: that direction is fail-open, and per-cwd edit markers would stop an orchestrator's edit from ever unlocking a coder's run. Two coders in the _same_ cwd share both markers by design — they are editing the same tree.
- _Attempted but never run_ — the user rejects the permission prompt, another gate denies the same call, the cwd was wrong, the package name was typo'd. **Resolved by decision 37**: only PostToolUse records, so none of these arm the deny. Under the single-event design every one of them produced a false deny whose stated reason ("already ran … nothing has been edited since") was untrue, and whose only unblocks were an unrelated file edit or an env var the message did not name.
- _The command ran and failed_ — still recorded. Claude Code fires `PostToolUseFailure` (not `PostToolUse`) on a non-zero exit, so the gate is registered on both; omp's `tool_result` fires either way. Recording failures is correct: the run happened, there is output to read, and re-running it unchanged is exactly what the cap exists to stop.
- _State directory unwritable_ — `mkdir -p` fails and the gate exits 0 on both branches (decision 18). The cap silently stops enforcing until the directory is fixed; nothing is denied. This is the one deliberate fail-open in the plan, and Phase 8's doctor is not a detector for it.
- _Narrow escape used_ — a trailing `#skip-quality-cap` comment on the command disables this gate for that one command, leaving every other rail armed (decisions 17 and 38).

**Shell-write gate:**

- _`>` inside a quoted string or a heredoc body_ — may be extracted as a target. If it resolves to a tracked path, a false deny; the message names the file.
- _Variable-indirect targets, `exec >`, targets built by expansion_ — not caught. Known open vector.
- _Target's directory does not exist_ — `git -C` fails, treated as untracked, allowed.
- _Not inside a git repo_ — allowed. Correct: nothing is tracked.
- _`sed -i` writing to an untracked file_ — still denied. In-place editing is unconditional per decision 4.

**Worktree-prefix rule:** fires at the `commit`/`push` verbs, not at worktree creation, so a misnamed branch still exists and is reachable by any path that does not route through those verbs. Detached HEAD yields an empty branch and the rule does not fire.

**`fix_induced=bug` promotion:** a caller passing `fix_induced=bug blocker=no` now gets `blocker=yes` — the tool overrides the caller silently rather than refusing (decision 9 rejected the refuse option). Rows across the `schema_version` 2/3 boundary are not comparable for blocker counts.

**SessionStart orchestration injection:** two failure halves, covered differently (decision 19). If `orchestration.md` is missing or unreadable, the hook injects a WARNING into context instead of exiting silently — the session is told, at the moment it matters, that it has no routing rules. If the hook itself is **unregistered**, nothing runs and nothing can announce it; that half is undetectable from inside the hook and Phase 8's doctor check remains the only detector, on demand. The `additionalContext` payload is not visible in the transcript, so neither half is noticeable by reading the screen.

**Output style:** exclusive slot. Selecting `Laconic` means `simple-english` can never be the active style; its skill remains invokable per document.

**`rules/` delivery:** path-scoped files load only when a matching file is read, not at session start. `git.md` has `paths: []` and loads unconditionally.

## Out of Scope

- The three CB-generated scripts and their stale `GENERATED` header (decision 15).
- Secret-inlining detection — `/security-review` and the `security-guidance` plugin own it (decision 7 item 4).
- The plain-language vocabulary ban — no gate at any tier (decision 8).
- `permissions.deny` additions. Every new rule here needs either state or a computed predicate, neither of which glob patterns express.
- Content linting of `rules/*.md`. ESLint and tsc own those.
- `coder.md`, `coder-deep.md`, `code-reviewer.md`, `code-reviewer-deep.md` bodies and frontmatter — unchanged (decisions 10 and 11).
- An opencode-side equivalent of the Orchestration injection, the Laconic style, or the new hooks beyond the bridge map.
- Any content-level enforcement of coder-core's handoff-line contract. Permanently impossible.
- Removing the empty `skills/code-reviewer-memory/` directory — untracked, not a scope item.

## Refactor Candidates (surfaced for `/refactor`, NOT part of this plan)

1. **`claude/.claude/scripts/` has no test harness at all.** Nine gate scripts carry deny logic; this plan adds two more plus fail-closed traps to two existing ones, all verified by hand-run JSON probes. Resolving refactor: a `scripts/t/` directory of payload fixtures plus one `run-gate-tests.sh`. The probes in this plan's verification sections are the first fixtures, already written. Blast radius: additive.
2. **The `class=` vocabulary is hand-duplicated** between `scripts/log-escape` and `skills/review/log-review-finding`. A drift makes the join silently lossy. Resolving refactor: a single `scripts/finding-vocabulary.sh` sourced by both. Blast radius: two scripts, no schema change.
3. **`test-ownership-gate.sh:39` lists `unified-coder` and `unified-coder-deep`**, agent types with no files anywhere in the repo. Dead branches in a live security-adjacent gate. Resolving refactor: delete the two case entries. Blast radius: one line.
4. **`settings.json` has four separate `PostToolUse`/`Write|Edit` matcher blocks.** Identical matchers split across four objects makes ordering non-obvious. Resolving refactor: merge into one block with an explicit hook order, preserving the current cross-block order.

## Success Criteria

1. `bash ~/.claude/scripts/claude-doctor.sh` exits 0, and `/tmp/doctor.log` shows `registered:` lines for `emit-orchestration.sh`, `shell-write-gate.sh`, and `quality-check-cap.sh`, plus a `rules/` section and an orchestration-wiring line.
2. All Automated Verification blocks in phases 1–9 pass when re-run in order, and each was confirmed to fail against the pre-implementation tree.
3. `wc -l ~/.claude/CLAUDE.md` is under 80 (currently 103), and `grep -E '^## ' ~/.claude/CLAUDE.md` shows `Communication`, `Orchestration (main session only)`, and `Git` are all absent.

   **This criterion measures file length, not context cost, and the two are not the same here** (decision 43). Of the three sections it counts, only `Communication` (to an output style) and `Orchestration` (to a SessionStart injection, main-session only) actually leave the always-loaded set. `## Git` moves to `rules/git.md`, which is `paths: []` and therefore loads unconditionally — the same context, a different file. The move is consolidation into git's single home, which AC8 asks for by name; it is not a reduction, and nothing downstream should read criterion 3's delta as though all three sections were removed from context.

4. In a fresh session: run a project's test command twice with no intervening edit — the second is denied with a message naming `/tmp/check.log` and the batch fix. Edit any file, run it a third time — allowed.
5. In a fresh session: ask the model to append a line to a git-tracked file using `>>` — denied, message names the file, model routes to Edit. Ask it to write `cmd > /tmp/x.log` — allowed.
6. In a fresh session with no prior file read: ask "which lane handles pre-existing repo debt?" — answered as `/refactor audit <dir>` with no file read first.
7. `/output-style` lists `Laconic` and shows it active; the session-start banner carries no caveman persona text and `/caveman` is not a registered command.
8. `REVIEW_FINDINGS_FILE=/tmp/rf.jsonl` + a `kind=finding fix_induced=bug` row yields `blocker=="yes"` and `schema_version==3`.
9. `git -C ~/dotfiles diff --stat` on the branch shows edits confined to: `claude/.claude/{CLAUDE.md,settings.json}`, `claude/.claude/orchestration.md`, `claude/.claude/output-styles/laconic.md`, `claude/.claude/rules/git.md`, `claude/.claude/scripts/{git-discipline-gate,review-commit-gate,dead-prose-gate,claude-doctor,shell-write-gate,quality-check-cap,emit-orchestration,agent-model-guard}.sh` (`agent-model-guard.sh` is the dangling-`Behavior §` fix Phase 9 step 1 names — decision 21), `claude/.claude/skills/coder-core/SKILL.md`, `claude/.claude/skills/brief/SKILL.md`, `claude/.claude/skills/_shared/finding-log.md`, `claude/.claude/skills/audit/review.md`, `claude/.claude/skills/review/log-review-finding`, `claude/.claude/skills/deps/SKILL.md`, `claude/.claude/agents/test-writer.md`, `claude/.claude/agents/code-reviewer.md`, `omp/.omp/agent/hooks/pre/claude-security-bridge.ts`, `opencode/.config/opencode/agents/code-reviewer.md`, `opencode/.config/opencode/agents/test-writer.md`. The last five are the dangling-pointer sweep (decisions 27 and 28); `code-reviewer.md` appears on both sides for a one-phrase deletion only — any hunk larger than that is out of bounds.
