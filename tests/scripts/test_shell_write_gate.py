"""Checks for shell_write_gate.py, the PreToolUse(Bash) hook that denies shell writes bypassing Write/Edit."""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

import toolkit_paths

SCRIPT = pathlib.Path(os.environ.get("HOOK_SCRIPTS_DIR")
                      or toolkit_paths.GATES_DIR) / "shell_write_gate.py"
HINT = "#skip-shell-write-gate"


class ShellWriteGateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        (self.repo / "tracked.txt").write_text("x\n")
        (self.repo / "untracked.txt").write_text("x\n")
        subprocess.run(["git", "-C", str(self.repo), "add", "tracked.txt"], check=True)

    def run_hook(self, stdin, env_extra=None, script=None):
        env = {"PATH": os.environ["PATH"], "HOME": str(self.home), "TMPDIR": str(self.tmp)}
        env.update(env_extra or {})
        return subprocess.run([sys.executable, str(script or SCRIPT)], input=stdin, capture_output=True,
                              text=True, env=env, cwd=str(self.repo))

    def run_command(self, command, agent=None, cwd=None, script=None):
        payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": command},
                   "cwd": cwd or str(self.repo)}
        if agent:
            payload["agent_type"] = agent
        return self.run_hook(json.dumps(payload), script=script)

    def denied(self, finished):
        self.assertEqual(finished.returncode, 0)
        self.assertEqual(finished.stderr, "")
        decision = json.loads(finished.stdout)["hookSpecificOutput"]
        self.assertEqual(decision["hookEventName"], "PreToolUse")
        self.assertEqual(decision["permissionDecision"], "deny")
        return decision["permissionDecisionReason"]

    def assert_denied(self, command, **options):
        return self.denied(self.run_command(command, **options))

    def assert_allowed(self, command, **options):
        finished = self.run_command(command, **options)
        self.assertEqual((finished.returncode, finished.stdout, finished.stderr), (0, "", ""))

    # input handling

    def test_empty_command_and_empty_input_pass(self):
        self.assert_allowed("")
        finished = self.run_hook("")
        self.assertEqual((finished.returncode, finished.stdout), (0, ""))
        finished = self.run_hook(json.dumps({"tool_input": {}}))
        self.assertEqual((finished.returncode, finished.stdout), (0, ""))

    def test_unparseable_input_fails_closed(self):
        for stdin in ("not json", json.dumps({"tool_input": "ls"}), json.dumps([1])):
            reason = self.denied(self.run_hook(stdin))
            self.assertEqual(reason, "[shell-write-gate] hook input did not parse — failing closed. "
                                     "Report this to the user.")

    def test_skip_hooks_env_passes(self):
        finished = self.run_hook(json.dumps({"tool_input": {"command": "sed -i s/a/b/ tracked.txt"}}),
                                 env_extra={"CLAUDE_SKIP_HOOKS": "1"})
        self.assertEqual((finished.returncode, finished.stdout), (0, ""))

    # in-place editors

    def test_sed_in_place_denied_with_target_and_hint(self):
        reason = self.assert_denied("sed -i 's/a/b/' tracked.txt")
        self.assertTrue(reason.startswith("[shell-write-gate] in-place editing of tracked.txt bypasses the "
                                          "Write/Edit hook pipeline. Use the Write or Edit tool."))
        self.assertIn(HINT, reason)

    def test_in_place_variants_denied(self):
        for command in ("gsed --in-place s/a/b/ f", "sed --in-place=.bak s/a/b/ f", "sed -ni 's/a/b/p' f",
                        "perl -pi -e 's/a/b/' f", "perl -i -ne 'print' f", "awk -i inplace '{print}' f",
                        "gawk -i inplace '{print}' f", "FOO=1 sed -i s/a/b/ f", "time sed -i s/a/b/ f",
                        "cat x && sed -i s/a/b/ f", "/usr/bin/sed -i s/a/b/ f", "ls | xargs sed -i s/a/b/",
                        "find . -exec sed -i s/a/b/ {} ;", "sudo sed -i s/a/b/ f"):
            self.assert_denied(command)

    def test_target_falls_back_to_whole_segment_when_last_word_is_unusable(self):
        self.assertIn("in-place editing of sed -i s/a/b/ -n bypasses",
                      self.assert_denied("sed -i s/a/b/ -n"))
        self.assertIn("editing of sed -i 's/a/b/' \"f\" bypasses", self.assert_denied("sed -i 's/a/b/' \"f\""))

    def test_editor_names_as_arguments_pass(self):
        for command in ("grep -in sed file", "echo sed -i", "ls -i", "sed s/a/b/ f", "perl -e 'print 1'",
                        "perl -p f", "awk '{print}' f", "git log -i"):
            self.assert_allowed(command)

    def test_escape_comment_disarms_rules(self):
        self.assert_allowed("sed -i s/a/b/ f " + HINT)
        self.assert_allowed("echo hi > tracked.txt " + HINT)

    # redirection and tee

    def test_redirect_onto_tracked_file_denied(self):
        for command in ("echo hi > tracked.txt", "echo hi >> tracked.txt", "echo hi >tracked.txt",
                        "echo hi | tee tracked.txt", "echo hi | tee -a tracked.txt",
                        "echo hi | tee -a -i tracked.txt", "echo hi > './tracked.txt'",
                        "echo hi > \"tracked.txt\"", "echo hi 2> tracked.txt"):
            reason = self.assert_denied(command)
            self.assertTrue(reason.startswith(f"[shell-write-gate] {self.repo}/"), reason)
            self.assertIn("tracked.txt is git-tracked. Shell writes bypass the Write/Edit hook pipeline "
                          "(comment/prose/budget gates). Use the Write or Edit tool.", reason)
            self.assertIn(HINT, reason)

    def test_redirect_onto_untracked_or_special_target_passes(self):
        for command in ("echo hi > untracked.txt", "echo hi > new.txt", "echo hi > /dev/null", "ls 2>&1",
                        "ls >&2", "echo hi | tee untracked.txt", "echo hi | tee -a", "echo a > ", "echo hi >> >",
                        "cat < tracked.txt", "echo committee tracked.txt"):
            self.assert_allowed(command)

    def test_absolute_tilde_and_cwd_targets(self):
        self.assert_denied(f"echo hi > {self.repo}/tracked.txt")
        self.assert_denied("echo hi > ../repo/tracked.txt")
        sub = self.repo / "sub"
        sub.mkdir()
        self.assert_denied("echo hi > ../tracked.txt", cwd=str(sub))
        tilde_repo = self.home / "r"
        subprocess.run(["git", "init", "-q", str(tilde_repo)], check=True)
        (tilde_repo / "t.txt").write_text("x\n")
        subprocess.run(["git", "-C", str(tilde_repo), "add", "t.txt"], check=True)
        reason = self.assert_denied("echo hi > ~/r/t.txt")
        self.assertIn(f"{self.home}/r/t.txt is git-tracked", reason)

    def test_symlink_to_tracked_file_denied_with_resolved_path(self):
        os.symlink(str(self.repo / "tracked.txt"), str(self.tmp / "link.txt"))
        reason = self.assert_denied("echo hi > ../link.txt")
        self.assertIn("%s is git-tracked" % (self.repo / "tracked.txt"), reason)

    def test_redirect_into_missing_directory_or_non_repo_passes(self):
        self.assert_allowed("echo hi > nodir/tracked.txt")
        plain = self.tmp / "plain"
        plain.mkdir()
        (plain / "f").write_text("x")
        self.assert_allowed("echo hi > f", cwd=str(plain))

    def test_trailing_slash_target_is_checked_without_error(self):
        self.assert_allowed("echo hi > untracked.txt/")

    def test_denies_on_second_segment(self):
        reason = self.assert_denied("echo a > untracked.txt; echo b > tracked.txt")
        self.assertIn("tracked.txt is git-tracked", reason)

    # test ownership gate beside the script

    def install_with_gate(self, gate_body):
        folder = self.tmp / "scripts" / "gates"
        folder.mkdir(parents=True)
        script = folder / SCRIPT.name
        shutil.copy(str(SCRIPT), str(script))
        shutil.copytree(str(SCRIPT.parent.parent / "lib"), str(folder.parent / "lib"),
                        ignore=shutil.ignore_patterns("__pycache__"))
        gate =folder / "test-ownership-gate.sh"
        gate.write_text(gate_body)
        return script

    DENY_TESTS_GATE = (
        '#!/usr/bin/env bash\n'
        'in=$(cat)\n'
        'f=$(jq -r .tool_input.file_path <<<"$in")\n'
        'a=$(jq -r .agent_type <<<"$in")\n'
        'if [[ "$f" == */tests/* ]]; then\n'
        '  jq -cn --arg r "tests are owned by the test agent ($a, $f)" '
        '\'{hookSpecificOutput:{permissionDecision:"deny",permissionDecisionReason:$r}}\'\n'
        'fi\n')

    def test_ownership_gate_denies_writes_by_agents(self):
        script = self.install_with_gate(self.DENY_TESTS_GATE)
        reason = self.assert_denied("echo hi > tests/new.py", agent="coder", script=script)
        self.assertEqual(
            reason, f"[shell-write-gate] tests are owned by the test agent (coder, {self.repo}/tests/new.py)"
        )
        for command in ("rm tests/a.py", "mv src/a.py tests/a.py", "cp a tests/a", "touch tests/x",
                        "git rm tests/a.py", "git checkout -- tests/a.py", "dd if=/dev/zero of=tests/z",
                        "sed -i s/a/b/ tests/a.py", "echo x | tee tests/t.py", "ls | xargs sed -i s/a/b/ tests/q",
                        "FOO=1 rm tests/a.py", "rm -rf tests"):
            self.assert_denied(command, agent="coder", script=script)

    def test_ownership_gate_skips_main_session_and_clean_paths(self):
        script = self.install_with_gate(self.DENY_TESTS_GATE)
        self.assert_allowed("echo hi > tests/new.py", script=script)
        self.assert_allowed("echo hi > src/new.py", agent="coder", script=script)
        self.assert_allowed("rm src/a.py", agent="coder", script=script)
        self.assert_allowed("git status tests/a.py", agent="coder", script=script)
        self.assert_allowed("sed s/a/b/ tests/a.py", agent="coder", script=script)
        self.assert_allowed("cat tests/a.py", agent="coder", script=script)

    def test_ownership_gate_is_not_escapable(self):
        script = self.install_with_gate(self.DENY_TESTS_GATE)
        self.assert_denied("rm tests/a.py " + HINT, agent="coder", script=script)

    def test_ownership_gate_checks_trailing_slash_form(self):
        script = self.install_with_gate(self.DENY_TESTS_GATE.replace("*/tests/*", "*/tests/"))
        self.assert_denied("rm tests", agent="coder", script=script)

    def test_failing_ownership_gate_fails_closed(self):
        script = self.install_with_gate("#!/usr/bin/env bash\nexit 3\n")
        reason = self.assert_denied("rm tests/a.py", agent="coder", script=script)
        self.assertEqual(reason, "[shell-write-gate] internal error (exit 3) — failing closed. "
                                 "Report this to the user.")

    def test_agent_without_gate_file_falls_through_to_other_rules(self):
        self.assert_allowed("rm tests/a.py", agent="coder")
        self.assert_denied("echo hi > tracked.txt", agent="coder")


if __name__ == "__main__":
    unittest.main()
