"""Checks for staged_claim_gate.py, the Stop and SubagentStop hook that blocks a final message saying files are
staged when the index does not hold them."""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

import toolkit_paths

SCRIPT = toolkit_paths.GATES_DIR / "staged_claim_gate.py"


def git(repo, *arguments):
    subprocess.run(["git", "-C", str(repo), *arguments], check=True, capture_output=True)


class StagedClaimGateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.repo = self.make_repo("repo")
        self.outside = self.tmp / "outside"
        self.outside.mkdir()

    def make_repo(self, name):
        repo = self.tmp / name
        repo.mkdir()
        git(repo, "init", "-q")
        git(repo, "config", "user.email", "t@example.com")
        git(repo, "config", "user.name", "t")
        for file_name in ("a.txt", "b.txt"):
            (repo / file_name).write_text("x\n")
        git(repo, "add", "a.txt", "b.txt")
        git(repo, "commit", "-qm", "start")
        for file_name in ("a.txt", "b.txt"):
            (repo / file_name).write_text("y\n")
        return repo

    def run_gate(self, message, cwd=None, event="Stop", stop_hook_active=False, transcript_path=None, home=None):
        payload = {"hook_event_name": event, "cwd": str(cwd or self.repo), "last_assistant_message": message,
                   "stop_hook_active": stop_hook_active, "transcript_path": str(transcript_path or "")}
        environment = dict(os.environ, HOME=str(home)) if home else None
        finished = subprocess.run([sys.executable, str(SCRIPT)], input=json.dumps(payload), capture_output=True,
                                  text=True, cwd=str(self.tmp), env=environment)
        self.assertEqual((finished.returncode, finished.stderr), (0, ""))
        return finished.stdout

    def assert_blocked(self, message, **options):
        decision = json.loads(self.run_gate(message, **options))
        self.assertEqual(decision["decision"], "block")
        self.assertIn("git diff --cached --name-only", decision["reason"])
        return decision["reason"]

    def assert_passes(self, message, **options):
        self.assertEqual(self.run_gate(message, **options), "")

    def test_a_staged_claim_with_an_empty_index_is_blocked(self):
        for message in ("Done. The files are staged for you to commit.", "I staged the change.",
                        "All three edits are now staged."):
            with self.subTest(message=message):
                reason = self.assert_blocked(message)
                self.assertIn(str(self.repo), reason)
                self.assertIn("nothing", reason)

    def test_a_subagent_hand_back_is_checked_too(self):
        self.assert_blocked("Fix applied; the files are staged.", event="SubagentStop")

    def test_a_staged_claim_with_files_in_the_index_passes(self):
        git(self.repo, "add", "a.txt")
        self.assert_passes("The change is staged.")
        self.assert_passes("a.txt is staged.")

    def test_a_named_file_missing_from_the_index_is_blocked_by_name(self):
        git(self.repo, "add", "a.txt")
        reason = self.assert_blocked("a.txt and b.txt are staged.")
        self.assertIn("b.txt", reason)
        self.assertNotIn("a.txt", reason.replace(str(self.repo), ""))

    def test_a_claim_naming_another_repo_checks_that_repo(self):
        other = self.make_repo("other")
        self.assert_blocked(f"{other}/a.txt is staged.", cwd=self.outside)
        git(other, "add", "a.txt")
        self.assert_passes(f"{other}/a.txt is staged.", cwd=self.outside)

    def test_a_claim_naming_another_tree_by_folder_git_dash_c_or_home_checks_that_tree_index(self):
        other = self.make_repo("other")
        messages = (f"a.txt is staged in {other}.", f"`git -C {other} diff --cached` shows a.txt is staged.",
                    "`git -C ../other diff --cached` shows a.txt is staged.", "a.txt is staged in ~/other.",
                    "`git -C ~/other diff --cached` shows a.txt is staged.")
        for message in messages:
            with self.subTest(message=message):
                self.assert_blocked(message, home=self.tmp)

                git(other, "add", "b.txt")
                reason = self.assert_blocked(message, home=self.tmp)
                self.assertIn(f"the index of {other.resolve()} does not hold a.txt", reason)

                git(other, "add", "a.txt")
                self.assert_passes(message, home=self.tmp)
                git(other, "reset", "-q")

    def test_a_claim_naming_no_repo_checks_the_cwd_index_beside_another_staged_tree(self):
        other = self.make_repo("other")
        git(other, "add", "a.txt")
        messages = ("a.txt is staged in ~/missing.", "`git -C ~/outside diff --cached` shows a.txt is staged.")
        for message in messages:
            with self.subTest(message=message):
                reason = self.assert_blocked(message, home=self.tmp)
                self.assertIn(f"the index of {self.repo.resolve()}", reason)

                git(self.repo, "add", "a.txt")
                self.assert_passes(message, home=self.tmp)
                git(self.repo, "reset", "-q")

    def test_a_claim_naming_a_tree_is_not_vouched_for_by_a_third_tree_from_the_transcript(self):
        other = self.make_repo("other")
        linked = self.stage_in_linked_tree("a.txt")
        transcript = self.write_transcript(f"git -C {linked} add a.txt")
        messages = ("`git -C ../other diff --cached` shows a.txt is staged.", "a.txt is staged in ~/other.")
        for message in messages:
            with self.subTest(message=message):
                reason = self.assert_blocked(message, home=self.tmp, transcript_path=transcript)
                self.assertIn(f"the index of {other.resolve()} holds nothing", reason)

    def test_a_git_dash_c_folder_the_hook_cannot_read_names_no_tree_so_the_transcript_still_vouches(self):
        linked = self.stage_in_linked_tree("a.txt")
        transcript = self.write_transcript(f"git -C {linked} add a.txt")
        self.assert_passes("`git -C $WT diff --cached` shows a.txt is staged.", transcript_path=transcript)

    def write_transcript(self, *commands, name="transcript.jsonl"):
        transcript = self.tmp / name
        entries = [{"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "tool_use", "name": "Bash", "input": {"command": command}}]}} for command in commands]
        transcript.write_text("".join(json.dumps(entry) + "\n" for entry in entries))
        return transcript

    def stage_in_linked_tree(self, file_name):
        linked = self.tmp / "linked"
        git(self.repo, "worktree", "add", "-q", "-b", "side", str(linked))
        (linked / file_name).parent.mkdir(exist_ok=True)
        (linked / file_name).write_text("z\n")
        git(linked, "add", file_name)
        return linked

    def test_a_claim_passes_only_when_a_worktree_the_session_staged_in_holds_staged_files(self):
        linked = self.stage_in_linked_tree("a.txt")
        transcript_without_staging = self.write_transcript("git status", name="without-staging.jsonl")
        self.assert_blocked("The files are staged.", transcript_path=transcript_without_staging)

        for command in (f"git -C {linked} add a.txt", f"cd {linked} && git add a.txt", "cd ../linked && git add a.txt"):
            with self.subTest(command=command):
                git(linked, "add", "a.txt")
                transcript = self.write_transcript("git status", command)
                self.assert_passes("The files are staged.", transcript_path=transcript)
                self.assert_blocked(f"{self.repo}/a.txt is staged.", transcript_path=transcript)

                git(linked, "reset", "-q", "a.txt")
                self.assert_blocked("The files are staged.", transcript_path=transcript)

    def test_a_linked_tree_with_staged_files_but_no_staging_command_does_not_vouch_for_the_claim(self):
        linked = self.stage_in_linked_tree("a.txt")
        transcript = self.write_transcript(f"git -C {linked} status", f"git -C {linked} diff --cached")
        self.assert_blocked("The files are staged.", transcript_path=transcript)

    def test_a_later_command_in_the_transcript_does_not_hide_the_staging_in_the_linked_tree(self):
        linked = self.stage_in_linked_tree("a.txt")
        transcript = self.write_transcript(f"git -C {linked} add a.txt", "git status")
        self.assert_passes("The files are staged.", transcript_path=transcript)

    def test_a_linked_tree_staging_other_files_does_not_vouch_for_a_named_file(self):
        linked = self.stage_in_linked_tree("b.txt")
        transcript = self.write_transcript(f"git -C {linked} add b.txt")
        self.assert_blocked("a.txt is staged.", transcript_path=transcript)
        self.assert_passes("b.txt is staged.", transcript_path=transcript)
        self.assert_blocked("a.txt and b.txt are staged.", transcript_path=transcript)

    def test_a_file_present_but_unstaged_in_the_linked_tree_is_blocked(self):
        linked = self.stage_in_linked_tree("a.txt")
        (linked / "queue").mkdir()
        (linked / "queue" / "x.md").write_text("z\n")
        transcript = self.write_transcript(f"git -C {linked} add a.txt")
        self.assert_blocked("queue/x.md is staged.", transcript_path=transcript)

    def test_a_file_missing_from_the_cwd_index_is_blocked_beside_a_staging_linked_tree(self):
        linked = self.stage_in_linked_tree("b.txt")
        transcript = self.write_transcript(f"git -C {linked} add b.txt")
        git(self.repo, "add", "a.txt")
        reason = self.assert_blocked("b.txt is staged.", transcript_path=transcript)
        self.assertIn("b.txt", reason)

    def test_an_untracked_file_in_the_cwd_checkout_blocks_a_claim_the_linked_tree_cannot_vouch_for(self):
        linked = self.stage_in_linked_tree("a.txt")
        (self.repo / "c.txt").write_text("x\n")
        transcript = self.write_transcript(f"git -C {linked} add a.txt")
        self.assert_blocked("c.txt is staged.", transcript_path=transcript)

    def test_a_file_named_relative_to_a_subdirectory_cwd_is_vouched_for_by_the_linked_tree(self):
        linked = self.stage_in_linked_tree("sub/c.txt")
        (self.repo / "sub").mkdir()
        (self.repo / "sub" / "c.txt").write_text("x\n")
        transcript = self.write_transcript(f"git -C {linked} add sub/c.txt")
        self.assert_passes("c.txt is staged.", cwd=self.repo / "sub", transcript_path=transcript)

    def test_a_file_staged_outside_the_subdirectory_cwd_is_not_vouched_for_by_the_linked_tree(self):
        linked = self.stage_in_linked_tree("c.txt")
        (self.repo / "sub").mkdir()
        (self.repo / "sub" / "c.txt").write_text("x\n")
        transcript = self.write_transcript(f"git -C {linked} add c.txt")
        self.assert_blocked("c.txt is staged.", cwd=self.repo / "sub", transcript_path=transcript)

    def test_a_reply_describing_what_the_hook_reads_passes_with_an_empty_index(self):
        for message in ("The hook blocks a reply that says files are staged.",
                        "The bug: a message saying all files are staged gets blocked.",
                        "The gate fired on a sentence claiming the edits are staged.",
                        "The linter says the config I changed is staged.",
                        "The worker said the files I touched are staged."):
            with self.subTest(message=message):
                self.assert_passes(message)

    def test_a_quoted_claim_with_its_own_closing_mark_or_a_path_passes(self):
        for message in ('A reply like "The files are staged." is wrong.', "Cite `I staged the fix.` here.",
                        'The gate blocks "I staged it!" when the index is empty.',
                        'The old reply read "All files are staged." and was wrong.',
                        "The note cites `notes.md is staged` as an example.",
                        'Use the phrase "the fix in docs/x.md is staged" in the test.',
                        "The gate flags `Files are staged!` lines.",
                        'Cite "Are the files staged?" as the example.'):
            with self.subTest(message=message):
                self.assert_passes(message)

    def test_a_claim_beside_a_reporting_word_still_blocks(self):
        for message in ("The staged-claim gate files are staged.",
                        "The tests passed as the plan said, and all files are staged.", "I said I staged the fix.",
                        "I said all files are staged.", "I have said the files are staged."):
            with self.subTest(message=message):
                self.assert_blocked(message)

    def test_a_torn_transcript_line_does_not_hide_a_false_claim_or_a_true_one(self):
        torn_line = '{"type": "assistant", "message": {"content": [{"type": "tool_use", "na\n'
        transcript = self.write_transcript("git status")
        with transcript.open("a") as torn:
            torn.write(torn_line)
        self.assert_blocked("The files are staged.", transcript_path=transcript)

        linked = self.stage_in_linked_tree("a.txt")
        valid_line = self.write_transcript(f"git -C {linked} add a.txt", name="valid.jsonl").read_text()
        for name, text in (("torn-before.jsonl", torn_line + valid_line), ("torn-after.jsonl", valid_line + torn_line)):
            with self.subTest(name=name):
                torn_transcript = self.tmp / name
                torn_transcript.write_text(text)
                self.assert_passes("The files are staged.", transcript_path=torn_transcript)

    def test_a_torn_multibyte_character_at_the_end_of_the_transcript_still_blocks(self):
        transcript = self.write_transcript("git status")
        with transcript.open("ab") as torn:
            torn.write(b'{"text": "caf\xc3')
        self.assert_blocked("The files are staged.", transcript_path=transcript)

    def test_a_missing_transcript_file_still_blocks_an_empty_index_claim(self):
        self.assert_blocked("The files are staged.", transcript_path=self.tmp / "missing.jsonl")

    def test_messages_without_a_staged_claim_pass(self):
        for message in ("Nothing is staged yet.", "The files are not staged.", "Stage a.txt when you are ready.",
                        "No files are staged.", "The unstaged edits stay in the tree.",
                        "The files were staged and committed as abc123.", ""):
            with self.subTest(message=message):
                self.assert_passes(message)

    def test_conditional_sentences_pass_with_an_empty_index(self):
        for message in ("Once the files are staged, run the commit line.", "After everything is staged, commit."):
            with self.subTest(message=message):
                self.assert_passes(message)

    def test_a_whether_clause_describes_staging_and_passes_with_an_empty_index(self):
        for message in ("The fingerprint will hash a new file the same way whether it is staged or untracked.",
                        "Whether the file is staged or not, the hash stays the same."):
            with self.subTest(message=message):
                self.assert_passes(message)

    def test_a_whether_in_an_earlier_clause_does_not_hide_the_claim(self):
        self.assert_blocked("I checked whether the hash moved, and all files are staged.")

    def test_a_conditional_word_after_the_claim_does_not_hide_it(self):
        for message in ("All four files are staged, so review the diff before you commit.",
                        "The edits are staged; commit when ready.", "I staged the fix after the tests passed."):
            with self.subTest(message=message):
                self.assert_blocked(message)

    def test_a_conditional_word_in_an_earlier_clause_does_not_hide_the_claim(self):
        for message in ("Once the tests passed, I staged the fix.",
                        "After the review I fixed two lines and all files are staged."):
            with self.subTest(message=message):
                self.assert_blocked(message)

    def test_staged_review_data_passes_with_an_empty_index(self):
        for message in ("The fix diffs are staged under fix-diffs.", "Two rows are staged for the ledger.",
                        "The diffs I staged are under fix-diffs.", "The two rows I staged are in the ledger.",
                        "The rows I've staged wait in the ledger."):
            with self.subTest(message=message):
                self.assert_passes(message)

    def test_review_data_in_the_git_index_and_plain_files_still_block(self):
        for message in ("The diffs are staged in the git index.", "All files are staged.",
                        "Two rows are staged, and all files are staged.",
                        "The rows are staged. All files are staged.",
                        "The diff of the file is staged.", "The file for each finding is staged."):
            with self.subTest(message=message):
                self.assert_blocked(message)

    def test_a_description_of_staging_behavior_passes_with_an_empty_index(self):
        for message in ("The script keeps your work: files you staged stay staged.",
                        "Files the user staged remain staged after the commit.",
                        "A staged file stays staged.", "`staged` files stay staged.",
                        "The gate quotes the rule \"all files are staged\" in its reason.",
                        "It printed `the files are staged` and went on.",
                        "“all files are staged” is the rule text."):
            with self.subTest(message=message):
                self.assert_passes(message)

    def test_a_report_of_another_sessions_work_passes_with_an_empty_index(self):
        for message in ("Another session's two files are staged.", "The coordinator's files are staged.",
                        "The coordinator\N{RIGHT SINGLE QUOTATION MARK}s files are staged.",
                        "The workers' files are staged.", "The worker left staged a list of pages.",
                        "The other session's files are staged.", "The other agent's files are staged.",
                        "Another peer's fix was staged.", "The peer's files are staged.",
                        "Another worker's files are staged."):
            with self.subTest(message=message):
                self.assert_passes(message)

    def test_a_claim_by_this_session_still_blocks_beside_a_description(self):
        for message in ("I staged the two files you edited.", "The files you edited are staged.",
                        "The script is staged.", "`a.txt` is staged.",
                        "Files you staged stay staged, and the new tests are staged.",
                        "Another session finished, and all files are staged.",
                        "`a.txt` is staged and `b.txt` is ready.",
                        "Edited `a.txt`; the files are staged; see `b.txt`.",
                        "The files stay staged.", "a.txt remains staged.", "The fix stays staged.",
                        "The worker's fix I staged.", "The coordinator's files I've staged.",
                        "Files from another session I staged.",
                        "I left staged the two files.", "The fix was left staged.",
                        "The files left staged are a.txt and b.txt.",
                        "The fix for the coordinator's queue is staged.",
                        "The note on the worker's queue is staged.",
                        'A 3" gap.\nAll files are staged.\nSee "x".',
                        'Edited `a.txt\nAll files are staged.\nSee `b.txt`.',
                        "The “draft\nAll files are staged.\nSee the ”end”.",
                        "The worker fix was left staged.", "The note from the peer left staged a.txt."):
            with self.subTest(message=message):
                self.assert_blocked(message)

    def test_a_hyphenated_name_or_a_bare_actor_word_does_not_exempt_a_claim(self):
        for message in ("`docs/staged-claim.md` is staged.",
                        "`/srv/dotfiles-staged-claim-gate/a.txt` is staged.",
                        "The staged-claim gate fix is staged.", "docs/staged-claim.md is staged.",
                        "/srv/dotfiles-staged-claim-gate/a.txt is staged.",
                        "src/workers/q.py is staged.", "`src/workers/q.py` is staged.",
                        "The worker pool fix is staged.", "The peer review fixes are staged.",
                        "I told the coordinator the files are staged.", "I told the worker I staged the fix.",
                        "`docs/staged-claim.md` stays staged.", "The staged-claim gate fix stays staged.",
                        "/srv/dotfiles-staged-claim-gate/a.txt remains staged.", "staged.md stays staged.",
                        "The staged_list stays staged.", "The unstaged list stays staged.",
                        "src/staged stays staged.", "The pre-staged list stays staged.",
                        "staged/a.txt stays staged."):
            with self.subTest(message=message):
                self.assert_blocked(message)

    def test_an_actor_named_only_as_an_object_or_a_path_does_not_exempt_a_claim(self):
        for message in ("The fix to the worker is staged.", "The fix for the coordinator is staged.",
                        "src/coordinator is staged.", "claude/.claude/agents/worker is staged.",
                        "The note from the peer is staged.", "The worker is staged.",
                        "The coordinator is staged."):
            with self.subTest(message=message):
                self.assert_blocked(message)

    def test_an_earlier_staged_word_exempts_only_a_stay_or_remain_claim(self):
        for message in ("The fix for staged files is staged.", "The tests of the staged list are staged.",
                        "The rule on staged paths was staged."):
            with self.subTest(message=message):
                self.assert_blocked(message)

    def test_a_negation_in_one_sentence_does_not_hide_a_claim_in_another(self):
        for message in ("The files are staged. No tests failed.", "I staged the fix.\nNothing else changed."):
            with self.subTest(message=message):
                self.assert_blocked(message)

    def test_a_file_named_relative_to_a_subdirectory_cwd_is_checked_in_the_index(self):
        sub = self.repo / "sub"
        sub.mkdir()
        (sub / "c.txt").write_text("x\n")
        git(self.repo, "add", "sub/c.txt")
        self.assert_passes("c.txt is staged.", cwd=sub)

        (sub / "c.txt").write_text("y\n")
        git(self.repo, "reset", "-q", "sub/c.txt")
        git(self.repo, "add", "a.txt")
        reason = self.assert_blocked("c.txt is staged.", cwd=sub)
        self.assertIn("sub/c.txt", reason)

    def test_a_second_stop_and_a_claim_outside_any_repo_pass(self):
        self.assert_passes("The files are staged.", stop_hook_active=True)
        self.assert_passes("The files are staged.", cwd=self.outside)


class PermissionQuestionTest(unittest.TestCase):
    """The same Stop hook sends back a main-session turn that ends asking permission for a reversible step."""

    setUp = StagedClaimGateTest.setUp
    make_repo = StagedClaimGateTest.make_repo
    run_gate = StagedClaimGateTest.run_gate
    assert_passes = StagedClaimGateTest.assert_passes

    def assert_sent_back(self, message, **options):
        decision = json.loads(self.run_gate(message, **options))
        self.assertEqual(decision["decision"], "block")
        self.assertIn("without that closing question", decision["reason"])
        return decision["reason"]

    def write_prompts(self, *prompts):
        transcript = self.tmp / "prompts.jsonl"
        entries = [{"type": "user", "message": {"role": "user", "content": prompt}} for prompt in prompts]
        transcript.write_text("".join(json.dumps(entry) + "\n" for entry in entries))
        return transcript

    def test_the_reason_says_to_drop_the_question_not_to_start_the_step(self):
        reason = self.assert_sent_back("Fixed the invoice total. The report has the same bug. Want me to fix it too?")
        self.assertNotIn("take the step yourself", reason)

    def test_an_answer_to_the_users_question_passes_even_when_it_ends_on_an_offer(self):
        offer = "The gate hashed staged files apart from untracked ones. Want me to fix it?"
        for prompt in ("what is the issue with it", "Why did the gate block the commit?", "how does the driver work",
                       "is the bench still running", "fix the report\n\nwait, why is the total wrong?"):
            with self.subTest(prompt=prompt):
                self.assert_passes(offer, transcript_path=self.write_prompts("fix the invoice", prompt))

    def test_an_offer_after_a_handed_over_task_is_still_sent_back(self):
        offer = "Fixed the invoice total. The report has the same bug. Want me to fix it too?"
        for prompt in ("fix the invoice total", "can you fix the invoice total?", "go"):
            with self.subTest(prompt=prompt):
                self.assert_sent_back(offer, transcript_path=self.write_prompts("why is the total wrong?", prompt))

    def test_a_question_inside_a_paste_or_a_later_tool_result_is_not_the_users_question(self):
        offer = "Fixed the invoice total. The report has the same bug. Want me to fix it too?"
        pasted = "fix this\n<pasted_content>why does it fail?</pasted_content>"
        transcript = self.write_prompts(pasted)
        with transcript.open("a") as handle:
            handle.write(json.dumps({"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "content": "why?"}]}}) + "\n")
        self.assert_sent_back(offer, transcript_path=transcript)

    def test_a_turn_ending_on_a_permission_question_is_sent_back(self):
        for message in ("Fixed the invoice total. The monthly report has the same bug. Want me to fix it too?",
                        "Fixed the invoice total. The report repeats the bug. Do you want me to fix that too?",
                        "Fixed the invoice total; the report has the same loop. Do you want that fixed too?",
                        "The golden file holds the wrong figure. Shall I regenerate it?",
                        "Tests pass. Would you like me to add a test for the empty invoice?"):
            with self.subTest(message=message):
                self.assert_sent_back(message)

    def test_a_question_about_an_outward_or_lasting_step_passes(self):
        for message in ("The fix is ready. Do you want me to commit it?", "Tests pass. Should I push the branch?",
                        "The build is green. Want me to deploy it to production?",
                        "The old rows are unused. Shall I delete them from the database?"):
            with self.subTest(message=message):
                self.assert_passes(message)

    def test_a_question_about_an_irreversible_step_in_an_external_app_passes(self):
        for message in ("The duplicate invoice is still open in the billing app. Want me to void it?",
                        "The order was placed twice. Should I cancel the second one?",
                        "The form is filled in. Shall I submit it?"):
            with self.subTest(message=message):
                self.assert_passes(message)

    def test_a_question_about_prefixed_tickets_or_a_named_tracker_passes_but_a_local_step_is_sent_back(self):
        for message in ("The work splits by domain. Want me to file the per-domain sub-tickets?",
                        "The work splits by domain. Want me to file them in Jira?",
                        "The work splits by domain. Want me to create them in Jira?",
                        "The work splits by domain. Shall I create the subtasks?",
                        "The work splits by domain. Want me to file this on GitHub?",
                        "The work splits by domain. Want me to file them in Linear?",
                        "The work splits by domain. Want me to raise them to Jira?",
                        "The work splits by domain. Want me to open them into Linear?",
                        "The work splits by domain. Want me to file the sub-task?",
                        "The work splits by domain. Want me to file the sub-issue?"):
            with self.subTest(message=message):
                self.assert_passes(message)
        for message in ("Tests fail. Want me to rerun the tests?", "Tests pass. Want me to add the test?",
                        "Want me to make the lookup linear?", "Want me to open the task file?",
                        "Want me to look it up on GitHub?", "Want me to switch the interpolation to linear?",
                        "Want me to create the tasks file?", "Want me to check the GitHub Actions log?",
                        "Want me to check the file on GitHub?", "Want me to open the docs on GitHub?"):
            with self.subTest(message=message):
                self.assert_sent_back(message)

    def test_a_quoted_question_is_no_closing_question(self):
        for quote in ("`{}`", '"{}"', "“{}”"):
            for question in ("Want me to file the three findings in Jira?", "Want me to rerun the tests?"):
                message = "The cost: " + quote.format(question) + " still blocks."
                with self.subTest(message=message):
                    self.assert_passes(message)
        self.assert_sent_back("Tests fail. Want me to rerun the tests?")

    def test_inline_code_inside_the_closing_question_stays_in_it(self):
        self.assert_sent_back("Tests fail. Want me to rerun `make test`?")

    def test_a_long_one_line_message_with_code_spans_still_sends_back_its_closing_question(self):
        spans = " ".join(f"`Want me to rerun check_{number}?` stays quoted." for number in range(12))
        message = spans + " The `lint` and `build` steps pass. Want me to rerun `make test`?"
        self.assertGreater(len(message), 400)
        self.assert_sent_back(message)

    def test_a_quoted_question_cut_by_the_tail_boundary_is_still_dropped_whole(self):
        cited = "Want me to rerun the tests?` is the line I cut from the draft. "
        message = "y " * 30 + "`" + cited + "z" * (400 - len(cited))
        self.assertEqual(len(message) - message.index("`") - 1, 400)
        self.assert_passes(message)

    def test_a_stray_quote_before_the_closing_question_does_not_hide_it(self):
        self.assert_sent_back('It is 3" Want me to rerun the tests? It is "x".')

    def test_a_stray_double_quote_does_not_hide_the_closing_question(self):
        self.assert_sent_back('The 3" margin is fixed. Want me to rerun the tests? The key is "mode".')

    def test_a_quote_inside_the_closing_question_does_not_hide_it(self):
        for message in ('Tests pass. Should I run "make test"?', "Tests pass. Should I run “make test”?"):
            with self.subTest(message=message):
                self.assert_sent_back(message)

    def test_a_question_about_filing_a_ticket_or_messaging_someone_passes(self):
        for message in ("The bug sits in the billing service. Want me to file a Jira ticket for it?",
                        "The branch is pushed. Should I open a pull request?",
                        "Should I open a PR for it?",
                        "The team owns that check. Do you want me to tell them on Slack?",
                        "The reviewer asked twice. Want me to reply on the thread?"):
            with self.subTest(message=message):
                self.assert_passes(message)

    def test_a_question_about_a_local_ticket_note_still_sent_back(self):
        self.assert_sent_back("The plan cites the old ticket number. Want me to fix the reference?")

    def test_a_question_that_asks_for_a_choice_or_sits_early_passes(self):
        long_tail = " The fix keeps every invoice line in the sum, and the test covers two lines." * 8
        for message in ("Which name do you prefer, totals or sums?", "Do you want the short or the long report?",
                        "Want me to fix the report too?" + long_tail, "Fixed it. Nothing is left to do."):
            with self.subTest(message=message):
                self.assert_passes(message)

    def test_a_trigger_phrase_does_not_join_a_choice_question_in_the_next_sentence(self):
        self.assert_passes("The tests are ready to run. Which name do you prefer, totals or sums?")

    def test_a_second_stop_and_a_subagent_hand_back_pass(self):
        message = "The report has the same bug. Want me to fix it too?"
        self.assert_passes(message, stop_hook_active=True)
        self.assert_passes(message, event="SubagentStop")

    def test_a_staged_claim_and_a_permission_question_send_back_both_reasons(self):
        reason = self.assert_sent_back("The files are staged. Want me to fix the report too?")
        self.assertIn("git diff --cached --name-only", reason)


if __name__ == "__main__":
    unittest.main()
