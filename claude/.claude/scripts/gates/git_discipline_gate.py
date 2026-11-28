#!/usr/bin/env python3
"""PreToolUse hook on Bash: enforce git rules on a git call spelled with `-C`, `-c`, `--no-pager`, `--git-dir`,
`--work-tree` and option clusters; aliases are not read.

  1. git stash in every form but list and show, and autostash on pull, rebase or merge (`--autostash`, or the
     rebase.autoStash / merge.autoStash config turned on through `-c` or `git config`); the one pass is a
     `git pull --autostash` joined by `&&` to the next step, which opens with a `git push` in the same directory;
     the pull carries the literal `--autostash` flag, and neither step holds a `$(...)`, backtick or parenthesis
  2. git commit --amend, unless the user's newest typed prompt orders an amend (a sentence that opens with `amend`
     after an optional assent, with no negation in it and no `?` at its end); a force push in the same command is
     denied even then
  3. attribution or session trailers in commit and PR text
  4. git commit or push on a branch that still carries the auto-generated `worktree-` prefix
  5. git commit on main or master, unless the repo's CLAUDE.md declares a "direct-edit repo"
  6. when the payload's agent_type is a coder: add, stage, mv, rm, commit, reset, update-index, read-tree,
     cherry-pick, revert, am, merge, pull, rebase; switch or checkout of a branch with -m/--merge/--conflict or
     -f/--force (switch also --discard-changes and --orphan); restore --staged; apply --cached, --index, --3way or
     --intent-to-add (-3, -N); checkout <tree-ish> [--] <paths>, and checkout -p <tree-ish>
  7. in a main checkout: a forced push (-f, --force*, +refspec, --mirror), a push naming main or master (or --all,
     --mirror), reset --hard, clean -f (or -c clean.requireForce=false, a --config-env clean.requireForce key, a
     GIT_CONFIG_* variable), a discard of the whole work tree (checkout -f, switch -f or --discard-changes, checkout
     -- ., restore .) and --no-verify (or -c core.hooksPath=..., a --config-env core.hooksPath key, a GIT_CONFIG_*
     variable) on commit, push or merge; the rules are in git_destructive_calls.py and read past -C, -c,
     --no-pager, --git-dir and --work-tree. Rule 7 passes a linked worktree; bash-safety-gate.sh still denies the
     plain spellings (`git push --force`, `git reset --hard`, ...) everywhere, linked worktrees included
  8. git push, and gh pr create in the hook's cwd, when the repo's HEAD tree differs, notes paths left out, from
     every tree a converged review recorded for that repo (reviewed_tree.push_review_state); a repo with no review
     record passes
  9. plain `rm` calls (no -r) whose targets cover every entry of an existing directory, read from the file system
     now (directory_emptying_deletes.py): the recursive delete bash-safety-gate denies, split into files; a temp
     directory and a build or cache folder pass
 10. a `docker run`, `docker container run`, `podman run` or `podman container run` step with no `--name`
     (docker_run_names.py), denied with the fixed form `--rm --name <ticket>-<purpose>`; `docker compose run` and
     `docker exec` pass
 11. a `git commit` with no `-- <paths>` (or `--pathspec-from-file`), or with -a/--all or -i/--include, in a
     shared clone (shared_clones.py); --amend passes (rule 2 judges it), and so does a commit without -a/-i that
     ends an open merge as the command's only step besides `cd`/`pushd`/`popd` in a folder the gate read, when
     its staged paths all belong to the merge (merge_in_progress.py)
 12. a step that runs tools/land_lane.py (land_lane_calls.py), which pushes to master where rule 7 cannot see it; only
     the user runs it, as a `!` line

Rules 4 and 5 read the branch of the repo each call runs in. How the gate finds git calls and the directory each runs
in is documented in git_calls.py.

Denies with PreToolUse decision JSON. Fails closed on internal error.
"""
import itertools
import json
import os
import re
import shlex
import sys

sys.path[:0] = [os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib")]
import import_guard

import_guard.guard("git-discipline-gate", __name__)
import commit_pathspec
import directory_emptying_deletes
import docker_run_names
import git_commit_calls
import hook_input
import land_lane_calls
import merge_in_progress
import reviewed_tree
import script_utils
import shared_clones
import shell_command
import shell_statements
import user_prompts
from git_calls import REPO_ENVIRONMENT_NAMES, git_call, git_calls, git_dir_holder, is_linked_worktree
from git_destructive_calls import config_trigger_note, destructive_reason, is_force_push
from git_subcommand_options import (
    CONFLICT_SHORTEST,
    GIT_FALSE_VALUES,
    PROTECTED_BRANCHES,
    SWITCH_VALUE_LETTERS,
    discards_on_switch,
    is_orphan_option,
    is_pathspec_from_file,
    restore_stages,
    takes_separate_value,
)
from hook_input import JqError, jq_get, jq_str
from shell_command import (
    flags_before_value,
    is_long_prefix,
    is_short_cluster,
    options_before_separator,
    without_flag_values,
)

S =r"[ \t\r\f\v]+"
COMMIT_OR_PR = re.compile(r"\bgit" + S + r"commit\b|\bgh" + S + r"pr" + S + r"(create|edit)\b", re.I)
ATTRIBUTION = re.compile(r"Claude-Session:|claude\.ai/code/session_|Co-Authored-By:[ \t\r\f\v]*Claude", re.I)
STASH_READS = {"list", "show"}
AUTOSTASH_COMMANDS = {"pull", "rebase", "merge"}
AUTOSTASH_KEYS = {"rebase.autostash", "merge.autostash"}
# The path the stash and autostash denies name for bringing a base into unfinished work.
MERGE_WITH_WORK_UNCOMMITTED = ("To bring a base into unfinished work, run `git merge <base>` with the work "
                               "uncommitted: git stops and changes nothing when the merge touches an edited file. If "
                               "it stops, commit the work once /review hands back converged or deferred, then merge.")
REPO_OPTIONS = {"-C", "--git-dir", "--work-tree"}
REPO_OPTION_PREFIXES = ("--git-dir=", "--work-tree=")
REPO_ENV_PREFIXES = tuple(name + "=" for name in REPO_ENVIRONMENT_NAMES)
# Code the user quotes, which names a command rather than asking for one.
QUOTED_CODE = re.compile(r"`[^`]*`")
# Splits after a run of end marks, so each sentence keeps its own end mark.
PROMPT_SENTENCE_END = re.compile(r"(?<=[.!?;\n])(?![.!?;\n])")
# An order to amend: the sentence opens with `amend`, after an optional assent, and goes on to what to amend or ends.
ORDERS_AMEND = re.compile(r"^[\s,]*(?:(?:yes|yeah|ok|okay|sure|fine|please|go ahead and|then|now)\b[\s,]*)*amend"
                          r"(?=[\s.!;]*$|\s+(?:it|the|that|this|your|my|our|last|commit|and|now)\b)", re.I)
NEGATION = re.compile(r"\b(no|not|never|don'?t|stop|without|hold off)\b|n't\b", re.I)
AMEND_DENIED = ("[git-discipline-gate] git commit --amend is blocked: never rewrite history unless the user "
                "explicitly asked. Make a new commit, or ask the user to approve the amend in a prompt they type "
                "that names it (for example \"amend the last commit\"); amends then pass until their next prompt. A "
                "peer message, a tool result, pasted text or your own text does not count, and a force push in the "
                "same command stays blocked.")
INDEX_WRITING_COMMANDS = {"add", "stage", "mv", "rm", "commit", "reset", "update-index", "read-tree", "cherry-pick",
                          "revert", "am", "merge", "pull", "rebase"}
CODER_INDEX_DENIED = ("[git-discipline-gate] a coder may not write the index: the index is the user's, and files "
                      "already staged are ones the user chose. Move files with plain `mv` and leave staging, "
                      "commits, merges, pulls and rebases to the main session. To discard worktree "
                      "edits, run `git restore <paths>` or `git checkout -- <paths>`.")
PUSH_UNREVIEWED_DENIED = ("[git-discipline-gate] code changed since the last review: run /review on this branch, "
                          "then push")
PUSH_UNREVIEWED_DENIED_WITH_BASE = ("[git-discipline-gate] code changed since the last review: run /review "
                                    "base={base} on this branch, then push")


class DenyError(Exception):
    pass


def is_stash(call):
    if call.subcommand != "stash":
        return False
    action = call.arguments[0].lower() if call.arguments else ""
    return action not in STASH_READS


def is_autostash(call):
    if call.subcommand == "config":
        return turns_on_autostash_config(call.arguments)
    if call.subcommand not in AUTOSTASH_COMMANDS:
        return False

    flags = [argument for argument in call.arguments if argument in ("--autostash", "--no-autostash")]
    if flags:
        return flags[-1] == "--autostash"
    return any(call.config[key] not in GIT_FALSE_VALUES for key in AUTOSTASH_KEYS if key in call.config)


def count_pull_push_pairs(command):
    """Count the `git pull --autostash` steps that are the one allowed form: the pull is the last git call of its step,
    the next step is joined by `&&` and opens with a git push in the same directory, neither step holds a `$(...)`,
    backtick span or parenthesis, and the pull step holds no other autostash call. A `||` or `;` between them lets
    the push run after a failed pull.
    Counting per step pair, never by position in the command's git calls, keeps `$(...)` calls (listed last by
    git_calls) from shifting the result."""
    normalized = shell_statements.shell_code(command)
    steps = shell_command.split_command_steps(normalized)
    allowed = 0
    for (_before, pull_step), (operator, push_step) in itertools.pairwise(steps):
        if operator != "&&":
            continue
        if shell_statements.code_spans(pull_step) or shell_statements.code_spans(push_step):
            continue
        if any(char in step for step in (pull_step, push_step) for char in "()"):
            continue
        # A code runner takes its directory or host from text the gate does not read.
        if shell_command.names_code_runner(pull_step) or shell_command.names_code_runner(push_step):
            continue
        pull_calls = git_calls(pull_step)
        push_calls = git_calls(push_step)[:1]
        if not (pull_calls and push_calls):
            continue
        pull = pull_calls[-1]
        push = push_calls[0]
        if pull.subcommand != "pull" or not is_autostash(pull) or "--autostash" not in pull.arguments:
            continue
        if push.subcommand != "push":
            continue
        if os.path.normpath(push.directory) != os.path.normpath(pull.directory):
            continue
        if dir_targets_differ(pull_step, push_step):
            continue
        if any(is_autostash(call) for call in pull_calls[:-1]):
            continue
        allowed += 1
    return allowed


def literal_dir_targets(step):
    """The repo-selecting text, as written, of the git call that opens the step: its `-C`, `--git-dir` and
    `--work-tree` options (spaced or `=` form) and the repo environment assignments (`REPO_ENVIRONMENT_NAMES`)
    before it."""
    all_words = shell_command.segment_words(step)
    words = shell_command.command_after_wrappers(all_words)
    wrapper_words = all_words[:len(all_words) - len(words)]
    targets = [word for word in wrapper_words if word.startswith(REPO_ENV_PREFIXES)]
    options, _index = shell_command.git_options(words)
    for option, value in options:
        if option in REPO_OPTIONS:
            targets.append(option + "=" + (value or ""))
        elif option.startswith(REPO_OPTION_PREFIXES):
            targets.append(option)
    return targets


def dir_targets_differ(pull_step, push_step):
    """True when the two calls' repo-selecting text (`-C`, `--git-dir`, `--work-tree`, the repo environment names
    of `REPO_ENVIRONMENT_NAMES`) differs. A target with a mark the directory reader skips (`$`, quote, glob)
    resolves to the caller's cwd, so equal directories prove nothing. Fails closed on harmless spellings like `/r`
    vs `/r/`."""
    pull_targets = literal_dir_targets(pull_step)
    push_targets = literal_dir_targets(push_step)
    return pull_targets != push_targets


def turns_on_autostash_config(arguments):
    # `git config [--global] rebase.autoStash true` sets it; a read (`--get`, no value) and a false value do not.
    for index, argument in enumerate(arguments):
        if argument.lower() not in AUTOSTASH_KEYS:
            continue
        if index + 1 == len(arguments):
            return False
        return arguments[index + 1].lower() not in GIT_FALSE_VALUES
    return False


def is_amend(call):
    return call.subcommand == "commit" and "--amend" in call.arguments


# Fails closed: a missing or unreadable transcript, or no typed prompt, means no approval and the amend stays denied.
def user_approved_amend(transcript_path):
    """True when a sentence of the user's newest typed prompt orders an amend, holds no negation and is not a question.
    Pasted text, appended reminders and quoted code inside the prompt are not the user's order and are dropped first."""
    if not transcript_path:
        return False
    prompt = user_prompts.latest_prompt(transcript_path)
    if prompt is None:
        return False

    typed_words = user_prompts.user_words(prompt)
    unquoted_words = QUOTED_CODE.sub(" ", typed_words)
    sentences = PROMPT_SENTENCE_END.split(unquoted_words)
    statements = [sentence for sentence in sentences if not sentence.rstrip().endswith("?")]
    return any(ORDERS_AMEND.search(sentence) and not NEGATION.search(sentence) for sentence in statements)


def apply_writes_index(argument):
    if is_short_cluster(argument):
        # `-p<n>` and `-C<n>` take a number, which is not the `-3` or `-N` flag.
        flags = flags_before_value(argument, "pC")
        return "3" in flags or "N" in flags
    return (is_long_prefix(argument, "--3way", "--3") or is_long_prefix(argument, "--cached", "--ca")
            or is_long_prefix(argument, "--index", "--ind")
            or is_long_prefix(argument, "--intent-to-add", "--int"))


def checkout_makes_branch(argument):
    if is_short_cluster(argument):
        # `-b` and `-B` take the branch name, so a flag run that ends early holds one of them.
        return "b" in argument[1:] or "B" in argument[1:]
    return is_orphan_option(argument)


def checkout_patches(argument):
    if is_short_cluster(argument):
        return "p" in flags_before_value(argument, SWITCH_VALUE_LETTERS["checkout"])
    if is_long_prefix(argument, "--patch", "--patc"):
        return True
    return is_pathspec_from_file(argument)


def checkout_writes_index(arguments):
    """True for the checkouts that write the index: `git checkout <tree-ish> [--] <paths>`,
    `git checkout -p <tree-ish>`, and a forced or merging checkout (`-m`, `--merge`, `--conflict`, `-f`, `--force`)
    with no paths after `--`.

    `git checkout -- <paths>` and a plain `git checkout <branch>` pass; `-b`, `-B` and `--orphan` make a branch, not
    a path checkout.
    """
    options = options_before_separator(arguments)
    has_paths_after_separator = len(arguments) - len(options) > 1
    if not has_paths_after_separator and switch_writes_index(options, SWITCH_VALUE_LETTERS["checkout"]):
        # A forced or merging checkout acts on HEAD or the target branch, with or without `-b`.
        return True
    if any(checkout_makes_branch(argument) for argument in options):
        return False
    option_words = without_flag_values(options, takes_value=takes_separate_value)
    positionals = [argument for argument in option_words if not argument.startswith("-")]
    if len(positionals) >= 2:
        return True
    if not positionals:
        return False
    if has_paths_after_separator:
        return True
    return any(checkout_patches(argument) for argument in options)


def merges_on_switch(argument, value_letters):
    """True for the option of a branch switch that merges local changes into the target: `-m`, `--merge` and
    `--conflict[=<style>]`. value_letters are the cluster letters that take the branch name."""
    if is_short_cluster(argument):
        return "m" in flags_before_value(argument, value_letters)
    option_name = argument.split("=")[0]
    return is_long_prefix(argument, "--merge", "--m") or is_long_prefix(option_name, "--conflict", CONFLICT_SHORTEST)


def switch_writes_index(options, value_letters):
    """True when any option merges local changes into the target or discards them (`-m`, `--merge`, `--conflict`,
    `-f`, `--force`, `--discard-changes`)."""
    return any(merges_on_switch(argument, value_letters) or discards_on_switch(argument, value_letters)
               for argument in options)


def writes_index(call):
    """True when the git call stages, unstages, commits, merges, pulls, rebases, applies a patch to the index,
    checks paths out of a tree, switches to an orphan branch, or switches or checks out a branch with a forced or
    merging option."""
    if call.subcommand in INDEX_WRITING_COMMANDS:
        return True
    options = options_before_separator(call.arguments)
    if call.subcommand == "switch":
        # `-c` and `-C` take the branch name, so a letter after them is part of it.
        # `--orphan` removes every tracked file, which empties the index.
        makes_orphan = any(is_orphan_option(argument) for argument in options)
        return makes_orphan or switch_writes_index(options, SWITCH_VALUE_LETTERS["switch"])
    if call.subcommand == "restore":
        return any(restore_stages(argument) for argument in options)
    if call.subcommand == "apply":
        return any(apply_writes_index(argument) for argument in options)
    if call.subcommand == "checkout":
        return checkout_writes_index(call.arguments)
    return False


def payload_of(raw):
    """The hook input as a dict, empty for blank input. Raises on input jq rejects."""
    if raw.strip() == "":
        return {}
    return json.loads(raw)


def command_of(payload):
    """`jq -r '.tool_input.command // ""'` with trailing newlines dropped.

    Raises JqError when the payload or its tool_input is not an object.
    """
    return jq_str(jq_get(payload, "tool_input", "command"))


def is_direct_edit_repo(directory):
    root = script_utils.repo_root(directory)
    if root is None:
        return False
    try:
        with open(root / "CLAUDE.md", "rb") as handle:
            return b"direct-edit repo" in handle.read().lower()
    except OSError:
        return False


def check_coder_index(payload, calls):
    """Rule 6. Passes when agent_type is absent or not a coder (the main session, omp); an internal error fails
    closed in main()."""
    agent_type = jq_str(jq_get(payload, "agent_type"))
    if not script_utils.CODERS.match(agent_type):
        return
    if any(writes_index(call) for call in calls):
        raise DenyError(CODER_INDEX_DENIED)


def check_autostash(command, calls):
    """Rule 1, autostash half: deny every autostash call except the counted pull-then-push pairs."""
    autostash_count = sum(is_autostash(call) for call in calls)
    if not autostash_count or autostash_count == count_pull_push_pairs(command):
        return
    raise DenyError("[git-discipline-gate] git autostash is blocked: it runs a git stash, which every worktree "
                    "shares and which resets staged files. Pass --no-autostash to the command, or do not set the "
                    "autostash config. To pull right before a push and keep staged files staged, run "
                    "`python3 ~/.claude/scripts/tools/pull_keep_index.py <repo> "
                    "&& git -C <repo> push -u origin HEAD`. "
                    f"{MERGE_WITH_WORK_UNCOMMITTED}")


def run(raw):
    try:
        payload = payload_of(raw)
        command = command_of(payload)
    except (ValueError, JqError):
        raise DenyError(
            "[git-discipline-gate] hook input did not parse — failing closed. Report this to the user."
        ) from None
    if not command:
        return

    payload_cwd = jq_str(jq_get(payload, "cwd")) or "."
    calls = git_calls(command, payload_cwd)

    check_coder_index(payload, calls)

    if any(is_stash(call) for call in calls):
        raise DenyError("[git-discipline-gate] git stash is blocked in every form, a tagged `git stash push -m <tag>` "
                        "included: every worktree shares one stash stack, and a stash resets staged files. "
                        f"{MERGE_WITH_WORK_UNCOMMITTED} If stashing is genuinely needed, ask the user — they can run "
                        "it themselves.")

    check_autostash(command, calls)

    if any(is_amend(call) for call in calls):
        transcript_path = jq_str(jq_get(payload, "transcript_path"))
        approved = user_approved_amend(transcript_path)
        if not approved or any(is_force_push(call) for call in calls):
            raise DenyError(AMEND_DENIED)

    if COMMIT_OR_PR.search(command) and ATTRIBUTION.search(command):
        raise DenyError("[git-discipline-gate] Commit and PR text must carry no attribution or session trailer. Remove "
                   "it and retry.")

    for call in calls:
        check_destructive(call)
        check_branch(call)

    check_shared_clone_commit(command, calls, payload_cwd)
    check_land_lane(command)
    check_push_reviewed(command, calls, payload_cwd)
    check_directory_emptying(command, payload_cwd)
    check_docker_run_names(command, payload_cwd)


def check_land_lane(command):
    """Rule 12: a step that runs tools/land_lane.py, which pushes to master from inside Python where rule 7 cannot see
    the push. Fails closed like the rest of the gate: a step the parser cannot read is still cut on its operators."""
    if not land_lane_calls.runs_land_lane(command):
        return
    raise DenyError("[git-discipline-gate] land_lane.py pushes to master, so only the user runs it, as a `!` line. "
                    "Do not run it. Hand the user the `!` line that runs it instead.")


def bare_commit_in_shared_clone(call, directory, sole_step=None):
    """True when `call` is a `git commit` that is bare per `commit_pathspec.is_bare_commit` and lands in a shared
    clone: its `--git-dir` is judged in place of `directory`. False for such a commit that ends an open merge
    (no -a/-i, every staged path belongs to the merge) when `sole_step`, a function called only once the clone is
    shared and the commit takes no -a/-i, says it is the command's only step besides `cd`/`pushd`/`popd`: an
    earlier step of a longer command may stage a peer's file after the hook reads the index."""
    if call.subcommand != "commit" or not commit_pathspec.is_bare_commit(call.arguments):
        return False
    git_dir_folder = git_dir_holder(call.git_dir)
    # The index is $GIT_DIR/index: --work-tree does not choose it.
    folder = directory if git_dir_folder is None else git_dir_folder
    if not shared_clones.is_shared_clone(folder):
        return False
    if sole_step is None or commit_pathspec.sweeps_whole_index(call.arguments):
        return True
    if not sole_step():
        return True
    # Git refuses a pathspec commit during a merge, so a bare one is the only way to end it.
    return not merge_in_progress.commit_ends_merge(folder)


def is_bare_shared_commit(words, directory, sole_step):
    """commit_call for git_commit_dirs (bound to `sole_step`, a function that says whether the command's only
    step besides `cd`/`pushd`/`popd` is the git call, by check_shared_clone_commit): True for a bare `git commit`
    that lands in a shared clone, except one that ends an open merge as the only step besides `cd`/`pushd`/`popd`
    in a folder the gate read (see bare_commit_in_shared_clone), judging its `--git-dir`, or its `-C` when
    `git_c_directory` does not follow it, it is absolute or the call is not placed, in place of `directory`. A
    `~user` `-C` is unread and judged in the hook's cwd."""
    call = git_call(words, directory)
    if call is None:
        return False
    c_directory = shell_command.git_c_directory(words, directory)
    # A commit whose folder the gate did not read (an unread `-C` or `--git-dir` value, an unplaced call) falls back
    # to the last folder it could read, which is not where the commit lands: it gets no merge exemption. An unread
    # `cd` is refused by is_sole_git_command.
    folder_read = call.placed and (c_directory is not None or git_dir_holder(call.git_dir) is not None)

    def exempt_sole_step():
        return folder_read and sole_step()

    if not call.placed or c_directory is None or shell_command.git_c_is_absolute(words):
        # `directory` is not moved by the `-C` options here (or the shell's folder is unknown, and an absolute
        # `-C` names the same folder from any start), so judge the folder they move to. An unread `-C` value
        # leaves `call.directory` at the last folder the gate could read.
        return bare_commit_in_shared_clone(call, call.directory, exempt_sole_step)
    return bare_commit_in_shared_clone(call, directory, exempt_sole_step)


def is_sole_git_command(command, payload_cwd):
    """True when `command` runs exactly one command besides `cd`/`pushd`/`popd` steps, and that command is a plain
    `git` call: no env assignment or wrapper before it (`GIT_DIR=`, `GIT_INDEX_FILE=`, `env`) and no command or
    process substitution, so nothing can change the index or the target clone between the hook's read and the
    commit. A `cd` the gate cannot read is not a sole step: the commit lands in a folder the hook's cwd does not
    name.
    Reads the same strip_stored_heredocs text as git_commit_dirs, so the lines of a body that cat or tee writes to a
    file, or that a script run reads, are not read as steps; a command that stores one, such as `cat > f <<EOF`, is
    still a step, and so is a `git commit -F - <<EOF` body line.
    Called only after git_commit_dirs has read the command, so it parses."""
    placed = git_commit_calls.commit_read_steps(command, payload_cwd)
    if len(placed) != 1:
        return False
    only = placed[0]
    if only.simple_command != only.words or only.words[0] != "git":
        return False
    if only.directory is None:
        return False
    has_substitution = bool(shell_command.substitution_bounds(only.step))
    has_process_substitution = bool(shell_command.process_substitution_bounds(only.step))
    return not has_substitution and not has_process_substitution


def check_shared_clone_commit(command, calls, payload_cwd):
    """Rule 11: a `git commit` that takes the whole index in a shared clone sweeps in the staged files of peer
    sessions. A bare commit whose `--git-dir` or `-C` names a shared clone is denied, as is one inside a code
    runner (`bash -c '...'`), judged from `calls`; the one exception is a commit without -a/-i that is the
    command's only step besides `cd`/`pushd`/`popd`, lands in a folder the gate read (not the fallback for an
    unread `cd` or `-C`), and ends an open merge whose staged paths all belong to the merge. A `GIT_DIR` assignment
    is judged in the folder the shell stands in; an `env -C`/`sudo -D` wrapper, a call after a `cd` it cannot read
    and an unread `-C` value (a `~user` one included) are judged in the hook's cwd, or in the folder an absolute
    `-C` names. A call read from code-runner text is judged in the folder the outer command's `cd` steps, when no
    `(` comes before a `cd`, move to (the hook's cwd when there are none); a `cd` inside the runner text is not
    read.
    A command `git_commit_dirs` cannot read as steps is judged only through runner text, all of
    it; when it can, only the `git` words inside the runner's quotes are judged there, so a `(cd ..)` or `pushd`
    step it already read is not judged twice at the hook's cwd. Rule 11 fails open when neither reader finds the
    commit. Accepted limit: a commit inside a file the same command writes through a stored heredoc and then runs
    (`bash run.sh`, `source run.sh`, `. ./run.sh`) is not read, like the commits of any script file."""
    runner_text = shell_command.names_code_runner(shell_statements.shell_code(command))
    sole_step_answers = []

    def sole_step():
        # Computed on the first commit that reaches the exemption, so a command with no such commit is not parsed twice.
        if not sole_step_answers:
            sole_step_answers.append(not runner_text and is_sole_git_command(command, payload_cwd))
        return sole_step_answers[0]

    def commit_call(words, directory):
        return is_bare_shared_commit(words, directory, sole_step)

    found = git_commit_calls.git_commit_dirs(command, payload_cwd, commit_call)
    runner_calls = calls
    if runner_text and found is not None:
        runner_calls = git_calls(command, payload_cwd, quoted_only=True)
    in_runner_text = runner_text and any(bare_commit_in_shared_clone(call, call.directory) for call in runner_calls)
    placed_in_shared = found is not None and (found.commit_dirs or found.unplaced)
    if not (placed_in_shared or in_runner_text):
        return
    raise DenyError("[git-discipline-gate] git commit that takes the whole index (no `-- <paths>`, or -a/--all, "
                    "-i/--include) in a shared clone is blocked: the index holds files other sessions staged, and "
                    "such a commit takes them too. Commit only your files with `git commit -m <msg> -- <paths>`.")


def check_docker_run_names(command, payload_cwd):
    """Rule 10: a `docker run` with no `--name`, denied with the fixed form of the first one."""
    forms = docker_run_names.unnamed_docker_runs(command, payload_cwd)
    if forms:
        raise DenyError("[git-discipline-gate] docker run without --name: an unnamed container cannot be tied to a "
                        f"ticket or session, and one that hangs runs on unseen. Run it as: {forms[0]}\n"
                        "--name carries the ticket key and the purpose, and --rm removes the container at "
                        "exit.")


def check_directory_emptying(command, payload_cwd):
    """Rule 9: plain `rm` calls whose targets cover every entry of an existing directory."""
    folders = directory_emptying_deletes.emptied_directories(command, payload_cwd)
    if not folders:
        return
    folder = folders[0]
    raise DenyError(f"[git-discipline-gate] rm of every entry in {folder} empties it: this is the recursive "
                    "delete bash-safety-gate denies as rm_recursive_force, split into files. A blocked delete "
                    "is never split or disguised. Leave the files and report the delete as a stop, so the user "
                    f"can run `rm -r {shlex.quote(folder)}` themselves.")


def opens_pull_request(command):
    """True when a step of the command runs `gh pr create`."""
    code = shell_statements.shell_code(command)
    for words in shell_command.step_words(code):
        if len(words) >= 3 and os.path.basename(words[0]) == "gh" and words[1:3] == ["pr", "create"]:
            return True
    return False


def check_push_reviewed(command, calls, payload_cwd):
    """Rule 8: a `git push` or `gh pr create` whose repo's HEAD holds code changed since the last converged review.
    A repo with no review record passes."""
    push_dirs = [call.directory for call in calls if call.subcommand == "push"]
    if opens_pull_request(command):
        push_dirs.append(payload_cwd)
    for directory in push_dirs:
        state = reviewed_tree.push_review_state(directory)
        if state == reviewed_tree.PUSH_CHANGED:
            base = reviewed_tree.newest_reviewable_base(directory)
            if base:
                raise DenyError(PUSH_UNREVIEWED_DENIED_WITH_BASE.format(base=base))
            raise DenyError(PUSH_UNREVIEWED_DENIED)


def check_destructive(call):
    """Rule 7: deny a forced push, a push that names main or master, `reset --hard`, `clean -f`, a discard of the whole
    work tree and `--no-verify` in a main checkout. A linked worktree is a lane's own tree, so it passes. A repo the
    gate cannot find reads as a main checkout."""
    reason = destructive_reason(call)
    if reason is None or is_linked_worktree(call):
        return
    notes = []
    config_note = config_trigger_note(call, reason)
    if config_note:
        notes.append(config_note)
    if not call.placed:
        notes.append("this call runs in a repo the gate cannot place, so it reads as a main checkout")
    detail = f" ({'; '.join(notes)})" if notes else ""
    raise DenyError(f"[git-discipline-gate] {reason} is blocked in a main checkout{detail}: it destroys work or skips "
                    "a check that other sessions rely on. Ask the user to run it themselves.")


def check_branch(call):
    """Rules 4 and 5 for one commit or push call, on the branch of the repo it runs in."""
    if call.subcommand not in ("commit", "push"):
        return
    branch = script_utils.current_branch(call.directory) or ""

    if branch.startswith("worktree-"):
        raise DenyError("[git-discipline-gate] branch '" + branch + "' still carries the auto-generated worktree- "
                   "prefix. Rename it to the plain TICKET-NUM-desc form and push it with -u first, then retry.")

    if call.subcommand == "commit" and branch in PROTECTED_BRANCHES and not is_direct_edit_repo(call.directory):
        raise DenyError("[git-discipline-gate] git commit on " + branch + " is blocked: create a feature branch "
                   "first (global rule). If committing here is genuinely intended, the user can run it "
                   "themselves.")


def main():
    if os.environ.get("CLAUDE_SKIP_HOOKS"):
        return 0
    internal = False
    try:
        run(sys.stdin.buffer.read().decode("utf-8", "replace"))
    except DenyError as denied:
        hook_input.emit_decision("deny", str(denied))
    except Exception:
        internal = True
    if internal:
        hook_input.emit_decision("deny", "[git-discipline-gate] internal error (exit 1) — failing closed. "
                                         "Report this to the user.")
    return 0


if __name__ == "__main__":
    hook_input.run_gate(main)
