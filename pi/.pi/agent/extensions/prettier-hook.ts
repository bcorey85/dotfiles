/**
 * Prettier Hook Extension
 *
 * Runs Prettier on supported files after edits.
 * Ported from Claude Code's prettier-hook.sh
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

		// Supported extensions
		if (!/\.(ts|tsx|js|jsx|vue|json|css|scss|md)$/i.test(filePath)) return;

		// Walk up to find project root
		let dir = dirname(resolve(filePath));
		let root = dir;
		while (root !== "/") {
			if (existsSync(`${root}/package.json`)) break;
			root = dirname(root);
		}
		if (root === "/") return;

		try {
			if (existsSync(`${root}/node_modules/.bin/prettier`)) {
				execSync(`npx prettier --write "${filePath}"`, { cwd: root, stdio: "ignore", timeout: 10000 });
			}
		} catch {
			// Format failures are non-fatal
		}
	});
}
