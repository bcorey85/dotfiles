---
type: "Change"
change_type: "fixed"
title: "Install flags any script it left unlinked, and a test ties herdr-phase-change's /code verbs to the code skill"
description: "install/stow now ends by running install/check-script-links, which names every script in scripts/.local/bin that ~/.local/bin does not link to the file itself and exits 1 if any is left. A new test also fails when the /code verbs herdr-phase-change keeps as given differ from the verbs step 1 of the code skill names. Before, a script added after the last restow, herdr-phase-change, stayed unlinked with nothing reporting it, and the two verb lists could drift apart unseen."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-30T05:00:33-05:00"}
seq: 323
kind: "fix"
components: ["script/install-stow", "script/herdr-phase-change"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_check_script_links.py::CheckScriptLinksTest::test_a_missing_script_is_named_and_fails"
asked: ""
proof: []
unmeasured: ""
---

## Change

- New `install/check-script-links`: for each file in `scripts/.local/bin` it checks that `~/.local/bin/<name>` exists and resolves to that file. It prints each script that is not linked with a hint to rerun `install/stow`, and exits 1; when all are linked it prints one line and exits 0.
- `install/stow` runs it after "Symlinks created", finishes its macOS steps, then exits 1 when a script is unlinked, so a fresh install fails loudly.
- `tests/scripts/test_herdr_phase_change.py`: a test reads the verb list in `herdr-phase-change`'s case statement and the backticked verbs in step 1 of the code skill, and fails when the two sets differ.

## Evidence

- `herdr-phase-change` was in `scripts/.local/bin` but not linked from `~/.local/bin`, while its siblings were. `stow -R scripts` links every file, so the gap came from no restow after the script was added, and nothing reported it.
- The new link test fails before the change: `install/check-script-links` does not exist.

## Result

- `tests/scripts/test_check_script_links.py` passes: all scripts linked exits 0; one missing link exits 1 and names the script; an entry that points elsewhere or dangles is flagged; relative links and a stow-folded directory pass.
- The verb-list test in `tests/scripts/test_herdr_phase_change.py` passes against the current files, and fails when either list gains or loses a verb.

## Watch

None. The check runs inside install and prints its result there; no intake number reads it.

## Back-out

Revert the commit. `install/stow` stops checking links, and a script left unlinked goes unreported again.
