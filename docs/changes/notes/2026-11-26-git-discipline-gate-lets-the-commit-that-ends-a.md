---
type: "Change"
change_type: "fixed"
title: "git-discipline-gate lets the commit that ends a merge through in a shared clone"
description: "Rule 11 allows a bare `git commit` in a shared clone when it is the command's only step besides `cd`/`pushd`/`popd`, carries no -a or -i, a merge is open there and every staged path is a path the merge changed, so a session can finish a conflicted merge."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-26T03:01:23-06:00"}
seq: 1
kind: "fix"
components: ["script/git-discipline-gate", "script/script-utils", "script/commit-pathspec", "script/merge-in-progress"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_git_discipline_gate.py::test_a_bare_commit_that_ends_a_merge_passes"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

New `lib/merge_in_progress.py` `commit_ends_merge` reads MERGE_HEAD in the commit's folder and checks that the staged paths are a subset of the paths each merged head changed since it left HEAD. It fails closed on any git failure. `bare_commit_in_shared_clone` skips the deny when that holds, the commit has no `-a`/`-i` (`commit_pathspec.sweeps_whole_index`), and the command is one plain `git` step, with only `cd`, `pushd` or `popd` steps beside it and no env wrapper, `GIT_DIR` assignment or command substitution.

The heredoc false match is not fixed here: rule 11 still denies `cat > f <<'EOF'` whose body holds `git commit -m x`, because `lib/git_commit_calls.py` `git_commit_dirs` reads heredoc body lines as commands, and every rule that calls it shares that reader. Quoted text (`echo '... git commit -m x'`) already passes. Queued as `git-discipline-gate-rule-11-reads-git-commit-text`.

## Evidence

Git refuses a pathspec commit during a merge, so a conflicted merge in a shared clone could not be finished. It hit the orchestrator's merge of a method branch into bench-base in a scratch worktree.

## Result

The four new pass tests fail against the old gate and pass now. The deny tests pass on both: a peer's staged file, no open merge, `-a` during a merge, an earlier step in the command, `$(...)`, and a `GIT_DIR` or `env` redirect. Hook time, median of 21 runs on `git commit --no-edit` in a shared clone: 67 ms with a merge open and 62 ms with none, against 62 ms and 63 ms before. A bare Python start takes 8 ms.

## Watch

None. Read the next rule 11 denies for a merge commit that still gets blocked.

## Back-out

Remove the `sole_step` path from `bare_commit_in_shared_clone`, the `is_sole_git_command` helper and `lib/merge_in_progress.py`.
