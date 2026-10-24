import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

import toolkit_paths

CLAUDE_DIR = toolkit_paths.CLAUDE_DIR
SCRIPT = pathlib.Path(os.environ.get("ADR_FLOW_PATH") or CLAUDE_DIR / "skills" / "adr" / "scripts" / "adr_flow.py")
SCRIPT_UTILS = pathlib.Path(os.environ.get("ADR_SCRIPT_UTILS_PATH") or CLAUDE_DIR / "scripts" / "script_utils.py")
RESOLVE_SCRIPT = pathlib.Path(os.environ.get("ADR_RESOLVE_SCRIPT") or CLAUDE_DIR / "scripts" / "resolve-task-dir.sh")
TEMPLATE = pathlib.Path(os.environ.get("ADR_TEMPLATE") or CLAUDE_DIR / "skills" / "_shared" / "adr-template.md")
PLANS = "docs/plans"
DECISIONS = "docs/decisions"


def install_into_home(home):
    """Lay the script and what it reads out as the install does, and return the installed script path."""
    installed = home / ".claude" / "skills" / "adr" / "scripts" / "adr_flow.py"
    for source, target in (
        (SCRIPT, installed),
        (SCRIPT_UTILS, home / ".claude" / "scripts" / "script_utils.py"),
        (RESOLVE_SCRIPT, home / ".claude" / "scripts" / "resolve-task-dir.sh"),
        (TEMPLATE, home / ".claude" / "skills" / "_shared" / "adr-template.md"),
    ):
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(source, target)
    return installed

GIT_ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
}

GOOD_ADR = """# LED-5: Yield view

- **Status**: Accepted
- **PR**: `(pending)`
- **Date**: 2026-10-20
- **Reversibility**: two-way door — cheap to undo

## TL;DR

One sentence. Two sentences.

## Problem

Line one.

## Decision

Line one.

## Alternatives rejected

- **Other** — why not.

## Assumptions

- valid while single-region

## Watch out for

- drift
"""

TEMPLATE_SKELETON = """# ABC-XXX: [Feature name from ticket]

- **Status**: Accepted
- **Supersedes**: [ABC-YYY](link) — omit if none
- **Ticket**: [ABC-XXX](jira-url)
- **PR**: `(pending)` — normal at creation
- **Date**: YYYY-MM-DD
- **Reversibility**: two-way door — [one clause] | one-way door — [one clause]

## TL;DR

[≤3 sentences. Written last.]

## Problem

[1–2 paras]

## Decision

[1–2 paras]

## Alternatives rejected

- **[Option]** — [why not, 1–3 sentences]

## Assumptions

- [Checkable condition: "valid while …" / "revisit if …"]

## Watch out for

- [Latent risk, drift, hidden coupling, deliberate non-goal, or an anti-pattern this work uncovered]
"""

FAKE_GH_FOUND = """#!/usr/bin/env python3
import sys
if sys.argv[1:3] == ["pr", "view"]:
    sys.exit(1)
print('[{"url": "https://github.com/o/r/pull/7"}]')
"""

FAKE_GH_VIEW = """#!/usr/bin/env python3
import sys
if sys.argv[1:3] == ["pr", "view"]:
    print("https://github.com/o/r/pull/3")
    sys.exit(0)
sys.exit(1)
"""

FAKE_GH_FAILS = """#!/usr/bin/env python3
import sys
sys.exit(1)
"""

FAKE_GH_LOGS_AND_FINDS = """#!/usr/bin/env python3
import json, sys
with open({log_path!r}, "a") as log:
    log.write(json.dumps(sys.argv[1:]) + "\\n")
if sys.argv[1:3] == ["pr", "view"]:
    sys.exit(1)
print('[{{"url": "https://github.com/o/r/pull/7"}}]')
"""


class AdrFlowTest(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.temp_root = pathlib.Path(temp_dir.name).resolve()
        self.home = self.temp_root / "home"
        self.installed_script = install_into_home(self.home)
        self.repo = self.temp_root / "repo"
        self.repo.mkdir()
        self.git("init", "-q", "-b", "feature/yield-view")
        self.write("README.md", "hello\n")
        self.git("add", "README.md")
        self.git("commit", "-q", "-m", "init")
        self.gh = self.fake_gh(FAKE_GH_FAILS)

    def git(self, *args, cwd=None):
        env = {**os.environ, **GIT_ENV}
        return subprocess.run(
            ["git", *args], cwd=cwd or self.repo, env=env, check=True, capture_output=True, text=True
        ).stdout

    def write(self, rel_path, body):
        path = self.repo / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
        return path

    def fake_gh(self, body):
        path = self.temp_root / f"gh{len(list(self.temp_root.glob('gh*')))}"
        path.write_text(body)
        path.chmod(0o755)
        return path

    def make_task_dir(self, name="LED-5-yield-view", commit=True):
        for file_name in ("00-ticket.md", "01-questions.md", "02-research.md", "03-decisions.md", "spec.md"):
            body = (
                "# t\n**URL:** https://jira.example/LED-5\n"
                if file_name == "00-ticket.md"
                else f"body of {file_name}\n"
            )
            self.write(f"{PLANS}/{name}/{file_name}", body)
        if commit:
            self.git("add", PLANS)
            self.git("commit", "-q", "-m", "plan")
        return f"{PLANS}/{name}"

    def commit_at(self, message, iso_time):
        env = {**os.environ, **GIT_ENV, "GIT_COMMITTER_DATE": iso_time, "GIT_AUTHOR_DATE": iso_time}
        subprocess.run(["git", "commit", "-q", "-m", message], cwd=self.repo, env=env, check=True, capture_output=True)

    def make_draft_newest(self, adr):
        future = time.time() + 1000
        os.utime(adr, (future, future))

    def absolute(self, rel_path):
        return str(self.repo / rel_path)

    def run_flow(self, *args, cwd=None):
        env = {key: value for key, value in os.environ.items() if not key.startswith("ADR_") and key != "PYTHONPATH"}
        env.update({**GIT_ENV, "HOME": str(self.home), "ADR_GH": str(self.gh)})
        return subprocess.run(
            [sys.executable, str(self.installed_script), *args],
            cwd=cwd or self.repo,
            env=env,
            capture_output=True,
            text=True,
        )

    def check_adr(self, body, name="c.md"):
        adr = self.write(f"{DECISIONS}/{name}", body)
        return self.run_flow("check", str(adr))

    # prep

    def test_prep_prints_short_fields_then_template_and_never_source_bodies(self):
        task_dir = self.make_task_dir()

        result = self.run_flow("prep", "LED-5")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"task dir: {self.absolute(task_dir)}", result.stdout)
        self.assertIn(f"- {self.absolute(task_dir)}/spec.md (1 lines)", result.stdout)
        self.assertIn(f"- {self.absolute(task_dir)}/03-decisions.md (1 lines)", result.stdout)
        self.assertNotIn("body of spec.md", result.stdout)
        self.assertIn("ticket url: https://jira.example/LED-5", result.stdout)
        self.assertIn("PR: (pending)", result.stdout)
        self.assertIn(f"target: {self.absolute(DECISIONS)}/LED-5-yield-view.md", result.stdout)
        self.assertIn("ADR Template", result.stdout)
        self.assertLess(result.stdout.index("target:"), result.stdout.index("ADR Template"))
        self.assertIn("Model still does:", result.stdout.splitlines()[-1])

    def test_prep_output_stays_small_for_huge_sources(self):
        task_dir = self.make_task_dir()
        self.write(f"{task_dir}/spec.md", "line of spec text\n" * 20000)
        self.write(f"{task_dir}/03-decisions.md", "line of decision text\n" * 20000)

        result = self.run_flow("prep", "LED-5")

        self.assertLess(len(result.stdout.encode()), 15000)
        self.assertIn("(20000 lines)", result.stdout)
        self.assertIn("target:", result.stdout)
        self.assertIn("Model still does:", result.stdout.splitlines()[-1])

    def test_prep_reports_missing_source_instead_of_skipping(self):
        task_dir = self.make_task_dir()
        (self.repo / PLANS / "LED-5-yield-view" / "02-research.md").unlink()

        result = self.run_flow("prep", "LED-5")

        self.assertIn(f"- {self.absolute(task_dir)}/02-research.md (missing)", result.stdout)

    def test_prep_pr_from_list_when_view_fails(self):
        self.make_task_dir()
        self.gh = self.fake_gh(FAKE_GH_FOUND)

        result = self.run_flow("prep", "LED-5")

        self.assertIn("PR: https://github.com/o/r/pull/7", result.stdout)

    def test_prep_pr_list_asks_for_the_branch_head_in_any_state(self):
        self.make_task_dir()
        log_path = self.temp_root / "gh-calls.log"
        self.gh = self.fake_gh(FAKE_GH_LOGS_AND_FINDS.format(log_path=str(log_path)))

        self.run_flow("prep", "LED-5")

        calls = [json.loads(line) for line in log_path.read_text().splitlines()]
        list_call = next(call for call in calls if call[:2] == ["pr", "list"])
        self.assertEqual(list_call[list_call.index("--head") + 1], "feature/yield-view")
        self.assertEqual(list_call[list_call.index("--state") + 1], "all")
        self.assertNotIn("--search", list_call)

    def test_prep_pr_on_default_branch_is_pending_without_asking_gh(self):
        self.make_task_dir()
        self.git("branch", "-m", "main")
        log_path = self.temp_root / "gh-calls.log"
        self.gh = self.fake_gh(FAKE_GH_LOGS_AND_FINDS.format(log_path=str(log_path)))

        result = self.run_flow("prep", "LED-5")

        self.assertIn("PR: (pending)", result.stdout)
        self.assertFalse(log_path.exists())

    def test_prep_pr_from_view(self):
        self.make_task_dir()
        self.gh = self.fake_gh(FAKE_GH_VIEW)

        result = self.run_flow("prep", "LED-5")

        self.assertIn("PR: https://github.com/o/r/pull/3", result.stdout)

    def test_prep_flags_collision(self):
        self.make_task_dir()
        self.write(f"{DECISIONS}/LED-5-yield-view.md", GOOD_ADR)

        result = self.run_flow("prep", "LED-5")

        self.assertIn("COLLISION", result.stdout)

    def test_prep_slug_dir_without_ticket_uses_branch_slug(self):
        self.make_task_dir("fuzzy-filter")

        result = self.run_flow("prep", f"{PLANS}/fuzzy-filter")

        self.assertIn(f"target: {self.absolute(DECISIONS)}/yield-view.md", result.stdout)
        self.assertIn("ticket key: (none)", result.stdout)

    def test_prep_argument_ticket_wins_over_branch_ticket(self):
        self.make_task_dir("LED-5-yield-view")
        self.git("branch", "-m", "LED-9-health-doctor")

        result = self.run_flow("prep", "LED-5")

        self.assertIn("ticket key: LED-5", result.stdout)
        self.assertIn(f"target: {self.absolute(DECISIONS)}/LED-5-yield-view.md", result.stdout)

    def test_prep_argument_ticket_without_spec_wins_over_branch_ticket(self):
        self.git("branch", "-m", "LED-9-health-doctor")

        result = self.run_flow("prep", "LED-5")

        self.assertIn("ticket key: LED-5", result.stdout)
        self.assertIn(f"target: {self.absolute(DECISIONS)}/LED-5.md", result.stdout)

    def test_prep_no_spec_on_keyed_branch_keeps_branch_slug(self):
        self.git("branch", "-m", "LED-5-yield-view")

        result = self.run_flow("prep")

        self.assertIn("no spec", result.stdout)
        self.assertIn("ticket key: LED-5", result.stdout)
        self.assertIn(f"target: {self.absolute(DECISIONS)}/LED-5-yield-view.md", result.stdout)

    def test_prep_keyed_feature_branch_keeps_slug_after_prefix(self):
        self.git("branch", "-m", "feature/LED-5-yield-view")

        result = self.run_flow("prep")

        self.assertIn(f"target: {self.absolute(DECISIONS)}/LED-5-yield-view.md", result.stdout)

    def test_prep_area_slug_with_digits_is_not_a_ticket_key(self):
        self.git("branch", "-m", "feature/phase-6-static-render")

        result = self.run_flow("prep")

        self.assertIn("ticket key: (none)", result.stdout)
        self.assertIn(f"target: {self.absolute(DECISIONS)}/phase-6-static-render.md", result.stdout)

    def test_prep_unprefixed_area_branch_with_digits_has_no_key(self):
        self.git("branch", "-m", "phase-6-static-render")

        result = self.run_flow("prep")

        self.assertIn("ticket key: (none)", result.stdout)
        self.assertIn("ask the user for a name", result.stdout)

    def test_prep_ambiguous_lists_candidates_without_target_and_gives_rerun(self):
        self.make_task_dir("LED-5-a")
        self.make_task_dir("LED-5-b")

        result = self.run_flow("prep", "LED-5")

        self.assertEqual(result.returncode, 0)
        self.assertIn("AMBIGUOUS", result.stdout)
        self.assertIn(f"- {self.absolute(PLANS)}/LED-5-a", result.stdout)
        self.assertIn("rerun: python3", result.stdout)
        self.assertNotIn("target:", result.stdout)

    def test_prep_ambiguous_rerun_line_carries_the_keep_word(self):
        self.make_task_dir("LED-5-a")
        self.make_task_dir("LED-5-b")

        kept = self.run_flow("prep", "LED-5 keep")
        plain = self.run_flow("prep", "LED-5")

        self.assertIn('prep "<one candidate path above> keep"', kept.stdout)
        self.assertNotIn("keep", plain.stdout.split("rerun:")[1].splitlines()[0])

    def test_prep_legacy_flat_plan_lists_path_without_body(self):
        self.write(f"{PLANS}/LED-5-old.md", "legacy body\n")

        result = self.run_flow("prep", "LED-5")

        self.assertIn(f"legacy flat plan: {self.absolute(PLANS)}/LED-5-old.md", result.stdout)
        self.assertIn("finish takes no --task-dir", result.stdout)
        self.assertNotIn("legacy body", result.stdout)

    def test_prep_old_style_eng_specs_dir_lists_files_and_takes_no_task_dir(self):
        self.write("docs/eng-specs/RES-2-queue-tui/RES-2-02-research.md", "r\n")
        self.write("docs/eng-specs/RES-2-queue-tui/RES-2-03-design.md", "d1\nd2\n")
        self.git("branch", "-m", "main")

        result = self.run_flow("prep", "RES-2")

        self.assertIn("finish takes no --task-dir", result.stdout)
        self.assertIn(
            f"- {self.absolute('docs/eng-specs/RES-2-queue-tui')}/RES-2-02-research.md (1 lines)", result.stdout
        )
        self.assertIn("RES-2-03-design.md (2 lines)", result.stdout)
        self.assertNotIn("(missing)", result.stdout)
        self.assertIn(f"target: {self.absolute(DECISIONS)}/RES-2-queue-tui.md", result.stdout)

    def test_prep_refuses_a_directory_that_is_not_a_task_dir_without_reading_it(self):
        self.write("src/app/main.py", "code\n")
        self.write("src/app/.git-notes", "x\n")

        result = self.run_flow("prep", "src/app")

        self.assertEqual(result.returncode, 1)
        self.assertIn(f"not a task dir: {self.absolute('src/app')}", result.stderr)
        self.assertNotIn("main.py", result.stdout)

    def test_prep_refuses_a_docs_plans_dir_with_a_slug_outside_the_grammar(self):
        self.write(f"{PLANS}/a.b/spec.md", "s\n")

        result = self.run_flow("prep", f"{PLANS}/a.b")

        self.assertEqual(result.returncode, 1)
        self.assertIn("not a task dir", result.stderr)

    def test_prep_prints_the_date_without_a_slug_too(self):
        self.git("branch", "-m", "phase-6-static-render")

        result = self.run_flow("prep")

        self.assertIn("ask the user for a name", result.stdout)
        self.assertRegex(result.stdout, r"date: \d{4}-\d{2}-\d{2}")

    def test_prep_keep_word_resolves_the_rest_and_adds_the_keep_flag_to_the_finish_command(self):
        task_dir = self.make_task_dir()

        result = self.run_flow("prep", "LED-5 keep")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ticket key: LED-5", result.stdout)
        self.assertIn(f"task dir: {self.absolute(task_dir)}", result.stdout)
        self.assertIn("--keep-task-dir", result.stdout.splitlines()[-1])

    def test_prep_without_the_keep_word_prints_no_keep_flag(self):
        self.make_task_dir()

        result = self.run_flow("prep", "LED-5")

        self.assertNotIn("--keep-task-dir", result.stdout)

    def test_prep_keep_word_is_matched_without_regard_to_case(self):
        self.make_task_dir()

        result = self.run_flow("prep", "LED-5 Keep")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ticket key: LED-5", result.stdout)
        self.assertIn("--keep-task-dir", result.stdout.splitlines()[-1])

    def test_prep_refuses_extra_words_instead_of_guessing(self):
        self.make_task_dir()

        result = self.run_flow("prep", "LED-5 keep it")

        self.assertEqual(result.returncode, 1)
        self.assertIn("prep takes one path or ticket key plus an optional keep; got: LED-5 keep it", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_prep_keep_inside_a_word_is_not_a_trigger(self):
        task_dir = self.make_task_dir("LED-7-keepalive")

        result = self.run_flow("prep", f"{PLANS}/LED-7-keepalive")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"task dir: {self.absolute(task_dir)}", result.stdout)
        self.assertNotIn("--keep-task-dir", result.stdout)

    def test_prep_model_steps_do_not_repeat_the_gate(self):
        result = self.run_flow("prep", "LED-5")

        self.assertNotIn("gate", result.stdout.splitlines()[-1])

    def test_prep_no_spec_still_prints_template(self):
        result = self.run_flow("prep", "LED-5")

        self.assertEqual(result.returncode, 0)
        self.assertIn("no spec", result.stdout)
        self.assertIn("ADR Template", result.stdout)

    def test_prep_outside_repo_exits_1(self):
        result = self.run_flow("prep", cwd=self.temp_root)

        self.assertEqual(result.returncode, 1)
        self.assertIn("not inside a git repository", result.stderr)

    def test_prep_writes_nothing(self):
        self.make_task_dir()
        before = self.git("status", "--porcelain=v1", "--ignored")

        self.run_flow("prep", "LED-5")

        self.assertEqual(self.git("status", "--porcelain=v1", "--ignored"), before)

    # check

    def test_check_accepts_good_adr(self):
        result = self.check_adr(GOOD_ADR)

        self.assertEqual(result.returncode, 0, result.stdout)

    def test_check_fails_each_cap(self):
        cases = {
            "Problem": 9,
            "Decision": 9,
            "Alternatives rejected": 13,
            "Assumptions": 7,
            "Watch out for": 11,
        }
        for section, line_count in cases.items():
            with self.subTest(section=section):
                body = GOOD_ADR.replace(
                    f"## {section}\n\n",
                    f"## {section}\n\n" + "".join(f"- extra {n}\n" for n in range(line_count)) + "\n",
                    1,
                )

                result = self.check_adr(body, "cap.md")

                self.assertEqual(result.returncode, 1)
                self.assertIn(f"`{section}` has", result.stdout)

    def test_check_fails_tldr_over_three_sentences(self):
        result = self.check_adr(GOOD_ADR.replace("One sentence. Two sentences.", "A. B. C. D."))

        self.assertEqual(result.returncode, 1)
        self.assertIn("TL;DR has 4 sentences", result.stdout)

    def test_check_fails_empty_alternatives_and_placeholder_assumptions(self):
        body = GOOD_ADR.replace("- **Other** — why not.\n", "").replace(
            "- valid while single-region", "- [Checkable condition]"
        )

        result = self.check_adr(body)

        self.assertEqual(result.returncode, 1)
        self.assertIn("`Alternatives rejected` is empty", result.stdout)
        self.assertIn("`Assumptions` is empty", result.stdout)

    def test_check_fails_missing_section(self):
        result = self.check_adr(GOOD_ADR.replace("## Watch out for\n\n- drift\n", ""))

        self.assertEqual(result.returncode, 1)
        self.assertIn("missing section `## Watch out for`", result.stdout)

    def test_check_fails_the_unfilled_template_skeleton(self):
        result = self.check_adr(TEMPLATE_SKELETON)

        self.assertEqual(result.returncode, 1)
        self.assertIn("unfilled placeholder: - **[Option]** — [why not, 1–3 sentences]", result.stdout)
        self.assertIn("`TL;DR` is empty or only placeholders", result.stdout)
        self.assertIn("`Problem` is empty or only placeholders", result.stdout)
        self.assertIn("header `Date` is `YYYY-MM-DD`", result.stdout)
        self.assertIn("unfilled placeholder: - **Ticket**: [ABC-XXX](jira-url)", result.stdout)
        self.assertIn("unfilled placeholder: - **Supersedes**: [ABC-YYY](link)", result.stdout)
        self.assertIn("unfilled placeholder: # ABC-XXX: [Feature name from ticket]", result.stdout)

    def test_check_fails_link_shaped_and_token_placeholders(self):
        for line in ("[repo#NNN](pr-url)", "[ABC-YYY](link)", "see ABC-XXX here", "repo#NNN", "[x](plain)"):
            with self.subTest(line=line):
                body = GOOD_ADR.replace("## Decision\n\nLine one.", f"## Decision\n\nLine one. {line}")

                result = self.check_adr(body, "link.md")

                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn("unfilled placeholder", result.stdout)

    def test_check_accepts_real_links_checkboxes_and_tokens_in_code(self):
        for line in ("[doc](https://x.example)", "[a](docs/a.md)", "[b](file.md)", "[c](#anchor)", "- [x] done",
                     "- [ ] todo", "write `ABC-XXX` as the key"):
            with self.subTest(line=line):
                body = GOOD_ADR.replace("## Decision\n\nLine one.", f"## Decision\n\nLine one.\n\n{line}")

                result = self.check_adr(body, "ok.md")

                self.assertEqual(result.returncode, 0, result.stdout)

    def test_check_fails_unknown_level_two_section_and_names_the_allowed_ones(self):
        result = self.check_adr(GOOD_ADR + "\n## Consequences\n\nRestated.\n")

        self.assertEqual(result.returncode, 1)
        self.assertIn("unknown section `## Consequences`", result.stdout)
        self.assertIn("`## Watch out for`", result.stdout)
        self.assertIn("`## Addenda`", result.stdout)
        self.assertIn("use ### for a sub-heading", result.stdout)

    def test_check_fails_the_template_subsystem_placeholder_inside_inline_code(self):
        body = GOOD_ADR + "\n## Related\n\n- Eng-arch: `docs/architecture/[subsystem].md`\n"

        result = self.check_adr(body)

        self.assertEqual(result.returncode, 1)
        self.assertIn("unfilled placeholder: - Eng-arch: `docs/architecture/[subsystem].md`", result.stdout)

    def test_check_accepts_addenda_and_related_sections(self):
        body = GOOD_ADR + "\n## Addenda\n\n- **2026-10-20** — outcome: fine\n\n## Related\n\n- eng-arch\n"

        result = self.check_adr(body)

        self.assertEqual(result.returncode, 0, result.stdout)

    def test_check_abbreviations_do_not_end_a_sentence(self):
        body = GOOD_ADR.replace("One sentence. Two sentences.", "Use a store, e.g. redis, i.e. a cache. Second. Third.")

        result = self.check_adr(body)

        self.assertEqual(result.returncode, 0, result.stdout)

    def test_check_lone_comment_opener_in_inline_code_does_not_hide_later_sections(self):
        body = GOOD_ADR.replace("## Decision\n\nLine one.", "## Decision\n\nWrite `<!--` to open a comment.")

        result = self.check_adr(body)

        self.assertEqual(result.returncode, 0, result.stdout)

    def test_check_still_drops_a_real_html_comment(self):
        body = GOOD_ADR + "\n## Addenda\n\n<!-- [what happened] -->\n"

        result = self.check_adr(body)

        self.assertEqual(result.returncode, 0, result.stdout)

    def test_runs_from_an_install_shaped_home_with_no_pythonpath(self):
        adr = self.write(f"{DECISIONS}/c.md", GOOD_ADR)

        result = self.run_flow("check", str(adr))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("ModuleNotFoundError", result.stderr)

    def test_check_fails_option_line_with_placeholders_beside_a_real_one(self):
        body = GOOD_ADR.replace("- **Other** — why not.\n", "- **Other** — why not.\n- **[Option]** — [why not]\n")

        result = self.check_adr(body)

        self.assertEqual(result.returncode, 1)
        self.assertIn("unfilled placeholder: - **[Option]** — [why not]", result.stdout)

    def test_check_fails_empty_tldr_and_bracketed_problem(self):
        body = GOOD_ADR.replace("One sentence. Two sentences.\n", "").replace(
            "## Problem\n\nLine one.", "## Problem\n\n[1–2 paras]"
        )

        result = self.check_adr(body)

        self.assertEqual(result.returncode, 1)
        self.assertIn("`TL;DR` is empty", result.stdout)
        self.assertIn("`Problem` is empty", result.stdout)

    def test_check_accepts_links_inline_code_and_fenced_brackets(self):
        body = GOOD_ADR.replace(
            "## Decision\n\nLine one.\n",
            "## Decision\n\nSee [the doc](https://x.example) and `items[0]`.\n\n```\nx = [1, 2]\n```\n",
        )

        result = self.check_adr(body)

        self.assertEqual(result.returncode, 0, result.stdout)

    def test_check_fails_missing_header_bullets(self):
        for field in ("Status", "Date", "Reversibility"):
            with self.subTest(field=field):
                lines = [line for line in GOOD_ADR.splitlines(keepends=True) if f"**{field}**" not in line]

                result = self.check_adr("".join(lines), "h.md")

                self.assertEqual(result.returncode, 1)
                self.assertIn(f"missing header bullet `- **{field}**", result.stdout)

    def test_check_ignores_heading_inside_fence_and_does_not_reset_the_section(self):
        extra = "".join(f"- extra {n}\n" for n in range(9))
        body = GOOD_ADR.replace("## Decision\n\nLine one.\n", f"## Decision\n\n```\n## Problem\n```\n{extra}")

        result = self.check_adr(body)

        self.assertEqual(result.returncode, 1)
        self.assertIn("`Decision` has 12 lines, cap 8", result.stdout)
        self.assertNotIn("repeats", result.stdout)
        self.assertNotIn("`Problem` is empty", result.stdout)

    def test_check_fails_repeated_heading(self):
        body = GOOD_ADR + "\n## Problem\n\nSecond problem.\n"

        result = self.check_adr(body)

        self.assertEqual(result.returncode, 1)
        self.assertIn("heading `## Problem` repeats line", result.stdout)

    # finish: delete and refusals

    def test_finish_deletes_exact_task_dir(self):
        task_dir = self.make_task_dir()
        adr = self.write(f"{DECISIONS}/LED-5-yield-view.md", GOOD_ADR)

        result = self.run_flow("finish", str(adr), "--task-dir", self.absolute(task_dir))

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertFalse((self.repo / task_dir).exists())
        self.assertTrue(adr.exists())
        self.assertIn(f"Drafted to {adr}. Adjust?", result.stdout)

    def test_finish_deletes_dir_with_uncommitted_plan_files(self):
        task_dir = self.make_task_dir()
        self.write(f"{task_dir}/05-plan-review-r1.md", "x\n")
        self.write(f"{task_dir}/spec.md", "edited\n")
        adr = self.write(f"{DECISIONS}/a.md", GOOD_ADR)
        self.make_draft_newest(adr)

        result = self.run_flow("finish", str(adr), "--task-dir", self.absolute(task_dir))

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertFalse((self.repo / task_dir).exists())

    def test_refuses_a_plan_file_moved_into_the_task_dir_after_the_draft(self):
        task_dir = self.make_task_dir()
        outside = self.write("notes/05-plan-review-r2.md", "moved in\n")
        os.utime(outside, (50, 50))
        adr = self.write(f"{DECISIONS}/a.md", GOOD_ADR)
        time.sleep(0.05)
        moved = self.repo / task_dir / "05-plan-review-r2.md"
        outside.rename(moved)

        result = self.run_flow("finish", str(adr), "--task-dir", self.absolute(task_dir))

        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("05-plan-review-r2.md", result.stdout)
        self.assertTrue(moved.exists())

    def test_refuses_an_ignored_plan_file_written_after_the_committed_draft(self):
        self.write(".gitignore", "05-plan-review-r*.md\n")
        task_dir = self.make_task_dir()
        adr = self.write(f"{DECISIONS}/LED-5-yield-view.md", GOOD_ADR)
        self.git("add", ".gitignore", DECISIONS)
        self.git("commit", "-q", "-m", "adr")
        review = self.write(f"{task_dir}/05-plan-review-r2.md", "ignored review\n")

        refused = self.run_flow("finish", str(adr), "--task-dir", self.absolute(task_dir))

        self.assertEqual(refused.returncode, 2, refused.stdout)
        self.assertIn("newer than the draft", refused.stdout)
        self.assertTrue(review.exists())

        result = self.run_flow("finish", str(adr), "--task-dir", self.absolute(task_dir), "--draft-is-current")

        self.assertEqual(result.returncode, 0, result.stdout)

    def test_refuses_an_ignored_plan_file_after_a_rebase_rewrote_the_committed_draft(self):
        self.write(".gitignore", "05-plan-review-r*.md\n")
        task_dir = self.make_task_dir()
        adr = self.write(f"{DECISIONS}/LED-5-yield-view.md", GOOD_ADR)
        self.git("add", ".gitignore", DECISIONS)
        self.commit_at("adr", "2020-01-01T00:00:00Z")
        review = self.write(f"{task_dir}/05-plan-review-r2.md", "ignored review\n")
        self.git("branch", "main", "HEAD~2")
        self.git("checkout", "-q", "main")
        self.write("other.txt", "moved main\n")
        self.git("add", "other.txt")
        self.git("commit", "-q", "-m", "main moved")
        self.git("checkout", "-q", "feature/yield-view")
        self.git("rebase", "-q", "main")
        self.assertGreater(adr.stat().st_mtime_ns, review.stat().st_mtime_ns)

        result = self.run_flow("finish", str(adr), "--task-dir", self.absolute(task_dir))

        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("newer than the draft", result.stdout)
        self.assertTrue(review.exists())

    def test_refuses_when_a_plan_file_is_newer_than_an_untracked_draft(self):
        task_dir = self.make_task_dir()
        adr = self.write(f"{DECISIONS}/a.md", GOOD_ADR)
        late = self.write(f"{task_dir}/05-plan-review-r2.md", "late\n")
        os.utime(adr, (100, 100))
        os.utime(late, (200, 200))

        result = self.run_flow("finish", str(adr), "--task-dir", self.absolute(task_dir))

        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("newer than the draft", result.stdout)
        self.assertTrue(late.exists())

    def test_draft_is_current_skips_the_newer_plan_file_check(self):
        task_dir = self.make_task_dir()
        adr = self.write(f"{DECISIONS}/a.md", GOOD_ADR)
        late = self.write(f"{task_dir}/05-plan-review-r2.md", "late\n")
        os.utime(adr, (100, 100))
        os.utime(late, (200, 200))

        result = self.run_flow("finish", str(adr), "--task-dir", self.absolute(task_dir), "--draft-is-current")

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertFalse((self.repo / task_dir).exists())

    def test_refuses_untracked_plan_file_when_git_hides_untracked_files(self):
        task_dir = self.make_task_dir()
        adr = self.write(f"{DECISIONS}/LED-5-yield-view.md", GOOD_ADR)
        self.git("add", DECISIONS)
        self.git("commit", "-q", "-m", "adr")
        self.git("config", "status.showUntrackedFiles", "no")
        review = self.write(f"{task_dir}/05-plan-review-r2.md", "new review\n")

        result = self.run_flow("finish", str(adr), "--task-dir", self.absolute(task_dir), "--draft-is-current")

        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("task dir has uncommitted changes", result.stdout)
        self.assertTrue(review.exists())

    def test_finish_deletes_dir_with_eng_spec_shard_files(self):
        task_dir = self.make_task_dir()
        shapes = (
            "review-shard-A.md", "review-shard-B.md", "review-shard-seam.md", "spec-review-shard-a.md",
            "spec-review-shard-b.md", "plan-review-shard-a.md", "plan-review-shard-b.md", "plan-review-round1.md",
            "01-leak-check.md", "04-exploration.md", "05-plan-review-r1.md", "05-plan-review-r12.md",
            "acceptance-criteria.md",
        )
        for name in shapes:
            self.write(f"{task_dir}/{name}", "x\n")
        adr = self.write(f"{DECISIONS}/a.md", GOOD_ADR)

        result = self.run_flow("finish", str(adr), "--task-dir", self.absolute(task_dir))

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertFalse((self.repo / task_dir).exists())

    def test_refuses_hand_written_names_that_only_look_like_plan_files(self):
        for name in ("plan.md", "slices.md", "04-acceptance-criteria.md", "plan-review-shard-.md", "review-shard-1.md"):
            with self.subTest(name=name):
                task_dir = self.make_task_dir(f"LED-5-{name.split('.')[0]}")
                self.write(f"{task_dir}/{name}", "mine\n")

                self.assert_refused(task_dir, name)
                self.assertTrue((self.repo / task_dir / name).exists())

    def test_refuses_task_dir_of_a_different_ticket_than_the_draft(self):
        task_dir = self.make_task_dir("LED-9-health-doctor")
        adr = self.write(f"{DECISIONS}/LED-5-yield-view.md", GOOD_ADR)

        result = self.run_flow("finish", str(adr), "--task-dir", self.absolute(task_dir))

        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("LED-5", result.stdout)
        self.assertIn("LED-9", result.stdout)
        self.assertTrue((self.repo / task_dir / "spec.md").exists())

    def test_deletes_when_only_one_side_names_a_ticket(self):
        task_dir = self.make_task_dir("fuzzy-filter")
        adr = self.write(f"{DECISIONS}/LED-5-yield-view.md", GOOD_ADR)

        result = self.run_flow("finish", str(adr), "--task-dir", self.absolute(task_dir))

        self.assertEqual(result.returncode, 0, result.stdout)

    def test_refuses_an_old_committed_draft_as_proof_of_a_new_one(self):
        adr = self.write(f"{DECISIONS}/LED-5-yield-view.md", GOOD_ADR)
        self.git("add", DECISIONS)
        self.commit_at("old adr", "2020-01-01T00:00:00Z")
        task_dir = self.make_task_dir()

        result = self.run_flow("finish", str(adr), "--task-dir", self.absolute(task_dir))

        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("already committed and unchanged", result.stdout)
        self.assertTrue((self.repo / task_dir / "spec.md").exists())

    def test_refuses_a_draft_committed_in_the_same_second_before_the_task_dir(self):
        adr = self.write(f"{DECISIONS}/LED-5-yield-view.md", GOOD_ADR)
        self.git("add", DECISIONS)
        self.commit_at("old adr", "2030-01-01T00:00:00Z")
        task_dir = self.make_task_dir(commit=False)
        self.git("add", PLANS)
        self.commit_at("plan", "2030-01-01T00:00:00Z")

        result = self.run_flow("finish", str(adr), "--task-dir", self.absolute(task_dir))

        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("already committed and unchanged", result.stdout)
        self.assertTrue((self.repo / task_dir / "spec.md").exists())

    def test_refuses_an_older_draft_after_a_rebase_put_the_task_dir_commit_on_top(self):
        self.git("checkout", "-q", "-b", "other")
        adr = self.write(f"{DECISIONS}/LED-5-yield-view.md", GOOD_ADR)
        self.git("add", DECISIONS)
        self.commit_at("old adr", "2099-01-01T00:00:00Z")
        self.git("checkout", "-q", "feature/yield-view")
        task_dir = self.make_task_dir()
        self.git("rebase", "-q", "other")

        result = self.run_flow("finish", str(adr), "--task-dir", self.absolute(task_dir))

        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("already committed and unchanged", result.stdout)
        self.assertTrue((self.repo / task_dir / "spec.md").exists())

    def test_refuses_a_committed_draft_when_the_task_dir_has_uncommitted_changes(self):
        task_dir = self.make_task_dir()
        adr = self.write(f"{DECISIONS}/LED-5-yield-view.md", GOOD_ADR)
        self.git("add", DECISIONS)
        self.git("commit", "-q", "-m", "adr")
        review = self.write(f"{task_dir}/05-plan-review-r2.md", "new review\n")
        spec = self.write(f"{task_dir}/spec.md", "edited spec\n")

        result = self.run_flow("finish", str(adr), "--task-dir", self.absolute(task_dir))

        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("uncommitted changes", result.stdout)
        self.assertTrue(review.exists())
        self.assertEqual(spec.read_text(), "edited spec\n")

    def test_draft_is_current_never_skips_the_dirty_task_dir_check(self):
        task_dir = self.make_task_dir()
        adr = self.write(f"{DECISIONS}/LED-5-yield-view.md", GOOD_ADR)
        self.git("add", DECISIONS)
        self.git("commit", "-q", "-m", "adr")
        review = self.write(f"{task_dir}/05-plan-review-r2.md", "new review\n")

        result = self.run_flow("finish", str(adr), "--task-dir", self.absolute(task_dir), "--draft-is-current")

        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertTrue(review.exists())

    def test_keep_task_dir_deletes_nothing_on_a_clean_task_dir_and_names_it(self):
        task_dir = self.make_task_dir()
        adr = self.write(f"{DECISIONS}/LED-5-yield-view.md", GOOD_ADR)

        result = self.run_flow("finish", str(adr), "--task-dir", self.absolute(task_dir), "--keep-task-dir")

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn(self.absolute(task_dir), result.stdout)
        self.assertTrue((self.repo / task_dir / "spec.md").exists())

    def test_keep_task_dir_prints_the_kept_absolute_path(self):
        task_dir = self.make_task_dir()
        adr = self.write(f"{DECISIONS}/LED-5-yield-view.md", GOOD_ADR)

        result = self.run_flow("finish", str(adr), "--task-dir", self.absolute(task_dir), "--keep-task-dir")

        self.assertIn(f"task dir kept: {self.absolute(task_dir)}", result.stdout)

    def test_keep_task_dir_does_not_claim_a_missing_dir_was_kept(self):
        adr = self.write(f"{DECISIONS}/a.md", GOOD_ADR)
        gone = self.absolute(f"{PLANS}/LED-5-gone")

        result = self.run_flow("finish", str(adr), "--task-dir", gone, "--keep-task-dir")

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotRegex(result.stdout, r"(?<!no )task dir kept")
        self.assertIn(f"no task dir kept: {gone} is not a task dir", result.stdout)

    def test_keep_task_dir_does_not_claim_a_relative_or_non_task_dir_path_was_kept(self):
        task_dir = self.make_task_dir()
        adr = self.write(f"{DECISIONS}/a.md", GOOD_ADR)
        for argument in (task_dir, self.absolute(PLANS)):
            with self.subTest(argument=argument):
                result = self.run_flow("finish", str(adr), "--task-dir", argument, "--keep-task-dir")

                self.assertEqual(result.returncode, 0, result.stdout)
                self.assertNotRegex(result.stdout, r"(?<!no )task dir kept")
                self.assertIn(f"no task dir kept: {argument} is not a task dir", result.stdout)

    def test_keep_task_dir_without_a_task_dir_says_none_was_passed(self):
        adr = self.write(f"{DECISIONS}/a.md", GOOD_ADR)

        result = self.run_flow("finish", str(adr), "--keep-task-dir")

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("no task dir passed", result.stdout)
        self.assertNotIn("task dir kept", result.stdout)

    def test_keep_task_dir_fails_when_the_draft_lives_inside_the_task_dir(self):
        task_dir = self.make_task_dir()
        adr = self.write(f"{task_dir}/05-adr.md", GOOD_ADR)

        result = self.run_flow("finish", str(adr), "--task-dir", self.absolute(task_dir), "--keep-task-dir")

        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("FAIL the draft lives inside the task dir; move it to the prep target", result.stdout)
        self.assertNotIn("task dir kept", result.stdout)

    def test_keep_task_dir_with_a_dir_that_holds_the_draft_but_is_not_a_task_dir_keeps_nothing(self):
        self.make_task_dir()
        adr = self.write(f"{DECISIONS}/a.md", GOOD_ADR)

        result = self.run_flow("finish", str(adr), "--task-dir", self.absolute("docs"), "--keep-task-dir")

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("no task dir kept", result.stdout)

    def test_keep_task_dir_with_an_empty_task_dir_says_so(self):
        adr = self.write(f"{DECISIONS}/a.md", GOOD_ADR)

        result = self.run_flow("finish", str(adr), "--task-dir", "", "--keep-task-dir")

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("no task dir kept: --task-dir is empty", result.stdout)

    def test_a_draft_inside_the_task_dir_is_refused_without_offering_the_keep_flag(self):
        task_dir = self.make_task_dir()
        adr = self.write(f"{task_dir}/05-adr.md", GOOD_ADR)

        result = self.run_flow("finish", str(adr), "--task-dir", self.absolute(task_dir))

        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("REFUSED delete: the draft lives inside the task dir", result.stdout)
        self.assertNotIn("--keep-task-dir", result.stdout)
        self.assertTrue((self.repo / task_dir / "spec.md").exists())

    def test_both_flags_on_a_clean_deletable_dir_leave_it_in_place(self):
        task_dir = self.make_task_dir()
        adr = self.write(f"{DECISIONS}/LED-5-yield-view.md", GOOD_ADR)

        result = self.run_flow(
            "finish", str(adr), "--task-dir", self.absolute(task_dir), "--draft-is-current", "--keep-task-dir"
        )

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertTrue((self.repo / task_dir / "spec.md").exists())
        self.assertIn("task dir kept", result.stdout)

    def test_keep_task_dir_skips_every_task_dir_refusal(self):
        task_dir = self.make_task_dir()
        self.write(f"{task_dir}/notes.md", "user note\n")
        self.write(f"{task_dir}/05-plan-review-r2.md", "staged\n")
        self.git("add", f"{task_dir}/05-plan-review-r2.md")
        adr = self.write(f"{DECISIONS}/LED-9-other.md", GOOD_ADR)
        refused = self.run_flow("finish", str(adr), "--task-dir", self.absolute(task_dir))
        self.assertEqual(refused.returncode, 2, refused.stdout)
        self.assertIn("--keep-task-dir", refused.stdout)

        result = self.run_flow("finish", str(adr), "--task-dir", self.absolute(task_dir), "--keep-task-dir")

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertTrue((self.repo / task_dir / "notes.md").exists())
        self.assertTrue((self.repo / task_dir / "05-plan-review-r2.md").exists())

    def test_keep_task_dir_skips_the_committed_draft_order_refusal(self):
        adr = self.write(f"{DECISIONS}/LED-5-yield-view.md", GOOD_ADR)
        self.git("add", DECISIONS)
        self.commit_at("old adr", "2020-01-01T00:00:00Z")
        task_dir = self.make_task_dir()

        result = self.run_flow("finish", str(adr), "--task-dir", self.absolute(task_dir), "--keep-task-dir")

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertTrue((self.repo / task_dir / "spec.md").exists())

    def test_keep_task_dir_still_fails_a_bad_draft(self):
        task_dir = self.make_task_dir()
        adr = self.write(f"{DECISIONS}/LED-5-yield-view.md", GOOD_ADR.replace("## Decision", "## Decide"))

        result = self.run_flow("finish", str(adr), "--task-dir", self.absolute(task_dir), "--keep-task-dir")

        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("FAIL", result.stdout)
        self.assertTrue((self.repo / task_dir / "spec.md").exists())

    def test_draft_is_current_deletes_when_the_new_draft_was_committed_before_the_task_dir(self):
        adr = self.write(f"{DECISIONS}/LED-5-yield-view.md", GOOD_ADR)
        self.git("add", DECISIONS)
        self.git("commit", "-q", "-m", "adr")
        task_dir = self.make_task_dir()

        refused = self.run_flow("finish", str(adr), "--task-dir", self.absolute(task_dir))
        self.assertEqual(refused.returncode, 2, refused.stdout)
        self.assertIn("--draft-is-current", refused.stdout)
        self.assertTrue((self.repo / task_dir).exists())

        result = self.run_flow("finish", str(adr), "--task-dir", self.absolute(task_dir), "--draft-is-current")

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertFalse((self.repo / task_dir).exists())

    def test_deletes_when_the_draft_was_committed_together_with_the_task_dir_files(self):
        task_dir = self.make_task_dir(commit=False)
        adr = self.write(f"{DECISIONS}/LED-5-yield-view.md", GOOD_ADR)
        self.git("add", PLANS)

        staged = self.run_flow("finish", str(adr), "--task-dir", self.absolute(task_dir))
        self.assertEqual(staged.returncode, 2, staged.stdout)
        self.assertIn("STOP: staged entries", staged.stdout)
        self.git("add", DECISIONS)
        self.git("commit", "-q", "-m", "plan and adr")

        result = self.run_flow("finish", str(adr), "--task-dir", self.absolute(task_dir))

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertFalse((self.repo / task_dir).exists())

    def test_deletes_when_the_committed_draft_is_newer_than_the_task_dir(self):
        task_dir = self.make_task_dir()
        adr = self.write(f"{DECISIONS}/LED-5-yield-view.md", GOOD_ADR)
        self.git("add", DECISIONS)
        self.commit_at("adr", "2099-01-01T00:00:00Z")

        result = self.run_flow("finish", str(adr), "--task-dir", self.absolute(task_dir))

        self.assertEqual(result.returncode, 0, result.stdout)

    def test_deletes_when_the_committed_draft_has_new_edits(self):
        task_dir = self.make_task_dir()
        adr = self.write(f"{DECISIONS}/LED-5-yield-view.md", GOOD_ADR)
        self.git("add", DECISIONS)
        self.git("commit", "-q", "-m", "old adr")
        self.write(f"{DECISIONS}/LED-5-yield-view.md", GOOD_ADR + "\n- edited\n")

        result = self.run_flow("finish", str(adr), "--task-dir", self.absolute(task_dir))

        self.assertEqual(result.returncode, 0, result.stdout)

    def test_refusal_for_a_missing_dir_does_not_claim_it_was_kept(self):
        adr = self.write(f"{DECISIONS}/a.md", GOOD_ADR)

        result = self.run_flow("finish", str(adr), "--task-dir", self.absolute(f"{PLANS}/LED-5-gone"))

        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Task dir kept", result.stdout)
        self.assertIn("Nothing was deleted", result.stdout)

    def test_refusal_for_an_existing_dir_says_it_was_kept_and_offers_the_keep_flag(self):
        task_dir = self.make_task_dir()
        self.write(f"{task_dir}/notes.txt", "mine\n")
        adr = self.write(f"{DECISIONS}/a.md", GOOD_ADR)

        result = self.run_flow("finish", str(adr), "--task-dir", self.absolute(task_dir))

        self.assertIn("Task dir kept", result.stdout)
        self.assertIn("rerun finish with --keep-task-dir", result.stdout)

    def test_a_path_refusal_asks_for_the_prep_path_and_does_not_offer_the_keep_flag(self):
        task_dir = self.make_task_dir()
        adr = self.write(f"{DECISIONS}/a.md", GOOD_ADR)
        for argument in (task_dir, "", self.absolute(DECISIONS), self.absolute(f"{PLANS}/LED-5-gone")):
            with self.subTest(argument=argument):
                result = self.run_flow("finish", str(adr), "--task-dir", argument)

                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertNotIn("--keep-task-dir", result.stdout)
                self.assertIn("Pass the absolute task dir printed by prep, or omit --task-dir.", result.stdout)

    def test_finish_tells_the_model_to_recheck_after_the_users_edits(self):
        adr = self.write(f"{DECISIONS}/a.md", GOOD_ADR)

        result = self.run_flow("finish", str(adr))

        self.assertIn("adr_flow.py check <path>", result.stdout)

    def test_finish_without_task_dir_deletes_nothing(self):
        task_dir = self.make_task_dir()
        adr = self.write(f"{DECISIONS}/a.md", GOOD_ADR)

        result = self.run_flow("finish", str(adr))

        self.assertEqual(result.returncode, 0)
        self.assertTrue((self.repo / task_dir).exists())

    def assert_refused(self, task_dir_argument, expected_text=None, absolute=True):
        adr = self.repo / DECISIONS / "a.md"
        if not adr.exists():
            self.write(f"{DECISIONS}/a.md", GOOD_ADR)
        argument = task_dir_argument
        if absolute and not os.path.isabs(argument):
            argument = self.absolute(argument)

        result = self.run_flow("finish", str(adr), "--task-dir", argument)

        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("REFUSED delete", result.stdout)
        if expected_text:
            self.assertIn(expected_text, result.stdout)
        self.assertTrue(adr.exists())

    def test_refuses_relative_task_dir(self):
        task_dir = self.make_task_dir()

        self.assert_refused(task_dir, "is relative", absolute=False)
        self.assertTrue((self.repo / task_dir / "spec.md").exists())

    def test_refuses_empty_task_dir_value(self):
        task_dir = self.make_task_dir()

        self.assert_refused("", "--task-dir is empty", absolute=False)
        self.assertTrue((self.repo / task_dir / "spec.md").exists())

    def test_refuses_task_dir_of_another_checkout_when_draft_is_elsewhere(self):
        other_repo = self.temp_root / "other"
        other_repo.mkdir()
        self.git("init", "-q", "-b", "main", cwd=other_repo)
        other_task = other_repo / PLANS / "LED-5-yield-view"
        other_task.mkdir(parents=True)
        (other_task / "04-exploration.md").write_text("uncommitted exploration\n")
        adr = self.write(f"{DECISIONS}/a.md", GOOD_ADR)

        result = self.run_flow("finish", str(adr), "--task-dir", str(other_task), cwd=other_repo)

        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("not exactly one slug", result.stdout)
        self.assertTrue((other_task / "04-exploration.md").exists())

    def test_refuses_path_not_directly_under_plans_dir(self):
        self.make_task_dir()
        self.write(f"{DECISIONS}/keep.md", "keep\n")

        self.assert_refused(DECISIONS, "not exactly one slug")
        self.assert_refused(f"{PLANS}/LED-5-yield-view/sub", "not exactly one slug")
        self.assert_refused(PLANS, "not exactly one slug")
        self.assert_refused(".", "not exactly one slug")
        self.assert_refused("docs", "not exactly one slug")
        self.assertTrue((self.repo / DECISIONS / "keep.md").exists())
        self.assertTrue((self.repo / PLANS / "LED-5-yield-view" / "spec.md").exists())

    def test_refuses_dotdot_escape(self):
        self.make_task_dir()

        self.assert_refused(f"{PLANS}/../decisions", "not exactly one slug")
        self.assert_refused(f"{PLANS}/LED-5-yield-view/..", "not exactly one slug")
        self.assertTrue((self.repo / PLANS / "LED-5-yield-view").exists())

    def test_refuses_path_outside_repo(self):
        outside = self.temp_root / "outside" / "x"
        outside.mkdir(parents=True)
        (outside / "f.md").write_text("x\n")

        self.assert_refused(str(outside), "not exactly one slug")
        self.assertTrue((outside / "f.md").exists())

    def test_refuses_plans_dir_of_another_repo(self):
        other_repo = self.temp_root / "other"
        (other_repo / PLANS / "LED-9-x").mkdir(parents=True)

        self.assert_refused(str(other_repo / PLANS / "LED-9-x"), "not exactly one slug")
        self.assertTrue((other_repo / PLANS / "LED-9-x").exists())

    def test_refuses_slug_outside_grammar(self):
        for bad_slug in (".hidden", "has space", "a;b", "-lead", "a$b", "a.b"):
            with self.subTest(slug=bad_slug):
                (self.repo / PLANS / bad_slug).mkdir(parents=True, exist_ok=True)

                self.assert_refused(f"{PLANS}/{bad_slug}", "task-dir grammar")
                self.assertTrue((self.repo / PLANS / bad_slug).exists())

    def test_refuses_symlink_task_dir(self):
        victim = self.repo / "victim"
        victim.mkdir()
        (victim / "precious.txt").write_text("x\n")
        (self.repo / PLANS).mkdir(parents=True)
        (self.repo / PLANS / "LED-5-link").symlink_to(victim)

        self.assert_refused(f"{PLANS}/LED-5-link", "symlink")
        self.assertTrue((victim / "precious.txt").exists())
        self.assertTrue((self.repo / PLANS / "LED-5-link").is_symlink())

    def test_refuses_when_plans_dir_is_symlink(self):
        victim = self.repo / "victim"
        (victim / "LED-5-x").mkdir(parents=True)
        (self.repo / "docs").mkdir()
        (self.repo / PLANS).symlink_to(victim)

        self.assert_refused(f"{PLANS}/LED-5-x", "symlink")
        self.assertTrue((victim / "LED-5-x").exists())

    def test_refuses_uncommitted_file_outside_plan_files(self):
        task_dir = self.make_task_dir()
        self.write(f"{task_dir}/notes.txt", "scratch\n")

        self.assert_refused(task_dir, "not plan files: " + f"{task_dir}/notes.txt")
        self.assertTrue((self.repo / task_dir / "notes.txt").exists())

    def test_refuses_numbered_user_note(self):
        task_dir = self.make_task_dir()
        self.write(f"{task_dir}/07-my-rollout-notes.md", "keep me\n")

        self.assert_refused(task_dir, "07-my-rollout-notes.md")
        self.assertTrue((self.repo / task_dir / "07-my-rollout-notes.md").exists())

    def test_refuses_committed_clean_non_plan_file(self):
        task_dir = self.make_task_dir()
        self.write(f"{task_dir}/diagram.png", "v1\n")
        self.git("add", PLANS)
        self.git("commit", "-q", "-m", "diagram")

        self.assert_refused(task_dir, "diagram.png")
        self.assertTrue((self.repo / task_dir / "diagram.png").exists())

    def test_refuses_deleted_committed_non_plan_file(self):
        task_dir = self.make_task_dir()
        self.write(f"{task_dir}/diagram.png", "v1\n")
        self.git("add", PLANS)
        self.git("commit", "-q", "-m", "diagram")
        (self.repo / task_dir / "diagram.png").unlink()

        self.assert_refused(task_dir, "diagram.png")
        self.assertTrue((self.repo / task_dir / "spec.md").exists())

    def test_refuses_uncommitted_nested_file(self):
        task_dir = self.make_task_dir()
        self.write(f"{task_dir}/sub/05-plan-review-r1.md", "nested\n")

        self.assert_refused(task_dir, "not plan files")

    def test_refuses_modified_tracked_non_plan_file(self):
        self.write(f"{PLANS}/LED-5-x/diagram.png", "v1\n")
        self.write(f"{PLANS}/LED-5-x/spec.md", "s\n")
        self.git("add", PLANS)
        self.git("commit", "-q", "-m", "plan")
        self.write(f"{PLANS}/LED-5-x/diagram.png", "v2\n")

        self.assert_refused(f"{PLANS}/LED-5-x", "diagram.png")

    def test_refuses_ignored_file(self):
        task_dir = self.make_task_dir()
        self.write(".gitignore", "*.log\n")
        self.git("add", ".gitignore")
        self.git("commit", "-q", "-m", "ignore")
        self.write(f"{task_dir}/run.log", "log\n")

        self.assert_refused(task_dir, "run.log")

    def test_refuses_task_dir_that_is_its_own_git_repo(self):
        task_dir = self.make_task_dir(commit=False)
        self.git("init", "-q", cwd=self.repo / task_dir)

        self.assert_refused(task_dir, "belongs to the git repository")
        self.assertTrue((self.repo / task_dir / "spec.md").exists())

    def test_refuses_when_plans_dir_is_its_own_git_repo(self):
        self.write(f"{PLANS}/LED-5-x/spec.md", "s\n")
        self.git("init", "-q", cwd=self.repo / PLANS)
        self.write(f"{PLANS}/LED-5-x/04-exploration.md", "uncommitted\n")

        self.assert_refused(f"{PLANS}/LED-5-x", "belongs to the git repository")
        self.assertTrue((self.repo / PLANS / "LED-5-x" / "04-exploration.md").exists())

    def test_refuses_when_docs_dir_is_its_own_git_repo(self):
        self.write(f"{PLANS}/LED-5-x/spec.md", "s\n")
        self.git("init", "-q", cwd=self.repo / "docs")
        adr = self.write("ADR.md", GOOD_ADR)

        result = self.run_flow("finish", str(adr), "--task-dir", self.absolute(f"{PLANS}/LED-5-x"))

        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("belongs to the git repository", result.stdout)
        self.assertTrue((self.repo / PLANS / "LED-5-x" / "spec.md").exists())

    def test_refuses_skip_worktree_file_with_hidden_edits(self):
        task_dir = self.make_task_dir()
        self.git("update-index", "--skip-worktree", f"{task_dir}/spec.md")
        self.write(f"{task_dir}/spec.md", "edits git status cannot see\n")

        self.assert_refused(task_dir, "hidden from git status")
        self.assertEqual((self.repo / task_dir / "spec.md").read_text(), "edits git status cannot see\n")

    def test_refuses_assume_unchanged_file(self):
        task_dir = self.make_task_dir()
        self.git("update-index", "--assume-unchanged", f"{task_dir}/spec.md")

        self.assert_refused(task_dir, "hidden from git status")

    def test_refuses_staged_new_plan_file_and_leaves_it_staged(self):
        task_dir = self.make_task_dir()
        self.write(f"{task_dir}/04-exploration.md", "new\n")
        self.git("add", f"{task_dir}/04-exploration.md")

        self.assert_refused(task_dir, f"STOP: staged entries in the task dir: {task_dir}/04-exploration.md")
        self.assertEqual(self.git("diff", "--cached", "--name-only").split(), [f"{task_dir}/04-exploration.md"])
        self.assertTrue((self.repo / task_dir / "04-exploration.md").exists())

    def test_refuses_staged_rename_and_names_the_new_path(self):
        task_dir = self.make_task_dir()
        self.git("mv", f"{task_dir}/02-research.md", f"{task_dir}/04-exploration.md")

        self.assert_refused(task_dir, f"STOP: staged entries in the task dir: {task_dir}/04-exploration.md")
        self.assertTrue((self.repo / task_dir / "04-exploration.md").exists())

    def test_an_intent_to_add_rename_is_not_reported_as_a_staged_entry(self):
        task_dir = self.make_task_dir()
        (self.repo / task_dir / "02-research.md").rename(self.repo / task_dir / "04-exploration.md")
        self.git("add", "-N", f"{task_dir}/04-exploration.md")
        adr = self.write(f"{DECISIONS}/LED-5-yield-view.md", GOOD_ADR)

        result = self.run_flow("finish", str(adr), "--task-dir", self.absolute(task_dir))

        self.assertNotIn("STOP: staged entries", result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_refuses_missing_dir(self):
        self.assert_refused(f"{PLANS}/LED-5-gone", "not a directory")

    def test_refuses_when_draft_is_inside_task_dir(self):
        task_dir = self.make_task_dir()
        adr = self.write(f"{task_dir}/05-adr.md", GOOD_ADR)

        result = self.run_flow("finish", str(adr), "--task-dir", self.absolute(task_dir))

        self.assertEqual(result.returncode, 2)
        self.assertTrue((self.repo / task_dir / "spec.md").exists())

    def test_failed_check_keeps_task_dir(self):
        task_dir = self.make_task_dir()
        adr = self.write(f"{DECISIONS}/bad.md", GOOD_ADR.replace("- valid while single-region\n", ""))

        result = self.run_flow("finish", str(adr), "--task-dir", self.absolute(task_dir))

        self.assertEqual(result.returncode, 1)
        self.assertIn("Nothing deleted", result.stdout)
        self.assertTrue((self.repo / task_dir / "spec.md").exists())

    def test_failed_check_still_prints_notes(self):
        task_dir = self.make_task_dir()
        long_body = GOOD_ADR.replace("- valid while single-region\n", "") + "".join(f"- more {n}\n" for n in range(90))
        adr = self.write(f"{DECISIONS}/long.md", long_body)

        result = self.run_flow("finish", str(adr), "--task-dir", self.absolute(task_dir))

        self.assertEqual(result.returncode, 1)
        self.assertIn("note:", result.stdout)


if __name__ == "__main__":
    unittest.main()
