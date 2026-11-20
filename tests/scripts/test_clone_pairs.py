import importlib.util
import json
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import fake_jscpd
import toolkit_paths

CLONE_PAIRS = toolkit_paths.CLAUDE_DIR / "skills" / "refactor" / "scripts" / "clone_pairs.py"
module_spec = importlib.util.spec_from_file_location("clone_pairs", CLONE_PAIRS)
clone_pairs = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(clone_pairs)


def report_with(duplicates):
    return json.dumps({"duplicates": duplicates, "statistics": {}})


class ReadPairsTest(unittest.TestCase):
    def read(self, report_text, prefix=""):
        with tempfile.TemporaryDirectory() as temp_dir:
            report_file = Path(temp_dir) / "jscpd-report.json"
            if report_text is not None:
                report_file.write_text(report_text)
            return clone_pairs.read_pairs(report_file, prefix)

    def test_a_report_gives_a_pair_per_duplicate_with_prompt_text_built_from_the_fields(self):
        duplicates = [fake_jscpd.duplicate(("a/one.py", 1, 32), ("b/two.py", 2, 33)),
                      fake_jscpd.duplicate(("docs/a.md", 4, 9), ("docs/b.md", 4, 9), "markdown")]

        pairs, note = self.read(report_with(duplicates))

        self.assertEqual("", note)
        self.assertEqual(["Clone found (python)", "Clone found (markdown)"],
                         [clone_pairs.pair_lines(pair)[0] for pair in pairs])
        self.assertEqual(["python", "markdown"], [pair.format for pair in pairs])
        self.assertEqual([("a/one.py", 1, 32), ("b/two.py", 2, 33)],
                         [tuple(site) for site in pairs[0].sites])

    def test_the_audit_prefix_is_joined_onto_each_site_path(self):
        duplicates = [fake_jscpd.duplicate(("x.py", 1, 2), ("y.py", 1, 2))]

        pairs, _note = self.read(report_with(duplicates), "target/sub")

        self.assertEqual(["target/sub/x.py", "target/sub/y.py"], [site.path for site in pairs[0].sites])
        self.assertEqual("- target/sub/x.py [1 - 2]", clone_pairs.pair_lines(pairs[0])[1])

    def test_a_report_that_is_missing_or_misshapen_gives_a_note_naming_the_file_and_the_form(self):
        valid = fake_jscpd.duplicate(("a", 1, 2), ("b", 1, 2))
        cases = {
            "missing file": None,
            "not json": "Clone found (python)",
            "no duplicates list": json.dumps({"statistics": {}}),
            "duplicates not a list of objects": json.dumps({"duplicates": [1]}),
            "no second file": report_with([{"format": "python", "firstFile": {"name": "a", "start": 1, "end": 2}}]),
            "no line fields": report_with([{"format": "python", "firstFile": {"name": "a"},
                                            "secondFile": {"name": "b"}}]),
            "format not a string": report_with([{**valid, "format": 3}]),
        }
        for label, report_text in cases.items():
            with self.subTest(label):
                pairs, note = self.read(report_text)

                self.assertEqual([], pairs)
                self.assertIn("jscpd output did not parse: ", note)
                self.assertIn("jscpd-report.json", note)
                self.assertIn("`duplicates`", note)


class RunJscpdTest(unittest.TestCase):
    def test_the_audit_prefix_comes_from_a_directory_target(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "target").mkdir()
            duplicates = [fake_jscpd.duplicate(("x.py", 1, 2), ("y.py", 1, 2))]
            env = {"REFACTOR_JSCPD_CMD": fake_jscpd.stub_command(root, duplicates)}

            with mock.patch.dict(os.environ, env):
                pairs, note = clone_pairs.run_jscpd("target", 30, cwd=str(root))
            call = (root / "jscpd_call.txt").read_text()

        self.assertEqual("", note)
        self.assertEqual(["target/x.py", "target/y.py"], [site.path for site in pairs[0].sites])
        self.assertIn("--reporters json", call)

    def test_exit_code_one_still_gives_the_pairs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            duplicates = [fake_jscpd.duplicate(("x.py", 1, 2), ("y.py", 1, 2))]
            env = {"REFACTOR_JSCPD_CMD": fake_jscpd.stub_command(root, duplicates, exit_code=1)}

            with mock.patch.dict(os.environ, env):
                pairs, note = clone_pairs.run_jscpd(".", 30, cwd=str(root))

        self.assertEqual("", note)
        self.assertEqual(1, len(pairs))

    def test_a_timeout_gives_the_no_detection_note(self):
        env = {"REFACTOR_JSCPD_CMD": "jscpd"}
        timeout = subprocess.TimeoutExpired("jscpd", 1)

        with mock.patch.dict(os.environ, env), \
                mock.patch.object(clone_pairs.subprocess, "run", side_effect=timeout):
            result = clone_pairs.run_jscpd(".", 1)

        self.assertEqual(([], clone_pairs.NO_DETECTION_NOTE), result)

    def test_an_os_error_from_the_detector_gives_the_no_detection_note(self):
        env = {"REFACTOR_JSCPD_CMD": "jscpd"}

        with mock.patch.dict(os.environ, env), \
                mock.patch.object(clone_pairs.subprocess, "run", side_effect=FileNotFoundError("jscpd")):
            result = clone_pairs.run_jscpd(".", 1)

        self.assertEqual(([], clone_pairs.NO_DETECTION_NOTE), result)

    def test_a_missing_npx_with_no_override_gives_the_no_detection_note(self):
        env = {key: value for key, value in os.environ.items() if key != "REFACTOR_JSCPD_CMD"}

        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(clone_pairs.shutil, "which", return_value=None):
            result = clone_pairs.run_jscpd(".", 1)

        self.assertEqual(([], clone_pairs.NO_DETECTION_NOTE), result)

    def test_a_detector_that_writes_no_report_gives_the_not_parsed_note(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            stub = root / "silent.py"
            stub.write_text("print('done')\n")
            env = {"REFACTOR_JSCPD_CMD": f"{shlex.quote(sys.executable)} {shlex.quote(str(stub))}"}

            with mock.patch.dict(os.environ, env):
                pairs, note = clone_pairs.run_jscpd(".", 30, cwd=str(root))

        self.assertEqual([], pairs)
        self.assertIn("jscpd output did not parse: ", note)

    def test_the_npx_command_names_the_pinned_package(self):
        env = {key: value for key, value in os.environ.items() if key != "REFACTOR_JSCPD_CMD"}
        done = mock.Mock(returncode=0, stdout="")

        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(clone_pairs.shutil, "which", return_value="/usr/bin/npx"), \
                mock.patch.object(clone_pairs.subprocess, "run", return_value=done) as run:
            clone_pairs.run_jscpd("target", 30)

        command = run.call_args.args[0]
        self.assertIn(clone_pairs.JSCPD_PACKAGE, command)
        self.assertRegex(clone_pairs.JSCPD_PACKAGE, r"^jscpd@\d+\.\d+\.\d+$")


class BranchPairsTest(unittest.TestCase):
    def pair(self, clone_format, first_name, second_name):
        sites = [clone_pairs.CloneSite(name, 1, 5) for name in (first_name, second_name)]
        return clone_pairs.ClonePair(sites, clone_format)

    def test_prose_pairs_are_dropped_before_the_listing_cap(self):
        prose_pairs = [self.pair("markdown", "docs/a.md", "docs/b.md") for _ in range(clone_pairs.MAX_CLONE_PAIRS + 5)]
        prose_pairs.append(self.pair("text", "notes/a.txt", "notes/b.txt"))
        code_pair = self.pair("python", "a.py", "b.py")
        names = ("docs/a.md", "notes/a.txt", "a.py")
        untracked = [mock.Mock(path=name, added_lines=[(number, "x") for number in range(1, 6)]) for name in names]

        with mock.patch.object(clone_pairs, "run_jscpd", return_value=([*prose_pairs, code_pair], "")):
            pairs, note = clone_pairs.branch_pairs([], untracked, ".", 30)

        self.assertEqual("", note)
        self.assertEqual([code_pair], pairs)


if __name__ == "__main__":
    unittest.main()
