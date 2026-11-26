"""lib/single_caller_census.py: the three kinds of dead weight a branch adds, found in a real git repo."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import single_caller_census

SCRIPT = pathlib.Path(os.environ.get("SINGLE_CALLER_CENSUS_PATH") or toolkit_paths.LIB_DIR / "single_caller_census.py")
GIT_IDENTITY = ("-c", "user.name=Test", "-c", "user.email=test@example.com")

BASE_SOURCE = '''def existing(value):
    print(value)
    return value
'''

BRANCH_SOURCE = '''from typing import NamedTuple

from base import existing


class Row(NamedTuple):
    name: str
    unused_field: int


def forwarder(value):
    return existing(value)


def entry(items):
    print(forwarder(items))


def old_helper(value):
    total = value + 1
    return total


def run(items):
    print(Row("a", 1).name)
    return old_helper(items)
'''

# The uncommitted change: a newer helper, and the one caller of old_helper now also calls it with the same argument.
WORK_SOURCE = BRANCH_SOURCE.replace(
    "    return old_helper(items)\n",
    "    print(old_helper(items))\n    return new_helper(items)\n") + '''

def new_helper(value):
    total = value + 2
    return total
'''

NEGATIVE_BRANCH_SOURCE = '''from typing import NamedTuple

from base import existing


class Record(NamedTuple):
    by_attribute: int
    by_key: int


def twice(value):
    return existing(value)


def first_user(value):
    print(twice(value))
    return Record(1, 2).by_attribute


def second_user(value):
    print(twice(value))
    return {"by_key": 1}["by_key"]


def other_old(value):
    total = value + 1
    return total


def caller(value):
    print(other_old(value))
    return value
'''

# The caller of other_old calls the newer helper with another argument.
NEGATIVE_WORK_SOURCE = NEGATIVE_BRANCH_SOURCE.replace(
    "    return value\n", "    return newer(value + 1)\n") + '''

def newer(value):
    total = value + 2
    return total
'''


FORWARDER_USE = "\n\ndef use(value):\n    print(lone(value))\n"

# Each source holds a candidate `lone` that one rule of the forwarder census excludes.
NOT_A_FORWARDER_SOURCES = {
    "decorated": "@staticmethod\ndef lone(value):\n    return existing(value)\n" + FORWARDER_USE,
    "dunder name": ("def __lone__(value):\n    return existing(value)\n\n\n"
                    "def use(value):\n    print(__lone__(value))\n"),
    "two statements": "def lone(value):\n    print(value)\n    return existing(value)\n" + FORWARDER_USE,
    "assignment body": "def lone(value):\n    result = existing(value)\n" + FORWARDER_USE,
    "two callers": "def lone(value):\n    return existing(value)\n" + FORWARDER_USE + "\n\ndef again(value):\n"
                   "    print(lone(value))\n",
    "no caller": "def lone(value):\n    return existing(value)\n",
    "referenced, not called": "def lone(value):\n    return existing(value)\n\n\ndef use(value):\n    print(lone)\n",
}

# Each source holds a `lone` forwarder with one caller that the census lists.
FORWARDER_SOURCES = {
    "expression statement call": "def lone(value):\n    print(value)\n" + FORWARDER_USE,
    "docstring then return": 'def lone(value):\n    """Forward."""\n    return existing(value)\n' + FORWARDER_USE,
}

# Each source holds a record class with one field that nothing reads.
RECORD_SOURCES = {
    "TypedDict": "from typing import TypedDict\n\n\nclass Row(TypedDict):\n    unused_field: int\n",
    "Protocol": "from typing import Protocol\n\n\nclass Row(Protocol):\n    unused_field: int\n",
    "dataclass": "from dataclasses import dataclass\n\n\n@dataclass\nclass Row:\n    unused_field: int\n",
    "dataclass call": ("import dataclasses\n\n\n@dataclasses.dataclass(frozen=True)\n"
                       "class Row:\n    unused_field: int\n"),
}

CALLERS_SOURCE = '''def old_helper(value):
    total = value + 1
    return total


def caller_a(items):
    return old_helper(items)


def caller_b(items):
    return old_helper(items)
'''


def git(repo, *args, env=None):
    done = subprocess.run(["git", *GIT_IDENTITY, *args], cwd=repo, capture_output=True, text=True, check=True,
                          env=env)
    return done.stdout.strip()


def commit_at(repo, date, message):
    """Commit everything with the author time set to `date`, so blame orders the lines."""
    env = {**os.environ, "GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date}
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", message, env=env)


def write(repo, name, text):
    pathlib.Path(repo, name).write_text(text, encoding="utf-8")


def make_repo(directory, branch_source, work_source, object_format="sha1"):
    """A repo with a base commit, a branch commit of app.py and an uncommitted rewrite of it. Returns the base sha."""
    git(directory, "init", "-q", "-b", "main", f"--object-format={object_format}")
    write(directory, "base.py", BASE_SOURCE)
    git(directory, "add", ".")
    git(directory, "commit", "-q", "-m", "base")
    base = git(directory, "rev-parse", "HEAD")
    write(directory, "app.py", branch_source)
    git(directory, "add", ".")
    git(directory, "commit", "-q", "-m", "branch")
    write(directory, "app.py", work_source)
    return base


def run_cli(repo, *args):
    return subprocess.run([sys.executable, str(SCRIPT), "--repo", str(repo), *args], capture_output=True, text=True)


class SingleCallerCensusTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

    def test_lists_one_entry_of_each_kind_on_the_branch_and_none_on_the_base(self):
        base = make_repo(self.directory.name, BRANCH_SOURCE, WORK_SOURCE)
        done = run_cli(self.directory.name, "--base", base)
        self.assertEqual(done.returncode, 0, done.stderr)
        entries = json.loads(done.stdout)["entries"]
        found = [(entry["kind"], entry["path"], entry["line"], entry["name"]) for entry in entries]
        expected = [("unread-field", "app.py", 8, "Row.unused_field"),
                    ("single-caller-forwarder", "app.py", 11, "forwarder"),
                    (single_caller_census.SUPERSEDED_HELPER, "app.py", 19, "old_helper")]
        self.assertEqual(found, expected)

        git(self.directory.name, "reset", "-q", "--hard", base)
        at_base = run_cli(self.directory.name, "--base", base)
        self.assertEqual(json.loads(at_base.stdout)["entries"], [], "the base commit alone adds nothing")

    def test_a_used_forwarder_a_read_field_and_a_different_argument_are_not_listed(self):
        base = make_repo(self.directory.name, NEGATIVE_BRANCH_SOURCE, NEGATIVE_WORK_SOURCE)
        done = run_cli(self.directory.name, "--base", base)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout)["entries"], [])

    def test_untracked_file_lines_all_count_as_added(self):
        make_repo(self.directory.name, BRANCH_SOURCE, BRANCH_SOURCE)
        write(self.directory.name, "fresh.py", "def lone(value):\n    return existing(value)\n\n\ndef use(value):\n"
              "    print(lone(value))\n    return value\n")
        result = single_caller_census.census(self.directory.name)
        names = [entry.name for entry in result.entries if entry.path == "fresh.py"]
        self.assertEqual(names, ["lone"])

    def test_an_untracked_file_lists_an_unread_field(self):
        make_repo(self.directory.name, BRANCH_SOURCE, BRANCH_SOURCE)
        write(self.directory.name, "fresh.py", RECORD_SOURCES["TypedDict"])
        result = single_caller_census.census(self.directory.name)
        found = [(entry.kind, entry.name) for entry in result.entries if entry.path == "fresh.py"]
        self.assertEqual(found, [("unread-field", "Row.unused_field")])

    def test_an_untracked_helper_and_its_replacement_list_the_unread_field_of_the_file(self):
        make_repo(self.directory.name, BRANCH_SOURCE, BRANCH_SOURCE)
        both_calls = "    print(old_helper(items))\n    return new_helper(items)\n"
        new_helper = "\n\ndef new_helper(value):\n    return value\n"
        both = CALLERS_SOURCE.replace("    return old_helper(items)\n", both_calls) + new_helper
        write(self.directory.name, "fresh.py", RECORD_SOURCES["TypedDict"] + "\n\n" + both)
        result = single_caller_census.census(self.directory.name)
        found = [(entry.kind, entry.name) for entry in result.entries if entry.path == "fresh.py"]
        self.assertEqual(found, [("unread-field", "Row.unused_field")], "no superseded-helper entry either")

    def test_an_old_helper_called_with_no_argument_is_not_superseded(self):
        old_call = "    return old_helper(items)\n"
        both_calls = "    print(old_helper())\n    return new_helper(items)\n"
        work_source = CALLERS_SOURCE.replace(old_call, both_calls) + "\n\ndef new_helper(value):\n    return value\n"
        self.assertEqual(self.superseded(work_source), [])

    def test_a_caller_that_recurses_with_the_helper_arguments_is_not_superseded(self):
        old_call = "    return old_helper(items)\n"
        recursive_calls = "    print(old_helper(items))\n    return caller_a(items, 1)\n"
        work_source = CALLERS_SOURCE.split("\n\ndef caller_b")[0].replace(old_call, recursive_calls) + "\n"
        base = make_repo(self.directory.name, CALLERS_SOURCE, work_source)
        result = single_caller_census.census(self.directory.name, base)
        self.assertEqual(result.entries, [])

    def test_a_function_that_does_not_meet_every_forwarder_rule_is_not_listed(self):
        for label, source in NOT_A_FORWARDER_SOURCES.items():
            with self.subTest(label), tempfile.TemporaryDirectory() as directory:
                base = make_repo(directory, source, source)
                result = single_caller_census.census(directory, base)
                self.assertEqual(result.entries, [], label)

    def test_each_forwarder_shape_is_listed(self):
        for label, source in FORWARDER_SOURCES.items():
            with self.subTest(label), tempfile.TemporaryDirectory() as directory:
                base = make_repo(directory, source, source)
                result = single_caller_census.census(directory, base)
                found = [(entry.kind, entry.name) for entry in result.entries]
                self.assertEqual(found, [("single-caller-forwarder", "lone")], label)

    def test_a_textconv_driver_does_not_change_the_diff_or_the_blame(self):
        directory = self.directory.name
        git(directory, "init", "-q", "-b", "main")
        git(directory, "config", "diff.broken.textconv", "false")
        write(directory, ".gitattributes", "*.py diff=broken\n")
        write(directory, "base.py", BASE_SOURCE)
        git(directory, "add", ".")
        git(directory, "commit", "-q", "-m", "base")
        base = git(directory, "rev-parse", "HEAD")
        source = RECORD_SOURCES["TypedDict"]
        write(directory, "app.py", source)
        commit_at(directory, "2020-01-01T00:00:00", "branch")
        result = single_caller_census.census(directory, base)
        found = [(entry.kind, entry.name) for entry in result.entries]
        self.assertEqual(found, [("unread-field", "Row.unused_field")])

    def test_a_field_that_is_only_assigned_is_still_listed(self):
        source = RECORD_SOURCES["TypedDict"] + "\n\ndef write_it(row):\n    row.unused_field = 1\n"
        base = make_repo(self.directory.name, source, source)
        result = single_caller_census.census(self.directory.name, base)
        found = [(entry.kind, entry.name) for entry in result.entries]
        self.assertEqual(found, [("unread-field", "Row.unused_field")])

    def test_calls_in_a_decorator_and_a_default_belong_to_the_enclosing_scope(self):
        source = (
            "def outer():\n    @deco(1)\n    def inner(a=helper(2)):\n        pass\n\n\n"
            "@top(3)\ndef later():\n    pass\n"
        )
        index = single_caller_census._Collector("m.py", single_caller_census.Index())
        index.visit(single_caller_census.ast.parse(source))
        callers = {name: [reference.caller for reference in references]
                   for name, references in index.index.references.items()}
        self.assertEqual([caller.name for caller in callers["deco"]], ["outer"])
        self.assertEqual([caller.name for caller in callers["helper"]], ["outer"])
        self.assertEqual(callers["top"], [None])

    def test_a_helper_and_its_replacement_added_in_one_commit_are_not_superseded(self):
        directory = self.directory.name
        git(directory, "init", "-q", "-b", "main")
        write(directory, "base.py", BASE_SOURCE)
        commit_at(directory, "2019-01-01T00:00:00", "base")
        base = git(directory, "rev-parse", "HEAD")
        both_calls = "    print(old_helper(items))\n    return new_helper(items)\n"
        source = (CALLERS_SOURCE.split("\n\ndef caller_b")[0].replace("    return old_helper(items)\n", both_calls)
                  + "\n\ndef new_helper(value):\n    return value\n")
        write(directory, "app.py", source)
        commit_at(directory, "2020-01-01T00:00:00", "helper and replacement together")
        result = single_caller_census.census(directory, base)
        found = [entry for entry in result.entries if entry.kind == single_caller_census.SUPERSEDED_HELPER]
        self.assertEqual(found, [])

    def test_a_forwarder_already_on_the_base_is_not_listed(self):
        source = "def lone(value):\n    return existing(value)\n" + FORWARDER_USE
        make_repo(self.directory.name, source, source)
        result = single_caller_census.census(self.directory.name, "HEAD")
        self.assertEqual(result.entries, [])

    def test_a_forwarder_the_branch_only_partly_changed_is_not_listed(self):
        branch_source = "def lone(value):\n    return existing(value)\n" + FORWARDER_USE
        work_source = branch_source.replace("    return existing", '    """Forward."""\n    return existing', 1)
        make_repo(self.directory.name, branch_source, work_source)
        result = single_caller_census.census(self.directory.name, "HEAD")
        self.assertEqual(result.entries, [])

    def test_only_a_field_on_an_added_line_is_listed(self):
        branch_source = "from typing import NamedTuple\n\n\nclass Row(NamedTuple):\n    old_unused: int\n"
        work_source = branch_source + "    new_unused: int\n"
        make_repo(self.directory.name, branch_source, work_source)
        result = single_caller_census.census(self.directory.name, "HEAD")
        found = [(entry.kind, entry.name) for entry in result.entries]
        self.assertEqual(found, [("unread-field", "Row.new_unused")])

    def test_each_record_class_kind_lists_its_unread_field(self):
        for label, source in RECORD_SOURCES.items():
            with self.subTest(label), tempfile.TemporaryDirectory() as directory:
                base = make_repo(directory, source, source)
                result = single_caller_census.census(directory, base)
                found = [(entry.kind, entry.name) for entry in result.entries]
                self.assertEqual(found, [("unread-field", "Row.unused_field")], label)

    def test_a_plain_class_field_is_not_listed(self):
        source = "class Row:\n    unused_field: int\n"
        base = make_repo(self.directory.name, source, source)
        self.assertEqual(single_caller_census.census(self.directory.name, base).entries, [])

    def test_a_helper_is_superseded_only_when_every_caller_calls_the_newer_helper(self):
        both = CALLERS_SOURCE.replace("    return old_helper(items)\n", "    print(old_helper(items))\n"
                                      "    return new_helper(items)\n") + '''

def new_helper(value):
    total = value + 2
    return total
'''
        only_a = both.replace("def caller_b(items):\n    print(old_helper(items))\n    return new_helper(items)\n",
                              "def caller_b(items):\n    return old_helper(items)\n")
        cases = {"every caller": (both, ["old_helper"]), "one caller only": (only_a, [])}
        for label, (work_source, expected) in cases.items():
            with self.subTest(label), tempfile.TemporaryDirectory() as directory:
                base = make_repo(directory, CALLERS_SOURCE, work_source)
                result = single_caller_census.census(directory, base)
                found = [entry.name for entry in result.entries if entry.kind == single_caller_census.SUPERSEDED_HELPER]
                self.assertEqual(found, expected, label)

    def superseded(self, work_source):
        base = make_repo(self.directory.name, CALLERS_SOURCE, work_source)
        result = single_caller_census.census(self.directory.name, base)
        return [entry for entry in result.entries if entry.kind == single_caller_census.SUPERSEDED_HELPER]

    def test_a_helper_also_called_at_module_level_is_not_superseded(self):
        both_calls = "    print(old_helper(items))\n    return new_helper(items)\n"
        work_source = (CALLERS_SOURCE.replace("    return old_helper(items)\n", both_calls)
                       + "\n\ndef new_helper(value):\n    return value\n\n\nTOP = old_helper(1)\n")
        self.assertEqual(self.superseded(work_source), [])

    def test_the_detail_names_every_newer_helper(self):
        both_calls = "    print(old_helper(items))\n    new_a(items)\n    return new_b(items)\n"
        work_source = (CALLERS_SOURCE.replace("    return old_helper(items)\n", both_calls)
                       + "\n\ndef new_a(value):\n    return value\n\n\ndef new_b(value):\n    return value\n")
        found = self.superseded(work_source)
        self.assertEqual([entry.name for entry in found], ["old_helper"])
        self.assertIn("`new_a`", found[0].detail)
        self.assertIn("`new_b`", found[0].detail)

    def test_keyword_arguments_count_and_the_newer_helper_may_take_more(self):
        old_source = CALLERS_SOURCE.replace("old_helper(items)", "old_helper(value=items)")
        both_calls = "    print(old_helper(value=items))\n    return new_helper(value=items, extra=1)\n"
        work_source = (old_source.replace("    return old_helper(value=items)\n", both_calls)
                       + "\n\ndef new_helper(value, extra):\n    return value\n")
        self.assertEqual([entry.name for entry in self.superseded(work_source)], ["old_helper"])

    def test_one_helper_call_the_newer_helper_does_not_cover_is_not_superseded(self):
        both_calls = "    print(old_helper(items))\n    print(old_helper(other))\n    return new_helper(items, 1)\n"
        work_source = (CALLERS_SOURCE.replace("    return old_helper(items)\n", both_calls)
                       + "\n\ndef new_helper(value, extra):\n    return value\n")
        self.assertEqual(self.superseded(work_source), [])

    def test_a_helper_is_superseded_when_every_commit_is_dated(self):
        directory = self.directory.name
        git(directory, "init", "-q", "-b", "main")
        write(directory, "base.py", BASE_SOURCE)
        commit_at(directory, "2019-01-01T00:00:00", "base")
        base = git(directory, "rev-parse", "HEAD")
        write(directory, "app.py", CALLERS_SOURCE)
        commit_at(directory, "2020-01-01T00:00:00", "old helper and callers")
        both_calls = "    print(old_helper(items))\n    return new_helper(items)\n"
        newer = (CALLERS_SOURCE.replace("    return old_helper(items)\n", both_calls)
                 + "\n\ndef new_helper(value):\n    return value\n")
        write(directory, "app.py", newer)
        commit_at(directory, "2021-01-01T00:00:00", "newer helper")
        result = single_caller_census.census(directory, base)
        found = [entry.name for entry in result.entries if entry.kind == single_caller_census.SUPERSEDED_HELPER]
        self.assertEqual(found, ["old_helper"])

    def test_a_helper_called_with_an_older_helper_is_not_superseded(self):
        directory = self.directory.name
        git(directory, "init", "-q", "-b", "main")
        write(directory, "base.py", BASE_SOURCE)
        commit_at(directory, "2019-01-01T00:00:00", "base")
        base = git(directory, "rev-parse", "HEAD")
        write(directory, "app.py", "def older(value):\n    total = value + 2\n    return total\n")
        commit_at(directory, "2020-01-01T00:00:00", "older helper")
        write(directory, "app.py", "def older(value):\n    total = value + 2\n    return total\n\n\n"
              "def old_helper(value):\n    total = value + 1\n    return total\n\n\n"
              "def caller(items):\n    print(old_helper(items))\n    return older(items)\n\n\n"
              "def other(items):\n    return older(items)\n")
        commit_at(directory, "2021-01-01T00:00:00", "newer helper and caller")
        result = single_caller_census.census(directory, base)
        found = [entry for entry in result.entries if entry.kind == single_caller_census.SUPERSEDED_HELPER]
        self.assertEqual(found, [])

    def test_a_helper_is_superseded_in_a_sha256_repo(self):
        try:
            base = make_repo(self.directory.name, BRANCH_SOURCE, WORK_SOURCE, object_format="sha256")
        except subprocess.CalledProcessError as error:
            self.skipTest(f"this git cannot make a sha256 repo: {error.stderr}")
        result = single_caller_census.census(self.directory.name, base)
        found = [entry.name for entry in result.entries if entry.kind == single_caller_census.SUPERSEDED_HELPER]
        self.assertEqual(found, ["old_helper"])

    def test_a_file_in_a_subfolder_is_read_with_paths_relative_to_that_folder(self):
        root = self.directory.name
        git(root, "init", "-q", "-b", "main")
        folder = pathlib.Path(root, "sub")
        folder.mkdir()
        write(folder, "base.py", BASE_SOURCE)
        write(folder, "app.py", "x = 1\n")
        git(root, "add", ".")
        git(root, "commit", "-q", "-m", "base")
        write(folder, "app.py", "def lone(value):\n    return existing(value)\n" + FORWARDER_USE)
        result = single_caller_census.census(str(folder), "HEAD")
        self.assertEqual([(entry.path, entry.name) for entry in result.entries], [("app.py", "lone")])

    def test_a_renamed_file_counts_as_all_added(self):
        source = "def lone(value):\n    return existing(value)\n" + FORWARDER_USE
        make_repo(self.directory.name, source, source)
        git(self.directory.name, "mv", "app.py", "moved.py")
        result = single_caller_census.census(self.directory.name, "HEAD")
        self.assertEqual([(entry.path, entry.name) for entry in result.entries], [("moved.py", "lone")])

    def test_a_deleted_typescript_file_gets_no_note(self):
        make_repo(self.directory.name, BRANCH_SOURCE, BRANCH_SOURCE)
        write(self.directory.name, "old.ts", "export const a = 1;\n")
        git(self.directory.name, "add", ".")
        git(self.directory.name, "commit", "-q", "-m", "ts")
        git(self.directory.name, "rm", "-q", "old.ts")
        result = single_caller_census.census(self.directory.name, "HEAD")
        self.assertEqual(result.notes, [])

    def test_notes_name_a_typescript_file_and_a_file_that_does_not_parse(self):
        make_repo(self.directory.name, BRANCH_SOURCE, BRANCH_SOURCE)
        write(self.directory.name, "view.ts", "export const a = 1;\n")
        write(self.directory.name, "broken.py", "def (:\n")
        result = single_caller_census.census(self.directory.name)
        self.assertTrue(any("view.ts" in note and "TypeScript" in note for note in result.notes), result.notes)
        self.assertEqual(len([note for note in result.notes if "TypeScript" in note]), 1, result.notes)
        self.assertTrue(any("broken.py" in note and "did not parse" in note for note in result.notes), result.notes)

    def test_a_file_too_deep_to_visit_is_noted_and_the_rest_is_still_read(self):
        base = make_repo(self.directory.name, BRANCH_SOURCE, BRANCH_SOURCE)
        deep_chain = " + ".join(['"a"'] * 600)
        source = f"def lone(value):\n    return existing(value)\n\n\nTOTAL = {deep_chain}\n"
        write(self.directory.name, "deep.py", source)
        git(self.directory.name, "add", ".")
        git(self.directory.name, "commit", "-q", "-m", "deep")
        result = single_caller_census.census(self.directory.name, base)
        names = [entry.name for entry in result.entries]
        self.assertIn("forwarder", names)
        self.assertNotIn("lone", names, "a half-visited file leaves no entries")
        self.assertTrue(any("deep.py" in note and "did not parse" in note for note in result.notes), result.notes)

    def test_many_typescript_files_make_one_bounded_note(self):
        make_repo(self.directory.name, BRANCH_SOURCE, BRANCH_SOURCE)
        for number in range(20):
            write(self.directory.name, f"view{number:02}.ts", "export const a = 1;\n")
        result = single_caller_census.census(self.directory.name)
        notes = [note for note in result.notes if "TypeScript" in note]
        self.assertEqual(len(notes), 1, notes)
        self.assertTrue(notes[0].startswith("20 TypeScript files were not read: view00.ts; "), notes)
        self.assertNotIn("view05.ts", notes[0])

    def test_blame_that_misses_a_line_of_a_tracked_file_raises_naming_the_path(self):
        base = make_repo(self.directory.name, BRANCH_SOURCE, WORK_SOURCE)
        original = single_caller_census.script_utils.git_output

        def git_output_without_blame_lines(repo, *command):
            if command[0] == "blame":
                return ""
            return original(repo, *command)

        single_caller_census.script_utils.git_output = git_output_without_blame_lines
        self.addCleanup(setattr, single_caller_census.script_utils, "git_output", original)
        with self.assertRaises(single_caller_census.CensusError) as caught:
            single_caller_census.census(self.directory.name, base)
        self.assertIn("app.py", str(caught.exception))

    def test_a_bad_base_exits_2_naming_the_git_command(self):
        make_repo(self.directory.name, BRANCH_SOURCE, BRANCH_SOURCE)
        done = run_cli(self.directory.name, "--base", "no-such-ref")
        self.assertEqual(done.returncode, 2)
        self.assertIn("git diff", done.stderr)

    def test_census_report_lines_keep_only_the_named_paths(self):
        base = make_repo(self.directory.name, BRANCH_SOURCE, WORK_SOURCE)
        lines = single_caller_census.census_report_lines(self.directory.name, base)
        self.assertEqual(lines[0], single_caller_census.CENSUS_HEADING)
        self.assertEqual(len(lines), 4)
        self.assertIn("app.py:8 unread-field `Row.unused_field`: field `unused_field` is never read as an "
                      "attribute or a string key", lines)
        other = single_caller_census.census_report_lines(self.directory.name, base, paths={"other.py"})
        self.assertEqual(other, [single_caller_census.CENSUS_HEADING, f"none (read against {base})"])

    def test_census_report_lines_keep_the_notes_when_paths_are_given(self):
        make_repo(self.directory.name, BRANCH_SOURCE, BRANCH_SOURCE)
        write(self.directory.name, "view.ts", "export const a = 1;\n")
        lines = single_caller_census.census_report_lines(self.directory.name, "HEAD", paths={"other.py"})
        self.assertEqual(lines, [single_caller_census.CENSUS_HEADING, "none (read against HEAD)",
                                 "note: 1 TypeScript files were not read: view.ts"])

    def test_a_census_that_cannot_run_is_reported_in_one_line(self):
        lines = single_caller_census.census_report_lines(self.directory.name, "HEAD")
        self.assertEqual(lines[0], single_caller_census.CENSUS_HEADING)
        self.assertTrue(lines[1].startswith("The census did not run:"), lines)

    def test_a_body_edit_of_a_sibling_helper_does_not_make_it_newer(self):
        directory = self.directory.name
        git(directory, "init", "-q", "-b", "main")
        write(directory, "base.py", BASE_SOURCE)
        commit_at(directory, "2019-01-01T00:00:00", "base")
        base = git(directory, "rev-parse", "HEAD")
        source = ("def first(value):\n    return value + 1\n\n\ndef second(value):\n    return value + 2\n\n\n"
                  "def caller(items):\n    print(first(items))\n    return second(items)\n")
        write(directory, "app.py", source)
        commit_at(directory, "2020-01-01T00:00:00", "two siblings")
        write(directory, "app.py", source.replace("value + 2", "value + 3"))
        commit_at(directory, "2021-01-01T00:00:00", "edit one body")
        result = single_caller_census.census(directory, base)
        found = [entry for entry in result.entries if entry.kind == single_caller_census.SUPERSEDED_HELPER]
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
