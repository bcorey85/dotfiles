"""Checks for git_discipline_gate.py, the PreToolUse(Bash) hook enforcing four git rules."""
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
                      or toolkit_paths.GATES_DIR) / "git_discipline_gate.py"


class GitDisciplineGateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def repo_on(self, branch, claude_md=None):
        repo = pathlib.Path(tempfile.mkdtemp(dir=str(self.tmp)))
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "symbolic-ref", "HEAD", "refs/heads/" + branch], check=True)
        if claude_md is not None:
            (repo / "CLAUDE.md").write_text(claude_md)
        return repo

    def run_raw(self, stdin, cwd, env_extra=None):
        env = {"PATH": os.environ["PATH"], "HOME": str(self.tmp), "TMPDIR": str(self.tmp)}
        env.update(env_extra or {})
        return subprocess.run([sys.executable, str(SCRIPT)], input=stdin, capture_output=True, text=True,
                              env=env, cwd=str(cwd))

    def run_command(self, command, cwd=None, branch="feature"):
        cwd = cwd or self.repo_on(branch)
        return self.run_raw(json.dumps({"tool_input": {"command": command}}), cwd)

    def reason_of(self, finished):
        self.assertEqual(finished.returncode, 0)
        self.assertEqual(finished.stderr, "")
        decision = json.loads(finished.stdout)["hookSpecificOutput"]
        self.assertEqual(decision["hookEventName"], "PreToolUse")
        self.assertEqual(decision["permissionDecision"], "deny")
        return decision["permissionDecisionReason"]

    def assert_denied(self, command, expected_start, **options):
        reason = self.reason_of(self.run_command(command, **options))
        self.assertTrue(reason.startswith(expected_start), reason)
        return reason

    def assert_allowed(self, command, **options):
        finished = self.run_command(command, **options)
        self.assertEqual((finished.returncode, finished.stdout, finished.stderr), (0, "", ""))

    def test_stash_denied_but_list_and_show_pass(self):
        for command in ("git stash", "git stash pop", "git  stash push -m x", "cd x && git stash", "GIT STASH",
                        "git stash push -u -m tag-1", "git stash apply --index 0123abc", "git stash drop 'stash@{0}'",
                        "git -C ../other stash push -m tag", "git -c core.pager=cat stash pop",
                        "git --no-pager stash apply", "env GIT_DIR=x git stash", "timeout 5 git stash",
                        "echo $(git stash)", "echo \"$(git stash pop)\"", "echo `git stash`",
                        "bash -c 'git stash push'", "eval \"git stash\"", "git \\\n  stash push"):
            with self.subTest(command=command):
                self.assert_denied(command, "[git-discipline-gate] git stash is blocked in every form")
        for command in ("git stash list", "git stash show -p", "git stash  list", "git -C x stash list"):
            self.assert_allowed(command)

    def test_stash_message_is_exact(self):
        reason = self.assert_denied("git stash", "[git-discipline-gate]")
        self.assertEqual(reason, "[git-discipline-gate] git stash is blocked in every form, a tagged `git stash "
                                 "push -m <tag>` included: every worktree shares one stash stack, and a stash "
                                 "resets staged files. Set work aside with a temporary WIP commit on your branch. "
                                 "If stashing is genuinely needed, ask the user — they can run it themselves.")

    def test_git_words_inside_text_pass(self):
        for command in ("python3 queue.py new <<'EOF'\nThe agent ran git stash push and git pull --autostash.\nEOF",
                        "python3 queue.py new <<EOF\nthen git stash pop and git commit --amend\nEOF",
                        "echo 'git stash pop'", "rg -n \"git stash\" docs", "echo x # git stash",
                        "printf '%s' 'git pull --autostash'"):
            with self.subTest(command=command):
                self.assert_allowed(command)

    def test_autostash_on_pull_rebase_and_merge_denied(self):
        for command in ("git pull --rebase --autostash", "git rebase --autostash origin/master",
                        "git merge --autostash topic", "git -C repo pull --autostash",
                        "git pull --no-autostash --autostash", "git -c rebase.autoStash=true pull --rebase",
                        "git -c merge.autostash=yes merge topic", "git config rebase.autoStash true",
                        "git config --global merge.autoStash on", "bash -c 'git pull --autostash'"):
            with self.subTest(command=command):
                reason = self.assert_denied(command, "[git-discipline-gate] git autostash is blocked")
        self.assertEqual(reason, "[git-discipline-gate] git autostash is blocked: it runs a git stash, which every "
                                 "worktree shares and which resets staged files. Commit or set your work aside with a "
                                 "temporary WIP commit first, or pass --no-autostash.")
        for command in ("git pull --rebase", "git pull --rebase --no-autostash",
                        "git rebase --autostash --no-autostash",
                        "git -c rebase.autoStash=false pull --rebase", "git config --get rebase.autoStash",
                        "git config rebase.autoStash false"):
            with self.subTest(command=command):
                self.assert_allowed(command)

    def test_amend_denied(self):
        for command in ("git commit --amend", "git commit -m x --amend --no-edit", "git commit --amend -m x"):
            reason = self.assert_denied(command, "[git-discipline-gate] git commit --amend is blocked")
        self.assertEqual(reason, "[git-discipline-gate] git commit --amend is blocked: never rewrite history "
                                 "unless the user explicitly asked. Make a new commit, or ask the user.")
        self.assert_allowed("git commit -m 'fix --amended'")
        self.assert_allowed("git commit -m x--amend")

    def test_attribution_trailers_denied_in_commits_and_prs(self):
        for command in ("git commit -m 'x\n\nClaude-Session: https://claude.ai/code/session_01'",
                        "git commit -m 'see https://claude.ai/code/session_abc'",
                        "git commit -m 'x\n\nCo-Authored-By: Claude <n@a.com>'",
                        "git commit -m 'co-authored-by:Claude'",
                        "gh pr create --body 'https://claude.ai/code/session_xyz'",
                        "gh pr edit 3 --body 'Claude-Session: z'"):
            reason = self.assert_denied(command, "[git-discipline-gate] Commit and PR text must carry no "
                                                 "attribution or session trailer.")
        self.assertEqual(reason, "[git-discipline-gate] Commit and PR text must carry no attribution or session "
                                 "trailer. Remove it and retry.")
        self.assert_allowed("echo 'Claude-Session: x'")
        self.assert_allowed("git commit -m 'Co-Authored-By: Someone Else'")

    def test_worktree_branch_blocks_commit_and_push(self):
        for command in ("git commit -m x", "git push -u origin HEAD", "git  push"):
            reason = self.assert_denied(command, "[git-discipline-gate] branch 'worktree-abc' still carries",
                                        branch="worktree-abc")
        self.assertEqual(reason, "[git-discipline-gate] branch 'worktree-abc' still carries the auto-generated "
                                 "worktree- prefix. Rename it to the plain TICKET-NUM-desc form and push it with "
                                 "-u first, then retry.")
        self.assert_allowed("git status", branch="worktree-abc")
        self.assert_allowed("git push", branch="feature")

    def test_worktree_rule_ignores_direct_edit_exemption(self):
        repo = self.repo_on("worktree-q", claude_md="This is a direct-edit repo.\n")
        self.assert_denied("git commit -m x", "[git-discipline-gate] branch 'worktree-q'", cwd=repo)

    def test_commit_on_main_or_master_denied(self):
        for branch in ("main", "master"):
            reason = self.assert_denied(
                "git commit -m x", f"[git-discipline-gate] git commit on {branch} is blocked", branch=branch
            )
        self.assertEqual(reason, "[git-discipline-gate] git commit on master is blocked: create a feature branch "
                                 "first (global rule). If committing here is genuinely intended, the user can run "
                                 "it themselves.")

    def test_push_and_other_git_on_main_pass(self):
        self.assert_allowed("git push", branch="main")
        self.assert_allowed("git status", branch="main")
        self.assert_allowed("git commit -m x", branch="feature/main")

    def test_direct_edit_repo_is_exempt_case_insensitively(self):
        for text in ("this is a Direct-Edit Repo\n", "intro\ndirect-edit repo (dotfiles)\n"):
            self.assert_allowed("git commit -m x", cwd=self.repo_on("main", claude_md=text))
        self.assert_denied("git commit -m x", "[git-discipline-gate] git commit on main",
                           cwd=self.repo_on("main", claude_md="some other repo\n"))

    def test_outside_a_repo_nothing_is_blocked_except_text_rules(self):
        plain = pathlib.Path(tempfile.mkdtemp(dir=str(self.tmp)))
        self.assert_allowed("git commit -m x", cwd=plain)
        self.assert_denied("git stash", "[git-discipline-gate] git stash", cwd=plain)

    def test_detached_head_is_not_a_branch(self):
        repo = self.repo_on("feature")
        (repo / ".git" / "HEAD").write_text("0123456789012345678901234567890123456789\n")
        self.assert_allowed("git commit -m x", cwd=repo)

    def test_non_git_and_empty_commands_pass(self):
        for command in ("", "ls -la", "echo stash", "git stashed", "git status"):
            self.assert_allowed(command)

    def test_skip_hooks_env_passes(self):
        finished = self.run_raw(json.dumps({"tool_input": {"command": "git stash"}}), self.repo_on("main"),
                                env_extra={"CLAUDE_SKIP_HOOKS": "1"})
        self.assertEqual((finished.returncode, finished.stdout), (0, ""))

    def test_unparseable_input_fails_closed(self):
        for stdin in ("not json", json.dumps({"tool_input": "git stash"}), json.dumps(["x"])):
            reason = self.reason_of(self.run_raw(stdin, self.tmp))
            self.assertEqual(reason, "[git-discipline-gate] hook input did not parse — failing closed. "
                                     "Report this to the user.")

    def test_empty_stdin_or_missing_command_passes(self):
        for stdin in ("", json.dumps({}), json.dumps({"tool_input": {}}), json.dumps({"tool_input": None})):
            finished = self.run_raw(stdin, self.tmp)
            self.assertEqual((finished.returncode, finished.stdout), (0, ""))


if __name__ == "__main__":
    unittest.main()
