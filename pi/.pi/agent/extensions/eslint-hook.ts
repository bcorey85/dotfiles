/**
 * ESLint Hook Extension
 *
 * Runs eslint/oxlint on JS/TS/Vue files after edits.
 * Ported from Claude Code's eslint-hook.sh
 */

import { execSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export default function (pi: ExtensionAPI) {
	pi.on("tool_result", async (event) => {
		if (event.toolName !== "write" && event.toolName !== "edit") return;

		const filePath = event.input.path as string;
		if (!filePath) return;

		// Only JS/TS/Vue files
		if (!/\.(ts|tsx|js|jsx|vue)$/i.test(filePath)) return;

		// Walk up to find project root (nearest package.json)
		let dir = dirname(resolve(filePath));
		let root = dir;
		while (root !== "/") {
			if (existsSync(`${root}/package.json`)) break;
			root = dirname(root);
		}
		if (root === "/") return;

		try {
			// Prefer oxlint, fall back to eslint
			if (existsSync(`${root}/node_modules/.bin/oxlint`)) {
				execSync(`npx oxlint --fix "${filePath}"`, { cwd: root, stdio: "ignore", timeout: 10000 });
			} else if (existsSync(`${root}/node_modules/.bin/eslint`)) {
				execSync(`npx eslint --fix --no-warn-ignored --max-warnings=0 "${filePath}"`, {
					cwd: root,
					stdio: "ignore",
					timeout: 15000,
				});
			}
		} catch {
			// Lint failures are non-fatal
		}
	});
}
