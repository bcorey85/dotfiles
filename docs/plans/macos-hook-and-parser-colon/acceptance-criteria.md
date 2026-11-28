# Acceptance criteria

- **AC1** — A section-format finding that ends in a colon, followed by case bullets at its indent or nested, parses as one finding holding the lead and every case, located at the lead's file:line; the next located item stays separate. (Phase 1)
- **AC2** — A tagged-bullet finding that ends in a colon, followed by untagged case bullets at its indent or nested, parses as one finding holding the lead and every case; the next tagged bullet stays separate. (Phase 1)
- **AC3** — A finding with a tilde line range (`file:~441-452`) parses whole with its path set. (Phase 1)
- **AC4** — On darwin, or any host with no systemd user scope, the foreground full-suite deny names run_in_background alone and no systemd-run command. (met on master by 6f543dd68; no change)
- **AC5** — `bash tests/run.sh` passes.
