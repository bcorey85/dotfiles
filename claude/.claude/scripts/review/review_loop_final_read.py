"""review_loop_final_read.py: the reviewer reads of the last code changes no round read, as a mixin for `LoopRun`: the
fix pass the round budget ended on, and the repair passes (gate, lint, class closure, stale prose) that ran after
the last read. The host class holds out, dispatches, iter_count, last_pass, last_fix, last_review_round, open_fixes,
scoped_tests, nits and round_two_fix_diff_path, and has next_round, run_reviewers, review_scope, stop, keep_open,
tree_paths, take_review and post_cap_round."""
import script_utils
from capped_review import CAP_REACHED
from review_loop_pass_names import CLASS_FIX_PASS, GATE_FIX_PASS, LINT_FIX_PASS, PROSE_FIX_PASS
from review_loop_post_cap import FINAL_READ, SCOPED_REREVIEW

FINAL_READ_AGENT = "code-reviewer"
FINAL_DIFF_NAME = "final-fix.diff"
LATE_REPAIR_DIFF_NAME = "late-repair.diff"
LATE_REPAIR_CALLS = (GATE_FIX_PASS, LINT_FIX_PASS, CLASS_FIX_PASS, PROSE_FIX_PASS)


class FinalRead:
    # The repair passes (call name, CoderResult) after the last reviewer read, in run order. A tuple, replaced on
    # each change, so no instance shares it.
    late_repairs = ()
    # True once a read filed a fix; `apply_pending_cap` then stops the run.
    cap_pending = False

    def note_late_repair(self, call_name, result):
        """Remembers a repair pass that changed code, for the read of `read_late_repairs`."""
        if call_name not in LATE_REPAIR_CALLS or not result.changed:
            return
        self.late_repairs = (*self.late_repairs, (call_name, result))

    def read_last_fix(self, round_budget):
        """After the round budget ended on a coder pass: one code-reviewer read of that pass's diff, and no coder
        after it. Its fixes join open_fixes, which the packet prints as findings_remaining, and stop the run as
        cap-reached. Either way the last fix counts as reviewed."""
        spent = self.iter_count >= round_budget
        if not (spent and self.last_pass == "coder" and self.last_fix is not None):
            return

        self.read_diffs(FINAL_DIFF_NAME, self.last_fix.diffs, self.last_fix.changed, FINAL_READ)

    def read_late_repairs(self):
        """One code-reviewer read of the diffs of the repair passes that ran after the last read. A run that stopped
        reads nothing. When none of the changed files is in the review scope, no reviewer reads the passes, so the
        packet names them in scoped_tests and the last fix stays unreviewed."""
        if self.status != "converged" or not self.late_repairs:
            return

        names = ", ".join(name for name, _result in self.late_repairs)
        diffs = [diff for _name, result in self.late_repairs for diff in result.diffs]
        changed = [path for _name, result in self.late_repairs for path in result.changed]
        self.late_repairs = ()
        if not self.read_diffs(LATE_REPAIR_DIFF_NAME, diffs, changed, SCOPED_REREVIEW):
            unread_note = f"no reviewer read the {names} pass"
            self.scoped_tests = "; ".join(filter(None, [self.scoped_tests, unread_note]))

    def read_diffs(self, diff_name, diffs, changed, kind):
        """One code-reviewer read of `diffs`, over the changed files in the review scope, counted as a post-cap pass
        of `kind`. True when it ran. Its fixes join open_fixes and, once `apply_pending_cap` runs, stop the run as
        cap-reached; the changes count as reviewed."""
        in_scope = self.review_scope()
        owned = [path for path in dict.fromkeys(changed) if path in in_scope]
        if not owned:
            return False

        diff_file = self.out / diff_name
        script_utils.write_text_atomically(diff_file, "\n\n".join(diffs))
        self.round_two_fix_diff_path = str(diff_file)
        self.dispatches = [(FINAL_READ_AGENT, owned)]
        self.post_cap_round(kind)
        reviews = self.run_reviewers()
        dispatched = self.dispatches
        self.dispatches = []
        self.last_review_round = self.iter_count
        self.round_claimed, self.round_fixes = set(), []
        # The read takes in what a round's review does (asks, plan impacts, nits, the run row); only the fixes go to
        # no coder.
        tree_paths = self.tree_paths()
        found = []
        for (agent, agent_owned), review in zip(dispatched, reviews, strict=True):
            taken = self.take_review(agent, agent_owned, review, tree_paths)
            self.nits += taken.nits
            found += taken.fixes
        self.keep_open(found)
        self.last_pass = "reviewer"
        # The stop waits for `apply_pending_cap`, so the full check, class closure and scoped tests still run.
        if found:
            self.cap_pending = True
        return True

    def apply_pending_cap(self):
        """Stops the run as cap-reached when a read filed a fix and no later step stopped the run. Runs last in the
        walk."""
        if self.cap_pending and self.status == "converged":
            self.stop(CAP_REACHED, [])
