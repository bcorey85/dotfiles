# Research Questions

1. How are session records stored and looked up under `~/.claude/sessions`, and what do `session_registry.py` and `session_id_of_name` do with a name or id? Where are the `--relayed-by` flags of `decide` and `asks-done` parsed, and what do they write to the entry and the relayed row?
2. What state does the review loop keep between runs (approval asks, rulings, outcomes), and where are the files, keys and writers defined? How is an ask's accepted or rejected outcome stored and read back?
3. How does `phase_asks.py` classify an ask as user_only, and how does its `rule` command treat the `accepted` and `rejected` outcomes, the `--by` value and the requirement to rule all asks in one call? Where are the tests for it?
4. How does the review loop take in a reviewer's findings (`review_loop_intake.py`) and compare them with asks already ruled on earlier runs of the same branch? What happens to a finding that matches a prior ruling?
5. How does a resumed review loop carry saved asks and their ruling text into a fix pass, and what checks run on the fix pass's diff afterwards (`review_loop_pass_checks.py`, `review_loop_final_read.py`, `review_loop_scope_guard.py`, `review_loop_ruled_out.py`)? What happens when a pass changes code that a ruling named?
6. How does the review loop count rounds and the cap, and which passes follow the cap (final read, class closure, scoped re-review)? Where do `review_round`, the packet text and the stop file text ("cap-reached") get their values?
7. How does the loop name and request reviewer reports for each round, and how does a round-N exit line tell the forking session which reviewers to dispatch? What happens when reports under a round's names never arrive?
8. How does a stop file print its resume line, including the `--by` value, and how does it decide between a user and a session as the ruler for a lane session?
9. How does the /code step handle a resume of a plan with feedback or a fix list: where is the decision to dispatch or skip the phase review loop made, and what does it read (diff, phase state, brief)? Where are the code-step tests?
10. What test patterns exist for the review loop and `phase_asks.py` under `tests/scripts/`? Where are the fixtures, path helpers (`toolkit_paths.py`) and the harnesses that drive a loop through several rounds?

## Exploration Map

- `claude/.claude/scripts/review/` — review loop, hand-back, packet and stop text, intake and pass checks
- `claude/.claude/scripts/code/` — plan check, phase asks, code-step helpers
- `claude/.claude/scripts/lib/` — session registry, shared modules for rulings and sign-offs
- `claude/.claude/scripts/tools/` — small commands such as `decide` and `asks-done`
- `claude/.claude/skills/` — /code and /review skill steps that dispatch the loop and the resume path
- `tests/scripts/` — existing tests, fixtures and `toolkit_paths.py`
