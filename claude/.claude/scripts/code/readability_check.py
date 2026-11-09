"""readability_check.py: list the functions a change wrote that break the coder's readability limits.

  readability_check.py [--base REV]      (run from inside a git repo; REV defaults to HEAD)

The changed lines are the added lines of `git diff -U0 REV` against the working tree, plus every line of each
untracked file. Test files are left out. Python is read with `ast`; TS, JS and the <script> blocks of a .vue file with
readability_ts.mjs beside this file, using the `typescript` package of the file's project, else the global one. A file
with no usable typescript, one that does not parse, or a .vue file with no <script> block is skipped.

A function breaks a limit when:
  - a control statement on an added line sits more than MAX_NESTING levels deep in it (an else-if stays at its if's
    level; a nested function counts from zero);
  - it spans more than MAX_FUNCTION_LINES lines, and the change wrote at least half of it or took it past the limit;
  - an added line holds a chained ternary;
  - an added line passes a call result straight into a call that is itself an argument;
  - an added line passes a ternary straight as a call argument;
  - an added line holds a comprehension with two or more `for` clauses, or one inside another (Python only);
  - an added line returns a tuple literal of MIN_WIDE_TUPLE or more values (TS: an array literal, in a function with a
    tuple return type or none);
  - its def line is added and it takes more than MAX_PARAMETERS parameters, self, cls and a TS `this` left out; a
    function whose name starts with `test` is left out.

Exit 0: no hit. Exit 1: hits, printed up to MAX_HIT_LINES lines with the fix for each. The check fails open: when git
cannot give the diff it says so on stderr and exits 0, so a broken environment never blocks a hand-back.
"""
import argparse
import ast
import functools
import json
import os
import pathlib
import subprocess
import sys

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent.parent / "lib")]
import script_utils
import source_text
from source_paths import is_test_path

HELPER = pathlib.Path(__file__).resolve().parent / "readability_ts.mjs"
MAX_NESTING = 2
MAX_FUNCTION_LINES = 40
MAX_PARAMETERS = 5
MIN_WIDE_TUPLE = 3
MAX_HIT_LINES = 10
HELPER_TIMEOUT_SECONDS = 120
PY_SUFFIXES = (".py",)
TS_SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts", ".vue")
SKIPPED_SUFFIXES = (".min.js", ".d.ts")

NESTING_FIX = "Return early on the guard case, or move the inner block into a function named for what it does."
LENGTH_FIX = "Split it into named steps, one function per step."
TERNARY_FIX = "Write it as an if/else or a lookup table."
DEEP_CALL_FIX = "Put the inner result in a named variable first."
ARGUMENT_TERNARY_FIX = "Assign it to a named variable first."
COMPREHENSION_FIX = "Write the outer loop as a for statement."
WIDE_TUPLE_FIX = "Return a dataclass, NamedTuple or interface."
PARAMETERS_FIX = "Pass one named object."

LINE_LIMITS = (
    ("ternary", "chained ternary", TERNARY_FIX),
    ("deep", "deep call (a call result passed into a call that is an argument)", DEEP_CALL_FIX),
    ("argternary", "ternary as a call argument", ARGUMENT_TERNARY_FIX),
    ("comp", "comprehension with two loops or a nested comprehension", COMPREHENSION_FIX),
)

PY_FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
PY_CONTROL = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.Match)
if hasattr(ast, "TryStar"):
    PY_CONTROL += (ast.TryStar,)
PY_TRANSPARENT = (ast.Starred, ast.Await, ast.UnaryOp, ast.JoinedStr, ast.FormattedValue)
PY_COMPREHENSIONS = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
PY_RECEIVERS = ("self", "cls")


def parameter_entry(node):
    """[def line, parameter count] of a def, self and cls left out; None for a lambda."""
    if isinstance(node, ast.Lambda):
        return None
    arguments = node.args
    names = [argument.arg for argument in [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs]]
    names += [argument.arg for argument in (arguments.vararg, arguments.kwarg) if argument]
    if names and names[0] in PY_RECEIVERS:
        names = names[1:]
    return [node.lineno, len(names)]


def is_wide_comprehension(node):
    """Whether a comprehension has two or more `for` clauses or holds another comprehension."""
    if len(node.generators) >= 2:
        return True
    inner_nodes = (inner for inner in ast.walk(node) if inner is not node)
    return any(isinstance(inner, PY_COMPREHENSIONS) for inner in inner_nodes)


class PythonFunctions(ast.NodeVisitor):
    """Collects one record per function: name, first and last line, and the lines that break a limit."""

    def __init__(self):
        self.records = []
        self.record = None
        self.depth = 0
        self.call_level = 0
        self.else_ifs = set()

    def visit_function(self, node):
        outer = (self.record, self.depth, self.call_level)
        name = getattr(node, "name", "<lambda>")
        self.record = {"name": name, "s": node.lineno, "e": node.end_lineno, "deep": [], "nest": [], "ternary": [],
                       "argternary": [], "comp": [], "wide": [], "params": parameter_entry(node)}
        self.records.append(self.record)
        self.depth = 0
        self.call_level = 0
        body = node.body if isinstance(node.body, list) else [node.body]
        for statement in body:
            self.visit(statement)
        self.record, self.depth, self.call_level = outer

    def visit_class(self, node):
        outer = self.record
        self.record = None
        self.generic_visit(node)
        self.record = outer

    def visit(self, node):
        if isinstance(node, PY_FUNCTIONS):
            return self.visit_function(node)
        if isinstance(node, ast.ClassDef):
            return self.visit_class(node)
        if self.record is None:
            return self.visit_plain(node)
        if isinstance(node, ast.Call):
            return self.visit_call(node)
        if isinstance(node, ast.IfExp):
            return self.visit_ternary(node)
        if isinstance(node, ast.Return):
            return self.visit_return(node)
        if isinstance(node, PY_COMPREHENSIONS):
            return self.visit_comprehension(node)
        if isinstance(node, PY_CONTROL) and id(node) not in self.else_ifs:
            return self.visit_control(node)
        return self.visit_plain(node)

    def visit_plain(self, node):
        # An argument passes its call level on only through a node that keeps the call in view, such as `*args`.
        outer_level = self.call_level
        if not isinstance(node, PY_TRANSPARENT):
            self.call_level = 0
        self.generic_visit(node)
        self.call_level = outer_level

    def visit_control(self, node):
        if isinstance(node, ast.If) and len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
            self.else_ifs.add(id(node.orelse[0]))
        self.depth += 1
        if self.depth > MAX_NESTING:
            self.record["nest"].append([node.lineno, self.depth])
        self.visit_plain(node)
        self.depth -= 1

    def visit_ternary(self, node):
        parts = (node.test, node.body, node.orelse)
        if any(isinstance(part, ast.IfExp) for part in parts):
            self.record["ternary"].append(node.lineno)
        self.visit_plain(node)

    def visit_return(self, node):
        is_wide = isinstance(node.value, ast.Tuple) and len(node.value.elts) >= MIN_WIDE_TUPLE
        if is_wide:
            self.record["wide"].append([node.lineno, len(node.value.elts)])
        self.visit_plain(node)

    def visit_comprehension(self, node):
        if is_wide_comprehension(node):
            self.record["comp"].append(node.lineno)
        self.visit_plain(node)

    def visit_call(self, node):
        level = self.call_level
        if level >= 2:
            self.record["deep"].append(node.lineno)
        self.call_level = 0
        self.visit(node.func)
        arguments = [*node.args, *(keyword.value for keyword in node.keywords)]
        for argument in arguments:
            if isinstance(argument, ast.IfExp):
                self.record["argternary"].append(argument.lineno)
            self.call_level = level + 1
            self.visit(argument)
        self.call_level = level


def python_records(text):
    """The function records of one Python source, or None when it does not parse."""
    try:
        tree = ast.parse(text)
        collector = PythonFunctions()
        collector.visit(tree)
    except (SyntaxError, ValueError, RecursionError):
        return None
    return collector.records


def usable_typescript(directory):
    """True for a typescript package with the classic compiler API (lib/typescript.js); 7.x ships none."""
    return (directory / "package.json").is_file() and (directory / "lib" / "typescript.js").is_file()


@functools.cache
def global_node_root():
    """The global node_modules folder, or None when npm cannot say. Read once per run."""
    try:
        completed = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    root = completed.stdout.strip()
    return pathlib.Path(root) if root else None


def find_typescript(file):
    """The `typescript` package of the file's project (walking up), else the one in the global root, else None."""
    for directory in pathlib.Path(file).resolve().parents:
        candidate = directory / "node_modules" / "typescript"
        if usable_typescript(candidate):
            return candidate
    global_root = global_node_root()
    if global_root is None:
        return None
    candidate = global_root / "typescript"
    return candidate if usable_typescript(candidate) else None


def typescript_records(files, tsdir):
    """{file: records | None} for files that share one typescript package."""
    request = json.dumps({"tsdir": str(tsdir), "files": [str(file) for file in files]})
    try:
        completed = subprocess.run(["node", str(HELPER)], input=request, capture_output=True, text=True,
                                   timeout=HELPER_TIMEOUT_SECONDS)
        parsed = json.loads(completed.stdout) if completed.returncode == 0 else {}
    except (OSError, subprocess.SubprocessError, ValueError):
        parsed = {}
    return {file: parsed.get(str(file)) for file in files}


def records_by_file(files):
    """{file: records | None} for Python and TS/JS files; TS files are read in one helper call per package."""
    records = {}
    typescript_groups = {}
    for file in files:
        if file.suffix in PY_SUFFIXES:
            records[file] = python_records(file_text(file))
            continue
        tsdir = find_typescript(file)
        typescript_groups.setdefault(tsdir, []).append(file)

    for tsdir, group in typescript_groups.items():
        if tsdir is None:
            records.update(dict.fromkeys(group))
            continue
        records.update(typescript_records(group, tsdir))
    return records


def file_text(file):
    try:
        return file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def is_checked_file(relative_path):
    name = relative_path.lower()
    if name.endswith(SKIPPED_SUFFIXES) or is_test_path(relative_path):
        return False
    return name.endswith(PY_SUFFIXES + TS_SUFFIXES)


def diff_added_lines(diff_text):
    """{relative path: set of added line numbers} from `git diff --no-prefix -U0` text. Raises ValueError on a diff
    that source_text cannot parse."""
    diff_files = source_text.parse_unified_diff(diff_text)
    return {diff.path: {number for hunk in diff.hunks for number, _ in hunk.added} for diff in diff_files}


def changed_lines(repo, base):
    """{relative path: added line numbers} of the checked files, or None when git cannot give the diff or the diff
    does not parse."""
    diff_text = script_utils.git_output(repo, "diff", "-U0", "--no-color", "--no-ext-diff", "--no-textconv",
                                        "--no-renames", "--no-prefix", "--relative", "--diff-filter=d", base)
    untracked_text = script_utils.git_output(repo, "-c", "core.quotePath=false", "ls-files", "--others",
                                             "--exclude-standard")
    if diff_text is None or untracked_text is None:
        return None

    try:
        added = diff_added_lines(diff_text)
    except ValueError as error:
        print(f"readability check: {error}", file=sys.stderr)
        return None

    for name in untracked_text.splitlines():
        line_count = file_text(repo / name).count("\n") + 1
        added[name] = set(range(1, line_count + 1))
    return {name: lines for name, lines in added.items() if lines and is_checked_file(name)}


def own_lines(record, records):
    """The lines of a function less the lines of the functions nested in it: a nested function is measured alone."""
    lines = set(range(record["s"], record["e"] + 1))
    for other in records:
        is_nested = other is not record and record["s"] <= other["s"] and other["e"] <= record["e"]
        if is_nested:
            lines -= set(range(other["s"], other["e"] + 1))
    return lines


def is_long(own, added):
    """Whether a function's own lines pass the limit, and the change wrote half of them or took it past the limit."""
    if len(own) <= MAX_FUNCTION_LINES:
        return False
    added_inside = len(own & added)
    lines_before = len(own) - added_inside
    return lines_before <= MAX_FUNCTION_LINES or 2 * added_inside >= len(own)


def parameter_hits(record, added):
    """[(line, text)] for a function whose def line the change wrote and that takes more than MAX_PARAMETERS."""
    entry = record["params"]
    if entry is None or record["name"].startswith("test"):
        return []
    line, count = entry
    if line not in added or count <= MAX_PARAMETERS:
        return []
    return [(line, f"{record['name']} — parameters ({count}, limit {MAX_PARAMETERS}): {PARAMETERS_FIX}")]


def function_hits(record, own, added):
    """[(line, text)] for one function record: each limit it breaks on the change's lines."""
    name = record["name"]
    hits = []
    if is_long(own, added):
        length = f"length ({len(own)} lines, limit {MAX_FUNCTION_LINES})"
        hits.append((record["s"], f"{name} — {length}: {LENGTH_FIX}"))
    for line, depth in record["nest"]:
        if line in added:
            hits.append((line, f"{name} — nesting ({depth} levels, limit {MAX_NESTING}): {NESTING_FIX}"))
    for field, label, fix in LINE_LIMITS:
        hits += [(line, f"{name} — {label}: {fix}") for line in record[field] if line in added]
    for line, count in record["wide"]:
        if line in added:
            hits.append((line, f"{name} — tuple return ({count} values): {WIDE_TUPLE_FIX}"))
    return hits + parameter_hits(record, added)


def readability_hits(repo, added_by_file):
    """Sorted hit lines `path:line text` over every changed file the analyzers could read."""
    files = {repo / name: name for name in added_by_file}
    records = records_by_file(list(files))
    hit_lines = []
    for file, name in files.items():
        added = added_by_file[name]
        file_records = records.get(file) or []
        for record in file_records:
            own = own_lines(record, file_records)
            hit_lines += [(name, line, text) for line, text in function_hits(record, own, added)]
    return [f"{name}:{line} {text}" for name, line, text in sorted(set(hit_lines))]


def report(hit_lines):
    shown = hit_lines[:MAX_HIT_LINES]
    print("Readability limits broken in the code this change wrote:")
    print("\n".join(shown))
    hidden = len(hit_lines) - len(shown)
    if hidden:
        print(f"... and {hidden} more; they show on the next run.")


def main(argv):
    parser = argparse.ArgumentParser(description="List the functions a change wrote that break readability limits.")
    parser.add_argument("--base", default="HEAD", help="the commit the change is measured against")
    arguments = parser.parse_args(argv)

    repo = script_utils.repo_root(os.getcwd())
    if repo is None:
        print("readability_check: skipped, not inside a git repo", file=sys.stderr)
        return 0
    repo = pathlib.Path(repo)

    # Fail open: a git failure is no readability defect, and the review still reads the code.
    added_by_file = changed_lines(repo, arguments.base)
    if added_by_file is None:
        print(f"readability_check: skipped, git could not diff against {arguments.base}", file=sys.stderr)
        return 0

    hit_lines = readability_hits(repo, added_by_file)
    if not hit_lines:
        return 0
    report(hit_lines)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
