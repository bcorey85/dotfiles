# Team Merge Digest

> Nightly agent that compiles the team's merged PRs into a risk-tagged, system-level digest note in the vault — replacing read-every-hunk review with a ten-minute morning map read.

## Context

Lead is drowning in review load and holds a "must read every diff to keep my
mental model" habit that stopped scaling. The digest mechanizes the one thing
that habit actually provides — a recency index ("something touched the retry
logic last Tuesday") — without the reading load. Came out of the same session
that built the note → daily-recap → vault-review pipeline; this is the first
extension slated for after the two-week feature freeze on that system.

## Proposal

- Nightly headless run (same scheduler pattern as `install/daily-recap`:
  launchd on the work Mac, `claude -p` with a minimal tool allowlist).
- For a **configured list of team repos** (config file, per-machine — do not
  hardcode in the skill), pull every PR merged since the last run via `gh`.
- Per PR, a two-line **system-level** summary: what changed in architecture
  terms and why — from the PR description plus a look at the diff, not a
  title restatement.
- **Risk-tag** PRs touching migrations, auth/permissions, public contracts,
  concurrency, or deleted guards/code — these are the deep-read candidates.
- Output `<vault>/Digest/<date>.md`: flagged PRs first, each with a one-line
  "why you should look"; everything else one line each.
- Morning workflow: read digest with coffee, deep-read only flagged or
  surprising entries.
- Compounding: digests accumulate in the vault, so `/vault-ask` can answer
  "when did the export service last change, who touched it" at incident time.

## Open questions

- Repo list source: dotfiles-local config file vs `gh` org query with an
  exclude list?
- Same 18:00 LaunchAgent run as daily-recap or a separate earlier one (digest
  is a morning read; compiling at 07:00 catches overnight merges)?
- Diff-reading depth per PR: description-only for small PRs vs full diff fetch
  — token cost vs summary quality; maybe size-gated.
- Cross-links: should the daily recap's "My work" section link to the digest
  entries for PRs the user reviewed?

## References

- Existing pieces this builds on: `install/daily-recap`,
  `claude/.claude/skills/daily-recap/`, `claude/.claude/skills/vault-ask/`
- Related backlog (same session, not yet captured): person-index for 1:1s,
  mobile capture, promotion-loop closure
