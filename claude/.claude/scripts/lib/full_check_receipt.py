"""The full-check receipt: the one record that a full check ran on a tree, written only by review/full_check.py and
read by every gate that asks whether it did. A gate never matches a command's text or a result line to decide that.

Store: append-only JSON lines at `git rev-parse --git-path full-check/receipts.jsonl`, so each work tree keeps its own.
Every row carries the `run_id` of one run and a `kind`:

  started   before the check starts: ts, configured (the CLAUDE.md `Quality check:` command), command (the command run),
            left_out (the Expected red steps it left out: [{"command", "until"}]).
  step      one per && step of the command run, written from the parsed command before it starts: index, step (its
            text), runs_tests, scope (its lib/check_scope.py scope; a test step with scope "targeted"
            voids the receipt).
  finished  ts, result (full_check's result string), exit (of the whole command), timed_out, ci (the repo leaves its
            full suite to CI), satisfied (the run met the full check this phase owes: the command exited 0, or there
            was no command to run; a runner summary that reports failures voids an exit 0),
            tree (the tree fingerprint after the check and its rewrites: the `tree:` line full_check prints), head (the
            commit HEAD named then; the fingerprint does not cover it), log (the check's log file as an absolute path,
            left out of the fingerprint).

A receipt is valid for the current tree when the latest started run has a finished row that is satisfied, none of its
test steps has scope "targeted", HEAD still names the commit in its head, and its tree fingerprint
equals the current tree's, taken with the same log left out.
A later started run with no finished row (a killed run) leaves no older receipt valid.
"""
import datetime
import pathlib
import uuid

import reviewed_tree
import script_utils

RECEIPTS_GIT_PATH = "full-check/receipts.jsonl"
STARTED, STEP, FINISHED = "started", "step", "finished"


def receipts_path(repo):
    """The receipts file of the work tree that holds `repo`, or None outside a git work tree."""
    return script_utils.git_path(repo, RECEIPTS_GIT_PATH)


def current_tree(repo, log=None):
    """The fingerprint (lib/reviewed_tree.py) of the work tree that holds `repo` now, `log` left out, or None when it
    cannot be taken."""
    try:
        return reviewed_tree.work_tree_fingerprint(repo, log)
    except (reviewed_tree.TreeFingerprintError, OSError):
        return None


def current_head(repo):
    """The commit HEAD names in the work tree that holds `repo` ("unborn" before the first commit), or None when it
    cannot be read."""
    top = script_utils.repo_root(repo)
    if top is None:
        return None

    found = reviewed_tree.fingerprint_base(top)
    return found[0] if found else None


def append(repo, row):
    """Append one row to the repo's receipts file in a single write. A repo outside git keeps no receipts."""
    path = receipts_path(repo)
    if path is None:
        return
    stamp = datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")
    script_utils.append_jsonl(path, {"ts": stamp, **row})


def write_started_row(repo, configured, command, left_out=()):
    """Write the started row, before the check process starts. Returns the run id."""
    run_id = uuid.uuid4().hex
    append(repo, {"kind": STARTED, "run_id": run_id, "configured": configured, "command": command,
                  "left_out": [{"command": entry["command"], "until": entry["until"]} for entry in left_out]})
    return run_id


def write_step_row(repo, run_id, index, step, runs_tests, scope):
    """Write the row of one && step of the command about to run. `scope` is the step's lib/check_scope.py scope."""
    append(repo, {"kind": STEP, "run_id": run_id, "index": index, "step": step, "runs_tests": runs_tests,
                  "scope": scope})


def write_finished_row(repo, run_id, result, exit_code, timed_out, ci, satisfied, tree, log):
    """Write the finished row. `tree` is the fingerprint of the work tree after the check and its rewrites; `head` is
    the commit HEAD names when the row is written, which the fingerprint does not cover."""
    log_file = str(pathlib.Path(log).resolve()) if log else ""
    append(repo, {"kind": FINISHED, "run_id": run_id, "result": result, "exit": exit_code,
                  "timed_out": timed_out, "ci": ci, "satisfied": satisfied, "tree": tree,
                  "head": current_head(repo), "log": log_file})


def latest_run(repo):
    """(started row, the rest of that run's rows) of the latest started run, or (None, [])."""
    path = receipts_path(repo)
    rows = script_utils.read_jsonl(path) if path else []
    starts = [index for index, row in enumerate(rows) if row.get("kind") == STARTED]
    if not starts:
        return None, []

    started = rows[starts[-1]]
    return started, [row for row in rows[starts[-1] + 1:] if row.get("run_id") == started.get("run_id")]


def latest_receipt(repo):
    """(why no receipt is valid for the work tree of `repo` as it stands, or None when one is; the finished row of the
    latest run, or None when it never finished). Reads the receipts file once."""
    started, rows = latest_run(repo)
    if started is None:
        return "no full check has run in this work tree", None

    finished = next((row for row in reversed(rows) if row.get("kind") == FINISHED), None)
    if finished is None:
        return "the latest full check run never finished (it was killed or is still running)", None
    if not finished.get("satisfied"):
        return f"the latest full check run did not verify the tree: {finished.get('result')}", finished

    # A declared check that names files, excludes tests or selects some in a test step is no full check. A step whose
    # scope cannot be read (a make call with a NAME=value argument) or that was scored none (cargo test, go test ./...,
    # unittest discover) is let through.
    scoped = next((row for row in rows if row.get("kind") == STEP and row.get("runs_tests")
                   and row.get("scope") == "targeted"), None)
    if scoped is not None:
        return f"the latest full check run was scoped: `{scoped.get('step')}`", finished

    ran_on = finished.get("tree")
    if not ran_on:
        return "the latest full check run recorded no tree fingerprint", finished
    if finished.get("head") != current_head(repo):
        return "HEAD moved after the latest full check run", finished
    if ran_on != current_tree(repo, finished.get("log")):
        return "the work tree changed after the latest full check run", finished
    return None, finished


def receipt_problem(repo):
    """Why no receipt is valid for the work tree of `repo` as it stands, or None when one is."""
    problem, _finished = latest_receipt(repo)
    return problem


def valid_receipt(repo):
    """The finished row of the latest full check run when it is a valid receipt for the work tree of `repo` as it
    stands, else None. `receipt_problem` says why none is valid."""
    problem, finished = latest_receipt(repo)
    if problem is not None:
        return None
    return finished
