---
type: "Change"
change_type: "fixed"
title: "herdr-phase-change starts a worker's /code headless"
description: "herdr-phase-change now sends a /code prompt as /code --headless <rest> unless --headless already follows /code (a bare /code and verb prompts such as resume or tick are kept as given), and takes --watched to send the prompt as given for a pane a person watches. Other prompts are unchanged. Before, an orchestrator that moved a worker from /eng-spec to /code got a run with no --headless, which stopped at a phase sign-off gate in a pane nobody watches and sat idle about three hours."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T04:36:06-05:00"}
seq: 322
kind: "fix"
components: ["script/herdr-phase-change", "rule/orchestration"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_herdr_phase_change.py::HerdrPhaseChangeTest::test_a_code_prompt_goes_out_headless_unless_it_already_is_or_the_pane_is_watched"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `scripts/.local/bin/herdr-phase-change`: a prompt whose first word is `/code` goes out as `/code --headless <rest>` unless `--headless` already follows `/code`. `/code` reads `--headless` only among the flags before the task text, so the script puts it first, where it always counts, and a second copy does no harm. A `--headless` word inside task text is not a flag, so it does not stop the insert. A bare `/code` and a prompt whose first word is a `/code` verb (`resume`, `continue`, `after-plan-edit`, `tick`, `verify`, `decide`, `asks-done`, `review-again`, `skill-done`, `abort`) are kept as given, since a flag first would turn them into a start.
- New `--watched` option sends the prompt as given. A prompt for any other phase (`/eng-spec`, `/verify-branch`) is never changed.
- `orchestration.md`: a `/code` prompt goes out with `--headless`; pass `--watched` only when a person watches that pane.

## Evidence

- An orchestrator moved a worker pane to `/code` with no `--headless`. The run stopped at a phase sign-off gate in a pane nobody watches and sat idle for about three hours.
- The new test fails before the change: the `/code` prompt reaches the pane without `--headless`.

## Result

- The herdr-phase-change tests pass against the stub pane. A plain `/code` prompt, one with a `+fast` modifier, and one with `--headless` inside task text or after `--task` gain `--headless`; one where `--headless` already follows `/code` is not doubled; bare `/code`, `/code resume`, `/code tick 2`, `--watched` and non-`/code` prompts go out as given.

## Watch

—

## Back-out

Revert the commit. A `/code` prompt goes out as the orchestrator wrote it, and a run without `--headless` can stop at a sign-off gate in an unwatched pane.
