"""The agent type names the gates key on. No imports: the gates load this module on every Bash and Write call,
so it must stay free of anything slow."""

# The agent the /code skill forks into (its `agent:` line). It has no Edit tool; fork_write_scope limits its Write
# calls to the run folder.
FORK_AGENT_TYPE = "code-fork"

REVIEW_LOOP_AGENT_TYPE = "review-loop"
