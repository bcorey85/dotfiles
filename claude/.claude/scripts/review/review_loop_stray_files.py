"""review_loop_stray_files.py: the files a fix pass changed outside its scope, as a mixin for `LoopRun`. The scope guard
puts them back and judges them with the gate this module runs; a file the fix needs stays, any other stops the loop.
The host holds gate_commands and files_touched, and has keep_unreverted_open, phase_test_commands,
scoped_run_within and scoped_failures_pre_existing."""
import time

import accepted_failures
from review_loop_scoped_tests import NAMED_TESTS_BUDGET_SECONDS


class StrayFileError(RuntimeError):
    """A coder pass changed a file outside its scope that the fix does not need. The message is the blocker."""


class StrayFiles:
    def stray_gate_passes(self):
        """The pass's gate on the tree as it is: the caller's test commands, else the ones derived for the reviewed
        and touched files. True when it passes (a red run whose every failure is pre-existing counts), False when it
        fails, None when no gate runs, every command was skipped, it gave no result or the accepted-failures store
        is refused."""
        commands = self.phase_test_commands(self.gate_commands)
        if not commands:
            return None
        deadline = time.monotonic() + NAMED_TESTS_BUDGET_SECONDS
        run = self.scoped_run_within(commands, deadline)
        # A command that timed out or never started makes gave_no_result true, so a timeout gives no verdict.
        if run.gave_no_result or run.ran_nothing:
            return None
        if not run.tails:
            return True
        try:
            return self.scoped_failures_pre_existing(run.real_failures)
        except accepted_failures.AcceptRefusedError:
            # Fail closed: a damaged acceptance store gives no verdict, so the guard puts the files back and stops.
            return None

    def stop_on_stray_files(self, scope_guard, findings, result):
        """Raises StrayFileError, with the findings kept open, when the scope guard put back a file the fix does not
        need. The pass's changed files, the kept ones included, count as touched first."""
        if scope_guard.stray_blocker is None:
            return
        self.files_touched.update(result.changed)
        self.keep_unreverted_open(findings, result.reverted)
        raise StrayFileError(scope_guard.stray_blocker)
