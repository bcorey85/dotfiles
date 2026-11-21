"""review_loop_intake.py: how the loop takes in one reviewer's findings, as a mixin for `LoopRun`. A round's review and
the final read of the last fix pass share it: the review is split, its plan impacts are routed, its row is filed and
its asks are added. The host class holds repo, skipped_fp, asks, split_review, route_plan_items, without_impact_repeats,
record_review, add_ask and without_held_findings."""
import typing

import script_utils
from review_loop_docs_kind import docs_kind
from review_loop_findings import UNLOCATED, near_title, plan_change_items

ABSENT_FILE_REASON = "the file is not in the tree"


def new_spot(path, title, entries):
    """The spot of a new finding: the file and title with the lowest `#n` ordinal no entry holds. A refile rewrites an
    earlier entry's title but keeps its spot, so the ordinal is checked against spots, not titles."""
    taken = {entry["spot"] for entry in entries}
    number = 1
    while f"{path}\0{title}#{number}" in taken:
        number += 1
    return f"{path}\0{title}#{number}"


def tally_review(tallies, findings, assessment):
    """Adds one review's new findings ({disposition: [finding records]}) to the metrics tallies, so a finding refiled
    in a later round counts once."""
    tallies["fix"] += len(findings["fix"])
    tallies["ask"] += len(findings["ask"])
    tallies["nit"] += len(findings["nit"])
    tallies["blocker"] += sum("[blocker]" in item.text.lower() for item in findings["fix"])
    every_finding = findings["fix"] + findings["ask"] + findings["nit"]
    tallies["smells"] += sum(item.finding_class == "smell" for item in every_finding)
    if assessment == "NEEDS CHANGES":
        tallies["result"] = "NEEDS CHANGES"
    elif assessment and tallies["result"] == "PASS":
        tallies["result"] = assessment


class TakenReview(typing.NamedTuple):
    """fixes: the items the coder gets (a plan impact the loop adopts counts as a fix). nits: the reviewer's nits."""

    fixes: list
    nits: list


class ReviewIntake:
    def tree_paths(self):
        """Every tracked and untracked, not ignored, path of the work tree. Raises when git fails."""
        paths = script_utils.repo_file_paths(self.repo)
        if paths is None:
            raise RuntimeError(f"`git ls-files --cached --others --exclude-standard` failed in {self.repo}")
        return paths

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

    def earlier_filing(self, entries, finding):
        """The entry from an earlier round that this finding refiles: not yet claimed this round, with the same
        disposition and a near title. None when it is new."""
        return next((entry for entry in entries if id(entry) not in self.round_claimed
                     and entry["disposition"] == finding["disposition"]
                     and near_title(entry["title"], finding["title"])), None)

    def ask_already_filed(self, ask):
        """Whether another reviewer already asked this text, so it stays one ask and files no second finding."""
        if ask in self.asks:
            return True
        for entries in self.filed.values():
            if any(entry["disposition"] == "ask" and entry["finding"] == ask for entry in entries):
                return True
        return False

    def filing_row(self, agent, owned, parsed, fixes, design):
        """The run row of one review. A fix starts `actioned: none`; fix_round sets it once the coder returns. A
        finding this reviewer filed in an earlier round, in the same file with the same disposition and the same or
        near title, updates that round's entry and stays off this row, wherever its line moved."""
        reported = [{"finding": item, "disposition": "fix", "actioned": "none", "source": "round"} for item in fixes]
        reported += [{"finding": item, "disposition": "ask", "actioned": "ask", "source": ""}
                     for item in parsed["ask"] + design]
        reported += [{"finding": item, "disposition": "nit", "actioned": "none", "source": ""}
                     for item in parsed["nit"]]

        findings = []
        for finding in reported:
            self.file_finding(agent, finding, findings)

        loc = sum(self.files[path][0] for path in owned if path in self.files)
        return {"iter": self.iter_count, "gate": agent, "loc": loc, "result": parsed["assessment"] or "PASS",
                "findings": findings}

    def file_finding(self, agent, finding, findings):
        """Files one reported finding. A refiling updates its earlier entry; a new finding gets a spot and joins
        `findings`, the run row's list; an ask another reviewer already filed is dropped."""
        path = finding["finding"].path or UNLOCATED
        finding["title"] = finding["finding"].title
        entries = self.filed.setdefault((agent, path), [])
        earlier = self.earlier_filing(entries, finding)
        if earlier:
            self.refile(earlier, finding)
            filed = earlier
        elif finding["disposition"] == "ask" and self.ask_already_filed(finding["finding"]):
            return
        else:
            finding["spot"] = new_spot(path, finding["title"], entries)
            finding["docs_kind"] = docs_kind(self.repo, self.docs_added, finding["finding"])
            entries.append(finding)
            findings.append(finding)
            filed = finding
        self.round_claimed.add(id(filed))
        if filed["disposition"] == "fix":
            self.round_fixes.append(filed)

    def refile(self, earlier, finding):
        """Updates an earlier round's entry from the same finding filed again, keeping its spot. The label is set
        again from this round's diff, class and line."""
        finding["spot"] = earlier["spot"]
        if finding["disposition"] == "ask":
            finding["finding"] = earlier["finding"]
        finding["docs_kind"] = docs_kind(self.repo, self.docs_added, finding["finding"])
        earlier.update(finding)

    def record_review(self, agent, owned, parsed, fixes, design):
        """Files one review's row, tallies its new findings and returns them by disposition."""
        row = self.filing_row(agent, owned, parsed, fixes, design)
        new_findings = {}
        for disposition in ("fix", "ask", "nit"):
            new_findings[disposition] = [finding["finding"] for finding in row["findings"]
                                         if finding["disposition"] == disposition]
        tally_review(self.tallies, new_findings, parsed["assessment"])
        self.run_rows.append(row)
        return new_findings
