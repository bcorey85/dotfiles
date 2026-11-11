"""Runs detach down its perl branch, the one macOS takes, by hiding setsid from PATH."""
import os
import pathlib
import shutil
import subprocess
import tempfile
import time
import unittest

BIN_DIR = pathlib.Path(__file__).resolve().parents[2] / "scripts" / ".local" / "bin"
DETACH = pathlib.Path(os.environ.get("DETACH", BIN_DIR / "detach"))
SHELL = "/bin/sh"
PS = shutil.which("ps")
PERL = shutil.which("perl")
CHILD_WAIT_SECONDS = 10


@unittest.skipUnless(PERL and PS, "needs perl and ps")
class DetachPerlBranchTest(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = pathlib.Path(os.path.realpath(scratch.name))
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        (bin_dir / "perl").symlink_to(PERL)
        self.env = {**os.environ, "PATH": str(bin_dir)}
        self.report = self.root / "report"

    def run_detach(self, *command, new_session):
        return subprocess.run([str(DETACH), *command], env=self.env, capture_output=True, text=True,
                              start_new_session=new_session, timeout=CHILD_WAIT_SECONDS)

    def wait_for_report(self):
        deadline = time.monotonic() + CHILD_WAIT_SECONDS
        while time.monotonic() < deadline:
            fields = self.report.read_text().split() if self.report.exists() else []
            if len(fields) == 2:
                return fields
            time.sleep(0.05)
        self.fail("the detached child never wrote its report")

    def assert_child_leads_a_new_session(self, new_session):
        # The pid line comes last, so a report that ends in a newline holds both values.
        script = f'{PS} -o sid= -p $$ > {self.report}; echo $$ >> {self.report}'
        result = self.run_detach(SHELL, "-c", script, new_session=new_session)
        self.assertEqual(0, result.returncode, result.stderr)
        sid, pid = self.wait_for_report()
        self.assertEqual(pid, sid, "the child is not the leader of a new session")

    def test_a_process_group_leader_forks_into_a_new_session(self):
        self.assert_child_leads_a_new_session(new_session=True)

    def test_a_process_that_leads_no_group_gets_a_new_session(self):
        self.assert_child_leads_a_new_session(new_session=False)

    def test_a_command_that_cannot_exec_exits_non_zero_with_the_exec_message(self):
        result = self.run_detach("/nonexistent/command", new_session=False)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("detach: exec /nonexistent/command", result.stderr)

    def test_no_command_prints_usage_and_exits_non_zero(self):
        result = self.run_detach(new_session=False)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("usage: detach", result.stderr)


@unittest.skipUnless(shutil.which("setsid") and PS, "needs setsid and ps")
class DetachSetsidBranchTest(DetachPerlBranchTest):
    """Runs detach down its setsid branch, the one Linux takes, with setsid on PATH."""

    def setUp(self):
        super().setUp()
        self.env = dict(os.environ)

    def test_a_command_that_cannot_exec_exits_non_zero_with_the_exec_message(self):
        result = self.run_detach("/nonexistent/command", new_session=False)
        self.assertNotEqual(0, result.returncode)


if __name__ == "__main__":
    unittest.main()
