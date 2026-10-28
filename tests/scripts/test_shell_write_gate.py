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

    def test_a_coder_new_file_rule_is_skipped_for_a_relative_target_after_a_directory_change(self):
        outside = self.make_outside_dir()
        for command in ("cd sub && echo x > new.py", "pushd sub && echo x > new.py", "popd; echo x > new.py",
                        "if true; then cd sub; fi; echo x > new.py", "echo $(cd sub; echo x > new.py)",
                        "command cd sub && echo x | tee new.py", "cd 'unterminated; echo x > new.py"):
            self.assert_allowed(command, agent="coder", cwd=str(outside))
        for command in ("echo x > new.py", "echo cd sub; echo x > new.py", "echo 'cd sub' > new.py",
                        "cd sub && echo x > /srv/not-a-temp-dir/new.py", "cd sub && echo x > $UNSET_DIR/new.py"):
            self.assert_denied(command, agent="coder", cwd=str(outside))

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

    def test_coder_in_the_main_session_cannot_use_the_skip_comment(self):
        reason = self.assert_denied("echo hi > tracked.txt " + HINT, agent="coder")
        self.assertIn("Write tool", reason)
        self.assert_allowed("echo hi > tracked.txt " + HINT, agent="reviewer")

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

    def test_a_heredoc_marker_in_a_comment_does_not_hide_the_next_line(self):
        reason = self.assert_denied("echo hi # <<X\necho x > tracked.txt")
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

    def test_a_heredoc_delimiter_is_the_whole_shell_word(self):
        self.make_tracked_scope_files()
        self.assert_denied("cat <<EOF-X > /dev/null\nx\nEOF-X\necho hi > tests/run.sh")

    def test_a_quoted_marker_on_a_multi_line_string_opens_no_heredoc(self):
        self.make_tracked_scope_files()
        self.assert_denied("echo 'a\ncat <<EOF\nb'\necho hi > tests/run.sh")

    def test_an_arithmetic_shift_with_spaces_opens_no_heredoc(self):
        self.make_tracked_scope_files()
        self.assert_denied("(( v = 1 << x ))\necho hi > tests/run.sh")

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

    def test_subagent_in_place_and_tracked_redirects_denied_as_in_main_session(self):
        for agent_fields in ({"agent_id": "a1"}, {"agent_type": "reviewer"}):
            for command in ("sed -i s/a/b/ untracked.txt", "perl -pi -e s/a/b/ f", "cat >> tracked.txt <<EOF\nx\nEOF",
                            "echo hi > tracked.txt", "echo hi | tee -a tracked.txt"):
                payload = {"tool_input": {"command": command}, "cwd": str(self.repo), **agent_fields}
                self.denied(self.run_hook(json.dumps(payload)))
                self.assert_denied(command)

    def test_main_session_still_gets_skip_comment_in_deny_text(self):
        self.assertIn(HINT, self.assert_denied("sed -i s/a/b/ f"))

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

    def test_untracked_script_given_a_tracked_file_as_argument_is_denied(self):
        script = self.tmp / "rewrite.py"
        script.write_text("import sys\nwith open(sys.argv[1], 'w') as f:\n    f.write('y')\n")
        self.assert_denied(f"python3 {script} tracked.txt")

    def test_inline_code_that_writes_a_tracked_file_is_denied(self):
        self.assert_denied("node -e \"require('fs').writeFileSync('tracked.txt', 'y')\"")

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
