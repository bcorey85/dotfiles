;;; config.el -*- lexical-binding: t; -*-

;; Private Doom config for the Emacs test drive. 99% of personal tweaks go here;
;; it loads after all modules. Re-run `doom sync` only after init.el/packages.el
;; changes — plain config.el edits just need a restart (or `doom/reload`).

;;; ---------------------------------------------------------------------------
;;; Environment — give the daemon the same PATH bits the shell has
;;; ---------------------------------------------------------------------------

;; A GUI/daemon Emacs never sources ~/.zshrc, so ~/.local/bin (where the
;; self-contained `claude` binary lives) is missing from exec-path. Add it
;; explicitly so claude-code-ide can find the CLI. Deterministic — survives the
;; systemd user service launch, no snapshot to keep fresh.
(let ((local-bin (expand-file-name "~/.local/bin")))
  (add-to-list 'exec-path local-bin)
  (setenv "PATH" (concat local-bin path-separator (getenv "PATH"))))

;; Same problem, nvm edition: node/npm live under ~/.nvm/versions/node/<ver>/bin,
;; which the daemon never gets because ~/.zshrc (where nvm initializes) isn't
;; sourced. Without this, lsp-mode can't find npm — so it "can't find a way to
;; install" pyright/typescript-language-server, and can't run them either. Pick
;; the HIGHEST installed version's bin and prepend it. Compare with `version<'
;; (not `string<', which sorts "v9" above "v10" lexically and would pin the
;; older node); globs at startup, so a new `nvm install' is picked up for free
;; on the next restart.
(let* ((dirs (file-expand-wildcards (expand-file-name "~/.nvm/versions/node/*")))
       (newest (car (sort dirs
                          (lambda (a b)
                            (version< (string-remove-prefix "v" (file-name-nondirectory b))
                                      (string-remove-prefix "v" (file-name-nondirectory a)))))))
       (node-bin (and newest (expand-file-name "bin" newest))))
  (when (and node-bin (file-directory-p node-bin))
    (add-to-list 'exec-path node-bin)
    (setenv "PATH" (concat node-bin path-separator (getenv "PATH")))))

;;; ---------------------------------------------------------------------------
;;; Evil — `kk' exits insert mode (vim `jj'/`kk' muscle memory)
;;; ---------------------------------------------------------------------------

;; evil-escape watches a 2-key sequence in insert state and fires ESC. Default
;; is "fd"; repoint to "kk". `evil-escape-delay' (default 0.5s) is the window
;; after the first `k' in which the second `k' triggers escape — long enough
;; that a literal double-k in a word (bookkeeper) lands without a false escape,
;; short enough that a deliberate `k k' reads as ESC.
(setq evil-escape-key-sequence "kk")

;;; ---------------------------------------------------------------------------
;;; Look & feel — Modus Vivendi + AporeticSansMono (icon glyphs via Symbols Nerd
;;; Font Mono)
;;; ---------------------------------------------------------------------------

;; JuliaMono — monospace with exceptionally broad Unicode coverage. Chosen for
;; one decisive reason: it natively contains the Dingbats block AND braille, so
;; Claude Code's thinking-spinner glyphs (✻ ✢ ✳ ✶ ✷ ✽ ⠋ ·) render IN the main
;; font rather than a fallback. No fallback = no jitter — neither the vertical
;; bounce (taller fallback box) nor the horizontal shimmy (proportional fallback
;; widths) that every Nerd Font tested here suffered. No dingbat pin.
;;
;; JetBrains Mono Nerd Font (matches the nvim/terminal font). It IS a Nerd Font,
;; so it also carries glyph icons; Doom's nerd-icons still uses its own
;; "Symbols Nerd Font Mono" (installed via `M-x nerd-icons-install-fonts').
;; A float :size is in POINTS (DPI-independent).
(setq doom-font (font-spec :family "JetBrainsMono Nerd Font Mono" :size 19.0 :weight 'medium)
      doom-variable-pitch-font (font-spec :family "JetBrainsMono Nerd Font Mono" :size 19.0 :weight 'medium))

;; DejaVu Sans Mono has no color-emoji glyphs, so emoji in Claude's output render
;; as tofu boxes. Point the `emoji' charset at a real color-emoji family when one
;; is installed (Arch: `pacman -S noto-fonts-emoji'). Guarded so it's a no-op
;; until the font exists — no error on a fresh machine.
(when-let ((emoji-font (seq-find (lambda (f) (member f (font-family-list)))
                                 '("Noto Color Emoji" "Twemoji" "OpenMoji"))))
  (set-fontset-font t 'emoji (font-spec :family emoji-font) nil 'prepend))

;; Extra vertical space between lines, in pixels (nil = none). Bump to taste.
(setq-default line-spacing 0.25)

;; Modus Vivendi — high-contrast dark theme, accessibility-focused (WCAG AAA).
;; Ships with Emacs 28+; no extra package needed.
(setq doom-theme 'modus-vivendi)

;; modus-vivendi handles its own background palette — no overrides needed.

(setq display-line-numbers-type 'relative)   ; matches nvim relativenumber

;; Window dividers — modus-vivendi has its own palette; use its muted gray
;; for a subtle split line that's visible but not distracting.
(custom-set-faces!
  '(vertical-border            :foreground "#595959")
  '(window-divider             :foreground "#595959")
  '(window-divider-first-pixel :foreground "#595959")
  '(window-divider-last-pixel  :foreground "#595959"))

;; Markdown — modus-vivendi provides its own markdown faces. No overrides needed.

;; Hide markup (##, **, _, backticks) by default — the closest thing to nvim
;; markview's clean look without a renderer package. `markdown-hide-markup' is the
;; var `SPC m t' (markdown-toggle-markup-hiding) flips, so per-buffer toggling
;; still works on top of this default.
(after! markdown-mode
  (setq markdown-hide-markup t))

;; `vertical-border' is a 1px char-cell line — drawn, but not a draggable handle,
;; so the mouse resize cursor only catches a sliver. window-divider-mode draws a
;; real divider of a set pixel width the mouse can actually grab. 6px on the
;; right edge (the side-by-side Claude split) gives a comfortable target; stacked
;; windows still resize via the mode-line drag as usual.
(setq window-divider-default-places 'right-only
      window-divider-default-right-width 6)
(window-divider-mode 1)

;;; ---------------------------------------------------------------------------
;;; Window navigation — keep the smart-splits / tmux muscle memory (C-hjkl)
;;; ---------------------------------------------------------------------------

;; In GUI Emacs there's no tmux underneath, so C-hjkl is free to mean "move
;; between windows" exactly like smart-splits.nvim does between nvim splits.
;; Doom puts help on SPC h, so reclaiming C-h for window-left is safe here.
(map! "C-h" #'evil-window-left
      "C-j" #'evil-window-down
      "C-k" #'evil-window-up
      "C-l" #'evil-window-right)

;; Paging the which-key popup is a two-part fix here:
;;
;; 1. TRIGGER KEY. The popup's help/paging trigger is whatever is in
;;    `help-event-list' (default C-h / <f1>). C-h is now window-left and <f1> is
;;    taken, so we add M-h. M-h is also our resize key (below), but that's a
;;    complete top-level binding firing only when NO prefix is pending;
;;    `help-event-list' keys fire only WHILE a prefix is mid-completion (popup
;;    up) — the contexts never overlap, so no conflict.
;;
;; 2. WHAT THE TRIGGER DOES. Doom sets `prefix-help-command' to a searchable
;;    completing-read of the prefix's commands (the "Command under SPC w" list).
;;    That's why M-h/<f1> searched instead of paging. We point it straight at
;;    `which-key-show-next-page-cycle' — not the C-h *dispatch menu* (whose
;;    sub-keys didn't advance the page here) — so each M-h directly flips to the
;;    next page and wraps around. Tradeoff: this is global, so it replaces the
;;    searchable prefix-help everywhere. Revert this one setq to get the search
;;    back.
(after! which-key
  (setq which-key-side-window-max-height 0.5      ; up from 0.25; fits more rows
        which-key-max-display-columns nil         ; use full frame width
        which-key-use-C-h-commands t
        prefix-help-command #'which-key-show-next-page-cycle)
  (add-to-list 'help-event-list ?\M-h))           ; M-h pages the popup (C-h is taken)

;;; ---------------------------------------------------------------------------
;;; Window resizing — tmux `prefix` + hjkl "resize-pane" mode, the Emacs 30 way
;;; ---------------------------------------------------------------------------

;; tmux's resize-pane mode is modal: hit the prefix once, then tap arrows
;; repeatedly without holding anything until you press an unrelated key. Emacs
;; 30's built-in `repeat-mode` gives that for free — no hydra, no extra package,
;; no `doom sync`. M-hjkl invokes a resize (matching the C-hjkl nav muscle
;; memory above, just with Meta), and because the commands live in a
;; `:repeat`-tagged keymap, the FIRST M-h/j/k/l arms a transient map where bare
;; h/j/k/l keep resizing. Press anything else (or ESC) to drop back to evil.
;;
;; h/l = horizontal (the left|right Claude Code split), j/k = vertical.
(repeat-mode 1)
(setq repeat-exit-key "<escape>"   ; vim reflex: ESC leaves resize mode
      repeat-exit-timeout nil)     ; persist like tmux until a non-map key

(defvar-keymap +window-resize-repeat-map
  :doc "Transient map for tmux-style modal window resizing."
  :repeat t
  "h" #'shrink-window-horizontally
  "l" #'enlarge-window-horizontally
  "j" #'enlarge-window
  "k" #'shrink-window)

(map! "M-h" #'shrink-window-horizontally
      "M-l" #'enlarge-window-horizontally
      "M-j" #'enlarge-window
      "M-k" #'shrink-window)

;; ghostel (the Claude Code backend) is a semi-char terminal: it forwards
;; nearly every key straight to the PTY, so the global M-hjkl above never fires
;; while focused in the Claude pane — the keys get swallowed by the TUI. Reclaim
;; the resize chords in `ghostel-semi-char-mode-map' (ghostel's default input
;; mode) so they resize the window instead of being sent to Claude. Once one
;; fires, repeat-mode's transient map outranks ghostel, so bare h/j/k/l keep
;; repeating in the Claude pane too.
(after! ghostel
  (map! :map ghostel-semi-char-mode-map
        "M-h" #'shrink-window-horizontally
        "M-l" #'enlarge-window-horizontally
        "M-j" #'enlarge-window
        "M-k" #'shrink-window)

  ;; Paste into the Claude prompt the vim way. ghostel has no built-in yank
  ;; command, so wire normal-state `p' and insert-state `C-v' to a command that
  ;; sends the top of the kill-ring down the PTY via `ghostel-send-string'.
  (defun +ghostel/yank ()
    "Send the top of the kill-ring to the ghostel pty."
    (interactive)
    (ghostel-send-string (current-kill 0)))
  (map! :map ghostel-semi-char-mode-map
        :n "p" #'+ghostel/yank
        :i "C-v" #'+ghostel/yank)

  ;; evil integration — `evil-ghostel-mode' syncs the terminal cursor with Emacs
  ;; point on state transitions so normal-state nav (hjkl etc.) works correctly,
  ;; and it owns `cursor-type' in the terminal so the per-state cursor SHAPES
  ;; below actually take effect. This replaces the manual cursor-refresh hook the
  ;; old vterm setup needed — ghostel + evil-ghostel auto-refresh on state entry.
  (add-hook 'ghostel-mode-hook #'evil-ghostel-mode)
  ;; Shape-only cursor: box in normal, bar in insert, hollow in visual. No
  ;; per-state color — ghostel now switches the cursor SHAPE by mode (vterm
  ;; couldn't, so the colors were the only mode signal there); the cursor keeps
  ;; the theme's default `cursor' color in every state.
  (setq evil-normal-state-cursor 'box
        evil-insert-state-cursor 'bar
        evil-visual-state-cursor 'hollow)

  ;; Overlay shedding: `global-hl-line-mode' and `show-paren-mode' are on
  ;; globally and add per-redraw overlay work (highlight the cursor line, scan
  ;; for parens). Both are useless in a terminal buffer — there are no code
  ;; parens to match and no useful line highlight on app-rendered cells — but
  ;; they keep recomputing every redisplay. Disable them buffer-locally.
  (add-hook 'ghostel-mode-hook
            (lambda ()
              (setq-local global-hl-line-mode nil)
              ;; show-paren is a global mode driven by its own machinery; the
              ;; per-buffer off switch is the local mode, not a setq-local on the
              ;; global var (which is a silent no-op).
              (show-paren-local-mode -1)))

  ;; Redraw fix: the global `line-spacing' 0.25 we set above (nice for prose)
  ;; makes ghostel leave cursor trails and stale rows — libghostty-vt lays out
  ;; on tight line boxes and the extra pixels desync it. Zero it out in terminal
  ;; buffers.
  (add-hook 'ghostel-mode-hook (lambda () (setq-local line-spacing nil)))

  ;; Colour re-sync chord. `doom/reload' tears the theme down and back up, and
  ;; ghostel's own `enable-theme-functions' sync fires mid-teardown — reading
  ;; unspecified faces and falling back to ANSI palette indices, so an open
  ;; terminal's default fg/bg land on garbage (blue bg + magenta/cyan fg) with
  ;; nothing re-syncing afterward. Pinning `ghostel-default' to concrete colours
  ;; (README "Color palette" / dakra/ghostel#178) does NOT beat the race here —
  ;; Doom re-applies customised faces through that same hook. A standalone
  ;; `ghostel-sync-theme' at a quiescent moment fixes it reliably, so bind it to
  ;; a chord ghostel RECLAIMS from the PTY (the TUI would otherwise swallow it):
  ;; after a `SPC h r r' with Claude open, hit `C-c r' in the pane to restore
  ;; colours.
  (map! :map ghostel-semi-char-mode-map
        "C-c r" #'ghostel-sync-theme)

  ;; Automatic version of the above — event-driven, not timed. A *timed* re-sync
  ;; can't beat doom/reload's late VT-default color reset (tested: even a 2s
  ;; deferred sync gets overwritten), but a re-sync at quiescence holds
  ;; permanently. So on reload, ARM a one-shot: re-sync the first time a ghostel
  ;; buffer is focused or receives a command (the reload has long settled by
  ;; then, so it sticks), then remove the triggers — so `post-command-hook' isn't
  ;; carried on the hot path forever, only transiently after a reload.
  ;; `C-c r' / `SPC l t' remain the manual fallback.
  (defun +ghostel--resync-once (&rest _)
    "Re-sync ghostel colors once a ghostel buffer is current, then disarm."
    (when (derived-mode-p 'ghostel-mode)
      (remove-hook 'post-command-hook #'+ghostel--resync-once)
      (remove-hook 'window-selection-change-functions #'+ghostel--resync-on-select)
      (when (fboundp 'ghostel-sync-theme) (ghostel-sync-theme))))
  (defun +ghostel--resync-on-select (&rest _)
    "`window-selection-change-functions' shim for `+ghostel--resync-once'."
    (with-current-buffer (window-buffer (selected-window))
      (+ghostel--resync-once)))
  (defun +ghostel--arm-resync (&rest _)
    "Arm a one-shot ghostel color re-sync for the next ghostel focus/command."
    (add-hook 'post-command-hook #'+ghostel--resync-once)
    (add-hook 'window-selection-change-functions #'+ghostel--resync-on-select))
  (add-hook 'doom-after-reload-hook #'+ghostel--arm-resync)

  ;; Show the evil state in the Claude window. Give ghostel the compact
  ;; `minimal' modeline (bar + modal state + buffer name), which fits the narrow
  ;; side window. (Doom doesn't auto-hide the modeline for ghostel the way it
  ;; does for its built-in vterm module, so there's no hook to remove — just set
  ;; the minimal modeline directly.)
  (defun +ghostel/use-minimal-modeline-h ()
    "Give ghostel a compact modeline that still surfaces the evil state."
    (doom-modeline-set-modeline 'minimal))
  (add-hook 'ghostel-mode-hook #'+ghostel/use-minimal-modeline-h 90)

  ;; Image paste: ghostel/claude-code-ide only move text through the PTY, so a
  ;; clipboard image can't be piped in like in a GUI terminal. The command
  ;; (+claude/paste-clipboard-image, defined top-level in the Claude Code
  ;; section so the SPC l v leader binding can reach it too) dumps the Wayland
  ;; clipboard image to a temp PNG and types its path at the prompt. C-S-v here.
  (map! :map ghostel-semi-char-mode-map
        :i "C-S-v" #'+claude/paste-clipboard-image)

  ;; Keyboard-native scrollback for a vim brain. `ghostel-copy-mode' freezes the
  ;; view (so streaming output stops yanking point to the bottom) and turns the
  ;; buffer into a read-only nav buffer. The one real gap: ghostel leaves you in
  ;; evil INSERT state there, where hjkl self-insert and motions are dead.
  ;; Switch to NORMAL on entry — then k/j/C-u/C-d/gg/G/`/' all work (vim AND
  ;; tmux copy-mode muscle memory) — and back to INSERT on exit to resume typing
  ;; to Claude.
  (defun +ghostel/copy-mode-evil-state-h ()
    "Evil normal state inside `ghostel-copy-mode', insert state outside it."
    (if (bound-and-true-p ghostel-copy-mode) (evil-normal-state) (evil-insert-state)))
  (add-hook 'ghostel-copy-mode-hook #'+ghostel/copy-mode-evil-state-h)
  ;; Enter scrollback with one free chord: `C-'' is unbound in insert state, in
  ;; ghostel-semi-char-mode-map, and globally, so this fills a blank rather than
  ;; shadowing a load-bearing key. `q' quits (tmux habit + idiomatic
  ;; special-buffer quit) by disabling copy-mode directly — ghostel's
  ;; `ghostel-readonly-fast-exit' would otherwise self-insert `q' and forward it
  ;; to Claude, so the explicit toggle is what gives a clean exit. `C-c C-t' and
  ;; RET still work too. C-' lives in ghostel-semi-char-mode-map, which is
  ;; shadowed once copy-mode is active, so it's enter-only — exit via `q'.
  (map! :map ghostel-semi-char-mode-map "C-'" #'ghostel-copy-mode
        :map ghostel-copy-mode-map :n "q"
        (lambda () (interactive) (ghostel-copy-mode -1)))

  ;; Send Escape to Claude with a second Esc. Claude clears the input draft on
  ;; Escape, but evil eats bare ESC in insert state (→ normal state) so it never
  ;; reaches the PTY. `<escape>' (the GUI key — distinct from the ESC/Meta prefix
  ;; that powers M-x etc.) is idle in evil normal state (just re-asserts normal),
  ;; so rebinding it there — in ghostel only — to send a real Escape makes "ESC
  ;; ESC" from insert = clear the prompt. `i' to start typing again. (Caveat:
  ;; spamming ESC in normal state now sends repeated escapes to Claude, which is
  ;; its double-Esc rewind menu — see the single-chord alternative if that
  ;; bites.)
  (defun +ghostel/send-escape ()
    "Send ESC to the ghostel pty."
    (interactive)
    (ghostel-send-key "escape"))
  (map! :map ghostel-semi-char-mode-map :n "<escape>" #'+ghostel/send-escape))

;; Open a standalone ghostel terminal. Replaces the `SPC o t' / `SPC o T'
;; bindings Doom's :term vterm module provided before it was removed.
(map! :leader
      (:prefix ("o" . "open")
       :desc "Ghostel terminal"        "t" #'ghostel
       :desc "Ghostel terminal (split)" "T" #'+ghostel/split
       :desc "Browser (eww)"           "w" #'eww))

;; oil.nvim muscle memory: SPC e opens dired at the current buffer's directory
(map! :leader :desc "Dired jump" "e" #'dired-jump)

(defun +ghostel/split ()
  "Open ghostel in a split window below."
  (interactive)
  (split-window-below)
  (ghostel))

;;; ---------------------------------------------------------------------------
;;; Tree-sitter grammars — mason-treesitter equivalent (auto-install on open)
;;; ---------------------------------------------------------------------------

;; This is the Emacs answer to nvim-treesitter's `ensure_installed`. treesit-auto
;; alone DOESN'T cut it here: Doom's :lang modules own the major-mode remap and
;; drop you straight into the -ts-mode, front-running treesit-auto's install
;; advice — so the grammar is never requested and native treesit just warns.
;;
;; So we do it declaratively. First a known-good source alist (URLs + the subdir
;; quirks for js/tsx/typescript), then a guarded startup loop that compiles any
;; missing grammar into doom-data-dir/tree-sitter. CRITICAL: native treesit does
;; NOT search that dir by default (it only searches `treesit-extra-load-path` and
;; `user-emacs-directory/tree-sitter`), so we must `add-to-list` it onto
;; `treesit-extra-load-path` *before* the availability check — otherwise every
;; grammar we compile is invisible and JS/JSX/TSX silently fall back to the
;; regexp `js-mode` with almost no highlighting. Mirrors the grammar set in
;; nvim/.../plugins/treesitter.lua, limited to langs with a Doom -ts-mode.
;;
;; NOTE: the first restart after adding a language compiles it synchronously
;; (git clone + cc, ~a few seconds each) — a one-time cost. Every later startup
;; sees the .so present and skips instantly.
(setq treesit-language-source-alist
      '((bash       "https://github.com/tree-sitter/tree-sitter-bash")
        (c          "https://github.com/tree-sitter/tree-sitter-c")
        (css        "https://github.com/tree-sitter/tree-sitter-css")
        (html       "https://github.com/tree-sitter/tree-sitter-html")
        (javascript "https://github.com/tree-sitter/tree-sitter-javascript" "master" "src")
        (json       "https://github.com/tree-sitter/tree-sitter-json")
        (lua        "https://github.com/tree-sitter-grammars/tree-sitter-lua")
        (python     "https://github.com/tree-sitter/tree-sitter-python")
        (toml       "https://github.com/tree-sitter-grammars/tree-sitter-toml")
        (tsx        "https://github.com/tree-sitter/tree-sitter-typescript" "master" "tsx/src")
        (typescript "https://github.com/tree-sitter/tree-sitter-typescript" "master" "typescript/src")
        (yaml       "https://github.com/tree-sitter-grammars/tree-sitter-yaml")))

(let ((out-dir (expand-file-name "tree-sitter" doom-data-dir)))
  ;; Make the install dir a searched dir FIRST, so already-compiled grammars are
  ;; found (and skipped) and freshly-compiled ones load this session.
  (add-to-list 'treesit-extra-load-path out-dir)
  (dolist (lang (mapcar #'car treesit-language-source-alist))
    (unless (treesit-language-available-p lang)
      ;; NO silent fallback. If the compile errors, OR if it "succeeds" but the
      ;; grammar still isn't loadable (the classic wrong-path trap), raise an
      ;; :error-level warning — that pops the *Warnings* buffer on startup
      ;; instead of letting JS/TSX quietly degrade to regexp font-lock.
      (condition-case err
          (progn
            (treesit-install-language-grammar lang out-dir)
            (unless (treesit-language-available-p lang)
              (lwarn 'treesit :error
                     "grammar `%s' compiled but NOT loadable from %s — fix treesit-extra-load-path"
                     lang out-dir)))
        (error
         (lwarn 'treesit :error
                "grammar `%s' FAILED to install: %S — `%s' files will have no tree-sitter highlighting"
                lang err lang))))))

;; Native treesit defaults to font-lock level 3 of 4 — it skips operators,
;; brackets, delimiters, and some variable/property faces, which is why TSX
;; looks dimmer than nvim-treesitter (roughly level 4). Max it out for parity.
(setq treesit-font-lock-level 4)

;;; ---------------------------------------------------------------------------
;;; Dired — oil.nvim muscle memory: `-` goes up a directory
;;; ---------------------------------------------------------------------------

;; Doom's evil dired leaves `-` unbound and puts up-directory on `^`. Rebind `-`
;; to `dired-up-directory` so it feels like oil.nvim. `:n` = normal state only,
;; so nothing in insert/wdired is affected.
(after! dired
  (map! :map dired-mode-map
        :n "-" #'dired-up-directory))

;;; ---------------------------------------------------------------------------
;;; LSP — attach to the native treesit modes
;;; ---------------------------------------------------------------------------

;; Doom's `javascript +lsp` hooks `lsp!` onto the CLASSIC modes (typescript-mode,
;; rjsx-mode, web-mode), but `+tree-sitter` opens .ts/.tsx in the NATIVE treesit
;; modes (typescript-ts-mode / tsx-ts-mode) — so the two never meet, lsp never
;; auto-attaches, and a manual `M-x lsp` falls through to the misleading "not in
;; project or it is blocklisted". Hooking lsp! onto the treesit modes is the
;; documented fix (merrick.luois.me Emacs-29 post; ovistoica's lsp-mode+treesit
;; config). lsp-language-id-configuration already maps tsx-ts-mode, and lsp's
;; standard root detection then handles the pnpm monorepo with no extra config.
(add-hook! '(typescript-ts-mode-hook tsx-ts-mode-hook) #'lsp!)

;; Doom's `(lsp +peek)' pulls in lsp-ui, whose sideline draws diagnostics as
;; inline virtual text inside the buffer (the grey message trailing the error
;; line). That duplicates the colored echo-area message below, so silence the
;; sideline's diagnostic layer. Code actions/hover on the sideline stay.
(after! lsp-ui
  (setq lsp-ui-sideline-show-diagnostics nil))

;;; ---------------------------------------------------------------------------
;;; Flycheck — childframe diagnostics, colored by severity
;;; ---------------------------------------------------------------------------

;; Doom's `(syntax +childframe)' shows diagnostics in a `flycheck-posframe'
;; childframe — the nvim diagnostic-float equivalent, and it draws over the
;; window rather than reflowing buffer text. modus-vivendi provides its own
;; accessibility-focused palette for these faces, so no overrides needed.

;; Red wavy underline under the whole offending expression. `flycheck-highlighting-mode'
;; keeps the region (with LSP end positions, that's the full call). The catch:
;; `flycheck-highlighting-style' defaults to a conditional that switches to an
;; invisible "delimiters" face (`flycheck-delimited-error', unspecified here) for
;; regions over ~4 lines — so a multi-line call like `sendMessage(...)' rendered
;; with NO underline at all. Forcing `level-face' makes flycheck always paint the
;; region with the level face (`flycheck-error' = wavy Red1), short or long.
(after! flycheck
  (setq flycheck-highlighting-mode 'symbols
        flycheck-highlighting-style 'level-face))

;; Deep-review mode: after RET'ing into a file from magit, walk the diff in the
;; real (tree-sitter'd) buffer. vc-gutter is diff-hl under the hood.
;;   ]c / [c  step through hunks (vim :Gdiffsplit muscle memory; ]d/[d also work)
;;   g h      pop the hunk (added + removed) in a posframe popup
;; The one that actually does what was wanted: a unified diff (green/red) of the
;; current file vs HEAD, in a real `diff-mode' buffer, where `diff-font-lock-syntax'
;; layers the SOURCE language's highlighting (treesitter for treesit modes) over
;; the +/- lines. magit-diff-mode and ediff both bypass this; plain diff-mode is
;; the only built-in view that gives green/red AND syntax highlighting together.
(defun +git-diff-file-highlighted ()
  "Show this file's diff vs HEAD in a syntax-highlighted `diff-mode' buffer."
  (interactive)
  (let* ((file (or (buffer-file-name) (user-error "Not visiting a file")))
         (root (or (vc-root-dir) default-directory))
         (buf  (get-buffer-create "*git-diff*")))
    (with-current-buffer buf
      (let ((inhibit-read-only t)
            (default-directory root))
        (erase-buffer)
        (call-process "git" nil t nil "--no-pager" "diff" "HEAD" "--" file)
        (when (zerop (buffer-size)) (insert "No changes vs HEAD.\n"))
        (diff-mode)
        (setq-local diff-font-lock-syntax t)
        (font-lock-ensure)))
    (pop-to-buffer buf)))

;; gitsigns `linehl` for Emacs ------------------------------------------------
;; diff-hl ships fringe bars + an on-demand hunk popup and deliberately NEVER
;; paints the line backgrounds — so the diff lives in the fringe/a side buffer,
;; not ON the buffer. gitsigns paints the changed LINES themselves (and keeps
;; tree-sitter + diagnostics on top). No package does this in Emacs, so: diff-hl
;; already lays a hunk overlay spanning the changed lines (diff-hl.el:705,
;; carrying `diff-hl-hunk-type`) — it just never gives it a face. We add one.
;; bg-only + :extend t + fg nil ⇒ tree-sitter foreground shows through and the
;; wash fills to the window edge (same trick as the ediff faces below).
;; modus-vivendi has built-in diff-hl faces, so use its palette:
;;   green bg for insert, yellow bg for change, red bg for delete.
(defface +diff-hl-line-insert '((t :background "#2e3c2e" :extend t))
  "gitsigns-style line wash for inserted lines (modus green-muted).")
(defface +diff-hl-line-change '((t :background "#3c3c2e" :extend t))
  "gitsigns-style line wash for changed lines (modus yellow-muted).")
(defface +diff-hl-line-delete '((t :background "#3c2e2e" :extend t))
  "gitsigns-style line wash anchoring deleted lines (modus red-muted).")

(defvar +diff-hl-inline-enabled nil
  "When non-nil, wash diff-hl hunk overlays with a line background.
Off by default so only the fringe gutter signs show; toggle on with `g L'.")

(defun +diff-hl-paint-hunks (&rest _)
  "Give every diff-hl hunk overlay a background face (gitsigns `linehl`)."
  (when +diff-hl-inline-enabled
    (dolist (o (overlays-in (point-min) (point-max)))
      (when (overlay-get o 'diff-hl-hunk)
        ;; Sit under hl-line and the visual-mode region so selection stays legible.
        (overlay-put o 'priority -60)
        (overlay-put o 'face
                     (pcase (overlay-get o 'diff-hl-hunk-type)
                       ('insert '+diff-hl-line-insert)
                       ('delete '+diff-hl-line-delete)
                       (_        '+diff-hl-line-change)))))))

(defun +diff-hl-toggle-inline ()
  "Toggle gitsigns-style inline line wash (cf. :Gitsigns toggle_linehl)."
  (interactive)
  (setq +diff-hl-inline-enabled (not +diff-hl-inline-enabled))
  (if +diff-hl-inline-enabled
      (+diff-hl-paint-hunks)
    (dolist (o (overlays-in (point-min) (point-max)))
      (when (overlay-get o 'diff-hl-hunk) (overlay-put o 'face nil))))
  (message "diff-hl inline linehl %s" (if +diff-hl-inline-enabled "on" "off")))

;; Removed lines ("what did I delete here?") are shown via diff-hl's own
;; posframe popup — `diff-hl-show-hunk', bound to `g h' below — which lists the
;; added AND removed lines for the hunk at point. (An earlier version rendered
;; the removed lines as inline phantom overlays by hand-parsing the unified diff;
;; that was ~150 lines riding on diff-hl internals, so it's gone — the popup is
;; the idiomatic, maintenance-free equivalent. `g =' still gives the full-file
;; syntax-highlighted diff for a deeper read.)

(after! diff-hl
  ;; Split staged from unstaged indicators: staged hunks render as "reference"
  ;; signs (dimmed via `diff-hl-reference-*' faces below) and unstaged hunks
  ;; stay solid — so `-'/`stage-hunk' FADES the hunk's gutter sign instead of
  ;; leaving it solid. The old `t' folded both into one HEAD-vs-working sign,
  ;; hiding which hunks were staged. Review-from-magit still works: staged
  ;; changes remain visible, just dimmed. See diff-hl.el:251,511-530,744-749.
  (setq diff-hl-show-staged-changes nil)
  ;; Render staged (reference) hunks with the SAME fringe renderer as unstaged
  ;; hunks. The default `diff-hl-highlight-reference-function' is
  ;; `diff-hl-highlight-on-fringe-flat', whose bitmap (`diff-hl-bmp-empty' =
  ;; `[0]', diff-hl.el:377) is a 1px EMPTY bitmap — so staged hunks render as
  ;; NOTHING in the fringe. Pointing it at `diff-hl-highlight-on-fringe' keeps
  ;; the same arrow shape as working hunks; only the dimmed
  ;; `diff-hl-reference-*' faces below differentiate staged from unstaged —
  ;; the gitsigns fade effect (same sign, dimmer color).
  (setq diff-hl-highlight-reference-function 'diff-hl-highlight-on-fringe)
  ;; Fade the staged (reference) fringe signs. The default `diff-hl-reference-*'
  ;; faces inherit the bright working faces, so without this staged hunks look
  ;; identical to unstaged. custom-set-faces! re-applies on theme load, so a
  ;; live `doom/reload' won't clobber the dim palette.
  ;; Using modus-vivendi muted tones for staged hunks.
  (custom-set-faces!
    '(diff-hl-reference-insert :foreground "#4ea04e")  ; muted green (staged add)
    '(diff-hl-reference-delete :foreground "#a04e4e")  ; muted red   (staged delete)
    '(diff-hl-reference-change  :foreground "#a08e4e")) ; muted yellow (staged change)
  ;; Paint the hunk lines after every (sync or async) overlay refresh.
  (advice-add 'diff-hl--update-overlays :after #'+diff-hl-paint-hunks)
  (map! :n "] c" #'diff-hl-next-hunk
        :n "[ c" #'diff-hl-previous-hunk
        :n "g L" #'+diff-hl-toggle-inline         ; toggle the ambient line wash (linehl)
        :n "g h" #'diff-hl-show-hunk              ; floating posframe popup: added + removed lines
        :n "g =" #'+git-diff-file-highlighted))   ; full-file side-buffer syntax diff

;; indent-bars: character mode instead of stipple ----------------------------
;; The doom `indent-guides' module picks stipple bitmaps here (non-macOS, Emacs
;; 30). Stipple is anchored to the WINDOW's pixel grid and drawn continuously
;; down the whole window, so it bleeds across overlay virtual-lines (an opaque
;; overlay background can't suppress it) — which garbles the removed-line diff
;; phantoms above, magit-blame, and any inline overlay UI. Character bars are
;; text-property based: they render only on real buffer lines, so virtual-line
;; phantoms stay clean. Must be set before the faces generate (next
;; `indent-bars-mode' enable), so override after the module's own `:config'.
(after! indent-bars
  (setq indent-bars-prefer-character t))

;; Ediff — modus-vivendi provides its own high-contrast diff faces. No overrides
;; needed — the built-in palette uses green/red/yellow with proper contrast.

;; Ediff + evil bindings (a/b copy, j/k/n/p navigate, q quit) are handled by
;; `evil-collection-ediff', enabled via `(evil +everywhere)' in init.el. It sets
;; ediff-mode's initial state to `normal' AND registers ediff-mode-map as an
;; overriding map for `normal' — the two MUST agree or evil wins and `a' becomes
;; evil-append (insert). A previous custom block here forced `motion' state while
;; evil-collection's override stayed on `normal', so the control buffer's `a'
;; fell through to insert. Don't reintroduce a competing state/override here.



;; Syntax-highlighted magit diffs via delta ------------------------------------
;; Stock magit does NOT fontify diff bodies (`magit-diff-wash-hunk` inserts raw
;; +/- lines; only the bg faces are applied), so code in a magit diff renders in
;; one flat color. `magit-delta` pipes each hunk through `delta`, which
;; syntax-highlights it.
;;
;; `--no-gitconfig' is the load-bearing flag: it drops the gitconfig
;; `line-numbers`/`navigate' settings whose gutter shifts the +/- markers off
;; column 0 and breaks `magit-diff-visit-file' with "Search failed". magit-delta
;; auto-appends --syntax-theme and --color-only; don't repeat them.
(use-package! magit-delta
  :hook (magit-mode . magit-delta-mode)
  :init (setq magit-delta-default-dark-theme "Dracula")
  :config
  (setq magit-delta-delta-args
        '("--no-gitconfig"
          "--max-line-distance" "0.6"
          "--true-color" "always"
          "--plus-style"       "syntax #2e3c2e"      ; muted green (modus)
          "--minus-style"      "syntax #3c2e2e"      ; muted red   (modus)
          "--plus-emph-style"  "syntax #3a5a3a"      ; word-level add
          "--minus-emph-style" "syntax #5a3a3a")))   ; word-level remove

;; File-row status keywords — neogit-style coloring. Magit faces the WHOLE file
;; heading (status word + filename) with one `magit-diff-file-heading` face
;; (`magit-format-file-default`, magit-diff.el), so "modified"/"new file"/"deleted"
;; render flat white. neogit colors the keyword instead. Swap in a format function
;; that faces the leading status word per-status and leaves the filename alone.
;;   modified → blue
;;   new file → green
;;   deleted  → red
;;   renamed  → yellow
(defface +magit-status-modified '((t :foreground "#5fafaf")) "neogit-style modified keyword (blue).")
(defface +magit-status-added    '((t :foreground "#5faf5f")) "neogit-style new-file keyword (green).")
(defface +magit-status-removed  '((t :foreground "#ff5f5f")) "neogit-style deleted keyword (red).")
(defface +magit-status-renamed  '((t :foreground "#d0a05f")) "neogit-style renamed keyword (yellow).")

(defun +magit-format-file-neogit (_kind file face &optional status orig)
  "Like `magit-format-file-default` but color the leading status keyword."
  (concat
   (and status
        (propertize (format "%-11s" status)
                    'font-lock-face
                    (pcase status
                      ("new file" '+magit-status-added)
                      ("deleted"  '+magit-status-removed)
                      ("renamed"  '+magit-status-renamed)
                      (_          '+magit-status-modified))))
   (propertize (if orig (format "%s -> %s" orig file) file)
               'font-lock-face face)))

;; Untracked file content on TAB (neogit-style). Stock magit lists untracked
;; files but TAB no-ops on them — it won't synthesize a diff for a file git
;; doesn't track (deliberate, perf-minded). neogit DOES, via `git diff
;; --no-index'. This swaps magit's untracked section for one whose per-file body
;; is filled LAZILY (magit-insert-section-body runs only on expand) with that
;; same output. Pure display — no index mutation, unlike `SPC u s' (intent-to-add).
;; The body pipes the diff through the `delta' binary directly and converts its
;; ANSI to text properties (magit-delta's wash hook doesn't fire on lazily
;; inserted content), reusing the exact `magit-delta-delta-args' + the
;; --color-only/--syntax-theme magit-delta auto-appends, so colors match the rest
;; of magit. Falls back to the raw diff if delta is missing or errors.
(defun +magit-insert-untracked-files-with-content ()
  "Untracked files as sections whose body lazily shows their content."
  (when-let ((files (magit-list-untracked-files)))
    (magit-insert-section (untracked)
      (magit-insert-heading "Untracked files")
      (dolist (file files)
        (magit-insert-section (file file t)   ; t = collapsed by default
          (magit-insert-heading
            (funcall magit-format-file-function 'list file 'magit-filename))
          ;; Only regular files get an expandable diff; dirs render as headings.
          (when (file-regular-p file)
            (magit-insert-section-body
              (let* ((dir default-directory)
                     ;; `--no-index' exits 1 when the file is non-empty; expected.
                     (raw (with-temp-buffer
                            (setq default-directory dir)
                            (ignore-errors
                              (call-process "git" nil t nil
                                            "diff" "--no-index" "--" "/dev/null" file))
                            (buffer-string)))
                     (out (if (and (executable-find "delta")
                                   (boundp 'magit-delta-delta-args)
                                   (not (string-empty-p raw)))
                              (with-temp-buffer
                                (insert raw)
                                (if (eq 0 (condition-case nil
                                              (apply #'call-process-region
                                                     (point-min) (point-max) "delta" t t nil
                                                     (append (list "--color-only"
                                                                   "--syntax-theme"
                                                                   magit-delta-default-dark-theme)
                                                             magit-delta-delta-args))
                                            (error 1)))
                                    (ansi-color-apply (buffer-string))
                                  raw))
                            raw)))
                (insert out)
                (unless (or (string-empty-p out) (string-suffix-p "\n" out))
                  (insert ?\n)))))))
      (insert ?\n))))

(after! magit
  ;; Word-level diff refinement is delegated to delta (--plus-emph/--minus-emph),
  ;; so magit's own refine is off here to avoid double word-emphasis.
  (setq magit-diff-refine-hunk nil)
  ;; defcustom won't clobber a value set before load, but set it post-load to be safe.
  (setq magit-format-file-function #'+magit-format-file-neogit)
  ;; Swap magit's untracked section for the expandable-content version above.
  (magit-add-section-hook 'magit-status-sections-hook
                          #'+magit-insert-untracked-files-with-content
                          #'magit-insert-untracked-files)   ; same position
  (remove-hook 'magit-status-sections-hook #'magit-insert-untracked-files)
  ;; Magit truncates lines by default, so long messages/diffs run off-screen.
  ;; Wrap them at the window edge instead.
  (add-hook 'magit-mode-hook (lambda () (setq-local truncate-lines nil))))

;; Static magit/diff faces delta doesn't own (context, hunk headings, stat
;; numbers). The +/- hunk-body colors come from delta's --plus/--minus-style;
;; these cover the rest, and double as the fallback if magit-delta-mode is off.
(custom-set-faces!
  '(magit-diff-context           :background nil      :foreground nil :extend t)
  '(magit-diff-context-highlight :background "#2a2a2a" :foreground nil :extend t)
  '(magit-diff-hunk-heading           :background "#2a2a2a" :foreground "#5fafaf" :extend t)
  '(magit-diff-hunk-heading-highlight :background "#333333" :foreground "#5fafaf" :extend t)
  ;; +N/-M stat fringe (commit diffstat), not the file-row keywords above.
  '(magit-diffstat-added   :foreground "#5faf5f")
  '(magit-diffstat-removed :foreground "#ff5f5f"))

;; Word-level diff refinement is delegated to delta now (magit-diff-refine-hunk is
;; nil above), so these `diff-refine-added` / `diff-refine-removed` faces only show
;; as the no-delta fallback. Use subtle bg-only emphasis matching modus-vivendi.
(custom-set-faces!
  '(diff-refine-added           :background "#3a5a3a" :foreground nil :extend t)
  '(diff-refine-removed         :background "#5a3a3a" :foreground nil :extend t)
  ;; status-buffer section chrome
  '(magit-section-highlight   :background "#2a2a2a" :foreground nil)
  '(magit-section-heading     :foreground "#d0a05f" :weight bold))   ; yellow, matches modus palette

;;; ---------------------------------------------------------------------------
;;; Claude Code — the cockpit centerpiece
;;; ---------------------------------------------------------------------------

;; Clipboard-image paste for the Claude prompt. ghostel/claude-code-ide only
;; move text through the PTY, so dump the Wayland clipboard image to a temp PNG
;; and type its path — Claude Code reads local image files by path. Bound to
;; insert-state C-S-v in ghostel and to SPC l v below.
(defun +claude/paste-clipboard-image ()
  "Save a Wayland clipboard image to a temp PNG and insert its path at point."
  (interactive)
  (unless (string-match-p "image/" (shell-command-to-string "wl-paste --list-types 2>/dev/null"))
    (user-error "No image on the clipboard"))
  (let ((file (make-temp-file "claude-clip-" nil ".png")))
    (call-process-shell-command
     (format "wl-paste --type image/png > %s" (shell-quote-argument file)))
    (ghostel-send-string file)
    (message "Pasted image path: %s" file)))

(use-package! claude-code-ide
  :defer t
  :init
  ;; SPC a is embark-act and SPC o is "open"; SPC l is free. Use it as the
  ;; Claude ("llm") prefix so nothing fights the C-hjkl window nav above.
  (map! :leader
        (:prefix ("l" . "llm/claude")
         :desc "Claude: start/toggle in project" "l" #'claude-code-ide
         :desc "Claude: continue last session"   "c" #'claude-code-ide-continue
         :desc "Claude: resume a session"        "r" #'claude-code-ide-resume
         :desc "Claude: send prompt/region"      "s" #'claude-code-ide-send-prompt
         :desc "Claude: switch to buffer"        "b" #'claude-code-ide-switch-to-buffer
         :desc "Claude: re-sync terminal colors" "t" #'ghostel-sync-theme
         :desc "Claude: paste clipboard image"   "v" #'+claude/paste-clipboard-image
         :desc "Claude: list sessions"           "L" #'claude-code-ide-list-sessions
         :desc "Claude: stop session"            "q" #'claude-code-ide-stop))
  ;; Upstream-style global chord, bound to the real entry command.
  (map! "C-c C-'" #'claude-code-ide)
  :config
  ;; ghostel (libghostty-vt) renders Claude's TUI better than vterm/eat:
  ;; native mouse forwarding, Kitty keyboard protocol, DEC 2026 synchronized
  ;; output, and off-main-thread parsing so Emacs stays responsive during
  ;; output floods. Configured in the (after! ghostel ...) block above.
  (setq claude-code-ide-terminal-backend 'ghostel)
  ;; Expose Emacs editor tools (xref, diagnostics, etc.) to Claude over MCP.
  (claude-code-ide-emacs-tools-setup))

;;; --- tmux-sessionizer + dev layout (on top of :ui workspaces) -----------
;; Ports ~/.local/bin/{tmux-sessionizer,tmux-project-open,dev}. The workspaces
;; module already IS the tmux-session layer (M-1..9 switch, gt/gT cycle, SPC TAB
;; menu, auto-workspace on projectile-switch-project). What's missing is the
;; picker + the two-"window" `dev' layout, so that's all this adds:
;;   window 1 "code"    -> project files (dired) | Claude (claude-code-ide side window)
;;   window 2 "console" -> `+dev-console-shells' ghostel shells (your 1-3 servers)
;; As in tmux-project-open, the layout is built only when the workspace is NEW;
;; re-running on an existing project just switches to it.

(defcustom +dev-project-parents '("~/dev")
  "Dirs whose immediate children are selectable projects (mirrors tmux-sessionizer)."
  :type '(repeat directory) :group 'doom)

(defcustom +dev-project-extras '("~/vault" "~/dotfiles")
  "Standalone project dirs added to the sessionizer list."
  :type '(repeat directory) :group 'doom)

(defcustom +dev-console-shells 3
  "Number of ghostel shells in the console layout (`dev' spawns 3)."
  :type 'integer :group 'doom)

(defvar +dev--roots (make-hash-table :test 'equal)
  "Workspace name -> project root, recorded by `+dev/sessionizer'.")

(defun +dev--root ()
  "Project root for the current workspace: recorded root, else projectile, else cwd."
  (or (gethash (+workspace-current-name) +dev--roots)
      (doom-project-root)
      default-directory))

(defun +dev--shell-buffer (dir n)
  "Get or create this workspace's Nth console shell, a login shell in DIR."
  (require 'ghostel)
  (let ((name (format "*sh:%s:%d*" (+workspace-current-name) n)))
    (or (get-buffer name)
        (let* ((default-directory dir)
               (buf   (get-buffer-create name))
               (shell (or (getenv "SHELL") shell-file-name)))
          (ghostel-exec buf shell)
          buf))))

(defcustom +dev-code-landing 'project-buffer
  "What the code layout's editor window shows:
- `project-buffer' : empty buffer rooted at the project (no prompt, no dired)
- `find-file'      : the projectile-find-file picker
- `dired'          : dired of the project root (nvim . style)"
  :type '(choice (const project-buffer) (const find-file) (const dired))
  :group 'doom)

(defun +dev--open-editor (dir)
  "Show the editor landing for DIR per `+dev-code-landing'."
  (pcase +dev-code-landing
    ('dired (dired dir))
    ('find-file (let ((default-directory dir)) (ignore-errors (projectile-find-file))))
    (_ ;; empty buffer rooted at the project: no prompt, and SPC SPC / SPC .
       ;; work instantly because `default-directory' is the project root.
       (let ((buf (get-buffer-create (format "*code:%s*" (+workspace-current-name)))))
         (with-current-buffer buf (setq-local default-directory dir))
         (switch-to-buffer buf)))))

(defun +dev--single-main-window ()
  "Collapse the frame to one main window, tolerating side windows.
`delete-other-windows' errors with \"Cannot make side window the only
window\" when a side window (e.g. claude-code-ide's Claude pane) is
selected or present, so step off it and delete side windows first."
  (when (window-parameter (selected-window) 'window-side)
    (select-window (or (window-main-window) (frame-first-window))))
  (dolist (w (window-list nil 'nomini))
    (when (and (window-live-p w) (window-parameter w 'window-side))
      (ignore-errors (delete-window w))))
  (delete-other-windows))

(defun +dev/window-code ()
  "dev window 1: editor landing (see `+dev-code-landing') | Claude side window."
  (interactive)
  (+dev--single-main-window)
  (+dev--open-editor (+dev--root))
  ;; claude-code-ide places/toggles its own side window, scoped to the project
  ;; root of the current buffer's `default-directory', so no manual split.
  (claude-code-ide))

(defun +dev/window-console ()
  "dev window 2: `+dev-console-shells' ghostel shells side by side."
  (interactive)
  (let ((dir (+dev--root)))
    (+dev--single-main-window)
    (set-window-buffer (selected-window) (+dev--shell-buffer dir 1))
    (dotimes (i (1- +dev-console-shells))
      (let ((w (split-window-right)))
        (set-window-buffer w (+dev--shell-buffer dir (+ i 2)))
        (select-window w)))
    (balance-windows)
    (select-window (frame-first-window))))

(defun +dev--candidates ()
  "Selectable project dirs, mirroring tmux-sessionizer's sources."
  (delete-dups
   (append
    (cl-loop for parent in +dev-project-parents
             for p = (expand-file-name parent)
             when (file-directory-p p)
             append (cl-remove-if-not
                     #'file-directory-p (directory-files p t "\\`[^.]")))
    (cl-remove-if-not #'file-directory-p
                      (mapcar #'expand-file-name +dev-project-extras)))))

(defun +dev/setup-current-workspace (&optional dir)
  "Build the `dev' layout in the CURRENT workspace for DIR, unless already set up.
DIR defaults to the current project root. Idempotent: the presence of the
first console shell buffer marks a workspace as already laid out, so re-entry
(via sessionizer, harpoon, or SPC p p) never clobbers your windows."
  (interactive)
  (let* ((dir  (file-name-as-directory (expand-file-name (or dir (+dev--root)))))
         (name (+workspace-current-name)))
    (puthash name dir +dev--roots)
    (unless (get-buffer (format "*sh:%s:1*" name))
      ;; spawn the console shells up front so all servers are live, like `dev'
      (dotimes (i +dev-console-shells) (+dev--shell-buffer dir (1+ i)))
      (+dev/window-code))))

(defun +dev-open-project (dir)
  "Open DIR in its own workspace (create if new) and ensure the `dev' layout.
Shared core of the sessionizer and harpoon jumps; the Emacs tmux-project-open."
  (setq dir (file-name-as-directory (expand-file-name dir)))
  ;; Name the workspace after the project basename. Unlike tmux-project-open we
  ;; do NOT map "." -> "_" (that exists only because tmux session names can't
  ;; contain dots) — Emacs workspace names allow dots, and the mapping would
  ;; collide distinct projects like node.js / node_js onto one workspace.
  (let ((name (file-name-nondirectory (directory-file-name dir))))
    (+workspace-switch name t)
    (+dev/setup-current-workspace dir)))

(defun +dev/sessionizer (dir)
  "Pick project DIR, open it in its own workspace, and build the `dev' layout.
The Emacs analog of tmux-sessionizer (prefix + f)."
  (interactive (list (completing-read "project> " (+dev--candidates) nil t)))
  (+dev-open-project dir))

;; (a) Doom auto-creates a workspace on `projectile-switch-project' (SPC p p);
;; hook the same layout builder onto it so the native project switch also lays
;; out code+console. Guarded + idempotent (see `+dev/setup-current-workspace').
(defcustom +dev-auto-layout-on-switch t
  "If non-nil, SPC p p also builds the `dev' layout in the new project's
workspace. When nil, SPC p p keeps Doom's default (find file in project)."
  :type 'boolean :group 'doom)

;; Replace Doom's post-switch action rather than stacking a hook on it. Doom
;; runs `+workspaces-switch-project-function' (default `doom-project-find-file')
;; after creating the workspace on SPC p p; the old `projectile-after-switch-
;; project-hook' fired IN ADDITION to it (two prompts) and also fires twice
;; (doomemacs#6559). Overriding the function gives exactly one post-switch action.
(defun +dev-switch-project-h (dir)
  "Doom `+workspaces-switch-project-function' for SPC p p."
  (if +dev-auto-layout-on-switch
      (+dev/setup-current-workspace dir)
    (doom-project-find-file dir)))
(setq +workspaces-switch-project-function #'+dev-switch-project-h)

;;; --- harpoon: pin projects to numbered slots (ports tmux-harpoon) --------
;; A persistent, ordered list of project dirs. M-1..9 jump to a slot's project
;; (opening its workspace + dev layout on demand, surviving restarts). Reorder
;; or clear slots by editing the list file (SPC o h), exactly like the tmux menu.

(defcustom +harpoon-file
  (expand-file-name "doom-harpoon/list"
                    (or (getenv "XDG_DATA_HOME") (expand-file-name "~/.local/share")))
  "File of pinned project dirs, one absolute path per line (harpoon slots)."
  :type 'file :group 'doom)

(defun +harpoon--slots ()
  "Pinned project dirs, one per non-blank line in `+harpoon-file'."
  (when (file-readable-p +harpoon-file)
    (with-temp-buffer
      (insert-file-contents +harpoon-file)
      (split-string (buffer-string) "\n" t "[ \t]+"))))

(defun +harpoon--save (slots)
  "Write SLOTS (a list of dirs) back to `+harpoon-file'."
  (make-directory (file-name-directory +harpoon-file) t)
  (with-temp-file +harpoon-file
    (when slots (insert (mapconcat #'identity slots "\n") "\n"))))

(defun +harpoon/add ()
  "Pin the current workspace's project to the next free harpoon slot."
  (interactive)
  (let* ((dir   (directory-file-name (expand-file-name (+dev--root))))
         (slots (+harpoon--slots))
         (label (file-name-nondirectory dir)))
    (if-let* ((pos (cl-position dir slots :test #'string=)))
        (message "harpoon: %s already pinned (slot %d)" label (1+ pos))
      (+harpoon--save (append slots (list dir)))
      (message "harpoon: pinned %s -> slot %d" label (length (+harpoon--slots))))))

(defun +harpoon/jump (n)
  "Open the project pinned at harpoon slot N (1-based)."
  (interactive "p")
  (let ((slots (+harpoon--slots)))
    (if (<= 1 n (length slots))
        (+dev-open-project (nth (1- n) slots))
      (message "harpoon: slot %d is empty" n))))

(defun +harpoon/menu ()
  "Edit the harpoon slots: line N = slot N. Reorder to reorder, delete to clear."
  (interactive)
  (make-directory (file-name-directory +harpoon-file) t)
  (find-file +harpoon-file))

;; (b) M-1..9 jump to pinned harpoon projects (was Doom's workspace-switch-to-N).
;; Raw workspace nav still lives on gt/gT and the SPC TAB menu.
(map! "M-1" (cmd! (+harpoon/jump 1)) "M-2" (cmd! (+harpoon/jump 2))
      "M-3" (cmd! (+harpoon/jump 3)) "M-4" (cmd! (+harpoon/jump 4))
      "M-5" (cmd! (+harpoon/jump 5)) "M-6" (cmd! (+harpoon/jump 6))
      "M-7" (cmd! (+harpoon/jump 7)) "M-8" (cmd! (+harpoon/jump 8))
      "M-9" (cmd! (+harpoon/jump 9)))

;; Under the existing SPC o "open" prefix. prefix + f muscle memory -> SPC o p;
;; the two dev windows are SPC o 1 / SPC o 2 (SPC 1..9 is Doom's winum).
(map! :leader
      (:prefix ("o" . "open")
       :desc "Project session (sessionizer)" "p" #'+dev/sessionizer
       :desc "dev: window 1 (code)"          "1" (cmd! (+dev/window 1))
       :desc "dev: window 2 (console)"       "2" (cmd! (+dev/window 2))
       :desc "dev: window 3"                 "3" (cmd! (+dev/window 3))
       :desc "Harpoon: pin current project"  "a" #'+harpoon/add
       :desc "Harpoon: edit slots"           "h" #'+harpoon/menu))

;; Windows within a workspace (the tmux windows). An ordered, extensible list:
;; to add a 3rd, append e.g. ("scratch" . +dev/window-scratch) — then M-o 3
;; (or SPC o 3) snaps straight to it. No other code changes needed.
(defvar +dev-windows
  '(("code"    . +dev/window-code)
    ("console" . +dev/window-console))
  "Ordered layouts for a workspace (the tmux windows). Each is (NAME . BUILDER).")

(defun +dev--show-window (idx)
  "Build window IDX (0-based) of `+dev-windows'."
  (funcall (cdr (nth idx +dev-windows))))

(defun +dev/window (n)
  "Snap directly to window N (1-based) in the current workspace."
  (interactive "p")
  (if (<= 1 n (length +dev-windows))
      (+dev--show-window (1- n))
    (message "dev: no window %d (have %d)" n (length +dev-windows))))

(defun +dev/window-dwim ()
  "Snap to the dev window numbered by the digit key that invoked this."
  (interactive)
  (+dev/window (- last-command-event ?0)))

;; M-o is the window PREFIX (the tmux prefix analog): M-o 1 / M-o 2 / M-o 3 snap
;; DIRECTLY to that window — no cycling, exactly like tmux `prefix N'.
;; `last-command-event' carries the digit, so one command covers 1-9 without
;; closures. Bound in the evil states AND ghostel's own map, so M-o never
;; reaches the PTY and can't interrupt anything in a shell.
(defvar +dev-window-map
  (let ((m (make-sparse-keymap)))
    (dolist (d '("1" "2" "3" "4" "5" "6" "7" "8" "9"))
      (define-key m (kbd d) #'+dev/window-dwim))
    m)
  "Keymap under the M-o window prefix; digit 1-9 snaps to that dev window.")

(map! :nvime "M-o" +dev-window-map)
(after! ghostel
  (map! :map ghostel-semi-char-mode-map "M-o" +dev-window-map))

(setq org-agenda-files '("~/org"))

;; Wrap in `after! org' so this runs AFTER Doom's org module sets its own
;; default templates — a bare top-level `setq' loses the race and gets clobbered.
(after! org
  (setq org-capture-templates
        '(("t" "Task" entry (file "~/org/inbox.org")
           "* TODO %?\n  %U\n  %i"))))

(setq org-refile-targets '((org-agenda-files :maxlevel . 3)))

;;; ---------------------------------------------------------------------------
;;; Org-roam + md-roam — Obsidian-like notes over ~/.md files in ~/vault
;;; ---------------------------------------------------------------------------

;; Doom's `(org +roam2)' flag installs org-roam and binds its commands under the
;; `SPC n' / `C-c n' prefixes. We override `org-roam-directory' to ~/vault (the
;; existing Obsidian vault) and tell it to index `.md' alongside `.org'.

;; md-roam-mode MUST be active before the autosync scan or .md files never get
;; indexed — so require+enable it here, then re-trigger db-autosync after. On a
;; first run or after editing .md files outside Emacs, run
;;   M-x org-roam-db-clear-all RET ; M-x org-roam-db-sync RET
;; (Doom binds these under `SPC n' too: `SPC n d c' / `SPC n d s'.)
(setq org-roam-directory (file-truename "~/vault")
      org-roam-file-extensions '("org" "md"))

;; Load md-roam eagerly (not deferrable) so it's active BEFORE org-roam's
;; autosync scans files at startup. A `:after org-roam' here races with
;; doom's `org-load' hook in contrib/roam.el and loses — .md never indexes.
(use-package! md-roam
  :demand t
  :config
  (setq md-roam-file-extension "md")
  (md-roam-mode 1)
  (when (fboundp 'org-roam-db-autosync-mode)
    (org-roam-db-autosync-mode 1))
  ;; Doom's `+default/find-in-notes' (SPC n f) opens ~/org, not the roam
  ;; vault. Override the keybinding to point at `org-roam-node-find' once
  ;; org-roam is loaded, so SPC n f finds nodes across ~/vault.
  (after! org-roam
    (map! :leader :desc "Find roam node" "n f" #'org-roam-node-find
                     :desc "Insert roam node" "n i" #'org-roam-node-insert
                     :desc "Toggle backlinks" "n l" #'org-roam-buffer-toggle
                     :desc "Capture roam note" "n c" #'org-roam-capture)))
