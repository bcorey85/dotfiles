;; -*- no-byte-compile: t; -*-
;;; packages.el

;; Claude Code IDE integration — runs the `claude` CLI in a side window and
;; speaks the editor IDE/MCP protocol, so Claude sees buffers, selections, and
;; diagnostics (the thing a dumb tmux pane can't do). Requires the `claude` CLI
;; on PATH (already present).
(package! claude-code-ide
  :recipe (:host github :repo "manzaltu/claude-code-ide.el"))

;; Catppuccin Mocha to match the rest of the dotfiles theme.
(package! catppuccin-theme)

;; md-roam — lets org-roam index markdown files alongside .org, so the existing
;; Obsidian-style ~/vault (wikilinks + plain .md) works without converting
;; anything. Must load BEFORE `org-roam-db-autosync-mode' runs — see config.el.
(package! md-roam
  :recipe (:host github :repo "nobiot/md-roam"))
