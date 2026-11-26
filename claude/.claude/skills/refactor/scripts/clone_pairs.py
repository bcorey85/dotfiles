"""Clone detection for /refactor: run jscpd, read its JSON report, and keep the pairs on the lines a branch
changed.

Used by refactor_flow.py (audit-prep and branch-prep) and the duplicate-code gate in
tests/duplicate_code.py. Plain functions; no repo state beyond the paths passed in.
"""
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts" / "lib"))
from changed_lines import changed_line_sets, range_touched

MAX_CLONE_PAIRS = 40
AUDIT_MIN_TOKENS = 70
BRANCH_MIN_TOKENS = 40
JSCPD_TIMEOUT_SECONDS = 120
# The version whose JSON report read_pairs reads; a newer release may write another shape.
JSCPD_PACKAGE = "jscpd@5.4.3"
REPORT_NAME = "jscpd-report.json"
# Prompt-text ports repeat prose on purpose; those pairs would fill the listing cap.
PROSE_FORMATS = {"markdown", "text", "txt"}
HEAD_MODE_NOTE = "clone detection reads the work tree only; skipped with --head"
NO_DETECTION_NOTE = "no mechanical detection — agent prior-art search only"
EXPECTED_REPORT_FORM = ("a JSON object whose `duplicates` list holds entries with a `format` string and "
                        "`firstFile`/`secondFile` objects of `name`, `start` and `end`")


class CloneSite(NamedTuple):
    path: str
    first_line: int
    last_line: int


class ClonePair(NamedTuple):
    sites: list  # CloneSite entries
    format: str


def not_parsed_note(report_file, reason):
    return f"jscpd output did not parse: {report_file}: {reason} (expected {EXPECTED_REPORT_FORM})"


def read_site(fragment, prefix):
    """The CloneSite for one `firstFile` or `secondFile` object; raises KeyError, TypeError or ValueError when it
    lacks `name`, `start` or `end`. `prefix` is the directory jscpd wrote the name relative to."""
    name = fragment["name"]
    if not isinstance(name, str):
        raise TypeError(f"name is {name!r}")
    if prefix:
        name = os.path.normpath(os.path.join(prefix, name))
    first_line = int(fragment["start"])
    last_line = int(fragment["end"])
    return CloneSite(name, first_line, last_line)


def read_pair(duplicate, prefix):
    clone_format = duplicate["format"]
    if not isinstance(clone_format, str):
        raise TypeError(f"format is {clone_format!r}")
    sites = [read_site(duplicate["firstFile"], prefix), read_site(duplicate["secondFile"], prefix)]
    return ClonePair(sites, clone_format)


def read_pairs(report_file, prefix=""):
    """(pairs, note) from jscpd's JSON report. A missing or misshapen report gives no pairs and a note; never raises."""
    try:
        report = json.loads(Path(report_file).read_text())
    except (OSError, ValueError) as error:
        return [], not_parsed_note(report_file, str(error))

    try:
        return [read_pair(duplicate, prefix) for duplicate in report["duplicates"]], ""
    except (KeyError, TypeError, ValueError) as error:
        return [], not_parsed_note(report_file, f"{type(error).__name__} {error}")


def run_jscpd(target, timeout, min_tokens=AUDIT_MIN_TOKENS, cwd=None):
    """Returns (clone_pairs, note). Never raises: detector failure is a note, not a stop."""
    override = os.environ.get("REFACTOR_JSCPD_CMD")
    if override:
        command = shlex.split(override)
    elif shutil.which("npx"):
        command = ["npx", "--yes", JSCPD_PACKAGE]
    else:
        return [], NO_DETECTION_NOTE

    with tempfile.TemporaryDirectory() as work_dir:
        try:
            done = subprocess.run([*command, target, "--min-tokens", str(min_tokens), "--reporters", "json",
                                   "--output", work_dir],
                                  capture_output=True, text=True, timeout=timeout, cwd=cwd)
        except (subprocess.TimeoutExpired, OSError):
            return [], NO_DETECTION_NOTE
        if done.returncode not in (0, 1):
            return [], NO_DETECTION_NOTE

        # jscpd writes site names relative to the target directory.
        target_path = Path(cwd or ".") / target
        prefix = target if target_path.is_dir() else ""
        return read_pairs(Path(work_dir) / REPORT_NAME, prefix)


def site_touches(site, changed):
    return range_touched(changed, site.path, site.first_line, site.last_line)


def pairs_on_changed_lines(pairs, changed):
    """The pairs with at least one site on a changed line. A pair whose sites all sit in unchanged lines is old debt."""
    return [pair for pair in pairs if any(site_touches(site, changed) for site in pair.sites)]


def branch_pairs(diff_files, untracked, root, timeout):
    """(pairs, note): the pairs over the whole repo at `root` that have a site on a line the branch changed.
    `diff_files` are parsed diff files (source_text.FileDiff)."""
    pairs, note = run_jscpd(".", timeout, BRANCH_MIN_TOKENS, cwd=root)
    if note:
        return [], note

    code_pairs = [pair for pair in pairs if pair.format not in PROSE_FORMATS]
    changed = changed_line_sets(diff_files, untracked)
    return pairs_on_changed_lines(code_pairs, changed), ""


def clone_summary_line(pairs, note, no_pairs_text, scope=""):
    """The one summary line for a clone run: the note, the pair count, or `no_pairs_text` when jscpd found none.
    `scope` is extra words after `clone pair(s)` in the count line."""
    if note:
        return f"- {note}"
    if not pairs:
        return f"- {no_pairs_text}"
    listed_count = len(listed_pairs(pairs))
    return f"- {len(pairs)} clone pair(s){scope}; {listed_count} listed in the dispatch prompt below"


def listed_pairs(pairs):
    """The pairs the dispatch prompt lists."""
    return pairs[:MAX_CLONE_PAIRS]


def pair_lines(pair):
    site_lines = [f"- {site.path} [{site.first_line} - {site.last_line}]" for site in pair.sites]
    return [f"Clone found ({pair.format})", *site_lines]


def print_candidate_pairs(pairs, instruction):
    """Print up to MAX_CLONE_PAIRS pairs, the count left out, and the instruction for judging them."""
    listed = listed_pairs(pairs)
    print("Candidate clone pairs (jscpd):")
    for pair in listed:
        print("\n".join(pair_lines(pair)))
    unlisted_count = len(pairs) - len(listed)
    if unlisted_count:
        print(f"{unlisted_count} more pair(s) not listed")
    print(instruction)
