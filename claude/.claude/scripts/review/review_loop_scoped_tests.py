"""review_loop_scoped_tests.py: the scoped and named test runs of a review loop, as a mixin for `LoopRun`. The host
class holds repo, out, gate_env, gates_every_run and scoped_tests, and has stop, autofix_touched_files,
reviewed_and_touched_files and scoped_failures_pre_existing."""
import pathlib
import time

import accepted_failures
import check_scope
import coder_gate
import full_check
import gate_commands as gate_command_derivation
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
    """The gate commands that are tests: the stale-prose check is left out."""
    return [command for command in gate_commands if not coder_gate.is_stale_prose_check(command)]


def derived_test_commands(repo, paths):
    """The test commands `gate_commands.derive_gate_commands` derives for the changed `paths` that exist in the tree.
    No commands are listed, so every test command is derived from the paths."""
    repo_dir = pathlib.Path(repo)
    existing = [path for path in paths if (repo_dir / path).is_file()]
    derived = gate_command_derivation.derive_gate_commands_for(repo_dir, existing, [])
    return [command for command in derived if check_scope.runs_tests(command)]


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

    def phase_test_commands(self, gate_commands):
        """The test commands of the phase's gate: the caller's (the stale-prose check left out), else the ones derived
        for the files this run reviewed and changed. Empty when none derive."""
        if gate_commands:
            return test_commands_of(gate_commands)
        return derived_test_commands(self.repo, self.reviewed_and_touched_files())

    def run_test_commands(self, test_commands, budgeted=False, stop_when_unrun=False, report_counts=False):
        """Run the scoped test commands and keep their result. A red run the autofix formatters can fix is fixed and
        run once more. A red run whose every failure also fails on HEAD without the diff is pre-existing, not red.
        A budgeted run is bound by the named-tests budget, counted from this call and shared with the rerun. With
        less than coder_gate.MIN_COMMAND_SECONDS of it left, no rerun starts and the first red run is kept.
        A run with stop_when_unrun that has a command that timed out, never started, or gave a command error or
        setup fault stops the loop too.
        A loop that gates every run, or a run with `report_counts`, adds the runner counts to the line. False, with the
        loop stopped, when one stays red."""
        deadline = time.monotonic() + NAMED_TESTS_BUDGET_SECONDS if budgeted else None
        run = self.scoped_run_within(test_commands, deadline)
        if run.tails and time_left_for_rerun(deadline) and self.autofix_touched_files():
            run = self.scoped_run_within(test_commands, deadline)
        self.scoped_tests = run.result
        if (self.gates_every_run or report_counts) and run.summaries:
            self.scoped_tests = f"{run.result}; counts: {command_summaries_text(run.summaries)}"
        if stop_when_unrun and run.gave_no_result:
            self.stop("critical-blocker", [named_run_blocker(run)])
            return False

        if not run.tails:
            return True

        try:
            pre_existing = self.scoped_failures_pre_existing(run.real_failures)
        except accepted_failures.AcceptRefusedError as error:
            # Fail closed: a damaged acceptance store must not pass a red run.
            self.stop("critical-blocker", [f"The accepted-failures store was refused: {error}. Fix or remove "
                                           "that line, then rerun."])
            return False
        if pre_existing:
            self.scoped_tests = f"{full_check.SCOPED_PRE_EXISTING}: {self.scoped_tests}"
            return True

        env_hint = ("If a test needs an env var the repo's CI sets, add it under "
                    f"{gate_env.gate_env_repo_name(self.repo)!r} in {gate_env.personal_gate_env_file()}.")
        failing = full_check.SCOPED_FAILING_PREFIX + "\n\n".join(run.tails)
        accept_hint = self.accept_failure_hint(run.real_failures)
        stop_text = "\n".join(part for part in (failing, env_hint, accept_hint) if part)
        self.stop("critical-blocker", [stop_text])
        return False
