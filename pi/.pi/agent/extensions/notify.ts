/**
 * Notify Extension
 *
 * Sends desktop notifications when Pi completes work.
 * Ported from Claude Code's notify hook.
 * Supports macOS (osascript), Linux (notify-send), and WSL (PowerShell toast).
 */

import { execSync } from "node:child_process";
import { homedir, hostname } from "node:os";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export default function (pi: ExtensionAPI) {
	pi.on("agent_end", async () => {
		const title = "Pi";
		const message = "Task complete";

		try {
			if (process.platform === "darwin") {
				// macOS
				const escMessage = message.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
				const escTitle = title.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
				execSync(
					`osascript -e 'display notification "${escMessage}" with title "${escTitle}"'`,
					{ stdio: "ignore", timeout: 5000 },
				);
			} else if (process.platform === "linux") {
				// Check if WSL
				try {
					const procVersion = execSync("cat /proc/version 2>/dev/null", {
						encoding: "utf-8",
						timeout: 2000,
					});
					if (procVersion.toLowerCase().includes("microsoft")) {
						// WSL — PowerShell toast
						execSync(
							`powershell.exe -NoProfile -Command "& {[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null; [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom, ContentType = WindowsRuntime] | Out-Null; ` +
							`\$template = '@\"\\n<toast>\\n  <visual>\\n    <binding template=\\\\"ToastGeneric\\\">\\n      <text>${title}</text>\\n      <text>${message}</text>\\n    </binding>\\n  </visual>\\n</toast>\\n\"@'; ` +
							`\$xml = New-Object Windows.Data.Xml.Dom.XmlDocument; \$xml.LoadXml(\$template); ` +
							`\$toast = [Windows.UI.Notifications.ToastNotification]::new(\$xml); ` +
							`[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier(\$app).Show(\$toast)}"`,
							{ stdio: "ignore", timeout: 5000 },
						);
					} else {
						// Native Linux
						execSync(`notify-send "${title}" "${message}"`, { stdio: "ignore", timeout: 5000 });
					}
				} catch {
					execSync(`notify-send "${title}" "${message}"`, { stdio: "ignore", timeout: 5000 });
				}
			}
		} catch {
			// Notifications are best-effort
		}
	});
}
