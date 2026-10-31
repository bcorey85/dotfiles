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

    def make_outside_dir(self):
        # A real directory outside every temp root: under the real home, not the test's HOME, which sits in TMPDIR.
        outside = pathlib.Path(tempfile.mkdtemp(dir=pathlib.Path.home(), prefix=".shell-write-gate-test-"))
        self.addCleanup(shutil.rmtree, outside, ignore_errors=True)
        return outside

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
                        "find . -exec sed -i s/a/b/ {} ;", "sudo sed -i s/a/b/ f",
                        "sed -i 's/a\\|b/c/' f", "sed -i 's/\\(a\\)/b/' f"):
            self.assert_denied(command)

    def test_target_falls_back_to_whole_segment_when_last_word_is_unusable(self):
        self.assertIn("in-place editing of sed -i s/a/b/ -n bypasses",
                      self.assert_denied("sed -i s/a/b/ -n"))
        self.assertIn("in-place editing of f bypasses", self.assert_denied("sed -i 's/a/b/' \"f\""))

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
                        "cat < tracked.txt", "echo committee tracked.txt", "rg -n tee tracked.txt"):
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

    # relative targets resolve against the session cwd, stream merges, heredoc bodies

    def test_a_relative_target_resolves_against_the_session_cwd_whatever_a_cd_names(self):
        (self.repo / "sub").mkdir()
        scratch = self.tmp / "scratch"
        scratch.mkdir()
        (scratch / "tracked.txt").write_text("x\n")
        for command in ("cd sub && echo x > tracked.txt", f"cd {scratch} && echo x > tracked.txt",
                        "(cd sub; echo x > tracked.txt)", "pushd sub && echo x | tee tracked.txt"):
            reason = self.assert_denied(command)
            self.assertIn(f"{self.repo}/tracked.txt is git-tracked", reason)
            self.assertIn("session cwd and each cd folder", reason, command)

    def test_a_deny_after_a_directory_change_says_a_relative_path_is_checked_against_each_folder(self):
        scratch = self.tmp / "scratch"
        scratch.mkdir()
        for command in (f"cd {scratch} && echo y >> tracked.txt", f"pushd {scratch} && echo y | tee tracked.txt",
                        f"(cd {scratch}; echo y >> tracked.txt)"):
            reason = self.assert_denied(command)
            self.assertIn("is git-tracked", reason, command)
            self.assertIn("This gate checks a relative path against the session cwd and each cd folder before it; "
                          "use an absolute path for the file you mean.", reason, command)

    def test_a_relative_target_is_checked_against_each_literal_cd_folder_before_it(self):
        other = self.tmp / "other"
        (other / "sub").mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(other)], check=True)
        (other / "sub" / "t.txt").write_text("x\n")
        subprocess.run(["git", "-C", str(other), "add", "sub/t.txt"], check=True)
        for command in ("cd ../other/sub && echo x > t.txt", "cd .. && cd other && echo x > sub/t.txt",
                        f"cd {other} && cd sub && echo x | tee t.txt", "pushd ../other && echo x >> sub/t.txt",
                        "cd -P ../other && cd /nowhere-real && echo x > sub/t.txt",
                        "(cd ../other; echo x > sub/t.txt)", "echo $(cd ../other/sub; echo x > t.txt)"):
            reason = self.assert_denied(command)
            self.assertIn(f"{other}/sub/t.txt is git-tracked", reason, command)
        for command in ("cd ../other && echo x > new.txt", "cd ../other && echo x > t.txt",
                        f"cd ../other && echo x > {self.tmp}/new.txt", "echo x > t.txt && cd ../other/sub"):
            self.assert_allowed(command)

    def test_a_relative_target_after_a_cd_to_a_folder_that_is_not_a_literal_is_denied(self):
        for command in ('cd "$D" && echo x > new.txt', "cd $(mktemp -d) && echo x > new.txt",
                        "cd - && echo x > new.txt", "popd; echo x > new.txt", "pushd && echo x | tee new.txt",
                        "cd sub* && echo x > new.txt", "cd ~someone && echo x > new.txt",
                        "cd a b && echo x > new.txt", "cd 'unterminated; echo x > new.py",
                        "pushd +1 && echo x > new.txt", "cd -1 && echo x > new.txt"):
            reason = self.assert_denied(command)
            self.assertIn("is a relative write target after a cd to a folder this gate cannot read", reason, command)
        reason = self.assert_denied('cd "$D" && echo x > -new.txt')
        self.assertIn("-new.txt is a relative write target after a cd to a folder this gate cannot read", reason)
        for command in ('cd "$D" && echo x > /dev/null', f'cd "$D" && echo x > {self.tmp}/new.txt',
                        'cd "$D" && ls 2>&1', "cd && echo x > new.txt", "cd ~ && echo x > new.txt",
                        'cd "$TMPDIR" && echo x > new.txt', "cd ${HOME} && echo x > new.txt"):
            self.assert_allowed(command)

    def test_a_deny_without_a_directory_change_before_the_write_has_no_cwd_hint(self):
        for command in ("echo y >> tracked.txt", "echo cd sub; echo y >> tracked.txt",
                        f"echo y >> tracked.txt && cd {self.tmp}"):
            reason = self.assert_denied(command)
            self.assertNotIn("session cwd", reason, command)

    def test_a_deny_for_an_absolute_target_after_a_directory_change_has_no_cwd_hint(self):
        scratch = self.tmp / "scratch"
        scratch.mkdir()
        reason = self.assert_denied(f"cd {scratch} && echo y >> {self.repo}/tracked.txt")
        self.assertNotIn("session cwd", reason)

    def test_a_coder_is_denied_any_relative_target_after_a_directory_change(self):
        outside = self.make_outside_dir()
        for command in ("cd sub && echo x > new.py", "pushd sub && echo x > new.py",
                        "if true; then cd sub; fi; echo x > new.py", "echo $(cd sub; echo x > new.py)",
                        f"command cd {self.tmp} && echo x | tee new.py"):
            reason = self.assert_denied(command, agent="coder", cwd=str(outside))
            self.assertIn("new.py is a relative write target after a cd. ", reason, command)
            self.assertIn("This agent has no way to skip this gate.", reason, command)
        reason = self.assert_denied("cd sub && echo x > -new.txt", agent="coder", cwd=str(outside))
        self.assertIn("-new.txt is a relative write target after a cd. ", reason)
        for command in ("echo x > new.py", "echo cd sub; echo x > new.py", "echo 'cd sub' > new.py",
                        "cd sub && echo x > /srv/not-a-temp-dir/new.py", "cd sub && echo x > $UNSET_DIR/new.py"):
            self.assert_denied(command, agent="coder", cwd=str(outside))
        for command in (f"cd sub && echo x > {self.tmp}/new.py", "cd sub && echo x > $TMPDIR/new.py",
                        "cd sub && echo x > /dev/null"):
            self.assert_allowed(command, agent="coder", cwd=str(outside))

    def test_a_coder_is_not_denied_for_a_redirect_like_text_after_a_substitution_in_quotes(self):
        outside = self.make_outside_dir()
        for command in ('echo "Result: $(true) => ok" | cat', 'git commit -m "Bump to $(cat VERSION) -> faster"'):
            self.assert_allowed(command, agent="coder", cwd=str(outside))

    def test_a_write_inside_a_shell_c_string_is_checked(self):
        for command in ('bash -lc "echo x > tracked.txt"', "bash -x -c 'echo x | tee tracked.txt'",
                        'zsh -ic "echo x > tracked.txt"', 'timeout 5 bash -lc "echo x > tracked.txt"',
                        'bash -lc "cd a && echo x > tracked.txt"', 'bash -c "bash -c \'echo x > tracked.txt\'"'):
            reason = self.assert_denied(command)
            self.assertIn("tracked.txt is git-tracked", reason)
        self.assert_allowed('bash -lc "echo x > untracked.txt"')

    def test_a_write_inside_shell_c_code_behind_options_invokers_and_escapes_is_checked(self):
        for command in ('bash -euo pipefail -c "echo x > tracked.txt"',
                        'bash --rcfile /dev/null -c "echo x > tracked.txt"',
                        'xargs sh -c "echo x > tracked.txt"',
                        'find . -exec sh -c "echo x > tracked.txt" \\;',
                        'eval "echo x > tracked.txt"',
                        'bash -c "echo \\"\\$(echo a > tracked.txt)\\""'):
            reason = self.assert_denied(command)
            self.assertIn("tracked.txt is git-tracked", reason)

    def test_heredoc_bodies_and_comments_inside_shell_c_code_are_not_read_as_redirects(self):
        outside = self.make_outside_dir()
        for command in ('bash -c "cat > /tmp/x.txt <<EOF\nfoo > /opt/bar.txt\nEOF"',
                        'bash -c "echo hi # > /opt/bar.txt"'):
            self.assert_allowed(command, agent="coder", cwd=str(outside))

    def test_a_write_in_code_a_runner_takes_is_checked_against_tracked_files_only(self):
        for command in ('head -n 5 > /tmp/f; eval "echo x > tracked.txt"',
                        'if true; then eval "echo x > tracked.txt"; fi',
                        'bash -c -- "echo x > tracked.txt"', 'bash -c -e "echo x > tracked.txt"',
                        'su -c "echo x > tracked.txt"', 'watch -n1 "echo x > tracked.txt"',
                        'sh -c "echo x > tracked.txt"', 'docker exec c sh -c "echo x > tracked.txt"',
                        'git rebase -i --exec "echo hi > tracked.txt" HEAD~3',
                        "parallel 'echo {} > tracked.txt' ::: a"):
            reason = self.assert_denied(command)
            self.assertIn("tracked.txt is git-tracked", reason)

    def test_a_coder_may_write_a_new_file_in_code_a_runner_takes(self):
        outside = self.make_outside_dir()
        for command in ('docker exec c sed -i s/a/b/ /app/conf',
                        'podman exec c sh -c "echo x > /app/new.txt"',
                        'kubectl exec p -- bash -c "echo x > /app/new.txt"',
                        'ssh host bash -c "echo x > /app/new.txt"',
                        'for s in a b; do docker exec $s sh -c "echo x > /app/new.txt"; done',
                        'docker compose exec app sh -c "echo x > /app/new.txt"',
                        'docker exec c bash -lc "cat > /app/new.txt <<EOF\nx\nEOF"',
                        'sudo docker exec c tee /app/new.txt',
                        'sh -c "echo x > /app/new.txt"'):
            self.assert_allowed(command, agent="coder", cwd=str(outside))

    def test_a_tee_inside_a_container_is_no_new_file_on_the_host(self):
        outside = self.make_outside_dir()
        for command in ("echo x | docker exec -i web tee /app/config.yml",
                        "docker compose exec web tee /srv/new.txt < /dev/null"):
            self.assert_allowed(command, agent="coder", cwd=str(outside))
        self.assert_denied("echo x | tee /srv/new.txt", agent="coder", cwd=str(outside))
        self.assert_denied("echo x | docker exec -i web cat > /srv/new.txt", agent="coder", cwd=str(outside))
        self.assert_denied("echo x | docker exec -i web tee tracked.txt")

    def test_stream_merges_are_not_targets(self):
        for command in ("ls 2>&1", "ls >&2", "ls 1>&2", "ls 2>&1 | cat", "make 2>&1 | tee untracked.txt"):
            self.assert_allowed(command)
        for command in ("ls 2>&1 > tracked.txt", "ls > tracked.txt 2>&1", "ls >&2 > tracked.txt"):
            reason = self.assert_denied(command)
            self.assertIn(f"{self.repo}/tracked.txt is git-tracked", reason)

    def test_in_place_deny_names_the_file_not_a_trailing_stream_merge(self):
        for command in ("sed -i s/a/b/ f.txt 2>&1", "sed -i s/a/b/ f.txt > out.log", "sed -i s/a/b/ f.txt 2>/dev/null"):
            reason = self.assert_denied(command)
            self.assertIn("in-place editing of f.txt bypasses", reason)

    def test_gt_inside_quotes_is_not_a_redirect_for_coders(self):
        outside = self.make_outside_dir()
        for agent in ("coder", "backend-coder"):
            for command in ('rg -n "(x) => x.id" src', "jq '.[] | select(.n > 3)' data.json",
                            "git log --format='%h > %s' -5", 'rg -n "count > 0" src',
                            "echo 'a > tracked.txt'"):
                self.assert_allowed(command, agent=agent, cwd=str(outside))
                self.assert_allowed(command)

    def test_coder_variants_are_covered_by_the_new_file_rule(self):
        outside = self.make_outside_dir()
        for agent in ("backend-coder", "frontend-coder-deep", "coder-deep"):
            reason = self.assert_denied("echo hi > helper.py", agent=agent, cwd=str(outside))
            self.assertIn("Write tool", reason)
            self.assertNotIn(HINT, reason)

    def test_coder_target_with_temp_variable_is_checked_after_expansion(self):
        outside = self.make_outside_dir()
        for target in ("$TMPDIR/check.log", "${TMPDIR}/check.log", "$HOME/check.log"):
            self.assert_allowed(f"echo hi > {target}", agent="coder", cwd=str(outside))

    def test_coder_target_with_unresolved_variable_is_denied(self):
        outside = self.make_outside_dir()
        for target in ("$PWD/out.log", "$UNSET_DIR/check.log"):
            reason = self.assert_denied(f"pytest > {target}", agent="coder", cwd=str(outside))
            self.assertIn(target, reason)
            self.assertIn("cannot resolve", reason)

    def test_coder_target_through_home_is_checked_against_the_temp_dir_rule(self):
        outside = self.make_outside_dir()
        for target in ("$HOME/new.py", "${HOME}/new.py"):
            payload = {"tool_input": {"command": f"echo hi > {target}"}, "cwd": str(self.repo), "agent_type": "coder"}
            reason = self.denied(self.run_hook(json.dumps(payload), env_extra={"HOME": str(outside)}))
            self.assertIn(f"{outside}/new.py", reason)

    def test_regex_fallback_finds_the_redirect_target(self):
        reason = self.assert_denied("grep 'x\\|y' f > tracked.txt")
        self.assertIn("tracked.txt is git-tracked", reason)
        outside = self.make_outside_dir()
        self.assert_allowed("grep 'x\\|y' 'a > new.py' src", agent="coder", cwd=str(outside))

    def test_clobber_and_merge_redirects_onto_tracked_files_are_denied(self):
        outside = self.make_outside_dir()
        for command in ("echo x >| tracked.txt", "echo x >&tracked.txt", "echo x >& tracked.txt",
                        "grep 'x\\|y' f >| tracked.txt", "grep 'x\\|y' f >&tracked.txt"):
            reason = self.assert_denied(command)
            self.assertIn("tracked.txt is git-tracked", reason)
        for command in ("echo x >| newfile.txt", "echo x >&newfile.txt", "grep 'x\\|y' f >| newfile.txt"):
            self.assertIn("new file created from the shell", self.assert_denied(command, agent="coder",
                                                                                cwd=str(outside)))
        for command in ("grep 'x\\|y' f 2>&1", "grep 'x\\|y' f >&2", "grep 'x\\|y' f >&-"):
            self.assert_allowed(command, agent="coder", cwd=str(outside))

    def test_tee_behind_an_output_wrapper_is_a_write(self):
        for command in ("echo x | stdbuf -oL tee tracked.txt", "echo x | stdbuf -o L tee -a tracked.txt",
                        "echo x | setsid tee tracked.txt", "echo x | ionice -c 3 tee tracked.txt",
                        "echo x | unbuffer tee tracked.txt"):
            reason = self.assert_denied(command)
            self.assertIn("tracked.txt is git-tracked", reason)

    def test_a_tilde_target_expands_without_home_set(self):
        payload = {"tool_input": {"command": "echo hi > ~/tracked.txt"}, "cwd": str(self.repo)}
        env = {"PATH": os.environ["PATH"]}
        finished = subprocess.run([sys.executable, str(SCRIPT)], input=json.dumps(payload), capture_output=True,
                                  text=True, env=env, cwd=str(self.repo))
        self.assertEqual(finished.returncode, 0)
        self.assertEqual(finished.stderr, "")
        self.assertEqual(finished.stdout, "")

    def test_a_comment_after_a_tee_target_is_not_a_target(self):
        self.assert_allowed("echo x | tee /tmp/out.log # keep log", agent="coder")
        self.assert_allowed("echo x | tee /tmp/out.log # see tracked.txt")

    def test_a_tee_target_before_a_comment_and_a_quoted_hash_are_still_checked(self):
        reason = self.assert_denied("echo x | tee tracked.txt # keep log")
        self.assertIn("tracked.txt is git-tracked", reason)
        reason = self.assert_denied("echo '# a' | tee tracked.txt")
        self.assertIn("tracked.txt is git-tracked", reason)

    def test_in_place_editor_inside_a_group_is_denied(self):
        for command in ("(sed -i s/a/b/ f.txt)", "{ sed -i s/a/b/ f.txt; }", "(cd sub && perl -pi -e s/a/b/ f.txt)"):
            reason = self.assert_denied(command)
            self.assertIn("in-place editing of f.txt bypasses", reason)

    # in-place loop and ownership loop read shell code only

    def test_heredoc_body_and_quoted_text_are_not_in_place_edits(self):
        for command in ("cat > /tmp/probe.sh <<'EOF'\nsed -i 's/a/b/' x\nEOF",
                        'echo "done; sed -i s/a/b/ f"', "echo 'x' ; echo \"a; perl -pi -e s/a/b/ f\""):
            self.assert_allowed(command)
            self.assert_allowed(command, agent="coder")

    def test_heredoc_body_fed_to_a_shell_is_read_as_commands(self):
        for agent_fields in ({"agent_id": "a1"}, {"agent_type": "coder"}):
            command = "bash <<'EOF'\nsed -i s/a/b/ tracked.txt\nEOF"
            payload = {"tool_input": {"command": command}, "cwd": str(self.repo), **agent_fields}
            reason = self.denied(self.run_hook(json.dumps(payload)))
            self.assertIn("in-place editing of tracked.txt", reason)

    def test_heredoc_body_is_never_parsed_as_redirect(self):
        for quote in ("", "'", '"'):
            body = f"cat <<{quote}EOF{quote}\necho hi > tracked.txt\nx | tee tracked.txt\nEOF"
            self.assert_allowed(body)
        self.assert_allowed("cat <<-'EOF'\n\tx > tracked.txt\n\tEOF\nls")
        self.assert_allowed("cat <<A <<B\n> tracked.txt\nA\n> tracked.txt\nB")
        reason = self.assert_denied("cat <<EOF\nhi\nEOF\necho x > tracked.txt")
        self.assertIn("tracked.txt is git-tracked", reason)
        self.assert_denied("cat > tracked.txt <<'EOF'\nhi\nEOF")

    # the reading of comments and heredocs

    def make_tracked_scope_files(self):
        # A tracked tests/run.sh.
        (self.repo / "tests").mkdir(exist_ok=True)
        (self.repo / "tests" / "run.sh").write_text("x\n")
        subprocess.run(["git", "-C", str(self.repo), "add", "tests/run.sh"], check=True)

    def test_a_write_inside_a_substitution_in_double_quotes_is_seen(self):
        for command in ('echo "$(echo x > tracked.txt)"', 'echo "`echo x > tracked.txt`"',
                        'echo "q" "$(echo "a" > tracked.txt)"'):
            self.assert_denied(command)

    def test_a_commit_message_heredoc_in_a_substitution_hides_its_body(self):
        self.assert_allowed("git commit -m \"$(cat <<'EOF'\nquote \" then > tracked.txt\nEOF\n)\"")
        self.assert_allowed("git commit -m \"$(cat <<'EOF'\n5\" screen\nsed -i is banned\nEOF\n)\"")

    def test_a_comment_with_an_apostrophe_does_not_hide_later_commands(self):
        for command in ("ls # it's\nls # don't\nsed -i s/a/b/ f.txt", "# don't\nsed -i s/a/b/ f.txt",
                        "ls # it's\necho x > tracked.txt"):
            self.assert_denied(command)

    def test_a_substitution_in_an_unquoted_heredoc_body_is_code(self):
        self.make_tracked_scope_files()
        self.assert_denied("cat <<EOF > /dev/null\n$(echo hi > tests/run.sh)\nEOF")

    def test_an_unparsed_line_that_opens_a_heredoc_keeps_the_body_as_code(self):
        reason = self.assert_denied("echo '|'; bash <<EOF\nsed -i s/a/b/ tracked.txt\nEOF")
        self.assertIn("in-place editing of tracked.txt", reason)

    def test_a_command_behind_a_wrapper_is_judged_like_the_bare_command(self):
        for command in ("nohup sed -i s/a/b/ f", "stdbuf -o0 sed -i s/a/b/ f"):
            self.assertIn("in-place editing", self.assert_denied(command))
        self.assert_denied("nohup tee tracked.txt")

    # subagent calls

    def test_subagent_skip_comment_does_not_disarm_and_deny_says_edit(self):
        for agent_fields in ({"agent_id": "a1"}, {"agent_type": "coder"}, {"agent_id": "a1", "agent_type": "coder"}):
            for command in ("sed -i s/a/b/ f " + HINT, "echo hi > tracked.txt " + HINT):
                payload = {"tool_input": {"command": command}, "cwd": str(self.repo), **agent_fields}
                reason = self.denied(self.run_hook(json.dumps(payload)))
                self.assertIn("Edit tool", reason)
                self.assertIn("Write tool", reason)
                self.assertIn("This agent has no way to skip this gate.", reason)
                self.assertNotIn(HINT, reason)
        self.assert_allowed("echo hi > tracked.txt " + HINT, agent="reviewer")

    def test_subagent_in_place_and_tracked_redirects_denied_as_in_main_session(self):
        for agent_fields in ({"agent_id": "a1"}, {"agent_type": "reviewer"}):
            for command in ("sed -i s/a/b/ untracked.txt", "perl -pi -e s/a/b/ f", "cat >> tracked.txt <<EOF\nx\nEOF",
                            "echo hi > tracked.txt", "echo hi | tee -a tracked.txt"):
                payload = {"tool_input": {"command": command}, "cwd": str(self.repo), **agent_fields}
                self.denied(self.run_hook(json.dumps(payload)))
                self.assert_denied(command)

    # interpreter writes

    def test_script_that_reads_a_tracked_file_and_writes_a_temp_file_passes(self):
        script = self.tmp / "convert.py"
        script.write_text("import json\nconfig = json.load(open('tracked.txt'))\n"
                          f"open('{self.tmp}/out.json', 'w').write('y')\n")
        self.assert_allowed(f"python3 {script}", agent="coder")
        self.assert_allowed(f"python3 -c \"x = open('tracked.txt').read(); open('{self.tmp}/o', 'w').write(x)\"")

    def test_script_written_and_run_in_the_same_command_is_read_from_its_heredoc(self):
        script = self.tmp / "rewrite.py"
        command = f"cat > {script} <<'PY'\nopen('tracked.txt', 'w').write('y')\nPY\npython3 {script}"
        self.assertIn(f"{self.repo}/tracked.txt", self.assert_denied(command, agent="coder"))

    def test_untracked_script_that_writes_a_tracked_file_is_denied_naming_edit(self):
        script = self.tmp / "rewrite.py"
        script.write_text("import pathlib\npathlib.Path('tracked.txt').write_text('y\\n')\n")
        reason = self.assert_denied(f"python3 {script}", agent="coder")
        self.assertIn(f"{self.repo}/tracked.txt", reason)
        self.assertIn("Edit tool", reason)
        self.assertNotIn(HINT, reason)

    def test_untracked_script_that_writes_a_tracked_file_through_a_name_is_denied(self):
        (self.repo / "sub").mkdir()
        (self.repo / "sub" / "nested.txt").write_text("x\n")
        (self.repo / "docs").mkdir()
        (self.repo / "docs" / "#notes.md").write_text("x\n")
        subprocess.run(["git", "-C", str(self.repo), "add", "sub/nested.txt", "docs/#notes.md"], check=True)
        scripts = {
            "variable": "import pathlib\np = pathlib.Path('tracked.txt')\ntext = p.read_text()\n"
                        "p.write_text(text.replace('x', 'y'))\n",
            "edit list": "import pathlib\nEDITS = [\n    ('tracked.txt', 'x', 'y'),\n]\n"
                         "for path, old, new in EDITS:\n    p = pathlib.Path(path)\n"
                         "    p.write_text(p.read_text().replace(old, new))\n",
            "helper": "from pathlib import Path\ndef edit(path, old, new):\n    p = Path(path)\n"
                      "    p.write_text(p.read_text().replace(old, new))\n\nedit('tracked.txt', 'x', 'y')\n",
            "joined path": "import pathlib\nROOT = pathlib.Path.cwd()\ntarget = ROOT / 'sub' / 'nested.txt'\n"
                           "with open(target, 'w') as f:\n    f.write('y')\n",
            "method open": "import pathlib\np = pathlib.Path('tracked.txt')\n"
                           "with p.open('w') as f:\n    f.write('y')\n",
            "edit dict": "from pathlib import Path\nEDITS = {'tracked.txt': 'y'}\n"
                         "for path, text in EDITS.items():\n    Path(path).write_text(text)\n",
            "edit dict with comment": "from pathlib import Path\nEDITS = {\n    # the format: path, then text's body\n"
                                      "    'tracked.txt': 'y',\n}\n"
                                      "for path, text in EDITS.items():\n    Path(path).write_text(text)\n",
            "dict value": "from pathlib import Path\nMAP = {'out.txt': 'tracked.txt'}\n"
                          "for src, dst in MAP.items():\n    Path(dst).write_text('y')\n",
            "list, comment with paren": "from pathlib import Path\nEDITS = [\n    # step 1)\n"
                                        "    ('tracked.txt', 'y'),\n]\n"
                                        "for path, text in EDITS:\n    Path(path).write_text(text)\n",
            "dict, comment with colon": "from pathlib import Path\nEDITS = {\n    # step 1: 'out.txt': 'z'\n"
                                        "    'tracked.txt': 'y',\n}\n"
                                        "for path, text in EDITS.items():\n    Path(path).write_text(text)\n",
            "one-name list, comment with paren": "from pathlib import Path\nPATHS = [\n    # step 1)\n"
                                                 "    'tracked.txt',\n]\nfor path in PATHS:\n"
                                                 "    Path(path).write_text('y')\n",
            "# inside a path": "from pathlib import Path\nPATHS = ['docs/#notes.md']\nfor path in PATHS:\n"
                               "    Path(path).write_text('y')  # rewrite it\n",
            "shutil destination": "import shutil\ndst = 'tracked.txt'\nshutil.copy('/tmp/x', dst)\n",
            "os.replace destination": "import os\ndst = 'tracked.txt'\nos.replace('/tmp/x', dst)\n",
            "perl open": "my $p = 'tracked.txt';\nopen(my $f, '>', $p);\n",
        }
        for shape, code in scripts.items():
            with self.subTest(shape=shape):
                script = self.repo / "edit_script.py"
                script.write_text(code)
                reason = self.assert_denied(f"python3 {script}", agent="coder")
                self.assertIn("scratchpad", reason)

    def test_relative_write_joined_to_an_absolute_root_resolves_under_that_root(self):
        scratch = self.tmp / "scratch"
        scripts = {
            "path join": f"from pathlib import Path\nR = Path('{scratch}')\n(R / 'tracked.txt').write_text('y')\n",
            "string concat": f"T = '{scratch}/'\nf = 'tracked.txt'\nopen(T + f, 'w').write('y')\n",
            "os.path.join": f"import os\nR = '{scratch}'\nopen(os.path.join(R, 'tracked.txt'), 'w').write('y')\n",
        }
        for shape, code in scripts.items():
            with self.subTest(shape=shape):
                script = self.tmp / "probe.py"
                script.write_text(code)
                self.assert_allowed(f"python3 {script}", agent="coder")

    def test_relative_write_joined_to_a_root_in_the_repo_or_a_rebound_root_is_denied(self):
        scripts = {
            "repo root": f"from pathlib import Path\nR = Path('{self.repo}')\n(R / 'tracked.txt').write_text('y')\n",
            "rebound root": f"from pathlib import Path\nR = Path('{self.tmp}')\nR = Path('.')\n"
                            "(R / 'tracked.txt').write_text('y')\n",
            "rebound to the repo": f"from pathlib import Path\nR = Path('{self.tmp}')\nR = Path('{self.repo}')\n"
                                   "(R / 'tracked.txt').write_text('y')\n",
            "two call arguments": f"def w(R):\n    open(R + 'tracked.txt', 'w')\n\nw('{self.tmp}/')\n"
                                  f"w('{self.repo}/')\n",
            "augmented assignment": f"R = '{self.tmp}/'\nR += '../repo/'\nopen(R + 'tracked.txt', 'w')\n",
            "root joined to a name": f"BASE = '../repo/'\nR = '{self.tmp}/' + BASE\nopen(R + 'tracked.txt', 'w')\n",
            "missing folder and a parent escape": f"R = '{self.tmp}/scratch/nonexist/'\n"
                                                  "open(R + '../../repo/tracked.txt', 'w')\n",
        }
        for shape, code in scripts.items():
            with self.subTest(shape=shape):
                script = self.tmp / "probe.py"
                script.write_text(code)
                self.assertIn(f"{self.repo}/tracked.txt", self.assert_denied(f"python3 {script}", agent="coder"))

    def test_relative_write_beside_a_write_under_an_absolute_root_is_denied(self):
        code = (f"from pathlib import Path\nR = Path('{self.tmp}')\n"
                "with open(R / 'out.txt', 'w') as f, open('tracked.txt', 'w') as g:\n    pass\n")
        script = self.tmp / "probe.py"
        script.write_text(code)
        self.assertIn(f"{self.repo}/tracked.txt", self.assert_denied(f"python3 {script}", agent="coder"))

    def test_relative_write_by_a_script_run_after_a_cd_is_denied_naming_the_cd(self):
        tree = self.tmp / "tree"
        tree.mkdir()
        subprocess.run(["git", "init", "-q", str(tree)], check=True)
        (tree / "inner.txt").write_text("x\n")
        subprocess.run(["git", "-C", str(tree), "add", "inner.txt"], check=True)
        for written in ("tracked.txt", "inner.txt"):
            with self.subTest(written=written):
                script = self.tmp / "probe.py"
                command = (f"cd {tree} && cat > {script} <<'PY'\nopen('{written}', 'w').write('y')\nPY\n"
                           f"python3 {script}")
                reason = self.assert_denied(command, agent="coder")
                self.assertIn(f"after a cd to {tree} writes the relative path " + written, reason)
                self.assertIn("cd folder", reason)

    def test_absolute_write_by_a_script_run_after_a_cd_is_denied_as_a_script_write(self):
        tree = self.tmp / "tree"
        tree.mkdir()
        script = self.tmp / "probe.py"
        command = (f"cd {tree} && cat > {script} <<'PY'\nopen('{self.repo}/tracked.txt', 'w').write('y')\nPY\n"
                   f"python3 {script}")
        reason = self.assert_denied(command, agent="coder")
        self.assertIn("scratchpad", reason)
        self.assertNotIn("after a cd", reason)

    def test_untracked_node_script_that_writes_a_tracked_file_through_a_name_is_denied(self):
        scripts = {
            "const": "const fs = require('fs');\nconst p = 'tracked.txt';\nfs.writeFileSync(p, 'y');\n",
            "for of": "const fs = require('fs');\nfor (const p of ['tracked.txt']) {\n  fs.writeFileSync(p, 'y');\n}\n",
        }
        for shape, code in scripts.items():
            with self.subTest(shape=shape):
                script = self.repo / "edit_script.js"
                script.write_text(code)
                self.assert_denied(f"node {script}", agent="coder")

    def test_inline_code_assigning_after_an_import_on_one_line_is_denied(self):
        self.assert_denied("python3 -c \"import os; p = 'tracked.txt'; open(p,'w').write('x')\"")
        self.assert_denied("node -e \"function f() { const p = 'tracked.txt'; fs.writeFileSync(p,'y') }\"")

    def test_inline_code_whose_name_is_bound_before_a_tracked_read_on_one_line_passes(self):
        out = f"{self.tmp}/out"
        self.assert_allowed(f"node -e \"const p = '{out}'; fs.readFileSync('tracked.txt'); fs.writeFileSync(p, 'y')\"")

    def test_untracked_script_that_reads_a_tracked_file_into_a_name_and_writes_elsewhere_passes(self):
        out = f"{self.tmp}/out"
        scripts = {
            "name": f"import pathlib\ndata = open('tracked.txt').read()\nout = '{out}'\n"
                    "open(out, 'w').write(data)\npathlib.Path(out).write_text(data)\n",
            "helper": "from pathlib import Path\ndef copy(src, dst):\n    Path(dst).write_text(Path(src).read_text())\n"
                      f"\ncopy('tracked.txt', '{out}')\n",
            "loop": f"from pathlib import Path\nPAIRS = [('tracked.txt', '{out}')]\nfor src, dst in PAIRS:\n"
                    "    Path(dst).write_text(Path(src).read_text())\n",
            "assigned write": f"from pathlib import Path\nsrc = 'tracked.txt'\n"
                              f"n = Path('{out}').write_text(open(src).read())\n",
            "zip": f"from pathlib import Path\nfor src, dst in zip(['tracked.txt'], ['{out}']):\n"
                   "    Path(dst).write_text(Path(src).read_text())\n",
            "shutil source": f"import shutil\nsrc = 'tracked.txt'\nshutil.copy(src, '{out}')\n",
            "dict items": f"from pathlib import Path\nSOURCES = {{'{out}': 'tracked.txt'}}\n"
                          "for dst, src in SOURCES.items():\n    Path(dst).write_text(Path(src).read_text())\n",
            "dict items, comment with colon": f"from pathlib import Path\nSOURCES = {{\n    # out: 'tracked.txt'\n"
                                              f"    '{out}': 'tracked.txt',\n}}\n"
                                              "for dst, src in SOURCES.items():\n"
                                              "    Path(dst).write_text(Path(src).read_text())\n",
        }
        for shape, code in scripts.items():
            with self.subTest(shape=shape):
                script = self.tmp / "copy.py"
                script.write_text(code)
                self.assert_allowed(f"python3 {script}", agent="coder")

    def test_untracked_script_running_a_multi_line_npm_install_with_a_tracked_file_argument_passes(self):
        script = self.tmp / "install.py"
        script.write_text("import subprocess, sys\nsubprocess.run([\n    'npm',\n    'install',\n"
                          "    sys.argv[1],\n])\n")
        self.assert_allowed(f"python3 {script} tracked.txt", agent="coder")

    def test_untracked_script_running_a_multi_line_sed_in_place_with_a_tracked_file_argument_is_denied(self):
        script = self.tmp / "install.py"
        script.write_text("import subprocess, sys\nsubprocess.run([\n    'sed',\n    '-i',\n"
                          "    's/a/b/',\n    sys.argv[1],\n])\n")
        self.assert_denied(f"python3 {script} tracked.txt", agent="coder")

    def test_shell_line_ending_in_a_comma_inside_a_string_keeps_its_step_separator(self):
        script = self.tmp / "rewrite.py"
        script.write_text('import subprocess, sys\nsubprocess.run("""echo a,\nsed -i s/a/b/ """ + sys.argv[1], '
                          "shell=True)\n")
        self.assert_denied(f"python3 {script} tracked.txt", agent="coder")

    def test_shell_line_ending_in_a_comma_after_a_string_with_an_escaped_quote_keeps_its_step_separator(self):
        script = self.tmp / "rewrite.py"
        script.write_text('import subprocess, sys\nsubprocess.run(["echo", "a\\"b", """echo a,\nsed -i s/a/b/ """, '
                          "sys.argv[1]])\n")
        self.assert_denied(f"python3 {script} tracked.txt", agent="coder")

    def test_untracked_script_given_a_tracked_file_as_argument_is_denied(self):
        script = self.tmp / "rewrite.py"
        script.write_text("import sys\nwith open(sys.argv[1], 'w') as f:\n    f.write('y')\n")
        self.assert_denied(f"python3 {script} tracked.txt")

    def test_untracked_script_whose_write_target_comes_from_argv_is_denied(self):
        scripts = {
            "rewrite.py": "import sys\nsrc, dst = sys.argv[1:3]\nopen(dst, 'w').write(open(src).read())\n",
            "parsed.py": "import argparse\nparser = argparse.ArgumentParser()\nparser.add_argument('out')\n"
                         "args = parser.parse_args()\nopen(args.out, 'w').write('y')\n",
            "main.py": "import sys\ndef main(argv):\n    out = argv[1]\n    open(out, 'w').write('y')\n\n"
                       "main(sys.argv)\n",
            "inplace.py": "import fileinput\nfor line in fileinput.input(inplace=True):\n    print(line, end='')\n",
            "rewrite.pl": "my ($out) = @ARGV;\nopen(my $f, '>', $out);\n",
            "rewrite.js": "const [, , out] = process.argv;\nrequire('fs').writeFileSync(out, 'y');\n",
            "replace.py": "import sys, pathlib\ntmp = pathlib.Path('x.tmp')\n"
                          "tmp.write_text('y'); tmp.replace(sys.argv[1])\n",
            "rename.py": "import sys, pathlib\ntmp = pathlib.Path('x.tmp')\ntmp.write_text('y')\n"
                         "out = sys.argv[1]; tmp.rename(out)\n",
            "rename.js": "const fs = require('fs');\nfs.renameSync('x.tmp', process.argv[2]);\n",
            "rename.pl": "rename('x.tmp', $ARGV[0]);\n",
            "child.py": "import subprocess, sys\nsubprocess.run(['sed', '-i', 's/a/b/', sys.argv[1]])\n",
            "mode.py": "import sys\nmode = 'w'\nopen(sys.argv[1], mode)\n",
            "click.py": "import click\n@click.command()\n@click.argument('out')\ndef main(out):\n"
                        "    open(out, 'w')\nmain()\n",
            "commander.js": "const { program } = require('commander');\nprogram.parse();\n"
                            "const opts = program.opts();\nrequire('fs').writeFileSync(opts.out, 'y');\n",
            "str.py": "import sys\nout = sys.argv[1]\nopen(str(out), 'w')\n",
            "abspath.py": "import os, sys\nopen(os.path.abspath(sys.argv[1]), 'w')\n",
            "path.py": "import pathlib, sys\nopen(pathlib.Path(sys.argv[1]), 'w')\n",
            "unlink.pl": "unlink($ARGV[0]);\n",
            "unlink bare.pl": "unlink $ARGV[0];\n",
            "file delete.rb": "File.delete(ARGV[0])\n",
            "fileutils rm.rb": "require 'fileutils'\nFileUtils.rm(ARGV[0])\n",
            "fileutils mv.rb": "require 'fileutils'\nFileUtils.mv('a', ARGV[0])\n",
            "fileutils cp.rb": "require 'fileutils'\nFileUtils.cp('a', ARGV[0])\n",
            "fs rm.js": "require('fs').rmSync(process.argv[2]);\n",
            "rmdir.py": "import os, sys\nos.rmdir(sys.argv[1])\n",
            "named mode.py": "import sys\ndef put(out, mode):\n    open(out, mode)\nput(sys.argv[1], 'w')\n",
            "system.py": "import os, sys\nos.system('sed -i s/a/b/ ' + sys.argv[1])\n",
            "exec.js": "require('child_process').execSync(`tee ${process.argv[2]}`);\n",
            "system.pl": "system('cp', 'a', $ARGV[0]);\n",
            "backticks.rb": "`mv a #{ARGV[0]}`\n",
            "star.py": "import sys\n*sources, dst = sys.argv[1:]\nopen(dst, 'w')\n",
            "prog.py": "import sys\nprog, *files = sys.argv\nopen(files[0], 'w')\n",
            "spread.js": "const [, , ...files] = process.argv;\nrequire('fs').writeFileSync(files[0], 'y');\n",
            "minimist.js": "const { out } = minimist(process.argv.slice(2));\nrequire('fs').writeFileSync(out, 'y');\n",
            "values.js": "const { values: { out } } = parseArgs({ args: [] });\n"
                         "require('fs').writeFileSync(out, 'y');\n",
            "each.pl": "foreach my $file (@ARGV) {\n    open(my $f, '>', $file);\n}\n",
            "sub.pl": "sub put { my ($out) = @_; open(my $f, '>', $out); }\nput($ARGV[0]);\n",
            "each.rb": "ARGV.each do |f|\n  File.write(f, 'y')\nend\n",
            "each.js": "const files = process.argv.slice(2);\nfiles.forEach((f) => {\n"
                       "  require('fs').writeFileSync(f, 'y');\n});\n",
            "open lines.py": "import sys\nout = sys.argv[1]\nwith open(\n    out,\n    'w',\n) as f:\n"
                             "    f.write('y')\n",
            "os replace lines.py": "import os, sys\nos.replace(\n    't',\n    sys.argv[1],\n)\n",
            "shutil copy lines.py": "import shutil, sys\nshutil.copy(\n    'src.txt',\n    sys.argv[1],\n)\n",
            "write file lines.js": "const fs = require('fs');\nfs.writeFileSync(\n  process.argv[2],\n  'y',\n);\n",
            "path replace lines.py": "import sys, pathlib\npathlib.Path('t').replace(\n    sys.argv[1]\n)\n",
            "os remove.py": "import os, sys\nopen('o.log', 'w').write('y')\nos.remove(sys.argv[1])\n",
            "os remove only.py": "import os, sys\nos.remove(sys.argv[1])\n",
            "os truncate.py": "import os, sys\nopen('o.log', 'w').write('y')\nos.truncate(sys.argv[1], 0)\n",
            "path unlink.py": "import pathlib, sys\nopen('o.log', 'w').write('y')\n"
                              "pathlib.Path(sys.argv[1]).unlink()\n",
            "path touch.py": "import pathlib, sys\nopen('o.log', 'w').write('y')\n"
                             "p = pathlib.Path(sys.argv[1]); p.touch()\n",
            "path truncate.py": "import pathlib, sys\nopen('o.log', 'w').write('y')\n"
                                "pathlib.Path(sys.argv[1]).truncate(0)\n",
            "rmtree.py": "import shutil, sys\nopen('o.log', 'w').write('y')\nshutil.rmtree(sys.argv[1])\n",
            "unlink sync.js": "const fs = require('fs');\nfs.writeFileSync('o.log', 'y');\n"
                              "fs.unlinkSync(process.argv[2]);\n",
            "rm sync.js": "const fs = require('fs');\nfs.writeFileSync('o.log', 'y');\nfs.rmSync(process.argv[2]);\n",
            "truncate sync.js": "const fs = require('fs');\nfs.writeFileSync('o.log', 'y');\n"
                                "fs.truncateSync(process.argv[2]);\n",
            "os replace source.py": "import os, sys\nos.replace(sys.argv[1], 'x')\n",
            "os rename source.py": "import os, sys\nos.rename(sys.argv[1], 'x')\n",
            "shutil move source.py": "import shutil, sys\nshutil.move(sys.argv[1], 'x')\n",
            "path through name.py": "import pathlib, sys\nout = sys.argv[1]\np = pathlib.Path(out)\n"
                                    "p.write_text('y')\n",
            "join through name.py": "import os, sys\nname = sys.argv[1]\nout = os.path.join('d', name)\n"
                                    "open(out, 'w')\n",
            "interpolated name.pl": "my $out=$ARGV[0]; open(my $f,'>',\"$out\");\n",
            "f string.py": "import sys\nopen(f'{sys.argv[1]}.bak', 'w')\n",
            "with path open.py": "import pathlib, sys\nwith pathlib.Path(sys.argv[1]).open('w') as f:\n"
                                 "    f.write('y')\n",
            "path open.py": "import pathlib, sys\np = pathlib.Path(sys.argv[1])\np.open('w')\n",
            "deno args.js": "Deno.writeTextFileSync(Deno.args[0], 'y');\n",
            "star args.rb": "File.write($*[0], 'y')\n",
            "known args.py": "import argparse\nparser = argparse.ArgumentParser()\n"
                             "args, rest = parser.parse_known_args()\nopen(args.out, 'w')\n",
            "unlink or die.pl": "unlink $ARGV[0] or die('no');\n",
            "delete if exists.rb": "other = 'x'\nFile.delete ARGV[0] if File.exist?(other)\n",
            "system f string.py": "import os, sys\nos.system(f\"sed -i s/a/b/ {sys.argv[1]}\")\n",
            "subprocess f string shell.py": "import subprocess, sys\n"
                                            "subprocess.run(f\"cp a {sys.argv[1]}\", shell=True)\n",
            "subprocess args keyword.py": "import subprocess, sys\n"
                                          "subprocess.run(args=[\"cp\",\"a\",sys.argv[1]])\n",
            "system list.pl": "system \"cp\",\"a\",$ARGV[0];\n",
            "system string.pl": "system \"sed -i s/a/b/ $ARGV[0]\";\n",
            "system list.rb": "system \"cp\",\"a\",ARGV[0]\n",
            "path absolute.py": "import sys\np = Path(sys.argv[1]); q = p.absolute(); q.write_text(\"y\")\n",
            "strip name.py": "import sys\nname = sys.argv[1]\nout = name.strip(); open(out,\"w\")\n",
            "file open block.rb": "File.open(ARGV[0], 'w') { |f| f.write('y') }\n",
            "file open do block.rb": "out = ARGV[0]\nFile.open(out, 'w') do |f|\n  f.puts 'y'\nend\n",
            "io open.py": "import io, sys\nio.open(sys.argv[1], 'w')\n",
            "codecs open.py": "import codecs, sys\ncodecs.open(sys.argv[1], 'w', 'utf-8')\n",
            "module constant.py": "import sys\nOUT = sys.argv[1]\nopen(OUT, 'w')\n",
            "system cd and rm.py": "import os, sys\nos.system('cd d && rm ' + sys.argv[1])\n",
            "system pipe tee.py": "import os, sys\nos.system('cat a | tee ' + sys.argv[1])\n",
            "shutil copy keyword.py": "import shutil, sys\nshutil.copy('a', dst=sys.argv[1])\n",
            "variable named new.py": "import sys\nold, new = sys.argv[1:3]\nopen(new, 'w')\n",
            "variable named old.py": "import sys\nold, new = sys.argv[1:3]\nopen(old, 'w')\n",
            "variable named process.py": "import sys\nprocess = sys.argv[1]\nopen(process, 'w')\n",
            "variable named path.py": "import sys\npath = sys.argv[1]\nopen(path, 'w')\n",
            "variable named ENV.py": "import sys\nENV = sys.argv[1]\nopen(ENV, 'w')\n",
            "keyword before args.py": "import subprocess, sys\n"
                                      "subprocess.run(check=True, args=['rm', sys.argv[1]])\n",
            "rstrip name.py": "import sys\nraw = sys.argv[1]\np = raw.rstrip(); open(p, 'w')\n",
            "lstrip name.py": "import sys\nraw = sys.argv[1]\np = raw.lstrip(); open(p, 'w')\n",
            "comment in bracket.py": "import sys\nopen(\n    # note (\n    sys.argv[1], 'w')\n",
            "copy file destination.js": "const fs = require('fs');\nfs.copyFileSync('a', process.argv[2]);\n",
            "fileutils cp destination.rb": "require 'fileutils'\nFileUtils.cp 'a', ARGV[0]\n",
            "copy file callback.js": "const fs = require('fs');\nfs.copyFile('a', process.argv[2], () => {});\n",
            "copy file mode.js": "const fs = require('fs');\n"
                                 "fs.copyFileSync('a', process.argv[2], fs.constants.COPYFILE_EXCL);\n",
            "shutil copy keyword trailing comma.py": "import shutil, sys\nshutil.copy(src='a', dst=sys.argv[1],\n)\n",
            "resolve name.py": "import pathlib, sys\nraw = sys.argv[1]\np = pathlib.Path(raw)\nq = p.resolve()\n"
                               "open(q,'w')\n",
            "joinpath name.py": "import pathlib, sys\nraw = sys.argv[1]\nq = pathlib.Path('d').joinpath(raw)\n"
                                "open(q,'w')\n",
            "as posix name.py": "import pathlib, sys\nraw = sys.argv[1]\np = pathlib.Path(raw)\nq = p.as_posix()\n"
                                "open(q,'w')\n",
            "fspath name.py": "import os, sys\nraw = sys.argv[1]\nq = os.fspath(raw)\nopen(q,'w')\n",
            "format name.py": "import sys\nraw = sys.argv[1]\nt = '{}.bak'\nq = t.format(raw)\nopen(q,'w')\n",
            "expanduser name.py": "import os, sys\nraw = sys.argv[1]\nq = os.path.expanduser(raw)\nopen(q,'w')\n",
            "realpath name.py": "import os, sys\nraw = sys.argv[1]\nq = os.path.realpath(raw)\nopen(q,'w')\n",
            "install child.py": "import subprocess, sys\nsubprocess.run(['install', 'a', sys.argv[1]])\n",
            "perl in place child.py": "import subprocess, sys\n"
                                      "subprocess.run(['perl', '-pi', '-e', 's/a/b/', sys.argv[1]])\n",
            "awk in place child.py": "import subprocess, sys\n"
                                     "subprocess.run(['awk', '-i', 'inplace', '1', sys.argv[1]])\n",
            "backticks cp.pl": "my $x = `cp a $ARGV[0]`;\n",
            "docopt.py": "import docopt\nargs = docopt.docopt('x')\nopen(args['<out>'], 'w')\n",
        }
        for name, code in scripts.items():
            with self.subTest(script=name):
                script = self.tmp / name.replace(" ", "_")
                script.write_text(code)
                interpreter = {".py": "python3", ".pl": "perl", ".js": "node", ".rb": "ruby"}[script.suffix]
                reason = self.assert_denied(f"{interpreter} {script} untracked.txt tracked.txt")
                self.assertIn("a script that writes", reason)
                self.assertIn("/tracked.txt", reason)

    def test_untracked_script_that_only_reads_a_tracked_argument_passes(self):
        scripts = {
            "with two opens.py": "import sys\nwith open(sys.argv[1]) as f, open('o.log', 'w') as g:\n"
                                 "    g.write(f.read())\n",
            "chained read.py": "import sys\nopen('o.log', 'w').write(open(sys.argv[1]).read())\n",
            "read in write.js": "const fs = require('fs');\n"
                                "fs.writeFileSync('o.log', fs.readFileSync(process.argv[2]));\n",
            "str replace.py": "import sys\nplan = sys.argv[1]\nprint('x'.replace(plan, 'y'))\nopen('o.log', 'w')\n",
            "last def.py": "import sys\ndef log_path(): return 'o.log'\nlp = log_path(); open(lp, 'w')\n"
                           "open(sys.argv[1])\n",
            "name in string.py": "import sys\nplan = sys.argv[1]\nopen('plan.log', 'w')\n",
            "multi-line read.py": "import sys\nwith open(\n    sys.argv[1],\n) as f, open(\n    'o.log',\n    'w',\n)"
                                  " as g:\n    g.write(f.read())\n",
            "shutil copy.py": "import shutil, sys\nshutil.copy(sys.argv[1], 'o.log')\n",
            "copy file source.js": "const fs = require('fs');\nfs.copyFileSync(process.argv[2], 'o.log');\n",
            "fileutils cp source.rb": "require 'fileutils'\nFileUtils.cp(ARGV[0], 'o.log')\n",
            "file open.rb": "File.open('o.log', 'w')\nputs File.read(ARGV[0])\n",
            "file write join.rb": "File.write(File.join('d', 'o.log'), File.read(ARGV[0]))\n",
            "open own file.pl": "open(my $in, '<', $ARGV[0]); open(my $out, '>', 'o.log');\n",
            "open or die.pl": "open(my $in, '<', $ARGV[0]);\nopen my $f, \">\", \"o.log\" or die \"no\";\n",
            "unlink or die.pl": "my $in = $ARGV[0];\nunlink \"o.log\" or die \"no\";\n",
            "unlink unless.pl": "my $in = $ARGV[0];\nunlink \"o.log\" unless -e \"x\";\n",
            "delete unless.rb": "File.read(ARGV[0])\nFile.delete \"o.log\" unless File.exist?(\"x\")\n",
            "write in dir.rb": "File.read(ARGV[0])\nFile.write(File.join(__dir__, \"o.log\"), \"y\")\n",
            "open env.pl": "my $in = $ARGV[0];\nopen(my $f, \">\", $ENV{LOG});\n",
            "write filename.js": "const fs = require('fs');\nfs.readFileSync(process.argv[2]);\n"
                                 "fs.writeFileSync(__filename + \".log\", \"y\");\n",
            "copy file source callback.js": "const fs = require('fs');\n"
                                            "fs.copyFile(process.argv[2], 'o.log', () => {});\n",
            "join dirname.py": "import os, sys\nopen(sys.argv[1])\n"
                               "open(os.path.join(os.path.dirname(__file__), 'o.log'), 'w')\n",
            "join dirname.js": "const fs = require('fs');\nconst path = require('path');\n"
                               "fs.readFileSync(process.argv[2]);\n"
                               "fs.writeFileSync(path.join(__dirname, 'o.log'), 'y');\n",
            "env target.js": "const fs = require('fs');\nfs.readFileSync(process.argv[2]);\n"
                             "fs.writeFileSync(process.env.OUT, 'y');\n",
            "with path open read.py": "import pathlib, sys\nwith pathlib.Path(sys.argv[1]).open() as f:\n"
                                      "    data = f.read()\nopen('o.log', 'w').write(data)\n",
            "path open named mode.py": "import pathlib, sys\np = pathlib.Path(sys.argv[1])\nmode = 'r'\n"
                                       "p.open(mode)\nopen('o.log', 'w')\n",
        }
        for name, code in scripts.items():
            with self.subTest(script=name):
                script = self.tmp / name.replace(" ", "_")
                script.write_text(code)
                interpreter = {".py": "python3", ".js": "node", ".rb": "ruby", ".pl": "perl"}[script.suffix]
                self.assert_allowed(f"{interpreter} {script} tracked.txt", agent="coder")

    def test_untracked_script_that_reads_a_tracked_argument_and_writes_its_own_file_passes(self):
        script = self.tmp / "start_review.py"
        script.write_text((pathlib.Path(__file__).parent / "fixtures/start_review_script.txt").read_text())
        self.assert_allowed(f"python3 {script} code tracked.txt 0 .review-handoff.txt", agent="coder")

    def test_inline_and_heredoc_scripts_are_judged_by_whether_a_write_reaches_the_tracked_argument(self):
        self.assert_denied("python3 -c \"import sys; open(sys.argv[1], 'w')\" tracked.txt")
        self.assert_denied("cat > x.py <<'PY'\nimport sys\nopen(sys.argv[1], 'w')\nPY\npython3 x.py tracked.txt")
        self.assert_allowed("python3 -c \"import sys; open('o.log', 'w'); print(open(sys.argv[1]).read())\" "
                            "tracked.txt", agent="coder")
        self.assert_allowed("cat > x.py <<'PY'\nimport sys\nopen('o.log', 'w')\nopen(sys.argv[1])\nPY\n"
                            "python3 x.py tracked.txt", agent="coder")
        self.assert_allowed("python3 -c \"import os; open(os.path.join('d', 'o.log'), 'w')\" tracked.txt",
                            agent="coder")

    def test_untracked_script_whose_writes_all_name_their_own_files_passes(self):
        scripts = {
            "launcher.py": "import subprocess, sys\nsubprocess.Popen(['claude', '-p', sys.argv[1]], "
                           "stdout=open('l', 'w'))\n",
            "named mode.py": "import sys\nmode = 'w'\nwith open('o.log', mode) as g, open(sys.argv[1]) as f:\n"
                             "    g.write(f.read())\n",
            "read mode.py": "import sys\nopen(sys.argv[1], 'rb')\nopen('o.log', 'w')\n",
            "string names.py": "import sys\nopen('shift-report.md', 'w')\nout = 'argv.log'\nopen(out, 'w')\n"
                               "open(sys.argv[1])\n",
            "after bracket.js": "const fs = require('fs');\n[1].forEach((n) => { fs.writeFileSync('o.log', 'y'); "
                                "fs.readFileSync(process.argv[2]); });\n",
            "quote in comment.py": "import sys\nopen('o.log', 'w')  # it's mine\nopen(sys.argv[1])\n",
            "wc child.py": "import subprocess, sys\nsubprocess.run(['wc', '-l', sys.argv[1]])\nopen('o.log', 'w')\n",
            "f string.py": "import sys\nd = 'logs'\nopen(f'{d}/o.log', 'w')\nopen(sys.argv[1])\n",
            "raw string.py": "import sys\nopen(r'o.log', 'w')\nopen(sys.argv[1])\n",
            "unlink missing ok.py": "import pathlib, sys\nopen(sys.argv[1])\n"
                                    "pathlib.Path('o.log').unlink(missing_ok=True)\n",
            "touch exist ok.py": "import pathlib, sys\nopen(sys.argv[1])\npathlib.Path('o.log').touch(exist_ok=True)\n",
            "rmtree keyword.py": "import shutil, sys\nd = 'logs'\nopen(sys.argv[1])\n"
                                 "shutil.rmtree(d, ignore_errors=True)\n",
            "copytree keyword.py": "import shutil, sys\na = 'x'\nb = 'y'\nopen(sys.argv[1])\n"
                                   "shutil.copytree(a, b, dirs_exist_ok=True)\n",
            "rm option key.js": "const fs = require('fs');\nconst p = 'logs';\nfs.readFileSync(process.argv[2]);\n"
                                "fs.rmSync(p, {recursive: true});\n",
            "replace keyword.py": "import sys\nfrom datetime import datetime\nopen('o.log', 'w')\nopen(sys.argv[1])\n"
                                  "stamp = datetime.now().replace(microsecond=0)\n",
            "conditional path.py": "import sys\nc = True\nopen('a' if c else 'b', 'w')\nopen(sys.argv[1])\n",
            "await unlink.js": "const fs = require('fs');\nfs.readFileSync(process.argv[2]);\nasync function main() {\n"
                               "  await fs.promises.unlink('o.log');\n}\n",
            "unlink in a string.py": "import sys\nopen('o.log', 'w')\nprint('unlink the old output')\n"
                                     "open(sys.argv[1])\n",
            "backtick in a docstring.py": "import sys\nopen('o.log', 'w')\nprint(\"run `rm` by hand\")\n"
                                          "open(sys.argv[1])\n",
            "module imports.js": "import fs from 'node:fs';\nimport * as path from 'path';\n"
                                 "fs.unlinkSync(path.join('d', 'o.log'));\nfs.readFileSync(process.argv[2]);\n",
            "install word.py": "import subprocess, sys\nsubprocess.run(['pip', 'install', '-r', sys.argv[1]])\n"
                               "subprocess.run(['grep', 'tee', sys.argv[1]])\nopen('o.log', 'w')\n",
            "args word in a string.py": "import subprocess, sys\nsubprocess.run(['echo', 'args=cp', sys.argv[1]])\n"
                                        "open('o.log', 'w')\n",
        }
        for name, code in scripts.items():
            with self.subTest(script=name):
                script = self.tmp / name.replace(" ", "_")
                script.write_text(code)
                interpreter = {".py": "python3", ".js": "node"}[script.suffix]
                self.assert_allowed(f"{interpreter} {script} tracked.txt", agent="coder")

    def test_inline_code_with_operator_characters_that_writes_a_tracked_file_is_denied(self):
        commands = (
            "python3 -c \"import pathlib; pathlib.Path('tracked.txt').write_text('y')\"",
            "python3 -c \"x = 1 > 0; open('tracked.txt','w').write('y')\"",
            "node -e \"[1].forEach(() => require('fs').writeFileSync('tracked.txt', 'y'))\"",
            "perl -e 'open(my $f, \">\", \"tracked.txt\")'",
            "python3 -Bc \"open('tracked.txt','w')\"",
            "perl -le 'open(my $f, \">\", \"tracked.txt\")'",
            "node --eval \"require('fs').writeFileSync('tracked.txt', 'y')\"",
            "node -p \"require('fs').writeFileSync('tracked.txt', 'y')\"",
            "python3 -W ignore -c \"open('tracked.txt','w')\"",
            "python3 -c \"import shutil; shutil.copy('untracked.txt', 'tracked.txt')\"",
            "deno eval \"Deno.writeTextFileSync('tracked.txt', 'y')\"",
            "deno eval -p \"Deno.writeTextFileSync('tracked.txt', 'y')\"",
            "bun -e \"Bun.write('tracked.txt', 'y')\"",
            "npx -p tsx tsx -e \"require('fs').writeFileSync('tracked.txt', 'y')\"",
            "npx tsx -e \"require('fs').createWriteStream('tracked.txt')\"",
            "pypy3 -c \"open('tracked.txt','w')\"",
            "node -e \"const s = \\`a #b\\`; fs.writeFileSync('tracked.txt', s)\"",
            "node -e \"const s = 'a'.replace(/ #x/g, ''); fs.writeFileSync('tracked.txt', s)\"",
        )
        for command in commands:
            with self.subTest(command=command):
                self.assert_denied(command)

    def test_coder_inline_code_that_writes_a_tracked_file_is_denied_without_skip_hint(self):
        reason = self.assert_denied("python3 -c \"import pathlib; pathlib.Path('tracked.txt').write_text('y')\"",
                                    agent="coder")
        self.assertIn("This agent has no way to skip this gate.", reason)
        self.assertNotIn(HINT, reason)

    def test_script_after_a_value_flag_is_read_as_the_script(self):
        script = self.tmp / "rewrite.py"
        script.write_text("open('tracked.txt', 'w').write('y')\n")
        self.assert_denied(f"python3 -W ignore {script}")
        self.assert_denied(f"node -r ts-node/register {script}")

    def test_script_after_a_flag_that_takes_no_value_is_checked_as_a_script(self):
        script = self.tmp / "rewrite.py"
        script.write_text("open('tracked.txt', 'w').write('y')\n")
        ruby_script = self.tmp / "rewrite.rb"
        ruby_script.write_text("File.write('tracked.txt', 'y')\n")
        deno_script = self.tmp / "rewrite.ts"
        deno_script.write_text("Deno.writeTextFileSync('tracked.txt', 'y')\n")
        commands = (
            f"python3 -I {script}",
            f"python3 -E {script}",
            f"ruby -E UTF-8 {ruby_script}",
            f"npx -p tsx tsx {deno_script}",
            f"deno run -c cfg.json {deno_script}",
        )
        for command in commands:
            with self.subTest(command=command):
                self.assert_denied(command)

    def test_git_ignored_script_that_writes_a_tracked_file_passes(self):
        (self.repo / ".gitignore").write_text("dist/\n")
        (self.repo / "dist").mkdir()
        (self.repo / "dist" / "server.js").write_text("require('fs').writeFileSync('tracked.txt', 'y')\n")
        self.assert_allowed("node dist/server.js")

    def test_script_that_reads_a_tracked_file_and_prints_a_quoted_arrow_passes(self):
        reader = self.tmp / "read.py"
        reader.write_text("data = open('tracked.txt').read()\nprint(data)\nprint('> quoted')\n")
        self.assert_allowed(f"python3 {reader}")

    def test_interpreter_runs_that_write_no_tracked_file_pass(self):
        script = self.tmp / "rewrite.py"
        script.write_text("import sys\nwith open(sys.argv[1], 'w') as f:\n    f.write('y')\n")
        reader = self.tmp / "read.py"
        reader.write_text("print(open('tracked.txt').read())\n")
        for command in (f"python3 {script} untracked.txt", f"python3 {reader}", "python3 -m json.tool tracked.txt",
                        "python3 -c \"print(open('tracked.txt').read().split('>'))\"",
                        "python3 -c \"print(open('tracked.txt').read(), '>')\""):
            with self.subTest(command=command):
                self.assert_allowed(command)

    def test_tracked_script_that_writes_a_tracked_file_passes(self):
        (self.repo / "build.py").write_text("open('tracked.txt', 'w').write('y')\n")
        subprocess.run(["git", "-C", str(self.repo), "add", "build.py"], check=True)
        self.assert_allowed("python3 build.py")

    def test_main_session_skip_comment_disarms_the_interpreter_check(self):
        script = self.tmp / "rewrite.py"
        script.write_text("open('tracked.txt', 'w').write('y')\n")
        self.assertIn(HINT, self.assert_denied(f"python3 {script}"))
        self.assert_allowed(f"python3 {script} {HINT}")

    def test_a_coder_may_redirect_into_a_new_log_under_var_tmp_but_not_onto_a_tracked_file_there(self):
        log_folder = pathlib.Path(tempfile.mkdtemp(dir="/var/tmp", prefix="shell-write-gate-test-"))
        self.addCleanup(shutil.rmtree, log_folder, ignore_errors=True)
        subprocess.run(["git", "init", "-q", str(log_folder)], check=True)
        (log_folder / "tracked.log").write_text("x\n")
        subprocess.run(["git", "-C", str(log_folder), "add", "tracked.log"], check=True)

        self.assert_allowed(f"cargo clippy > {log_folder}/clippy.log 2>&1", agent="coder")
        reason = self.assert_denied(f"cargo clippy > {log_folder}/tracked.log 2>&1", agent="coder")

        self.assertIn(f"{log_folder}/tracked.log is git-tracked", reason)

    def test_coder_new_file_outside_temp_dir_denied_naming_write(self):
        outside = self.make_outside_dir()
        temp_dir = self.tmp / "tempdir"
        temp_dir.mkdir()
        env = {"TMPDIR": str(temp_dir)}

        def run_in(command, cwd, agent):
            payload = {"tool_input": {"command": command}, "cwd": str(cwd)}
            if agent:
                payload["agent_type"] = agent
            return self.run_hook(json.dumps(payload), env_extra=env)

        for command in ("cat > helper.py <<EOF\nx\nEOF", "echo hi > helper.py", "echo hi | tee helper.py"):
            reason = self.denied(run_in(command, outside, "coder"))
            self.assertIn("Write tool", reason)
            self.assertIn(f"{outside}/helper.py", reason)
            self.assertNotIn(HINT, reason)
            for agent in (None, "reviewer"):
                finished = run_in(command, outside, agent)
                self.assertEqual((finished.returncode, finished.stdout), (0, ""), command)
        for command in (f"echo hi > {temp_dir}/check.log", "echo hi > /tmp/shell-gate-check.log",
                        "echo hi > /dev/null", "ls 2>&1"):
            finished = run_in(command, outside, "coder")
            self.assertEqual((finished.returncode, finished.stdout), (0, ""), command)
        (outside / "existing.txt").write_text("x")
        finished = run_in("echo hi > existing.txt", outside, "coder")
        self.assertEqual((finished.returncode, finished.stdout), (0, ""))


if __name__ == "__main__":
    unittest.main()
