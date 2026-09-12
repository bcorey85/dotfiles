# Design Decisions — claude-toolkit-0906

> Research: ./02-research.md
> Status: 43 numbered decisions, 49 queue items, all resolved. The two numbering
> series are independent — a queue item records a question raised, a numbered
> decision records a choice made, and several queue items resolved without one.
> Cross-references in `spec.md` cite **decision** numbers.

## Queue

- [x] D1. The 2-run quality-check cap — gate it, and on what boundary (session counter vs no-edit-between-runs)? — backend-architect
- [x] D2. Where the Orchestration section goes (stay / SessionStart hook / Output Style / skill) — backend-architect
- [x] D3. Where the shell-write bypass gets closed (unconditional `sed -i` only / + git-tracked redirect targets / wider) — backend-architect
- [x] D4. Which deny convention wins, and whether to migrate the two miscategorized PreToolUse gates — backend-architect
- [x] D5. `rules/*.md` — enforce, delete, or keep-and-populate? — backend-architect
- [x] D6. Which remaining CLAUDE.md rules become gates (worktree prefix / portability / fix_induced / secrets / vocabulary ban) — backend-architect
- [x] D7. `fix_induced=bug` promotion — auto-set, refuse, or leave prose; schema_version consequence — backend-architect
- [x] D8. code-reviewer's calibration read — `skills:` preload or keep the prose line? — backend-architect
- [x] D9. `coder-deep` body duplication vs `code-reviewer-deep` delegation — codify which? — backend-architect
- [x] Q1. Is opencode's main agent expected to hold workflow-routing rules? (D2 consequence) — backend-architect
- [x] Q2. Vocabulary ban conflicts with D-C: warn tier, or hold the deny line? — backend-architect
- [x] Q3. Output Style exclusivity — is `simple-english` ever meant to be selected? — backend-architect
- [x] Q4. Ponytail/caveman already carry terseness — delete the laconic directive rather than relocate it? — backend-architect
- [x] D10. Removing the `caveman` plugin — blast radius (settings, skills, agents, its SessionStart/SubagentStart hooks) — added mid-conversation by user
- [x] Q5. `rules/` `paths:` matching semantics — RESOLVED AS FACT, recorded under Constraints (not a decision: no alternative existed)
- [x] Q6. Already-drifted opencode `code-reviewer.md` — fix in this ticket or file separately? — backend-architect
- [x] Q7. Is the CB YAML generator available? — RESOLVED AS FACT (not available), recorded under Constraints; no alternative existed
- [x] D11. The three CB-generated scripts say "GENERATED — do not edit directly" with no generator and no source — what happens to that marker? (scope question) — surfaced resolving Q7
- [x] D12. False deny on the two new gates — is session-wide `CLAUDE_SKIP_HOOKS` an acceptable unblock, or does each gate need a narrow one? — surfaced by spec-criteria in Phase 6
- [x] D13. `quality-check-cap.sh` with an unwritable state directory — fail closed (deny every check) or fail open? — surfaced by spec-criteria in Phase 6
- [x] D14. SessionStart orchestration injection failing silently — accept the doctor-only detection gap, or announce it? — surfaced by spec-criteria in Phase 6
- [x] D15. Phase 9 sweep grep matches append-only runtime logs and can never pass — how is it scoped? — plan-reviewer BLOCKER, round 1
- [x] D16. Phase 9 step 1 names a file Success Criterion 9's confinement list omits — which one gives? — plan-reviewer BLOCKER, round 1
- [x] D17. Phase 9 step 2's opencode drift premise went stale mid-planning — rewrite or drop the step? — plan-reviewer GAP, round 1
- [x] D18. A live skill documents composing with the plugin Phase 5 deletes, and no check sees it — what changes? — plan-reviewer BLOCKER, round 2
- [x] D19. The deleted Git section gets no Where-the-rest-lives pointer, unlike the other two — add it or accept? — plan-reviewer GAP, round 2
- [x] D20. Phase 9's prose sweep list is wider than the regex that verifies it — reconcile which way? — plan-reviewer NIT, round 2
- [x] D21. Phase 8's reviewer-calibration doctor check warns forever on 7 healthy agents — narrow it or drop it? — plan-reviewer BLOCKER, round 3
- [x] D22. opencode's `test-writer.md:58` carries the same dangling `## Orchestration` reference and no phase edits it — which phase takes it? — plan-reviewer BLOCKER, round 3
- [x] D23. Five live pointers to the 2-run cap dangle once Phase 3 deletes it, two inside a file the plan declares no-edit — fix or reopen the boundary? — plan-reviewer GAP, round 3
- [x] D24. Selecting a custom output style drops the built-in coding system prompt unless a frontmatter key says otherwise — set it or accept? — plan-reviewer BLOCKER, round 4
- [x] D25. Phase 8's doctor label contains a string Phases 3 and 9 sweep as retired — relabel or add an exclusion? — plan-reviewer BLOCKER, round 4
- [x] D26. The SessionStart matcher enumerates three sources and `clear` is not one — add it or accept the hole? — plan-reviewer GAP, round 4
- [x] D27. `stub-guard` has a second site the plan's own count denies exists — who owns it? — plan-reviewer GAP, round 4
- [x] D28. Phase 3 deletes an anti-dodge clause the gate does not actually mechanize — delete anyway or keep a residual? — plan-reviewer GAP, round 4
- [x] D29. The narrow `CLAUDE_SKIP_*` escapes are undiscoverable at the moment of a false deny — surface them where? — plan-reviewer GAP, round 4
- [x] D30. Two new gates join `## Safety Rails`, whose stop-and-report instruction contradicts one of their deny messages — which gives? — plan-reviewer GAP, round 4
- [x] D31. Doctor section 4d has no criterion distinguishing implemented from skipped — add one or accept? — plan-reviewer GAP, round 4
- [x] D32. quality-check-cap records the run before the command executes, so an attempt that never ran arms a false deny — move the recording to PostToolUse, at the cost of an omp bridge path? — plan-reviewer ALT, round 4
- [x] D33. The narrow `CLAUDE_SKIP_*` escapes cannot reach a PreToolUse hook at all — what replaces them? — plan-reviewer BLOCKER, round 5
- [x] D34. The omp recording branch gated on `isError` never stamps a failing check, which is the only case the cap is for — drop the guard? — plan-reviewer BLOCKER, round 5
- [x] D35. Hook Contracts table and Phase 4 state the SessionStart matcher two different ways — which is authoritative? — plan-reviewer GAP, round 5
- [x] D36. Phase 3's deny registration is asserted by nothing; every probe invokes the script directly — add the assertion? — plan-reviewer GAP, round 5
- [x] D37. Phases 2 and 3 manual steps assume a same-session hook edit is live — say "fresh session" as Phases 4 and 5 do? — plan-reviewer GAP, round 5
- [x] D38. The edit counter's read-modify-write races on parallel Edit dispatch and drops increments, producing a false deny — mtime markers instead? — plan-reviewer ALT, round 5
- [x] D39. Round 5's NIT on the `simple-english.md` line number is wrong — the cited line 4 is correct. Rejected, no change. — plan-reviewer NIT, round 5
- [x] D40. An `ERR` trap does not fire for failures in functions, subshells, or on `set -u`, so the fail-closed gates fail open — what trap actually closes them? — plan-reviewer BLOCKER, round 6
- [x] D41. The normalizer strips `env VAR=val ` but not a bare `VAR=val ` prefix, so `FOO=1 npm test` never anchor-matches and bypasses the whole cap — strip it too? — plan-reviewer BLOCKER, round 6
- [x] D42. `spec.md:172` still advertises the `CLAUDE_SKIP_*` escapes by glob after decision 38 replaced them with in-band tokens — name the tokens instead? — plan-reviewer GAP, round 6
- [x] D43. The in-place-editor deny message never interpolates the target file AC3 requires it to name — interpolate it? — plan-reviewer GAP, round 6
- [x] D44. AC4 promises untracked-path shell writes still work, which decision 4's unconditional in-place deny contradicts — reword AC4 or narrow the deny? — plan-reviewer GAP, round 6
- [x] D45. The omp `tool_result` payload shape the PostToolUse recording branch depends on is assumed, never exercised — record it as declared-only and add a behavioural step? — plan-reviewer GAP, round 6
- [x] D46. Phase 2 deletes the whole `## Tools` shell-write bullet, including the new-file and heredoc half the gate does not mechanize — narrow it instead? — plan-reviewer GAP, round 6
- [x] D47. Phase 5 removes the Communication rules from every subagent and the plan never says so, while Phase 4 states its equivalent — state it? — plan-reviewer GAP, round 6
- [x] D48. Parallel coders in separate worktrees collide on the cap's run key, producing a false first-run deny — put `cwd` in the key? — plan-reviewer GAP, round 6
- [x] D49. Success Criterion 3 scores the `## Git` move as a size win, but `rules/git.md` is `paths: []` and loads unconditionally — stop scoring it, or leave the section where it is? — plan-reviewer ALT, round 6

## Resolved

### 1. The 2-run quality-check cap — enforcement boundary

**Choice**: Gate it on **no-edit-between-runs**, not on a session run-counter. A PreToolUse(Bash) hook records each quality-check invocation (normalized) against a monotonic per-session edit counter; a PreToolUse(Write|Edit) hook bumps that counter. A repeat of the same normalized command is denied when the counter has not advanced since that command's previous run. Normalization strips `| tail`, `| grep`, `| head`, `2>&1`, and `> /tmp/...` so the pipe-suffix dodge named in `coder-core:60` resolves to the same command. The deny message carries the batch-fix instruction (Pattern H), not just the refusal.

**Reasoning**: User chose B. The rule's stated intent is "never enter fix-rerun loops" — the defect is re-running without having changed anything, not the absolute count. A legitimate re-run always follows an edit, so the oracle is exact rather than conservative, and the rule needs no task boundary to be correct. My original framing to the architect (that hooks see tool calls but not exit codes, so this may be ungateable) was wrong: the rule caps runs, not failures, and exit codes never enter it.

**Alternatives rejected**:

- _Session-scoped run counter (Pattern C verbatim, deny on 3rd)_ — cheapest to build and a direct copy of `review-commit-gate.sh`, but the granularity is wrong: a multi-phase `/code` session legitimately runs `npm test` once per phase. The user-visible failure is a denied **correct** test run mid-branch, whose only unblock is `CLAUDE_SKIP_HOOKS` — session-wide, disabling every security gate including the credential and force-push gates, to let one passing test through. A gate that routinely trains the user to disarm the whole rail is worse than no gate.
- _Leave as prose_ — the status quo the ticket exists to end; four files restate a rule nothing enforces, and it has demonstrably not held.

**Trade-off accepted**: Two hook registrations instead of one, and per-session state with the same `-mtime` pruning burden as the review gate. A coder that edits via shell rather than Write/Edit evades the counter — closed separately by D3, and if D3 lands narrower than the git-tracked-file test, this evasion path stays open. Command normalization is a maintained list: a check command wrapped in a form the list does not strip reads as a distinct command and gets a free extra run.

### 2. Home for the Orchestration section

**Choice**: Move `## Orchestration (main session only)` out of `claude/.claude/CLAUDE.md` into a stowed, git-tracked file emitted as `additionalContext` by a **SessionStart hook** registered with matchers `startup|resume|compact`. The content stays a plain diffable file the hook `cat`s — the hook is transport, not storage. Delete `skills/coder-core/SKILL.md:16` and `agents/test-writer.md:78` in the same change: both instruct a subagent to skip a section that will no longer reach it.

**Reasoning**: User chose B. 683 words, 44% of CLAUDE.md, injected verbatim into every subagent and then explicitly disclaimed by two of them — the section is paid for on every dispatch and used by none. SessionStart output is not propagated to subagents (verified empirically: the architect's own dispatch received CLAUDE.md and `rules/git.md` but not `warn-skip-hooks.sh`'s systemMessage), which is exactly the delivery boundary this content wants. `warn-skip-hooks.sh:7` is the working precedent for JSON-on-stdout at SessionStart. The `compact` matcher is required, not optional: without it the routing rules vanish at the first compaction of a long session.

**Alternatives rejected**:

- _Leave in CLAUDE.md_ — status quo; the user-visible failure is that every subagent dispatch in the system carries 683 dead words, and the two "skip this section" lines are themselves prose added to work around prose.
- _Output Style_ — survives compaction natively and needs no hook, but output styles are **exclusive**: one active at a time, and the enabled `simple-english` plugin ships one. Selecting an orchestration style permanently locks out every other output style on the machine, including the one the laconic directive (D-A) was headed for. Trading a whole harness slot for a delivery mechanism a hook already provides is a bad exchange.
- _A `/orient`-style skill fetched on demand_ — routing rules must be resident to work. The user-visible failure is circular: the session must already know which lane to use in order to invoke the thing that says which lane to use.

**Trade-off accepted**: One more indirection between the user and a file they read often — the rules are no longer at a fixed path in a single file. If the hook fails or is misregistered the rules are **silently** absent rather than visibly missing, and nothing detects that (candidate `claude-doctor.sh` check). And `opencode/.config/opencode/AGENTS.md` is a symlink to the same CLAUDE.md with no translation layer and no equivalent SessionStart registration, so opencode's main agent loses the routing rules outright — the size and acceptability of that loss is Q1, still open.

### 3. opencode's exposure to the Orchestration move (Q1)

**Choice**: Accept the loss. No opencode-side equivalent is built. When Orchestration leaves CLAUDE.md for the SessionStart hook, opencode's main agent simply stops receiving the workflow-routing rules, and the plan does not compensate.

**Reasoning**: User: "ignore opencode on this one." opencode is not a lane-orchestration surface in practice; the routing rules name skills (`/code`'s dispatch loop, `/review`'s convergence loop, `/eng-spec`'s phases) whose machinery is not wired on that side regardless of whether the prose describing them is present.

**Alternatives rejected**:

- _An opencode-side hook or config injection mirroring the SessionStart delivery_ — real machinery (a second registration, a second thing to keep in sync) built for a surface the user does not orchestrate from. The user-visible failure of building it is maintenance drift: a second copy of the routing rules that silently disagrees with the first, which is the exact failure this repo has already shipped three times in dangling cross-references.
- _`@`-including the orchestration file from AGENTS.md so opencode keeps it_ — cheaper than a hook, but AGENTS.md **is** CLAUDE.md (one inode), so an include added for opencode's benefit is also read by every Claude subagent, re-importing the 683 words the decision exists to remove. It does not work without first splitting the symlink, which is a larger change than the ticket.

**Trade-off accepted**: opencode's main agent operates without written routing rules. If opencode later grows a real orchestration role, this must be revisited — and nothing will signal that moment; it will present as opencode making unrouted choices, not as an error.

### 4. Closing the shell-write bypass

**Choice**: A new hand-written PreToolUse(Bash) gate that (a) denies in-place editors unconditionally — `sed -i`, `awk -i inplace`, `perl -pi` — and (b) denies `>`, `>>`, and `tee` when the resolved target is a **git-tracked** file, tested with `git ls-files --error-unmatch`. Untracked and scratch targets pass, so `/tmp/check.log` (required by D1), build output, and newly created files are unaffected. New script, not an edit to `bash-safety-gate.sh` (generated, off-limits). Registered stdout-JSON + ERR trap + `CLAUDE_SKIP_HOOKS` first, and added to `PRE_TOOL_GATES` in `omp/.omp/agent/hooks/pre/claude-security-bridge.ts` or it does not exist under omp.

**Reasoning**: User chose B. The git-tracked test is not a conservative approximation of the rule — it is the rule's actual oracle. CLAUDE.md's stated concern is that shell writes "bypass the Write/Edit hook pipeline (formatters, stub-guard, safety gate) and leave no reviewable diff"; that is exactly true of a tracked file and exactly false of a scratch file. Also closes D1's named evasion route (a coder that "fixes" via shell instead of Edit).

**Alternatives rejected**:

- _In-place editors only (option A)_ — near-zero false positives but leaves redirection open, which is the more common vector and the one D1 depends on being closed. The user-visible failure is a coder that rewrites a tracked source file with `cat > file` and produces a change no formatter touched and no gate saw.
- _Option B plus standalone heredoc detection_ — a heredoc into `cat > file` **is** the redirection case and is already covered; detecting bare heredocs adds shell-parsing complexity for no additional coverage.
- _Deny all redirection outside `/tmp`_ — this is the shape the ticket's own fuzzy-rule policy (D-C) would produce, and it is wrong here. The user-visible failure is denying `jq ... > out.json`, generated-file workflows, and ordinary build steps many times a day, which trains the user to run with `CLAUDE_SKIP_HOOKS` set permanently — disarming every security gate to work around one over-broad rule.

**Trade-off accepted**: A `git ls-files` call per redirecting command, plus target extraction from compound commands — exotic shell forms (variable-indirect targets, `exec >`, redirections built by expansion) will not be caught, so this is a strong filter, not a proof. It also conflicts with this session's own auto-mode instruction to prefer Bash for file edits: once the gate lands, that route is denied for tracked files and Write/Edit becomes mandatory there.

### 5. Deny conventions — codify the tier rule, migrate the two outliers

**Choice**: Write down the rule that already governs the codebase — **PreToolUse denies via `permissionDecision` JSON on stdout with exit 0, plus a fail-closed `ERR` trap; PostToolUse blocks via stderr + exit 2; the warn tier is a message with exit 0** — and migrate the only two scripts on the wrong side of it: `git-discipline-gate.sh` and `review-commit-gate.sh`, both PreToolUse gates currently using stderr/exit-2. Add an `ERR` trap and a `CLAUDE_SKIP_HOOKS` check to each while there. No bridge change needed (`claude-security-bridge.ts:28-29` already handles both conventions).

**Reasoning**: User chose B. The research's "two conventions coexist, pick one" framing (which I relayed) was wrong: there are three tiers and the tier is determined by the **event**, not by author preference — PostToolUse has no `permissionDecision` field, so `comment-bloat-gate.sh` could never have used stdout-JSON. The genuine defect is narrower and more serious than a style split: both migration targets run `set -euo pipefail` with no trap, so a bug in either exits 1, the harness treats that as a non-blocking error, and the command is **allowed**. The two gates enforcing git-history discipline and the review-before-commit obligation currently fail open. Neither honors `CLAUDE_SKIP_HOOKS`, which contradicts CLAUDE.md's Safety Rails and makes the D-C escape hatch fictional for exactly the gates most likely to false-positive.

**Alternatives rejected**:

- _Leave both conventions documented as-is_ — costs nothing to do and leaves a live ambiguity every time a gate is written, but the real user-visible failure is the fail-open: a syntax error or an unset variable in `review-commit-gate.sh` silently permits an unreviewed commit, and nothing in the system reports that the gate stopped working.
- _Migrate everything to stderr + exit 2_ — uniform, but discards the fail-closed `ERR` trap that is the whole safety property, and cannot be applied to the three CB-generated scripts at all, so it produces a split anyway.

**Trade-off accepted**: Editing two working enforcement gates for a failure mode that has not been observed firing — the change is justified by the fail-open property, not by a logged incident, and there is no test harness under `scripts/` to prove the migration did not break them (research §10: no tests exist). Adding `CLAUDE_SKIP_HOOKS` to these two also genuinely widens the bypass surface: git-discipline and review-commit become disarmable by an env var that previously did not reach them.

### 6. `rules/*.md` — keep, populate, validate

**Choice**: Keep all five files. Designate `claude/.claude/rules/` as the destination for band 2 of the scope — path-scoped prose that cannot be mechanized, which then costs tokens only when its `paths:` match. Add a `claude-doctor.sh` validation pass over the directory (well-formed `paths:` frontmatter, non-empty body) alongside its existing agent/skill checks. Explicitly do NOT build lint enforcement for the rules' content.

**Reasoning**: User chose B. The files are a working harness-level injection mechanism, not dead documentation — `rules/git.md` was injected verbatim into the architect's own subagent context. `rules/git.md` is additionally the sole home for the branch/commit/PR naming convention; it is not duplicated in CLAUDE.md.

**Alternatives rejected**:

- _Delete as unenforced convention docs_ — the premise is false (they load), and the user-visible failure is losing the naming convention entirely plus removing the cheapest available home for the prose that D-B band 2 needs to relocate somewhere.
- _Add bash lint enforcement for the rules' content (braces-required, no `any`, named exports)_ — the most enforcement-looking option and the wrong one. These are ESLint/tsc rules; `frontend-style.md:10` already states the braces rule "will break CI," so the project's own toolchain owns them. The user-visible failure is a hand-rolled bash approximation that disagrees with the real linter — passing the gate and failing CI, or the reverse — for rules the linter already decides correctly.

**Trade-off accepted**: `rules/` gains a structural check but still no content enforcement, so its rules remain advisory. More importantly, the delivery is unverified: the architect could not determine when the harness evaluates `paths:` — `git.md` (`paths: []`) loaded into its dispatch while the four globbed files did not, despite matching file types existing in the repo. Relocating prose here may therefore deliver it to fewer contexts than intended. Tracked as Q5.

### 7. Which remaining CLAUDE.md rules become gates

**Choice**: Take three, skip one; the vocabulary ban is split out as Q2.

1. **Worktree branch prefix** — extend `git-discipline-gate.sh` to deny commit/push verbs when `git rev-parse --abbrev-ref HEAD` starts with `worktree-`. The branch lookup already exists in that script (`:33`). ~6 lines.
2. **Portability / hardcoded paths** — extend `dead-prose-gate.sh` (PostToolUse(Write|Edit), warn tier) to warn when a file under `.claude/{agents,skills,commands}/` contains `/Users/`, `/home/<name>/`, or the literal `dotfiles`. Same event and file scope as the existing checks, so no new script and no new registration.
3. **`fix_induced=bug` ⇒ `blocker=yes`** in `skills/review/log-review-finding` — ~4 lines of jq. Schema consequence resolved separately in D7.
4. **Secret inlining — NOT taken.**

**Reasoning**: User selected items 1–3. Each is deterministic with no judgment step: a branch name is a string, a path literal is a string, and the `fix_induced`/`blocker` implication is already fully specified in `_shared/finding-log.md:52`. Items 1 and 2 also reuse existing scripts on existing registrations rather than adding gates, which keeps the omp `PRE_TOOL_GATES` map untouched for both (item 1 edits an already-mapped script; item 2 is PostToolUse, which the bridge does not mediate).

**Alternatives rejected**:

- _Also gate secret inlining ("Ansible Vault for any secrets")_ — regexable in principle (`AKIA`, `-----BEGIN.*PRIVATE KEY`, `password\s*=`), and rejected. The `security-guidance` plugin is enabled (`settings.json:394`) and `/security-review` is the routed lane for this, so a hand-rolled scanner duplicates an owner that already exists. Its user-visible failure is the worst false-positive profile of any candidate — test fixtures, documentation examples, and example config all trip high-entropy and `password=` patterns — on a gate whose only escape is the all-or-nothing `CLAUDE_SKIP_HOOKS`.
- _A new dedicated script for the worktree check_ — rejected on reuse: `git-discipline-gate.sh` is already registered on PreToolUse(Bash), already in the omp bridge map, and already resolves the current branch. A second script would duplicate all three.

**Trade-off accepted**: Item 2 is a warn, so it informs and does not prevent — a hardcoded path still ships if the warning is ignored, and PostToolUse means the write has already landed. Item 1 blocks at the commit/push verbs rather than at worktree creation, so the misnamed branch still exists and is still reachable by any path that does not route through those verbs. Secret inlining stays enforced only by prose and by a review lane that runs on demand.

### 8. The plain-language vocabulary ban (Q2)

**Choice**: Drop it. No gate at any tier. The rule stays as prose in `skills/coder-core/SKILL.md:24` and is enforced only by the reviewer's judgment, where it already lives (`code-reviewer.md` flags it as `[comment-noise]` against `_shared/code-vocabulary.md`). Named exception to the Phase 3 fuzzy-rule policy, granted by the user.

**Reasoning**: User chose drop. The ban is a **use-versus-mention** rule and no regex separates those readings: `canary` and `sidecar` are the correct standard nouns in Kubernetes and deployment work, so the same token is right in one file and wrong in another depending on whether it names a real deployment pattern or imports private-workflow jargon. Deciding that requires reading what the word refers to, which is a judgment step — and per the Phase 4 adversarial pass, a rule needing judgment is not a gate. Demonstrated live during this session: `git-discipline-gate.sh` matched the literal words "git commit" inside spec **prose** and blocked a markdown write, the exact use/mention failure this rule would reproduce on every file discussing deployment patterns.

**Alternatives rejected**:

- _Conservative deny, per the Phase 3 policy_ — the policy's premise is that false positives are tolerable because `CLAUDE_SKIP_HOOKS` is the release valve. That premise fails here in a way it does not for the other gates: this one fires on **correct** code, and the valve is all-or-nothing, so shipping a legitimately-named canary deployment means running with the credential-read, force-push, and sudo gates disarmed. A gate whose routine unblock is disarming the security rail is a net loss of safety.
- _Warn tier (`dead-prose-gate.sh` pattern, stderr + exit 0)_ — my recommendation, declined. It would surface the vocabulary without blocking correct code, but it is advisory only, and it still fires on every correct use of `canary`/`sidecar`, training the reader to ignore that warning — which degrades the other checks sharing that script.

**Trade-off accepted**: The vocabulary rule is now enforced by nothing mechanical. Private-workflow jargon reaching code comments is caught only if a reviewer is dispatched and notices — and `code-reviewer.md`'s opencode port is already drifted on precisely this bullet (Q6), so on that side it is currently enforced by nothing at all.

### 9. `fix_induced=bug` promotion in `log-review-finding`

**Choice**: The script auto-sets `blocker=yes` on any row carrying `fix_induced=bug`, implementing the rule already documented in `_shared/finding-log.md:52` and in the script's own header. Bump `schema_version` to **3**. Update the snippet in `_shared/finding-log.md` in the same change so the doc and the tool cannot disagree. `log-escape` is untouched and stays at `schema_version=2` — it has no `fix_induced` field.

**Reasoning**: User chose A. The script already validates every other field in this schema — `kind`, `gate`, `class`, `result`, `n_findings` — and declines to enforce the one implication it documents twice. Putting the rule in the tool is the ticket's thesis applied to the tool that logs the ticket's own findings. The version bump is required by the repo's own rule (bump only on breaking vocabulary/meaning changes, never additive): the same caller invocation produces a different `blocker` value before and after, so `/audit review` blocker counts are not comparable across the boundary and downstream filtering needs a way to tell the eras apart.

**Alternatives rejected**:

- _Refuse with `exit 1` unless the caller also passed `blocker=yes`_ — defensible, cheaper, needs no version bump, and has direct precedent (the script already hard-fails on bad `class=`, unmappable `result=`, missing `n_findings=`). Rejected because it makes every caller restate a rule the tool already holds, which is the exact prose-over-mechanism pattern this ticket exists to remove. Its user-visible failure is a telemetry write that hard-fails mid-review over a field the tool could have filled in, costing a review iteration to a logging error.
- _Leave as prose_ — nothing breaks today only because the rule has apparently never fired; the first `fix_induced=bug` row silently lands as a non-blocker and is triaged as ordinary, which is precisely the case the rule was written to catch.

**Trade-off accepted**: The log stops being a pure record of what the caller asserted — the tool now adds a fact the caller did not pass, so a row's `blocker=yes` no longer distinguishes "the reviewer judged this blocking" from "the tool inferred it." Rows before and after the bump are not directly comparable, and any existing `/audit review` query that aggregates blockers across history needs to filter on `schema_version` or knowingly mix the two.

### 10. code-reviewer's calibration read stays a prose first-action line

**Choice**: Keep the prose line. `code-reviewer.md` and the other reviewer agents continue to name `_shared/reviewer-calibration.md` in their body as a first action; they do NOT gain a `skills:` preload. The item is closed as a **justified difference**, not an inconsistency to remove. The justification is recorded in the commit message, per the repo's no-rationale-in-agent-bodies rule — nothing is added to any agent file.

**Reasoning**: User deferred to the best option. Three constraints make the preload strictly worse. (1) `calibration-refs-guard.sh:31-38` enforces heading integrity by grepping each `agents/*reviewer*.md` for a line containing the literal string `reviewer-calibration.md`, extracting its `**bold**` spans and checking each against a real `##` heading in the calibration file — removing the prose line makes the guard find no references, report nothing, and exit 0. It does not fail loudly; it silently stops protecting. That guard exists because three agents once shipped pointing at a renamed heading. (2) `skills:` frontmatter requires a real skill directory containing `SKILL.md`; `skills/_shared/` is 17 loose `.md` files with no `SKILL.md`, so `skills: [reviewer-calibration]` is not expressible without restructuring `_shared/`. (3) The opencode reviewer ports have no `skills:` field and resolve the file by path, so the preload cannot cross to that side at all. The coder/reviewer split is therefore two correct answers to different constraints: `coder-core` **is** a skill directory and has no integrity guard reading its reference; `reviewer-calibration` is a `_shared` fragment shared with opencode and has one.

**Alternatives rejected**:

- _Convert `_shared/reviewer-calibration.md` into a real skill and add `skills: [reviewer-calibration]` to all 11 reviewer agents_ — saves one tool call per reviewer dispatch. Rejected: the user-visible failure is a renamed calibration heading shipping undetected across every reviewer agent, exactly the break `calibration-refs-guard.sh` was written after. The guard would have to be rewritten to parse `skills:` frontmatter, `_shared/` restructured, and the opencode ports left behind — three changes to lose a working protection and buy one tool call.
- _Declare the difference an inconsistency and normalize the other way (give coder a prose read instead of the `skills:` preload)_ — discards a working, harness-native preload for symmetry alone, and `coder-core` has no guard depending on a prose reference, so the change buys nothing.

**Trade-off accepted**: One extra tool call per reviewer dispatch, multiplied across 11 reviewer agents, permanently. The two agent-loading patterns remain visibly different with no in-file explanation — a future reader will see the asymmetry and, unless they find the commit message, may "fix" it and silently disable the guard. The mitigation available is a `claude-doctor.sh` check, not a comment.

### 11. `*-deep` agent inheritance — codify the size rule

**Choice**: Codify the rule that already describes both files correctly — **a `*-deep` agent with a short body (under ~15 lines) duplicates it; one with a longer body delegates by reference to its base agent's body** — and add a `claude-doctor.sh` warn when a `*-deep.md` body exceeds the threshold and does not contain a `Read ~/.claude/agents/` line. No agent file changes: `coder-deep.md` (4-line body, duplicated) and `code-reviewer-deep.md` (118-line base, delegated) are both already compliant. Closed as a justified difference, like D8.

**Reasoning**: User accepted the recommendation. The two patterns are two correct answers to different body sizes, not an inconsistency: duplicating 4 lines costs nothing and cannot meaningfully drift, while duplicating 118 lines guarantees drift — already demonstrated in this repo, where the opencode port of `code-reviewer.md` has drifted exactly that way and is missing a whole Do-Flag bullet. Delegation covers only the body in any case; `coder-deep` cannot inherit `coder.md`'s frontmatter because it must carry `model: opus`. Putting the threshold in `claude-doctor.sh` is the Pattern G move: a structural property that is not a per-tool-call event belongs in the doctor, not a hook, and it converts a judgment re-made per agent into a check a script performs.

**Alternatives rejected**:

- _Normalize on delegation (make `coder-deep` read `coder.md`)_ — one body to maintain, but it spends a Read on every coder-deep dispatch to deduplicate four lines whose drift risk is nil. The user-visible cost is a tool call per dispatch bought with nothing.
- _Normalize on duplication (give `code-reviewer-deep` the full 118-line body)_ — avoids the Read, and the user-visible failure is the one already observed on the opencode side: the two copies diverge, the deep reviewer silently applies stale calibration, and no gate detects it because both files remain individually well-formed.

**Trade-off accepted**: The threshold is a chosen number, not a measured one, so an agent body near 15 lines gets an arbitrary verdict. The doctor check is a warn and runs only when the doctor runs, so a non-compliant `*-deep` agent can ship and sit unflagged until someone invokes it. And the rule governs the claude tree only — the opencode ports have their own structure and are not covered.

### 12. The laconic directive relocates to an Output Style; `caveman` is removed (Q4)

**Choice**: Two parts. (1) `## Communication` (225 words) leaves `claude/.claude/CLAUDE.md` and becomes a Claude Code **Output Style**, selected via the `outputStyle` setting — the relocation the user chose in Phase 2, now confirmed against the overlap objection. (2) The `caveman` plugin is **removed** from `enabledPlugins` in `settings.json` — the user does not use it. Blast radius of the removal is tracked as D10.

**Reasoning**: User: "i dont use caveman, we should drop that. move to output style." The architect's argument against relocating was that three channels already carry terseness rules — caveman (SessionStart **and** SubagentStart), ponytail, and CLAUDE.md — so a fourth would be duplication of exactly the kind this ticket removes. Removing caveman dissolves that objection at the source rather than working around it: the laconic directive stops being a redundant copy and becomes the canonical statement, in a first-class harness surface the user controls, with ponytail left governing what gets built rather than how it reads.

**Alternatives rejected**:

- _Delete the laconic directive outright, relying on the plugins_ — my lean before the user's answer, and wrong once caveman goes. Its user-visible failure is losing the terseness mandate entirely: ponytail governs construction (the YAGNI ladder, shortest working diff), not prose style, so deleting the Communication section with caveman also removed would leave nothing specifying output format at all.
- _Keep it in CLAUDE.md alongside caveman_ — the status quo the objection targets: two overlapping persona statements, one of them a third-party marketplace plugin the user does not use, both paid for on every session.

**Trade-off accepted**: Output styles are **exclusive** — one active at a time — so selecting the laconic style permanently occupies that slot (see Q3 for `simple-english`). The directive also stops reaching subagents: like the Orchestration move in decision 2, an output style is a main-session surface, so subagent prose style becomes governed by nothing. Removing caveman is a behavior change beyond the ticket's original four surfaces, taken on explicit user instruction.

### 13. The laconic style takes the Output Style slot, on trial with a kill condition (Q3)

**Choice**: The laconic directive is the single occupant of the exclusive Output Style slot. `simple-english` stays enabled in `enabledPlugins` for its **skill**, invoked per document when controlled English is wanted, and is never selected as the output style. The relocation ships with an explicit kill condition recorded in the spec: if the style does not visibly change output in normal use, the next pass **deletes** the directive rather than relocating it a fourth time.

**Reasoning**: User asked which is better, then supplied the decisive evidence: "you dont EVER follow the laconic mode directions right now so i dont know if i like it" — correct, and observable in this very session, where caveman's SessionStart injection is also active and also unfollowed. That settles two things. First, between the two styles: `simple-english` is ASD-STE100, a document standard (sentence-length caps, approved modals, no contractions, articles required) aimed at runbooks and procedures; laconic governs chat prose, which is the surface the user actually reads, and the two contradict head-on — simple-english mandates the articles and full grammar laconic drops, so they cannot be blended and whichever holds the slot overrides the other's core mechanic. Second, and more important for this ticket: **no mechanism enforces prose style at all**. No hook sees assistant prose before it reaches the user. An Output Style is the strongest available injection point — system prompt, every turn, versus a CLAUDE.md read once — but strongest-available is not enforcement, and caveman proves stronger injection alone does not produce compliance. So the move is logged for what it is: a modest upgrade in injection strength, not a mechanization, and it earns its place only if it demonstrably works.

**Alternatives rejected**:

- _Select `simple-english` as the output style_ — its user-visible failure is producing prose the user did not ask for: ASD-STE100 forbids contractions and fragments and requires full articles, which is longer and more formal than the terseness the user wants in chat, applied session-wide to every answer rather than to the documents the standard is for.
- _Disable the `simple-english` plugin too, alongside caveman_ — would remove the skill as well as the style, losing a genuinely useful on-demand tool for README/runbook work. The plugin costs nothing while its output style is unselected; caveman was removed because its **hooks** fire unconditionally, which is not true here.
- _Leave the directive in CLAUDE.md_ — the status quo the user's own evidence indicts: 225 words paid for on every session and every subagent dispatch, demonstrably not followed, which is precisely the prose-that-does-nothing this ticket exists to remove.
- _Keep both, switching per task_ — an exclusive slot makes this a manual `outputStyle` change per task; a directive the user must remember to select is no better than prose they must remember to follow, and adds a step.

**Trade-off accepted**: The slot is spent on an unenforced directive, so `simple-english` can never be the active style without displacing laconic. The kill condition is a judgment call with no oracle — nothing measures "visibly changed output", so the week-later verdict is the user's impression, not a check. And this decision knowingly ships one item that is relocation rather than mechanization, against the ticket's stated thesis; it is retained only because deleting the terseness mandate outright (with caveman also gone) would leave output format specified by nothing.

### 14. `caveman` is backed out by deleting both settings keys (D10)

**Choice**: Remove `"caveman@caveman": true` from `enabledPlugins` and the whole `caveman` block from `extraKnownMarketplaces` in `claude/.claude/settings.json`. Nothing else changes: the marketplace tree under `claude/.claude/plugins/` is gitignored and stays on disk untouched, and no other tracked file is edited.

**Reasoning**: User chose full deletion over disabling. The measured blast radius supports it — `settings.json` is the **only** tracked file mentioning caveman, and no tracked file mentions `cavecrew`, so the plugin's three agents are dead weight already. What actually stops is two unconditional hooks (`SessionStart` injecting the persona, `UserPromptSubmit` tracking the mode), the `/caveman` command, and the `~/.claude/.caveman-active` state file, which goes stale harmlessly. Because the install lives in a gitignored, machine-local tree that deletion does not touch, re-enabling is a `/plugin` marketplace add, not a recovery operation — which is what makes the fuller removal cheap rather than risky.

**Alternatives rejected**:

- _Delete the `enabledPlugins` key but keep `extraKnownMarketplaces.caveman`_ — leaves a six-line block in a tracked, stowed file that changes no behavior. Its user-visible failure is the one this ticket exists to stop: config read on every session that a future reader must investigate to learn it does nothing, the same cost as the dead prose being deleted elsewhere in this spec.
- _Set the flag to `false` rather than deleting it_ — same runtime effect, two dead blocks instead of one, and it invites the reading that the plugin is temporarily paused rather than dropped.
- _Also delete the machine-local marketplace tree_ — not in scope, gitignored, and deleting it would make a later change of mind a full reinstall for no benefit to the repo.

**Trade-off accepted**: Restoring caveman needs the marketplace re-added, not one key flipped. The three `cavecrew-*` agents disappear from the agent roster — unused today, but they were an available option and no longer are. And the settings file loses the only trace that this was ever evaluated; the reasoning survives only here and in the commit message.

### 15. The stale `GENERATED` marker is left alone (D11)

**Choice**: No change to `bash-safety-gate.sh`, `block-credential-read.sh`, or `write-edit-safety-gate.sh`. The `GENERATED — do not edit directly` header stays as-is, inaccurate, in all three. The plan records the fact in Constraints so an implementer hitting the banner has a written answer, and does nothing to the files themselves.

**Reasoning**: User chose A — hold the ticket to its four named surfaces. The ticket is `claude/.claude/CLAUDE.md`, `rules/*.md`, and the coder/code-reviewer agents; hook-script file headers are none of these, and D11 only surfaced as a side effect of establishing Q7. The confusion it can cause is bounded and one-time: an implementer building D1's `PreToolUse(Write|Edit)` hook next to `write-edit-safety-gate.sh` reads a banner that does not bind them, and the Constraints block now says so in writing.

**Alternatives rejected**:

- _Amend the marker in all three files to say the generator is unavailable and the file is hand-maintained_ — my recommendation before the user's answer. Correct on the merits (the header states a falsehood, and this ticket deletes rules that do nothing), but it edits three files whose current header forbids editing, on a ticket that never named them. Its user-visible failure is scope: a diff reviewer sees three security-gate files modified in a spec about CLAUDE.md prose and has to establish that the change is cosmetic before trusting the rest.
- _Add a `claude-doctor.sh` check flagging a `GENERATED` marker with no resolvable generator_ — Pattern G, mechanization proper, and structurally the "right" answer. Rejected because the condition is permanent and known: a warn that fires on every doctor run for a state nobody intends to fix is noise that trains the user to skim doctor output, which degrades the checks that do matter.

**Trade-off accepted**: Three files keep a header that is false, and this spec knowingly ships that. Anyone who later builds the generator-side tooling, or who tries to regenerate these gates, starts from a header implying a source that does not exist. The mitigation is documentation only — the Constraints block — which is exactly the prose-instead-of-mechanism trade this ticket exists to reduce, accepted here because the alternative costs more scope than the problem is worth.

### 16. The opencode `code-reviewer.md` port is repaired in this ticket, last (Q6)

**Choice**: Port `claude/.claude/agents/code-reviewer.md` to `opencode/.config/opencode/agents/code-reviewer.md` as the **final step** of this plan, after every claude-side edit has landed. One reconciliation, not two. The port is hunk-by-hunk with judgment, never a copy: the established opencode adaptations are preserved deliberately — `model: opencode-go/mimo-v2.5`, `mode: subagent`, `permission: edit: deny`, hex `color`, `CLAUDE.md` to `AGENTS.md` in all references, and the explicit instruction to skip the calibration file's **Persistent Memory** section because opencode agents have no memory directory. The same sweep covers `coder.md` if this plan's edits reach it.

**Reasoning**: User chose A. The two copies have diverged across two generations: the claude copy was trimmed on 2026-09-07 while the opencode copy dates to 2026-08-14, so opencode carries the older verbose prose throughout plus two substantive gaps — no comment-density rule at all, and the pre-broadening vocabulary rule covering only tracker references, not phase numbers, decision IDs, plan paths, or agent provenance. Since this spec rewrites the claude copy anyway, doing the sweep at the end costs one pass; deferring guarantees two, against a file that is already two generations behind. This repo's own CLAUDE.md makes the propagation sweep mandatory and names patching the opencode port as step 2 of it, so this is the documented obligation rather than new scope.

**Alternatives rejected**:

- _File it as a separate ticket_ — keeps this spec strictly inside its four named surfaces, but the user-visible failure is a wider gap: the separate ticket would have to reconcile the August drift AND everything this plan changes, on a file whose divergence nobody noticed for three weeks. Deferring a sweep is what produced the current state.
- _Stop maintaining the opencode reviewer port (delete or freeze it)_ — defensible on the caveman evidence (stale and unnoticed implies unused), and I raised it explicitly. Rejected by the user's choice. Its failure mode is a silent capability loss: any future opencode review session would run a reviewer missing the density and vocabulary rules with nothing announcing it, and it would additionally require amending the propagation-sweep rule in this repo's CLAUDE.md in the same change.
- _Port immediately, before the claude-side edits_ — reconciles the August drift now but guarantees a second pass once this plan's edits land.

**Trade-off accepted**: The plan's final step touches a surface the ticket did not name, so the diff is wider than the four stated targets and a reviewer must accept that expansion. The port is a judgment task, not a mechanical copy — the adaptations have no test and no gate protecting them, so a careless sweep can silently reintroduce `CLAUDE.md` references or the Persistent Memory instruction into an agent that cannot honour them. And nothing this plan builds prevents the same drift recurring: the sweep stays a prose obligation in CLAUDE.md, unmechanized, which is precisely the category this ticket set out to reduce.

### 17. False denies on the two new gates get a narrow escape, not the session-wide one

**Choice**: `shell-write-gate.sh` and `quality-check-cap.sh` each check their own variable (`CLAUDE_SKIP_SHELL_WRITE`, `CLAUDE_SKIP_QUALITY_CAP`) alongside `CLAUDE_SKIP_HOOKS`. The security gates get no narrow escape.
**Reasoning**: `spec-criteria` raised it as a damage-path question and the user approved the narrow variables. `CLAUDE_SKIP_HOOKS` is session-wide: reaching for it to clear one misjudged test command also disarms credential-read and force-push for the rest of the session. The plan's own Edge Cases list several false-deny vectors on both gates (heredoc bodies containing `>`, unrecognized command wrappers), so the unblock is expected to be used.
**Alternatives rejected**: Leave `CLAUDE_SKIP_HOOKS` as the only unblock — the routine cost of a false deny becomes an unarmed credential rail for the remainder of a working session, which is the exact failure the rails exist to prevent, and it happens silently. Give the security gates narrow variables too — a per-gate bypass on force-push or credential reads is a bypass anyone can reach for one command at a time, which is what makes those rails deterministic today.
**Trade-off accepted**: Two more environment variables to know about, and the escape hatches now differ per gate rather than being one uniform switch. A gate whose narrow variable is set fails open with no record that it did.

### 18. `quality-check-cap.sh` fails OPEN when its state directory is unwritable

**Choice**: every state-directory operation in `quality-check-cap.sh` is `|| exit 0`. `git-discipline-gate.sh` and `review-commit-gate.sh` keep unqualified fail-closed behaviour.
**Reasoning**: `spec-criteria` raised it and the user approved. Decision 5's fail-closed rule protects security rails; this gate enforces a productivity rule. Failing closed on a bookkeeping error denies _every_ quality-check command in the session, not just repeats — the cap would stop the developer testing at all, and the only unblock would be an environment variable.
**Alternatives rejected**: Fail closed uniformly for consistency with decision 5 — an unwritable `~/.claude/state/` (full disk, permissions, a sandboxed run) blocks every test, lint and typecheck invocation until someone diagnoses a hook nobody was thinking about. Deny only the repeat case and allow first runs — the gate cannot tell a repeat from a first run without the state it just failed to read.
**Trade-off accepted**: The cap silently stops enforcing when state breaks, and nothing detects that — the doctor cannot check a runtime condition. The plan carries this as its one deliberate fail-open.

### 19. `emit-orchestration.sh` warns in-context when the file is missing

**Choice**: an unreadable or missing `orchestration.md` injects a WARNING string as `additionalContext` rather than exiting 0 silently. An unregistered hook stays doctor-only.
**Reasoning**: `spec-criteria` raised the silent-failure gap and the user approved the partial fix. The missing-file half is detectable from inside the hook at zero cost, at the exact moment the session would otherwise proceed with no routing rules.
**Alternatives rejected**: Exit 0 silently and rely on the doctor — the main session routes work to the wrong lane with no signal, and the doctor only runs when someone thinks to run it, which is precisely when they already suspect a problem. Fail the hook loudly (non-zero exit) — SessionStart has no deny tier; a non-zero exit produces harness noise at every session start without putting the fact where the model will read it.
**Trade-off accepted**: Only one of the two failure halves is covered. If the hook is unregistered nothing runs, so nothing can announce it, and the doctor remains the sole detector. Neither half is visible on screen — `additionalContext` does not appear in the transcript.

### 20. The Phase 9 sweep uses `git grep`, not `grep -r`

**Choice**: the sweep and its verification command run `git -C ~/dotfiles grep -nE ... -- claude omp opencode`, restricted to tracked files.
**Reasoning**: plan-reviewer round 1 found the original `grep -r` already matching 25 files, 21 of them append-only runtime state inside the live symlinked tree — `file-history/` snapshots, `history.jsonl`, `security-hook-block-log.jsonl`, `settings.json.bak`. Those quote the retired headings by design and gain matches on every session, including the coder's own runs of this plan's verification commands. Every one of them is untracked or gitignored, so tracked-only scoping excludes the whole category structurally. Verified after the change: three matches, all files the plan's phases already edit.
**Alternatives rejected**: Extend the `grep -v` exclusion list to cover the four newly-found paths — the list was already incomplete once for exactly this reason, the runtime tree grows new state directories over time, and the next miss reappears as an unpassable Success Criterion during implementation rather than during planning. Drop the verification command and make the sweep manual — Success Criterion 2 requires every automated block to pass, and a sweep with no check is the failure mode the propagation-sweep rule exists to prevent.
**Trade-off accepted**: a dangling reference living in an untracked-but-real file (a working-copy edit not yet added) is invisible to the sweep. Acceptable: an untracked file is not yet part of the toolkit.

### 21. `agent-model-guard.sh` joins Success Criterion 9's confinement list

**Choice**: add `claude/.claude/scripts/agent-model-guard.sh` to the permitted-diff list, keeping Phase 9 step 1's fix of its dangling `Behavior §` reference in scope.
**Reasoning**: plan-reviewer round 1 found the phase and the criterion contradicting each other — the phase names the file explicitly, the criterion's list omits it, and two competent coders resolve that opposite ways. Both instructions were authored in the same pass and the omission is an oversight, not a scope judgment.
**Alternatives rejected**: Drop the fix from Phase 9 instead — the plan's own sweep step identifies the reference as dangling, so leaving it means shipping a sweep that knowingly skips a defect it found, and AC16 then reads as false. Leave both as written and let the coder decide — a plan that reads two ways at the same point is the defect; a coder resolving it silently either way produces work nobody can verify against the criteria.
**Trade-off accepted**: the branch's diff widens by one file for a one-line comment fix unrelated to the mechanization work.

### 22. Phase 9 step 2 becomes a verify-only step

**Choice**: rewrite the step to diff the two `code-reviewer.md` copies and confirm every remaining difference is a deliberate adaptation, porting a hunk only if real drift appears. A no-op is the expected outcome.
**Reasoning**: plan-reviewer round 1 found the premise stale, and the tree confirms it — commit `0db6d3ee` ("agent trim pass 2") landed during planning and synced both copies. The opencode file is now 128 lines against the claude side's 127, both last touched in that commit, already carrying the comment-density rule and the broadened vocabulary rule. The Phase 6 falsification sweep checked the plan's claims against the tree but did not check whether HEAD had moved since research, which is how a two-generation drift description survived into a finalized plan after the drift was gone.
**Alternatives rejected**: Delete the step outright — the verification is nearly free and the adaptations (`AGENTS.md` wording, no Persistent Memory, model/permission/color) are exactly the kind of thing a future sync silently flattens, so a standing diff check is worth keeping. Leave the stale narrative and let the coder discover the no-op — the coder is then working from false evidence with a "hunk by hunk with judgment" instruction for a diff that does not exist, and cannot tell a finished step from a skipped one.
**Trade-off accepted**: Phase 9 now most likely does nothing on its second step, which reads as dead weight to anyone who does not know why the check is there.

### 23. `skills/brief/SKILL.md` loses its Caveman reference, and the caveman check becomes tracked-only and case-insensitive

**Choice**: Phase 5 also edits `claude/.claude/skills/brief/SKILL.md:81`, replacing `Composes with Caveman (which compresses wording); this skill decides what exists at all.` with `This skill decides what exists at all, not how it is worded.` The phase's verification becomes `git -C ~/dotfiles grep -in caveman -- claude opencode omp`. The file joins Success Criterion 9's confinement list.
**Reasoning**: plan-reviewer round 2 found a live skill documenting composition with the plugin this phase removes, invisible to every check the plan specified. Two independent misses let it through: the grep was case-sensitive and the reference is capitalized, and it was `grep -r` rather than `git grep`, so it also matched the untracked `skill-usage.jsonl` — noise that would have masked a real hit even had the case matched. Decision 20 fixed that same `grep -r` defect in Phase 9 only; the class went unfixed in Phase 5.
**Alternatives rejected**: Leave the prose and delete only the settings keys — `brief` then instructs its reader to compose with a plugin that no longer exists in the session, and AC16 is false while every automated check reports success. Keep the check case-sensitive and just edit the file — the next capitalized reference anyone adds is equally invisible, which is the defect rather than this one instance of it.
**Trade-off accepted**: a case-insensitive sweep will match an incidental future use of the word in unrelated prose and need a human read to dismiss.

### 24. The deleted `## Git` section gets a `Where the rest lives` pointer

**Choice**: Phase 7 adds `git conventions → ~/.claude/rules/git.md` to CLAUDE.md's `## Where the rest lives`, matching what Phases 4 and 5 do for the sections they remove.
**Reasoning**: plan-reviewer round 2 found Git as the only one of the three removed sections with no pointer. AC8 requires all three. The omission was an oversight in a plan that built the mechanism twice already.
**Alternatives rejected**: Rely on `rules/git.md` being an established directory a reader will infer — inference is a materially weaker guarantee than the pointer the plan builds for the other two, and it fails exactly for the reader who does not already know the layout. Drop the pointers from all three for consistency — that discards a working mechanism to make an oversight look deliberate.
**Trade-off accepted**: three lines of index in CLAUDE.md, paid for in every session's context.

### 25. Phase 9's verification regex covers every term its prose sweep names

**Choice**: the regex gains `caveman` and `## Communication` and becomes case-insensitive. `schema_version`, `git-discipline-gate` and `review-commit-gate` stay hand-swept only, with a comment saying why: all three legitimately survive the change, so a match is not a defect.
**Reasoning**: plan-reviewer round 2 noted the prose named eight terms and the regex checked four — and that gap is the exact mechanism by which the round-2 blocker reached a finalized plan. A term named in the sweep but absent from the check is a term nothing verifies.
**Alternatives rejected**: Narrow the prose list to the four that were regexed — the unregexed terms are real sweep targets, and dropping them from the instruction loses the sweep rather than fixing the check. Regex all eight — `schema_version` and both gate names match legitimately after the change, so the check would fail forever on correct work, which is the unpassable-verification defect decision 20 already removed once.
**Trade-off accepted**: three of the eight terms are verified by human sweep only, and the comment explaining why is the sole thing keeping someone from "fixing" it by adding them.

### 26. The reviewer-calibration doctor check is dropped, and replaced by a whole-tree one

**Choice**: Phase 8 does not add a per-file "every `*reviewer*.md` must reference `reviewer-calibration.md`" warn. In its place, new doctor section 4d warns only when **zero** reviewer agents reference the file at all. Decision 10's trade-off named "a `claude-doctor.sh` check" as its mitigation; this is the half of that mitigation that has an oracle.

**Reasoning**: plan-reviewer round 3, verified against the tree. Seven of thirteen `*reviewer*.md` agents legitimately carry no such reference — the five `*-deep` variants delegate calibration transitively by reading their base agent, and `plan-reviewer`, `test-reviewer` and `test-intent-reviewer` are not calibration-style reviewers at all. The check as specified warns permanently on all seven, and Phase 8's own manual-verification step declares a permanent unfixable warning a defect in that phase — the plan contradicted itself. I then checked whether any property in the tree discriminates the six that must carry the reference from the seven that must not: `reviewer-domains`, `finding-log` and `_shared/` references were all tested and none separate them (`_shared/` correlates perfectly today, but only coincidentally — nothing makes it stay true). No mechanical discriminator exists.

**Alternatives rejected**:

- _Keep the check with a hand-maintained allowlist of the six_ — a new reviewer agent added later is either omitted from the list and unchecked, or the list is forgotten and the warn returns permanently. That is the same permanent-noise failure that trains a reader to skim doctor output, which decision 15 already rejected once, plus a second file to keep in sync.
- _Exempt `*-deep` by filename and the three test/plan reviewers by name_ — the filename half is defensible, the three by name are an allowlist wearing a different hat, with the same rot.
- _Drop the check with no replacement_ — leaves decision 10's trade-off with no mitigation at all: a future reader converting the reviewers to a `skills:` preload deletes the prose lines, `calibration-refs-guard.sh` finds no references, reports nothing, exits 0, and the protection is silently gone. That is the exact failure decision 10 was written to prevent.

**Trade-off accepted**: the replacement only fires when the guard has gone completely blind. One reviewer losing its reference in isolation — the more likely accident — is still undetected, and nothing in the tree can detect it.

### 27. opencode's `test-writer.md` is fixed in Phase 4 alongside the claude copy

**Choice**: Phase 4 edits `opencode/.config/opencode/agents/test-writer.md:58` in the same phase as the claude copy. Phase 9 step 1's "already handled" list is corrected to say **both** copies, the sweep list and regex gain the bare `## Orchestration` form, Phase 4's verification gains a `git grep` for it, and the file joins Success Criterion 9's confinement list.

**Reasoning**: plan-reviewer round 3, verified. `AGENTS.md` is a symlink to the same `CLAUDE.md`, so deleting the `## Orchestration` section dangles the opencode reference for exactly the same reason as the claude one — the two are one defect, not two. It survived to a finalized plan through four independent gaps at once: no phase edited it, step 1 claimed `test-writer.md:58` was handled (true claude-side only), the regex checked only the long `Orchestration (main session only)` form, and criterion 9 omitted the file. Fixing the edit without the other three leaves the same hole open for the next relocation.

**Alternatives rejected**:

- _Leave it to Phase 9's sweep to discover_ — the sweep as written could not discover it: its regex matched only the long form, and its prose asserted the file was already done. A step that states a false premise does not self-correct.
- _Fix the edit and leave the regex alone_ — the bare `## Orchestration` form then remains unverified, so the next section relocation reintroduces the identical dangling reference with nothing to catch it. This is the class-versus-instance failure that already cost this plan a round.
- _Treat opencode as knowingly-skipped, like the Orchestration injection itself (decision 3)_ — decision 3 accepts opencode losing a _capability_. This is not a lost capability; it is an agent instructing itself to consult a section that no longer exists, which reads as a live rule and misroutes work.

**Trade-off accepted**: the two `test-writer.md` files must now be edited in lockstep, and nothing enforces that beyond the sweep regex catching the survivor.

### 28. The five dangling `2-run cap` pointers die in Phase 3, including two in `code-reviewer.md`

**Choice**: Phase 3 deletes the phrase at all five surviving sites in the same phase that deletes the rule — `agents/test-writer.md:44`, `agents/code-reviewer.md:120`, `skills/deps/SKILL.md:35`, and the opencode copies of the first two. `2-run cap` joins Phase 9's sweep list and its verification regex; the four files not already there join Success Criterion 9. The plan's "no body edits to `code-reviewer.md`" boundary is narrowed explicitly: it covers _rules_, not pointer deletions the propagation sweep obliges.

**Reasoning**: plan-reviewer round 3 named two sites; the tree has six, five of which survive the phase (`CLAUDE.md:70` is removed by Phase 3's own reword, and `coder-core/SKILL.md:57` by its section deletion). Every one is a deletion inside an existing sentence or list item — no rule changes, no line added. Leaving them means an agent pointing at a cap that no longer exists in the file it names, which is worse than the prose it replaced: the reader follows the pointer, finds nothing, and cannot tell whether the rule was deleted or the pointer is wrong.

**Alternatives rejected**:

- _Defer the two `code-reviewer.md` sites to a follow-up to preserve the no-edit boundary_ — ships a known-dangling pointer in the most-dispatched reviewer on both harnesses, to protect a boundary whose purpose (don't restructure reviewer rules) a one-phrase deletion does not threaten. The boundary would be enforcing its letter against its own intent.
- _Repoint them at the deny message instead of deleting_ — an agent cannot read a hook's deny message before triggering it, so the pointer would name something unreachable at read time. Worse than silence.
- _Fix them in Phase 9's sweep rather than Phase 3_ — the pointers dangle between the two phases, and every phase boundary in that window runs `/review` and a commit against a tree the plan knows is inconsistent.

**Trade-off accepted**: this plan now touches both `code-reviewer.md` files, so the diff no longer supports the flat claim that the four coder/reviewer agents are untouched — the divergence note in `acceptance-criteria.md` is accurate about _rules_ and imprecise about the diff.

### 29. `laconic.md` carries `keep-coding-instructions: true`

**Choice**: the output style's frontmatter gains the key, and Phase 5's automated verification greps for it.

**Reasoning**: plan-reviewer round 4, verified against the tree. Selecting a custom output style replaces Claude Code's built-in software-engineering system prompt unless this key is set — the key exists only because dropping them is the default. Decision 13 described an output style as purely additive ("system prompt, every turn"); that property does not hold, and the External Contracts entry recorded only the exclusivity and name-matching rules. The single output style installed on this machine, `simple-english.md:4`, is also prose-only and carries the flag, which is the precedent that settles it.

**Alternatives rejected**:

- _Ship the two-key frontmatter as originally specified_ — every automated check in Phase 5 passes either way (`outputStyle == "Laconic"`, file exists, `/output-style` lists it), and AC17 asks only whether prose got terser, which it does. The user-visible failure is the coding system prompt silently gone from every session, discovered eventually as degraded engineering behaviour with no obvious cause, and attributed to anything but a style file.
- _Abandon the output style and leave `## Communication` in CLAUDE.md_ — the relocation is the ticket's band-2 work and the kill condition already covers the case where the style does not earn its place. Reversing it over a one-line frontmatter fix discards the phase to avoid writing the line.

**Trade-off accepted**: this plan's evidence for the flag is precedent plus the key's existence, not an exercised run — the built-in prompt's absence is not directly observable from inside a session, so nothing here proves the flag works, only that omitting it is the documented way to lose them.

### 30. The doctor's registration label avoids the swept phrase

**Choice**: Phase 8's label is `quality-check-cap.sh:quality-check repeat-run cap`, not `…2-run cap`.

**Reasoning**: plan-reviewer round 4, verified. `claude-doctor.sh` is under `claude/`, which is inside the scope of Phase 3's and Phase 9's `git grep -in '2-run cap' -- claude omp opencode` checks. The original label would have made both print FAIL on a correctly implemented tree, and Phase 9 step 1 would then instruct the coder to "fix any residual dangling reference" — pointing at a string the plan itself ordered written. Success Criterion 2 requires every verification block to pass on re-run in order, so Phase 3's block would also fail retroactively.

**Alternatives rejected**:

- _Add a path exclusion for `claude-doctor.sh` to both greps_ — two checks now carry an exception whose reason lives only in a comment, and the next legitimate use of the phrase needs a third. The sweep's value is that a match is unambiguously a defect; the first exclusion ends that.
- _Drop `2-run cap` from the sweep list_ — the five dangling pointers decision 28 fixes then have nothing verifying them, which is the unverified-term defect decision 25 closed.

**Trade-off accepted**: the doctor's label no longer uses the phrase a reader would search for, so grepping the doctor output for `2-run cap` finds nothing.

### 31. The SessionStart matcher enumerates four sources, including `clear`

**Choice**: matcher `"startup|resume|clear|compact"`, and the verification asserts both `clear` and `compact` are present.

**Reasoning**: plan-reviewer round 4. Phase 4's own prose already argued that omitting `compact` makes the routing rules vanish at the first compaction; `clear` is the identical failure on a more frequent trigger. The one SessionStart block already in `settings.json` uses the match-all `"*"`, so this plan is the first to enumerate sources at all — enumeration is what creates the possibility of a hole, and AC7 names no source.

**Alternatives rejected**:

- _Keep three sources_ — after any `/clear` the main session runs with no workflow-routing rules and nothing says so. The user asks which lane handles cleanup and gets an answer from the model's priors instead of the file, indistinguishably from a correct one.
- _Use the match-all `"*"` like the existing block_ — simpler, and would have avoided this class entirely, but it also fires the hook on sources this plan has not considered; the enumerated form states intent and the verification can assert it.

**Trade-off accepted**: an enumerated matcher must be revisited if Claude Code adds a SessionStart source, and nothing in the doctor checks for one it does not name.

### 32. The bridge header's `stub-guard` mention is Phase 1's to delete

**Choice**: Phase 1's bridge header edit gains a second item — drop `stub-guard / ` from `claude-security-bridge.ts:25`. Phase 9's count is corrected from one site to two.

**Reasoning**: plan-reviewer round 4, verified: the tracked tree has two `stub-guard` sites, `CLAUDE.md:60` (deleted by Phase 2) and the bridge header. The plan asserted "in one", so Phase 9's regex would print FAIL and the coder would be hunting a reference the plan told them did not exist. Phase 1 already edits that header for the `mechanical-check-gate` paragraph, so the second deletion is free there.

**Alternatives rejected**:

- _Leave it to Phase 9's "fix any residual" catch-all_ — the catch-all works only if the coder disbelieves the count printed two lines above it. A stated count that is wrong is worse than no count.
- _Give it its own phase_ — a two-word deletion in a header Phase 1 already opens.

**Trade-off accepted**: none identified; this is a correction, and the alternative shape has no advocate.

### 33. Phase 3 keeps a one-line anti-dodge residual

**Choice**: the `## Quality Check Cap (HARD RULE)` heading and rule statement go; one line stays in `coder-core/SKILL.md` — variants of the same check (extra flags, an added path arg, `run test` vs `test`) are the same command, do not vary one to buy another run.

**Reasoning**: plan-reviewer round 4. The phase claimed "the rule and its anti-dodge clause are both mechanized". Decision 1's own trade-off says otherwise: the normalizer is a maintained list, and it strips pipe suffixes, `2>&1` and `> file` only. Argument variation cksums to a different key and silently unlocks a free run — exactly the dodge the deleted sentence names. Mechanizing the rule does not mechanize the clause.

**Alternatives rejected**:

- _Delete it as originally specified_ — the gate's known blind spot loses its only cover, and the failure is invisible: the second run is simply allowed, and nothing distinguishes a legitimate different command from a dodged one.
- _Extend the normalizer to strip arguments_ — it cannot: `pytest tests/unit` and `pytest tests/integration` are genuinely different commands, and any rule that collapses them denies real work.

**Trade-off accepted**: one line of prose survives a phase whose purpose is deleting prose, and it is unenforceable — the same category the ticket set out to shrink.

### 34. Both new gates name their escape variable in the deny message

**Choice**: `quality-check-cap`'s and `shell-write-gate`'s deny messages each end with a clause naming their own `CLAUDE_SKIP_*` variable and stating it disarms that gate only.

**Reasoning**: plan-reviewer round 4. Decision 17 created the narrow variables because `CLAUDE_SKIP_HOOKS` also disarms the credential-read and force-push rails. But neither variable appeared in any deny message, in `CLAUDE.md`, or in the doctor — only in this spec and a script preamble. The acceptance criteria raise the false-deny unblock as an open question for exactly this reason. A narrow escape nobody can find is worth nothing, and the deny is the one moment the user needs it.

**Alternatives rejected**:

- _Document the variables in `CLAUDE.md` instead_ — adds prose to the file this ticket is shrinking, and puts the information where it is read at session start rather than where it is needed, which is at the block.
- _Leave them undocumented so they are not casually used_ — the reachable alternative for a blocked user is then `CLAUDE_SKIP_HOOKS`, which is the broad hammer decision 17 was written to avoid. Hiding the safe option promotes the dangerous one.

**Trade-off accepted**: every deny message is longer, and naming the escape at the moment of the block makes reaching for it easier than reading the message — including on true positives.

### 35. Workflow gates get their own line, separate from `## Safety Rails`

**Choice**: `## Safety Rails` gains "shell writes to tracked files" and `shell-write-gate`; a **separate** line below it names the advisory workflow gates — `shell-write-gate`, `quality-check-cap` — as having deny messages that say what to do next and per-gate `CLAUDE_SKIP_*` variables. `quality-check-cap` does not join the rails list. `shell-write-gate` is deliberately in both.

**Reasoning**: plan-reviewer round 4. `## Safety Rails` reads "never work around a block … report it to the user and stop." `quality-check-cap`'s deny message says the opposite — fix in one batch and run it once more — and this plan's own Deviations section already classes it as enforcing a productivity rule, not a security rail. Two instructions with opposite required actions for the same block is the ambiguity the mechanization was supposed to remove.

**Alternatives rejected**:

- _Add both gates to the rails list as originally specified_ — the model hits a `quality-check-cap` deny, follows the rails paragraph, stops and reports to the user, and the batch-fix instruction in the deny message is never acted on. The gate then costs a turn and delivers nothing.
- _Reword `## Safety Rails` to stop claiming universal stop-and-report_ — weakens the one paragraph whose absolute wording is load-bearing for the credential and force-push rails, to accommodate two gates that are not rails.

**Trade-off accepted**: `## Safety Rails` gains a second, adjacent list with a similar shape, and `shell-write-gate` appearing in both invites a reader to conclude one of the placements is a mistake.

### 36. Doctor section 4d gets an implementation criterion

**Choice**: Phase 8's verification adds a grep for the 4d warn string in `claude-doctor.sh` itself, alongside the existing grep asserting it stays silent on a healthy tree.

**Reasoning**: plan-reviewer round 4. Six reviewer agents reference `reviewer-calibration.md` today, so the silence check prints OK before the phase, after the phase, and also if the coder skips 4d entirely — it cannot distinguish implemented from absent. 4d is the replacement decision 26 installed for the dropped calibration check, and it was the only new doctor check with nothing behind it. The phase's "the last three fail today" line was also wrong about this one.

**Alternatives rejected**:

- _Build a fixture agents directory with no calibration references and run the doctor against it_ — a truer test, and the doctor takes no directory override (unlike `calibration-refs-guard.sh`, which has `CALIB_AGENTS_DIR`), so it would mean adding one for a warn that fires only in a state nobody intends to reach.
- _Accept the silence check alone_ — leaves a check that can never fail and never proves anything, which is the shape of a check that gets deleted later as noise, taking decision 26's mitigation with it.

**Trade-off accepted**: the criterion tests that a string is present in a script, not that the check works — it would pass on a 4d whose condition is inverted.

### 37. `quality-check-cap` records the run on PostToolUse, and the omp bridge gains the matching path

**Choice**: the Bash branch splits across two events. PreToolUse reads state and denies but writes nothing; PostToolUse writes `run-$key` and never denies. `settings.json` gains a `PostToolUse`/`Bash` registration, and the existing `pi.on("tool_result", …)` handler in `claude-security-bridge.ts` gains a `bash` branch so the recording half fires under omp too. Edit counting stays on PreToolUse. Adopted **in full**, including the bridge work — not as the cheaper degraded variant.

**Reasoning**: plan-reviewer round 4 raised this as an ALT; the user directed it be fixed. Recording before the command is allowed to run means every path where it does not run — the user rejects the permission prompt, `bash-safety-gate` or `shell-write-gate` denies the same call, the cwd was wrong, the package name was typo'd — leaves a phantom run behind. The next real attempt is then denied with "already ran this session and nothing has been edited since", which is false, and whose only unblocks are an unrelated file edit or an env var. That is a false deny generated by the gate's own bookkeeping, on the failure path, which is where a productivity gate can least afford to be wrong. The ALT's stated cost was that the omp bridge has no generic `tool_result` fan-out; checked against the source, it has a `tool_result` handler already (`claude-security-bridge.ts:261-281`, arming `review-commit-gate` on a `task` result), so the recording path is a branch added ahead of an existing early return, not new machinery.

**Alternatives rejected**:

- _Keep the single-event design_ — retains a false-deny class that fires precisely when the user is already blocked by something else, with a message that misstates the cause. This is worse than the prose rule it replaces: the prose was ignorable, the gate is not.
- _Move the recording to PostToolUse and accept the cap becoming a no-op under omp_ — the ALT's own cheaper reading. Rejected: AC14 requires every new deny-capable gate to behave the same under both harnesses, and a gate that silently does nothing on one of them is the failure mode the omp bridge exists to prevent. The bridge branch is roughly fifteen lines.
- _Record on PreToolUse but delete the record if the command is later found not to have run_ — needs a PostToolUse hook anyway to observe the outcome, so it pays the same cost for a compensating-write design that is wrong in the window between the two events.

**Trade-off accepted**: the gate now has two registrations per harness and its correctness depends on both firing. If the PostToolUse half is unregistered, dropped by a settings edit, or fails under omp, the cap silently stops capping — the fail-open direction, and the automated verification checks the registration but nothing detects it drifting later.

### 38. The narrow gate escapes travel in the command, not the environment

**Choice**: `CLAUDE_SKIP_SHELL_WRITE` and `CLAUDE_SKIP_QUALITY_CAP` are deleted. Each gate's narrow escape is an in-band token in the command string — `#skip-shell-write-gate` and `#skip-quality-cap` — tested with `grep -qF` against `.tool_input.command`. `CLAUDE_SKIP_HOOKS` is unchanged and remains session-launch-only. The escape token is authorized by the user, never appended by the model on its own initiative; `## Safety Rails`' stop-and-report rule governs that, since the gate cannot tell who wrote the token.

**Reasoning**: plan-reviewer round 5 raised this as a BLOCKER; the user directed it be fixed. A PreToolUse hook is spawned by Claude Code, in Claude Code's environment, **before** the command executes. An env-var prefix on the denied command is inert text inside `.tool_input.command` and never reaches the hook process, so decision 17's narrow variables could never have worked. The tree already agreed: `warn-skip-hooks.sh` tells the user to unset the variable and restart Claude Code, i.e. these are session-launch variables. Both phases' verification set the variable in the probe shell — which _is_ the gate's parent — so both criteria passed whether or not the escape worked in a session. A shell comment is the only channel that carries per-command intent into a PreToolUse gate.

**Alternatives rejected**:

- _Keep the variables and reword the message to "export it and restart Claude Code"_ — honest, but it makes the narrow escape useless at the only moment it is needed. Decision 17 exists because a routine false deny must not force the session-wide bypass that also disarms the credential-read and force-push rails; an escape costing a session restart is one the user will skip in favour of `CLAUDE_SKIP_HOOKS`, which is the outcome decision 17 was written to prevent.
- _Drop the narrow escape entirely and route false denies through `CLAUDE_SKIP_HOOKS`_ — reopens decision 17 to reach the same place: a productivity gate with a routine false-positive case disarming two security rails every time it misfires.
- _Let the env prefix defeat `quality-check-cap` incidentally, via the normalizer_ — it currently does, because the strip list handles `env VAR=val ` but not bare `VAR=val `, so the segment stops anchor-matching. Rejected as an escape and closed as a hole: it is undocumented, gate-specific, and means any unrelated env prefix (`FOO=1 npm test`) silently escapes the cap. Phase 3 now strips bare assignments and asserts the closure.

**Trade-off accepted**: the escape is visible in the command string, so a model can append it as readily as a user can — the token is a convention backed by a rule, not a mechanism, and it is strictly weaker than an env var the model cannot set. The env var was not weaker in principle; it was inert in practice, which is worse. Nothing detects a model that appends the token unbidden except the user reading the command.

### 39. `quality-check-cap` state is mtime markers, not a counter

**Choice**: `<session>/edits` and `<session>/run-<cksum>` become empty marker files. Branch A `touch`es `edits`; PostToolUse `touch`es `run-<key>`; the deny predicate is `[[ "$dir/run-$key" -nt "$dir/edits" ]]`. The read-modify-write counter, the `|| echo 0` defaults, and the content-equality read all disappear.

**Reasoning**: plan-reviewer round 5 raised this as an ALT; the user directed it be fixed. The counter sat on the hot Write/Edit path, where Claude Code dispatches parallel Edit calls that each spawn their own hook process. Two concurrent increments drop one, and a dropped increment leaves the counter equal to the stamp — a **false deny** stating `nothing has been edited since` when something was. That is the same false-deny-on-a-lie class decision 37 removed from the Bash half, surviving in the edit half. `touch` is idempotent and races harmlessly. The counter shape was inherited from `review-commit-gate.sh`'s write-a-word-to-a-file pattern and never re-examined after the two-event split separated the writer from the reader.

**Alternatives rejected**:

- _Keep the counter and make the increment atomic_ — needs a lock or an `O_APPEND` line-count trick on every Write and Edit in the session, which is real cost on the hottest path in the toolkit to preserve a representation with no remaining advantage.
- _Keep the counter and accept the race_ — the dropped increment produces exactly the false deny, on exactly the message, that decision 37 was written to eliminate. Accepting it in one half while paying a two-event redesign to remove it from the other is incoherent.

**Trade-off accepted**: correctness now rides on filesystem mtime granularity. On a 1-second-granularity filesystem an edit and a run in the same second compare as not-newer and the run is allowed — a fail-open in a one-second window, the direction this design already declares it wants. ext4, btrfs and APFS are nanosecond, so it is theoretical on all four supported platforms. The counter was also marginally easier to eyeball when debugging state by hand.

### 40. Fail-closed is an `EXIT` trap under `set -Eeuo pipefail`, not an `ERR` trap

**Choice**: every PreToolUse gate this plan touches gets `set -Eeuo pipefail`, an `emitted` flag, a `deny()` helper that sets it, and `trap fail_closed EXIT` where `fail_closed` denies when `rc != 0 && emitted == 0`. The plan's previous `ERR`-trap wording is replaced everywhere it appeared.

**Reasoning**: plan-reviewer round 6 raised this as a BLOCKER with an exercised experiment (bash 5.3.15). Two facts sink the `ERR` form. Without `set -E`, bash does not run an `ERR` trap for a failure inside a shell function, a command substitution, or a subshell — which is where every one of these gates does its work. And `set -u` on an unbound variable exits 1 **without** running the `ERR` trap even when `-E` is set. A PreToolUse hook that exits 1 with empty stdout is non-blocking: the tool proceeds. So the exact failures the trap exists to catch were the ones it would have missed, and the gate would have failed **open** while the plan claimed it failed closed.

**Alternatives rejected**:

- _`set -E` plus the `ERR` trap_ — closes the function/subshell hole but not the `set -u` hole, so an unbound variable in a gate still lets an unreviewed commit or a credential read through silently. Half a fail-closed gate reads exactly like a whole one from outside.
- _Drop `set -u`_ — trades one silent-failure class for another: an unset variable then expands to empty and the gate's own predicate matches nothing, allowing rather than denying.

**Trade-off accepted**: `EXIT` fires on every termination path, so the deny is now correct-by-construction but blunt — `review-commit-gate.sh` mediates every `git commit` in this repo, and after this change any non-zero exit in it denies all commits until the script is fixed. That is stated as a self-gating risk in Phase 1 with a `bash -n` pre-flight and a verification-before-first-commit ordering. The `emitted` flag is bookkeeping the `ERR` form did not need.

### 41. The Output Style relocation removes the Communication rules from every subagent, and the plan says so

**Choice**: Phase 5 carries an explicit scope-change paragraph stating that an Output Style rewrites the **main session's** system prompt only, that subagents receive their agent file plus `CLAUDE.md` and not the active style, and that AC17 must therefore be judged on the main session's own prose.

**Reasoning**: plan-reviewer round 6 raised this as a GAP. Today every coder, reviewer and researcher reads the ten laconic paragraphs because they sit in `CLAUDE.md`; after Phase 5 none of them do. Phase 4 already states its equivalent scope change (SessionStart output is not injected into subagents), so the asymmetry was an omission rather than a considered difference. Left unstated, AC17's kill condition would be evaluated in a session where the agents producing much of the prose had silently stopped receiving the directive, and a "no visible change" reading would delete the style for the wrong reason.

**Alternatives rejected**:

- _Keep the Communication section in `CLAUDE.md` as well as adding the style_ — duplicates the rule in two surfaces with no mechanism keeping them in sync, and forfeits the whole point of the relocation, which is getting the paragraphs out of every subagent's context.
- _Add the laconic rules to each agent body instead_ — pays the tokens in every dispatch, in more places, and collides with the house rule against restating in an agent file what its own report format already fixes.

**Trade-off accepted**: agent reports get no terseness directive at all after this phase. Accepted because agent bodies carry their own report formats and the Communication rules were written for chat prose — but it does mean a future "reports got wordier" complaint has no single knob to turn.

### 42. The quality-check cap key includes the working directory

**Choice**: `key=$(printf '%s\n%s' "$norm" "$cwd" | cksum | awk '{print $1}')`, with `cwd` read from the hook payload. The `edits` marker stays per-session and undimensioned.

**Reasoning**: plan-reviewer round 6 raised the parallel-coder case. PreToolUse hooks fire on subagent tool calls, and the orchestration rules explicitly sanction parallel coders in separate worktrees. Keyed on the command alone, coder B's **first** `npm test` denies because coder A already ran it in a different tree — a false deny whose message ("already ran this session and nothing has been edited since") is untrue, the same class decisions 37 and 39 were written to eliminate.

**Alternatives rejected**:

- _Dimension the `edits` marker by cwd too_ — symmetric and wrong: an orchestrator edit in the repo root would then never unlock a coder's run in a worktree, converting a fail-open into a fail-closed on the most common single-agent path.
- _Key on `session_id` only and accept the collision_ — the collision is exactly the false deny, and the sanctioned parallel-coder workflow makes it routine rather than theoretical.

**Trade-off accepted**: two coders in the _same_ cwd share both markers, and one coder's run silently satisfies the other's cap. That is by design — they are editing the same tree — but it is a real gap in the cap's guarantee, not a case the key can distinguish.

### 43. Success Criterion 3 measures file length, and stops being scored as a context saving

**Choice**: keep the `## Git` relocation to `rules/git.md`, keep the portability warn, and annotate Success Criterion 3 to state that only `Communication` and `Orchestration` leave the always-loaded set — `rules/git.md` is `paths: []` and loads unconditionally, so that third section is consolidation into git's single home, not a reduction.

**Reasoning**: plan-reviewer round 6 raised this as an ALT with exercised evidence (`claude/.claude/rules/git.md:2` is `paths: []`). The criterion counts three sections leaving `CLAUDE.md` and reads the line-count delta as progress; for one of the three the content moves from one unconditionally-loaded file into another. The criterion is still a true and checkable statement about file length — the defect was in what a reader would infer from it.

**Alternatives rejected**:

- _Leave `## Git` in `CLAUDE.md`_ — AC8 names the Git section by hand as one of the three that must be gone from that file, and `git.md` is already the sole home of the branch/commit naming convention. Splitting git conventions across two files to avoid overstating a metric is a worse tree for a better number.
- _Give `rules/git.md` a `paths` glob so it loads conditionally_ — the worktree-prefix and diff-focus rules must be known **before** the first matching read, and per this ledger's own `rules/` delivery semantics a globbed file triggers only on reading a matching file. It would make the metric honest by breaking the rule.

**Trade-off accepted**: criterion 3's number now overstates the context saving by three lines and needs its annotation read alongside it. Chosen over either splitting the git conventions or silently deferring their delivery.

## Direction & Constraints

- **The base moved during planning.** HEAD advanced from `350af135` to `0db6d3ee` while this spec was written (`c82532fe agent trim pass`, `0db6d3ee agent trim pass 2`). Any research statement about `claude/.claude/agents/` describes the pre-`c82532fe` tree. Re-check against HEAD before trusting a research line about those files.

- **The `git symbolic-ref` substitution is approved with its behavior change understood (Phase 1).** Verified by live exercise: `git rev-parse --abbrev-ref HEAD` prints the literal `HEAD` and exits 128 on an unborn branch, so the pre-existing main/master commit rule has silently never fired there. After Phase 1 it does. The user approved the change knowing it makes an existing rule stricter on `git init` repos rather than only enabling the new worktree check.
- **Phase 8 keeps the two doctor checks built from trade-off mentions rather than resolved decisions** — orchestration wiring, and the reviewer-calibration reference that `calibration-refs-guard.sh` depends on. Both close silent-failure holes the ledger names; the user approved keeping them rather than holding Phase 8 to resolved decisions only.

### Settled in Phase 2/3 (before the architect ran)

**Scope band (user, Phase 3).** Three bands in scope: (1) mechanize what is deterministic via hook scripts, `permissions.deny`, and agent frontmatter, DELETING the prose each mechanization replaces; (2) relocate prose that cannot be mechanized to its cheapest home; (3) settle the structural inconsistencies the research surfaced.

**Fuzzy-rule policy (user, Phase 3).** A rule without a clean deterministic oracle is still gated, on a conservative pattern, accepting false positives, with `CLAUDE_SKIP_HOOKS` as the escape hatch. Rejected: log-first-tighten-later, and leaving fuzzy rules as prose. **Note: the architect challenges this for exactly one candidate — see Q2.**

**Laconic directive leaves CLAUDE.md (user, Phase 2 walkthrough).** Persona/format directives are not gate material. Original decision was to move to an Output Style; the architect surfaced two complications (exclusivity vs `simple-english`, and overlap with ponytail/caveman) — now tracked as Q3/Q4.

### Architect corrections to the research (accepted as ground truth)

1. **`rules/*.md` DO load.** `rules/git.md` (`paths: []`) was injected verbatim into the architect's own subagent context. They are a working path-scoped injection mechanism, not dead prose. Deleting them as "unread" would be wrong.
2. **"Pick one deny convention" is not achievable.** There are three tiers and the tier is determined by the _event_: PostToolUse has no `permissionDecision` field, so it cannot use stdout-JSON. Only two scripts are genuinely miscategorized (`git-discipline-gate.sh`, `review-commit-gate.sh` — PreToolUse gates using stderr/exit-2).
3. **`skills/code-reviewer-memory/` is untracked.** So is `skills/_shared/memory/code-reviewer/`. Both empty, both `rmdir` with no commit. Not a scope item.
4. **Three dangling cross-references already exist** — `agent-model-guard.sh:26` cites a CLAUDE.md `Behavior §` that no longer exists; the omp bridge documents `mechanical-check-gate.sh`, deleted; `CLAUDE.md:60` names a "stub-guard" that does not exist. The propagation-sweep failure mode has already happened three times here.

### Hard constraints the plan must respect

- **No hook can ever see a subagent's report.** PostToolUse(Agent) fires at launch with a metadata stub. Therefore coder-core's `BEHAVIOR:`/`WHY:`/`REFACTOR CANDIDATES:`/`REVIEW:`/`PLAN-IMPACT:` block (43% of the file) is permanently prose-only. A ceiling, not a gap.
- **Moving content out of CLAUDE.md removes it from every subagent's context.** SessionStart hook output is NOT injected into subagents. `opencode/.config/opencode/AGENTS.md` is a **symlink** to `claude/.claude/CLAUDE.md` — no translation layer.
- **Any new PreToolUse gate must be added to `PRE_TOOL_GATES` in `omp/.omp/agent/hooks/pre/claude-security-bridge.ts`** or it silently does not exist under omp.
- **The three CB-generated scripts are off-limits.** Their YAML generator is not available anywhere — see the Q7 block below. New safety rules go in new hand-written scripts.
- **Their `GENERATED — do not edit directly` header is stale and stays stale (decision 15).** It binds nothing in this plan: no generator exists to regenerate from, and all three are already hand-maintained (12/10/9 commits). An implementer building D1's `PreToolUse(Write|Edit)` hook alongside `write-edit-safety-gate.sh` should read the banner as historical, not as a prohibition — while still not editing those three files, which this plan has no reason to touch.
- **`CLAUDE_SKIP_HOOKS` does not currently cover the hand-written tier** — not checked in git-discipline, review-commit, comment-bloat, spec-budget, dead-prose, claudemd-linecount. The escape hatch D-C relies on is partly fictional today.
- **Hand-written gates have no ERR trap**, so a bug in one exits 1 and the harness allows. Only the generated three fail closed.
- **`calibration-refs-guard.sh` greps reviewer agents for the literal prose line naming `reviewer-calibration.md`.** Replacing that prose with a `skills:` preload silently disables the guard.
- **`skills:` frontmatter needs a real skill directory with `SKILL.md`.** `_shared/*.md` are loose files, not skills.
- **`class=` enum is hand-duplicated** between `log-escape` and `log-review-finding` so the caught and escaped sides cross-tabulate. No shared source; a change touches both.
- **House rules bind the plan's own output**: no rationale in agent/skill bodies (rationale goes in commit messages); the toolkit-edit propagation sweep is mandatory.

### Patterns available (the reusable menu)

A. command-string regex denylist · B. path-glob on resolved path · C. cross-event session state machine · D. agent-scoped gate via `agent_type` · E. content lint on the pending edit · F. word/size budget by displacement · G. structural audit outside the tool-call loop (`claude-doctor.sh`) · H. rule-at-the-moment-of-block (the instruction lives in the deny message, not in per-session context).

### Ruled NOT gateable (architect, adversarial pass — accepted)

LSP-over-grep · `--help`-first · WebSearch-first · keep-diffs-focused · Reuse-Before-You-Write · Fixture Provenance · every handoff-format rule · all Engineering Judgment items.

### Counter-primed approaches (NOT taken)

1. One consolidated mega-gate — destroys per-gate granularity in the omp map, one bug fails everything closed, ambiguous block messages.
2. A model-judged gate (SubagentStop → haiku grader) — reintroduces a model as the oracle, costs a dispatch per coder, and the report isn't in the payload anyway.
3. Deleting `rules/*.md` as unread — refuted on evidence; they load.
4. Moving CLAUDE.md content into auto-memory — `autoMemoryEnabled: false`, and memory is not a rules-precedence surface.

### Confirmed by user (Phase 5, step 12)

The eight patterns above (six from research + `claude-doctor.sh` structural audit + rule-at-the-moment-of-block) are the right ones to build on. The counter-primed four stay rejected.

### `rules/` delivery semantics (Q5 — factual, no fork)

Per the Claude Code memory documentation (https://docs.claude.com/en/docs/claude-code/memory):

- A rules file **without** a `paths` field loads **unconditionally**. This is why `rules/git.md` (`paths: []`) reached the architect's subagent context.
- A rules file **with** `paths` triggers **when Claude reads a file matching the pattern** — not on every tool use, and not from a repo scan. The four globbed files did not load in the architect's dispatch because nothing in it read a `.ts`/`.vue` file.
- Since v2.1.198, matching also works when the file is reached through a **symlinked** path into the project directory — which this repo depends on, as the entire `.claude/` tree is stow-symlinked.

**Consequence for D5**: relocating prose into `rules/` does deliver it, but delivery is _deferred to first matching read_, not available at session start. Path-scoped `rules/` is therefore correct for conventions that only bind once you are inside a matching file, and wrong for anything that must be known before the first read (routing, precedence, safety posture).

### CB generator availability (Q7 — factual, no fork)

Established by direct check, not inference:

- **The generator is not installed and not obtainable from anything this repo knows about.** No `cb` / `cb-hooks` / `claude-hooks` binary on PATH; `~/.local/bin` holds none; the complete global npm list under mise's node 24.18.0 is `@earendil-works/pi-coding-agent`, `corepack`, `diffity`, `hunkdiff`, `npm`; no `.yaml`/`.yml` source exists anywhere under `claude/.claude/` outside vendored plugin trees; and the registered marketplaces are only `caveman`, `claude-plugins-official`, `ponytail`, `simple-english`, `workmux`.
- **The generated set is THREE scripts**, confirmed by the `GENERATED — do not edit directly` marker on line 6: `bash-safety-gate.sh`, `block-credential-read.sh`, `write-edit-safety-gate.sh`, each at `CB Security Hooks / Version: 0.1.6`. The research's count was right. A grep for the string `CB Security Hooks` returns five files, because `git-discipline-gate.sh:5` and `warn-skip-hooks.sh:3` **mention** the generated gates in comments — the first to say which rules it covers that the generated gate does not, the second to state it is "not generated from YAML rules". Both are hand-written and freely editable. Match the header marker, not the product name.
- **Consequence for D3**: the shell-write bypass gate is a new hand-written script. There is no generated-rule route to put it in, so the option the architect raised in Q7 does not exist and D3 stands as decided.

Recorded as a constraint rather than a decision: no alternative existed to choose between.
