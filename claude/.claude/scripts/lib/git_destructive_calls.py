"""Which git calls destroy work or skip a safety check, read from a GitCall (see git_calls.py):
- a forced push (`-f`, `--force*`, `+<refspec>`, `--mirror`);
- a push that names main or master, or pushes `--all` or `--mirror`;
- `reset --hard`;
- `clean -f`, or a `clean` forced by `-c clean.requireForce=false`, a `--config-env clean.requireForce=<VAR>` key or
  a GIT_CONFIG_* assignment;
- a discard of the whole work tree: `checkout -f`, `switch -f` or `--discard-changes`, `checkout -- .`, `restore .`;
- `--no-verify` on a commit, push or merge, or hooks turned off by `-c core.hooksPath=...`, a `--config-env
  core.hooksPath=<VAR>` key or a GIT_CONFIG_* assignment.
The one owner of those rules; the git discipline gate applies them in a main checkout.

Flags are read from the call's arguments after git's own options are dropped, so `git -C d reset -q --hard` and
`git --no-pager push -f origin x` read as `reset` and `push`."""
from git_calls import CONFIG_FROM_ENVIRONMENT
from git_commit_calls import COMMIT_VALUE_LETTERS, COMMIT_VALUE_OPTIONS
from git_subcommand_options import (
    GIT_FALSE_VALUES,
    PROTECTED_BRANCHES,
    SWITCH_VALUE_LETTERS,
    discards_on_switch,
    is_orphan_option,
    restore_restores_worktree,
    restore_stages,
    takes_separate_value,
)
from shell_command import (
    flags_before_value,
    is_long_prefix,
    is_short_cluster,
    one_letter_options,
    options_before_separator,
    value_letter_ends_cluster,
    without_flag_values,
)

# Pathspecs that name every file of the work tree.
WHOLE_TREE_PATHSPECS = {".", "./", ":/", "*"}
# The push options that take the next word as their value, which is no refspec.
PUSH_VALUE_OPTIONS = ("-o", "--push-option", "--repo", "--receive-pack", "--exec")
CLEAN_DRY_RUN_LETTERS = "n"


def push_arguments(call):
    """The push words with the value word of each option that takes one dropped, so `-o main` is no refspec."""
    return without_flag_values(call.arguments, value_flags=PUSH_VALUE_OPTIONS)


def is_force_push(call):
    """True for `push` with `--force`, `--force-with-lease`, `--force-if-includes`, `--mirror`, a short flag cluster
    holding `f`, or a `+<refspec>`."""
    if call.subcommand != "push":
        return False
    for argument in push_arguments(call):
        is_long_flag = argument.startswith("--force") or is_long_prefix(argument, "--mirror", "--mi")
        is_plus_refspec = argument.startswith("+")
        # `-oci.skip` holds a push option: the letters after `o` are its value, not flags.
        cluster_flags = flags_before_value(argument, one_letter_options(PUSH_VALUE_OPTIONS))
        is_short_flag_cluster = is_short_cluster(argument) and "f" in cluster_flags
        if is_long_flag or is_plus_refspec or is_short_flag_cluster:
            return True
    return False


def refspec_names_protected_branch(argument):
    """True when a push argument (`main`, `+master`, `HEAD:main`, `main:feature`, `src:refs/heads/MASTER`) names main
    or master on either side of the colon, in any case. The one owner of this rule."""
    if argument.startswith("-"):
        return False
    for part in argument.split(":"):
        branch = part.lstrip("+").removeprefix("refs/heads/")
        if branch.lower() in PROTECTED_BRANCHES:
            return True
    return False


def names_protected_branch(call):
    """True for `push` with a refspec that names main or master (`origin master`, `HEAD:main`, `main:feature`), or
    with `--all` or `--mirror`, which push main without naming it."""
    if call.subcommand != "push":
        return False
    arguments = push_arguments(call)
    for argument in arguments:
        if is_long_prefix(argument, "--all", "--al") or is_long_prefix(argument, "--mirror", "--mi"):
            return True
    return any(refspec_names_protected_branch(argument) for argument in arguments)


def is_hard_reset(call):
    options = options_before_separator(call.arguments)
    return call.subcommand == "reset" and any(is_long_prefix(option, "--hard", "--ha") for option in options)


def clean_forced_by_config(call):
    """True when the call's config can turn off `clean`'s force check: `-c clean.requireForce=false` (or an empty
    value), a `--config-env clean.requireForce=<VAR>` key, or a GIT_CONFIG_COUNT, GIT_CONFIG_PARAMETERS,
    GIT_CONFIG_GLOBAL, GIT_CONFIG_SYSTEM or GIT_CONFIG assignment."""
    require_force = call.config.get("clean.requireforce")
    if require_force in GIT_FALSE_VALUES or require_force == CONFIG_FROM_ENVIRONMENT:
        return True
    return call.environment_sets_config


def is_forced_clean(call):
    """True for `clean` with a force flag (`-f`, `-fd`, `--force`) or config that turns off the force check (see
    clean_forced_by_config), and no dry-run flag."""
    if call.subcommand != "clean":
        return False
    options = options_before_separator(call.arguments)
    # `-e <pattern>` and `-e<pattern>` hold a value, so the letters after `e` are not flags.
    clusters = [flags_before_value(option, "e") for option in options if is_short_cluster(option)]
    forced = any("f" in letters for letters in clusters) or any(is_long_prefix(o, "--force", "--f") for o in options)
    forced = forced or clean_forced_by_config(call)
    dry_run = any(CLEAN_DRY_RUN_LETTERS in letters for letters in clusters) or "--dry-run" in options
    return forced and not dry_run


def pathspecs_of(call):
    """The words that follow `--`, else the words that are not options."""
    if "--" in call.arguments:
        return call.arguments[call.arguments.index("--") + 1:]
    return [argument for argument in call.arguments if not argument.startswith("-")]


def checkout_names_paths(options, value_letters):
    """True when a `checkout` with no `--` names a tree-ish and a path (`checkout -f feature file.txt`), or reads its
    paths from `--pathspec-from-file`: that is a path checkout, not a discard of the whole work tree. The branch name
    after `-b`, `-B` or `--orphan`, and the value of an option that takes a separate word, are no paths."""
    def takes_next_word(argument):
        if value_letter_ends_cluster(argument, value_letters):
            return True
        if is_orphan_option(argument):
            return "=" not in argument
        return takes_separate_value(argument)

    if any(is_long_prefix(option.split("=")[0], "--pathspec-from-file", "--pathspec-fr") for option in options):
        return True
    words = without_flag_values(options, takes_value=takes_next_word)
    return len([word for word in words if not word.startswith("-")]) > 1


def switch_discards_changes(call):
    """True for `checkout` or `switch` given `-f`, `--force` or `--discard-changes` with no path after `--`: every
    uncommitted change in the work tree is thrown away."""
    value_letters = SWITCH_VALUE_LETTERS.get(call.subcommand)
    if value_letters is None:
        return False
    options = options_before_separator(call.arguments)
    has_paths_after_separator = len(call.arguments) - len(options) > 1
    if has_paths_after_separator:
        return False
    if call.subcommand == "checkout" and checkout_names_paths(options, value_letters):
        return False
    return any(discards_on_switch(option, value_letters) for option in options)


def discards_whole_tree(call):
    """True for `checkout -f`, `switch -f` and `switch --discard-changes`, and for `checkout` or `restore` given a
    pathspec that names the whole work tree. `restore --staged .` only unstages, so it passes unless `--worktree` is
    also given."""
    if switch_discards_changes(call):
        return True
    if call.subcommand not in ("checkout", "restore"):
        return False
    if not WHOLE_TREE_PATHSPECS.intersection(pathspecs_of(call)):
        return False
    if call.subcommand == "checkout":
        return True

    options = options_before_separator(call.arguments)
    stages = any(restore_stages(option) for option in options)
    restores_worktree = any(restore_restores_worktree(option) for option in options)
    return restores_worktree or not stages


def commit_takes_next_word(argument):
    if argument in COMMIT_VALUE_OPTIONS:
        return True
    return value_letter_ends_cluster(argument, COMMIT_VALUE_LETTERS)


HOOK_COMMANDS = ("commit", "push", "merge")


def hooks_set_by_config(call):
    """True for a `commit`, `push` or `merge` whose config can set core.hooksPath: `-c core.hooksPath=...`, a
    `--config-env core.hooksPath=<VAR>` key, or a GIT_CONFIG_COUNT, GIT_CONFIG_PARAMETERS, GIT_CONFIG_GLOBAL,
    GIT_CONFIG_SYSTEM or GIT_CONFIG assignment."""
    if call.subcommand not in HOOK_COMMANDS:
        return False
    return "core.hookspath" in call.config or call.environment_sets_config


def skips_hooks(call):
    """True for `commit`, `push` or `merge` with `--no-verify` or config that can set core.hooksPath (see
    hooks_set_by_config); `commit -n` is the same flag as `--no-verify`, while `merge -n` is `--no-stat`. A message
    or other value word is not read as a flag."""
    if call.subcommand not in HOOK_COMMANDS:
        return False
    if hooks_set_by_config(call):
        return True
    options = options_before_separator(call.arguments)
    if call.subcommand == "commit":
        options = without_flag_values(options, takes_value=commit_takes_next_word)
    for option in options:
        if is_long_prefix(option, "--no-verify", "--no-v"):
            return True
        is_commit_no_verify = call.subcommand == "commit" and is_short_cluster(option) and "n" in option
        if is_commit_no_verify and "n" in flags_before_value(option, COMMIT_VALUE_LETTERS):
            return True
    return False


CLEAN_REASON = "git clean -f"
NO_VERIFY_REASON = "--no-verify"


def destructive_reason(call):
    """The short name of the rule the call breaks, or None. A forced push is read before a push that names main."""
    if is_force_push(call):
        return "a forced push"
    if names_protected_branch(call):
        return "a push that names main or master"
    if is_hard_reset(call):
        return "git reset --hard"
    if is_forced_clean(call):
        return CLEAN_REASON
    if discards_whole_tree(call):
        return "a discard of the whole work tree"
    if skips_hooks(call):
        return NO_VERIFY_REASON
    return None


CLEAN_CONFIG_NOTE = ("a git config override (-c clean.requireForce, --config-env or a GIT_CONFIG_* variable) can turn "
                     "off clean's force check")
HOOKS_CONFIG_NOTE = ("a git config override (-c core.hooksPath, --config-env or a GIT_CONFIG_* variable) can set "
                     "core.hooksPath")


def config_trigger_note(call, reason):
    """The sentence that names a git config override as the trigger of a `git clean -f` or `--no-verify` reason; ''
    when the reason comes from a flag, or is another rule."""
    if reason == CLEAN_REASON and clean_forced_by_config(call):
        return CLEAN_CONFIG_NOTE
    if reason == NO_VERIFY_REASON and hooks_set_by_config(call):
        return HOOKS_CONFIG_NOTE
    return ""
