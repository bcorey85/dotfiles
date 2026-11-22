"""Checks that every `mcp__<server>__` tool name in the toolkit names a server this toolkit knows.

The `ledger` server is read from scripts/mcp_ledger (the script that registers it). The other servers are registered
outside this repo (the Jira and Atlassian connectors, the context7 plugin), so they are listed here, once.
"""
import pathlib
import re
import tempfile
import unittest

import toolkit_paths

MCP_LEDGER_SCRIPT = toolkit_paths.REPO_ROOT / "scripts" / "mcp_ledger"
EXTERNAL_SERVERS = {"jira", "claude_ai_Atlassian", "plugin_context7_context7"}
TOOL_NAME = re.compile(r"mcp__([A-Za-z0-9_-]+?)__")
TEXT_SUFFIXES = {".md", ".json", ".sh", ".py"}


def registered_ledger_server():
    """The server name scripts/mcp_ledger registers."""
    found = re.search(r'^server_name="([^"]+)"', MCP_LEDGER_SCRIPT.read_text(), re.MULTILINE)
    if not found:
        raise AssertionError(f"{MCP_LEDGER_SCRIPT} sets no server_name")
    return found.group(1)


def named_servers(root):
    """Map each server named as mcp__<server>__ under root to the files that name it."""
    servers = {}
    for file in sorted(pathlib.Path(root).rglob("*")):
        if not file.is_file() or file.suffix not in TEXT_SUFFIXES:
            continue
        for server in set(TOOL_NAME.findall(file.read_text(errors="replace"))):
            servers.setdefault(server, []).append(str(file))
    return servers


class McpServerNames(unittest.TestCase):
    def test_every_named_server_is_known(self):
        known = EXTERNAL_SERVERS | {registered_ledger_server()}
        unknown = {s: f for s, f in named_servers(toolkit_paths.CLAUDE_DIR).items() if s not in known}
        self.assertEqual({}, unknown, f"servers this toolkit does not register: {unknown}")

    def test_old_agent_memory_name_is_flagged(self):
        with tempfile.TemporaryDirectory() as temp:
            (pathlib.Path(temp) / "SKILL.md").write_text("Call mcp__agent-memory__facts first.")
            servers = named_servers(temp)
        known = EXTERNAL_SERVERS | {registered_ledger_server()}
        self.assertEqual(["agent-memory"], [s for s in servers if s not in known])


if __name__ == "__main__":
    unittest.main()
