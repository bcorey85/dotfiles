/**
 * Protected Paths Extension
 *
 * Blocks read, write, and edit operations on sensitive files.
 * Silently blocks every time — no prompts.
 * If you need to access a protected file, use your terminal directly.
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export default function (pi: ExtensionAPI) {
	// Paths that are always protected (glob-style patterns)
	const protectedPatterns = [
		// SSH keys
		"~/.ssh/",
		"~/.ssh/*",
		// Cloud credentials
		"~/.aws/",
		"~/.aws/*",
		"~/.kube/",
		"~/.kube/*",
		"~/.config/gcloud/*",
		"~/.gcloud/*",
		"~/.azure/*",
		"~/.docker/config.json",
		// GPG
		"~/.gnupg/*",
		// Git credentials
		"~/.git-credentials",
		// Local overrides (secrets not in dotfiles repo)
		"~/.zshrc.local",
		"~/.gitconfig.local",
		"~/.env",
		"~/.envrc",
		// Certificates
		"~/*.pem",
		"~/*.key",
		"~/*.p12",
		// Pi/auth
		"~/.pi/agent/auth.json",
		"~/.pi/agent/.credentials.json",
		// Claude/OpenCode settings (managed by stow)
		"~/.claude/settings.json",
		"~/.claude/settings.local.json",
		"~/.config/opencode/opencode.json",
		"~/.config/opencode/opencode.jsonc",
	];

	function expandHome(pattern: string): string {
		return pattern.replace(/^~/, process.env.HOME || "");
	}

	function isProtected(filePath: string): boolean {
		const expanded = filePath.startsWith("~") ? filePath : filePath;
		const resolved = expanded.replace(/^~/, process.env.HOME || "");

		return protectedPatterns.some((pattern) => {
			const expandedPattern = expandHome(pattern);

			// Exact match or starts with directory prefix
			if (expandedPattern.endsWith("/*")) {
				const dir = expandedPattern.slice(0, -2);
				return resolved.startsWith(dir);
			}

			// Wildcard match for extensions
			if (expandedPattern.includes("*.")) {
				const [prefix, ext] = expandedPattern.split("*.");
				return resolved.startsWith(prefix) && resolved.endsWith("." + ext);
			}

			// Directory prefix
			if (expandedPattern.endsWith("/")) {
				return resolved.startsWith(expandedPattern);
			}

			// Exact match
			return resolved === expandedPattern;
		});
	}

	// Block reads on protected paths — always, no prompt
	pi.on("tool_call", async (event) => {
		if (event.toolName === "read") {
			const path = event.input.path as string;
			if (isProtected(path)) {
				return {
					block: true,
					reason: `Read blocked: "${path}" is protected. Use a local terminal to access this file.`,
				};
			}
			return undefined;
		}

		// Block writes/edits on protected paths — always, no prompt
		if (event.toolName === "write" || event.toolName === "edit") {
			const path = event.input.path as string;
			if (isProtected(path)) {
				return {
					block: true,
					reason: `Write blocked: "${path}" is protected.`,
				};
			}
			return undefined;
		}

		return undefined;
	});
}
