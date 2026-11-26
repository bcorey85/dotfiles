# Review loop put-back and intake defects, batch of 2026-11-25

Source: ~/agent-evals/queue/review-loop-put-back-reverts-files-a-fix-coder.md
Source: ~/agent-evals/queue/review-loop-put-back-restores-comment-deletions-a.md
Source: ~/agent-evals/queue/review-loop-cannot-find-files-with-a-dollar-sign.md
Source: ~/agent-evals/queue/review-loop-drops-a-round-s-reviewer-findings-when.md
Source: ~/agent-evals/queue/packet-adopts-code-wins-over-a-recorded-user.md

## 1. review-loop-put-back-reverts-files-a-fix-coder

### Context
In a /code phase review loop, a fix coder edited a file that no finding named, because the fix could not work without it (it defined a function the finding's file called). The loop's out-of-scope put-back reverted that file and reported only "out of scope". The same put-back also undid fixes from earlier rounds in files no current finding named. The result was a broken typecheck and failing tests that the next round blamed on the code, and the loop stopped at its round cap on a blocker it had created.

### Done when
- Put-back never reverts a hunk an earlier round's accepted fix wrote.
- A file a fix coder edits outside the named files is kept when the gate passes with it and fails without it; otherwise the loop stops and names the file and why, instead of reverting silently.
- The loop's report lists every reverted file and where its bytes were saved.

## 2. review-loop-put-back-restores-comment-deletions-a

### Context
A /fix run was handed an audit list of comments to delete or shorten. The fix pass removed them. The put-back step then restored nine of them as "removed with no finding naming them" and held each one as a user ask. A finding in the same run named every one of them, and those findings still showed as remaining. The match probably missed because earlier edits in the same file had moved the line numbers.

### Done when
- Put-back matches a removed comment against findings by file and content, not only by line.
- A test covers a finding that names a comment whose line moved before the fix pass ran.

## 3. review-loop-cannot-find-files-with-a-dollar-sign

### Context
The review loop reported a changed test file as not in the tree. The file exists; its name starts with a dollar sign (a TanStack route param file). A reviewer finding on that file was then dropped.

### Done when
The review loop reads and applies findings on files whose paths hold `$`, with a test using such a path.

## 4. review-loop-drops-a-round-s-reviewer-findings-when

### Context
A review round returned NEEDS CHANGES with a blocker and two fixes. The next fix round ran only lint, full-check and class-closure coders. None of their briefs held the reviewer's findings. The following re-review prompt listed the round before as all fixed, and its scope named two files only. So the blocker was never sent to a coder, and the loop went on toward convergence.
A second issue: the orchestrator ran code_wait on an older background output and re-dispatched a stale review round. The loop gives no sign that a review round is already used up.

### Done when
- Every finding in a reviewer report ends in a coder brief or in an ask, before the next review round is built.
- A dispatch for a review round already used is refused with a clear message.

## 5. packet-adopts-code-wins-over-a-recorded-user

### Context
A reviewer flagged that a new decision-log line (a user ruling) was not yet reflected in the code, and asked whether the user gave it. The packet step adopted it by rule as "no acceptance criterion changes, so the code wins: the plan follows the code" and told the session to log that under Plan Deviations, while the same packet listed the matching code change as an open ask. Following it would have recorded the reverse of what the user ruled.

### Done when
A plan impact whose plan side is a dated user ruling in the decision log is routed as an ask (or as code to change), never adopted as code-wins; a test packet with such a finding shows no Plan Deviations line for it.
