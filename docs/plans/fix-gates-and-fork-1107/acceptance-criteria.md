# Acceptance Criteria — fix-gates-and-fork-1107

> Written before implementation.

- **AC1** — The comment-bloat-gate marker deny names the matched marker text next to each line it lists.
- **AC2** — The staged-claim Stop gate passes a closing question that files tickets (`sub-tickets`, `subtasks`, or a file/open/create/raise verb with a pronoun object and then Jira, Linear or GitHub, as in `file them in Jira`), and still blocks a question about a local, reversible step.
- **AC3** — git-discipline-gate passes `git -C <repo> pull --rebase=merges --autostash && git -C <repo> push`, and still denies a lone `pull --autostash`, a pull whose next git call is not a push in the same directory, `rebase`/`merge --autostash`, and autostash config.
- **AC4** — The /code skill tells its caller to cancel a fork with a `stop` message, and the code-fork agent stops every agent it dispatched and names them in its stop.
- **AC5** — The /code sign-off rule covers ticket ACs and eng-spec criteria; a queue-item done-clause criterion changes on an orchestrator ruling recorded in the queue item or brief, logged under `## Plan Deviations`.
- **AC6** — `bash tests/run.sh` passes.
