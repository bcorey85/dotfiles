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

;; magit-delta — pipes magit diff hunks through `delta` (already in install/deps
;; on every platform) so they get real syntax highlighting, matching nvim's
;; treesitter-colored diffs. Configured in config.el with `--no-gitconfig` to
;; dodge the gitconfig line-numbers gutter that otherwise breaks visit-file.
(package! magit-delta)

;; md-roam — lets org-roam index markdown files alongside .org, so the existing
;; Obsidian-style ~/vault (wikilinks + plain .md) works without converting
;; anything. Must load BEFORE `org-roam-db-autosync-mode' runs — see config.el.
(package! md-roam
  :recipe (:host github :repo "nobiot/md-roam"))

;; ghostel — Emacs terminal built on libghostty-vt (the Ghostty VT engine).
;; Replaces vterm as the claude-code-ide terminal backend: it forwards mouse
;; events natively (no SGR workaround), parses off the main thread on a Zig
;; background PTY so Emacs stays responsive during output floods, and supports
;; the Kitty keyboard + graphics protocols, DEC 2026 synchronized output, and
;; OSC 8 hyperlinks — none of which libvterm offers. Auto-injects zsh shell
;; integration with no RC edits. Prebuilt native module auto-downloads on first
;; use (macOS/Linux/FreeBSD — covers WSL, which runs the Linux build).
(package! ghostel)

;; evil-ghostel — evil integration for ghostel: syncs the terminal cursor with
;; Emacs point on state transitions so normal-state nav (hjkl) works in the
;; terminal, and owns cursor-type so per-state cursor shapes take effect.
;; Replaces the manual cursor-refresh hook the old vterm setup needed.
(package! evil-ghostel)
