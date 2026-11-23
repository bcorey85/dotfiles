"""Checks that every `mcp__<server>__` tool name in the toolkit names a server this toolkit knows.

The `ledger` server is read from scripts/mcp_ledger (the script that registers it). The other servers are registered
outside this repo (the Jira and Atlassian connectors, the context7 plugin), so they are listed here, once.
"""
import pathlib
import re
import subprocess
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


def tracked_files(root):
    """The files git tracks under root: caches, plugins and synced skills are untracked downloads."""
    listing = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--full-name", "--", "."],
                             capture_output=True, text=True, check=True).stdout
    top = subprocess.run(["git", "-C", str(root), "rev-parse", "--show-toplevel"],
                         capture_output=True, text=True, check=True).stdout.strip()
    return [pathlib.Path(top) / name for name in sorted(listing.split("\0")) if name]


def named_servers(root):
    """Map each server named as mcp__<server>__ in a git-tracked file under root to the files that name it."""
    servers = {}
    for file in tracked_files(root):
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

    def make_repo(self, temp):
        subprocess.run(["git", "-C", temp, "init", "-q"], check=True)
        return pathlib.Path(temp)

    def test_old_agent_memory_name_is_flagged(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = self.make_repo(temp)
            (repo / "SKILL.md").write_text("Call mcp__agent-memory__facts first.")
            subprocess.run(["git", "-C", temp, "add", "SKILL.md"], check=True)
            servers = named_servers(temp)
        known = EXTERNAL_SERVERS | {registered_ledger_server()}
        self.assertEqual(["agent-memory"], [s for s in servers if s not in known])

    def test_untracked_cache_and_plugin_files_are_ignored(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = self.make_repo(temp)
            (repo / "SKILL.md").write_text("Call mcp__ledger__facts first.")
            for folder in ("cache", "plugins", "skills/synced"):
                (repo / folder).mkdir(parents=True)
                (repo / folder / "x.md").write_text("mcp__thirdparty__tool")
            subprocess.run(["git", "-C", temp, "add", "SKILL.md"], check=True)
            servers = named_servers(temp)
        self.assertEqual(["ledger"], list(servers))


if __name__ == "__main__":
    unittest.main()
