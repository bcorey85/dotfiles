# Plan review, round 1, shard A (plan-reviewer hand-back, verbatim)

DUCK     Phase 0: Freezes four contracts: the lock data model, the `calibration_lock` API, the `mutation_lock.py` CLI (check, lock, restore) and the `log --help` template. Nothing is verified here.
DUCK     Phase 1: Moves the log grammar (lines 117-119, 599-745 and 806-820 of `refactor_flow.py`) into `refactor_log_input.py` with `LOG_TEMPLATE` and `FIELD_NOTES`. `log --help` prints the template between two markers, and `refactor_flow.py` ends near 930 lines.
DUCK     Phase 2: Takes the key text and the fenced JSON out of the refactor skill's step 5, repoints close-branch:68 to `log --help`, rehashes anchor row 458c884f and adds two text tests.
DUCK     Phase 3: Moves the guard's lock helpers into `lib/calibration_lock.py`. The guard calls them and gives the same output; the existing guard tests are the proof, and a new module test is added.
DUCK     Phase 4: Builds `tools/mutation_lock.py` on top of calibration_lock, file_backup and file_lock, with 13 subprocess test cases.

GAP      Phase 4 tests / acceptance-criteria.md: several of the plan's own criteria have no test among the 13 cases
         Evidence: cases (1)-(13) cover restore only for "another `owner_pid` and another `writer`" (9, 13), a tampered backup (8) and the old layout (10). No case tests restore with no lock (`STOP_NO_LOCK`), a missing backup (`STOP_BACKUP_MISSING`) or a lock found only at the legacy path (`STOP_LEGACY_LOCK`), all named in AC18. No case tests a lock that cannot be removed (`STOP_LOCK_NOT_REMOVED`, AC20) or a target too large to back up (`STOP_BACKUP_FAILED`, AC15). Case 6 tests `lock` against "a lock" of one kind, but AC13 needs `lock` against a live, a stale and a legacy lock.
         Reading: the plan says "The Close pass reconciles every id against the real suite", and AC15, AC18 and AC20 will come up uncovered there. All of them can be tested at the boundary without mocks:
           - too large: a sparse file over 50 MiB made with `os.truncate`, since `save_files` checks `st_size` (file_backup.py:35);
           - lock not removable: a read-only state folder after `lock`;
           - legacy only, and missing backup: arrange the files on disk.
         Enumerated: AC15, AC18 (3 branches), AC20, AC13 (lock verb) -> 4 criteria, 6 branches with no case.

GAP      Phase 0 §3 / D16: the dirty-target refusal breaks a case the agent was written for
         Evidence: mutation-tester.md:98-99 says "Never `git checkout` — it would also destroy the real uncommitted work in that file". Phase 5 (spec.md:402) keeps that sentence word for word. test-audit/SKILL.md:44 says "The script measures the branch and the working tree, so the audit's uncommitted fixes count". D16: `check` and `lock` refuse whenever `git status --porcelain -- <relpath>` prints anything.
         Reading: a target with uncommitted coder work can no longer be mutation-tested at all. A new untracked source file prints `?? src/new.py`, so it is refused too. The restore copies from the backup, so it never needed a clean target. The kept Step 4 sentence then describes a state that `check` makes impossible, so the plan contradicts itself. D16 is a session ruling (agent-evals-c3) and AC12/AC15 encode it. The orchestrator should confirm that this narrowing is meant, including the untracked case. If it is, Phase 5's kept sentence needs rewording.

GAP      Phase 1 §4: the identity test fails with the loading method the plan names
         Evidence: "load the module with `importlib.util.spec_from_file_location` from `SCRIPT.parent / "refactor_log_input.py"`" and "`load_script_module().RefactorFlowError is refactor_log_input.RefactorFlowError`". `load_script_module` (test_refactor_flow.py:40-43) runs refactor_flow through `SourceFileLoader`, and refactor_flow then runs its own `import refactor_log_input` through `sys.path`.
         Reading: a module loaded with `spec_from_file_location` and not registered in `sys.modules["refactor_log_input"]` is a second module object with its own class, so the `is` check is False. One coder registers it in `sys.modules` first. Another compares against `load_script_module().refactor_log_input.RefactorFlowError`. A third follows the text as written and gets a red test. The plan should name one.

GAP      Phase 2 §1 / D3 vs AC6: "three judgment bullets word for word" cannot be kept word for word once the key text is deleted
         Evidence: Phase 2 keeps "the three judgment bullets word for word from `:65-67`" (findings, guards, lane) and also says "Delete the key-shape text". Bullet :66 holds `{class, disposition, actioned, file, line, desc}` and "(`line` 0 when none; `desc` one line)". Bullet :65 is `finder`/`lane`/`result` key text. AC6 names a different set of three: "one entry per smell, never escape sweep matches or legacy targets, the `miss_reason` source" and "no key list".
         Reading:
           - Reading A keeps bullets :65-67 verbatim, so the key list survives and AC6 fails.
           - Reading B strips the key parts, so nothing is "word for word" and the coder decides what counts as judgment.
         The only automated check is "no fenced json block", so neither reading is caught. Quote the exact text of the kept bullets.

GAP      Phase 2: the consumers of the step-5 shape are named one by one, and one is missed
         Evidence: refactor/SKILL.md:115 (audit mode 6d) says "Log the finder with `log --mode audit` (JSON as in step 5, with `target`…)". Step 5 will no longer hold any JSON. Phase 2 repoints only close-branch:68.
         Enumerated: `rg -n 'JSON as in step 5|input shape of' claude/.claude opencode -g '*.md'` -> 2 sites (refactor/SKILL.md:115, close-branch/SKILL.md:68); the plan covers 1.

GAP      Phase 0 §1/§3: `lock` takes its flock before anything has created the state folder, and `LOCK_WAIT_SECONDS` has no value
         Evidence: "inside `hold_exclusive(<state folder>/lock.write, LOCK_WAIT_SECONDS)`", and `lock` first does "take `hold_exclusive` … ; re-run the six checks". `hold_exclusive` does `open(lock_path, "a")` (file_lock.py:20), which raises `FileNotFoundError` when the folder is missing; that is not `LockTimeoutError`. `LOCK_WAIT_SECONDS` appears once in spec.md (line 164), with no value and not in the API table.
         Reading: on a fresh machine, and in every Phase 4 test with a fresh `XDG_STATE_HOME`, `lock` crashes with a traceback and no `STOP:` line, unless the coder guesses a `mkdir` and picks a timeout.
         Evidence-class: exercised claude/.claude/scripts/lib/file_lock.py:17-20

NIT      Phase 0 §3 check (5): "the backups folder can be created and written" conflicts with "`check` writes nothing" and with case (1) "writes neither lock nor backup". One coder creates the folder and probes it with a temp file; another runs `os.access` on the nearest existing parent.

NIT      Phase 0 §1 "byte-compatible with today's jq output": `json.dumps` escapes non-ASCII by default (`ensure_ascii=True`), while jq writes UTF-8. The two files differ for a non-ASCII `--class`. The guard reads both the same way, so only the "byte-compatible" claim is wrong.

NIT      Phase 4 case (5): "`gates/calibration_guard.py --live` exits 0 against that lock with a live `--owner-pid`". The guard has no `--owner-pid` flag (calibration_guard.py:100-102). This should read "a lock written with a live `--owner-pid`".

NIT      Phase 0 §3 restore: the `STOP_NOT_OURS` check runs before the old-layout check. An old prose lock from another session (the normal case) therefore hits `STOP_NOT_OURS`, and its `cp "<backup>" "<target>"` line may name a relative `file`. Case 10 only reaches `STOP_OLD_LAYOUT` if it sets the matching owner pid. The plan does not say whether `<target>` in the recovery line is joined to `worktree`.

Claims checked and found true:
- refactor_flow.py is 1097 lines. Every refactor_flow line cited is right: 53, 70, 90, 117-119, 479, 599-745, 806-820, 902, 1008-1010, 1050-1055, 1074-1077, and the docstring at 22-34.
- ruff.toml:28 is the refactor_flow E402 entry, and the `scripts/*/*.py` E402 glob is at :31.
- refactor/SKILL.md is 133 lines with exactly 1 fenced json block, at :70-101.
- close-branch:68 holds the cited text.
- calibration_guard.py is 167 lines, and every cited line is right.
- The file_backup and file_lock signatures match the plan; `write_text_atomically` (script_utils.py:1357) and `pid_is_alive` exist.
- mutation-tester is 152 lines and the opencode port 161, with the state path repeated 6 times.
- The anchor rows sit at :127, :131, :132 and :135 with the hashes the plan gives (checked with `rule-anchors.sh list`).
- guide/SKILL.md is 236 lines.
- toolkit_paths names exist.
- `HEAVY_FIRST` (:42) and `PROMPT_READING_TESTS` are as the plan says.
- test_calibration_guard.py, test_review_fixes.py and test_toolkit_self_location.py exist.
- `plan_format.is_ruling_by` exists.
- No file outside refactor_flow.py imports its internals.
- test_hook_module_imports allows a new lib module the guard imports.
- `rule_meter_verifier.py:76` is as cited.
- `git -C ~/agent-evals status bin/` is clean.
- The `python3 -m unittest -k <name> tests/scripts/test_refactor_flow.py` form runs (checked with an existing test).

Files: /tmp/plan-review-shards-m_xqi7l5/review-shard-a.md, /home/brandon/dotfiles-toolkit-scripts-nov22/docs/plans/toolkit-scripts-1122/spec.md, /home/brandon/dotfiles-toolkit-scripts-nov22/docs/plans/toolkit-scripts-1122/acceptance-criteria.md, /home/brandon/dotfiles-toolkit-scripts-nov22/claude/.claude/skills/refactor/SKILL.md, /home/brandon/dotfiles-toolkit-scripts-nov22/claude/.claude/agents/mutation-tester.md, /home/brandon/dotfiles-toolkit-scripts-nov22/claude/.claude/scripts/lib/file_lock.py, /home/brandon/dotfiles-toolkit-scripts-nov22/tests/scripts/test_refactor_flow.py

VERDICT: NEEDS CHANGES (0 blocker, 6 gap)
