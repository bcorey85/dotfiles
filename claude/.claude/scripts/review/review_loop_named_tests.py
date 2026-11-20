"""review_loop_named_tests.py: the tests a plan's scoped commands run by name, kept through a fix pass. The mixin's host
class holds repo, gate_commands and files_touched, and has repair."""
import named_test_targets
from finding_record import parse_finding
from review_loop_coder import CoderResult


class NamedTestRemovedError(RuntimeError):
    """A fix pass removed a test the plan runs by name, and the restore pass did not bring it back. The message is
    the blocker."""


def restore_finding(target):
    return f"restore {target}: the last fix pass removed a test the plan runs by name"


def named_test_removal_blocker(targets):
    return "the fix pass removed plan-named test " + ", ".join(targets)


class NamedTestRuns:
    def named_tests(self):
        """The plan-named test targets that exist now, for the next coder prompt."""
        return named_test_targets.named_targets(self.gate_commands, self.repo)

    def restore_named_tests(self, call_name, named, result):
        """The result of a coder pass, after one repair pass that restores any of the `named` targets the pass
        removed. Raises NamedTestRemovedError when one is still gone. The pass's own report stays the result's, so a
        skip line of the restore pass is never read as a skip of the pass's issues."""
        gone = named_test_targets.missing_targets(named, self.repo)
        if not gone:
            return result

        restore_findings = [parse_finding(restore_finding(target)) for target in gone]
        self.files_touched.update(result.changed)
        restore = self.repair(f"{call_name}-restore", restore_findings, restore_named=False)
        changed = sorted({*result.changed, *restore.changed})
        still_gone = named_test_targets.missing_targets(gone, self.repo)
        if still_gone:
            self.files_touched.update(restore.changed)
            raise NamedTestRemovedError(named_test_removal_blocker(still_gone))
        return CoderResult(result.report, [*result.diffs, *restore.diffs], changed)
