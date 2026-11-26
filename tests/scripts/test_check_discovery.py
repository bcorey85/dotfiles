"""Checks for code/check_discovery.py: the full check found from a repo's own files."""
import json
import pathlib
import sys
import tempfile
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.CODE_DIR))
import check_discovery


def assert_lint_and_make_test_are_separate_parts(test, command):
    # A failing lint step must not skip the repo's own tests.
    test.assertNotIn("npm run lint && make test", command)
    test.assertIn("PART package exit", command)
    test.assertIn("PART tests exit", command)


class CheckDiscoveryTest(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.repo = pathlib.Path(scratch.name)

    def write(self, name, text):
        (self.repo / name).write_text(text)

    def write_package(self, **package):
        self.write("package.json", json.dumps(package))

    def discovered(self):
        return check_discovery.discovered_check_command(self.repo)

    def test_a_makefile_check_target_gives_make_check_ahead_of_a_package_check_script(self):
        self.write("Makefile", ".PHONY: check\ncheck: lint test\n\t@echo ok\n")
        self.write_package(scripts={"check": "tsc"})

        self.assertEqual("make check", self.discovered())

    def test_a_makefile_with_no_check_or_test_target_gives_none(self):
        self.write("Makefile", ".PHONY: build\nbuild:\n\t@echo ok\n")

        self.assertIsNone(self.discovered())

    def test_a_unittest_repo_with_a_makefile_test_target_runs_make_test_not_a_pytest_guess(self):
        self.write("Makefile", ".PHONY: test\ntest:\n\tpython3 -m unittest discover -s tests\n")
        (self.repo / "tests").mkdir()
        (self.repo / ".venv" / "bin").mkdir(parents=True)
        (self.repo / ".venv" / "bin" / "python").write_text("")

        self.assertEqual("make test", self.discovered())

    def test_a_makefile_test_target_wins_over_a_package_test_script_and_its_runner_dependency(self):
        self.write("Makefile", "test:\n\t@echo ok\n")
        self.write_package(scripts={"lint": "eslint .", "test": "vitest"}, devDependencies={"vitest": "^2"})

        assert_lint_and_make_test_are_separate_parts(self, self.discovered())

    def test_a_package_test_script_wins_over_a_pytest_guess(self):
        self.write_package(scripts={"test": "node --test"})
        (self.repo / "tests").mkdir()

        self.assertEqual("npm test", self.discovered())

    def test_a_package_check_script_runs_with_the_package_manager_of_the_lock_file(self):
        self.write_package(scripts={"check": "tsc"})
        cases = [("npm", None), ("pnpm", "pnpm-lock.yaml"), ("yarn", "yarn.lock")]
        for manager, lock_file in cases:
            with self.subTest(manager=manager):
                for stale in ("pnpm-lock.yaml", "yarn.lock"):
                    (self.repo / stale).unlink(missing_ok=True)
                if lock_file:
                    self.write(lock_file, "")

                self.assertEqual(f"{manager} run check", self.discovered())

    def test_a_package_with_no_check_script_gets_its_lint_type_check_and_vitest_run(self):
        self.write("pnpm-lock.yaml", "")
        self.write_package(scripts={"lint": "eslint .", "typecheck": "tsc --noEmit"},
                           devDependencies={"vitest": "^2"})

        self.assertEqual("pnpm run lint && pnpm run typecheck && pnpm exec vitest run", self.discovered())

    def test_a_package_with_only_a_test_script_runs_it_with_the_package_manager(self):
        self.write("yarn.lock", "")
        self.write_package(scripts={"test": "node --test"})

        self.assertEqual("yarn test", self.discovered())

    def test_a_django_repo_gets_ruff_and_manage_py_test_through_the_lock_file_runner(self):
        self.write("manage.py", "")
        self.write("pyproject.toml", "[tool.ruff]\nline-length = 100\n")
        self.write("uv.lock", "")

        self.assertEqual("uv run ruff check && uv run python manage.py test --noinput", self.discovered())

    def test_a_shell_wrapper_manage_py_runs_through_its_shell_not_python(self):
        self.write("manage.py", "#!/usr/bin/env bash\ncd backend && python manage.py \"$@\"\n")
        self.write("Pipfile.lock", "{}")

        self.assertEqual("pipenv run bash manage.py test --noinput", self.discovered())

    def test_a_python_manage_py_with_a_shebang_runs_through_python(self):
        self.write("manage.py", "#!/usr/bin/env python\nimport sys\n")

        self.assertEqual("python3 manage.py test --noinput", self.discovered())

    def test_a_pytest_repo_gets_pytest(self):
        self.write("pytest.ini", "[pytest]\naddopts = -q\n")

        self.assertEqual("python3 -m pytest", self.discovered())

    def test_a_repo_with_no_recognised_file_gives_none(self):
        self.write("README.md", "# hi\n")

        self.assertIsNone(self.discovered())


class ChangedPathPartsTest(unittest.TestCase):
    # A repo with a package part (lint script) and a Python part (pytest).
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.repo = pathlib.Path(scratch.name)
        self.write("package.json", json.dumps({"scripts": {"lint": "eslint ."}}))
        self.write("pytest.ini", "[pytest]\naddopts = -q\n")

    def write(self, name, text):
        (self.repo / name).write_text(text)

    def discovered(self):
        return check_discovery.discovered_check_command(self.repo)

    def discovered_for(self, changed_paths):
        return check_discovery.discovered_check_command(self.repo, changed_paths)

    def assert_runs_each_part_alone(self, command):
        self.assertIn("npm run lint", command)
        self.assertIn("python3 -m pytest", command)
        self.assertIn("FAILED PARTS:", command)

    def test_a_frontend_only_change_gives_only_the_package_part(self):
        paths = ["src/App.tsx", "src/app.css", "package.json"]
        self.assertEqual("npm run lint", self.discovered_for(paths))

    def test_a_backend_only_change_gives_only_the_python_part(self):
        paths = ["app/views.py", "pytest.ini", "requirements.txt"]
        self.assertEqual("python3 -m pytest", self.discovered_for(paths))

    def test_a_template_or_fixture_change_runs_both_parts(self):
        for paths in (["app/templates/page.html"], ["app/fixtures/seed.json"], ["app/templates/page.html", "a.py"]):
            with self.subTest(paths=paths):
                self.assert_runs_each_part_alone(self.discovered_for(paths))

    def test_a_root_config_change_runs_both_parts(self):
        for paths in (["Makefile.local"], ["pnpm-lock.yaml"], [".github/workflows/ci.yml"],
                      ["src/App.tsx", "Makefile.local"]):
            with self.subTest(paths=paths):
                self.assert_runs_each_part_alone(self.discovered_for(paths))

    def test_a_code_file_under_a_docs_folder_keeps_its_kind(self):
        paths = ["src/docs/Page.tsx", "app/views.py"]
        self.assert_runs_each_part_alone(self.discovered_for(paths))

    def test_doc_paths_beside_frontend_files_do_not_widen_the_check_to_every_part(self):
        paths = ["src/App.tsx", "docs/plans/x/plan.md"]
        self.assertEqual("npm run lint", self.discovered_for(paths))

    def test_doc_paths_beside_python_files_do_not_widen_the_check_to_every_part(self):
        paths = ["app/views.py", "docs/x.md"]
        self.assertEqual("python3 -m pytest", self.discovered_for(paths))

    def test_a_docs_only_change_runs_every_part(self):
        self.assert_runs_each_part_alone(self.discovered_for(["docs/plans/x/plan.md", "README.md"]))

    def test_no_changed_paths_given_runs_both_parts(self):
        self.assert_runs_each_part_alone(self.discovered_for(None))
        self.assert_runs_each_part_alone(self.discovered_for([]))
        self.assert_runs_each_part_alone(self.discovered())

    def test_frontend_and_backend_changes_run_both_parts(self):
        self.assert_runs_each_part_alone(self.discovered_for(["src/a.ts", "app/b.py"]))

    def test_a_change_that_touches_no_existing_part_runs_the_parts_there_are(self):
        pathlib.Path(self.repo / "package.json").unlink()

        self.assertEqual("python3 -m pytest", self.discovered_for(["src/App.tsx"]))

    def test_the_repos_own_test_command_is_a_part_of_its_own(self):
        self.write("Makefile", "test:\n\t@echo ok\n")

        command = self.discovered_for(["src/App.tsx"])

        assert_lint_and_make_test_are_separate_parts(self, command)


if __name__ == "__main__":
    unittest.main()
