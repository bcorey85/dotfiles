"""The review loop's later-round steps: the fixes held back past the first review pass, the fixes that need new code
and the new code a coder added against its rule. LoopRun inherits LaterRoundSteps."""

import pathlib
import sys

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(SCRIPT_DIR.parent / folder) for folder in (".", "review", "code", "lib")]
from finding_record import merged_from, parse_finding
from review_loop_findings import later_round_split, merge_findings
from source_text import new_code_in

LATER_ROUND_SOURCE = "later-round"
ASK_ROW_FIELDS = {"disposition": "ask", "actioned": "ask", "source": ""}


def new_spot(path, title, entries):
    """The spot of a new finding: the file and title with the lowest `#n` ordinal no entry holds. A refile rewrites an
    earlier entry's title but keeps its spot, so the ordinal is checked against spots, not titles."""
    taken = {entry["spot"] for entry in entries}
    number = 1
    while f"{path}\0{title}#{number}" in taken:
        number += 1
    return f"{path}\0{title}#{number}"


def append_entry(entries, path, entry):
    """Files a new ledger entry: gives it the next free spot for its file and title and adds it to the entries."""
    entry["spot"] = new_spot(path, entry["title"], entries)
    entries.append(entry)


class LaterRoundSteps:
    """The later-round steps of a LoopRun. The host sets iter_count, fixed, open_fixes, round_fixes, run_rows, filed
    and tallies, and provides add_ask(agent, item) and reopen_fixed(open_findings)."""

    def init_later_round_state(self):
        self.fix_lines = {}  # {path: the line numbers the last coder pass changed}

    def defer_later_round_fixes(self, round_fix):
        """Past the first round, the fixes that neither block, name a bug, correctness or security defect, nor clean up
        the last fix go to the open fixes, unfixed. Returns round_fix without them."""
        if self.iter_count == 1:
            return round_fix

        kept_round_fix = []
        for agent, fixes in round_fix:
            kept, deferred = later_round_split(fixes, self.fix_lines, self.fixed)
            kept_round_fix.append((agent, kept))
            self.open_fixes = merge_findings(self.open_fixes + deferred)
            for entry in self.round_fixes:
                if entry["finding"] in deferred:
                    entry.update(actioned="deferred", source=LATER_ROUND_SOURCE)
        self.round_fixes = [entry for entry in self.round_fixes if entry["actioned"] != "deferred"]
        self.reopen_fixed(self.open_fixes)
        return kept_round_fix

    def hold_new_code_fix(self, held_fix, need):
        """A fix that needs new code past the first round goes to the user as an ask, not to a coder. The ask keeps
        the gate of the review that filed the fix."""
        ask = parse_finding(f"{held_fix.text} \N{EM DASH} the fix needs new code after the first review pass: {need}")
        ask_filed = False
        for row in self.run_rows:
            for entry in list(row["findings"]):
                if entry not in self.round_fixes or not merged_from(entry["finding"], held_fix):
                    continue

                self.tallies["fix"] -= 1
                if ask_filed:
                    row["findings"].remove(entry)
                    continue

                self.add_ask(row["gate"], ask)
                entry.update(finding=ask, **ASK_ROW_FIELDS)
                self.tallies["ask"] += 1
                ask_filed = True

    def ask_about_added_code(self, coder_diffs):
        """New code a coder added against its rule stays in the tree and goes to the user as an ask."""
        gate = self.run_rows[-1]["gate"]
        for path, line, name in new_code_in(coder_diffs):
            ask = parse_finding(f"`{path}:{line}` [complexity] The fix added `{name}` after the first review pass. "
                                f"Keep it? \N{EM DASH} change: remove `{name}` and fix the issue in the existing code.")
            self.add_ask(gate, ask)
            self.tallies["ask"] += 1
            entries = self.filed.setdefault((gate, path), [])
            entry = {"finding": ask, **ASK_ROW_FIELDS, "title": ask.title}
            append_entry(entries, path, entry)
            self.run_rows[-1]["findings"].append(entry)
