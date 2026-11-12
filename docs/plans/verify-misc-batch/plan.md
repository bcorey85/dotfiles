# Verify and misc batch: plan folders verify, the commit review counts, branch-prep sees the work tree, safer pulls, true dry-run labels

Fix six queued toolkit defects. Each phase starts with a test that fails on the current tree. Scripts live in
`claude/.claude/scripts/` (and `claude/.claude/skills/refactor/scripts/`); tests in `tests/scripts/`, paths from
`tests/scripts/toolkit_paths.py`.

## Scope

- In: `review/verify-prep`, `review/verify-log`, `review/verify_common.py`, `lib/plan_format.py` (criteria owner of a
  plan folder with no ticket), `lib/reviewed_tree.py` (one read of the shared record),
  `skills/refactor/scripts/refactor_flow.py`, `tools/pull_keep_index.py`, `lib/criteria_verdict.py`,
  `tools/criteria_dry_run.py`, a new repo-root `.prettierignore`, `skills/verify-branch/SKILL.md` only if a printed
  step changes, and the tests of each.
- Out: `review/review_fix*.py`, `review/review_loop*.py`, `review/review_launch.py` (another lane edits them);
  `agents/code-fork.md`; `bash-safety-gate.sh`.

## Phase Status

- [x] Phase 1: verify-prep runs on a plan.md folder with no ticket (risk: medium)
- [x] Phase 2: a converged commit review of the current tree counts as the branch review once one was logged (risk: medium)
- [x] Phase 3: refactor branch-prep covers uncommitted and untracked files (risk: low)
- [x] Phase 4: pull_keep_index skips the pull on a branch rewritten locally (risk: medium)
- [ ] Phase 5: the criteria dry run labels environment failures ENV and judges escaped rg patterns the same (risk: low)
- [ ] Phase 6: the formatter leaves the gate replay corpus layout alone (risk: low)

## Phase 1: verify-prep runs on a plan.md folder with no ticket

Bug: a /code plan written as `docs/plans/<name>/plan.md` plus `acceptance-criteria.md`, with no `00-ticket.md`, could
not run /verify-branch. The plan.md path exited 4; the folder exited 2 (no ticket); with a ticket file written it ran
`plan: none`, because only `spec.md` or `*-05-plan.md` count as the plan. Every criterion was then treated as the
user's, so the session sent the user rulings on criteria the plan author wrote.

1. `verify-prep`: a target that is an existing file named `plan.md` (or `spec.md`) resolves to its folder.
2. `resolve_inputs` dir mode: the plan is `spec.md`, else `plan.md`, else the single `*-05-plan.md`.
3. Dir mode with no ticket beside the plan: when the folder holds a plan and `acceptance-criteria.md`, run in a new
   `plan-only` mode: ticket None, criteria from the folder's `acceptance-criteria.md`, criteria owner `plan`. A folder
   with neither a ticket nor a criteria file still fails loudly (exit 2), naming both missing files.
4. Everything that reads `context["ticket"]` (verify-prep's printout and verifier payload, `read_criteria`,
   verify-log's checklist and label checks) handles a None ticket: no ticket lines, `ticket: none (plan-only)`.
5. Criteria owner for plan-only: `plan_format.owner_record(None, CRITERIA_OWNER_PLAN, None)`, whose rule lets the
   orchestrating session rule on a cut or reword and record it in Plan Deviations. `plan_format.plan_criteria_owner`
   gives `plan` (not `user`) for a plan with no ticket beside it only when its folder holds `acceptance-criteria.md`.
   Check every caller of `plan_criteria_owner` still reads the new value.

#### Automated Verification

- New tests in `tests/scripts/test_verify_prep*.py` (or the existing verify-branch test file): a fixture repo with
  `docs/plans/x/plan.md` and `acceptance-criteria.md` and no ticket resolves from the plan.md path and from the folder,
  prints `plan:` with the plan path, lists the criteria ids and `criteria owner: plan`; a folder with neither ticket
  nor criteria exits 2; verify-log logs rows for that context.
- `python3 tests/parallel_tests.py` on the changed test files passes.

## Phase 2: a converged commit review of the current tree counts as the branch review once one was logged

Bug: /verify-branch Step 1 logs a branch review on a tree; its coder fixes are uncommitted; the commit gate then needs
a converged /review, whose fix rounds change the tree; verify-prep then says the branch review has not run on this
tree and asks for another. The loop never closes.

1. `lib/reviewed_tree.py`: add `shared_record_covers(repo_dir)`: True when the work tree's `reviewed_fingerprint` is
   in the shared reviewed record any session wrote (the read `is_reviewed` already does, without a session).
2. `verify_common.review_state`: when the ledger shows a branch-exit review row for this branch on an earlier tree
   (`review_ran` returns not-ran with trees listed), or, when the ledger is unread, the saved context holds a
   `reviewLoggedTree`, and `shared_record_covers(top)` is True, the review counts as ran with the reason
   `branch review logged on an earlier tree; a converged /review covers this tree`. With no branch review logged
   earlier, a converged commit review alone does not count.
3. `review_state` takes the repo top as a new argument; update its caller in verify-prep.

#### Automated Verification

- New tests: ledger lists an earlier tree and the shared record holds the current reviewed fingerprint: ran True; no
  earlier tree listed: ran False; ledger unread with a saved `reviewLoggedTree` plus the shared record: ran True.
- `python3 tests/parallel_tests.py` on the changed test files passes.

## Phase 3: refactor branch-prep covers uncommitted and untracked files

Bug: `refactor_flow.py branch-prep` lists files and bounds the smell-reviewer by `git diff <base>...HEAD`, so
uncommitted edits and untracked new files are missing from the prompt.

1. With no `--head`, branch-prep spans the merge-base against the work tree: changed files come from
   `git diff <merge-base>` (labels as now), plus untracked files from `git ls-files --others --exclude-standard`,
   labelled `untracked`. The sweep also reads each untracked text file's lines as added lines.
2. The smell bound names that span: `git diff <merge-base>` (committed and uncommitted) plus the untracked files.
   With `--head`, behavior is unchanged.
3. The empty-diff stop fires only when committed, uncommitted and untracked are all empty.

#### Automated Verification

- New test in the refactor flow tests: a branch with one commit, one uncommitted edit and one untracked new file:
  all three appear in the printed changed-file list, the untracked one labelled `untracked`, and the bound names the
  merge-base span.
- `python3 tests/parallel_tests.py` on the changed test files passes.

## Phase 4: pull_keep_index skips the pull on a branch rewritten locally

Bug: after a local rewrite (rebase onto a squash-merged base), the script pulls the old remote branch and rebases the
rewritten commits onto it, replaying the squashed commit and stopping on conflicts, so the force push never runs.

1. Before setting anything aside, when `@{u}` resolves and is not an ancestor of HEAD, and the upstream's commit is in
   the local branch's reflog (so this branch held it before and the remote has nothing it never had), print
   `pull_keep_index: <branch> was rewritten locally (the remote tip <short> was on it before); nothing pulled. Push
   with --force-with-lease.` and exit 0.
2. When the upstream tip is not in the reflog (another machine pushed), the pull runs as now.

#### Automated Verification

- New tests in `tests/scripts/test_pull_keep_index.py`: a clone pushes, rewrites its last commit (amend), and runs the
  script: exit 0, the message, HEAD unchanged, no rebase state; a second clone pushes a new commit and the first runs
  the script: the pull still runs.
- `python3 tests/parallel_tests.py test_pull_keep_index.py` passes.

## Phase 5: the criteria dry run labels environment failures ENV and judges escaped rg patterns the same

Bug: a version-manager shim failing (mise's uv exiting 1 because the pinned version is missing) made every uv
criterion read RED. A no-match rg with backslash-escaped asterisks read GREEN at rc=1 while the same rg without escapes
read RED.

1. `criteria_verdict.item_verdict`: output that shows the tool itself could not start (a shell `command not found`,
   a mise, asdf or pyenv error that a version is not installed or not set) reads outcome `ENV`, keeping the exit-style
   code. One named pattern constant owns the forms; collect the forms from the real messages of those tools.
2. `is_search_ban`: judge the wording on the line with every backticked span removed, not with
   `line.replace(command, "")`, so an escaped pattern whose command text differs from the line's span reads the same.
3. `criteria_dry_run.py`: `ENV` adds a flag `environment failure: <last output line>` and needs an answer like BROKEN.
   Check every reader of `outcome` (grep `.outcome`) accepts `ENV`.

#### Automated Verification

- New tests in `tests/scripts/test_criteria_verdict.py`: a mise not-installed message at rc 1 reads ENV; the escaped
  and unescaped rg forms of the same no-match ban read the same outcome at rc 1.
- `python3 tests/parallel_tests.py test_criteria_verdict.py test_check_output.py` passes.

## Phase 6: the formatter leaves the gate replay corpus layout alone

Bug: the format-on-Edit hook runs prettier with its defaults on this repo's JSON, reflowing the one-line entries of
`tests/scripts/gate_replay_corpus.json`, so a one-line edit churns the whole file.

1. Add a repo-root `.prettierignore` that lists `tests/scripts/gate_replay_corpus.json`.
2. A test reads `.prettierignore` and asserts the corpus path is listed.

#### Automated Verification

- New test passes; `python3 tests/parallel_tests.py` on it passes.

## Final

- `bash tests/run.sh` passes. One change file per phase under `docs/changes/notes/`.

## Plan Deviations

Phase 1: plan-only mode limited to a plan named plan.md (a ticketless spec.md folder still exits 2); decided by the session, 2026-11-11; changes no criterion.
Phase 2: covered case does not require HEAD unmoved since the branch review (Option B: the commit gate covers commits made in between); session, 2026-11-11.
Phase 2: the review-credit rule in shared_record_covers covers the uncommitted change, or the last commit's change (work tree fingerprinted against HEAD~1, notes paths left out) when the tree is clean and HEAD has a parent; the empty change never counts; adopted, ruled by the user on the commit-survival change at 2026-11-11 23:33 (criteria owner plan, AC3 wording unchanged and met).
Phase 5: adopted, no criterion changes; the criteria dry-run flag shows the matched ENV line instead of the last output line because real mise output ends in `Run with --verbose` boilerplate; ruled by the session, not the user, 2026-11-12.

- 2026-11-11: Adopt plan change. Ruled by the session, not the user at 2026-11-11 22:51. No acceptance criterion changes, so the code wins: the plan follows the code. claude/.claude/skills/code/SKILL.md:34 [plan-drift]: a ticketless plan.md with acceptance-criteria.md now gets owner `plan`, and the skill's queue-item clause for ticketless plans adds a stricter condition (a record in the queue item or brief) than the owner-`plan` path; the skill was not reconciled with plan step 5.
- 2026-11-11: Adopt plan change. Ruled by the session, not the user at 2026-11-11 22:51. No acceptance criterion changes, so the code wins. Same plan-drift as above, raised again in review round two; still undecided between removing the queue-item sentence or keeping it as a stricter rule.
- 2026-11-11: Adopt plan change. Ruled by the session, not the user at 2026-11-11 22:51. No acceptance criterion changes, so the code wins. Same plan-drift as above, raised by the second code reviewer.

- 2026-11-11: Adopt plan change. Ruled by the user at 2026-11-11 23:33: the credit must survive the commit.

  The ruling: credit covers the uncommitted change, or the last commit's change when the tree is clean, never the empty change; criteria owner plan, AC3 wording unchanged and met

  The disagreement:
  claude/.claude/scripts/lib/reviewed_tree.py:302 [plan-drift] PLAN-IMPACT: `shared_record_covers` returns False when the tree has no change against HEAD (`NO_CHANGE_FINDERPRINT`, spelled `NO_CHANGE_FINGERPRINT` in the code). The plan does not say this. Plan Phase 2 step 1 says only "True when the work tree's `reviewed_fingerprint` is in the shared reviewed record", and the Plan Deviations line for Phase 2 records only Option B (HEAD may move). **What breaks:** the converged /review exists so the commit gate lets the user commit. Once the reviewed change is committed, the uncommitted change is empty, so the commit-review route stops counting. Two cases: (a) Branch review logged on T1, then a converged /review plus a commit. verify-prep reports `NOT run` and asks for another branch review. That is the loop the bug describes, now one commit later. (b) verify-prep reports `ran` through this route, the user commits, then runs `verify-log --rows`. The branch fingerprint does not change, because the content against the merge-base is the same. But `require_current_review` (verify-log:224) recomputes `review_state`, coverage is now False, and verify-log exits 2 with "no branch-wide code review covers this tree". **Why it is not a plain fix:** the reason for the exclusion holds. The empty-change value sits in many repos' records and would credit everything. But no record of a committed, gate-credited change exists to stand in for it, so more than one correction is defensible. **Question:** is "the converged review must still be uncommitted when verify-prep and verify-log run" the rule you want, given AC3's wording ("a converged /review of the current tree makes verify-prep report the review as ran")? **Change if accepted:** add a Phase 2 line to docs/plans/verify-misc-batch/plan.md `## Plan Deviations` that records the clean-tree exclusion and the commit-before-verify-log consequence, with who and when. If rejected, commit credit needs a record that survives the commit, which is a design call. acceptance_criteria: AC3
