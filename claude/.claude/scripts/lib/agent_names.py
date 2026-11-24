"""The names of the agent types the toolkit tells apart. No imports: the gates load this module on every Bash call, so
it must stay free of anything slow."""

# The agent the /code skill forks into (its `agent:` line). It has no Edit or Write tool.
FORK_AGENT_TYPE = "code-fork"
