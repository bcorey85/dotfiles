# Toolkit scripts

These rules apply to every script under `claude/.claude/scripts/` and `claude/.claude/skills/*/scripts/`, and to every draft of one.

`claude/.claude/scripts/` holds one folder per concern: `code/` (code-step and coder gate), `review/` (review loop, hand-back, verify), `telemetry/` (log writers and the telemetry switch), `lib/` (shared modules: `script_utils.py`, `hook_input.py`, `plan_format.py`, `shell_command.py`, `makefile_text.py`, `_kv.sh`), `tools/` (small commands), `gates/` (hook gates). The three security hooks stay at the top. A script finds its siblings through `sys.path` lines computed from `pathlib.Path(__file__).resolve()`; imports stay bare module names.

## Names

- Name every Python file in snake_case, as PEP 8 says: `review_fix.py`, `script_utils.py`. Python cannot import a name with a hyphen.
- Name functions, methods, variables, parameters and attributes in snake_case, classes in CapWords and constants in UPPER_CASE, as PEP 8 says. Keep the names of JSON keys, log fields and state-file keys as they are: files on disk already hold them.
- `ruff check` with the repo `ruff.toml` must pass before hand-over. Ignore a rule only in `ruff.toml`, with a comment that says why its fix makes the code worse.

## Read the real inputs first

- Before you write code that reads text a model or a person wrote (a plan, a packet, a report, a transcript), collect the real files it will read. On this machine: plans under `~/dev/*/docs/plans/`, code-step state under each repo's `git rev-parse --git-path code-step`, and subagent transcripts under `~/.claude/projects/`.
- List every shape in those files before you write the grammar: id forms, heading levels, indents, optional sections, empty values. Write the grammar from that list, not from one example.
- Work files never come to this machine. If the work machine also writes the format, count its shapes with an intake script that prints labels and counts only, and read the counts before you trust the grammar.
- When you fix a script bug, search the real files for every other shape of the same kind, and fix all of them in one change. A second report of the same kind of bug means that the first fix covered a case, not the class.

## One grammar, loud failures

- Read each format through one function, and make every caller use it. Never parse the same format with a second regex.
- Stop on any input the grammar does not parse. Print the file, the line and the expected form, and exit non-zero. Never skip the line, guess, or use a default.
- Give each format a `check` command. Run it where the text is written: in the skill step right after the write, or in an edit hook. A bad file then fails when it is written, not in the middle of a run.

## Callers and events

- Before you change a script's output, exit code or arguments, search the toolkit for every caller: skills, agents, hooks, other scripts and `settings.json`. Test that each caller still reads the new output.
- For a hook script, capture one real event of each type that it reads, and keep it as a fixture. Write the code against the captured fields. Never assume that a field holds a result at that event: an agent launch event fires before the agent finishes.

## Changes during a run

- List each way that the input or the state can change while a run is open: the main session adds a phase or a step, the user edits the file, a step runs twice, the branch changes. Write a route only for a change that a session reported. Send every other change to one fallback stop that names the state and the recovery command.
- Every verb ends with a next command, a stop with a reason, or done. Test a step script with a walk over every state and verb, not one happy path. The walk fails when a path repeats a step or never ends.

## Size

- Add code for a defect only when a session hit it, or when it fires on every run. A case that only a reviewer or a designer thought of gets the fallback stop, not new code.
- Before you write a helper, search `lib/` (`script_utils.py`, `hook_input.py`, `plan_format.py`, `shell_command.py`, `makefile_text.py`) and the other scripts for one that does the job. Use it, or move it into a shared module and make both callers use it.
- Do not add a verb, a route or a state field to a script over 1000 lines. First split it by concern, or cut it.
- When a design gives a size estimate, report the real diff size at hand-over. If the diff is more than twice the estimate, stop and report to the orchestrator before review.

## Tests

- Put the tests in `~/dotfiles/tests/scripts/test_<script>.py`. Each test file reads the script path from one environment variable that defaults to the installed path. Run the tests against the draft before hand-over, and against the installed path after the install.
- Add a test that fails without the change. Copy each real input shape that broke into a fixture.
- Before hand-over, run the draft over every real input that you collected and report "parsed N of M". Name each failure as a bad input or a script gap.
- Run `bash ~/dotfiles/tests/run.sh` before you say that the change is done.
