"""Runs hunk-review-pane against stub herdr and hunk commands.

Checks that a pane started by hand names itself `review` so nvim-jump finds it, and that outside herdr nothing renames.
Also covers the memory cap, the restart after an OOM kill, clearing the pid and handoff files, and `--viewers`.
"""
import json
import os
import pathlib
import re
import subprocess
import tempfile
import unittest

from stubs import write_stub

BIN_DIR = pathlib.Path(__file__).resolve().parents[2] / "scripts" / ".local" / "bin"
HUNK_REVIEW_PANE = BIN_DIR / "hunk-review-pane"


class HunkReviewPaneRenameTest(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = pathlib.Path(os.path.realpath(scratch.name))
        stub_dir = self.root / "stubs"
        stub_dir.mkdir()
        self.stub_dir = stub_dir
        self.herdr_args = self.root / "herdr-args"
        write_stub(stub_dir / "herdr-api", f'printf "%s\\n" "$*" >> {self.herdr_args}')
        write_stub(stub_dir / "hunk", "exit 0")
        write_stub(stub_dir / "hunk-untracked-flag", "exit 0")
        self.env = {
            "PATH": f"{stub_dir}:{BIN_DIR}:{os.environ['PATH']}",
            "HOME": str(self.root),
            "XDG_RUNTIME_DIR": str(self.root),
        }

    def run_pane(self, **extra_env):
        env = {**self.env, **extra_env}
        return subprocess.run([str(HUNK_REVIEW_PANE)], env=env, cwd=self.root, capture_output=True, text=True)

    def test_unlabeled_pane_renames_itself_review(self):
        result = self.run_pane(HERDR_PANE_ID="p7")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.herdr_args.read_text().splitlines(), ["pane rename p7 review"])

    def test_outside_herdr_makes_no_rename_call(self):
        result = self.run_pane()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.herdr_args.exists())

    def test_failed_rename_does_not_stop_the_review(self):
        write_stub(self.stub_dir / "herdr-api", "exit 1")
        result = self.run_pane(HERDR_PANE_ID="p7")
        self.assertEqual(result.returncode, 0, result.stderr)


POP_LINE = """
pop_line() {
    local file="$1" default="$2" first
    if [ -s "$file" ]; then
        first=$(head -n 1 "$file")
        tail -n +2 "$file" >"$file.rest"
        mv "$file.rest" "$file"
        echo "$first"
    else
        echo "$default"
    fi
}
"""


class StubbedLauncherTest(unittest.TestCase):
    """Base: stub systemd-run, systemctl, uname, hunk and herdr-api around the real launcher."""

    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = pathlib.Path(os.path.realpath(scratch.name))
        self.stub_dir = self.root / "stubs"
        self.stub_dir.mkdir()
        self.runtime = self.root / "run"
        self.runtime.mkdir()
        (self.runtime / "bus").write_text("")
        self.systemd_log = self.root / "systemd-run.log"
        self.reset_log = self.root / "reset.log"
        self.hunk_log = self.root / "hunk.log"
        self.results = self.root / "results"
        self.hunk_exits = self.root / "hunk-exits"
        write_stub(self.stub_dir / "systemd-run", f'echo "$*" >> {self.systemd_log}\nshift 8\nexec "$@"')
        write_stub(
            self.stub_dir / "systemctl",
            POP_LINE + f'case "$2" in\n  show) pop_line {self.results} success ;;\n'
            f'  reset-failed) echo "$*" >> {self.reset_log} ;;\nesac',
        )
        write_stub(self.stub_dir / "uname", "echo Linux")
        hunk_body = POP_LINE + f'echo "$*" >> {self.hunk_log}\nexit "$(pop_line {self.hunk_exits} 0)"'
        write_stub(self.stub_dir / "hunk", hunk_body)
        self.stty_log = self.root / "stty.log"
        write_stub(self.stub_dir / "stty", f'echo "$*" >> {self.stty_log}')
        write_stub(self.stub_dir / "hunk-untracked-flag", "exit 0")
        write_stub(self.stub_dir / "herdr-api", "exit 0")
        self.env = {
            "PATH": f"{self.stub_dir}:{BIN_DIR}:{os.environ['PATH']}",
            "HOME": str(self.root),
            "XDG_RUNTIME_DIR": str(self.runtime),
        }

    def run_launcher(self, *args, stdin="", **extra_env):
        env = {**self.env, **extra_env}
        command = [str(HUNK_REVIEW_PANE), *args]
        return subprocess.run(command, env=env, cwd=self.root, input=stdin, capture_output=True, text=True, timeout=60)

    def hunk_runs(self):
        return len(self.hunk_log.read_text().splitlines()) if self.hunk_log.exists() else 0


class HunkReviewPaneCapTest(StubbedLauncherTest):
    def test_launcher_starts_hunk_under_the_memory_cap(self):
        pattern = r"--user --scope --quiet --unit=hunk-review-\S+ -p MemoryMax=1G -p MemorySwapMax=0 hunk diff --watch"
        for label, extra_env in (("outside herdr", {}), ("inside herdr", {"HERDR_PANE_ID": "p7"})):
            with self.subTest(label):
                self.systemd_log.unlink(missing_ok=True)
                result = self.run_launcher(**extra_env)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertRegex(self.systemd_log.read_text(), pattern, label)

    def test_an_oom_kill_result_restarts_the_viewer(self):
        self.hunk_exits.write_text("143\n0\n")
        self.results.write_text("oom-kill\nsuccess\n")
        result = self.run_launcher(HUNK_REVIEW_RESTART_WINDOW_SECONDS="0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.hunk_runs(), 2)
        self.assertIn("1G memory cap", result.stderr)
        self.assertIn("reset-failed", self.reset_log.read_text())
        units = re.findall(r"--unit=(\S+)", self.systemd_log.read_text())
        self.assertEqual(len(units), 2, units)
        self.assertNotEqual(units[0], units[1])
        self.assertTrue(units[0].endswith("-1"), units[0])
        self.assertTrue(units[1].endswith("-2"), units[1])

    def test_an_oom_restart_clears_the_dead_viewers_pid_and_handoff(self):
        seen = self.root / "seen"
        first_done = self.root / "first-done"
        stub_body = (
            f'echo "pid=$([ -e "$HUNK_REVIEW_PIDFILE" ] && echo yes || echo no)'
            f' handoff=$([ -e "$HUNK_REVIEW_HANDOFF" ] && echo yes || echo no)" >> {seen}\n'
            f'[ ! -e {first_done} ] || exit 0\n'
            f'touch {first_done}\n'
            'echo 4242 > "$HUNK_REVIEW_PIDFILE"\n'
            'echo nvim > "$HUNK_REVIEW_HANDOFF"\n'
            'exit 137'
        )
        write_stub(self.stub_dir / "hunk", stub_body)
        result = self.run_launcher(HERDR_PANE_ID="p7", HUNK_REVIEW_RESTART_WINDOW_SECONDS="0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(seen.read_text().splitlines(), ["pid=no handoff=no", "pid=no handoff=no"])

    def test_exit_143_with_a_success_result_does_not_restart(self):
        self.hunk_exits.write_text("143\n")
        result = self.run_launcher(HUNK_REVIEW_RESTART_WINDOW_SECONDS="0")
        self.assertEqual(result.returncode, 143, result.stderr)
        self.assertEqual(self.hunk_runs(), 1)
        self.assertNotIn("restarting", result.stderr)

    def test_memory_max_variable_sets_the_cap(self):
        result = self.run_launcher(HUNK_REVIEW_MEMORY_MAX="512M")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("-p MemoryMax=512M ", self.systemd_log.read_text())

    def test_bad_memory_max_exits_2_before_hunk_starts(self):
        result = self.run_launcher(HUNK_REVIEW_MEMORY_MAX="lots")
        self.assertEqual(result.returncode, 2)
        self.assertIn("HUNK_REVIEW_MEMORY_MAX", result.stderr)
        self.assertEqual(self.hunk_runs(), 0)

    def test_no_user_bus_runs_hunk_uncapped(self):
        (self.runtime / "bus").unlink()
        result = self.run_launcher()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.systemd_log.exists())
        self.assertEqual(self.hunk_runs(), 1)

    def test_not_linux_runs_hunk_uncapped(self):
        write_stub(self.stub_dir / "uname", "echo Darwin")
        result = self.run_launcher()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.systemd_log.exists())
        self.assertEqual(self.hunk_runs(), 1)

    def test_oom_kill_after_the_window_restarts_the_viewer(self):
        self.hunk_exits.write_text("137\n0\n")
        result = self.run_launcher(HUNK_REVIEW_RESTART_WINDOW_SECONDS="0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.hunk_runs(), 2)
        self.assertIn("1G memory cap", result.stderr)
        self.assertIn("\x1b[?1049l", result.stdout)
        self.assertEqual(self.stty_log.read_text().splitlines(), ["sane"])

    def test_oom_kill_inside_the_window_waits_for_enter(self):
        self.hunk_exits.write_text("137\n0\n")
        result = self.run_launcher(stdin="\n", HUNK_REVIEW_RESTART_WINDOW_SECONDS="600")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.hunk_runs(), 2)
        self.assertIn("press Enter to try again", result.stderr)

    def test_oom_kill_inside_the_window_with_no_input_stops(self):
        self.hunk_exits.write_text("137\n0\n")
        result = self.run_launcher(stdin="", HUNK_REVIEW_RESTART_WINDOW_SECONDS="600")
        self.assertEqual(result.returncode, 137, result.stderr)
        self.assertEqual(self.hunk_runs(), 1)

    def test_uncapped_exit_137_is_not_restarted(self):
        (self.runtime / "bus").unlink()
        self.hunk_exits.write_text("137\n0\n")
        result = self.run_launcher(HUNK_REVIEW_RESTART_WINDOW_SECONDS="0")
        self.assertEqual(result.returncode, 137, result.stderr)
        self.assertEqual(self.hunk_runs(), 1)

    def test_a_scope_that_fails_to_start_starts_no_uncapped_viewer(self):
        write_stub(self.stub_dir / "systemd-run", 'echo "Failed to start transient scope" >&2\nexit 1')
        result = self.run_launcher()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.hunk_runs(), 0)
        self.assertIn("Failed to start transient scope", result.stderr)


class HunkReviewPaneViewersTest(StubbedLauncherTest):
    def add_viewer(self, pane, pid_text, root_text=None):
        pane_dir = self.runtime / "hunk-review-pane" / pane
        pane_dir.mkdir(parents=True)
        (pane_dir / "hunk.pid").write_text(pid_text)
        if root_text is not None:
            (pane_dir / "root").write_text(root_text + "\n")

    def test_viewers_lists_each_state_dir_with_a_pid_file(self):
        self.add_viewer("w5M_p2", "936851\n", "/work/checkout")
        self.add_viewer("p9", "42")
        (self.runtime / "hunk-review-pane" / "p3").mkdir()
        result = self.run_launcher("--viewers")
        self.assertEqual(result.returncode, 0, result.stderr)
        listing = json.loads(result.stdout)
        self.assertEqual(listing["cap_bytes"], 1073741824)
        self.assertEqual(
            sorted(listing["viewers"], key=lambda row: row["pane"]),
            [
                {"pane": "p9", "root": "", "pid": 42},
                {"pane": "w5M_p2", "root": "/work/checkout", "pid": 936851},
            ],
        )

    def test_viewers_with_no_state_root_prints_an_empty_list(self):
        result = self.run_launcher("--viewers")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"cap_bytes": 1073741824, "viewers": []})

    def test_viewers_reports_the_cap_in_bytes(self):
        result = self.run_launcher("--viewers", HUNK_REVIEW_MEMORY_MAX="2G")
        self.assertEqual(json.loads(result.stdout)["cap_bytes"], 2147483648)

    def test_viewers_exits_2_when_jq_fails(self):
        write_stub(self.stub_dir / "jq", "exit 1")
        result = self.run_launcher("--viewers")
        self.assertEqual(result.returncode, 2, result.stderr)

    def test_a_pid_file_that_is_not_a_pid_exits_2_naming_it(self):
        self.add_viewer("p1", "12ab\n")
        result = self.run_launcher("--viewers")
        self.assertEqual(result.returncode, 2)
        self.assertIn("p1/hunk.pid: expected a pid", result.stderr)

    def test_an_empty_pid_file_is_skipped_as_mid_write(self):
        self.add_viewer("p1", "")
        self.add_viewer("p2", "42\n")
        result = self.run_launcher("--viewers")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([row["pane"] for row in json.loads(result.stdout)["viewers"]], ["p2"])

    def test_a_bad_memory_cap_exits_2_naming_the_variable_and_prints_nothing(self):
        result = self.run_launcher("--viewers", HUNK_REVIEW_MEMORY_MAX="lots")
        self.assertEqual(result.returncode, 2)
        self.assertIn("HUNK_REVIEW_MEMORY_MAX", result.stderr)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
