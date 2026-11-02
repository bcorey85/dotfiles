"""Checks for code/check_discovery.py: the full check found from a repo's own files."""
import json
import pathlib
import sys
import tempfile
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.CODE_DIR))
import check_discovery


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

    def test_a_makefile_with_no_check_target_gives_none(self):
        self.write("Makefile", ".PHONY: check\ntest:\n\t@echo ok\n")

        self.assertIsNone(self.discovered())

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

    def test_a_pytest_repo_gets_pytest(self):
        self.write("pytest.ini", "[pytest]\naddopts = -q\n")

        self.assertEqual("python3 -m pytest", self.discovered())

    def test_a_repo_with_no_recognised_file_gives_none(self):
        self.write("README.md", "# hi\n")

        self.assertIsNone(self.discovered())


if __name__ == "__main__":
    unittest.main()
