"""review_launch.py: `review_fix.py launch`, the start of every /review and /fix run.

It starts review_loop_script.py --reviewers main as a detached process and returns when the loop asks for reviewers
(`ACTION: dispatch-reviewer`, see reviewer_dispatch.py) or when the loop exits. With --detach (the /review and /fix
fork) it returns once the loop has started and names the `code_wait.py review --loop` command that waits on it.
It records the session's dispatch row, writes the prompt file, the loop's pid, <loop dir>/handoff.txt and
<loop dir>/launch.json (the packet arguments the wait prints, which name the run's mode (`fix` or `review`), and the
flags a later fix run of the same review carries, and the branch, launch time and `--detach` flag that the
session-start notice reads), and keeps its state under
<git dir>/review-script. It SIGTERMs the process group of every live earlier loop of the same repo and run mode; a
live loop of the repo started in another mode (or whose record names no mode) stops the launch before any folder is
made. It deletes the --fix, --also-fix and --handoff files that sit in the code-phase run folder.

A findings file (`--fix`, `--also-fix`) holds one finding per item: a line that starts with `- ` at column 0, then
any indented continuation lines. Blank lines may sit between items. Any other line stops the launch.
"""
import argparse
import json
import os
import pathlib
import subprocess
import sys
import time
from typing import NamedTuple

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent / folder) for folder in (".", "../lib", "../code")]
import code_wait
import handback_hook
import handback_store
import hook_input
import merge_free_base
import phase_asks
import plan_format
import process_group
import resume_review_gate
import review_fix_state
import review_user_ruled
import reviewer_dispatch
import script_utils
import stop_file_names
from review_fix_names import RUN_FOLDER_FINDINGS_NAME
from review_loop_plan import review_files
from review_loop_post_cap import post_cap_kinds
from review_loop_prompt_file import (
    ADOPTED_HEADER_KEY,
    BASE_KEY,
    CI_GATE_KEY,
    CODER_MODEL_KEY,
    FILES_KEY,
    FINDINGS_KEY,
    FIX_ROUNDS_KEY,
    GIVEN_BASE_KEY,
    ITER_KEY,
    LIST_SEPARATOR,
    NO_REVIEW_KEY,
    PLAN_KEY,
    POST_CAP_PASSES_KEY,
    REPO_KEY,
    REVIEWER_MODEL_KEY,
    REVIEWERS_MAIN,
    RULED_OUT_FILES_KEY,
    SESSION_RULED_HEADER_KEY,
    USER_RULED_AT_KEY,
    USER_RULED_HEADER_KEY,
    YES,
    loop_script_command,
    render_prompt,
    write_findings,
    write_script_prompt,
)

STATE_NAME = reviewer_dispatch.LAUNCH_STATE_NAME
AGENT_PREFIX = "review-script-"
DEFAULT_HANDOFF = "Review the working tree against HEAD."
FAST_MODEL = "haiku"
FINDINGS_JSON = "findings.json"
HANDOFF_NAME = "handoff.txt"
# The launch record's flags for a later fix run of the same review: `packet --launch` stores them for asks-done.
RELAUNCH_KEY = "relaunch_args"
# In the launch record of a fix run: the list of texts of the findings the user accepted; no key means none. A value
# that is not a list of strings stops the read (read_user_ruled).
USER_RULED_RECORD_KEY = "user_ruled"
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
    parser.add_argument("--also-fix", metavar="FINDINGS_FILE",
                        help="with --fix: more findings for the fix coder, in the same format; they come after "
                             "the --fix findings, so --user-ruled and --session-ruled numbers stay valid")
    parser.add_argument("--no-review", action="store_true", help="with --fix: apply the findings and review nothing")
    parser.add_argument("--user-ruled", action="append", type=int, default=[], metavar="N",
                        help="with --fix (repeatable): the user accepted finding N of the findings file, counted "
                             "from 1; if the fix coder skips it, it comes back as an ask")
    parser.add_argument("--session-ruled", action="append", type=int, default=[], metavar="N",
                        help="with --fix (repeatable): a session ruled on finding N of the findings file, counted "
                             "from 1; if the fix coder re-asks it, it is skipped, not asked again")
    parser.add_argument("--base",
                        help="review every change since this ref (its merge base with HEAD when the ref is no "
                             "ancestor of HEAD), commits included, leaving out what later merge commits brought in")
    parser.add_argument("--file", action="append", default=[], dest="files",
                        help="review only this file (repeatable): absolute, or relative to the repo root. A file "
                             f"under {hook_input.SESSION_TEMP_ROOT_FORMS} is read as a brief for the reviewers")
    parser.add_argument("--plan", metavar="PATH",
                        help="the plan file of this work: absolute, or relative to the repo root. With no flag the "
                             "plan of the repo's code-phase record is used, when it names a file in the repo")
    parser.add_argument("--ruled-out", action="append", default=[], metavar="PATH",
                        help="a file the user ruled out of this review (repeatable): the loop never reviews it, "
                             "sends no finding on it to a coder and puts back any change a coder makes to it")
    parser.add_argument("--handoff", metavar="FILE", help="the handoff block the reviewers and coder read")
    parser.add_argument("--test", action="append", default=[], dest="tests", metavar="CMD",
                        help="a test command the loop runs on every converged run, before review credit (repeatable)")
    parser.add_argument("--ci-gate", default="", metavar="RUN",
                        help="the caller ruled that this CI run is the test gate: the loop runs no local full check "
                             "and the packet names the run")
    models = parser.add_mutually_exclusive_group()
    models.add_argument("--fast", action="store_true", help=f"run the reviewers and the fix coder on {FAST_MODEL}")
    models.add_argument("--deep", action="store_true", help="run the reviewers on their agents' own model")
    parser.add_argument("--iter", type=int, default=0, help="review rounds an earlier run of this review used")
    parser.add_argument("--fix-rounds", type=int, default=0,
                        help="fix rounds an earlier run of this review reported; the run counts on from there")
    parser.add_argument("--post-cap-passes", default="", metavar="KINDS",
                        help="the post-cap passes an earlier run of this review reported, joined with "
                             f"`{LIST_SEPARATOR}`")
    parser.add_argument("--lane", help="lane of the run (default none for review, code for fix)")
    parser.add_argument("--detach", action="store_true",
                        help="return once the loop has started and print the code_wait.py command that waits on it")
    return parser


def launch_arguments(argv):
    options = launch_parser().parse_args(argv)
    if options.no_review and not options.fix:
        raise LaunchError("--no-review needs --fix: a review-first run with no review does nothing")
    if options.also_fix and not options.fix:
        raise LaunchError("--also-fix needs --fix: it adds findings to a fix run")
    if options.user_ruled and not options.fix:
        raise LaunchError("--user-ruled needs --fix: only a fix run applies findings the user accepted")
    if options.session_ruled and not options.fix:
        raise LaunchError("--session-ruled needs --fix: only a fix run applies findings a session ruled on")
    if options.iter < 0:
        raise LaunchError(f"--iter {options.iter} is negative; expected the rounds an earlier run used")
    if options.fix_rounds < 0:
        raise LaunchError(f"--fix-rounds {options.fix_rounds} is negative; expected the fix rounds an earlier run "
                          "reported")
    try:
        post_cap_kinds(options.post_cap_passes, LIST_SEPARATOR)
    except ValueError as error:
        raise LaunchError(f"--post-cap-passes {options.post_cap_passes!r} {error}") from error
    if any(not command.strip() for command in options.tests):
        raise LaunchError("--test needs a command; got an empty one")
    options.tests = list(dict.fromkeys(options.tests))
    options.skill = "fix" if options.fix else "review"
    options.lane = options.lane or ("code" if options.fix else "none")
    return options


def read_findings_file(findings_file, flag="--fix"):
    """The finding texts of a findings file, one per `- ` item, continuation lines joined with a space. `flag` names
    the launch flag that gave the file, for a read error."""
    try:
        lines = pathlib.Path(findings_file).read_text().splitlines()
    except OSError as error:
        raise LaunchError(f"{flag} {findings_file}: {error}") from error

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
    """BaseResolution(given, commit, used): `given` is --base as typed, `used` the commit the review diffs against:
    the merge base with HEAD when the base is no ancestor of HEAD, with what later merge commits brought in folded
    into it."""
    commit = script_utils.git_output(repo, "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}")
    if not commit:
        raise LaunchError(f"--base {base} names no commit in {repo}")
    try:
        resolution = merge_free_base.resolve_base(repo, commit.strip(), base)
        folded = merge_free_base.merge_free_base(repo, resolution.used)
        return resolution._replace(used=folded)
    except merge_free_base.MergeConflictError as error:
        raise LaunchError(f"--base {base}: {str(error).rstrip('.')}. Resolve or revert merge {error.merge}, or "
                          "pass a --base that comes after it. Nothing was launched.") from error
    except (merge_free_base.NoMergeBaseError, merge_free_base.MergeBaseGitError) as error:
        raise LaunchError(f"--base {base}: {str(error).rstrip('.')}. Nothing was launched.") from error


def is_session_brief(full):
    """True when `full` is an existing file under one of the session temp roots."""
    if not os.path.isfile(full):
        return False
    return hook_input.is_under_session_temp_root(full)


class FileFlags(NamedTuple):
    repo_files: list
    briefs: list


def split_brief_files(repo, files):
    """The --file values as FileFlags: the ones in the repo as paths relative to the repo root, and the briefs
    (absolute paths of existing files under the session temp root). A relative value is read against the repo.
    Any other path outside the repo stops, and the message names the temp root forms."""
    repo_files, briefs = [], []
    for given in files:
        full = repo / given
        relative = script_utils.repo_relative(repo, given)
        if relative is not None:
            repo_files.append(relative)
        elif is_session_brief(full):
            briefs.append(full.resolve())
        else:
            raise LaunchError(f"--file {given} is outside the repo {repo}; outside it, --file reads only an existing "
                              f"brief file under {hook_input.SESSION_TEMP_ROOT_FORMS}")
    return FileFlags(repo_files, briefs)


def with_briefs(handoff, briefs):
    """The handoff followed by the text of each brief file, so the brief reaches every reviewer prompt."""
    parts = [handoff]
    for brief in briefs:
        try:
            parts.append(f"Caller's brief ({brief}):\n{brief.read_text()}")
        except (OSError, UnicodeDecodeError) as error:
            raise LaunchError(f"--file {brief}: {error}") from error
    return "\n\n".join(parts)


def ruled_out_files(repo, given):
    """Each --ruled-out as a path relative to the repo root. The flag takes one file per use, so a folder stops."""
    paths = []
    for given_file in given:
        relative = script_utils.repo_relative(repo, given_file)
        if relative is None:
            raise LaunchError(f"--ruled-out {given_file} is outside the repo {repo}")
        if (repo / relative).is_dir():
            raise LaunchError(f"--ruled-out {relative} is a folder; --ruled-out takes one file per flag")
        paths.append(relative)
    return paths


def launch_plan(repo, given):
    """The plan path relative to the repo root, or "" for no plan. `given` (the --plan value) must be a file inside
    the repo, else the launch stops. With no `given`, the plan of the code-phase record when that file exists in the
    repo."""
    if given:
        relative = repo_file_relative(repo, given)
        if relative is None:
            raise LaunchError(f"--plan {given} is not a file inside the repo {repo}")
        return relative
    recorded = code_wait.read_phase_run(repo).get(phase_asks.PLAN_KEY)
    if not recorded:
        return ""
    return repo_file_relative(repo, recorded) or ""


def repo_file_relative(repo, given):
    """`given` relative to the repo root when it names a file inside the repo, else None."""
    relative = script_utils.repo_relative(repo, given)
    if relative is None or not (repo / relative).is_file():
        return None
    return relative


def check_files_exist(repo, paths, base):
    changed = review_files(repo, base)
    missing = [path for path in paths if not (repo / path).exists() and path not in changed]
    if missing:
        raise LaunchError(f"--file names no file in {repo}: {', '.join(missing)}")


def header_pairs(options, base, paths, findings_file, ruled_out=(), adopted=None, given_base=None, plan="", repo=""):
    # A launch with no --fix still runs fix-first when adopted rulings come back as findings (`findings_file` is set).
    mode = "fix-first" if options.fix or findings_file else "review-first"
    pairs = [("mode", mode), ("caller", options.skill), ("lane", options.lane)]
    if plan:
        pairs.append((PLAN_KEY, plan))
        # reviewer_dispatch.plan_arguments passes --plan only when the header holds both plan and repo.
        pairs.append((REPO_KEY, str(repo)))
    if base:
        pairs.append((BASE_KEY, base))
    if given_base:
        pairs.append((GIVEN_BASE_KEY, given_base))
    if paths:
        pairs.append((FILES_KEY, LIST_SEPARATOR.join(paths)))
    if ruled_out:
        pairs.append((RULED_OUT_FILES_KEY, LIST_SEPARATOR.join(ruled_out)))
    if findings_file:
        pairs.append((FINDINGS_KEY, str(findings_file)))
    if findings_file and options.user_ruled:
        pairs.append((USER_RULED_HEADER_KEY, LIST_SEPARATOR.join(str(number) for number in options.user_ruled)))
        ruled_at = plan_format.ruled_at_now()
        pairs.append((USER_RULED_AT_KEY, ruled_at))
    if findings_file and adopted:
        rows = [{"number": number, **ruling._asdict()} for number, ruling in adopted.items()]
        pairs.append((ADOPTED_HEADER_KEY, json.dumps(rows)))
    if findings_file and options.session_ruled:
        pairs.append((SESSION_RULED_HEADER_KEY, LIST_SEPARATOR.join(str(number) for number in options.session_ruled)))
    if options.no_review:
        pairs.append((NO_REVIEW_KEY, YES))
    if options.fast:
        pairs.append((REVIEWER_MODEL_KEY, FAST_MODEL))
        pairs.append((CODER_MODEL_KEY, FAST_MODEL))
    if options.ci_gate:
        pairs.append((CI_GATE_KEY, options.ci_gate))
    if options.iter:
        pairs.append((ITER_KEY, str(options.iter)))
    if options.fix_rounds:
        pairs.append((FIX_ROUNDS_KEY, str(options.fix_rounds)))
    if options.post_cap_passes:
        pairs.append((POST_CAP_PASSES_KEY, options.post_cap_passes))
    return pairs


def cap_count_args(target):
    """The `--fix-rounds` and `--post-cap-passes` flags that carry a packet's cap counts to a later run of the
    review. A count the packet lacks (an older packet) or holds as zero or empty adds no flag."""
    args = []
    fix_rounds = target.get("fix_rounds")
    if fix_rounds:
        args += ["--fix-rounds", str(fix_rounds)]
    post_cap_passes = target.get("post_cap_passes")
    if post_cap_passes:
        args += ["--post-cap-passes", LIST_SEPARATOR.join(post_cap_passes)]
    return args


def handoff_text(options, paths, findings):
    """The handoff: the --handoff file, else the files named, else the fix brief when `findings` (the findings left
    after the leave-out) are to be fixed, else the default."""
    if options.handoff:
        try:
            return pathlib.Path(options.handoff).read_text()
        except OSError as error:
            raise LaunchError(f"--handoff {options.handoff}: {error}") from error
    if paths:
        return "Review only these files: " + LIST_SEPARATOR.join(paths) + "."
    if options.fix and findings:
        return "Fix the findings, then review the fix."
    return DEFAULT_HANDOFF


def packet_args(options, launch_file):
    args = [reviewer_dispatch.SKILL_FLAG, options.skill]
    if options.base:
        args += ["--scope", "branch-exit"]
    return [*args, "--lane", options.lane, "--launch", str(launch_file)]


def relaunch_args(options, repo, paths, handoff_file, ruled_out=(), plan=""):
    """The flags a later fix run of this review carries: the same repo, range, plan, files, ruled-out files,
    reviewer model, CI gate, lane, handoff and test commands. `--fix`, `--also-fix`, `--iter`, `--fix-rounds`,
    `--post-cap-passes`, `--user-ruled`, `--session-ruled` and `--detach` are the caller's to add."""
    args = ["--repo", str(repo)]
    if options.base:
        args += ["--base", options.base]
    if plan:
        args += ["--plan", plan]
    for path in paths:
        args += ["--file", path]
    for path in ruled_out:
        args += ["--ruled-out", path]
    if options.fast:
        args.append("--fast")
    if options.deep:
        args.append("--deep")
    if options.ci_gate:
        args += ["--ci-gate", options.ci_gate]
    for test_command in options.tests:
        args += ["--test", test_command]
    return [*args, "--lane", options.lane, "--handoff", str(handoff_file)]


def relaunch_args_with_files(args, paths):
    """The relaunch flags with a `--file` for each of paths not already listed. Flags that scope no files stay
    as they are: adding a file would narrow a whole-tree run."""
    if "--file" not in args:
        return list(args)
    listed = {args[index + 1] for index, word in enumerate(args[:-1]) if word == "--file"}
    extra = []
    for path in paths:
        if path in listed:
            continue
        listed.add(path)
        extra += ["--file", path]
    return [*args, *extra]


def relaunch_handoff(args):
    """The handoff file the relaunch flags name: `relaunch_args` always ends with `--handoff <file>`."""
    return pathlib.Path(args[args.index("--handoff") + 1])


def relaunch_repo(args):
    """The repo the relaunch flags name after `--repo`, or None when they carry no `--repo` or it has no value."""
    _rest, repo = script_utils.pop_option(args, "--repo")
    return repo or None


def relaunch_args_with_handoff(args, handoff_file):
    """The relaunch flags with their `--handoff` pointed at handoff_file."""
    handoff_index = args.index("--handoff")
    return [*args[:handoff_index + 1], str(handoff_file), *args[handoff_index + 2:]]


def read_relaunch_args(launch_file):
    """The relaunch flags a launch record holds."""
    try:
        return reviewer_dispatch.read_string_list(launch_file, RELAUNCH_KEY)
    except reviewer_dispatch.ManifestError as error:
        raise LaunchError(f"--launch {error}") from error


def ruled_texts(flag, numbers, findings):
    """The texts of the findings the `flag` (`--user-ruled` or `--session-ruled`) numbers name. A number past the
    findings stops the launch."""
    try:
        return script_utils.numbered_items(numbers, findings)
    except script_utils.ItemNumberError as error:
        raise LaunchError(f"{flag} {error.number} names no finding: the findings file holds "
                          f"{error.item_count}") from error


def read_user_ruled(launch_file):
    """What a launch record says the user accepted: the list of finding texts, empty for none (also a record with no
    key)."""
    try:
        return reviewer_dispatch.read_string_list(launch_file, USER_RULED_RECORD_KEY, default=[])
    except reviewer_dispatch.ManifestError as error:
        raise LaunchError(f"--launch {error}") from error


def remove_stale_run_folder_findings(repo):
    """Deletes the run folder's fix-findings.md, the file a session writes for `--also-fix`, and returns True when one
    was there. A launch reads only a file written after this call, never one an earlier run left."""
    folder = code_wait.phase_dir_or_none(repo)
    if folder is None:
        return False
    stale = folder / RUN_FOLDER_FINDINGS_NAME
    if not stale.is_file():
        return False
    stale.unlink()
    return True


def consume_run_folder_inputs(repo, options):
    """Deletes the --fix, --also-fix and --handoff files that sit in the code-phase run folder. A file elsewhere, such
    as the asks findings file, and the run folder's review-stop.md stay. A failed Write of the next launch's input then
    cannot leave this launch's file in place for the next one to read."""
    folder = code_wait.phase_dir_or_none(repo)
    if folder is None:
        return
    inputs = [pathlib.Path(given).resolve() for given in (options.fix, options.also_fix, options.handoff)
              if given]
    consumed = [input_file for input_file in inputs if input_file.parent == folder.resolve()]
    if not consumed:
        return
    for stale in consumed:
        try:
            stale.unlink(missing_ok=True)
        except OSError as error:
            print(f"review_launch: could not delete {stale}: {error}", file=sys.stderr)


def record_resume_loop(repo, loop_dir):
    """Writes the run folder's loop-dir file with `loop_dir` when the folder holds a resume record, so the resume
    gate sees that a review loop ran on the resumed run."""
    folder = code_wait.phase_dir_or_none(repo)
    if folder is None:
        return
    if not (folder / resume_review_gate.RESUME_FILE).is_file():
        return
    script_utils.write_text_atomically(folder / stop_file_names.LOOP_DIR_FILE, f"{loop_dir}\n")


def loop_repo(launch_file):
    """The repo a loop's launch record names: the --repo that `relaunch_args` always puts in its relaunch flags."""
    args = read_relaunch_args(launch_file)
    repo = relaunch_repo(args)
    if repo is None:
        raise LaunchError(f"--launch {launch_file}: {RELAUNCH_KEY} names no --repo")
    return pathlib.Path(repo).resolve()


def is_live_loop_of(loop_dir, pid, repo):
    """True when the launch record in loop_dir names repo and the command line of pid names the loop's agent id (a
    reused pid does not). Raises LaunchError or OSError when the record or `ps` cannot be read."""
    if loop_repo(loop_dir / reviewer_dispatch.LAUNCH_FILE) != repo:
        return False
    return loop_dir.name in process_group.command_line(pid)


def stop_loop(loop_dir, pid, repo):
    """SIGTERMs the process group of the live loop (loop_dir, pid) of repo and waits for every process of the group to
    exit, so the old loop has removed its worktrees and children before the new loop starts. A group still running
    after the wait, or a failed kill, is printed on stderr and the launch goes on."""
    try:
        result = process_group.stop_group(pid)
    except OSError as error:
        print(f"review_launch: could not stop the loop in {loop_dir}: {error}", file=sys.stderr)
        return
    if result == process_group.GROUP_GONE:
        return
    print(f"Stopped the earlier review loop {loop_dir.name} of {repo} (pid {pid}).")
    if result == process_group.GROUP_STILL_RUNNING:
        print(f"review_launch: the earlier loop (pid {pid}) is still running after "
              f"{process_group.STOP_WAIT_SECONDS} s", file=sys.stderr)


def loop_skill(launch_file):
    """The run mode (`fix` or `review`) a launch record names after `--skill` in its packet arguments, or None for a
    record with none."""
    try:
        saved_args = reviewer_dispatch.read_string_list(
            launch_file, reviewer_dispatch.PACKET_ARGS_KEY, default=[])
    except reviewer_dispatch.ManifestError as error:
        raise LaunchError(str(error)) from error
    _rest, skill = script_utils.pop_option(saved_args, reviewer_dispatch.SKILL_FLAG)
    return skill or None


class LiveLoop(NamedTuple):
    loop_dir: pathlib.Path
    pid: int
    started_by: str | None


def live_loop_of(loop_dir, pid, repo):
    """The LiveLoop for (loop_dir, pid) when it is a live loop of repo, else None. A loop whose record or `ps` cannot
    be read is named on stderr and returns None, so it is never stopped."""
    launch_file = loop_dir / reviewer_dispatch.LAUNCH_FILE
    if not launch_file.is_file():
        return None
    try:
        if not is_live_loop_of(loop_dir, pid, repo):
            return None
        started_by = loop_skill(launch_file)
    except (LaunchError, OSError) as error:
        print(f"review_launch: could not stop the loop in {loop_dir}: {error}", file=sys.stderr)
        return None
    return LiveLoop(loop_dir, pid, started_by)


def refuse_loop_of_another_skill(loop, repo, skill):
    """Raises a LaunchError that names the live loop of repo when another run mode started it."""
    if loop.started_by == skill:
        return
    started_as = f"a {loop.started_by} run" if loop.started_by else "a run whose record names no mode"
    raise LaunchError(
        f"the review loop {loop.loop_dir.name} of {repo} (pid {loop.pid}) was started as {started_as}, not a "
        f"{skill} run, and still runs. Nothing was launched and the loop was not stopped. End the run with a stop "
        f"that names this loop; launch again after pid {loop.pid} exits.")


def stop_earlier_loops(state_dir, repo, skill):
    """Stops every live loop of repo that an earlier launch of the same run mode started, so two loops never edit one
    tree. Each loop is looked at once: a live loop of repo started in another run mode stops the launch before any
    loop is stopped, and a loop that cannot be read is reported and left running."""
    loop_root = pathlib.Path(state_dir) / reviewer_dispatch.LOOP_FOLDER
    answers = [live_loop_of(loop_dir, pid, repo) for loop_dir, pid in reviewer_dispatch.live_loops(loop_root)]
    loops = [loop for loop in answers if loop is not None]
    for loop in loops:
        refuse_loop_of_another_skill(loop, repo, skill)
    for loop in loops:
        stop_loop(loop.loop_dir, loop.pid, repo)


class FixRunFindings(NamedTuple):
    findings: list
    user_ruled_numbers: list
    user_ruled_texts: list
    left_out: list
    session_ruled_numbers: list
    adopted: dict  # number of each adopted finding -> its AdoptedRuling


def fix_run_findings(options, repo):
    """The fix run's findings with the plan impacts a recorded ruling settled left out, the numbers of the findings
    the user ruled on after the renumbering, their texts, the findings left out, and the session-ruled numbers after
    the renumbering. Prints each finding left out. A launch with no --fix reads no findings file, and an adopted
    ruling the repo holds still comes back as a finding, so the loop gets it on every resume."""
    findings = []
    if options.fix:
        findings = read_findings_file(options.fix)
    if options.also_fix:
        findings += read_findings_file(options.also_fix, "--also-fix")
    # Called only to check the numbers: a --user-ruled or --session-ruled number that names no finding stops the launch.
    ruled_texts("--user-ruled", options.user_ruled, findings)
    ruled_texts("--session-ruled", options.session_ruled, findings)
    rows_repo = handback_store.ruled_rows_repo(repo)
    rulings = review_user_ruled.session_rulings(rows_repo)
    left = review_user_ruled.leave_out_ruled_impacts(
        findings, options.user_ruled, rulings, options.session_ruled)
    for text in left.dropped:
        print(f"Left out of the fix run (a ruling already settled this plan impact): {text}")
    user_texts = ruled_texts("--user-ruled", left.user_ruled_numbers, left.kept)
    return FixRunFindings(left.kept, left.user_ruled_numbers, user_texts, left.dropped, left.session_ruled_numbers,
                          left.adopted)


def command_launch(argv, loop_script):
    """Runs the launch. The skill runs it as a background command, so its completion is the wake-up."""
    options = launch_arguments(argv)
    # The --fix launch of the printed line clears before the session, repo and file checks, so a launch that fails
    # below still lets the fork report the failure.
    if options.fix:
        review_fix_state.clear_asks_launch_pending(options.fix)
    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    if not session_id:
        raise LaunchError("CLAUDE_CODE_SESSION_ID is not set, so the review loop cannot be tied to this session. "
                          "Nothing was launched. Tell the user.")

    found_root = script_utils.repo_root(options.repo or os.getcwd())
    if found_root is None:
        raise LaunchError(f"{options.repo or os.getcwd()} is not inside a git work tree")
    repo = found_root.resolve()

    found = fix_run_findings(options, repo)
    findings, user_ruled, left_out = found.findings, found.user_ruled_texts, found.left_out
    options.user_ruled = found.user_ruled_numbers
    options.session_ruled = found.session_ruled_numbers
    base_resolution = resolved_base(repo, options.base) if options.base else None
    base = base_resolution.used if base_resolution else ""
    file_flags = split_brief_files(repo, options.files)
    paths = file_flags.repo_files
    ruled_out = ruled_out_files(repo, options.ruled_out)
    plan = launch_plan(repo, options.plan)
    check_files_exist(repo, paths, base)
    handoff = with_briefs(handoff_text(options, paths, findings), file_flags.briefs)
    changed = review_files(repo, base, paths)
    # The loop leaves the plan folder out of a whole-tree scope (LoopRun.review_scope); the guard must agree.
    scoped = changed if paths else plan_format.outside_plan_folder(changed, plan)
    in_scope = script_utils.without_paths(scoped, ruled_out)
    if options.fix and left_out and not findings and (options.no_review or not in_scope):
        raise LaunchError(f"every finding in {options.fix} was left out: a recorded ruling already settled each plan "
                          "impact, and there is nothing else to fix or review. Nothing was launched.")
    if not findings and not in_scope:
        since = f"since {options.base}" if base else "against HEAD"
        if changed and not scoped:
            raise LaunchError(f"every changed file {since} is under the plan folder {plan_format.plan_folder(plan)}, "
                              "which holds plan documents, not the change, so the review scope is empty and no "
                              "reviewer would read anything. Nothing was launched. Name a file with --file to "
                              "review it.")
        if changed:
            outside_plan = f" outside the plan folder {plan_format.plan_folder(plan)}" if scoped != changed else ""
            raise LaunchError(f"every changed file {since}{outside_plan} was given to --ruled-out, so the review scope "
                              "is empty and no reviewer would read anything. Nothing was launched.")
        if base:
            raise LaunchError(f"the branch in {repo} has no changes of its own {since}, so the review scope is "
                              "empty and no reviewer would read anything. Nothing was launched.")
        raise LaunchError(f"the working tree of {repo} has no changes {since}, so the review scope is empty and no "
                          "reviewer would read anything. Nothing was launched. To review committed work, launch "
                          "with --base <ref>.")

    state_dir = script_utils.git_path(repo, STATE_NAME)
    stop_earlier_loops(state_dir, repo, options.skill)
    agent_id = f"{AGENT_PREFIX}{script_utils.sortable_unique_id()}"
    loop_dir = pathlib.Path(state_dir) / reviewer_dispatch.LOOP_FOLDER / agent_id
    loop_dir.mkdir(parents=True, exist_ok=True)
    findings_file = loop_dir / FINDINGS_JSON if findings else None
    if findings_file:
        write_findings(findings_file, findings)
    given_base = base_resolution.given_if_moved() if base_resolution else None
    pairs = header_pairs(options, base, paths, findings_file, ruled_out, found.adopted, given_base, plan, repo)
    prompt = render_prompt(pairs, handoff)
    prompt_file, log_path = write_script_prompt(state_dir, agent_id, prompt)
    handoff_file = loop_dir / HANDOFF_NAME
    script_utils.write_text_atomically(handoff_file, handoff)
    launch_file = loop_dir / reviewer_dispatch.LAUNCH_FILE
    launch_record = {reviewer_dispatch.PACKET_ARGS_KEY: packet_args(options, launch_file),
                     RELAUNCH_KEY: relaunch_args(options, repo, paths, handoff_file, ruled_out, plan),
                     USER_RULED_RECORD_KEY: user_ruled,
                     reviewer_dispatch.LAUNCH_BRANCH_KEY: script_utils.current_branch(repo),
                     reviewer_dispatch.LAUNCH_TIME_KEY: time.time(),
                     reviewer_dispatch.LAUNCH_DETACH_KEY: options.detach}
    script_utils.write_text_atomically(launch_file, json.dumps(launch_record) + "\n")
    consume_run_folder_inputs(repo, options)
    record_resume_loop(repo, loop_dir)
    print(f"The review loop runs as a script; its log is {log_path}")
    sys.stdout.flush()

    handback_hook.record_script_dispatch(session_id, repo, no_review=options.no_review)
    command = loop_script_command(loop_script, repo, state_dir, session_id, agent_id, prompt_file,
                                  gate_commands=options.tests, reviewers=REVIEWERS_MAIN,
                                  gates_every_run=bool(options.tests))
    with log_path.open("w") as log:
        loop = subprocess.Popen(command, cwd=repo, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                start_new_session=True)
    script_utils.write_text_atomically(loop_dir / reviewer_dispatch.PID_FILE, f"{loop.pid}\n")
    if options.detach:
        wait_command = code_wait.launched_review_command(loop_dir)
        print(f"The review loop started. Run `{wait_command}` now, again while it prints `Still working`.")
        return 0

    dispatch_lines = reviewer_dispatch.wait_for_step(loop_dir, lambda: loop.poll() is None)
    if dispatch_lines is not None:
        print("\n".join(dispatch_lines))
        return 0
    try:
        packet_command = reviewer_dispatch.packet_command(loop_dir)
    except reviewer_dispatch.ManifestError as error:
        raise LaunchError(str(error)) from error
    print(f"The review loop script exited {loop.returncode}. Run `{packet_command}` now.")
    return 0
