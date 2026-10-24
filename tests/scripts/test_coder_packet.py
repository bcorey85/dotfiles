import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
REAL_CLAUDE = pathlib.Path(os.environ.get("CODE_STEP_REAL_CLAUDE") or REPO_ROOT / "claude" / ".claude")
PACKET = pathlib.Path(os.environ.get("CODER_PACKET_SCRIPT") or REAL_CLAUDE / "scripts" / "coder_packet.py")

WHOLE_ID = "6"
DOTTED_ID = "6.1"
PLAN_WITH_A_DOTTED_PHASE_FIRST = f"""# Plan

## Phase Status

- [ ] Phase {DOTTED_ID}: Dotted
- [ ] Phase {WHOLE_ID}: Whole

## Phase {DOTTED_ID}: Dotted

dotted body

## Phase {WHOLE_ID}: Whole

whole body
"""


class CoderPacketTest(unittest.TestCase):
    def setUp(self):
        temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temp_directory.cleanup)
        self.repo = pathlib.Path(temp_directory.name)
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True, capture_output=True)
        self.env = dict(os.environ, HOME=str(self.repo))

    def packet(self, plan_text, phase_number):
        (self.repo / "plan.md").write_text(plan_text)
        return subprocess.run([sys.executable, str(PACKET), str(self.repo / "plan.md"), phase_number], cwd=self.repo,
                              env=self.env, capture_output=True, text=True)

    def test_a_phase_reads_its_own_section_when_a_dotted_phase_of_the_same_prefix_comes_first(self):
        result = self.packet(PLAN_WITH_A_DOTTED_PHASE_FIRST, WHOLE_ID)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn(f"plan.md lines 12-14 (Phase {WHOLE_ID})", result.stdout)

    def test_the_dotted_phase_reads_its_own_section(self):
        result = self.packet(PLAN_WITH_A_DOTTED_PHASE_FIRST, DOTTED_ID)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn(f"plan.md lines 8-11 (Phase {DOTTED_ID})", result.stdout)

    def test_a_phase_is_not_found_when_the_plan_has_only_its_dotted_phase(self):
        plan_with_only_the_dotted_phase = PLAN_WITH_A_DOTTED_PHASE_FIRST.split(f"## Phase {WHOLE_ID}: Whole")[0]

        result = self.packet(plan_with_only_the_dotted_phase, WHOLE_ID)

        self.assertNotEqual(0, result.returncode)
        self.assertIn(f"no Phase {WHOLE_ID} heading in the plan", result.stderr)


if __name__ == "__main__":
    unittest.main()
