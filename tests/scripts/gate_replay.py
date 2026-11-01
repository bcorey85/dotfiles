"""Replay the hand-labelled corpus of Bash calls against the local hook gates and print five metrics per gate.

Each call in gate_replay_corpus.json names a gate, a command and its labels (the file's `labels` key says what each
means). The replay runs every call through a fresh gate process in a throwaway fixture repo and prints, per gate:
denials, redundant denials, must-deny bypasses, deny-text tokens and the median fresh-process latency.

    python3 tests/scripts/gate_replay.py [--ref <git ref>]

--ref replays the gates as they stand at that ref beside the working tree. Exits 1 when the working tree bypasses a
must-deny call or decides a call against its label, and names each such call.
"""
import argparse
import io
import json
import os
import pathlib
import statistics
import subprocess
import sys
import tarfile
import tempfile
import time
from dataclasses import dataclass

import toolkit_paths

CORPUS = pathlib.Path(os.environ.get("GATE_REPLAY_CORPUS")
                      or pathlib.Path(__file__).resolve().with_name("gate_replay_corpus.json"))
# Each gate's file name, found in whichever folder under the scripts folder holds it, and how it reads a call: `hook`
# reads the PreToolUse JSON and denies with decision JSON on stdout; `command` reads the bare command and denies with
# exit 1.
GATES = {
    "shell-write-gate": ("shell_write_gate.py", "hook"),
    "git-discipline-gate": ("git_discipline_gate.py", "hook"),
    "inline-interpreter-hint": ("inline_interpreter_hint.py", "hook"),
    "pipe-shell-check": ("pipe_shell_check.py", "command"),
}
FIXTURE_REPOS = ("feature", "main")
REQUIRED_KEYS = {"id": str, "gate": str, "command": str, "expect": str, "mustDeny": bool, "redundant": bool,
                 "source": str}
OPTIONAL_KEYS = {"repo": str, "agent": str, "open": str}
# Deny-text tokens are estimated at four characters a token.
CHARACTERS_PER_TOKEN = 4
WORKING_TREE = "working tree"
# A gate call takes milliseconds; one that runs this long is hung.
GATE_TIMEOUT_SECONDS = 30


class CorpusError(Exception):
    pass


class ReplayError(Exception):
    pass


@dataclass
class Outcome:
    call: dict
    denied: bool
    reason: str
    elapsed_ms: float


def load_corpus(corpus_path):
    """The corpus calls, after every label is checked. Raises CorpusError naming the call and the bad label."""
    try:
        calls = json.loads(pathlib.Path(corpus_path).read_text())["calls"]
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise CorpusError(f"{corpus_path}: cannot read the corpus ({error})") from error

    seen_ids = set()
    for position, call in enumerate(calls):
        call_name = call.get("id") or f"call {position}"
        problem = call_label_problem(call, seen_ids)
        if problem:
            raise CorpusError(f"{corpus_path}: {call_name}: {problem}")
        seen_ids.add(call["id"])
    return calls


def call_label_problem(call, seen_ids):
    for key, kind in REQUIRED_KEYS.items():
        if not isinstance(call.get(key), kind):
            return f"needs `{key}` as a {kind.__name__}"
    unknown_keys = set(call) - set(REQUIRED_KEYS) - set(OPTIONAL_KEYS)
    if unknown_keys:
        return f"unknown keys {sorted(unknown_keys)}"
    for key, kind in OPTIONAL_KEYS.items():
        if key in call and not isinstance(call[key], kind):
            return f"`{key}` must be a {kind.__name__}"

    if call["id"] in seen_ids:
        return "duplicate id"
    if call["gate"] not in GATES:
        return f"gate must be one of {sorted(GATES)}"
    if call["expect"] not in ("allow", "deny"):
        return "expect must be allow or deny"
    if call.get("repo", "feature") not in FIXTURE_REPOS:
        return f"repo must be one of {list(FIXTURE_REPOS)}"
    if (call["mustDeny"] or call["redundant"]) and call["expect"] != "deny":
        return "mustDeny and redundant label a deny, so expect must be deny"
    if call["mustDeny"] and "open" in call:
        return "a mustDeny call cannot carry an open mismatch"
    return None


def build_fixture(root):
    """A home folder and one repo per fixture branch under root, each with a tracked and an untracked file."""
    home = root / "home"
    home.mkdir()

    repos = {}
    for branch in FIXTURE_REPOS:
        repo = root / f"repo-{branch}"
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "symbolic-ref", "HEAD", f"refs/heads/{branch}"], check=True)
        (repo / "tracked.txt").write_text("x\n")
        (repo / "untracked.txt").write_text("x\n")
        subprocess.run(["git", "-C", str(repo), "add", "tracked.txt"], check=True)
        repos[branch] = repo

    environment = {"PATH": os.environ["PATH"], "HOME": str(home), "TMPDIR": str(root)}
    return repos, environment


def run_call(gate_script, reads, call, repos, environment):
    repo = repos[call.get("repo", "feature")]
    if reads == "hook":
        payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": call["command"]},
                   "cwd": str(repo)}
        if "agent" in call:
            payload["agent_type"] = call["agent"]
        stdin_text = json.dumps(payload)
    else:
        stdin_text = call["command"]

    started = time.perf_counter()
    try:
        finished = subprocess.run([sys.executable, str(gate_script)], input=stdin_text, capture_output=True, text=True,
                                  env=environment, cwd=str(repo), timeout=GATE_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as error:
        raise ReplayError(f"{call['id']}: {gate_script} did not finish within {GATE_TIMEOUT_SECONDS} s") from error
    elapsed_ms = (time.perf_counter() - started) * 1000

    if reads == "command":
        if finished.returncode not in (0, 1) or finished.stderr:
            raise ReplayError(f"{call['id']}: {gate_script} exited {finished.returncode}: {finished.stderr}")
        return Outcome(call, finished.returncode == 1, "", elapsed_ms)

    if finished.returncode != 0 or finished.stderr:
        raise ReplayError(f"{call['id']}: {gate_script} exited {finished.returncode}: {finished.stderr}")
    if not finished.stdout:
        return Outcome(call, False, "", elapsed_ms)
    try:
        decision = json.loads(finished.stdout)["hookSpecificOutput"]
        denied = decision["permissionDecision"] == "deny"
        reason = decision["permissionDecisionReason"]
    except (ValueError, KeyError, TypeError) as error:
        raise ReplayError(f"{call['id']}: {gate_script} wrote no decision JSON: {finished.stdout!r}") from error
    return Outcome(call, denied, reason, elapsed_ms)


def replay(scripts_dir, calls, repos, environment):
    """{gate: [Outcome]} for every corpus call, or {gate: None} for a gate whose file scripts_dir lacks."""
    outcomes_by_gate = {}
    for gate, (file_name, reads) in GATES.items():
        try:
            gate_script = toolkit_paths.script_in(scripts_dir, file_name)
        except FileNotFoundError:
            outcomes_by_gate[gate] = None
            continue
        gate_calls = [call for call in calls if call["gate"] == gate]
        outcomes_by_gate[gate] = [run_call(gate_script, reads, call, repos, environment) for call in gate_calls]
    return outcomes_by_gate


def gate_metrics(outcomes):
    denials = [outcome for outcome in outcomes if outcome.denied]
    deny_text_characters = sum(len(outcome.reason) for outcome in denials)
    return {
        "denials": len(denials),
        "redundant": sum(1 for outcome in denials if outcome.call["redundant"]),
        "bypasses": sum(1 for outcome in outcomes if outcome.call["mustDeny"] and not outcome.denied),
        "deny_tokens": deny_text_characters // CHARACTERS_PER_TOKEN,
        "median_ms": statistics.median(outcome.elapsed_ms for outcome in outcomes) if outcomes else 0.0,
    }


def label_problems(outcomes_by_gate):
    """One line per call the gates decide against its labels: a must-deny bypass, a mismatch with no open note, or an
    open call that now matches and must drop its note."""
    problems = []
    for outcomes in outcomes_by_gate.values():
        for outcome in outcomes or []:
            problem = outcome_problem(outcome)
            if problem:
                problems.append(f"{outcome.call['gate']} {outcome.call['id']}: {problem}")
    return problems


def outcome_problem(outcome):
    call = outcome.call
    decided = "deny" if outcome.denied else "allow"
    if call["mustDeny"] and not outcome.denied:
        return "must-deny bypass: the gate allowed it"
    if decided == call["expect"] and "open" in call:
        return f"now decides {decided} as labelled; drop its open note ({call['open']})"
    if decided != call["expect"] and "open" not in call:
        return f"expected {call['expect']}, the gate decided {decided}"
    return None


def scripts_at_ref(ref, destination):
    """Extract claude/.claude/scripts as it stands at ref into destination and return its path there."""
    repo_root = toolkit_paths.TREE_CLAUDE_DIR.resolve().parents[1]
    archive = subprocess.run(["git", "-C", str(repo_root), "archive", ref, "claude/.claude/scripts"],
                             capture_output=True, check=False)
    if archive.returncode != 0:
        raise ReplayError(f"git archive {ref} failed: {archive.stderr.decode(errors='replace').strip()}")

    with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as scripts_archive:
        scripts_archive.extractall(destination, filter="data")
    return pathlib.Path(destination) / "claude" / ".claude" / "scripts"


# The width of each column of the metrics table, in header order.
COLUMN_WIDTHS = (25, 16, 7, 9, 18, 16, 9)
# The gate and side columns are left-aligned; the metric columns after them are right-aligned.
LEFT_ALIGNED_COLUMNS = 2


def format_row(cells):
    """One line of the metrics table: each cell padded to its column width. A row may give only its leading cells."""
    padded = []
    for index, cell in enumerate(cells):
        width = COLUMN_WIDTHS[index]
        if index < LEFT_ALIGNED_COLUMNS:
            padded.append(f"{cell:<{width}}")
        else:
            padded.append(f"{cell:>{width}}")
    return " ".join(padded)


def metrics_table(results_by_side):
    """Rows of the five metrics, one per gate and side; a gate missing on a side prints dashes."""
    header = format_row(["gate", "side", "denials", "redundant", "must-deny bypasses", "deny-text tokens", "median ms"])
    lines = [header]
    for gate in GATES:
        for side, outcomes_by_gate in results_by_side.items():
            outcomes = outcomes_by_gate[gate]
            if outcomes is None:
                row = format_row([gate, side, "-", "-", "-", "-", "-"])
                lines.append(row)
                continue
            metrics = gate_metrics(outcomes)
            median_cell = f"{metrics['median_ms']:.1f}"
            row = format_row([gate, side, metrics["denials"], metrics["redundant"], metrics["bypasses"],
                              metrics["deny_tokens"], median_cell])
            lines.append(row)
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ref", help="also replay the gates as they stand at this git ref")
    arguments = parser.parse_args(argv)

    try:
        calls = load_corpus(CORPUS)
    except CorpusError as error:
        print(error, file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory(prefix="gate-replay-") as fixture_root:
        repos, environment = build_fixture(pathlib.Path(fixture_root))
        try:
            working_tree_results = replay(toolkit_paths.SCRIPTS_DIR, calls, repos, environment)
            absent_gates = [gate for gate, outcomes in working_tree_results.items() if outcomes is None]
            if absent_gates:
                absent_list = ", ".join(absent_gates)
                raise ReplayError(f"the working tree has no gate file for: {absent_list}")
            results_by_side = {WORKING_TREE: working_tree_results}
            if arguments.ref:
                ref_scripts = scripts_at_ref(arguments.ref, pathlib.Path(fixture_root) / "at-ref")
                results_by_side[arguments.ref] = replay(ref_scripts, calls, repos, environment)
        except ReplayError as error:
            print(error, file=sys.stderr)
            return 2

    print(f"{len(calls)} calls from {CORPUS}")
    print("\n".join(metrics_table(results_by_side)))

    working_tree_problems = label_problems(results_by_side[WORKING_TREE])
    if arguments.ref:
        print(f"{arguments.ref}: {len(label_problems(results_by_side[arguments.ref]))} calls against their labels")
    if working_tree_problems:
        print(f"working tree: {len(working_tree_problems)} calls against their labels", file=sys.stderr)
        print("\n".join(working_tree_problems), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
