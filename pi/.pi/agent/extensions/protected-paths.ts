/**
 * Protected Paths Extension
 *
 * Blocks read, write, and edit operations on sensitive files.
 * Rules extracted from Claude Code's bash-safety-gate, block-credential-read,
 * and write-edit-safety-gate hooks.
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export default function (pi: ExtensionAPI) {
	// Path patterns — checked against resolved absolute paths
	const protectedPatterns: { pattern: string; label: string }[] = [
		// === SSH & TLS ===
		{ pattern: "**/.ssh/*", label: "SSH" },
		{ pattern: "**/*.pem", label: "TLS key" },
		{ pattern: "**/*.key", label: "TLS key" },
		{ pattern: "**/*.p12", label: "TLS key" },
		{ pattern: "**/*.pfx", label: "TLS key" },

		// === Cloud credentials ===
		{ pattern: "**/.aws/credentials", label: "AWS credentials" },
		{ pattern: "**/.aws/config", label: "AWS config" },
		{ pattern: "**/.kube/config", label: "Kube config" },
		{ pattern: "**/.kube/*", label: "Kube config" },
		{ pattern: "**/.config/gcloud/*", label: "GCP credentials" },
		{ pattern: "**/.gcloud/*", label: "GCP credentials" },
		{ pattern: "**/.azure/*", label: "Azure credentials" },
		{ pattern: "**/.docker/config.json", label: "Docker config" },
		{ pattern: "**/*credentials.json", label: "Cloud credentials" },
		{ pattern: "**/*service_account.json", label: "Service account" },
		{ pattern: "**/*application_default_credentials.json", label: "GCP ADC" },

		// === Package manager credentials ===
		{ pattern: "**/.npmrc", label: "npm config" },
		{ pattern: "**/.pypirc", label: "PyPI config" },
		{ pattern: "**/.gem/credentials", label: "Gem credentials" },
		{ pattern: "**/.nuget/NuGet.Config", label: "NuGet config" },

		// === Git ===
		{ pattern: "**/.git-credentials", label: "Git credentials" },
		{ pattern: "**/.gitconfig.local", label: "Git local config" },

		// === GPG ===
		{ pattern: "**/.gnupg/*", label: "GPG keyring" },

		// === Environment / secrets ===
		{ pattern: "**/.env", label: ".env file" },
		{ pattern: "**/.envrc", label: ".envrc file" },
		{ pattern: "**/.env.*", label: ".env file" },
		{ pattern: "*.env", label: ".env file" },

		// === Misc credentials ===
		{ pattern: "**/.netrc", label: ".netrc" },
		{ pattern: "**/.boto", label: "boto config" },
		{ pattern: "**/.s3cfg", label: "s3cfg" },
		{ pattern: "**/.vault-token", label: "Vault token" },
		{ pattern: "**/.htpasswd", label: "htpasswd" },
		{ pattern: "**/.dev.vars", label: "dev vars" },
		{ pattern: "**/token.json", label: "token file" },

		// === Shell history ===
		{ pattern: "**/.bash_history", label: "bash history" },
		{ pattern: "**/.zsh_history", label: "zsh history" },
		{ pattern: "**/.sh_history", label: "sh history" },

		// === GitHub CLI ===
		{ pattern: "**/.config/gh/hosts.yml", label: "gh auth config" },

		// === Terraform ===
		{ pattern: "**/*.tfstate", label: "Terraform state" },
		{ pattern: "**/*.tfstate.*", label: "Terraform state" },

		// === Local overrides (secrets not in dotfiles repo) ===
		{ pattern: "~/.zshrc.local", label: "Local zshrc" },
		{ pattern: "~/.gitconfig.local", label: "Local gitconfig" },

		// === Harness configs ===
		{ pattern: "~/.pi/agent/auth.json", label: "Pi auth" },
		{ pattern: "~/.claude/settings.json", label: "Claude settings" },
		{ pattern: "~/.claude/settings.local.json", label: "Claude local settings" },
		{ pattern: "~/.config/opencode/opencode.json", label: "OpenCode config" },
		{ pattern: "~/.config/opencode/opencode.jsonc", label: "OpenCode config" },
	];

	function matchPattern(filePath: string, pattern: string): boolean {
		const home = process.env.HOME || "";
		const resolved = filePath.replace(/^~/, home);
		const normPattern = pattern.replace(/^~/, home);

		// **/.ssh/* — match any path containing .ssh/ and anything after
		if (normPattern.startsWith("**/")) {
			const suffix = normPattern.slice(3); // e.g. ".ssh/*"
			if (suffix.endsWith("/*")) {
				const dir = suffix.slice(0, -2);
				return resolved.includes("/" + dir);
			}
			if (suffix.endsWith("*")) {
				const prefix = suffix.slice(0, -1);
				return resolved.includes("/" + prefix);
			}
			return resolved.includes("/" + suffix);
		}

		// Wildcard extension match
		if (normPattern.includes("*.")) {
			const [prefix, ext] = normPattern.split("*.");
			if (prefix.endsWith("/")) {
				return resolved.startsWith(prefix) && resolved.endsWith("." + ext);
			}
			return resolved.includes(prefix) && resolved.endsWith("." + ext);
		}

		// Directory prefix
		if (normPattern.endsWith("/")) {
			return resolved.startsWith(normPattern);
		}

		// Exact match
		return resolved === normPattern;
	}

	function isProtected(filePath: string): string | null {
		for (const { pattern, label } of protectedPatterns) {
			if (matchPattern(filePath, pattern)) {
				return label;
			}
		}
		return null;
	}

	// Block tool calls
	pi.on("tool_call", async (event) => {
		if (event.toolName === "read" || event.toolName === "write" || event.toolName === "edit") {
			const path = event.input.path as string;
			const label = isProtected(path);
			if (label) {
				return {
					block: true,
					reason: `[${event.toolName}] Blocked: "${path}" is protected (${label}). Use a terminal directly.`,
				};
			}
		}
		return undefined;
	});
}
