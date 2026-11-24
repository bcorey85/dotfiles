"""The review viewer's memory cap lib, sourced in bash with stubbed system commands."""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from stubs import write_stub

DEFAULT_LIB = Path(__file__).resolve().parents[2] / "scripts" / ".local" / "lib" / "viewer-memory.bash"
LIB = Path(os.environ.get("VIEWER_MEMORY_LIB", DEFAULT_LIB))
_bash_path = shutil.which("bash")
if _bash_path is None:
    raise RuntimeError("bash is not on PATH: the viewer memory lib tests need it")
BASH: str = _bash_path


def run_bash(body, env_extra=None, path_prefix=None, only_path=None):
    """Source the lib, then run body. only_path replaces PATH, so no real binary is found."""
    env = {**os.environ, **(env_extra or {})}
    for name in ("HUNK_REVIEW_MEMORY_MAX", "HUNK_REVIEW_RESTART_WINDOW_SECONDS"):
        if name not in (env_extra or {}):
            env.pop(name, None)
    if path_prefix:
        env["PATH"] = f"{path_prefix}:{env['PATH']}"
    if only_path:
        env["PATH"] = only_path
    script = f'source "{LIB}"\n{body}'
    return subprocess.run([BASH, "-c", script], env=env, capture_output=True, text=True, check=False)


class ViewerMemoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.stubs = self.tmp / "stubs"
        self.stubs.mkdir()

    def require_en_us_locale(self):
        """The non-ASCII digit cases need a locale where [0-9] matches them; C would pass them vacuously."""
        probe = run_bash("[[ $'\\u0663' =~ ^[0-9]+$ ]]", {"LC_ALL": "en_US.UTF-8"})
        if probe.returncode != 0:
            self.fail("locale en_US.UTF-8 is not installed: the non-ASCII digit cases cannot test the digit class")

    def test_cap_suffixes_k_m_g(self):
        cases = {"512M": "536870912", "4K": "4096", "2G": "2147483648",
                 "010M": "10485760", "09K": "9216", "08G": "8589934592"}
        for value, expected in cases.items():
            with self.subTest(value=value):
                result = run_bash("viewer_memory_max_bytes", {"HUNK_REVIEW_MEMORY_MAX": value})
                self.assertEqual(result.stdout.strip(), expected, f"{value}: {result.stderr}")

    def test_bad_cap_value_is_refused_naming_the_variable(self):
        for value in ("1.5G", "G", "12", "1T", "-1M"):
            with self.subTest(value=value):
                result = run_bash("viewer_memory_checked", {"HUNK_REVIEW_MEMORY_MAX": value})
                self.assertEqual(result.returncode, 1, f"{value!r} accepted")
                self.assertIn("HUNK_REVIEW_MEMORY_MAX=", result.stderr)
                self.assertIn("expected digits then K, M or G", result.stderr)

    def test_non_ascii_digit_cap_value_is_refused(self):
        self.require_en_us_locale()
        value = "\N{ARABIC-INDIC DIGIT ONE}G"
        result = run_bash("viewer_memory_checked",
                          {"HUNK_REVIEW_MEMORY_MAX": value, "LC_ALL": "en_US.UTF-8"})
        self.assertEqual(result.returncode, 1, f"{value!r} accepted")
        self.assertIn("HUNK_REVIEW_MEMORY_MAX=", result.stderr)
        self.assertIn("expected digits then K, M or G", result.stderr)

    def test_zero_cap_says_must_be_more_than_zero(self):
        for value in ("0G", "0K", "000M"):
            with self.subTest(value=value):
                result = run_bash("viewer_memory_checked", {"HUNK_REVIEW_MEMORY_MAX": value})
                self.assertEqual(result.returncode, 1, f"{value!r} accepted")
                self.assertIn(f"HUNK_REVIEW_MEMORY_MAX={value}: must be more than zero", result.stderr)
                self.assertNotIn("expected digits", result.stderr)

    def test_too_large_cap_says_too_large(self):
        result = run_bash("viewer_memory_checked", {"HUNK_REVIEW_MEMORY_MAX": "99999999999G"})
        self.assertEqual(result.returncode, 1)
        self.assertIn("HUNK_REVIEW_MEMORY_MAX=", result.stderr)
        self.assertIn("too large", result.stderr)
        self.assertNotIn("expected digits", result.stderr)

    def test_digit_limit_per_suffix_is_exact(self):
        cases = {
            "9" * 15 + "K": 0, "9" * 16 + "K": 1,
            "9" * 12 + "M": 0, "9" * 13 + "M": 1,
            "9" * 9 + "G": 0, "9" * 10 + "G": 1,
            "0000" + "9" * 9 + "G": 0,
        }
        for value, expected_status in cases.items():
            with self.subTest(value=value):
                result = run_bash("viewer_memory_checked", {"HUNK_REVIEW_MEMORY_MAX": value})
                self.assertEqual(result.returncode, expected_status, f"{value}: {result.stderr}")

    def test_default_restart_window_is_60_seconds(self):
        result = run_bash("viewer_memory_checked && echo $viewer_restart_window_seconds")
        self.assertEqual(result.stdout.strip(), "60", result.stderr)

    def test_bad_restart_window_is_refused(self):
        result = run_bash("viewer_memory_checked", {"HUNK_REVIEW_RESTART_WINDOW_SECONDS": "soon"})
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("HUNK_REVIEW_RESTART_WINDOW_SECONDS=soon", result.stderr)
        self.assertIn("expected digits", result.stderr)

    def test_non_ascii_digit_restart_window_is_refused(self):
        self.require_en_us_locale()
        value = "\N{ARABIC-INDIC DIGIT THREE}"
        result = run_bash("viewer_memory_checked",
                          {"HUNK_REVIEW_RESTART_WINDOW_SECONDS": value, "LC_ALL": "en_US.UTF-8"})
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(f"HUNK_REVIEW_RESTART_WINDOW_SECONDS={value}", result.stderr)
        self.assertIn("expected digits", result.stderr)

    def test_too_long_restart_window_says_too_large(self):
        for value in ("9" * 19, "99999999999999999999"):
            with self.subTest(value=value):
                result = run_bash("viewer_memory_checked", {"HUNK_REVIEW_RESTART_WINDOW_SECONDS": value})
                self.assertEqual(result.returncode, 1)
                expected = f"HUNK_REVIEW_RESTART_WINDOW_SECONDS={value}: too large (at most 18 digits)"
                self.assertIn(expected, result.stderr)
                self.assertNotIn("expected digits", result.stderr)

    def test_both_bad_values_are_named_in_one_run(self):
        result = run_bash("viewer_memory_checked", {"HUNK_REVIEW_MEMORY_MAX": "1T",
                                                    "HUNK_REVIEW_RESTART_WINDOW_SECONDS": "soon"})
        self.assertEqual(result.returncode, 1)
        self.assertIn("HUNK_REVIEW_MEMORY_MAX=1T", result.stderr)
        self.assertIn("HUNK_REVIEW_RESTART_WINDOW_SECONDS=soon", result.stderr)

    def test_restart_window_of_18_digits_with_leading_zeros_is_accepted(self):
        result = run_bash("viewer_memory_checked && echo $viewer_restart_window_seconds",
                          {"HUNK_REVIEW_RESTART_WINDOW_SECONDS": "00" + "9" * 18})
        self.assertEqual(result.stdout.strip(), "9" * 18, result.stderr)

    def test_leading_zero_restart_window_is_read_as_decimal(self):
        result = run_bash("viewer_memory_checked && echo $((viewer_restart_window_seconds + 1))",
                          {"HUNK_REVIEW_RESTART_WINDOW_SECONDS": "09"})
        self.assertEqual(result.stdout.strip(), "10", result.stderr)

    def prefix_with(self, with_bus, env_extra=None, uname="Linux", commands=("systemd-run", "systemctl")):
        """Run set_viewer_cap_prefix with PATH holding only the stub folder, so no real binary is found."""
        runtime = self.tmp / "runtime"
        runtime.mkdir(exist_ok=True)
        if with_bus:
            (runtime / "bus").write_text("")
        for old_stub in self.stubs.iterdir():
            old_stub.unlink()
        write_stub(self.stubs / "uname", f"echo {uname}")
        for command in commands:
            write_stub(self.stubs / command, "exit 0")
        body = 'set_viewer_cap_prefix lane-unit\nprintf "%s\\n" "${#viewer_cap_prefix[@]}" "${viewer_cap_prefix[@]}"'
        env = {"XDG_RUNTIME_DIR": str(runtime), **(env_extra or {})}
        return run_bash(body, env, only_path=str(self.stubs))

    def test_prefix_is_empty_when_the_runtime_dir_is_empty(self):
        result = self.prefix_with(with_bus=True, env_extra={"XDG_RUNTIME_DIR": ""})
        self.assertEqual(result.stdout.split(), ["0"], result.stderr)

    def test_prefix_is_empty_off_linux_or_without_a_command(self):
        cases = {
            "not linux": {"uname": "Darwin"},
            "no systemd-run": {"commands": ("systemctl",)},
            "no systemctl": {"commands": ("systemd-run",)},
        }
        for label, options in cases.items():
            with self.subTest(label=label):
                result = self.prefix_with(with_bus=True, **options)
                self.assertEqual(result.stdout.split(), ["0"], f"{label}: {result.stderr}")

    def test_prefix_is_the_systemd_run_scope_with_a_bus(self):
        result = self.prefix_with(with_bus=True, env_extra={"HUNK_REVIEW_MEMORY_MAX": "512M"})
        words = result.stdout.split("\n")[1:-1]
        expected = ["systemd-run", "--user", "--scope", "--quiet", "--unit=lane-unit",
                    "-p", "MemoryMax=512M", "-p", "MemorySwapMax=0"]
        self.assertEqual(words, expected, result.stderr)

    def scope_read(self, result_text):
        result_file = self.tmp / "result"
        result_file.write_text((result_text or "") + "\n")
        log_file = self.tmp / "systemctl.log"
        # reset-failed deletes the result file, as a real reset clears the scope: a show after it reads nothing.
        show_command = (f'[ -f "{result_file}" ] && cat "{result_file}"' if result_text is not None
                        else "echo show failed >&2; exit 1")
        write_stub(self.stubs / "systemctl",
                   f'case "$*" in\n'
                   f'  "--user show lane-unit.scope -p Result --value") {show_command} ;;\n'
                   f'  "--user reset-failed lane-unit.scope") echo "$*" >> "{log_file}"; '
                   f'rm "{result_file}"; echo reset noise >&2 ;;\n'
                   f'  *) echo "unexpected systemctl call: $*" >&2; exit 64 ;;\nesac\n')
        run = run_bash("viewer_scope_was_oom_killed lane-unit", path_prefix=str(self.stubs))
        log = log_file.read_text() if log_file.exists() else ""
        return run, log

    def test_an_oom_kill_result_reads_as_killed(self):
        run, log = self.scope_read("oom-kill")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("reset-failed lane-unit.scope", log)

    def test_a_failed_read_reads_as_not_killed_and_still_resets(self):
        run, log = self.scope_read(None)
        self.assertEqual(run.returncode, 1)
        self.assertIn("reset-failed lane-unit.scope", log)
        self.assertEqual(run.stderr, "")


if __name__ == "__main__":
    unittest.main()
