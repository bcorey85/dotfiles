# Stage, full check and skill fixes: staged deletions, doc-only paths, lane git state, fix args, ADR step

Fix five queued toolkit defects. Each script phase starts with a test that fails on the current tree. Scripts live in
`claude/.claude/scripts/` and `claude/.claude/skills/*/scripts/`; tests in `tests/scripts/`, paths from
`tests/scripts/toolkit_paths.py`.

## Scope

- In: `skills/stage/scripts/stage.mjs`, `code/check_discovery.py`, `tools/lane_status.py`,
  `scripts/.local/bin/lane-status` (usage only), `skills/adr/scripts/adr_flow.py`, `skills/fix/SKILL.md`,
  `skills/verify-branch/SKILL.md`, `skills/close-branch/SKILL.md`, the opencode ports of those skills if any, and the
  tests of each.
- Out: every other `review/` script and every `gates/` file (other lanes own them); `settings.json` (the lane-status
  allow rule goes to the orchestrator as a proposed line).

## What We're NOT Doing

- The brief switch that turns off a named gate in the review loop (code-review-loop item, second Done-when line). Cut
  by ruling; see 03-decisions.md.

## Phase Status

- [x] Phase 1: stage --run counts an already-staged deletion as staged (risk: low)
- [ ] Phase 2: doc paths do not widen the full check to every part (risk: low)
- [ ] Phase 3: lane-status --git prints each lane's branch state (risk: low)
- [ ] Phase 4: a fork skill takes its findings from its args (risk: low)
- [ ] Phase 5: /adr is a run step at branch end, and a PR with a task dir left reads as not finished (risk: low)

## Phase 1: stage --run counts an already-staged deletion as staged

Bug: the change set comes from `git diff HEAD --name-status`, so a deletion already staged with `git rm` shows as `D`.
When that path is SAFE, `git add -- <path>` fails with `pathspec did not match any files`, the run aborts with exit 2
and nothing else is staged.

1. In the SAFE staging step, leave out of the `git add` call each `D` path that is no longer in the index (`git
   ls-files --cached` on the D paths). It still counts as staged in the report and metrics.
2. When nothing is left to add, skip the `git add` call.
3. Test first, in `tests/scripts/test_stage_run.py`: a repo with a `git rm`'d barrel file (SAFE) beside an unstaged
   edit; `--run` exits 0, the deletion stays staged, and the edit is staged or queued. It fails on the current tree.

#### Automated Verification

- [ ] **Stage run tests**: `python3 tests/parallel_tests.py test_stage_run.py`

Size: about 15 lines of code and 25 of test.

## Phase 2: doc paths do not widen the full check to every part

Bug: `check_discovery.parts_to_run` returns every part when a changed path is neither a package, Python nor shared
path. A plan doc (`docs/plans/x/plan.md`) beside frontend files therefore starts the backend suite.

1. In `parts_to_run`, skip each path for which `source_paths.is_doc_path(path)` is true before the kind checks.
2. A diff of doc paths only keeps today's result (every part), through the existing `selected or parts` fallback.
3. Test first, in `tests/scripts/test_check_discovery.py`: a package-plus-Python repo with changed paths of one
   frontend file and one `docs/plans/x/plan.md` selects only the package part (fails on the current tree); doc paths
   only select every part.

#### Automated Verification

- [ ] **Discovery and full check tests**: `python3 tests/parallel_tests.py test_check_discovery.py test_full_check.py`

Size: about 3 lines of code and 25 of test.

## Phase 3: lane-status --git prints each lane's branch state

1. `lane_status.py main` takes `--git`. For each open lane from `read_lanes()` it prints one line: lane name, branch,
   `merged` or `N ahead / M behind` against `origin/<default branch>` of the lane's main checkout, the dirty file
   count of the lane worktree (`git status --porcelain` lines), and `reports_to` (`-` when empty).
2. A lane whose worktree is gone, or whose git call fails, prints that line with the reason in place of the counts.
3. The default branch is `origin/HEAD` when set, else `origin/master`, else `origin/main`.
4. Update the module docstring and the usage line, and the wrapper's comment if it has a usage line. Search every
   caller of `lane_status.py` and `lane-status` first; the existing modes keep their output and exit codes.
5. Send the orchestrator the proposed `settings.json` allow line for `lane-status`.
6. Test first, in `tests/scripts/test_lane_status.py` on fixture lanes with a bare origin: a merged lane, a lane 2
   ahead and 1 behind with one dirty file, and a lane with no worktree. Each pins the branch, merge state, dirty count
   and `reports_to`.

#### Automated Verification

- [ ] **Lane status tests**: `python3 tests/parallel_tests.py test_lane_status.py`

Size: about 70 lines of code and 90 of test.

## Phase 4: a fork skill takes its findings from its args

1. `skills/fix/SKILL.md` description: drop "or the conversation" as a source; tell the caller to pass the findings
   (or the `/review` handoff block) in the args.
2. Step 1: drop the conversation as a source. A run with no findings in args, no handoff and no `resume` stops at
   once with one line asking for the findings, and starts no loop. Keep the `/cc` pointer for inline comments.
3. `--source conversation` on the packet command stays for findings the caller pasted from the conversation; check
   the packet script's accepted values before you change the flag text.
4. New test in `tests/scripts/test_guidance_rules.py` (or a sibling test file): every `SKILL.md` with `context: fork`
   in its frontmatter has a description that does not name the conversation as an input source. It fails on the
   current fix skill.
5. Run the agent-evals rule workflow for the reworded rule (rule_trials search, rule_meter on and off arms,
   rule-anchors update) and patch the opencode port if one exists.

#### Automated Verification

- [ ] **Guidance rule tests**: `python3 tests/parallel_tests.py test_guidance_rules.py`

## Phase 5: /adr is a run step at branch end, and a PR with a task dir left reads as not finished

1. `adr_flow.py status [<path-or-ticket>]`: resolve the task dir as `prep` does and detect the PR with
   `detect_pr`. When a PR exists and the task dir still exists, print `adr: not finished: PR <url> exists and task
   dir <dir> remains; run /adr` and exit 1. Otherwise print `adr: done` (no task dir) or `adr: no PR yet` and exit 0.
2. `skills/verify-branch/SKILL.md` Clean route: replace the "After the PR exists, `/adr`" pointer with a numbered
   step: once the PR exists, run `/adr`, then `adr_flow.py status`; the branch is not finished until it exits 0.
3. `skills/close-branch/SKILL.md`: the same numbered step after the PR, and its Next line names the status check.
4. Run the agent-evals rule workflow for the changed skill text, and patch the opencode ports if any.
5. Test first, in `tests/scripts/test_adr_flow.py` with the fake `ADR_GH`: PR plus task dir exits 1 with the line;
   PR with no task dir exits 0 `adr: done`; no PR exits 0 `adr: no PR yet`. The first fails on the current tree.

#### Automated Verification

- [ ] **ADR flow tests**: `python3 tests/parallel_tests.py test_adr_flow.py`

Size: about 35 lines of code and 50 of test.

## Final

- `bash tests/run.sh` passes; `bash tests/lint.sh` passes on every changed `.py` file.
