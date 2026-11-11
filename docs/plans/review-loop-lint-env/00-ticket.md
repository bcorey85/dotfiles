# Review loop: lint every changed file, formatting-only hunks, personal gate env, re-review after resume

No Jira ticket. The source is three agent-evals queue items; their Done-when text follows verbatim.

## Acceptance

1. review-loop-lints-source-files-but-not-the-branch: The review loop's lint and format check covers every changed file in the diff, including tests, and a converged review means pre-commit's ruff hooks pass on the diff.
2. code-review-loop-gate-env-and-churn-revert-false: The gate takes test env vars from the plan's gate commands or repo config.
3. code-review-loop-gate-env-and-churn-revert-false: The removed-change guard ignores hunks whose only change is formatting.
4. code-resume-edits-reviewed-code-without-re-review: A /code resume whose feedback edits a file the converged review covered (outside notes paths) goes back to the phase review before its phase-complete stop reaches the user. A script check (code_relay.py) is preferred; a SKILL.md step needs rule-meter counts.
5. code-resume-edits-reviewed-code-without-re-review: A resume that edits only plan or notes files still keeps the commit credit.
