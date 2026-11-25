"""review_loop_post_cap.py: the loop's count of fix rounds and its post-cap passes by kind, as a mixin for `LoopRun`.
`iter` counts every pass and `review_round` is the last round a reviewer ran in; these two fields tell the reader how
many rounds were fix rounds and which passes ran after them. Standard library only. The host class has next_round."""

FINAL_READ = "final read"
CLASS_CLOSURE = "class closure"
PROSE_REPAIR = "prose repair"
SCOPED_REREVIEW = "scoped re-review"
POST_CAP_KINDS = (FINAL_READ, CLASS_CLOSURE, PROSE_REPAIR, SCOPED_REREVIEW)


def post_cap_kinds(text, separator):
    """The post-cap kinds of `text`, split on `separator`, [] for empty text. An empty or unknown kind raises
    ValueError."""
    if not text:
        return []

    kinds = text.split(separator)
    bad_kinds = [kind for kind in kinds if kind not in POST_CAP_KINDS]
    if bad_kinds:
        raise ValueError(f"holds {bad_kinds}; expected kinds from {separator.join(POST_CAP_KINDS)}, joined with "
                         f"{separator!r}")
    return kinds


class PostCapPasses:
    fix_rounds = 0
    # The kinds of the post-cap passes in run order. A tuple, replaced on each change, so no instance shares it.
    post_cap_passes = ()

    def count_fix_round(self):
        """One reviewer-and-fix round of the walk."""
        self.next_round()
        self.fix_rounds += 1

    def post_cap_round(self, kind):
        """One pass after the rounds, of `kind` (a kind constant of this module)."""
        self.next_round()
        self.post_cap_passes = (*self.post_cap_passes, kind)


def cap_summary_line(packet):
    """The cap-reached line that names the fix rounds and the post-cap passes by kind, or None for a packet written
    before the loop sent `fix_rounds`."""
    fix_rounds = packet.get("fix_rounds")
    if fix_rounds is None:
        return None

    kinds = ", ".join(packet.get("post_cap_passes") or []) or "none"
    return f"cap reached after {fix_rounds} fix round(s); post-cap passes: {kinds}"
