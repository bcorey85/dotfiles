"""review_loop_prompt_file.py: the prompt file of a scripted review loop run, and the command that starts the run.

The prompt file is header lines (`key: value`), a blank line, then the handoff block. The header keys are lane
(required), mode, caller, repo, plan, phase, later-phase files, guidance, structure-pass, and:
  base: <commit>            review every change since the commit, commits included
  files: <path>, <path>     review only these files
  held files: <path>, ...   files another session holds (dirty at the run's start, not the run's own): never
                            reviewed, never edited
  held-by: <json list>      the proof for held files: one {"path", "session", "claim"} object per file a named
                            session holds. A held file with no row is held without proof: its findings go to the coder
  ruled-out files: <path>, ...  files the user ruled out of this review: never reviewed, no finding on one goes to a
                            coder, and a coder pass never leaves one changed
  findings: <json file>     fix-first: a JSON list of finding texts the fix coder applies before any review
  user-ruled: <n>, <n>      the 1-based numbers of the findings the user accepted
  user-ruled-at: <time>     when the fix run was launched, the time the coder is told those findings were accepted;
                            required with user-ruled (read_prompt stops without it)
  adopted: <json list>      the findings whose plan change a ruling adopted: one {"number", "text", "finding_text",
                            "owner", "ruled_at"} object each, the number among the user-ruled ones; the fix pass must
                            apply each
  session-ruled: <n>, <n>   the 1-based numbers of the findings a session ruled on; the fix coder's re-ask of one is a
                            skip
  no-review: yes            fix-first with no review after the fix
  reviewer-model: <model>   the model every reviewer runs on
  iter: <n>                 review rounds an earlier run of the same review already used
"""
import json
import pathlib
import sys

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent / "../lib")]
import script_utils
from handback_store import AdoptedRuling

# Who runs the reviewers (--reviewers): `claude -p` calls of the loop script, or the main session as its subagents.
REVIEWERS_HEADLESS = "headless"
REVIEWERS_MAIN = "main"
PROMPT_FILE = "prompt.txt"
BASE_KEY = "base"
FILES_KEY = "files"
HELD_FILES_KEY = "held files"
RULED_OUT_FILES_KEY = "ruled-out files"
HELD_BY_KEY = "held-by"
HOLDER_FIELDS = ("path", "session", "claim")
ADOPTED_HEADER_KEY = "adopted"
ADOPTED_FIELDS = ("number", *AdoptedRuling._fields)
FINDINGS_KEY = "findings"
USER_RULED_HEADER_KEY = "user-ruled"
USER_RULED_AT_KEY = "user-ruled-at"
SESSION_RULED_HEADER_KEY = "session-ruled"
NO_REVIEW_KEY = "no-review"
REVIEWER_MODEL_KEY = "reviewer-model"
ITER_KEY = "iter"
LIST_SEPARATOR = ", "
YES = "yes"


class PromptFileError(ValueError):
    """A prompt file, or a file its header names, that does not hold the expected form."""


def holder_row(path, session, claim):
    """One holder row of the held-by line, with the fields `header_held_by` expects."""
    return dict(zip(HOLDER_FIELDS, (path, session, claim), strict=True))


def render_prompt(header, handoff):
    """The prompt file text of [(key, value)] header pairs and a handoff block."""
    lines = [f"{key}: {value}" for key, value in header]
    return "\n".join(lines) + "\n\n" + handoff.strip() + "\n"


def read_prompt(path):
    """({header key: value}, handoff block) of the review prompt file. The header ends at the first blank line."""
    header_text, _separator, handoff = pathlib.Path(path).read_text().partition("\n\n")
    header = {}
    ruled_line_number = 0
    for line_number, line in enumerate(header_text.splitlines(), start=1):
        key, separator, value = line.partition(":")
        if separator:
            header[key.strip()] = value.strip()
        if separator and key.strip() == USER_RULED_HEADER_KEY:
            ruled_line_number = line_number
    if not header.get("lane"):
        raise PromptFileError(f"the prompt file {path} has no lane line")
    if ruled_line_number and not header.get(USER_RULED_AT_KEY):
        raise PromptFileError(f"{path}:{ruled_line_number}: a {USER_RULED_HEADER_KEY} line needs a {USER_RULED_AT_KEY} "
                              f"line; expected `{USER_RULED_AT_KEY}: <time>`")
    return header, handoff.strip()


def header_list(header, key):
    """The comma-separated values of one header line, [] when it is absent."""
    return [value for value in header.get(key, "").split(LIST_SEPARATOR) if value]


def header_json_rows(header, key, expected):
    """The JSON list of one header line, [] when it is absent. A value that is not JSON or not a list stops the run
    with `expected` in the message."""
    value = header.get(key, "")
    if not value:
        return []
    try:
        rows = json.loads(value)
    except json.JSONDecodeError as error:
        raise PromptFileError(f"the prompt file's {key} line is not JSON ({error}); {expected}") from error
    if not isinstance(rows, list):
        raise PromptFileError(f"the prompt file's {key} line holds {value!r}; {expected}")
    return rows


def header_held_by(header):
    """The holder rows of the held-by line as {path: {"path", "session", "claim"}}, {} when the header has none. A
    value that is not a JSON list of objects with those three non-empty string fields stops the run."""
    expected = 'expected a JSON list of {"path": ..., "session": ..., "claim": ...} objects'
    rows = header_json_rows(header, HELD_BY_KEY, expected)
    holders = {}
    for row in rows:
        if not isinstance(row, dict) or not all(
                isinstance(row.get(field), str) and row[field].strip() for field in HOLDER_FIELDS):
            raise PromptFileError(f"the prompt file's {HELD_BY_KEY} line holds the row {row!r}; {expected}")
        holders[row["path"]] = {field: row[field] for field in HOLDER_FIELDS}
    return holders


def header_adopted(header, findings):
    """{finding text: its row} for the adopted line: the rows of the findings it names, {} when the header has none. A
    value that is not a JSON list of objects with the `ADOPTED_FIELDS`, or a number that names no finding, stops the
    run."""
    expected = f"expected a JSON list of objects with the fields {', '.join(ADOPTED_FIELDS)}"
    rows = header_json_rows(header, ADOPTED_HEADER_KEY, expected)
    adopted = {}
    for row in rows:
        if not isinstance(row, dict) or not set(ADOPTED_FIELDS) <= set(row):
            raise PromptFileError(f"the prompt file's {ADOPTED_HEADER_KEY} line holds the row {row!r}; {expected}")
        number = row["number"]
        if not isinstance(number, int) or not 1 <= number <= len(findings):
            raise PromptFileError(f"the prompt file's {ADOPTED_HEADER_KEY} line holds the number {number!r}; "
                                  f"expected the number of one of the {len(findings)} findings")
        adopted[findings[number - 1]] = row
    return adopted


def header_iter(header):
    """The rounds an earlier run already used: 0 when the header has no iter line."""
    value = header.get(ITER_KEY, "0")
    if not (value.isascii() and value.isdecimal()):
        raise PromptFileError(f"the prompt file's iter line holds {value!r}; expected a whole number")
    return int(value)


def write_findings(path, findings):
    pathlib.Path(path).write_text(json.dumps(findings, indent=2) + "\n")


def read_findings(header):
    """The finding texts of a fix-first run, from the JSON file the findings line names."""
    findings_file = header.get(FINDINGS_KEY, "")
    if not findings_file:
        return []
    try:
        findings = json.loads(pathlib.Path(findings_file).read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise PromptFileError(f"{findings_file}: {error}; expected a JSON list of finding texts") from error
    if not script_utils.is_nonblank_string_list(findings):
        raise PromptFileError(f"{findings_file}: expected a JSON list of non-empty finding texts")
    return findings


def header_ruled(header, findings, key):
    """The texts of the findings the `key` line (the user-ruled or session-ruled line) names, [] when the header has
    none. A number that is no whole number, or names no finding, stops the run."""
    words = header_list(header, key)
    for word in words:
        if not (word.isascii() and word.isdecimal()):
            raise PromptFileError(f"the prompt file's {key} line holds {word!r}; expected the "
                                  f"number of one of the {len(findings)} findings")
    try:
        return script_utils.numbered_items([int(word) for word in words], findings)
    except script_utils.ItemNumberError as error:
        raise PromptFileError(f"the prompt file's {key} line holds {str(error.number)!r}; "
                              f"expected the number of one of the {error.item_count} findings") from error


def reviewer_brief(header, handoff):
    lines = [f"{key}: {header[key]}" for key in ("plan", "phase") if header.get(key)]
    if header.get(BASE_KEY):
        base = header[BASE_KEY]
        lines.append(f"Review every change since {base}, commits included: `git diff {base}` plus untracked files.")
    lines += ["Handoff:", handoff]
    return "\n".join(lines)


def write_script_prompt(state_dir, agent_id, prompt):
    """(prompt file, log file) of a script run under <state dir>/loop-script/<agent id>, with the prompt written."""
    script_dir = pathlib.Path(state_dir) / "loop-script" / agent_id
    script_dir.mkdir(parents=True, exist_ok=True)
    prompt_file = script_dir / PROMPT_FILE
    prompt_file.write_text(prompt)
    return prompt_file, script_dir / "script.log"


def loop_script_command(loop_script, repo_dir, state_dir, session_id, agent_id, prompt_file, gate_commands=(),
                        reviewers=REVIEWERS_HEADLESS, gates_every_run=False):
    """The argv that runs review_loop_script.py, with one --gate-command per gate command. gates_every_run makes the
    loop run them on every converged run; a time budget bounds only the run on a converged run with no untested fix."""
    command = [sys.executable, str(loop_script), str(repo_dir), "--state-dir", str(state_dir), "--session", session_id,
               "--agent-id", agent_id, "--prompt-file", str(prompt_file), "--reviewers", reviewers]
    for gate_command in gate_commands:
        command += ["--gate-command", gate_command]
    if gates_every_run:
        command.append("--gates-every-run")
    return command
