"""Fails when a prompt block and its row in docs/rule-anchors.md drift apart: a block with no row, a row whose block
changed or went, or a row whose file is gone."""
import os
import subprocess
import unittest

import toolkit_paths

RULE_ANCHORS = os.environ.get("RULE_ANCHORS_SCRIPT") or str(toolkit_paths.TOOLS_DIR / "rule-anchors.sh")
DRIFT_HELP = ("Run `rule-anchors.sh list <file>` for each file named above and update its row in "
              "docs/rule-anchors.md: replace the hash, then fix the evidence and the reason.")


def awk_reads_heading_intervals():
    """False on an awk whose regex has no {n,m} interval: the script's block finder then sees no heading."""
    probe = subprocess.run(["awk", 'BEGIN { exit !("## x" ~ /^#{1,6} /) }'], capture_output=True)
    return probe.returncode == 0


@unittest.skipUnless(awk_reads_heading_intervals(), "this awk has no regex interval support")
class RuleAnchorsTest(unittest.TestCase):
    def test_every_prompt_block_has_a_current_row(self):
        result = subprocess.run(["bash", RULE_ANCHORS, "check"], capture_output=True, text=True)
        faults = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, f"{faults}\n{DRIFT_HELP}")
        self.assertEqual(faults, "", f"{faults}\n{DRIFT_HELP}")


if __name__ == "__main__":
    unittest.main()
