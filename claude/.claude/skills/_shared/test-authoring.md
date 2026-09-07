# Test Authoring Rules (coder write-time)

How a coder decides WHICH tests to write — read before authoring/changing any test. Lives outside `coder-core` deliberately (applies only to test-touching dispatches); the universal prohibitions stay there.

Consumers: `coder-core` (pointer), `/code` step 3b (test-writer dispatch), `/audit review`.

## Test budget (the list comes before the tests)

Tests are ordinary tests — names describe behavior, never ids/paths (`~/.claude/skills/_shared/code-vocabulary.md`). Beyond AC: derive from plan/task, never code — list behaviors from success criteria, one test per behavior + named edge cases; that list is the whole budget. Extend existing files by default; new files need a stated reason. Don't unit-test what a stub/spec/higher test already covers. Untraceable-to-criterion/edge/invariant → not written.

## One altitude per behavior

With feature-level acceptance specs, READ them first. Asserted-in-spec ⇒ NOT re-asserted elsewhere (parent/page own wiring + one smoke traversal; units own spec-invisible internals). Behavior at two altitudes (even pre-existing) → don't extend, flag it. Tripwire: one behavior change forcing two files' edits = wrong altitude somewhere.

## Test value bar (apply before submitting)

Every added test must fail for a reason a user cares about, else diff noise. Drop ones that only: assert a mock called with just-passed args; exercise framework over our code; restate implementation; re-hit a sibling-covered branch cosmetically.

## An existence check is not an assertion about content

When the criterion names specific content, existence assertions don't pin it (`!= ""`, `toBeTruthy`, `length > 0` pass on any wrong message). Assert the named content; when the exact string isn't fixed, assert the discriminating substring.

Same trap down a level: inputs satisfying **both** rules can't discriminate; loose patterns matching other output values don't pin. Pick inputs where the rules disagree.

## Diagnostics you write to stderr need a test that reads stderr

When the criterion says the tool _warns_/_explains_/_rejects_, capture stderr and assert content — exit-code/stdout-only tests leave diagnostics free to change. Check the stream has a test before judging assertions on it.

This bar governs **tests you wrote this task** — never AC tests or pre-existing ones; one smoke test per unit is fine (redundant 2nd+ goes). Unsure → delete; real behavior re-adds deliberately from a criterion.
