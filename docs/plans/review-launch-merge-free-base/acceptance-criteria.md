# Acceptance criteria

- **AC1** — A /review on a branch that merged master after its base, given that older base, reviews only the branch's own lines: the launch's review base leaves out the merged-in commits. (Phase 1)
- **AC2** — review_launch reads the base through `lib/merge_free_base.py` `merge_free_base`, like code_review_start, with no copy of its logic. (Phase 1)
- **AC3** — `bash tests/run.sh` passes.
