#!/usr/bin/env python3
"""Fail when the toolkit scripts gain duplicate code: a top-level function name defined in a second file, or a jscpd
token clone between two files. Today's repeats sit in duplicate_code_baseline.json, which may only shrink.

  duplicate_code.py            check; exit 1 on a new repeat or on a baseline entry that has shrunk
  duplicate_code.py --shrink   rewrite the baseline without the entries that have shrunk; never adds one
  --root DIR                   the repo to check (default: the tree this file sits in)

jscpd runs through npx at a pinned version. Without npx the clone check is skipped with a note, as run.sh skips ruff."""
import argparse
import ast
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

JSCPD = "jscpd@4.0.5"
# Entry points every hook and command script defines by convention; a repeat of one is not a copied helper.
ENTRY_POINT_NAMES = {"main", "check", "run", "decide"}
BASELINE_NAME = "duplicate_code_baseline.json"


def python_sources(root):
    # Mirrors the ruff include: the toolkit scripts and each skill's own scripts folder, not the vendored skills.
    claude_dir = root / "claude" / ".claude"
    scripts = sorted((claude_dir / "scripts").rglob("*.py"))
    skill_scripts = sorted((claude_dir / "skills").glob("*/scripts/*.py"))
    return scripts + skill_scripts


def same_name_functions(root):
    """{function name: sorted relative paths} for each top-level function defined in two or more files."""
    files_by_name = {}
    for path in python_sources(root):
        tree = ast.parse(path.read_text(), filename=str(path))
        relative_path = str(path.relative_to(root))
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if node.name in ENTRY_POINT_NAMES:
                continue
            files_by_name.setdefault(node.name, set()).add(relative_path)

    return {name: sorted(paths) for name, paths in sorted(files_by_name.items()) if len(paths) > 1}


def jscpd_clone_pairs(root):
    """{"fileA | fileB": clone count} from jscpd at its default thresholds, or None when npx is missing."""
    if shutil.which("npx") is None:
        return None

    scan_dirs = ["claude/.claude/scripts", "claude/.claude/hooks"]
    with tempfile.TemporaryDirectory() as report_dir:
        command = ["npx", "--yes", JSCPD, "--format", "python,bash", "--reporters", "json", "--output", report_dir,
                   "--silent", *scan_dirs]
        subprocess.run(command, cwd=root, check=True, stdout=subprocess.DEVNULL)
        report_path = pathlib.Path(report_dir) / "jscpd-report.json"
        report = json.loads(report_path.read_text())

    clone_counts = {}
    for duplicate in report["duplicates"]:
        pair = sorted([duplicate["firstFile"]["name"], duplicate["secondFile"]["name"]])
        pair_key = " | ".join(pair)
        clone_counts[pair_key] = clone_counts.get(pair_key, 0) + 1
    return dict(sorted(clone_counts.items()))


def read_baseline(baseline_path):
    baseline = json.loads(baseline_path.read_text())
    if set(baseline) != {"same_name_functions", "jscpd_clone_pairs"}:
        sys.exit(f"{baseline_path}: expected exactly the keys same_name_functions and jscpd_clone_pairs")
    return baseline


def compare_same_name_functions(current, allowed):
    """(new repeat messages, shrunk baseline messages)."""
    new_repeats = []
    shrunk = []
    for name, paths in current.items():
        extra_paths = sorted(set(paths) - set(allowed.get(name, [])))
        if extra_paths:
            new_repeats.append(f"def {name} is defined in {', '.join(paths)}; new: {', '.join(extra_paths)}")
    for name, paths in allowed.items():
        gone_paths = sorted(set(paths) - set(current.get(name, [])))
        if gone_paths:
            shrunk.append(f"def {name} no longer repeats in {', '.join(gone_paths)}")
    return new_repeats, shrunk


def compare_clone_pairs(current, allowed):
    """(new clone messages, shrunk baseline messages)."""
    new_clones = []
    shrunk = []
    for pair, count in current.items():
        if count > allowed.get(pair, 0):
            new_clones.append(f"{pair}: {count} clones, baseline {allowed.get(pair, 0)}")
    for pair, count in allowed.items():
        if current.get(pair, 0) < count:
            shrunk.append(f"{pair}: {current.get(pair, 0)} clones, baseline {count}")
    return new_clones, shrunk


def shrink_same_name_functions(allowed, current):
    """The allowed repeats cut to the files that still define each name; never adds a file or a name."""
    kept = {name: sorted(set(paths) & set(current.get(name, []))) for name, paths in allowed.items()}
    return {name: paths for name, paths in kept.items() if len(paths) > 1}


def shrink_clone_pairs(allowed, current):
    """The allowed clone counts cut to today's counts; never raises a count or adds a pair."""
    kept = {pair: min(count, current.get(pair, 0)) for pair, count in allowed.items()}
    return {pair: count for pair, count in kept.items() if count > 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=pathlib.Path, default=pathlib.Path(__file__).resolve().parent.parent)
    parser.add_argument("--shrink", action="store_true")
    arguments = parser.parse_args()
    root = arguments.root.resolve()
    baseline_path = root / "tests" / BASELINE_NAME
    baseline = read_baseline(baseline_path)

    current_names = same_name_functions(root)
    new_findings, shrunk = compare_same_name_functions(current_names, baseline["same_name_functions"])

    current_clones = jscpd_clone_pairs(root)
    if current_clones is None:
        print("npx not installed: jscpd clone check skipped", file=sys.stderr)
    else:
        new_clones, shrunk_clones = compare_clone_pairs(current_clones, baseline["jscpd_clone_pairs"])
        new_findings += new_clones
        shrunk += shrunk_clones

    if arguments.shrink:
        baseline["same_name_functions"] = shrink_same_name_functions(baseline["same_name_functions"], current_names)
        if current_clones is not None:
            baseline["jscpd_clone_pairs"] = shrink_clone_pairs(baseline["jscpd_clone_pairs"], current_clones)
        baseline_path.write_text(json.dumps(baseline, indent=2) + "\n")
        shrunk = []

    for message in new_findings:
        print(f"duplicate code: {message}. Move the shared code into lib/ and import it.", file=sys.stderr)
    for message in shrunk:
        print(f"baseline shrank: {message}. Run tests/duplicate_code.py --shrink.", file=sys.stderr)
    if new_findings or shrunk:
        sys.exit(1)


if __name__ == "__main__":
    main()
