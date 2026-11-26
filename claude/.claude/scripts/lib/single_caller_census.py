#!/usr/bin/env python3
"""single_caller_census.py: the dead weight a branch adds to Python code, listed for a reviewer to judge.

Three kinds: a function the branch added that only forwards a call and has one caller, a record field the branch
added that no code reads, and a helper the branch added whose every caller also calls a newer helper with every
argument it passes the helper. References are counted by name over every Python file git lists, so a census is a
list of suspects: the reviewer decides. Standard library plus changed_lines, source_text and script_utils, which sit
in the same folder.

    single_caller_census.py [--repo DIR] [--base REF]    prints {"entries": [...], "notes": [...]} as JSON; exit 2
                                                         with the error on stderr when git fails or its output
                                                         does not parse
"""
import argparse
import ast
import collections
import json
import pathlib
import re
import sys
from typing import NamedTuple

import changed_lines
import script_utils
import source_text

FORWARDER = "single-caller-forwarder"
UNREAD_FIELD = "unread-field"
SUPERSEDED_HELPER = "superseded-helper"

PYTHON_SUFFIX = ".py"
TYPESCRIPT_SUFFIXES = (".ts", ".tsx", ".mts", ".cts")
RECORD_BASE_NAMES = ("NamedTuple", "TypedDict", "Protocol")
RECORD_DECORATOR_NAME = "dataclass"
UNCOMMITTED_TIME = float("inf")
BLAME_HEADER = re.compile(r"^([0-9a-f]{40}|[0-9a-f]{64}) \d+ (\d+)")
BLAME_TIME_PREFIX = "author-time "
LISTED_UNPARSED_PATHS = 5
CENSUS_HEADING = "Single-caller census (dead weight this branch adds; judge each entry):"


class CensusError(Exception):
    """A git call the census needs failed, or its output did not parse."""


class UntrackedLines(NamedTuple):
    path: str
    added_lines: list


class Entry(NamedTuple):
    kind: str
    path: str
    line: int
    name: str
    detail: str


class Census(NamedTuple):
    entries: list
    notes: list


class Reference(NamedTuple):
    """One place that names a def: the caller is the innermost function around it, None at module level."""
    path: str
    is_call: bool
    caller: object


class Definition(NamedTuple):
    path: str
    node: object


class Call(NamedTuple):
    name: str
    node: object


class Index:
    """What the census reads from every Python file: references by name, defs, classes, read attributes, strings."""

    def __init__(self):
        self.references = collections.defaultdict(list)
        self.definitions = []
        self.classes = []
        self.read_attributes = set()
        self.strings = set()
        self.calls_in = collections.defaultdict(list)
        self.unparsed = []


def _called_name(call):
    """The name a call goes through: `f(x)` and `obj.f(x)` both give `f`; None for any other callee."""
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _all_arguments(arguments):
    """Every ast.arg of a signature, in source order."""
    named = [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs]
    for extra in (arguments.vararg, arguments.kwarg):
        if extra is not None:
            named.append(extra)
    return named


class _Collector(ast.NodeVisitor):
    def __init__(self, path, index):
        self.path = path
        self.index = index
        self.call_funcs = set()
        self.function_stack = []

    def _caller(self):
        if not self.function_stack:
            return None
        return self.function_stack[-1]

    def _add_reference(self, name, node):
        reference = Reference(self.path, id(node) in self.call_funcs, self._caller())
        self.index.references[name].append(reference)

    def _visit_function(self, node):
        definition = Definition(self.path, node)
        self.index.definitions.append(definition)
        # Decorators, defaults and annotations run in the enclosing scope, so visit them before the push.
        outer_parts = [*node.decorator_list, *node.args.defaults, *node.args.kw_defaults]
        outer_parts += [argument.annotation for argument in _all_arguments(node.args)]
        outer_parts.append(node.returns)
        for part in outer_parts:
            if part is not None:
                self.visit(part)

        self.function_stack.append(node)
        for statement in node.body:
            self.visit(statement)
        self.function_stack.pop()

    def visit_FunctionDef(self, node):
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node):
        self._visit_function(node)

    def visit_ClassDef(self, node):
        definition = Definition(self.path, node)
        self.index.classes.append(definition)
        self.generic_visit(node)

    def visit_Call(self, node):
        self.call_funcs.add(id(node.func))
        name = _called_name(node)
        caller = self._caller()
        if name is not None and caller is not None:
            call = Call(name, node)
            self.index.calls_in[caller].append(call)
        self.generic_visit(node)

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            self._add_reference(node.id, node)

    def visit_Attribute(self, node):
        self._add_reference(node.attr, node)
        if isinstance(node.ctx, ast.Load):
            self.index.read_attributes.add(node.attr)
        self.generic_visit(node)

    def visit_Constant(self, node):
        if isinstance(node.value, str):
            self.index.strings.add(node.value)


def _build_index(repo, paths):
    index = Index()
    for relative in paths:
        if not relative.endswith(PYTHON_SUFFIX):
            continue

        file_path = pathlib.Path(repo, relative)
        if not file_path.is_file():
            continue

        try:
            source = file_path.read_bytes().decode("utf-8")
            tree = ast.parse(source)
        except (SyntaxError, ValueError, OSError) as error:
            index.unparsed.append(f"{relative}: {error}")
            continue

        _Collector(relative, index).visit(tree)
    return index


def _unparsed_note(unparsed):
    if not unparsed:
        return []
    shown = "; ".join(unparsed[:LISTED_UNPARSED_PATHS])
    return [f"{len(unparsed)} Python files did not parse and were not read: {shown}"]


def _git_text(command):
    return f"`git {' '.join(command)}`"


def _diff_files(repo, base):
    """The parsed diff (source_text.FileDiff list) of the work tree against base."""
    command = (
        "diff", "-U0", "--no-prefix", "--no-color", "--no-ext-diff", "--no-textconv", "--no-renames", "--relative",
        base,
    )
    output = script_utils.git_output(repo, *command)
    if output is None:
        raise CensusError(f"{_git_text(command)} failed in {repo}")

    try:
        return source_text.parse_unified_diff(output)
    except ValueError as error:
        raise CensusError(f"{_git_text(command)} output in {repo} did not parse: {error}") from error


def _untracked_entries(repo, untracked):
    """One UntrackedLines per readable untracked Python file."""
    entries = []
    for relative in untracked:
        if not relative.endswith(PYTHON_SUFFIX):
            continue

        file_path = pathlib.Path(repo, relative)
        lines = script_utils.read_text_lines(file_path)
        if lines is None:
            continue

        entry = UntrackedLines(relative, lines)
        entries.append(entry)
    return entries


def _typescript_notes(paths):
    names = sorted({name for name in paths if name.endswith(TYPESCRIPT_SUFFIXES)})
    if not names:
        return []
    shown = "; ".join(names[:LISTED_UNPARSED_PATHS])
    return [f"{len(names)} TypeScript files were not read: {shown}"]


class _BlameTimes:
    """Author times of the lines of a file in the work tree, read with `git blame` once per file."""

    def __init__(self, repo, untracked):
        self.repo = repo
        self.untracked = set(untracked)
        self.by_path = {}

    def _read(self, relative):
        command = ("blame", "--no-textconv", "--line-porcelain", "--", relative)
        output = script_utils.git_output(self.repo, *command)
        if output is None:
            raise CensusError(f"{_git_text(command)} failed in {self.repo}")

        times = {}
        sha = None
        final_line = None
        for text in output.split("\n"):
            header = BLAME_HEADER.match(text)
            if header:
                sha, final_line = header.group(1), int(header.group(2))
            elif text.startswith(BLAME_TIME_PREFIX) and sha is not None:
                is_uncommitted = sha.strip("0") == ""
                if is_uncommitted:
                    times[final_line] = UNCOMMITTED_TIME
                else:
                    author_time = int(text[len(BLAME_TIME_PREFIX):])
                    times[final_line] = author_time
        return times

    def newest(self, relative, first, last):
        """The latest author time among lines first..last; an uncommitted or untracked line is the newest of all.
        Raises CensusError when blame of a tracked file does not report a line."""
        if relative in self.untracked:
            return UNCOMMITTED_TIME

        if relative not in self.by_path:
            self.by_path[relative] = self._read(relative)

        times = self.by_path[relative]
        for number in range(first, last + 1):
            if number not in times:
                raise CensusError(f"`git blame` of {relative} in {self.repo} did not report line {number}")
        return max(times[number] for number in range(first, last + 1))


def _is_added(definition, added):
    """True when every line of the def, from `def` to its last line, is a line the branch added."""
    node = definition.node
    return changed_lines.range_added(added, definition.path, node.lineno, node.end_lineno)


def _is_touched(definition, added):
    node = definition.node
    return changed_lines.range_touched(added, definition.path, node.lineno, node.end_lineno)


def _is_dunder(name):
    return name.startswith("__") and name.endswith("__")


def _body_without_docstring(node):
    if ast.get_docstring(node, clean=False) is not None:
        return node.body[1:]
    return node.body


def _is_forwarding_body(node):
    body = _body_without_docstring(node)
    if len(body) != 1:
        return False

    statement = body[0]
    if isinstance(statement, ast.Return):
        return True
    return isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call)


def _forwarder_entries(index, added):
    entries = []
    for definition in index.definitions:
        node = definition.node
        if node.decorator_list or _is_dunder(node.name):
            continue
        if not _is_added(definition, added) or not _is_forwarding_body(node):
            continue

        references = index.references[node.name]
        if len(references) != 1 or not references[0].is_call:
            continue

        detail = f"`{node.name}` is a one-statement body with a single caller, in {references[0].path}"
        entry = Entry(FORWARDER, definition.path, node.lineno, node.name, detail)
        entries.append(entry)
    return entries


def _expression_names(expression):
    """The names a base class or decorator expression goes through: `a.B`, `B[T]` and `B(x)` all give `B`."""
    if isinstance(expression, ast.Name):
        return [expression.id]
    if isinstance(expression, ast.Attribute):
        return [expression.attr]
    if isinstance(expression, ast.Subscript):
        return _expression_names(expression.value)
    if isinstance(expression, ast.Call):
        return _expression_names(expression.func)
    return []


def _is_record_class(node):
    base_names = {name for base in node.bases for name in _expression_names(base)}
    decorator_names = {name for decorator in node.decorator_list for name in _expression_names(decorator)}
    return bool(base_names & set(RECORD_BASE_NAMES)) or RECORD_DECORATOR_NAME in decorator_names


def _unread_field_entries(index, added):
    entries = []
    for definition in index.classes:
        node = definition.node
        if not _is_record_class(node):
            continue

        lines = added.get(definition.path, set())
        for statement in node.body:
            if not isinstance(statement, ast.AnnAssign) or not isinstance(statement.target, ast.Name):
                continue
            if statement.lineno not in lines:
                continue

            field_name = statement.target.id
            if field_name in index.read_attributes or field_name in index.strings:
                continue

            detail = f"field `{field_name}` is never read as an attribute or a string key"
            entry = Entry(UNREAD_FIELD, definition.path, statement.lineno, f"{node.name}.{field_name}", detail)
            entries.append(entry)
    return entries


def _argument_dumps(call):
    positional = [ast.dump(argument) for argument in call.args]
    keyword = [ast.dump(argument.value) for argument in call.keywords]
    return set(positional + keyword)


def _widening_helpers(caller, helper_name, index, touched, times, helper_time):
    """Names of the touched defs, newer than the helper, that `caller` calls with every argument of each helper call."""
    helper_sets = [_argument_dumps(call.node) for call in index.calls_in[caller] if call.name == helper_name]
    if not all(helper_sets):
        return set()

    wider_sets = collections.defaultdict(list)
    for call in index.calls_in[caller]:
        if call.name == helper_name or call.name == caller.name or call.name not in touched:
            continue

        wider_sets[call.name].append(_argument_dumps(call.node))

    names = set()
    for name, wider_arguments in wider_sets.items():
        newest = max(times.newest(d.path, d.node.lineno, d.node.end_lineno) for d in touched[name])
        if newest <= helper_time:
            continue

        if all(any(narrow <= wider for wider in wider_arguments) for narrow in helper_sets):
            names.add(name)
    return names


def _superseding_names(definition, sites, index, touched, times):
    """The helper names that every caller of the def also calls, newer and with every argument it passes the def."""
    callers = {site.caller for site in sites}
    helper_time = times.newest(definition.path, definition.node.lineno, definition.node.lineno)
    name_sets = [_widening_helpers(caller, definition.node.name, index, touched, times, helper_time)
                 for caller in callers]
    return sorted(set.intersection(*name_sets))


def _superseded_entries(index, added, times):
    touched = collections.defaultdict(list)
    for definition in index.definitions:
        if _is_touched(definition, added):
            touched[definition.node.name].append(definition)

    entries = []
    for definition in index.definitions:
        if not _is_added(definition, added):
            continue

        sites = [reference for reference in index.references[definition.node.name] if reference.is_call]
        if not sites:
            continue

        names = _superseding_names(definition, sites, index, touched, times)
        if not names:
            continue

        callers = sorted({site.caller.name for site in sites})
        newer = ", ".join(f"`{name}`" for name in names)
        detail = (f"every caller ({', '.join(callers)}) also calls the newer {newer} with every argument it passes "
                  f"`{definition.node.name}`; check whether each of {newer} gives the same output")
        entry = Entry(SUPERSEDED_HELPER, definition.path, definition.node.lineno, definition.node.name, detail)
        entries.append(entry)
    return entries


def census(repo, base="HEAD"):
    """The Census of the dead weight the work tree of `repo` adds over `base`.

    Raises CensusError when git fails or its output does not parse."""
    untracked = script_utils.untracked_paths(repo)
    if untracked is None:
        raise CensusError(f"`git ls-files --others --exclude-standard` failed in {repo}")

    diff_files = _diff_files(repo, base)
    untracked_entries = _untracked_entries(repo, untracked)
    added = changed_lines.changed_line_sets(diff_files, untracked_entries)
    try:
        listed = script_utils.repo_file_paths_or_raise(repo)
    except script_utils.GitCallError as error:
        message = str(error)
        raise CensusError(message) from error

    index = _build_index(repo, listed)
    times = _BlameTimes(repo, untracked)
    entries = _forwarder_entries(index, added)
    entries += _unread_field_entries(index, added)
    entries += _superseded_entries(index, added, times)
    entries.sort(key=lambda entry: (entry.path, entry.line, entry.kind))
    read_paths = [path for path, numbers in added.items() if numbers]
    notes = _unparsed_note(index.unparsed) + _typescript_notes(read_paths + untracked)
    return Census(entries, notes)


def census_lines(result, paths=None):
    """The prompt lines of a Census: one per entry, only those in `paths` when given, then one per note."""
    lines = []
    for entry in result.entries:
        if paths is not None and entry.path not in paths:
            continue
        lines.append(f"{entry.path}:{entry.line} {entry.kind} `{entry.name}`: {entry.detail}")
    lines += [f"note: {note}" for note in result.notes]
    return lines


def report_lines(repo, base, paths=None):
    """The census of the work tree against `base` under CENSUS_HEADING: the entries in `paths` when given, then
    every census note, or "none". A census that cannot run is said so in one line."""
    try:
        result = census(repo, base)
    except CensusError as error:
        return [CENSUS_HEADING, f"The census did not run: {error}"]
    lines = census_lines(result, paths)
    return [CENSUS_HEADING, *(lines or ["none"])]


def main(argv=None):
    parser = argparse.ArgumentParser(description="List the dead weight a branch adds to Python code.")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--base", default="HEAD")
    arguments = parser.parse_args(argv)
    try:
        result = census(arguments.repo, arguments.base)
    except CensusError as error:
        print(f"single_caller_census: {error}", file=sys.stderr)
        return 2

    payload = {"entries": [entry._asdict() for entry in result.entries], "notes": result.notes}
    text = json.dumps(payload, indent=2)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
