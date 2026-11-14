#!/usr/bin/env python3
"""PreToolUse hook on Bash: enforce git rules the generic bash safety gate does not cover.

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

Rules 4 and 5 read the branch of the repo each call runs in. How the gate finds git calls and the directory each runs
in is documented in git_calls.py.

Denies with PreToolUse decision JSON. Fails closed on internal error.
"""
import itertools
import json
import os
import re
import sys

sys.path[:0] = [os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib")]
import hook_input
import script_utils
import shell_command
import shell_statements
import user_prompts
from git_calls import git_calls
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
REPO_ENV_PREFIXES = ("GIT_DIR=", "GIT_WORK_TREE=")
# git accepts `--c` as `--conflict` on checkout; on switch `--c` is ambiguous and git refuses it, so the wider match
# only denies calls git would reject.
CONFLICT_SHORTEST = "--c"
FALSE_VALUES = {"false", "no", "off", "0"}
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
    return any(call.config[key] not in FALSE_VALUES for key in AUTOSTASH_KEYS if key in call.config)


def count_pull_push_pairs(command):
    """Count the `git pull --autostash` steps that are the one allowed form: the pull is the last git call of its step,
    the next step is joined by `&&` and opens with a git push in the same directory, neither step holds a `$(...)`,
    backtick span or parenthesis, and the pull step holds no other autostash call. A `||` or `;` between them lets
    the push run after a failed pull.
    Counting per step pair, never by position in the command's git calls, keeps `$(...)` calls (listed last by
    git_calls) from shifting the result."""
    normalized = shell_statements.strip_comments(shell_statements.strip_heredocs(command))
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
    `--work-tree` options (spaced or `=` form) and the GIT_DIR and GIT_WORK_TREE assignments before it."""
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
    """True when the two calls' repo-selecting text (`-C`, `--git-dir`, `--work-tree`, GIT_DIR, GIT_WORK_TREE)
    differs. A target with a mark the directory reader skips (`$`, quote, glob)
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
        return arguments[index + 1].lower() not in FALSE_VALUES
    return False


def is_amend(call):
    return call.subcommand == "commit" and "--amend" in call.arguments


def is_force_push(call):
    if call.subcommand != "push":
        return False
    for argument in call.arguments:
        is_long_flag = argument.startswith("--force")
        is_plus_refspec = argument.startswith("+")
        is_short_flag_cluster = is_short_cluster(argument) and "f" in argument
        if is_long_flag or is_plus_refspec or is_short_flag_cluster:
            return True
    return False


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


def restore_stages(argument):
    if is_short_cluster(argument):
        # `-s<tree>` and `-U<n>` take a value, which is not the `-S` flag.
        return "S" in flags_before_value(argument, "sU")
    return is_long_prefix(argument, "--staged", "--st")


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
    return is_long_prefix(argument, "--orphan", "--or")


def checkout_patches(argument):
    if is_short_cluster(argument):
        return "p" in flags_before_value(argument, "bB")
    if is_long_prefix(argument, "--patch", "--patc"):
        return True
    option_name = argument.split("=")[0]
    return is_long_prefix(option_name, "--pathspec-from-file", "--pathspec-fr")


def takes_separate_value(argument):
    # `--conflict <style>`, `--pathspec-from-file <file>`, `--unified <n>`, `--inter-hunk-context <n>` and a short
    # cluster ending in `U` (`-U <n>`, `-pU <n>`) carry their value in the next word.
    if is_short_cluster(argument):
        return argument.endswith("U")
    if is_long_prefix(argument, "--conflict", CONFLICT_SHORTEST):
        return True
    if is_long_prefix(argument, "--unified", "--u"):
        return True
    if is_long_prefix(argument, "--inter-hunk-context", "--in"):
        return True
    return is_long_prefix(argument, "--pathspec-from-file", "--pathspec-fr")


def checkout_writes_index(arguments):
    """True for the checkouts that write the index: `git checkout <tree-ish> [--] <paths>`,
    `git checkout -p <tree-ish>`, and a forced or merging checkout (`-m`, `--merge`, `--conflict`, `-f`, `--force`)
    with no paths after `--`.

    `git checkout -- <paths>` and a plain `git checkout <branch>` pass; `-b`, `-B` and `--orphan` make a branch, not
    a path checkout.
    """
    options = options_before_separator(arguments)
    has_paths_after_separator = len(arguments) - len(options) > 1
    if not has_paths_after_separator and switch_writes_index(options, "bB"):
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


def discards_on_switch(argument, value_letters):
    """True for `-f`, `--force` and `--discard-changes`, which reset the index to the target branch."""
    if is_short_cluster(argument):
        return "f" in flags_before_value(argument, value_letters)
    return is_long_prefix(argument, "--force", "--f") or is_long_prefix(argument, "--discard-changes", "--di")


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
        makes_orphan = any(is_long_prefix(argument.split("=")[0], "--orphan", "--or") for argument in options)
        return makes_orphan or switch_writes_index(options, "cC")
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

    calls = git_calls(command)

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
        check_branch(call)


def check_branch(call):
    """Rules 4 and 5 for one commit or push call, on the branch of the repo it runs in."""
    if call.subcommand not in ("commit", "push"):
        return
    branch = script_utils.current_branch(call.directory) or ""

    if branch.startswith("worktree-"):
        raise DenyError("[git-discipline-gate] branch '" + branch + "' still carries the auto-generated worktree- "
                   "prefix. Rename it to the plain TICKET-NUM-desc form and push it with -u first, then retry.")

    if call.subcommand == "commit" and branch in ("main", "master") and not is_direct_edit_repo(call.directory):
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
