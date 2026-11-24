# Plan review round 1, shard a (Phases 0-4)

VERDICT: NEEDS CHANGES (2 blocker, 9 gap)

BLOCKER Phase 2 §2: new test-intent-reviewer description is invalid YAML unquoted (`scope: cull` holds `: `). Current line 3 is double-quoted.

BLOCKER Phase 4 §1: GP01/GP02 `rule_text` is body lines 7-18, which Phase 4 deletes. `check_rule_texts` runs before any pending-cell filter and exits on missing text (rule_meter.py:1594-1602, :2707). With a worktree root the Agent-run check fails after the cut; with the master root it breaks after the merge. No retirement path for a scenario whose text was cut.

GAP AC2: 5-decisions step 14 and the 4-explore invariant survey are listed by the ticket but no phase splits them (Phase 3 moves the survey verbatim).

GAP Phase 3 §3: opencode backend-architect.md:42/:44 carry the seed and gate sentences; the plan only patches the frontend port. Frontend gate line is :55. 8 lines in 4 files; plan removes 6.

GAP Phases 2-4 criteria: six multi-file `rg -c -F` presence items and "exactly one path" items pass on exit code whether or not every file was edited.

GAP Phase 0: G, AE, R, ES01 read ~/.claude (master); PF01 reads ~/dotfiles-test-budget-gate. The byte-identical contract is never checked against this worktree.

GAP Phase 1 §4: PF01/PF02 `rule_text` ("item is one rule, never one input") is not in this worktree and is not lines 25/30/31; the splits are always `unmeasured`. PF02's root is `~/dev/evals/rulemeter1/toolkits/pf-old-template/claude/.claude`, not the budget-gate worktree. ES01W/ES02W measure line 71, unchanged.

GAP Phase 1 §3: test_spec_budget_gate.py:146-157 uses synthetic 1000-word files; after the fold expected string is "currently 7100" (7×1000+100), 2601 gives "~8701 words".

GAP Phase 1 §2: the fold drops the `### N. [Topic]` heading form that spec-template.md:37 indexes, and drops "Scope-only rejections require explicit user sign-off"; neither is listed as cut.

GAP Phase 2 §2 / Phase 4 §2: opencode has no verify-branch or close-branch command (`commands/` has verify.md, test-audit.md, eng-spec.md); claude dispatcher names would be false there. opencode test-intent-reviewer :45 cull line keeps "(from `/test-audit`".

GAP Phase 1/4 Agent-run items: `--rule` filters to one scenario; labels name ES01W..PF02W and GP01+GP02 but the command runs one.

NIT: anchor rows 138/174/178 descriptions go stale after the cut (check compares hashes only).
NIT: fold text shown flush-left in a fence; step 13 is a 4-space-indented list item.
NIT: 03-decisions.md:107 says step 14; spec says step 13; step 13 is right.
NIT: GP02 `rule_text`/`rule_source` unstated.
NIT: whether opencode preloads architect-core cannot be settled from the tree.
