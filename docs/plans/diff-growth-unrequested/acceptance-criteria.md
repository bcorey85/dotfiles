# Acceptance criteria

Owner: session (queue item close-pass-and-fix-add-docs-and-tests-nobody-asked).

- **AC1** — `concentration.py <base>` prints `Diff split:` with the added lines of docs, tests and code and each part's share of the branch; a test file counts as tests, a Markdown file or a file under a docs folder counts as docs, and a lockfile or generated file counts nowhere. (Phase 1)
- **AC2** — On a branch of at least 300 added lines whose docs or tests part is over 40%, the line says `OVERSIZED:` and names that part; under either bar it says `No part over 40%.` (Phase 1)
- **AC3** — The code reviewer has a rule that a new doc file or test module that no plan step, criterion or finding asks for is a `fix` finding to cut it, and so is a doc that repeats a sibling doc or the code; a rule-meter scenario runs its on and off arms, or the change file marks it `unmeasured`. (lane, direct edit)
- **AC4** — The close-branch skill keeps the split line for the recap, and an `OVERSIZED:` part is a finding for its fix step. (lane, direct edit)
- **AC5** — `bash tests/run.sh` passes.
