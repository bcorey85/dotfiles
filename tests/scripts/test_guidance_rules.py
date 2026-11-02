"""Checks that each prose rule a toolkit fix added is still in the guidance file the affected agents load."""
import unittest

import toolkit_paths


def guidance_text(relative_path):
    return " ".join((toolkit_paths.CLAUDE_DIR / relative_path).read_text().split())


def repo_doc_text(relative_path):
    repo_root = toolkit_paths.TREE_CLAUDE_DIR.parents[1]
    return " ".join((repo_root / "docs" / relative_path).read_text().split())


class GuidanceRulesTest(unittest.TestCase):
    def test_the_main_session_and_the_coder_loop_over_arrays_in_a_form_zsh_and_bash_both_split(self):
        for relative_path in ("orchestration.md", "skills/coder-core/SKILL.md"):
            with self.subTest(path=relative_path):
                text = guidance_text(relative_path)
                self.assertIn("zsh", text)
                self.assertIn('files=(a b); for f in "${files[@]}"', text)

    def test_a_child_session_in_list_agents_is_not_taken_for_a_rival_worker(self):
        text = guidance_text("orchestration.md")
        self.assertIn("A ListAgents peer named `child of <name>` is a headless step of that session's run, not a "
                      "rival worker", text)

    def test_the_code_fork_acts_on_feedback_the_user_already_gave_on_a_stop(self):
        text = guidance_text("agents/code-fork.md")
        self.assertIn("When the user already gave feedback on the run's last stop in this conversation, apply it and "
                      "never raise that stop again.", text)

    def test_code_stops_end_as_statements_asks_are_decided_and_main_relays_with_no_tool_call(self):
        text = guidance_text("skills/code/SKILL.md")
        self.assertIn("A stop states what stopped and what the user does next; it never ends on a question.", text)
        self.assertIn("Decide each `ask[]` entry yourself; never stop on one.", text)
        self.assertIn("ask_decided_by=session", text)
        self.assertIn("finding_id=<entry finding_id>", text)
        self.assertIn("When two paths are both defensible, take the one closer to the plan and name it in the report.",
                      text)
        self.assertNotIn("or when two paths are both defensible", text)
        self.assertIn("say the fork's stop word for word and make no other tool call", text)
        self.assertNotIn("confirm here", text)
        self.assertNotIn("present it as a STOP", text)
        self.assertIn("Before a step that cannot be undone or that leaves this machine, STOP: name the step and say "
                      "that `/code resume` runs it.", text)
        self.assertNotIn("Ask only before", text)

    def test_a_code_resume_finds_its_plan_and_an_unresolved_task_writes_no_stop_file(self):
        text = guidance_text("skills/code/SKILL.md")
        self.assertIn("`To go on: /code resume <plan path> <your feedback>`, with the plan's absolute path", text)
        self.assertIn("an absolute path right after it names the plan, and that plan's git repo is the repo root", text)
        self.assertIn("run the stop's `To go on:` line with their reply", text)
        self.assertEqual(text.count("no run started, so write no stop file"), 2)
        self.assertNotIn("Exit 4 → STOP", text)

    def test_the_main_session_is_told_to_send_simple_commands_after_enter_worktree(self):
        text = guidance_text("orchestration.md")
        self.assertIn("After `EnterWorktree`, Claude Code's own worktree guard refuses", text)
        self.assertIn("one simple command per call with literal paths", text)

    def test_the_test_intent_reviewer_names_no_shape_list_it_never_gives(self):
        text = guidance_text("agents/test-intent-reviewer.md")
        self.assertNotIn("one of the six", text)
        self.assertNotIn("shape pass", text)
        self.assertIn("the assertion (or `absent` when no assertion holds the promise), the wrong value it accepts", text)

    def test_a_main_push_line_waits_for_the_branch_s_verify_branch_and_non_negotiables_results(self):
        text = guidance_text("orchestration.md")
        self.assertIn("only after the branch reports `/verify-branch` done and, where the repo's CLAUDE.md names a "
                      "non-negotiables check, that check passed", text)
        self.assertIn("A green gate or CI run alone never produces that line.", text)

    def test_the_orchestrator_never_answers_a_question_put_to_the_user_in_another_session_s_pane(self):
        text = guidance_text("orchestration.md")
        self.assertIn("Never submit text in another session's input box to answer a question put to the user", text)
        self.assertIn("tell the user to answer in that pane", text)

    def test_a_coder_runs_a_changed_test_file_through_the_sharding_runner(self):
        text = repo_doc_text("toolkit-script-rules.md")
        self.assertIn("Run a changed test file through `python3 tests/parallel_tests.py <test file name>`", text)

    def test_a_cancelled_spec_deletes_its_questions_file_and_research_writes_nothing_without_it(self):
        phase_text = guidance_text("skills/eng-spec/phases/2-research.md")
        self.assertIn("delete only `<task-dir>/01-questions.md` with a plain `rm <path>` (no flags)", phase_text)
        research_text = guidance_text("agents/spec-research.md")
        self.assertIn("If it is gone, the spec was cancelled: write nothing", research_text)

    def test_the_test_reviewer_never_mutates_the_shared_tree(self):
        text = guidance_text("agents/test-reviewer.md")
        self.assertIn("Never change a file in the tree, not even to mutate it and restore it", text)

    def test_spec_criteria_numbers_ids_flat_and_runs_plan_check_before_it_returns(self):
        text = guidance_text("agents/spec-criteria.md")
        raw_text = (toolkit_paths.CLAUDE_DIR / "agents/spec-criteria.md").read_text()
        tools_line = next(line for line in raw_text.splitlines() if line.startswith("tools:"))
        self.assertIn("Bash", [tool.strip() for tool in tools_line.removeprefix("tools:").split(",")])
        self.assertIn("never a lettered sub-id such as `AC1a`", text)
        self.assertIn("plan_check.py check", text)
        self.assertIn("return those rows unedited", text)
        self.assertIn("Never edit `spec.md`", text)

    def test_eng_spec_runs_the_final_plan_check_before_it_reports_the_plan_saved(self):
        text = guidance_text("skills/eng-spec/phases/7-handoff.md")
        self.assertIn("plan_check.py check --final ", text)
        self.assertIn("Exit 1 is an unresolved planning gate", text)

    def test_branch_recap_lists_companion_branches_that_have_no_pr(self):
        text = guidance_text("skills/branch-recap/SKILL.md")
        self.assertIn("## Step 2b: Companion branches", text)
        self.assertIn("gh pr list --repo <owner/name> --head <branch> --state all", text)
        self.assertIn("### Companion branches", text)
        self.assertIn("git ls-remote --heads <remote-url> <branch>", text)
        self.assertIn("— not pushed", text)

    def test_review_loop_never_hands_back_an_ask_with_an_empty_question(self):
        text = guidance_text("agents/review-loop.md")
        self.assertIn("question is never empty: an ask with no question takes its finding, or else its change, "
                      "as its question", text)

    def test_review_loop_writes_each_logger_call_with_literal_arguments(self):
        text = guidance_text("agents/review-loop.md")
        self.assertIn("Write each call out with literal key=value arguments, one call per row", text)
        self.assertIn("never build the arguments by splitting a string in a loop", text)

    def test_sign_offs_stay_in_the_decision_log_and_out_of_code(self):
        text = guidance_text("CLAUDE.md")
        self.assertIn("Record each sign-off with who and when, only in the plan's decision log", text)
        self.assertIn("never in code, comments, fixtures or commit messages", text)

        coder_text = guidance_text("skills/coder-core/SKILL.md")
        self.assertIn("the user's name, and sign-offs (who and when) are banned", coder_text)

    def test_frontend_style_calls_a_braceless_block_a_lint_error_only_where_eslint_enables_curly(self):
        text = guidance_text("rules/frontend-style.md")
        self.assertIn("eslint config enables `curly`", text)
        self.assertNotIn("will break CI", text)


if __name__ == "__main__":
    unittest.main()
