"""review_loop_intake.py: how the loop takes in one reviewer's findings, as a mixin for `LoopRun`. A round's review and
the final read of the last fix pass share it: the review is split, its plan impacts are routed, its row is filed and
its asks are added. The host class holds repo, skipped_fp, asks, split_review, route_plan_items, without_impact_repeats,
record_review, add_ask and without_held_findings."""
import typing

import script_utils
from review_loop_findings import plan_change_items

ABSENT_FILE_REASON = "the file is not in the tree"


class TakenReview(typing.NamedTuple):
    """fixes: the items the coder gets (a plan impact the loop adopts counts as a fix). nits: the reviewer's nits."""

    fixes: list
    nits: list


class ReviewIntake:
    def tree_paths(self):
        """Every tracked and untracked, not ignored, path of the work tree. Raises when git fails."""
        args = ("ls-files", "--cached", "--others", "--exclude-standard")
        output = script_utils.git_output(self.repo, *args)
        if output is None:
            raise RuntimeError(f"`git {' '.join(args)}` failed in {self.repo}")
        return output.splitlines()

    def take_review(self, agent, owned, review, tree_paths):
        """Takes in one reviewer's review of the files `owned`: drops what held and ruled-out files hold, splits it,
        routes its plan impacts to the coder or holds them for a ruling, files its row and adds its asks. Returns a
        TakenReview. A plan impact never stops the run."""
        review = self.without_held_findings(review)
        split = self.split_review(tree_paths, review)
        parsed, design = split.parsed, split.design
        self.skipped_fp += [{"item": item, "reason": ABSENT_FILE_REASON} for item in split.absent]

        plan_items = plan_change_items(parsed["ask"] + design)
        routed, ruling_held = self.route_plan_items(agent, plan_items)
        parsed["ask"] = [item for item in parsed["ask"] if item not in routed]
        design = [item for item in design if item not in routed]
        fixes = split.fixes + routed
        parsed["ask"] = self.without_impact_repeats(parsed["ask"], ruling_held)

        new_findings = self.record_review(agent, owned, parsed, fixes, design)
        self.add_asks_without_ruling(agent, new_findings["ask"], ruling_held)
        return TakenReview(fixes, parsed["nit"])

    def add_asks_without_ruling(self, agent, asks, ruling_held):
        """Adds each ask of a review that no plan impact holds for a ruling at the end."""
        for item in asks:
            if item not in ruling_held:
                self.add_ask(agent, item)
