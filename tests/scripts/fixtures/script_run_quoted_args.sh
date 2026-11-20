cd ~/agent-evals && python3 bin/build_queue.py new --by session --kind method --source "llm-verifier-playground session, /code fork report" --components "code-fork,/code skill" --description "The /code fork's final report hands the user a git commit command, which the global rule reserves for the main session." --body - "code-fork report hands user a commit command" <<'EOF'
## Context
A /code fork, finishing a small change, ended its report with "Next: read the diff, stage, then commit: `! git commit -m ...`". The global rules say only the main session hands the user a command; a subagent names the step it could not do and why. The main session here was batching many changes into one later commit, so a relayed per-fork commit line would split the history and skip the leak scan the repo requires before each commit.

## Done when
The code-fork / /code skill final-report template names the remaining git step without writing a user-facing command, and a fixture run of a /code fork shows no `! git` line in its report.
EOF
