# Test Authoring Rules (coder write-time)

Single source of truth for how a coder decides WHICH tests to write. Read this
before authoring or changing any test.

Lives outside `coder-core` deliberately: it applies only to dispatches that
touch tests, while `coder-core` is preloaded into every coder dispatch —
including fix coders and the review loop's MEDIUM bucket, which write no tests
and paid for these rules on every spawn. The prohibitions that DO bind every
coder (never delete or reword an acceptance stub; never open an
`ACCEPTANCE-CONTRACT` file) stay in `coder-core` — only the authoring guidance
moved here.

Consumers: `coder-core` (pointer), `/code` step 5, `/audit review`.

## Test budget (the list comes before the tests)

Tests you author beyond the acceptance stubs are derived from the plan/task,
never from the code: list the behaviors from the success criteria (or the task
description), then write one test per behavior plus the edge cases the plan
names — that list is the whole budget. Extend existing test files and describe
blocks by default; a new test file needs a stated reason. Don't unit-test what
a stub, feature spec, or higher-level test already exercises — unit tests cover
the internals those can't see. A test you can't trace to a criterion, a named
edge case, or a real internal invariant doesn't get written: test volume is
diff noise, not rigor, and it does not make the implementation more likely to
be correct.

## One altitude per behavior

When the project uses feature-level acceptance specs (a feature-root spec file
or feature-local `specs/` dir), READ them before writing any test at another
level. A behavior already asserted in the feature spec is NOT re-asserted in a
parent/page or unit test — parent/page tests own wiring plus at most one smoke
traversal per feature; unit tests own the internals the spec can't see. If you
notice a behavior asserted at two altitudes (including pre-existing duplication
your change would extend), don't add to it — flag it in your report. Tripwire:
if one behavior change forces test edits in two files, one of those tests is at
the wrong altitude.

## Test value bar (apply before submitting)

Every test you add must be able to fail for a reason a user cares about —
otherwise it is diff noise, not coverage, and it taxes every future reader of an
already-noisy diff. Before you keep a test you wrote this task, confirm it
exercises real behavior; drop the ones that only: assert a mock/spy was called
with the args you just passed it; exercise the framework/library rather than our
code; restate the implementation (`render` with no meaningful `expect`, a
snapshot of trivial output); or re-hit a branch a sibling test already covers
with only cosmetic input changes.

This bar governs **tests you wrote this task** — it never licenses touching an
acceptance stub or a pre-existing test, and one smoke test per unit is fine (it
is the redundant 2nd+ that goes). When unsure whether a test you wrote this task
earns its place, delete it — behavior that actually matters traces back to a
criterion and can be re-added deliberately; elaborating an unsure test to
justify keeping it is how suites rot.
