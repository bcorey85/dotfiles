# Plan review, round 1, shard B (plan-reviewer hand-back, verbatim)

DUCK     Phase 5: rewrites Steps 0, 1 and 4 of both mutation-tester prompts into `mutation_lock.py` calls, rehashes three anchor rows, adds three prompt-reading tests and adds `test_mutation_lock.py` to `PROMPT_READING_TESTS`.
DUCK     Phase 6: replaces the `## Three worked cards` heading (guide/SKILL.md:114) with `## A worked card` and deletes the A/B card (:187-197) and the rating line (:198).
DUCK     Phase 7: copies the trimmed skill into a rule-meter toolkit folder, adds four GD scenario rows, adds a new `rule_meter_guide.py` detector module (merged into `rule_meter_verifier.DETECTORS`) and adds its tests in ~/agent-evals.
DUCK     Phase 8: runs 24 opus meter cells, plus up to 24 more, then cuts the guide rules the meter clears and renumbers the rest.
DUCK     Phase 9: writes three change notes with build_changes.py, links four anchor rows to them and runs the full suite under systemd-run.
DUCK     Phase 10: /close-branch review, fix pass and recap.

BLOCKER  Phase 5 §4 vs §1: the prompt test requires "exactly two bullets" in Step 0, but §1 tells the coder to write three
         Evidence: §1 says "bullets: first, … 'The dispatch does not state a test command …'; then 'The target is not the file named in the dispatch → stop.'; then 'Run `python3 ~/.claude/scripts/tools/mutation_lock.py check <target>` …'". §4 says "`test_both_mutation_tester_prompts_name_no_lock_path_hash_tool_or_count`: … and the Step 0 section holds exactly two bullets."
         Reading: If the coder writes the prose as §1 says, Step 0 has three bullets and the Phase 5 test fails. To make it pass, the coder must turn the `check` line into a paragraph or a fenced block, and nothing in the plan says which. AC24's "keeps as prose only the two preconditions" fits either reading. Two coders will write different prose, or one of them hits a red test.

BLOCKER  Phase 5 §4 vs §1: the Step 4 test requires the literal `RESTORE HASH MISMATCH`, but the specified Step 4 prose never contains it
         Evidence: §4 says the test checks that each file's Step 4 "names `RESTORE HASH MISMATCH` as a loud stop". The Step 4 bullets in §1 say "Exit 3 → **STOP and say so loudly**, with the target path and the backup path it printed …". The literal appears only as the script's output in the Phase 4 contract (spec.md:203).
         Reading: Prose written word for word from §1 fails the test. The coder has to either add the literal somewhere the plan never places it or weaken the test, and the plan picks neither. The same mismatch hits both prompt files.

GAP      Phase 5 prose and anchor reason vs the Phase 4 contract and AC22: who owns the precondition list is described three ways
         Evidence: spec.md:112 says "`check --help` owns the precondition list". The Phase 5 anchor reason says "owned by `mutation_lock.py check --help`". The Phase 5 Step 0 bullet says "Run `… mutation_lock.py check <target>` (its `--help` lists what it checks)". spec.md:197 says "`description = __doc__.splitlines()[0]`; the epilog lists `PRECONDITIONS`", on the top-level parser. AC22 says "`mutation_lock.py --help` lists every precondition". Phase 4 test case (11) checks bare `--help`.
         Reading: argparse prints a top-level epilog only for `mutation_lock.py --help`, not for `check --help`. If the epilog sits only on the top-level parser, the prompt and the anchor row send the agent to a `check --help` that does not list the preconditions. Exercised: `build_changes.py --help` vs `build_changes.py new --help` above show the same split, each parser printing only its own text.

GAP      Phase 9 §1 vs AC28: the Step 4 gate sentence is assigned to two different change notes
         Evidence: AC28 says "The guide change note records … lists rule 8, the Step 4 gate sentence of the mutation-tester and any ungradeable rule under `unmeasured`". Phase 9 says "The mutation-tester note lists the D13 sentence under `unmeasured`", and Decisions D13 says "listed `unmeasured` in the mutation-tester change file".
         Reading: If the coder follows Phase 9, the Close pass finds AC28 unmet as written. If the coder follows AC28, Phase 9 and D13 are unmet. One of the two texts has to change.

GAP      Phase 7: the detector location contradicts a lane-brief ruling, and no sign-off is recorded
         Evidence: The ticket (lane brief, "Rulings already made") says "New scenarios go in `bin/rule_meter_scenarios.json`; new detectors go in `bin/rule_meter_checks/` with tests; `bin/rule_meter.py` stays untouched." Phase 7 / D10 puts them in a new `~/agent-evals/bin/rule_meter_guide.py`. `## Plan Deviations` records only the two item-1 rulings.
         Reading: The plan's reason holds. `rule_meter_checks/` holds subprocess-run tree checks (`ls` shows .mts/.py hidden checks), and `grade()` reaches result-text detectors only through module dicts (rule_meter.py:1477-1480, `rule_meter_fixture.DETECTORS` and `rule_meter_verifier.DETECTORS`). Even so, the plan overrides an orchestrator ruling on its own. The plan needs a dated deviation entry ruled by agent-evals-c3; otherwise the Close pass's reconciler will flag it.

GAP      Phase 8: a first-pass NO_TEST cell has no route, and the automated criterion fails on a result the plan allows
         Evidence: The second pass is triggered by "a rule whose off arm complied at least as often as its on arm at every level". The criterion says "`summary` shows a graded on and off cell at every level for GD03, GD04, GD05 and GD07". D17 / §2 say "a rule with … fewer than two graded runs at any level stays, listed `unmeasured`".
         Reading: If a first-pass cell grades NO_TEST, "off ≥ on" is undefined for that level. One coder runs the second pass to try to fill the cell; another treats the rule as unmeasured and stops. A NO_TEST cell is an allowed outcome (it leads to `unmeasured`), yet it makes the Agent-run criterion fail.

GAP      Phase 7 §2, GD03 detector: the COMPLIED and VIOLATED definitions leave cases between them
         Evidence: The table says "COMPLIED: `defaults.response` present and no card carries `response`; VIOLATED: two or more cards carry the same `response`".
         Reading: Neither definition covers these batches:
         - `defaults.response` plus one card that overrides it.
         - No `defaults` and cards whose responses all differ.
         - Exactly one card carrying `response`.
         One coder grades all of these VIOLATED ("not COMPLIED"); another grades them NO_TEST. The choice changes the on/off counts that decide the cut. (GD04, GD05 and GD07 are written "VIOLATED otherwise" and have no such gap.)

GAP      D10 / Phase 7: no phase schedules the agent-evals commit that D10 promises
         Evidence: D10 says "the lane commits the agent-evals files itself". The Phase 7 manual check expects `git -C ~/agent-evals status bin/` to show the four files, still uncommitted. No phase (7, 8, 9 or 10) has a commit step for ~/agent-evals. Its branch is `bench-base` (`git -C ~/agent-evals branch --show-current`).
         Reading: The scenarios and detectors the Phase 8 runs depend on stay uncommitted in another repo when the lane finishes. The coder has to guess when to commit them, and on which branch.

NIT      Phase 5 §2: "the same Step 0, 1 and 4 bodies" does not say whether the opencode headings change. The opencode Step 0 heading reads "(all four, before touching anything)" (opencode mutation-tester.md:27), and Step 4 is "Restore. Non-negotiable, and it runs on every path" (:102). The ban test forces the Step 0 heading to change; for Step 4, say whether the heading stays.

NIT      Phase 9 §1: `--by claude-code/claude-fable-5-1` is described as "this session's model", but the coder who runs the step may be a different model. Name the rule ("the model running the step"), not a fixed string.

Claims checked and confirmed:
- File sizes: mutation-tester.md is 152 lines, the opencode port 161 and guide/SKILL.md 236 (`wc -l`).
- Guide line numbers: :39, :114, :116, :187, :198 and :200 are all exact (`rg -n`). settings.json:195 is `"guide": "user-invocable-only"`.
- The Phase 6 ban and presence criteria fail today, so they are real criteria.
- Anchor rows: 6ca266a8, 84cdf15f and d11ed9bc carry the stated keys (`rule-anchors.sh list`). The guide skill has no anchor row.
- `PROMPT_READING_TESTS` holds `test_log_review_finding.py` at :31. The new test's `CLAUDE_DIR / "agents"` matches `PROMPT_READER_SIGNAL`.
- `rule_meter_verifier.py:76` is as quoted. Exercised: `grade()` dispatches result-text detectors at rule_meter.py:1479-1480, and a `rule_source` scenario with no agent appends the arm's copy of the skill to the project CLAUDE.md (rule_meter.py:1697-1708).
- The `"rule": "X"` row form in results.jsonl matches the Phase 8 `rg -c` pattern.
- The `build_changes.py new --by --root` and `--check --root` flags exist (`--help`).
- The three Phase 9 presence greps match nothing today.
- Not settleable from the tree: whether `$PPID` stays the same across tool calls under opencode.

Paths: /tmp/plan-review-shards-m_xqi7l5/review-shard-b.md, /home/brandon/dotfiles-toolkit-scripts-nov22/docs/plans/toolkit-scripts-1122/spec.md, /home/brandon/dotfiles-toolkit-scripts-nov22/docs/plans/toolkit-scripts-1122/acceptance-criteria.md, /home/brandon/dotfiles-toolkit-scripts-nov22/claude/.claude/agents/mutation-tester.md, /home/brandon/dotfiles-toolkit-scripts-nov22/opencode/.config/opencode/agents/mutation-tester.md, /home/brandon/agent-evals/bin/rule_meter.py

VERDICT: NEEDS CHANGES (2 blocker, 6 gap)
