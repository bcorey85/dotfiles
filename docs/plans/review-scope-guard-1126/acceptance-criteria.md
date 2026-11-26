# Acceptance Criteria — review-scope-guard-1126

> Written before implementation. The closing Verify phase reconciles these
> against the test suite.

- **AC1** — A test where a fix pass edits a file outside the branch diff ends the loop with that file put back (or named in the stop packet), and a fix that changes text an AC quotes is filed as an ask, not applied.
- **AC2** — A test of the scope guard: a fix pass that writes a file outside the reviewed repo's work tree has the write reported as a blocker (or put back), and the run does not end as if the edit belonged to it.
- **AC3** — When a fix pass edits a file outside the branch diff, that file is back to its earlier content when the loop ends, or the stop packet names it.
- **AC4** — When a fix pass removes or rewords text that an acceptance criterion quotes, the loop does not keep the change: the lines that held the text come back and one ask names the criterion, the file and the text.
- **AC5** — When a fix pass removes quoted criterion text, its other edits in the same file stay applied.
- **AC6** — A fix that removes quoted criterion text, where the user already accepted that change as an ask, is applied without a new ask.
- **AC7** — A fix that removes quoted criterion text, where the user already rejected that change, stays put back and files no new ask.
- **AC8** — A fix pass that writes a file outside the reviewed repo ends the run as a blocker that names each path and says the loop did not put it back, never as a converged or clean review.
- **AC9** — A fix pass that writes to a sibling repo through a symlinked path (for example `~/.claude` pointing into the dotfiles checkout) is caught the same as a direct write.
- **AC10** — A review with no plan on disk runs as before: no criterion guard fires and no note is filed for it.

- **AC11** — A fix pass that died after writing outside the reviewed repo has each such path named in its blocker, and nothing is put back.
- **AC12** — A malformed criteria file leaves the criterion guard off for that run, the loop goes on, and the stop packet's tool_fault names the file.
- **AC13** — An unreadable coder transcript leaves a note in the stop packet's tool_fault, and the run goes on.

## Manual only

None.
