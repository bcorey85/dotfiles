"""commit_gate_denials.py: the deny texts of review_commit_gate.py for a commit in a repo with a ruling still open:
plan impacts the latest review handed back, and phase asks that no session has ruled on, whatever review came after.
unruled_plan_impact_denial and unruled_phase_asks_denial take the commit's repo dirs, git_timeout and (the plan
impacts) the session id; commit_asks_denial takes the dirs the command placed, the commits it left unplaced and the
hook's cwd, and wraps unruled_phase_asks_denial. Each returns the deny text, or None when nothing is open. The two
that import the store fail open when the store or its readers cannot be imported: the gate's own no-review deny still
applies. The phase-asks check also fails open on a store it cannot read, and fails closed on a
damaged row of the repo (an unparsable line counts only when it names the repo). A commit the gate
cannot place in a repo is read in the hook's cwd repo (fail closed), so it can be denied for that repo's asks
(commit_asks_denial)."""
import pathlib
import shlex
import sys

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent / folder) for folder in (".", "../lib")]
import hook_input
import plan_format
import script_utils


def commit_repo_tops(repo_dirs, git_timeout):
    """The top level of each repo dir the commit runs in; a dir of None or outside a work tree names none."""
    tops = []
    for repo_dir in repo_dirs:
        repo_top = script_utils.repo_root(repo_dir, timeout=git_timeout) if repo_dir else None
        if repo_top is not None:
            tops.append(repo_top)
    return tops


def unruled_plan_impact_denial(repo_dirs, session, git_timeout):
    """The deny text for a commit in a repo whose latest review handed back plan impacts that still await a ruling,
    or None. A ruling settles them."""
    try:
        import handback
    except ImportError as error:
        # A missing store or handback module skips this check (fail open): the plain review deny still applies.
        hook_input.emit_stderr(f"review-commit-gate: cannot import handback: {error}\n")
        return None

    for repo_top in commit_repo_tops(repo_dirs, git_timeout):
        unruled = handback.session_unruled_plan_impacts(session, str(repo_top))
        if not unruled:
            continue
        review_fix = pathlib.Path(__file__).resolve().parent / "review_fix.py"
        return (
            f"[review-commit-gate] The latest /review of {repo_top} handed back {len(unruled)} plan impact(s) that "
            f"await a ruling. Do not run /review again: rule on them first, with `python3 {review_fix} defer "
            f"<handoff file>` to defer them to phase end or `python3 {review_fix} {plan_format.DECIDE_USAGE}`. "
            "`defer` and `decide keep` settle them, and so does `decide adopt` when every fix is already in "
            "the tree and the packet leaves nothing else open; any other `decide adopt` logs the deviation and "
            "re-dispatches the loop (or, when no packet state waits on this impact, stops for "
            "`/code resume`). Then commit the tree the review covered."
        )
    return None


def commit_asks_denial(named_dirs, unplaced_commits, cwd, git_timeout):
    """unruled_phase_asks_denial for a command whose commits git_commit_dirs placed in `named_dirs` (None: the
    command cannot be read) and left `unplaced_commits` out. The placed dirs are judged as they are. Only when they
    draw no deny does an unplaced commit count as one in the hook's `cwd` repo (fail closed: the gate cannot tell which
    repo it lands in), and that deny tells the session to name the repo with `git -C`."""
    if named_dirs is None:
        return unruled_phase_asks_denial([cwd], git_timeout)
    named_denial = unruled_phase_asks_denial(list(named_dirs), git_timeout)
    if named_denial is not None or not unplaced_commits:
        return named_denial
    cwd_denial = unruled_phase_asks_denial([cwd], git_timeout)
    if cwd_denial is None:
        return None
    return (cwd_denial + " The gate cannot place this command's git call in a repo: run `git -C <repo> <subcommand>` "
            "on one line naming the repo the call lands in, with no `cd`, `env -C` or `--git-dir`.")


def unruled_phase_asks_denial(repo_dirs, git_timeout):
    """The deny text for a commit in a repo where a phase review handed finding asks that nobody has ruled on, or
    None. The asks belong to the repo, not to a session: a session with a new id meets them too. Only a ruling
    settles them: a later review of the repo leaves them open. Only the repos of `repo_dirs` (the dirs the command
    names) are read; a dir outside any work tree names none."""
    try:
        import ask_outcome_words
        import handback_store
    except ImportError as error:
        # A missing store or word module skips this check (fail open): a session with no open row is never blocked.
        hook_input.emit_stderr(f"review-commit-gate: cannot import ask_outcome_words: {error}\n")
        return None

    for repo_top in commit_repo_tops(repo_dirs, git_timeout):
        try:
            open_row = handback_store.unruled_phase_asks(str(repo_top))
        except handback_store.PhaseAskRowError as error:
            # A damaged row of this repo fails closed: the asks it held cannot be told apart from none, and the deny
            # names the line to fix or delete.
            return (f"[review-commit-gate] Cannot read the phase review asks: {error}. Fix or delete that line of "
                    "the hand-back store, then commit.")
        except OSError as error:
            # A store that cannot be read fails open: the deny could name no fix, and the plain review deny still
            # applies. The reason goes to stderr.
            hook_input.emit_stderr(f"review-commit-gate: cannot read the phase review asks of {repo_top}: {error}\n")
            continue
        if open_row is None:
            continue
        asks = open_row["asks"]
        listed = "; ".join(f"{number}. {script_utils.one_line(script_utils.ask_text(item), 200)}"
                           for number, item in enumerate(asks, 1))
        return (
            f"[review-commit-gate] A phase review of {repo_top} handed back {len(asks)} ask(s) that you have "
            f"not ruled on: {listed}. Do not run /review again: rule on them first, with "
            f"`cd {shlex.quote(str(repo_top))} && {ask_outcome_words.rule_command(len(asks))}` "
            f"(`{ask_outcome_words.LIST_COMMAND}` shows each ask's change, also from there). "
            "Then commit the tree the review covered."
        )
    return None
