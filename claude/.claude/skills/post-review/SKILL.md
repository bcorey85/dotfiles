---
name: post-review
description: Post an approved set of PR review comments (review body + inline comments) to GitHub as one review. Builds the payload, validates every anchor against the PR diff, then hands the user the post command. Used by /peer-review +comment; also for "post these comments to the PR".
allowed-tools: [Bash, Read, Write]
---

# Post Review

Turns already-approved comment text into one GitHub review. This skill does not draft or judge findings — the caller (usually `/peer-review` step 7) owns that.

**The agent never posts.** `bash-safety-gate` blocks every mutating `gh api` call (`gh_api_mutate`), and `gh pr review` cannot attach inline comments. Posting is always the user's `!` command. Never wrap the call in a script, alias, or other form that slips past the gate.

## Instructions

### 1. Preconditions

- The exact text of every comment is already shown to and approved by the user. No approved text → stop and show the draft first.
- Resolve the PR number and head SHA: `gh pr view <arg> --json number,headRefOid,url`.
- Repo slug: `gh repo view --json nameWithOwner --jq .nameWithOwner`.

### 2. Build the payload

Write it with the Write tool to `<scratchpad>/review-<pr>.json` (never a shell heredoc):

```json
{
  "commit_id": "<headRefOid>",
  "event": "COMMENT",
  "body": "<review body — scope questions and anything with no single anchor line>",
  "comments": [
    { "path": "<repo-relative>", "line": 42, "side": "RIGHT", "body": "..." }
  ]
}
```

- `event`: `COMMENT` unless the user explicitly said approve or request changes.
- `line` is the head-file line number (`side: RIGHT`). Use `side: LEFT` only for comments on deleted lines (old-file numbering). For a range, add `start_line` (+ `start_side`).
- A finding whose natural line is outside every diff hunk: re-anchor it to the nearest changed line that expresses it (e.g. the caller or the UI line that shows it), or move it to `body`. Don't drop it silently.

### 3. Validate

```bash
bash "$CLAUDE_SKILL_DIR/check-anchors" <pr> <scratchpad>/review-<pr>.json
```

It checks that `commit_id` is still the PR head, that `event` is valid, and that every anchor sits on a diff line. Non-zero exit → fix the payload and re-run. A stale head means the PR was pushed since drafting: re-read the anchors at the new head and show the user any comment whose code changed.

### 4. Hand off

Give the user one command to type:

```
! gh api -X POST repos/<owner>/<repo>/pulls/<pr>/reviews --input <scratchpad>/review-<pr>.json
```

### 5. Verify

After the user runs it, confirm with GETs only:

```bash
gh api repos/<owner>/<repo>/pulls/<pr>/reviews/<review-id>/comments --jq length
```

The review id comes from the `id` in the POST response. Report the review URL (`html_url`) and whether the inline count matches the payload.
