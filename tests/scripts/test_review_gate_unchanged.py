import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

import isolated_state
import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import reviewed_tree

CHECK_SCRIPT = pathlib.Path(os.environ.get("REVIEW_GATE_UNCHANGED_SCRIPT")
                            or pathlib.Path(__file__).resolve().parents[1] / "review_gate_unchanged.py")


class ReviewGateUnchangedTest(unittest.TestCase):
    def setUp(self):
        isolated_state.isolate_state_root(self)
        self.gate_folder = reviewed_tree.review_gate_dir()
        self.env = {**os.environ, "REVIEW_GATE_CHECK_DIR": str(self.gate_folder)}
        run_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(run_tmp.cleanup)
        self.run_tmp = run_tmp.name

    def snapshot_after_first_record(self):
        reviewed_tree.record_reviewed("live", None, tree=("/srv/first/repo", "sha256:a"))
        return self.check("snapshot").stdout

    def test_an_untouched_folder_passes(self):
        taken = self.snapshot_after_first_record()
        self.assertEqual(self.compare(taken).returncode, 0)

    def test_new_keys_outside_the_run_folder_pass(self):
        taken = self.snapshot_after_first_record()
        reviewed_tree.record_reviewed("live", None, tree=("/srv/other/repo", "sha256:b"))
        reviewed_tree.record_reviewed("fresh", None, tree=("/srv/third/repo", "sha256:c"))
        self.assertEqual(self.compare(taken).returncode, 0)

    def test_a_changed_or_removed_file_passes(self):
        taken = self.snapshot_after_first_record()
        (self.gate_folder / "live.reviewed").write_text("{}\n")
        (self.gate_folder / reviewed_tree.SHARED_REVIEWED_NAME).unlink()
        self.assertEqual(self.compare(taken).returncode, 0)

    def test_a_new_key_under_the_run_folder_fails_and_names_file_and_key(self):
        taken = self.snapshot_after_first_record()
        leaked_repo = str(pathlib.Path(self.run_tmp) / "test-repo")
        reviewed_tree.record_reviewed("fresh", None, tree=(leaked_repo, "sha256:d"))
        done = self.compare(taken)
        self.assertEqual(done.returncode, 1)
        self.assertIn(f"fresh.reviewed: {leaked_repo}", done.stderr)

    def test_a_leaked_key_in_a_base_file_or_the_shared_file_fails_and_names_the_file(self):
        taken = self.snapshot_after_first_record()
        leaked_repo = str(pathlib.Path(self.run_tmp) / "test-repo")
        base_name = "fresh" + reviewed_tree.BASE_SUFFIX
        (self.gate_folder / base_name).write_text(json.dumps({leaked_repo: "sha256:h"}))
        (self.gate_folder / reviewed_tree.SHARED_REVIEWED_NAME).write_text(json.dumps({leaked_repo: "sha256:h"}))
        done = self.compare(taken)
        self.assertEqual(done.returncode, 1)
        self.assertIn(f"{base_name}: {leaked_repo}", done.stderr)
        self.assertIn(f"{reviewed_tree.SHARED_REVIEWED_NAME}: {leaked_repo}", done.stderr)

    def test_a_key_under_the_real_path_of_a_symlinked_run_folder_fails(self):
        real_folder = pathlib.Path(self.run_tmp) / "real"
        real_folder.mkdir()
        link = pathlib.Path(self.run_tmp) / "link"
        link.symlink_to(real_folder)
        taken = self.check("snapshot").stdout
        reviewed_tree.record_reviewed("fresh", None, tree=(str(real_folder.resolve() / "repo"), "sha256:f"))
        done = self.check("compare", str(link), stdin=taken)
        self.assertEqual(done.returncode, 1)

    def test_a_new_temp_key_outside_the_given_run_folder_passes(self):
        taken = self.check("snapshot")
        other_run_repo = str(pathlib.Path(tempfile.gettempdir()) / "other-run" / "repo")
        reviewed_tree.record_reviewed("fresh", None, tree=(other_run_repo, "sha256:e"))
        done = self.compare(taken.stdout)
        self.assertEqual(done.returncode, 0)
        self.assertEqual(done.stderr, "")

    def test_a_key_under_a_folder_that_only_shares_the_run_folder_prefix_passes(self):
        taken = self.check("snapshot")
        sibling_repo = self.run_tmp + "d/repo"
        reviewed_tree.record_reviewed("fresh", None, tree=(sibling_repo, "sha256:g"))
        done = self.compare(taken.stdout)
        self.assertEqual(done.returncode, 0)
        self.assertEqual(done.stderr, "")

    def compare(self, snapshot):
        return self.check("compare", self.run_tmp, stdin=snapshot)

    def check(self, *arguments, stdin=""):
        return subprocess.run([sys.executable, "-I", str(CHECK_SCRIPT), *arguments], input=stdin, env=self.env,
                              text=True, capture_output=True)


if __name__ == "__main__":
    unittest.main()
