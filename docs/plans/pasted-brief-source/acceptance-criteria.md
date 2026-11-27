# Acceptance criteria

- **AC1** — `plan_check.py owner` prints owner `session`, with the path as source, for a ticket that names an existing session-written `~/agent-evals/queue/<slug>.md` path anywhere in its text, in either the `~` or the home-folder spelling. (Phase 1)
- **AC2** — A ticket that names no queue path, or only a queue path whose file does not exist, keeps owner `user`; a ticket that names a `human:`-written queue item keeps owner `user`. (Phase 1)
- **AC3** — `bash tests/run.sh` passes. (Phase 1)
