"""review_loop_outside_writes.py: the files a fix coder wrote outside the reviewed repo's work tree, as a mixin for
`LoopRun`. The scope guard watches the repo only, so a write to a sibling checkout (also through a symlinked path)
stays where the coder put it. The loop reads the coder's own transcript for the paths its Write, Edit, MultiEdit and
NotebookEdit calls named, and stops the run in a blocker that names each path. Nothing is put back.

Owner of which written paths count as outside the repo. Import it; never classify a written path another way.
The host has files_touched and keep_unreverted_open, and holds repo."""
import contextlib
import pathlib

import hook_input
import loop_transcript
import session_registry

# The notes of this run's passes, read by coder_fault_notes into the packet's tool_fault.
OUTSIDE_WRITE_FAULTS = []
# {pass name: the outside paths its transcript showed}, popped by every stop that names the paths.
PASS_OUTSIDE_WRITES = {}


class OutsideWriteError(RuntimeError):
    """A coder pass wrote a file outside the reviewed repo. The message is the blocker."""


def scratch_roots(repo, out):
    """The folders a coder may write to besides the repo: the temp folders and the loop's own `out`. A temp folder
    that holds the repo is no scratch folder, since every sibling checkout there would read as scratch."""
    resolved_repo = pathlib.Path(repo).resolve()
    temp_roots = [pathlib.Path(root) for root in hook_input.temp_roots() + hook_input.session_temp_roots()]
    roots = [root for root in temp_roots if not resolved_repo.is_relative_to(root)]
    roots.append(pathlib.Path(out).resolve())
    return list(dict.fromkeys(roots))


def outside_writes(repo, written, roots):
    """The sorted resolved paths of `written` (as the transcript names them) that lie outside the resolved `repo`
    and under none of the `roots`. A relative name reads against the repo; a symlink reads as its target."""
    resolved_repo = pathlib.Path(repo).resolve()
    outside = set()
    for name in written:
        resolved = (resolved_repo / name).resolve()
        if resolved.is_relative_to(resolved_repo):
            continue
        if any(resolved.is_relative_to(root) for root in roots):
            continue
        outside.add(str(resolved))
    return sorted(outside)


def outside_write_blocker(call_name, repo, paths):
    """The blocker for a pass that wrote the `paths` outside the reviewed `repo`."""
    return (f"{call_name} wrote files outside the reviewed repo {repo}: {', '.join(paths)}; the loop did not put "
            "them back, so revert them by hand before you push")


def record_pass_writes(role, repo, out, session):
    """Reads the transcript of the coder call `session` and sets PASS_OUTSIDE_WRITES[role] to its outside writes.
    Fails open, on purpose: a transcript that is missing or unreadable must not stop a run whose pass may be clean,
    so it leaves a note for the packet's tool_fault and records nothing."""
    PASS_OUTSIDE_WRITES.pop(role, None)
    transcript = session_registry.session_transcript(session)
    if transcript is None:
        OUTSIDE_WRITE_FAULTS.append(unreadable_note(role, session))
        return
    try:
        written = loop_transcript.written_paths(transcript, succeeded_only=True)
    except OSError:
        OUTSIDE_WRITE_FAULTS.append(unreadable_note(role, session))
        return
    paths = outside_writes(repo, written, scratch_roots(repo, out))
    PASS_OUTSIDE_WRITES[role] = paths
    if paths:
        OUTSIDE_WRITE_FAULTS.append(f"{role} wrote outside the reviewed repo (not put back): {', '.join(paths)}")


def unreadable_note(role, session):
    """The tool_fault note of a pass whose transcript could not be read."""
    return (f"{role}: the outside-write check could not run: no readable transcript for session {session!r} "
            f"under {session_registry.projects_dir()}")


@contextlib.contextmanager
def outside_paths_on_stop(call_name, repo):
    """Around the checks that run before the outside-write stop: when one stops the run, the outside paths of the
    pass `call_name` join its message, so the blocker still names them. The error keeps its type."""
    try:
        yield
    except RuntimeError as error:
        paths = PASS_OUTSIDE_WRITES.pop(call_name, [])
        if paths:
            error.args = (f"{error} {outside_write_blocker(call_name, repo, paths)}",)
        raise


class OutsideWrites:
    def stop_on_outside_writes(self, call_name, findings, result):
        """Raises OutsideWriteError, with the findings kept open, when the pass `call_name` wrote outside the repo.
        The pass's changed files count as touched first."""
        paths = PASS_OUTSIDE_WRITES.pop(call_name, [])
        if not paths:
            return
        self.files_touched.update(result.changed)
        self.keep_unreverted_open(findings, result.reverted)
        raise OutsideWriteError(outside_write_blocker(call_name, self.repo, paths))
