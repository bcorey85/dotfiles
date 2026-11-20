"""review_loop_pass_checks.py: the LoopRun methods that judge a coder pass's result against the plan's
later phases and the size of the change under review."""
import change_removal
import script_utils


class LaterPhaseEditError(RuntimeError):
    """A coder pass that edited a file the plan gives to a later phase."""


class ChangeRemovedError(RuntimeError):
    """A coder pass that removed half or more of the lines the change under review adds. The message is the blocker."""


class PassChecks:
    """The LoopRun methods that check what a coder pass changed."""

    def check_pass_result(self, call_name, result):
        """Raises LaterPhaseEditError when the pass edited a later-phase file, ChangeRemovedError when the passes so
        far removed half or more of the lines the change adds."""
        later_phase_edits = sorted(set(result.changed) & self.later_phase_files)
        if later_phase_edits:
            self.files_touched.update(result.changed)
            raise LaterPhaseEditError(f"{call_name} edited files the plan gives to a later phase: "
                                      + ", ".join(later_phase_edits))

        removed, written = self.change.removal()
        if change_removal.is_gutted(self.change.added, removed, written):
            self.files_touched.update(result.changed)
            raise ChangeRemovedError(change_removal.removal_blocker(self.change.added, removed, written))

        self.note_late_repair(call_name, result)

    def keep_coder_commit_in_scope(self):
        """When a coder pass committed and the review diffs against HEAD, the review diffs against the commit HEAD
        named when the loop started from then on, so the committed fix and the change stay under review."""
        if self.review_base:
            return
        start = self.change.start
        if start is None or script_utils.head_commit(self.repo) == start:
            return
        self.review_base = start
