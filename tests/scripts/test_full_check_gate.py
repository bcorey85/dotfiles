import pathlib
import sys
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.REVIEW_DIR))
import full_check
import full_check_gate
import handback

BUILD_TIME_COMMAND = "pytest && npm test"
NARROWED_COMMAND = "npm test"


class StubHost(full_check_gate.FullCheckSteps):
    """A LoopRun stand-in: the check runs as the narrowed command and ends with the result the test sets."""

    def __init__(self, result, tail="tail text"):
        self.init_full_check_state()
        self.result = result
        self.tail = tail
        self.stops = []
        self.out = pathlib.Path("/tmp/full-check-gate-test")

    def lint_pass(self, check_command):
        return True

    def run_check(self, check_command):
        self.full_check_command = NARROWED_COMMAND
        self.full_check = self.result
        return self.tail

    def stop(self, status, remaining):
        self.stops.append((status, remaining))


class FullCheckMessagesNameTheCommandThatRanTest(unittest.TestCase):
    def test_a_setup_fault_stop_names_the_narrowed_command(self):
        host = StubHost(full_check.SETUP_FAULT)

        host.full_check_pass(BUILD_TIME_COMMAND)

        status, findings = host.stops[0]
        self.assertEqual(status, handback.SETUP_FAULT_STATUS)
        self.assertIn(f"(`{NARROWED_COMMAND}`)", findings[0])
        self.assertNotIn(BUILD_TIME_COMMAND, findings[0])

    def test_a_failure_finding_names_the_narrowed_command(self):
        host = StubHost("failed (exit 1)", tail="FAIL web/app.spec.ts")

        host.full_check_pass(BUILD_TIME_COMMAND)

        status, findings = host.stops[0]
        self.assertEqual(status, "critical-blocker")
        self.assertIn(f"(`{NARROWED_COMMAND}`)", findings[0])
        self.assertNotIn(BUILD_TIME_COMMAND, findings[0])


if __name__ == "__main__":
    unittest.main()
