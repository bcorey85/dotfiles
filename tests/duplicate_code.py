#!/usr/bin/env python3
"""Fail when the toolkit scripts hold duplicate code: a top-level function name defined in two files, or a jscpd
token clone between two places.

  duplicate_code.py            check; exit 1 on any repeat
  --root DIR                   the repo to check (default: the tree this file sits in)

jscpd runs through npx at a pinned version. Without npx the clone check is skipped with a note, as run.sh skips ruff."""
import argparse
import ast
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "scripts"))
import toolkit_paths

JSCPD = "jscpd@4.0.5"
# The hook handler that a script's main() calls: every gate names it one of these.
HANDLER_NAMES = {"check", "run", "decide"}
# A CLI verb handler: command_<verb>. Two scripts that share a verb each handle it their own way.
VERB_HANDLER = re.compile(r"^command_\w+$")
# Python scripts under scripts/review without a .py suffix, as ruff.toml lists them.
EXTENSIONLESS_PYTHON_SCRIPTS = ["verify-log", "verify-prep"]
GENERATED_HOOKS = [f"claude/.claude/{hook}" for hook in toolkit_paths.WORK_HOOKS]


def python_sources(root):
    # Mirrors the ruff include: the toolkit scripts and each skill's own scripts folder, not the vendored skills.
    claude_dir = root / "claude" / ".claude"
    scripts = sorted((claude_dir / "scripts").rglob("*.py"))
    skill_scripts = sorted((claude_dir / "skills").glob("*/scripts/*.py"))
    extensionless_scripts = [claude_dir / "scripts" / "review" / name for name in EXTENSIONLESS_PYTHON_SCRIPTS]
    return scripts + skill_scripts + [path for path in extensionless_scripts if path.is_file()]


def names_main_uses(tree):
    main_functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main"]
    if not main_functions:
        return set()

    main_nodes = ast.walk(main_functions[0])
    return {node.id for node in main_nodes if isinstance(node, ast.Name)}


def is_entry_point(name, handlers_in_main):
    return name == "main" or VERB_HANDLER.match(name) is not None or name in handlers_in_main


def same_name_functions(root):
    """{function name: sorted relative paths} for each top-level function defined in two or more files."""
    files_by_name = {}
    for path in python_sources(root):
        tree = ast.parse(path.read_text(), filename=str(path))
        relative_path = str(path.relative_to(root))
        handlers_in_main = names_main_uses(tree) & HANDLER_NAMES
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if is_entry_point(node.name, handlers_in_main):
                continue
            files_by_name.setdefault(node.name, set()).add(relative_path)

    return {name: sorted(paths) for name, paths in sorted(files_by_name.items()) if len(paths) > 1}


def import_preamble_lines(path):
    """Line numbers of the top-level imports and `sys.path` assignments in a Python file, and of its blank lines."""
    source = path.read_text()
    preamble_lines = {number for number, line in enumerate(source.splitlines(), 1) if not line.strip()}
    for node in ast.parse(source, filename=str(path)).body:
        is_import = isinstance(node, ast.Import | ast.ImportFrom)
        is_sys_path = isinstance(node, ast.Assign) and "sys.path" in ast.unparse(node.targets[0])
        if is_import or is_sys_path:
            preamble_lines.update(range(node.lineno, node.end_lineno + 1))
    return preamble_lines


def is_import_preamble(root, fragment):
    # jscpd's first and last lines can be partial, so only the lines between them must be preamble.
    path = root / fragment["name"]
    if path.suffix != ".py":
        return False

    interior_lines = range(fragment["start"] + 1, fragment["end"])
    return set(interior_lines) <= import_preamble_lines(path)


def scan_dirs(root):
    claude_dir = root / "claude" / ".claude"
    skill_script_dirs = sorted((claude_dir / "skills").glob("*/scripts"))
    candidate_dirs = [claude_dir / "scripts", claude_dir / "hooks", *skill_script_dirs]
    return [str(directory.relative_to(root)) for directory in candidate_dirs if directory.is_dir()]


def jscpd_clones(root):
    """One "fileA:start-end and fileB:start-end" line per jscpd clone at its default thresholds, leaving out clones
    that are only import lines; None when npx is missing."""
    if shutil.which("npx") is None:
        return None

    with tempfile.TemporaryDirectory() as report_dir:
        command = ["npx", "--yes", JSCPD, "--format", "python,bash", "--reporters", "json", "--output", report_dir,
                   "--ignore", ",".join(GENERATED_HOOKS), "--silent", *scan_dirs(root)]
        subprocess.run(command, cwd=root, check=True, stdout=subprocess.DEVNULL)
        report_path = pathlib.Path(report_dir) / "jscpd-report.json"
        report = json.loads(report_path.read_text())

    clones = []
    for duplicate in report["duplicates"]:
        fragments = [duplicate["firstFile"], duplicate["secondFile"]]
        # Both sides hold the same tokens, so one side of only imports makes the clone imports; jscpd's line span on
        # the other side can reach past them.
        if any(is_import_preamble(root, fragment) for fragment in fragments):
            continue
        places = [f"{fragment['name']}:{fragment['start']}-{fragment['end']}" for fragment in fragments]
        clones.append(" and ".join(places))
    return sorted(clones)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=pathlib.Path, default=pathlib.Path(__file__).resolve().parent.parent)
    arguments = parser.parse_args()
    root = arguments.root.resolve()

    repeats = [f"def {name} is defined in {', '.join(paths)}" for name, paths in same_name_functions(root).items()]

    clones = jscpd_clones(root)
    if clones is None:
        print("npx not installed: jscpd clone check skipped", file=sys.stderr)
    else:
        repeats += [f"jscpd clone {clone}" for clone in clones]

    for message in repeats:
        print(f"duplicate code: {message}. Move the shared code into lib/ and import it.", file=sys.stderr)
    if repeats:
        sys.exit(1)


if __name__ == "__main__":
    main()
