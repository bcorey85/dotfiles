# Plan review, round 1 (unsharded)

Reviewer: plan-reviewer, 2026-11-22. Verdict: NEEDS CHANGES (3 blocker, 8 gap).

DUCK     Phase 1: adds `agent_interrupted` to lib/loop_transcript.py and a new code/fork_children.py. Its CLI verb prints the fork's live child ids and kills the run's detached review loop. Its hook verb denies a TaskStop of a code-fork once, but stays unwired. Phase 1 also rewrites the cancel sentence in SKILL.md's frontmatter description (line 3).
DUCK     Phase 2: renames `unchanged_dirty_files` to `recorded_dirty_files` and holds every start-dirty path. It notes changed held files as a tool fault and, when another session is live, holds untracked files that no subagent coder of this session wrote. code_wait gets a function that prints the fault line, and handoff-block.md:28 is reworded.
DUCK     Phase 3: moves SKILL.md:100-157 (375 words) into skills/code/phase-end-block.md, cuts 14 duplicate words plus the :34 restatement, turns the dense paragraphs into lists, re-hashes anchor rows 79-84, runs rule-meter and writes the change file.
DUCK     Phase 4: runs /close-branch as the close pass, plus a new branch_bounds.py checker.

BLOCKER  Phases 1-2 vs Phase 3: edits in Phases 1 and 2 break `test_rule_anchors.py`, which runs in the full suite. Phase 3 re-hashes only the SKILL.md rows, so the handoff-block row is never repaired.
         Evidence: `rule-anchors.sh check` exits 0 today, and test_rule_anchors.py:22-23 runs `check` inside `bash tests/run.sh` (parallel_tests runs every test file). Phase 1 edits SKILL.md line 3, which sits in the `(preamble)` block (row 5bcfdcf0). Phase 2 edits handoff-block.md:28, which sits inside `## Who writes \`files\` for \`/code\`` (lines 26-29; docs/rule-anchors.md:208, row 78d7b13d). Phase 3 step 3 names only "`docs/rule-anchors.md` (rows 79-84)" and runs `rule-anchors.sh list` "on both files" (SKILL.md and phase-end-block.md).
         Reading: The /code review loop's execution gate is the full suite (SKILL.md:57). Phase 1's and Phase 2's reviews therefore see a red suite caused by their own prose edit. Either the fix coder re-hashes out of plan order, or the phase stops. After Phase 3, row 208 is still stale and Phase 4's `bash tests/run.sh` fails.

BLOCKER  Phase 2 step 4 (`code_wait.print_held_fault`): as written, the new function exits the process, looks in the wrong folder, and creates an import cycle.
         Evidence: `read_scope` calls `sys.exit` on an OSError (code_review_start.py:196-202), so a missing review-scope.json stops the run rather than printing nothing. `detach` writes the scope to `phase_dir(repo) / SCOPE_FILE` (code_review_start.py:298), but the plan's signature takes `loop_dir`. `print_ended_loop(run)` (code_wait.py:530) is shared with the launched-folder run (code_wait.py:364, the review_launch.py `--loop` route), and that run has no scope file. Also, `phase_review` (code_wait.py:300) prints nothing itself: it only builds a ReviewRun. Finally, code_review_start.py:43/56 already imports `code_wait` and `from code_wait import ...`, so code_wait importing code_review_start is circular.
         Reading: A coder who wires `print_held_fault` into `print_ended_loop` as the plan says makes every `/review --loop` wait end in `sys.exit`, or in a stale fault line left by an earlier /code phase. phase_start.py never moves review-scope.json aside. A top-level `import code_review_start` in code_wait fails with ImportError whenever code_wait is imported first.

BLOCKER  Phase 2 / AC12: the review prompt the loop actually reads never carries the Tool fault wording, yet the test passes.
         Evidence: `held_note` prints to stderr and appends to `notes` (code_review_start.py:141-145). `notes` reach stdout only under `--dry-run` (code_review_start.py:390-393). `review_prompt` (:236-262) writes only the held-by rows, and the plan's claim string `"dirty at the run start; live session in {cwd}" + ", changed since"` does not name the coder. test_phase_start.py's `review_prompt` helper runs `--dry-run` (:188-191).
         Reading: AC12 asks for the review prompt to name both the coder and the other session as possible writers. The flipped :211 test asserts on dry-run stdout, so it passes while the live detached prompt lacks the line. No Phase 2 change touches `review_prompt`.

GAP      Approach / Constraints line 49: the claim that `status_codes` lists an untracked folder as one `dir/` entry is false.
         Evidence: lib/worktree_snapshot.py:27-28 runs `git status --porcelain -z --find-renames --untracked-files=all`. `rg uall` finds nothing only because the flag is spelled out in full.
         Reading: The "directories expanded to files" code in `foreign_untracked` (step 3, decision 6) is dead weight. AC14's folder case already holds file by file through `status_codes`.

GAP      Phase 1 Success Criteria, the Replay bullet: it cannot fail.
         Evidence: "after the interrupt record is appended to the coder transcript the gate passes and the coder transcript has no record after the interrupt line."
         Reading: The test appends the interrupt line itself, so "no record after it" holds by construction. AC2 ("writes nothing after the stop") is mapped to this test and test_loop_transcript.py, and neither exercises a write after the stop. The coverage table overstates AC2.

GAP      Phase 3 Count check: it measures only SKILL.md, which narrows AC15.
         Evidence: The plan says "today SKILL.md alone, 3033 words" and checks with `skill_word_band.py ... SKILL.md 2730`. But SKILL.md tells the fork to read other files before the phase end: line 16 modifiers.md (114 words, "read it when present"), line 40 plan-reading.md (205), line 85 handoff-block.md (476, which Phase 2 also grows).
         Reading: AC15 counts "SKILL.md plus the files it reads before phase end". On that set the threshold is about 3714 × 0.9, not 2730. The check can pass while the AC fails, and the change file would record the wrong "before" number.

GAP      Phase 2 / AC11: the plan never says how a held file the current phase targets is "named to the reader".
         Evidence: "(a path the current phase targets stays held and named)" gives no text and no output location. expected_red.py offers `earlier_phase_paths` and `later_phase_paths` but no current-phase reader (`section_paths` is the nearest).
         Reading: One coder adds a note line and another adds a claim suffix. Neither the test files nor the success criteria name a case for AC11.

GAP      Phase 2 untracked attribution: files the review loop's fix coder writes are held as foreign.
         Evidence: The loop's coder runs as `claude -p` (review/review_loop_calls.py:3, :68), so its transcript lies outside `session_subagents_dir(session_id)`. `/code resume` keeps start.json under `--resume`, and a resume in a new session has a different session id.
         Reading: A resumed phase whose earlier loop pass created a new test file holds that file whenever another session is live. That breaks AC13 ("an untracked file the run's own coders wrote is still reviewed"). The plan names neither case.

GAP      Phases 3 and 4: two new checker scripts are dangling.
         Evidence: `tests/scripts/skill_word_band.py` and `tests/scripts/branch_bounds.py` appear only in Automated Verification, marked "(new checker ...)". Neither is in any `**File**` list, and Phase 4 has no Changes Required at all. Neither file exists (`ls` confirms).
         Reading: Nobody is told to write them before their checks run. Separately, branch_bounds' list leaves out `verify-prep`, which Constraints line 46 names as out of bounds.

GAP      Phase 2 hold rule: two readings, and the claim format is undefined.
         Evidence: Decision 2 says "every path in start.json `dirty` is held for the whole phase", yet the claim text still says "live session in {cwd}", and today's code returns [] when `other_live_session_in` is None (code_review_start.py:173-175). The claim is given as `"...; live session in {cwd}"` plus `", changed since"`, while step 6 expects `dirty at the run start, changed since; live session in {repo}`.
         Reading: One coder keeps the live-session gate, so the hold drops once the other session exits mid-phase. That contradicts "for the whole phase". Another drops the gate, which changes solo runs. The suffix is either inserted before the `;` or appended at the end.

GAP      Phase 2 step 5: the reworded handoff-block.md:28 drops a rule the code keeps.
         Evidence: The current text says "a file the plan gives to an earlier phase is never held". The plan's replacement sentence omits it, yet the Approach says "keep the earlier-phase removal".
         Reading: AC16 requires every kept rule to still reach the run. Neither text pin nor rule-meter catches the loss.

NIT      Phase 1 step 3: the plan doesn't say whether the new cancel route replaces or extends the current sentence ("SendMessage it `stop` and wait for its stop; TaskStop the fork only after ..."). The current sentence is also pinned with code-fork.md:14 in test_guidance_rules.py:184-191.

NIT      Phase 1 step 1: "the two interrupt text shapes" are never named. Real subagent transcripts show `[Request interrupted by user]` (30 cases) and `[Request interrupted by user for tool use]` (14). In all 43 stopped transcripts the record is the last one. The plan also gives no `tail_bytes` for `transcript_tail_lines(transcript_path, tail_bytes)` (script_utils.py:904).

NIT      External Contracts: the plan calls it "`code_review_start.holder_row`", but `holder_row` is defined in review/review_loop_prompt_file.py:64, which is out of bounds, and only imported by code_review_start. The claim string is built in code_review_start (:177), so nothing breaks.

NIT      Phase 1 step 5: no ticket item asks for the 30-run timing medians. Also, rule_meter_scenarios.json has 14 entries with no `rule_source` (it lives outside the tree), so the "each entry has `rule_source`" claim is loose.

Claims settled true: all named functions exist at the cited places (`agent_finished` :385, `finished_by_meta` :379, `live_children` :63, `CODE_FORK`, `DENIED_KIND`, `pid_is_alive`, `command_line`/`ProcessQueryError`, `terminate_group`, `file_hash`, `other_live_session_in`, `pre_tool_use_deny`, `bash_commands`, `tool_use_calls`, `CODERS`, `record`/`was_recorded`, `agent_transcript`, `AGENT_ID`, `running_review_pid`, `START_FILE`, `SCOPE_FILE`, `ReviewScope`, `read_scope`). `session_subagents_dir`, `written_paths` and `agent_interrupted` do not exist yet, as the plan expects. script_utils.py is 1378 lines and loop_transcript.py 525. `ReviewScope(` appears only at test_code_review_start.py:210/225/612. `unchanged_dirty_files` appears only in code_review_start.py and that test file. SKILL.md is 3033 words and its Phase-Complete section 375. Anchor rows 79-84 are the SKILL.md rows. Real meta files carry `parentAgentId`, and real TaskStop input is `{"task_id": ...}`. rule_meter.py `run-all --rule` exists. I can doubt but not settle whether the harness honors a PreToolUse deny on TaskStop: there is no captured event.

VERDICT: NEEDS CHANGES (3 blocker, 8 gap)

## Orchestrator check of the facts, 2026-11-22

- `status_codes` runs `--untracked-files=all` (worktree_snapshot.py:27-28): confirmed, so the folder-expansion code is dead.
- Start-load word counts, measured: SKILL.md 3033, `_shared/modifiers.md` 114, `_shared/plan-reading.md` 205, `_shared/handoff-block.md` 476; total 3828, so the AC15 limit on that set is 3445.
- `claude_call` in review_loop_calls.py runs the loop's coder as `claude -p`: confirmed.
- The live-session gate at code_review_start.py:173-175 returns `[]` with no holder: confirmed.
