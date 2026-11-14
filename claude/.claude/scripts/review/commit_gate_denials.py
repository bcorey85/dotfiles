"""commit_gate_denials.py: the deny texts of review_commit_gate.py for a commit in a repo with a ruling still open:
plan impacts the latest review handed back, and phase asks the session has not ruled on, whatever review came after.
Each function takes the commit's repo dirs, the session id and git_timeout, and returns the deny text, or None when
nothing is open. Both fail open when the store or its readers cannot be imported: the gate's own no-review deny
still applies."""
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
        import handback_store
    except ImportError as error:
        # A missing store or handback module skips this check (fail open): the plain review deny still applies.
        hook_input.emit_stderr(f"review-commit-gate: cannot import handback: {error}\n")
        return None

    for repo_top in commit_repo_tops(repo_dirs, git_timeout):
        unruled = handback.unruled_plan_impacts(handback_store.latest_for_repo(session, str(repo_top)))
        if not unruled:
            continue
        review_fix = pathlib.Path(__file__).resolve().parent / "review_fix.py"
        return (
            f"[review-commit-gate] The latest /review of {repo_top} handed back {len(unruled)} plan impact(s) that "
            f"await a ruling. Do not run /review again: rule on them first, with `python3 {review_fix} defer "
            f"<handoff file>` to defer them to phase end or `python3 {review_fix} {plan_format.DECIDE_USAGE_STEM}`. "
            "Only `decide keep` settles them; `decide adopt` logs the deviation and re-dispatches the loop (or, with "
            "no `packet` state, stops for `/code resume`). Then commit the tree the review covered."
        )
    return None


def unruled_phase_asks_denial(repo_dirs, session, git_timeout):
    """The deny text for a commit in a repo where a phase review handed the session finding asks it has not ruled
    on, or None. Only a ruling settles them: a later review of the repo leaves them open."""
    try:
        import handback_store
        import phase_asks
    except ImportError as error:
        # A missing store or ask module skips this check (fail open): a session with no open row is never blocked.
        hook_input.emit_stderr(f"review-commit-gate: cannot import phase_asks: {error}\n")
        return None

    for repo_top in commit_repo_tops(repo_dirs, git_timeout):
        open_row = handback_store.unruled_phase_asks(session, str(repo_top))
        if open_row is None:
            continue
        asks = open_row["asks"]
        listed = "; ".join(f"{number}. {script_utils.one_line(script_utils.ask_text(item), 200)}"
                           for number, item in enumerate(asks, 1))
        return (
            f"[review-commit-gate] A phase review of {repo_top} handed back {len(asks)} ask(s) that you have "
            f"not ruled on: {listed}. Do not run /review again: rule on them first, with "
            f"`cd {shlex.quote(str(repo_top))} && {phase_asks.rule_command(len(asks))}` "
            f"(`{phase_asks.LIST_COMMAND}` shows each ask's change, also from there). "
            "Then commit the tree the review covered."
        )
    return None
