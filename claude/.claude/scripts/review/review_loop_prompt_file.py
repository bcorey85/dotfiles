"""review_loop_prompt_file.py: the prompt file of a scripted review loop run, and the command that starts the run.

The prompt file is header lines (`key: value`), a blank line, then the handoff block. The header keys are lane
(required), mode, caller, repo, plan, phase, later-phase files, guidance, structure-pass, and:
  base: <commit>            review every change since the commit, commits included
  files: <path>, <path>     review only these files
  held files: <path>, ...   files another session holds (dirty at the run's start, not the run's own): never
                            reviewed, never edited
  findings: <json file>     fix-first: a JSON list of finding texts the fix coder applies before any review
  user-ruled: <n>, <n>      the 1-based numbers of the findings the user accepted
  user-ruled-at: <time>     when the fix run was launched, the time the coder is told those findings were accepted;
                            required with user-ruled (read_prompt stops without it)
  no-review: yes            fix-first with no review after the fix
  reviewer-model: <model>   the model every reviewer runs on
  iter: <n>                 review rounds an earlier run of the same review already used
"""
import json
import pathlib
import sys

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent / "../lib")]
import script_utils

# Who runs the reviewers (--reviewers): `claude -p` calls of the loop script, or the main session as its subagents.
REVIEWERS_HEADLESS = "headless"
REVIEWERS_MAIN = "main"
BASE_KEY = "base"
FILES_KEY = "files"
HELD_FILES_KEY = "held files"
FINDINGS_KEY = "findings"
USER_RULED_HEADER_KEY = "user-ruled"
USER_RULED_AT_KEY = "user-ruled-at"
NO_REVIEW_KEY = "no-review"
REVIEWER_MODEL_KEY = "reviewer-model"
ITER_KEY = "iter"
LIST_SEPARATOR = ", "
YES = "yes"


class PromptFileError(ValueError):
    """A prompt file, or a file its header names, that does not hold the expected form."""


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


def header_user_ruled(header, findings):
    """The texts of the findings the user-ruled line names, [] when the header has none. A number that is no whole
    number, or names no finding, stops the run."""
    words = header_list(header, USER_RULED_HEADER_KEY)
    for word in words:
        if not (word.isascii() and word.isdecimal()):
            raise PromptFileError(f"the prompt file's {USER_RULED_HEADER_KEY} line holds {word!r}; expected the "
                                  f"number of one of the {len(findings)} findings")
    try:
        return script_utils.numbered_items([int(word) for word in words], findings)
    except script_utils.ItemNumberError as error:
        raise PromptFileError(f"the prompt file's {USER_RULED_HEADER_KEY} line holds {str(error.number)!r}; "
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
    prompt_file = script_dir / "prompt.txt"
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
