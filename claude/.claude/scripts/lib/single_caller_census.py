#!/usr/bin/env python3
"""single_caller_census.py: the dead weight a branch adds to Python code, listed for a reviewer to judge.

Three kinds: a function the branch added whose body (docstring aside) is one `return` or one call statement, with one
caller; a record field the branch added that no code reads; and a helper the branch added whose every caller also
calls a newer helper with every argument it passes the helper. References are counted by name over every Python file
git lists, so a census is a list of suspects: the reviewer decides. Standard library plus change_added_ranges,
diff_ranges and script_utils, which sit in the same folder.

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

import change_added_ranges
import diff_ranges
import script_utils

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

        # A deeply nested expression overflows the visitor's recursion, so the visit sits inside the try too. The
        # file is read into its own Index, merged only after the visit finishes, so a failed visit leaves no entries.
        file_index = Index()
        try:
            source = file_path.read_bytes().decode("utf-8-sig")
            tree = ast.parse(source)
            _Collector(relative, file_index).visit(tree)
        except (SyntaxError, ValueError, OSError, RecursionError) as error:
            index.unparsed.append(f"{relative}: {error}")
            continue

        _merge_index(index, file_index)
    return index


def _merge_index(index, file_index):
    """Add everything one file's Index holds to the whole-repo Index."""
    for name, references in file_index.references.items():
        index.references[name].extend(references)
    for caller, calls in file_index.calls_in.items():
        index.calls_in[caller].extend(calls)
    index.definitions.extend(file_index.definitions)
    index.classes.extend(file_index.classes)
    index.read_attributes |= file_index.read_attributes
    index.strings |= file_index.strings


def _unparsed_note(unparsed):
    if not unparsed:
        return []
    shown = "; ".join(unparsed[:LISTED_UNPARSED_PATHS])
    return [f"{len(unparsed)} Python files did not parse and were not read: {shown}"]


def _git_text(command):
    return f"`git {' '.join(command)}`"


def _added_ranges(repo, base):
    """{path: [(first, last)]} of the lines the work tree adds against base, untracked text files whole."""
    try:
        added = change_added_ranges.change_added_ranges(repo, base, text_only=True, relative=True, no_renames=True)
    except ValueError as error:
        raise CensusError(f"the diff of {repo} against {base} did not parse: {error}") from error
    if added is None:
        raise CensusError(f"`git diff` or `git ls-files --others --exclude-standard` failed in {repo}")
    return added


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

    def time_of(self, relative, line):
        """The author time of one line; an uncommitted or untracked line is the newest of all. Raises CensusError
        when blame of a tracked file does not report the line."""
        if relative in self.untracked:
            return UNCOMMITTED_TIME

        if relative not in self.by_path:
            self.by_path[relative] = self._read(relative)

        times = self.by_path[relative]
        if line not in times:
            raise CensusError(f"`git blame` of {relative} in {self.repo} did not report line {line}")
        return times[line]


def _is_added(definition, added):
    """True when every line of the def, from `def` to its last line, is a line the branch added."""
    node = definition.node
    return diff_ranges.ranges_cover(added.get(definition.path, ()), node.lineno, node.end_lineno)


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
        if node.decorator_list or (node.name.startswith("__") and node.name.endswith("__")):
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

        for statement in node.body:
            if not isinstance(statement, ast.AnnAssign) or not isinstance(statement.target, ast.Name):
                continue
            if not diff_ranges.ranges_touch(added.get(definition.path, ()), statement.lineno, statement.lineno):
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


def _widening_helpers(caller, definition, index, touched, times):
    """Names of the touched defs, newer than the helper, that `caller` calls with every argument of each helper call."""
    helper_name = definition.node.name
    helper_sets = [_argument_dumps(call.node) for call in index.calls_in[caller] if call.name == helper_name]
    if not all(helper_sets):
        return set()

    wider_sets = collections.defaultdict(list)
    for call in index.calls_in[caller]:
        if call.name == helper_name or call.name == caller.name or call.name not in touched:
            continue

        wider_sets[call.name].append(_argument_dumps(call.node))

    if not wider_sets:
        return set()

    helper_time = times.time_of(definition.path, definition.node.lineno)
    names = set()
    for name, wider_arguments in wider_sets.items():
        newest = max(times.time_of(d.path, d.node.lineno) for d in touched[name])
        if newest <= helper_time:
            continue

        if all(any(narrow <= wider for wider in wider_arguments) for narrow in helper_sets):
            names.add(name)
    return names


def _superseding_names(definition, sites, index, touched, times):
    """The helper names that every caller of the def also calls, newer and with every argument it passes the def."""
    callers = {site.caller for site in sites}
    name_sets = [_widening_helpers(caller, definition, index, touched, times) for caller in callers]
    return sorted(set.intersection(*name_sets))


def _superseded_entries(index, added, times):
    touched = collections.defaultdict(list)
    for definition in index.definitions:
        node = definition.node
        if diff_ranges.ranges_touch(added.get(definition.path, ()), node.lineno, node.end_lineno):
            touched[node.name].append(definition)

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
    added = _added_ranges(repo, base)
    untracked = [path for path, ranges in added.items() if ranges == change_added_ranges.WHOLE_FILE]
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
    read_paths = [path for path, ranges in added.items() if ranges]
    notes = _unparsed_note(index.unparsed) + _typescript_notes(read_paths)
    return Census(entries, notes)


def _entry_lines(result, paths=None):
    """The prompt lines of the entries of a Census, only those in `paths` when given."""
    lines = []
    for entry in result.entries:
        if paths is not None and entry.path not in paths:
            continue
        lines.append(f"{entry.path}:{entry.line} {entry.kind} `{entry.name}`: {entry.detail}")
    return lines


def census_report_lines(repo, base, paths=None):
    """The census of the work tree against `base` under CENSUS_HEADING: the entries in `paths` when given, or a
    "none" line that names the base when none is listed, then every census note. A census that cannot run is said
    so in one line."""
    try:
        result = census(repo, base)
    except CensusError as error:
        return [CENSUS_HEADING, f"The census did not run: {error}"]
    entries = _entry_lines(result, paths) or [f"none (read against {base})"]
    notes = [f"note: {note}" for note in result.notes]
    return [CENSUS_HEADING, *entries, *notes]


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
