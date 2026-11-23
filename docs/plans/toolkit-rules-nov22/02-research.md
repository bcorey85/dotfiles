---
date: 2026-11-22
git_commit: dfb9fd4ef
branch: fix/toolkit-rules-nov22
topic: Agent model hooks, shell-write blocking, interpreter hint, rule text locations, rule-anchors and the rule-meter harness
tags: [hooks, agent-model-guard, bash-safety-gate, inline-interpreter-hint, orchestration, rule-anchors, rule-meter, change-files]
status: complete
---

# Research: Agent model hooks, shell-write blocking, interpreter hint, rule text locations, rule-anchors and the rule-meter harness

## Findings

### Q1. Hooks that act on the `model` field of an Agent call

One script acts on `tool_input.model`: `claude/.claude/scripts/agent-model-guard.sh`. It is the only hook script under `claude/.claude/scripts/` that reads `.tool_input.model` to allow, block or rewrite (`agent-model-guard.sh:42`). `telemetry/log_agent_usage.py:95` reads `model` from tool_input only to log it (`first_truthy(lambda: index(tool_input, "model"), lambda: "inherit")`, row key `model` at `:101`); it never blocks.

Registration: `settings.json:460-466`, a `PreToolUse` group `"matcher": "Agent"` with the command `~/.claude/scripts/agent-model-guard.sh`. Other `"matcher": "Agent"` groups exist at `settings.json:256` (handback `hook ran`, line 260), `:301` (`telemetry/log_agent_usage.py`, line 305) and `:424` (handback `hook dispatch`, line 428); none of those act on model.

Decision order in `agent-model-guard.sh`:
1. `CLAUDE_SKIP_HOOKS` non-empty: exit 0 (`:34`).
2. `tool_name` not `Agent`: exit 0.
3. `subagent_type == "fork"`: exit 0 with any model (`:46-48`).
4. `subagent_type` non-empty and not `^[A-Za-z0-9_-]+$`: deny, reason "Agent call to subagent_type='...' is invalid..." (`:50-54`).
5. Case-insensitive (`nocasematch`) `model` containing `opus`: deny (`:57-67`).
6. Case-insensitive `model` containing `inherit`: deny (`:69-79`).
7. Any other non-empty model: exit 0 (`:84-86`).
8. Empty model and `subagent_type == "web-fetch"`: allow with `updatedInput` = tool_input plus `"model":"haiku"` (`:87-90`).
9. Empty model otherwise: looks for `${CLAUDE_PROJECT_DIR}/.claude/agents/<subagent>.md`, then `${HOME}/.claude/agents/<subagent>.md`; if the found file has a line matching `^model:`, exit 0 (`:92-109`); otherwise deny (`:111-...`).

Not in settings as a hook: `settings.json:186` has a top-level `"model": "opus"` (session model setting).

The script header says "See ~/.claude/CLAUDE.md — "Never spawn Opus subagents."" (`agent-model-guard.sh:30`). That sentence does not appear in `claude/.claude/CLAUDE.md` (no `rg` hit for "never spawn opus" outside docs/changes and docs/plans).

`tests/scripts/toolkit_paths.py:27-31` says the work repo's CB Security Hooks package supplies `bash-safety-gate.sh`, `block-credential-read.sh`, `write-edit-safety-gate.sh`, `agent-model-guard.sh`, `warn-skip-hooks.sh` (`WORK_HOOKS`), and that `agent-model-guard.sh` "carries a local fork pass, tested in test_agent_model_guard.py, that the package must carry too". `bash-safety-gate.sh:4-6` states it is "GENERATED — do not edit directly".

### Q2. Block messages of the model hook

Each deny writes text to stderr and a JSON `permissionDecisionReason` to stdout.

- Opus at call site (`agent-model-guard.sh:60-65`, reason `:66`): stderr "[agent-model-guard] BLOCKED: Agent call sets model containing 'opus' at the call site." / "Call-site Opus is forbidden. The only legitimate way to run a subagent on Opus" / "is a 'model: opus' line in the agent file's own frontmatter." / "Use 'haiku' (read-only/lookup) or 'sonnet' (fan-out implementation) at the call site." JSON reason: "Agent call sets model containing 'opus' at the call site. Call-site Opus is forbidden — add a 'model: opus' pin in the agent file frontmatter instead."
- Inherit (`:72-77`, reason `:78`): "BLOCKED: Agent call sets model containing 'inherit' at the call site." / "Call-site 'inherit' resolves to the orchestrator's model at runtime." / "When the orchestrator is on Opus this silently fans out Opus subagents." / same haiku/sonnet line. JSON reason: "... 'inherit' resolves to the orchestrator model at runtime, silently fanning out Opus subagents."
- No pin (`:112-122`): "BLOCKED: Agent call to subagent_type='X' has no model pin." / "No 'model:' frontmatter was found in the agent file (or the agent file does not exist)." / "Without a pin the subagent inherits the orchestrator's model — silently running Opus when dispatched from an Opus orchestrator." / "Either:" / "Add 'model: <opus|sonnet|haiku>' to the agent file's frontmatter, OR" / "Pass an explicit model at the call site:" with `model: "haiku"` read-only / lookup and `model: "sonnet"` fan-out implementation or analysis. JSON reason (`:123`): "... Add a 'model:' line to the agent frontmatter or pass an explicit model at the call site."
- Invalid subagent_type (`:51`): JSON only, no stderr text.

Call-site versus frontmatter: opus is allowed only through the agent file's frontmatter (`model: opus`); call-site opus and call-site `inherit` are denied; a frontmatter `model:` line of any value (the grep is `^model:` only) lets an empty call-site model pass; any other explicit call-site value passes.

### Q3. Shell-write gate, and the inline-interpreter hint

The PreToolUse(Bash) `shell-write-gate` no longer exists in the tree. `docs/changes/notes/2026-11-21-remove-shell-write-gate.md` (change_type `removed`, kind `user-rule`, asked "2026-11-21: delete it") records the deletion of `gates/shell_write_gate.py` and `lib/shell_write_denial.py`, `lib/shell_write_paths.py`, `lib/interpreter_writes.py`, `lib/inplace_edit.py`, `lib/shell_variables.py`, and the removal of its hook entry from `settings.json`. `rg --files` finds no `shell_write*` file under `claude/.claude/scripts` or `tests`; `settings.json` has no `shell_write_gate`/`shell-write-gate` reference. Its 34 earlier change notes (for example `2026-10-31-shell-write-gate-reads-a-name-joined-onto-a-base.md`) remain in `docs/changes/notes/`.

What currently blocks shell writes, in `scripts/bash-safety-gate.sh` (registered `settings.json:358` as the first PreToolUse(Bash) hook; generated, "do not edit directly", `:5-6`). Each rule is a `grep -qiE` on `$CMD` and calls `block "<[id]> <message>"`; `block()` prints `{"hookSpecificOutput":{..."permissionDecision":"deny","permissionDecisionReason":"<id> ..."}}` and exits 0 (`:70-103`). File-write rules, all limited to protected paths (`.zshrc`, `.bashrc`, `.bash_profile`, `.zprofile`, `.zshenv`, `/.ssh/`, `/.aws/`, `/.kube/`, `/.docker/config`, `.gitconfig`, `.git-credentials`, `.github/workflows`, `.claude/settings.json`, `/etc/`, `Library/LaunchAgents`, `.git/hooks/`):
- `:485-488` `[sed_inplace_protected] [threat:5] sed -i on protected paths is not allowed` (command has `sed -i`).
- `:489-491` `[tee_redirect_protected] [threat:5] Shell redirection to protected paths is not allowed` (`tee` or `>`/`>>` followed by a protected path).
- `:492-495` `[scripted_write_protected] [threat:5] Scripted file writes to protected paths are not allowed` (`python3?|node|perl ... -c|-e ... write|open|writeFile|writeSync` plus a protected path).
- Also `[curl_download_write]` (`:399`), `[wget_download_write]` (`:403`), `[dd_write]` (`:526`).
- Auto-mode pilot: `block()` lets a listed id through under `permission_mode == "auto"` after writing a row to `~/.claude/security-hook-shadow-log.jsonl` (`pilot_shadow`, `:19-31`; the id lists are at `:72-77`, which include `sed_inplace_protected`, `tee_redirect_protected`, `scripted_write_protected`, `interpreter_inline`, `interpreter_stdin`); off switch `~/.claude/security-pilot-off`.

Interpreter rules in the same gate:
- `[interpreter_inline] [threat:7] Interpreter inline execution (python -c, node -e, perl -e) is not allowed — prevents rule bypass` at `:311-314`: pattern `\b(python3?|node|perl|ruby|php)\b[^;|&]*(\s-(c|e|r)\b|\s--?(eval|command)\b)` on `$CMD_UNQUOTED` (quoted spans blanked), unless `$CMD` matches the ALLOWED imports (`import json|sys|os.path|pathlib|re|...`, `JSON.parse|stringify`, `require(`, `console.log|...`, `process.version|...`, `Buffer.from|alloc`).
- `[interpreter_stdin] [threat:7] Interpreter code from stdin or a heredoc (python3 - <<EOF, echo x | python3) is not allowed — prevents rule bypass` at `:316-318`.

Inline-interpreter hint: `claude/.claude/scripts/gates/inline_interpreter_hint.py`, registered `settings.json:360-363` as the second PreToolUse(Bash) hook. Its docstring (`:2-16`) says the safety gate's own block text names no other path, so this hook re-runs the gate's patterns through the system `grep` and denies with a message saying what to do instead.
- Match: `INLINE = r"\b(python3?|node|perl|ruby|php)\b[^;|&]*\s(-(c|e|r)|--?(eval|command))\b"` (`:30-32`) on the command with quoted text blanked to `_` (`without_quoted_text`, `:~150`); `ALLOWED` (`:39-43`) is the same import/JSON/console allow-list; `INTERPRETER_FAMILIES`/`INTERPRETER` come from `lib/shell_command.py`. Also denied: stdin code to a bare interpreter via `runs_stdin_code` (`shell_command.reads_code_from_stdin`), inline flags before the script file (`flags_before_script_run_inline_code`), nested `bash -c`/`ssh`/`eval`/`$(...)` command strings (`nested_shell_runs_inline_code`). `blocked()` at `:170-175`: stdin code gets no ALLOWED excuse; inline code is blocked unless `grep ALLOWED` matches.
- Deny text (`TEXT`, `:46-52`): "Inline interpreter runs (python3 -c, node -e, perl -e, manage.py shell -c) and code fed on stdin to a bare interpreter (python3 -, python3 <<'EOF', cat file | python3) are blocked. Do not retry another inline form. Write the code to a script file in your scratchpad directory with the Write tool, then run the file: python3 <file>, node <file>, or python manage.py shell < <file>. A script file may still read data on stdin (python3 <file> <<'EOF'). If the command holds no inline code, run the interpreter step as its own Bash call, apart from any later -c, -e or -r flag."
- Auto-mode pilot (`pilot_passes`, `:181-196`): under `permission_mode == "auto"` and no `~/.claude/security-pilot-off`, a hit is written to the shadow log (`hook: "inline-interpreter-hint"`) and not denied; if the log write fails it is denied.
- Same hook also denies: an uncapped test run (`memory_cap_scope.DENY_TEXT`, `:221`) and a foreground full-suite run in a main session (`memory_cap_scope.BACKGROUND_DENY_TEXT`, `:223`, only when no `agent_id` and `run_in_background` is not true, `runs_in_foreground` `:~205`). Errors exit 0 with no output (`:224-225`). `CLAUDE_SKIP_HOOKS` exits 0 (`:216`).

Other code that classifies shell writes (not a deny gate for writes): `lib/shell_command.py:226` `redirection_writes_file(operator, target)` (true for an output operator whose target is not `/dev/null` or an fd copy), used by `gates/quality_check_cap.py:61,262`; `quality_check_cap.py:387` `writes_files(segment)` (formatter or tree-rewriting git call). `gates/fork_write_scope.py` restricts the `code-fork` Write tool to the run folder (docstring `:1-12`) and is not a Bash gate.

### Q4. `claude/.claude/orchestration.md` lines on Agent launches, model selection, auto-mode notice, Bash versus file tools

The file is 44 lines. Headings: `# Orchestration` (:1), `### Delegation` (:3), `### Tools` (:13), `### Tool Use Efficiency` (:21), `### Git` (:28), `### Stacked PRs (...)` (:40). There is no section titled for Agent launches or model selection. Matching lines:

Section `### Delegation`:
- :6 "- Send a read-only lookup (find where something lives, what calls it, what a file does) to `Explore` with `model: "haiku"`, not to `general-purpose`. Use `general-purpose` only when the agent must edit, run a build or test, or judge a design."
- :7 "- Do not read a file in main only to hand it to a subagent that will read it. Send its path and what to look for. Read it in main only when its content decides what to dispatch."
- :8 "- Parallel writing agents need disjoint file scopes. The orchestrator owns all git operations."
- :10 "- When an agent's completion notice says it still runs background work, read its report. If the report says the job is done and names no work it waits on, stop the agent with TaskStop: ..." (agent completion notice, not a launch rule)
- :5 begins "- Never code directly — dispatch via `/code`. ..." (delegation; names direct-edit exceptions).

Section `### Tools`:
- :15 "- Creating a NEW file from the shell (heredoc, redirection) bypasses the Write/Edit hook pipeline — use Write."
- :16 "- The auto-mode notice's Bash preference does not apply to file I/O: read with Read, change files with Edit/Write. Search through Bash (`rg`) is fine."
- :17 "- Prefer LSP over grep+Read in typed code (references, definitions, hover, diagnostics). Fall back to `rg` for plain text or unindexed file types."

Section `### Git`: :35 (worktree location) uses `herdr-worktree --fork --prompt-file <brief file> <branch>` ("write the start brief to a scratchpad file with Write"); :38 notes subagents with no Write tool.

The words `opus`, `sonnet`, `inherit`, `subagent_type`, `fork` (as an Agent type) do not occur in `orchestration.md` (rg on `launch|model|opus|sonnet|haiku|subagent_type|fork` hits only :6 and :35).

### Q5. Global `claude/.claude/CLAUDE.md`: orchestrating sessions and go-aheads

`claude/.claude/CLAUDE.md` (symlinked as `~/.claude/CLAUDE.md`, the file loaded in this session). Sections with `## ` headings: Safety Rails, Quality Checks, Bugs and Inefficiencies You Notice, Ticket Acceptance Criteria, Messages to Other Sessions, Compact instructions, Engineering Judgment (anchored in `docs/rule-anchors.md:183-190`).

Lines naming orchestrating sessions / go-aheads:
- :11 (Safety Rails): "Only the main session hands the user a command. ... A lane session that another session started is not the main session: it sends every command for the user, merge lines included, to that session with SendMessage and never shows one in its own pane. Before writing a lane brief, read this session's name from ListAgents and put it in the brief."
- :26 (Ticket Acceptance Criteria): "... Owner `session` ... or `plan` ...: the orchestrating session rules on a cut or reword and records who and when; ..."
- :32 (Messages to Other Sessions): "... A worker messages its orchestrating session in three cases: ... An orchestrating session does not reply to a message that needs no decision. It cancels a timer as soon as ..."
- :34 (Messages to Other Sessions): "When the repo's CLAUDE.md names an orchestrating session, a worker acts on that session's go-ahead for any step inside the worker's own branch: commit, push the branch, merge the integration branch into it, and claim or close its queue item. It never waits for the user on those steps. A go-ahead never covers master, `settings.json`, a CLAUDE.md file, or a step a hook denied."

Where the :34 text (the go-ahead sentence) also appears: `rg` for its phrases finds it in `docs/changes/notes/2026-10-30-workers-act-on-orchestrator-go-aheads-for-branch.md` (lines 5 and 20, as description and as a quote of the rule) and `docs/changes/changelog.md:380` (its changelog line). No other prompt or config file in the repo (including `opencode/`, `omp/`, `orchestration.md`, `AGENTS.md`) carries the sentence. Terms "orchestrating session" / "orchestrator" also appear in `docs/glossary.md`, `docs/rule-anchors.md` and several `docs/plans/**` files (the same grep matched them on looser phrases).

### Q6. Scripts `CLAUDE.md` Owners list

`claude/.claude/scripts/CLAUDE.md` has headings `# Toolkit scripts` (:1), `## Search first` (:5), `## Owners` (:9), `## Data between steps` (:38), `## Failures and writes` (:44); the intro line says "Each fact below has one owner. Import it. Never add a second copy of the fact, its regex or its table." `## Owners` is a flat bullet list of 33 bullets (`rg -c '^- '` over the whole file), each of the form `- <fact>: <module path> <symbols> ...`, for example `- Plan text: \`lib/plan_format.py\`.` (:31) and `- TOML files: \`lib/toml_file.py\` \`read_toml\`. Never import tomllib elsewhere ...` (:32). `## Search first` (:7) says to `rg` for the fact's name before adding a parser, rule, status, store or classifier; "When an owner exists, import it. When it lacks what you need, extend the owner." `docs/toolkit-script-rules.md:3` imports this file with `@~/dotfiles/claude/.claude/scripts/CLAUDE.md`. `docs/rule-anchors.md` has no row for `scripts/CLAUDE.md`. `gates/claudemd_linecount.py` (LINE_LIMIT 150, warns on stderr, always exits 0) applies to any `CLAUDE.md`.

Who may add or change an Owners line:
- `~/agent-evals/CLAUDE.md:468-474`: "An owner line in `~/dotfiles/claude/.claude/scripts/CLAUDE.md` (a pointer to the module that owns a fact) is the exception: the session decides it, writes it with a change file, and never asks the user. The user, 2026-11-22, asked to stop being asked about owner lines in the scripts CLAUDE.md." This is the exception to the sentence at `:463-466`: "No rule enters a toolkit skill, agent, command, hook prompt or CLAUDE.md (the files under `~/dotfiles/claude/.claude/`) without rule-meter runs."
- No file in `~/dotfiles-toolkit-rules-nov22` (CLAUDE.md, docs/, scripts/CLAUDE.md) states who may add or change an Owners line (`rg -i 'owner line'` outside docs/changes and docs/plans finds nothing).
- Example change file for an Owners edit: `docs/changes/notes/2026-11-22-scripts-owner-list-names-the-work-tree-s-git-tree.md` (change_type `changed`, kind `user-rule`, components `["rule/scripts-claude-md"]`, evidence `["user request","judgment"]`, `asked` quotes the user's "yes", `unmeasured`: "No rule-meter run: ...", sections Change/Evidence/Result/Watch/Back-out). Earlier: `2026-11-14-scripts-folder-claude-md-names-the-owner-of-commit.md`. Commit history: `ac11605e0` (latest), `4732aaf3c`, `3ea0f1f6a`.

### Q7. Rule-anchors mechanism

Script: `claude/.claude/scripts/tools/rule-anchors.sh`. Commands (`:2-9`, `:35-59`):
- `rule-anchors.sh list <file>...`: prints `hash TAB file TAB heading` per block; paths relative to the `.claude` dir (`CLAUDE_DIR`).
- `rule-anchors.sh check`: reads the sidecar, takes every file named in its rows, and for each file reports `MISSING FILE  <rel>` (file absent), `UNANCHORED  <rel> <hash> <heading>` (a current block whose 8-char hash has no row for that file) and `STALE  <rel> <hash> <section>` (a row whose hash no current block has). Exit 1 on any fault, 0 otherwise. Any other verb prints usage and exits 2.
- Block definition: a heading line (`^#{1,6} `) plus text to the next heading outside a code fence; text before the first heading is `(preamble)`; whitespace runs collapse to one space; hash is `sha256sum | cut -c1-8` (`:15-26`).
- Sidecar: `SIDECAR="${RULE_ANCHORS:-$CLAUDE_DIR/../../docs/rule-anchors.md}"` (`:13`) = `docs/rule-anchors.md`. Rows are markdown table lines `| hash | file | section | evidence | reason |` (the awk takes rows whose second field is hex); header text in `docs/rule-anchors.md:1-27` gives the 4-step edit procedure and the evidence kinds (`gate ranking`, `census`, `removal round`, `seeded round`, `controlled replay`, `rule meter`, `judgment`, `unproven`, plus others used in rows such as `user rule`, `hook block log`).
- `claude-doctor.sh:228-236` section 4e runs `rule-anchors.sh check` and prints `rule anchor: <line>` errors (header comment `:13`).
- Test: `tests/scripts/test_rule_anchors.py::RuleAnchorsTest::test_every_prompt_block_has_a_current_row` runs `bash rule-anchors.sh check` (env `RULE_ANCHORS_SCRIPT` overrides the path) and requires no output.

Rows for global `CLAUDE.md` (`docs/rule-anchors.md:183-190`, hash / section / evidence):
- d49ae4a9 `# Global Claude Code Rules` / unproven
- af3fc96c `## Safety Rails` / hook block log, removal round, sealed round, judgment, user rule
- d7190cb5 `## Quality Checks` / removal round, user rule
- 6e3726cd `## Bugs and Inefficiencies You Notice` / user rule
- 2ad6e36a `## Ticket Acceptance Criteria` / judgment
- a1ceac7b `## Messages to Other Sessions` / census, user rule
- 8b1826a7 `## Engineering Judgment` / removal round, seeded round, judgment, user rule
- 3e30b77d `## Compact instructions` / unproven

Rows for `orchestration.md` (`:191-196`):
- c263556a `# Orchestration` / unproven
- 37b5ea1e `### Tools` / removal round
- 3c347f82 `### Tool Use Efficiency` / removal round
- 2ebac3a6 `### Delegation` / removal round, census
- f0f98f35 `### Git` / removal round, rule meter, judgment, user rule
- cb8fd8eb `### Stacked PRs (...)` / removal round

Rows exist for other files too (agents/code-reviewer.md, skills/coder-core/SKILL.md, etc.; `rg '^\| [0-9a-f]{8} \| CLAUDE.md'` shows the CLAUDE.md block). No row has file `scripts/CLAUDE.md`. Change-file note introducing the check: `docs/changes/notes/2026-11-02-rule-anchors-fail-ci-when-a-prompt-block-drifts.md`.

### Q8. Rule-meter harness (`~/agent-evals/bin/`)

Files: `rule_meter.py` (2723 lines), `rule_meter_scenarios.json`, `rule_meter_config.py`, `rule_meter_families.py`, `rule_meter_fixture.py`, `rule_meter_index.py`, `rule_meter_plans.py`, `rule_meter_regress.py`, `rule_meter_stacks.py`, `rule_meter_coder5.py`, `rule_meter_verifier.py`, `rule_meter_shipped.json`, `rule_meter_plants/`, `rule_meter_checks/` (11 files: `async_panel_states.mts`, `async_view_states.mts`, `branch_has_failing_test.py`, `incidental_owner_filters.py`, `keep_behavior.mts`, `keep_date.mts`, `keep_quantity.mts`, `second_owner_mutation.py`, `stale_docs.mts`, `sweep_defaults.mts`, `sweep_owner_check.mts`, `weak_fix_test.mts`) and `test_rule_meter*.py`.

Concept (`rule_meter.py:1-37`): one cell = rule x level (`LEVELS = supportive, neutral, competing`, `:87`) x arm (`ARMS = ("on", "off")`, `:88`). A cell builds a bench tree from the ticketsim fixture (`build_tree`, `:2390`), writes the arm CLAUDE.md (`write_arm_claude_md`, `:1696`), runs `claude -p` on the scenario task, and grades the recorded tool calls and tree with a detector (`grade`, `:1435`). Outcomes: COMPLIED, VIOLATED, NO_TEST, NO_CHANGE, ERROR. Commands: `run --rule A --level competing --arm on [--run 1] [--dry-run]`, `run-all [--runs N] [--level L] [--dry-run]` (runs only the runs `results.jsonl` lacks), `summary` (complied/graded per cell; per rule, compliance on minus off). Trees and results under `~/dev/evals/rulemeter1/` (`ROUND`, `RESULTS = runs/results.jsonl`, `:~75`).

Scenario definition (`rule_meter_scenarios.json`, a dict keyed by rule id, 105 entries). Keys and counts: `name`, `setup`, `detector`, `task`, `suffix` (object with `supportive`/`neutral`/`competing` strings appended to the task, `build_prompt` `:1646`) on all 105; `rule_text` 97; `rule_source` 91; `toolkit_root` 86; `agent` 84; `plant` 76; `note` 71; `model` 40; `family` 21; `split` 10; `rule_file` 8; `retired` 6. Example, scenario `WT01` (`rule_source` `orchestration.md`, `rule_text` "Create a worktree only when the user explicitly asks for one; ...", `detector` `no_unasked_worktree`).
- `rule_text`: verbatim text of the rule inside its source; the off arm is the source with this text removed once (`rule_source_for_arm`, `:1594-1603`, `remove_once`; "loud when not found").
- `rule_source`: a toolkit file relative to the toolkit root; default is global `~/.claude/CLAUDE.md` (`rule_source_path`, `:1614-1620`). The global CLAUDE.md is appended whole in both arms (docstring `:34-37`).
- `agent`: runs the session as that agent with the agent file and its listed skills copied into the tree's `.claude/` (`write_agent_files`, `:1754`).
- `model`: default sonnet (docstring `:26`).
- `plant`: scenery code committed before the base sha.
- `rule_file`: whole file under the toolkit root copied into the on arm only (`check_rule_file`, `:1640-1647`).
- `toolkit_root`: `~`-expanding path to the toolkit tree the scenario reads agent file, skills and rule source from, else `~/.claude` (`toolkit_home`, `:1605-1611`). Values are other worktrees (e.g. `~/dotfiles-coder-worktree-fixes/claude/.claude` for WT01), per-round copies under `~/dev/evals/rulemeter1/toolkits/<name>/claude/.claude`, or `~/dev/evals/rulemeter-testrev/toolkit/claude/.claude`.
- `retired`, `family`, `split` (tune/held-out), `note` are metadata.

Detectors: the scenario's `detector` string is looked up in dicts in `rule_meter.py`/sibling modules: `CODER5_DETECTORS` (`:133`), `STACK_DETECTORS` (`:147`), `STACK_RED_DETECTORS` (`:153`), `RECORD_DETECTORS` (`:1361`), `rule_meter_fixture.DETECTORS` (`:1477`), `rule_meter_verifier.DETECTORS` (`:1479`), among others; `grade()` dispatches. Hidden behavior checks live in `rule_meter_checks/` (`CHECK_SOURCES`, `:161`, 120 s timeout `CHECK_TIMEOUT_SECONDS`): `.mts` checks run via `node --no-warnings <script> <target>` (`:1226`) and `.py` checks via `python -I -B <script> ...` (`:1275`, `:1301`, `:1309`). NO_TEST there means the check could not run, tests were red before mutation, or nothing to mutate.

Recording results in a change file: per `~/agent-evals/CLAUDE.md:456-474`, create it with `python3 bin/build_changes.py new "<title>" --by claude-code/<model id>`, fill it, then `python3 bin/build_changes.py`; per-arm counts go in the change file's `## Result`; evidence kind `rule meter` (frontmatter `evidence: ["rule meter"]`); a `structured`/`open` change names in `proof` finding stems with at least 8 (structured) or 32 (open) runs per arm (`build_changes.py:57`, `PROOF_FLOORS`). Settled results also go in `findings/` via `build_findings.py new`. Required frontmatter keys (`build_changes.py:41-46`, `:162-171`): `type: "Change"`, `change_type`, `title`, `description`, `generated {by, at}`, `seq`, `components`, `evidence`, `watches`; optional `kind`, `test`, `asked`, `proof`, `unmeasured`, `overlap`, `regression`, `reverts`, `impact`. Body headings in order: Change, Evidence, Result, Watch, Back-out. Rule-meter gating text: `~/agent-evals/CLAUDE.md:462-474` ("No rule enters a toolkit skill, agent, command, hook prompt or CLAUDE.md ... without rule-meter runs" for a new and a reworded rule, of every `kind`; "Until both arms have run, the edit stays on a branch or uncommitted"; a rule the meter cannot grade says so in `unmeasured` and goes to the user). Also `python3 bin/rule_trials.py search "<words>"` before writing a rule and `rule_trials.py build` after each round (`:475-478`).

### Q9. Existing scenarios and change files for reworded, added and deleted rule lines

Scenarios (all in `~/agent-evals/bin/rule_meter_scenarios.json`):
- Added rule (on arm has the line, off arm lacks it): `WT01` (orchestration.md, worktree only when asked; `toolkit_root` `~/dotfiles-coder-worktree-fixes/claude/.claude`); `AF` (agents/code-reviewer.md, `toolkit_root` `~/dev/evals/rulemeter1/toolkits/docs-wording/claude/.claude`, model opus, plant `plant_docs_wording`).
- Reworded rule: `WR01`..`WR04` and `WRB1`/`WRB2` (orchestration.md; `WR01`'s note: "The reworded worktree rule, read from a copy of the branch fix/workers-report-to-orchestrator ... The off arm is the sentence deleted.", toolkit_root `~/dev/evals/rulemeter1/toolkits/wr-new/claude/.claude`, detectors `keeps_user_in_this_pane` / `brief_routes_fork_questions`); `PJ07B`/`PD07B` (family `repo-error-class`, splits `tune`/`held-out`; note "PJ07 with the rule line reworded to name raise and a built-in Python error", `rule_file` `rules/backend.md`).
- Deleted/retired rule: `AA` (coder-core, "Retired from the live coder-core on 2026-11-08 after scoring 8 of 8 in both arms; this pins the toolkit that still carried the sentence.", `toolkit_root` a saved copy `.../toolkits/readability-49fcc309/claude/.claude`); `retired: true` on `N`, `O`, `P`, `Z`, `O2`, `Z2` (toolkit_root pins an older worktree or toolkit copy).
- Reviewer/test-reviewer families with quiet twins: `TR01`..`TR04` and `TR01Q`..`TR04Q` (family, split, note naming the false-alarm twin).

Change files (all under `~/dotfiles-toolkit-rules-nov22/docs/changes/notes/<date>-<slug>.md`, built into `docs/changes/{index,changelog,what-worked,fixes-by-script,ruled-out,in-progress}.md`). Counts of `change_type`: added 58, changed 378, fixed 602, removed 61, security 1. Fields shown by real examples:
- Added rule with meter proof: `2026-11-02-coder-fixes-every-site-of-a-reviewed-defect.md` (change_type `changed`, kind `structured`, components `["skill/coder-core"]`, evidence `["rule meter"]`, `proof` one finding stem, `impact {"metric":"quality","before":100,"after":6,"unit":"% of runs leaving a sibling site unfixed","finding":...,"better":"lower"}`, `unmeasured` text; Result says 0 of 16 to 15 of 16; Back-out "Delete the ... section").
- Removed (deleted component): `2026-11-21-remove-shell-write-gate.md` (change_type `removed`, kind `user-rule`, `asked`, `watches` two ids, `test` path::name, `unmeasured`).
- Owner-line edit (reworded/added line, no meter): `2026-11-22-scripts-owner-list-names-the-work-tree-s-git-tree.md` (kind `user-rule`, `unmeasured` "No rule-meter run: ...").
- Evidence kinds across all notes (top counts from `evidence:` lines): judgment 540, census 102, removal round 30, `work incident` 21, `user rule` 15, seeded round 15, `rule meter` 9.
- Anchor rows record the rule-meter link: `docs/rule-anchors.md` rows citing `rule meter` evidence include `f0f98f35` (orchestration.md `### Git`) and `a96a963a`/`dfb91d45`/`0148f08a`/`b98d9c52` (skills).

### Q10. `toolkit-writing` skill and no-op/duplicate flagging

`claude/.claude/skills/toolkit-writing/SKILL.md` (only file in the folder). Opening: "Every line ... is read on each load. A line ships only when it changes what the agent does." Terms: No-op ("a line whose prevented failure you cannot name: the agent would act the same without it"), Duplicate ("a rule stated twice, in one file or across files. Keep one owner; point to it from the rest"), Cache, Sprawl, Weak pointer, Sediment, Dense rule (more than one branch or more than three conditions). Eight Checks: Description is the trigger; User-invoked or model-invoked (`rg` callers before `disable-model-invocation: true`); Done when; Lead with the action; Exactness matches fragility; One default; Order by use; Prune ("Cut each no-op, duplicate, cache and sediment line. Fix each weak pointer, sprawl and dense rule."). Section `## Cutting a rule`: "A no-op or duplicate flag on an existing rule is a candidate. Test it with `~/agent-evals/bin/rule_meter.py` before you cut it. A new or reworded rule follows the agent-evals rule workflow. Done when every line of the changed text passes the eight checks, or carries a rule-meter candidate note in your report."

How the repo flags such lines:
- `claude/.claude/skills/audit/retro.md:45` table row: "No-op rule line | A deletion candidate, to test with `~/agent-evals/bin/rule_meter.py` before cutting". `skills/audit/retro.md:52` and `:63` give the `build_queue.py prior` / `new` commands for candidates.
- `claude/.claude/skills/list/SKILL.md:31`: `Gate` values `direct`, `meter` ("a new or reworded rule, needs rule-meter runs first"), `user`.
- `~/agent-evals/CLAUDE.md:475-478`: "Write and judge the rule's wording with the `toolkit-writing` skill. A line it flags as a no-op or a duplicate is a candidate for a removal round, never a cut on its own." Also `rule_trials.py search` (NO-EFFECT, ALREADY, BACKFIRE logged results are "not new").
- Hooks: `gates/dead_prose_gate.py` (PostToolUse Write|Edit, warn on stderr, always exits 0) flags banned rationale regexes (e.g. "(you|this|it) exists?( only)? because", `the reason (you|this|it) exists?`) in `.claude/{agents,skills}/*.md`, and hardcoded paths in agents/skills/commands (`dead_prose_gate.py:2-25`); `gates/claudemd_linecount.py` warns above 150 lines (`LINE_LIMIT = 150`).
- Repo `CLAUDE.md` section "Working with This Repo": "No rationale in agent/skill bodies ..." and the "Toolkit-edit propagation sweep" bullet.
- `docs/rule-anchors.md` evidence kind `unproven` ("never exercised") is the repo's label on blocks with no measurement (`# Orchestration`, `# Global Claude Code Rules`, `## Compact instructions`).
- `claude-doctor.sh` and `rule-anchors.sh check` flag a block with no row; neither detects a no-op or duplicate.

### Q11. Tests for the model hooks, shell-write gate and rule-anchors check

All under `~/dotfiles-toolkit-rules-nov22/tests/scripts/`:
- `test_agent_model_guard.py` (172 lines): `SCRIPT` from env `AGENT_MODEL_GUARD` or `toolkit_paths.SCRIPTS_DIR / "agent-model-guard.sh"` (`:13`); helpers `write_agent_files(root, agent_files)` (`:16`), `run_guard(tool_input, home_agents=None, project_agents=None, tool_name="Agent", extra_environment=None)` (`:25`, builds a temp HOME and `CLAUDE_PROJECT_DIR`, pipes the event JSON to `bash <script>`, returns `(exit code, parsed stdout JSON)`), `denial_reason(reply)` (`:51`). 19 tests in `AgentModelGuardTest` (:59-165): fork with no model / opus / inherit passes; unpinned agent without file denied; forker without model or file denied; frontmatter pin passes; project agent file preferred over home; invalid subagent_type denied; explicit non-opus passes; opus and inherit on non-fork denied; `CLAUDE_SKIP_HOOKS` passes opus; non-Agent tool passes; opus and inherit match ignores case; unpinned web-fetch runs pinned to haiku; web-fetch with explicit sonnet left alone; web-fetch with opus or inherit denied; unpinned general-purpose still denied. No fixture files; agent files are written to temp dirs.
- `test_agent_hook_registration.py` (30 lines): reads `claude/.claude/settings.json` and requires exactly one agent-model-guard command under PreToolUse matcher `Agent` (`test_exactly_one_agent_model_guard_runs_on_agent`).
- `test_inline_interpreter_hint.py` (188 lines): `HOOK = toolkit_paths.GATES_DIR / "inline_interpreter_hint.py"` (`:10`); tables `DENIED_COMMANDS` (`:12`) and `ALLOWED_COMMANDS` (`:105`); 3 tests in `InlineInterpreterHintTest` (`:161`): `test_inline_and_stdin_code_is_denied` (:170), `test_a_script_file_module_or_version_flag_is_allowed` (:175), `test_the_deny_names_the_scratchpad_script_and_the_stdin_forms` (:180).
- `test_rule_anchors.py` (30 lines): `RuleAnchorsTest.test_every_prompt_block_has_a_current_row` (see Q7); skipped when `awk` lacks regex interval support (`awk_reads_heading_intervals`, `:13-16`).
- Shell-write gate: no test file exists now (the four test files were deleted with the gate, per `2026-11-21-remove-shell-write-gate.md`). `tests/scripts/test_hook_if_filters.py:34-35` lists `bash-safety-gate.sh` and `gates/inline_interpreter_hint.py` among scripts that fire per command (the removed note names `test_hook_if_filters.py::HookIfFiltersTest::test_scripts_that_fire_per_command`). `tests/scripts/test_directory_emptying_deletes.py:190` reads `bash-safety-gate.sh` text. `tests/scripts/gate_replay.py`, `gate_replay_corpus.json` and `test_gate_replay.py` hold replay rows; the corpus has 2 rows that mention `bash-safety-gate`/`inline_interpreter`/`agent-model` (the `redundant` field's description at corpus `:5` names bash-safety-gate.sh). No dedicated test file exercises `bash-safety-gate.sh` directly (rg for its name in tests lists only `toolkit_paths.py`, `test_hook_if_filters.py`, `test_directory_emptying_deletes.py`, `gate_replay_corpus.json`, `fixtures/script_path_quoted_heredoc.sh`).
- Shared: `tests/scripts/toolkit_paths.py` (`SCRIPTS_DIR`, `TOOLS_DIR`, `GATES_DIR`, `LIB_DIR`, `CLAUDE_DIR`, `WORK_HOOKS`). Run through `python3 tests/parallel_tests.py <test file name>` and `bash tests/run.sh` (docs/toolkit-script-rules.md "Tests").

## Dormant scaffolding

- `agent-model-guard.sh:30` comment cites `~/.claude/CLAUDE.md — "Never spawn Opus subagents."`; no such sentence exists in `claude/.claude/CLAUDE.md`.
- `settings.json:186` `"model": "opus"` is a top-level setting, not read by any hook script in `scripts/`.
- `log_agent_usage.py:95` defaults a missing `model` to the string `"inherit"` in its log row; the model guard denies the same string at the call site.
- `inline_interpreter_hint.py` INLINE, ALLOWED, TEXT duplicate the patterns of `bash-safety-gate.sh:311-318` (the docstring `:3-5` says it runs the gate's own patterns); `ALLOWED` text appears in both files.
- `tests/scripts/toolkit_paths.py:27-31` `WORK_HOOKS` lists `bash-safety-gate.sh`, `block-credential-read.sh`, `write-edit-safety-gate.sh`, `warn-skip-hooks.sh` as "not tested here".
- `rule_meter_scenarios.json` entries with `retired: true`: N, O, P, Z, O2, Z2; scenarios with `rule_text` count 97 of 105 (8 use `rule_file`).
- `docs/rule-anchors.md` has no row for `claude/.claude/scripts/CLAUDE.md` or `docs/toolkit-script-rules.md`.
- `orchestration.md` has no Agent-launch or model-selection section; `model: "haiku"` appears only in the `Explore` line (:6).

## Code References

- `claude/.claude/scripts/agent-model-guard.sh:34-123` - full model guard logic and deny texts.
- `claude/.claude/settings.json:460-466` - PreToolUse(Agent) registration of agent-model-guard.
- `claude/.claude/settings.json:358-363` - PreToolUse(Bash) bash-safety-gate then inline_interpreter_hint.
- `claude/.claude/scripts/bash-safety-gate.sh:70-103` - `block()` and pilot shadow handling; `:311-318` interpreter inline/stdin; `:485-495` protected-path write rules.
- `claude/.claude/scripts/gates/inline_interpreter_hint.py:30-52` - INLINE/ALLOWED/TEXT; `:170-225` blocked/pilot/main.
- `claude/.claude/scripts/lib/shell_command.py:226` - `redirection_writes_file`.
- `claude/.claude/orchestration.md:3-16` - Delegation and Tools lines cited in Q4.
- `claude/.claude/CLAUDE.md:11,26,32,34` - lane/orchestrator/go-ahead text.
- `claude/.claude/scripts/CLAUDE.md:9-36` - Owners list.
- `claude/.claude/scripts/tools/rule-anchors.sh:1-59` - anchors script.
- `docs/rule-anchors.md:183-196` - CLAUDE.md and orchestration.md rows.
- `claude/.claude/skills/toolkit-writing/SKILL.md` - line-writing rules.
- `~/agent-evals/bin/rule_meter.py:87-88,161,1594-1650,1696,2390` - levels, arms, toolkit_root, arm CLAUDE.md, tree build.
- `~/agent-evals/bin/rule_meter_scenarios.json` - 105 scenarios.
- `~/agent-evals/CLAUDE.md:456-478` - change file and rule-meter workflow; owner-line exception.
- `docs/changes/notes/2026-11-21-remove-shell-write-gate.md` - deletion of the shell-write gate.
- `tests/scripts/test_agent_model_guard.py`, `test_agent_hook_registration.py`, `test_inline_interpreter_hint.py`, `test_rule_anchors.py`, `toolkit_paths.py`.

## Patterns Found

- Deny output form: hook emits `{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":...}}` and exits 0 (agent-model-guard.sh, bash-safety-gate.sh `block()`, inline_interpreter_hint.py `emit_deny`).
- `CLAUDE_SKIP_HOOKS` non-empty exits 0 in agent-model-guard.sh, bash-safety-gate.sh and inline_interpreter_hint.py.
- Auto-mode pilot in bash-safety-gate.sh and inline_interpreter_hint.py: record to `~/.claude/security-hook-shadow-log.jsonl`, switch `~/.claude/security-pilot-off`.
- The model guard exists as a bash script, tested by running the script through `subprocess` with a JSON event on stdin; gates in `gates/` are Python invoked by `sh ~/.claude/scripts/tools/hook-python <path>`.
- Prompt-file blocks are hash-anchored per heading in `docs/rule-anchors.md`; every toolkit edit also gets a change file under `docs/changes/notes/` with sections Change/Evidence/Result/Watch/Back-out.
- Rule-meter scenarios pin a prior or alternate toolkit through `toolkit_root` and the off arm is the source minus the `rule_text`.

## Reuse Inventory

- `agent-model-guard.sh` (stdin hook JSON -> deny JSON or exit 0) - `claude/.claude/scripts/agent-model-guard.sh:1` - Agent model gate.
- `inline_interpreter_hint.blocked(command) -> bool` - `claude/.claude/scripts/gates/inline_interpreter_hint.py:170` - true when the gate's inline/stdin interpreter rules fire.
- `inline_interpreter_hint.runs_inline_code(command) -> bool` - `:160` - inline-flag detection with nested shell, ssh, eval and substitution.
- `inline_interpreter_hint.without_quoted_text(command) -> str` - `:~127` - blanks quoted text.
- `inline_interpreter_hint.runs_stdin_code(command) -> bool` - `:~58` - stdin code to bare interpreter.
- `inline_interpreter_hint.emit_deny(reason)` - `:199` - writes the PreToolUse deny JSON.
- `shell_command.redirection_writes_file(operator, target) -> bool` - `claude/.claude/scripts/lib/shell_command.py:226` - whether a redirection writes a file.
- `shell_command.is_redirect_word(word)`, `redirect_takes_next_word(word)` - `lib/shell_command.py:236,242` - redirect word classification.
- `rule-anchors.sh list <file>...` / `check` - `claude/.claude/scripts/tools/rule-anchors.sh` - hashes and sidecar check; env `RULE_ANCHORS` overrides the sidecar path.
- `run_guard(tool_input, home_agents=None, project_agents=None, tool_name="Agent", extra_environment=None) -> (code, reply)` - `tests/scripts/test_agent_model_guard.py:25` - harness for the model guard.
- `write_agent_files(root, agent_files)` - `tests/scripts/test_agent_model_guard.py:16` - writes `.claude/agents/<name>.md` into a temp root.
- `denial_reason(reply) -> str|None` - `tests/scripts/test_agent_model_guard.py:51` - extracts a deny reason.
- `agent_pretooluse_commands() -> list[str]` - `tests/scripts/test_agent_hook_registration.py:11` - hook commands registered under PreToolUse matcher Agent.
- `awk_reads_heading_intervals() -> bool` - `tests/scripts/test_rule_anchors.py:13` - awk capability probe.
- `toolkit_paths` constants (`SCRIPTS_DIR`, `TOOLS_DIR`, `GATES_DIR`, `LIB_DIR`, `CLAUDE_DIR`, `WORK_HOOKS`, ...) - `tests/scripts/toolkit_paths.py` - shared test paths.
- `tests/scripts/gate_replay.py`, `gate_replay_corpus.json` - replay rows for gates.
- `rule_meter.py run|run-all|summary` - `~/agent-evals/bin/rule_meter.py` - runs and summarizes cells.
- `rule_source_for_arm(source_text, scenario, arm, source_path)` - `rule_meter.py:1594` - on/off arm source text.
- `toolkit_home(scenario)`, `rule_source_path(scenario)`, `read_rule_source(scenario)` - `rule_meter.py:1605,1614,1623` - scenario toolkit lookups.
- `build_prompt(scenario, level)` - `rule_meter.py:1646` - task plus level suffix.
- `cell_id`, `run_id` - `rule_meter.py:1650,1654` - cell and run identifiers.
- `build_changes.py new "<title>" --by <actor> [--date]` and bare `build_changes.py [--check]` - `~/agent-evals/bin/build_changes.py` - create and rebuild change files.
- `build_findings.py new`, `build_queue.py new|claim|set|prior|next`, `rule_trials.py search|build` - `~/agent-evals/bin/` - finding, queue and rule-trial commands named in `~/agent-evals/CLAUDE.md`.
- `dead_prose_gate.py`, `claudemd_linecount.py` - `claude/.claude/scripts/gates/` - warn-only prose and line-count hooks.
- `claude-doctor.sh` section 4e - `claude/.claude/scripts/tools/claude-doctor.sh:228` - runs `rule-anchors.sh check`.
