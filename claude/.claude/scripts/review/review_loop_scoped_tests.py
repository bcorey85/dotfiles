"""review_loop_scoped_tests.py: the scoped and named test runs of a review loop, as a mixin for `LoopRun`. The host
class holds repo, out, gate_env, gates_every_run and scoped_tests, and has stop, autofix_touched_files and
scoped_failures_pre_existing."""
import time

import coder_gate
import full_check
import gate_env
from test_run_output import command_summaries_text

# The file in the loop's state folder that holds the whole output of a red scoped test run.
SCOPED_TESTS_LOG = "scoped-tests.log"
# The time the named-test run of one --gates-every-run loop gets; a command that cannot start in it is named as
# never started. It bounds that run only, not the post-fix scoped test run.
NAMED_TESTS_BUDGET_SECONDS = 540


def named_run_blocker(run):
    """Why a named run stopped the loop: its result, the no-result lines the result does not already name, and the
    real failures' tails."""
    lines = [run.result, *run.unnamed_lines]
    if run.tails:
        lines.append(full_check.SCOPED_FAILING_PREFIX + "\n\n".join(run.tails))
    return "\n".join(lines)


def test_commands_of(gate_commands):
    """The gate commands that are tests: the readability and stale-prose checks are left out."""
    return [command for command in gate_commands
            if not coder_gate.is_readability_check(command) and not coder_gate.is_stale_prose_check(command)]


def time_left_for_rerun(deadline):
    """True when a rerun can start a command by `deadline`; an unbound run (deadline None) always can. A rerun with
    less left would start nothing and replace the red first run's failure with a bare `not run`."""
    if deadline is None:
        return True
    return deadline - time.monotonic() >= coder_gate.MIN_COMMAND_SECONDS


class ScopedTestRuns:
    def scoped_run_within(self, test_commands, deadline):
        """One scoped run that ends by `deadline` (a time.monotonic() value), or is unbound when deadline is None."""
        budget = None
        if deadline is not None:
            budget = max(deadline - time.monotonic(), 0)
        return coder_gate.scoped_run(self.repo, test_commands, self.gate_env, self.out / SCOPED_TESTS_LOG, budget)

    def run_test_commands(self, test_commands, budgeted=False, stop_when_unrun=False):
        """Run the scoped test commands and keep their result. A red run the autofix formatters can fix is fixed and
        run once more. A red run whose every failure also fails on HEAD without the diff is pre-existing, not red.
        A budgeted run is bound by the named-tests budget, counted from this call and shared with the rerun. With
        under 60 s of it left, no rerun starts and the first red run is kept.
        A run with stop_when_unrun that has a command that timed out, never started, or gave a command error or
        setup fault stops the loop too.
        A loop that gates every run adds the runner counts to every run's line. False, with the loop stopped, when one
        stays red."""
        deadline = time.monotonic() + NAMED_TESTS_BUDGET_SECONDS if budgeted else None
        run = self.scoped_run_within(test_commands, deadline)
        if run.tails and time_left_for_rerun(deadline) and self.autofix_touched_files():
            run = self.scoped_run_within(test_commands, deadline)
        self.scoped_tests = run.result
        if self.gates_every_run and run.summaries:
            self.scoped_tests = f"{run.result}; counts: {command_summaries_text(run.summaries)}"
        if stop_when_unrun and run.gave_no_result:
            self.stop("critical-blocker", [named_run_blocker(run)])
            return False

        if run.tails and self.scoped_failures_pre_existing(run.real_failures):
            self.scoped_tests = f"{full_check.SCOPED_PRE_EXISTING}: {self.scoped_tests}"
            return True

        if run.tails:
            env_hint = ("If a test needs an env var the repo's CI sets, add it under "
                        f"{gate_env.gate_env_repo_name(self.repo)!r} in {gate_env.personal_gate_env_file()}.")
            failing = full_check.SCOPED_FAILING_PREFIX + "\n\n".join(run.tails)
            self.stop("critical-blocker", [failing + "\n" + env_hint])
            return False

        return True
