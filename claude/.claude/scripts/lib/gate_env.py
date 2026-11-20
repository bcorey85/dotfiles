"""The environment variables a repo's gate commands need: the plans' `NAME=value` words and the ones a personal
per-repo file lists. Also `check_env`, the owner of the environment the coder gate, full_check.py,
criteria_dry_run.py and gate_commands.project_python_runner run a check command in (the pyenv pin).
The linters of lib/format_files.py run in the caller's own environment.

The personal file is `~/.claude/gate-env.json` (the file `CLAUDE_GATE_ENV_FILE` names instead, when set), shaped
{"<repo name>": ["NAME=value", ...]}. It lives in the home folder, so a company repo gets no toolkit file. Plan text is
read through plan_format; this module reads and checks the personal file and merges it under the plans' assignments.
"""
import json
import os
import pathlib

import plan_format
import script_utils

PERSONAL_GATE_ENV_FILE = pathlib.Path("~/.claude/gate-env.json")
PERSONAL_GATE_ENV_VAR = "CLAUDE_GATE_ENV_FILE"
PYTHON_VERSION_FILE = ".python-version"


def main_checkout_pin(repo):
    """The `.python-version` file of the repo's main checkout, or None when git cannot say or the main checkout has
    none. Read only when the repo has no pin of its own, as a linked worktree has when the file is gitignored and not
    linked."""
    main_dir = script_utils.main_checkout_dir(repo)
    if main_dir is None or main_dir.is_bare:
        return None

    pin_file = main_dir.folder / PYTHON_VERSION_FILE
    if not pin_file.is_file():
        return None
    return pin_file


def own_pin_exists(repo):
    """Whether `repo` or a folder above it, up to the top of its work tree, has a `.python-version`: the pyenv
    walk from a subfolder, cut off at the top of the work tree."""
    start = pathlib.Path(repo).resolve()
    top = (script_utils.repo_root(repo) or start).resolve()
    return script_utils.nearest_file_upward(start, PYTHON_VERSION_FILE, top) is not None


def check_env(repo, env=None):
    """The full environment the coder gate, full_check.py, criteria_dry_run.py and gate_commands.project_python_runner
    run a check command of `repo` in: `env` (default `os.environ`) as a new dict. The repo's Python pin is the
    nearest `.python-version` from `repo` up to the top of its work tree, else the main checkout's. When only the
    main checkout pins a version, PYENV_VERSION is that file's first non-empty line, unless `env` already sets
    PYENV_VERSION, which wins as in pyenv's own order. With a pin, `$PYENV_ROOT/shims` (default `~/.pyenv/shims`)
    goes first on PATH when it is a folder. With no pin the env is unchanged."""
    environment = dict(os.environ if env is None else env)
    if not own_pin_exists(repo):
        pin_file = main_checkout_pin(repo)
        if pin_file is None:
            return environment

        version = script_utils.first_nonempty_line(pin_file)
        if version:
            # pyenv reads PYENV_VERSION before any .python-version file, so the caller's value stays.
            environment.setdefault("PYENV_VERSION", version)

    pyenv_root = pathlib.Path(environment.get("PYENV_ROOT") or pathlib.Path.home() / ".pyenv")
    shims = pyenv_root / "shims"
    if shims.is_dir():
        environment["PATH"] = os.pathsep.join([str(shims), environment.get("PATH", "")])
    return environment


def repo_gate_env(repo_root, plan_rel=None):
    """The environment variables the repo's gate commands need: the plans' assignments (`plan_format.plan_gate_env`)
    on top of the ones the personal file lists for the repo (`personal_gate_env`). A plan's assignment wins for the
    same name. Raises ValueError when the personal file is malformed."""
    root = pathlib.Path(repo_root)
    personal = personal_gate_env(root)
    planned = plan_format.plan_gate_env(root, plan_rel)
    return script_utils.last_per_name(personal + planned)


def gate_env_repo_name(root):
    """The key of the personal gate-env file: the last part of the origin URL without `.git`, else the name
    `script_utils.repo_name` gives (the main checkout's folder name)."""
    origin_url = script_utils.git_output(root, "remote", "get-url", "origin")
    if origin_url:
        return script_utils.repo_name_from_url(origin_url)

    return script_utils.repo_name(str(root))


def personal_gate_env_file():
    """The personal gate-env file: the file `CLAUDE_GATE_ENV_FILE` names, else `~/.claude/gate-env.json`."""
    return pathlib.Path(os.environ.get(PERSONAL_GATE_ENV_VAR) or PERSONAL_GATE_ENV_FILE).expanduser()


def personal_gate_env(root):
    """The literal `NAME=value` words that the personal file (`personal_gate_env_file`) lists under this repo's name.
    A missing file gives []. Raises ValueError naming the file and the entry for text that is not JSON, a shape other
    than {"<repo>": ["NAME=value", ...]}, or a word that is not a literal NAME=value (no quoting the loop cannot read
    back, no `$`, `;` or other shell syntax)."""
    env_file = personal_gate_env_file()
    try:
        file_text = env_file.read_text()
    except FileNotFoundError:
        return []

    try:
        listed = json.loads(file_text)
    except json.JSONDecodeError as error:
        raise ValueError(f"{env_file}: not valid JSON: {error}") from error

    if not isinstance(listed, dict):
        raise ValueError(f'{env_file}: expected {{"<repo name>": ["NAME=value", ...]}}, got {listed!r}')
    for repo, assignments in listed.items():
        if not script_utils.is_string_list(assignments):
            raise ValueError(f'{env_file}: entry {repo!r} must be a list of "NAME=value" words, got {assignments!r}')
        for word in assignments:
            if "\n" in word or not script_utils.ENV_ASSIGNMENT.fullmatch(word):
                raise ValueError(f"{env_file}: entry {repo!r}: {word!r} is not a literal NAME=value")

    return listed.get(gate_env_repo_name(root), [])
