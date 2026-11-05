#!/usr/bin/env python3
"""Run the live review loop script for /code.

    python3 ~/.claude/scripts/code/code_review_start.py <lane> <plan> <phase> <handoff file>
        --base <phase start sha> [--dry-run | --detach]

The prompt header is: lane, repo, plan, phase and later-phase files, then the handoff block and the repo's gate env.
A <plan> of `-` means the run has no plan file: the header leaves out the plan, phase and later-phase lines, and the
gate commands come from the handoff block's files.
The loop's state folder is <git dir>/code-step. The pid goes in <git dir>/code-phase/pid, where `code_wait.py review`
looks, so the session can end its turn while the loop runs. The loop runs with `--reviewers main`: the fork dispatches
each round's reviewers as its own subagents, and <git dir>/code-phase/loop-dir names the folder that holds the
requests. Prints the hand-back packet when the loop ends, then the defer ACTION when the packet holds a plan impact
that waits for a ruling.
"""

import os
import pathlib
import re
import subprocess
import sys

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path[:0] = [str(SCRIPTS_DIR / folder) for folder in ("lib", "review", "code")]

import coder_gate
import expected_red
import gate_commands
import handback
import handback_hook
import handoff_files
import plan_format
import review_fix
import script_utils
from code_wait import LOOP_DIR_FILE, PID_FILE, REVIEW_OUTPUT, phase_dir
from review_loop_prompt_file import REVIEWERS_MAIN, loop_script_command, write_script_prompt

LOOP_SCRIPT = SCRIPTS_DIR / "review/review_loop_script.py"
WAIT_COMMAND = "python3 ~/.claude/scripts/code/code_wait.py review"
DEFER_COMMAND = "python3 ~/.claude/scripts/review/review_fix.py defer"
AGENT_PREFIX = "loop-script-"
NO_PLAN = gate_commands.NO_PLAN


HANDOFF_FILE_PATH = re.compile(r"^\s*-\s*path:\s*(\S+)", re.M)


HANDOFF_FILES_LINE = "  files:"
HANDOFF_WHY_LINE = re.compile(r"^\s{6}why:")


def coder_why_blocks(entry_lines):
    # {path: the entry's `why:` lines} of the coder's files entries. Only the why lines are kept.
    why_by_path = {}
    path = None
    in_why = False
    for line in entry_lines:
        entry = HANDOFF_FILE_PATH.match(line)
        if entry:
            path = entry.group(1)
            in_why = False
            continue
        if path and HANDOFF_WHY_LINE.match(line):
            in_why = True
        if path and in_why:
            why_by_path.setdefault(path, []).append(line)
    return why_by_path


def handoff_with_git_files(repo, base, handoff):
    # The handoff's `files:` list is the files git shows changed since base (tracked changes plus untracked files).
    # The coder's own list is dropped; only its `why:` lines are kept, under the matching path.
    lines = handoff.splitlines()
    starts = [at for at, line in enumerate(lines) if line.rstrip() == HANDOFF_FILES_LINE]
    if not starts:
        return handoff

    start = starts[0]
    end = len(lines)
    for at in range(start + 1, len(lines)):
        if lines[at].strip() and not lines[at].startswith("    "):
            end = at
            break

    base_commit = script_utils.git_output(repo, "rev-parse", "--verify", f"{base}^{{commit}}")
    if base_commit is None:
        sys.exit(f"code_review_start: --base {base} is not a commit in {repo}; the handoff's files come from git")

    why_by_path = coder_why_blocks(lines[start + 1:end])
    changed = coder_gate.changed_files(repo, base_commit)
    if not changed:
        return "\n".join([*lines[:start], f"{HANDOFF_FILES_LINE} []", *lines[end:]]) + "\n"

    files_lines = [HANDOFF_FILES_LINE, *handoff_files.file_entry_lines(changed, {}, "changed since the phase base",
                                                                        why_by_path)]
    return "\n".join([*lines[:start], *files_lines, *lines[end:]]) + "\n"


def phase_changed_files(repo, base):
    """The files git shows changed since the phase base; [] when the base is no commit."""
    base_commit = script_utils.git_output(repo, "rev-parse", "--verify", f"{base}^{{commit}}")
    if base_commit is None:
        return []
    return script_utils.changed_files(repo, base_commit)


def review_prompt(repo, lane, plan, phase, handoff, phase_changed=()):
    """A later phase's file that this phase's diff already changed stays the phase's own, so a fix pass may edit the
    lines the phase wrote there."""
    header = ["mode: review-first", "caller: code", f"lane: {lane}", f"repo: {repo}"]

    if plan != NO_PLAN:
        header += [f"plan: {plan}", f"phase: {phase}"]
        plan_lines = (repo / plan).read_text().splitlines()
        later_paths = expected_red.later_phase_paths(plan_lines, phase)
        later_files = [path for path in later_paths if path not in set(phase_changed)]
        if later_files:
            header.append(f"later-phase files: {', '.join(later_files)}")

    prompt = "\n".join(header) + "\n\n" + handoff.strip()
    gate_env_text = plan_format.gate_env_text(plan_format.repo_gate_env(repo, None if plan == NO_PLAN else plan))
    return f"{prompt}\n\n{gate_env_text}\n" if gate_env_text else prompt + "\n"


def phase_gate_commands(repo, plan, phase, base, handoff=""):
    # The plan phase names the files and Automated Verification commands; a plan with no entry for the phase gives
    # the whole plan. The stale-prose pass runs only for a phase the plan has an entry for. With no plan, the files
    # come from the handoff block.
    if plan == NO_PLAN:
        handoff_files = HANDOFF_FILE_PATH.findall(handoff)
        return gate_commands.derive_gate_commands(repo, "\n".join(f"`{path}`" for path in handoff_files))

    commands, has_section = gate_commands.plan_gate_commands(repo, plan, phase)
    if not has_section:
        return commands

    stale_prose_script = pathlib.Path(__file__).resolve().parent / coder_gate.STALE_PROSE_SCRIPT
    return [*commands, f"python3 {stale_prose_script} --base {base}"]


def detach(repo, argv):
    # The fork's Bash call times out at 600 s and a review can run longer, so the loop runs on in its own session and
    # `code_wait.py review` waits for it. The pid file is written here too, before the waiter can look.
    folder = phase_dir(repo)
    folder.mkdir(exist_ok=True)
    pid_file = folder / PID_FILE
    review_output = folder / REVIEW_OUTPUT
    # A folder left by an earlier phase's loop would show its unanswered requests as this loop's.
    (folder / LOOP_DIR_FILE).unlink(missing_ok=True)
    command = [sys.executable, __file__, *[arg for arg in argv[1:] if arg != "--detach"]]
    with review_output.open("w") as output:
        loop = subprocess.Popen(command, cwd=repo, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
                                start_new_session=True)
    pid_file.write_text(str(loop.pid))
    print(f"The review loop is running. Run {WAIT_COMMAND} with the Bash timeout set to 600000.")
    return 0


def base_option(argv):
    # The phase start commit, which the stale-prose pass diffs against; the loop cannot find it from the repo alone.
    if "--base" not in argv or argv.index("--base") + 1 >= len(argv):
        sys.exit(__doc__)
    return argv[argv.index("--base") + 1]


def main(argv):
    if len(argv) < 5:
        sys.exit(__doc__)
    lane, plan, phase, handoff_file = argv[1:5]
    base = base_option(argv)
    repo = pathlib.Path.cwd().resolve()
    coder_handoff = pathlib.Path(handoff_file).read_text()
    handoff = handoff_with_git_files(repo, base, coder_handoff)
    phase_changed = phase_changed_files(repo, base)
    prompt = review_prompt(repo, lane, plan, phase, handoff, phase_changed)
    if "--dry-run" in argv:
        print(prompt)
        return 0

    if "--detach" in argv:
        return detach(repo, argv)

    session_id = os.environ["CLAUDE_CODE_SESSION_ID"]
    run_id = script_utils.sortable_unique_id()
    agent_id = f"{AGENT_PREFIX}{run_id}"
    state_dir = script_utils.git_path(repo, "code-step")
    if state_dir is None:
        sys.exit(f"code_review_start: {repo} is not inside a git checkout")
    folder = phase_dir(repo)
    folder.mkdir(exist_ok=True)
    (folder / PID_FILE).write_text(str(os.getpid()))

    handback_hook.record_script_dispatch(session_id, repo)
    prompt_file, log_path = write_script_prompt(state_dir, agent_id, prompt)
    commands = phase_gate_commands(repo, plan, phase, base, handoff)
    # The fork runs the reviewers as its own subagents; `code_wait.py review` finds their requests in this folder.
    command = loop_script_command(LOOP_SCRIPT, repo, state_dir, session_id, agent_id, prompt_file, commands,
                                  reviewers=REVIEWERS_MAIN)
    script_utils.write_text_atomically(folder / LOOP_DIR_FILE, f"{prompt_file.parent}\n")
    with log_path.open("w") as log:
        finished = subprocess.run(command, cwd=repo, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)

    print(f"The review loop script exited {finished.returncode}.")
    packet_file = prompt_file.parent / "packet.txt"
    if not packet_file.exists():
        print(f"No packet. Log: {log_path}")
        return 0

    packet_text = packet_file.read_text()
    print(packet_text)
    print("\n".join(held_impact_lines(packet_text, handoff_file)))
    return 0


def held_impact_lines(packet_text, handoff_file):
    """The ACTION lines for the packet's held plan impacts: the commit gate counts the review as dirty until the
    session defers them, whatever the packet's status says. [] when none is held."""
    try:
        packet = handback.load(packet_text)
    except handback.PacketError as error:
        return [f"code_review_start: the packet does not parse, so its held plan impacts are unknown: {error}"]

    held = handback.held_plan_impacts(packet)
    if not held:
        return []
    return [f"ACTION: defer-plan-impacts. {len(held)} plan impact(s) wait for a ruling, so the commit gate counts this "
            f"review as dirty. Before any commit, set `plan_impact` in {handoff_file} to the one line "
            f"`{review_fix.DEFER_LINE.removeprefix('plan_impact: ')}` and run "
            f"`{DEFER_COMMAND} {handoff_file}`."]


if __name__ == "__main__":
    sys.exit(main(sys.argv))
