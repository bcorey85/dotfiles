"""review_launch.py: `review_fix.py launch`, the start of every /review and /fix run.

It starts review_loop_script.py --reviewers main as a detached process and returns when the loop asks for reviewers
(`ACTION: dispatch-reviewer`, see reviewer_dispatch.py) or when the loop exits. It records the session's dispatch row,
writes the prompt file, the loop's pid and <loop dir>/launch.json (the packet arguments the wait prints), and keeps
its state under <git dir>/review-script.

A findings file (`--fix`) holds one finding per item: a line that starts with `- ` at column 0, then any indented
continuation lines. Blank lines may sit between items. Any other line stops the launch.
"""
import argparse
import json
import os
import pathlib
import subprocess
import sys

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent / folder) for folder in (".", "../lib")]
import handback_hook
import reviewer_dispatch
import script_utils
from review_loop_plan import review_files
from review_loop_prompt_file import (
    BASE_KEY,
    FILES_KEY,
    FINDINGS_KEY,
    ITER_KEY,
    LIST_SEPARATOR,
    NO_REVIEW_KEY,
    REVIEWER_MODEL_KEY,
    REVIEWERS_MAIN,
    YES,
    loop_script_command,
    render_prompt,
    write_findings,
    write_script_prompt,
)

STATE_NAME = reviewer_dispatch.LAUNCH_STATE_NAME
AGENT_PREFIX = "review-script-"
DEFAULT_HANDOFF = "Review the working tree against HEAD."
FAST_REVIEWER_MODEL = "haiku"
FINDINGS_JSON = "findings.json"
FINDING_START = "- "
FINDINGS_FORM = "expected `- <finding>` at column 0, an indented continuation line, or a blank line"


class LaunchError(ValueError):
    """A launch that cannot start: the message says why, and nothing was launched."""


def launch_parser():
    parser = argparse.ArgumentParser(
        prog="review_fix.py launch", add_help=False,
        description="Start the scripted review loop. With no flag it reviews the working tree against HEAD.")
    parser.error = lambda message: (_ for _ in ()).throw(LaunchError(message))
    parser.add_argument("-h", "--help", action="help", help="show this help and exit")
    parser.add_argument("--repo", help="absolute path of the repo to review, when it is not the cwd's repo")
    parser.add_argument("--fix", metavar="FINDINGS_FILE",
                        help="fix-first: the fix coder applies these findings, then the loop reviews")
    parser.add_argument("--no-review", action="store_true", help="with --fix: apply the findings and review nothing")
    parser.add_argument("--base", help="review every change since this ref, commits included")
    parser.add_argument("--file", action="append", default=[], dest="files",
                        help="review only this file (repeatable): absolute, or relative to the repo root")
    parser.add_argument("--handoff", metavar="FILE", help="the handoff block the reviewers and coder read")
    models = parser.add_mutually_exclusive_group()
    models.add_argument("--fast", action="store_true", help=f"run the reviewers on {FAST_REVIEWER_MODEL}")
    models.add_argument("--deep", action="store_true", help="run the reviewers on their agents' own model")
    parser.add_argument("--iter", type=int, default=0, help="review rounds an earlier run of this review used")
    parser.add_argument("--lane", help="lane of the run (default none for review, code for fix)")
    return parser


def launch_arguments(argv):
    options = launch_parser().parse_args(argv)
    if options.no_review and not options.fix:
        raise LaunchError("--no-review needs --fix: a review-first run with no review does nothing")
    if options.iter < 0:
        raise LaunchError(f"--iter {options.iter} is negative; expected the rounds an earlier run used")
    options.skill = "fix" if options.fix else "review"
    options.lane = options.lane or ("code" if options.fix else "none")
    return options


def read_findings_file(findings_file):
    """The finding texts of a findings file, one per `- ` item, continuation lines joined with a space."""
    try:
        lines = pathlib.Path(findings_file).read_text().splitlines()
    except OSError as error:
        raise LaunchError(f"--fix {findings_file}: {error}") from error

    findings = []
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        if line.startswith(FINDING_START):
            findings.append(line[len(FINDING_START):].strip())
            continue
        if line[0].isspace() and findings:
            findings[-1] += " " + line.strip()
            continue
        raise LaunchError(f"{findings_file}:{number}: {line!r}; {FINDINGS_FORM}")
    if not findings or not all(findings):
        raise LaunchError(f"{findings_file}: no finding text; {FINDINGS_FORM}")
    return findings


def resolved_base(repo, base):
    commit = script_utils.git_output(repo, "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}")
    if not commit:
        raise LaunchError(f"--base {base} names no commit in {repo}")
    return commit.strip()


def repo_paths(repo, files):
    """Each --file as a path relative to the repo root. A path neither on disk nor changed in the range stops."""
    paths = []
    for given in files:
        full = pathlib.Path(given) if pathlib.Path(given).is_absolute() else repo / given
        try:
            relative = full.resolve().relative_to(repo)
        except ValueError as error:
            raise LaunchError(f"--file {given} is outside the repo {repo}") from error
        paths.append(relative.as_posix())
    return paths


def check_files_exist(repo, paths, base):
    changed = review_files(repo, base)
    missing = [path for path in paths if not (repo / path).exists() and path not in changed]
    if missing:
        raise LaunchError(f"--file names no file in {repo}: {', '.join(missing)}")


def header_pairs(options, base, paths, findings_file):
    pairs = [("mode", "fix-first" if options.fix else "review-first"), ("caller", options.skill),
             ("lane", options.lane)]
    if base:
        pairs.append((BASE_KEY, base))
    if paths:
        pairs.append((FILES_KEY, LIST_SEPARATOR.join(paths)))
    if findings_file:
        pairs.append((FINDINGS_KEY, str(findings_file)))
    if options.no_review:
        pairs.append((NO_REVIEW_KEY, YES))
    if options.fast:
        pairs.append((REVIEWER_MODEL_KEY, FAST_REVIEWER_MODEL))
    if options.iter:
        pairs.append((ITER_KEY, str(options.iter)))
    return pairs


def handoff_text(options, paths):
    if options.handoff:
        try:
            return pathlib.Path(options.handoff).read_text()
        except OSError as error:
            raise LaunchError(f"--handoff {options.handoff}: {error}") from error
    if paths:
        return "Review only these files: " + LIST_SEPARATOR.join(paths) + "."
    if options.fix:
        return "Fix the findings, then review the fix."
    return DEFAULT_HANDOFF


def packet_args(options):
    args = ["--skill", options.skill]
    if options.base:
        args += ["--scope", "branch-exit"]
    return [*args, "--lane", options.lane]


def command_launch(argv, loop_script):
    """Runs the launch. The skill runs it as a background command, so its completion is the wake-up."""
    options = launch_arguments(argv)
    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    if not session_id:
        raise LaunchError("CLAUDE_CODE_SESSION_ID is not set, so the review loop cannot be tied to this session. "
                          "Nothing was launched. Tell the user.")

    found_root = script_utils.repo_root(options.repo or os.getcwd())
    if found_root is None:
        raise LaunchError(f"{options.repo or os.getcwd()} is not inside a git work tree")
    repo = found_root.resolve()

    findings = read_findings_file(options.fix) if options.fix else []
    base = resolved_base(repo, options.base) if options.base else ""
    paths = repo_paths(repo, options.files)
    check_files_exist(repo, paths, base)
    handoff = handoff_text(options, paths)
    in_scope = review_files(repo, base, paths)
    if not options.fix and not in_scope:
        since = f"since {options.base}" if base else "against HEAD"
        raise LaunchError(f"the working tree of {repo} has no changes {since}, so the review scope is empty and no "
                          "reviewer would read anything. Nothing was launched. To review committed work, launch "
                          "with --base <ref>.")

    state_dir = script_utils.git_path(repo, STATE_NAME)
    agent_id = f"{AGENT_PREFIX}{script_utils.sortable_unique_id()}"
    loop_dir = pathlib.Path(state_dir) / reviewer_dispatch.LOOP_FOLDER / agent_id
    loop_dir.mkdir(parents=True, exist_ok=True)
    findings_file = loop_dir / FINDINGS_JSON if findings else None
    if findings_file:
        write_findings(findings_file, findings)
    prompt = render_prompt(header_pairs(options, base, paths, findings_file), handoff)
    prompt_file, log_path = write_script_prompt(state_dir, agent_id, prompt)
    launch_record = json.dumps({"packet_args": packet_args(options)}) + "\n"
    script_utils.write_text_atomically(loop_dir / reviewer_dispatch.LAUNCH_FILE, launch_record)
    print(f"The review loop runs as a script; its log is {log_path}")
    sys.stdout.flush()

    handback_hook.record_script_dispatch(session_id, repo, no_review=options.no_review)
    command = loop_script_command(loop_script, repo, state_dir, session_id, agent_id, prompt_file,
                                  reviewers=REVIEWERS_MAIN)
    with log_path.open("w") as log:
        loop = subprocess.Popen(command, cwd=repo, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                start_new_session=True)
    script_utils.write_text_atomically(loop_dir / reviewer_dispatch.PID_FILE, f"{loop.pid}\n")

    dispatch_lines = reviewer_dispatch.wait_for_step(loop_dir, lambda: loop.poll() is None)
    if dispatch_lines is not None:
        print("\n".join(dispatch_lines))
        return 0
    packet_command = reviewer_dispatch.packet_command(loop_dir)
    print(f"The review loop script exited {loop.returncode}. Run `{packet_command}` now.")
    return 0
