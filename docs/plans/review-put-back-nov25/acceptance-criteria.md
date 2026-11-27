# Acceptance Criteria — review-put-back-nov25

> Written before implementation. The closing verify reconciles these against the test suite.

Ticket ACs are copied verbatim from the queue items' Done-when (AC1-AC10). AC11 onward are behaviors observable from the ticket's contexts.

- **AC1** — Put-back never reverts a hunk an earlier round's accepted fix wrote.
- **AC2** — A file a fix coder edits outside the named files is kept when the gate passes with it and fails without it; otherwise the loop stops and names the file and why, instead of reverting silently.
- **AC3** — The loop's report lists every reverted file and where its bytes were saved.
- **AC4** — Put-back matches a removed comment against findings by file and content, not only by line.
- **AC5** — A test covers a finding that names a comment whose line moved before the fix pass ran.
- **AC6** — The review loop reads and applies findings on files whose paths hold `$`, with a test using such a path.
- **AC7** — Every finding in a reviewer report ends in a coder brief or in an ask, before the next review round is built.
- **AC8** — A dispatch for a review round already used is refused with a clear message.
- **AC9** — A plan impact whose plan side is a dated user ruling in the decision log is routed as an ask (or as code to change), never adopted as code-wins.
- **AC10** — A test packet with such a finding shows no Plan Deviations line for it.
- **AC11** — Each of the five defects has a test in tests/scripts that fails on the tree at 832ce08b4 and passes after its phase.
- **AC12** — A comment removal that no finding names by line, span or content is still put back and held as an ask, as before.
- **AC13** — A path with no `$` parses to the same file and line as before the change (no existing finding-path test changes its expectation).
- **AC14** — A plan impact that changes no criterion and cites no user ruling in the decision log is still adopted by rule with its Plan Deviations line.
