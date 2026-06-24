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
;; the newest installed version's bin and prepend it. Update happens for free on
;; the next `nvm install` since it globs at startup.
(let ((node-bin (car (last (sort (file-expand-wildcards
                                  (expand-file-name "~/.nvm/versions/node/*/bin"))
                                 #'string<)))))
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
;;; Look & feel — Catppuccin Mocha + JuliaMono (icon glyphs via Symbols Nerd
;;; Font Mono)
;;; ---------------------------------------------------------------------------

;; JuliaMono — monospace with exceptionally broad Unicode coverage. Chosen for
;; one decisive reason: it natively contains the Dingbats block AND braille, so
;; Claude Code's thinking-spinner glyphs (✻ ✢ ✳ ✶ ✷ ✽ ⠋ ·) render IN the main
;; font rather than a fallback. No fallback = no jitter — neither the vertical
;; bounce (taller fallback box) nor the horizontal shimmy (proportional fallback
;; widths) that every Nerd Font tested here suffered. No dingbat pin.
;;
;; Icons: JuliaMono isn't a Nerd Font, so Doom's modeline/dashboard/dired/
;; completion icons come from "Symbols Nerd Font Mono" (installed via
;; `M-x nerd-icons-install-fonts'). A float :size is in POINTS (DPI-independent).
(setq doom-font (font-spec :family "JuliaMono" :size 19.0 :weight 'medium)
      doom-variable-pitch-font (font-spec :family "JuliaMono" :size 19.0 :weight 'medium))

;; DejaVu Sans Mono has no color-emoji glyphs, so emoji in Claude's output render
;; as tofu boxes. Point the `emoji' charset at a real color-emoji family when one
;; is installed (Arch: `pacman -S noto-fonts-emoji'). Guarded so it's a no-op
;; until the font exists — no error on a fresh machine.
(when-let ((emoji-font (seq-find (lambda (f) (member f (font-family-list)))
                                 '("Noto Color Emoji" "Twemoji" "OpenMoji"))))
  (set-fontset-font t 'emoji (font-spec :family emoji-font) nil 'prepend))

;; Extra vertical space between lines, in pixels (nil = none). Bump to taste.
(setq-default line-spacing 0.25)

;; Catppuccin Mocha. Flavor must be set before the theme loads.
(setq catppuccin-flavor 'mocha)
(setq doom-theme 'catppuccin)

;; Port the nvim `color_overrides` (theme.lua): Catppuccin Mocha but with the
;; OneDark-ish backgrounds, plus a uniform background (no solaire two-tone) to
;; match the nvim/tmux look.
;;
;; `+catppuccin-apply` is idempotent and recursion-guarded, so it works both at
;; startup (via doom-load-theme-hook, before the first GUI frame) AND on a live
;; `doom/reload` / `SPC h r r` (the immediate call at the bottom, when the theme
;; is already loaded). It removes Doom's `(doom-load-theme . solaire-global-mode)`
;; enabler so the reload below won't bring solaire back.
;;
;; NOTE: the large `custom_highlights` block in theme.lua is nvim-plugin-specific
;; (BlinkCmp*, SnacksPicker*, MiniClue*, GitSigns*, …) and has no Emacs
;; equivalent — only these base/mantle/crust overrides carry over.
(defvar +catppuccin--applying nil)
(defun +catppuccin-apply (&rest _)
  "Apply nvim base/mantle/crust overrides and force a uniform background."
  (unless +catppuccin--applying
    (let ((+catppuccin--applying t))
      ;; uniform bg: stop Doom re-enabling solaire on theme loads, turn it off now
      (remove-hook 'doom-load-theme-hook #'solaire-global-mode)
      (when (bound-and-true-p solaire-global-mode) (solaire-global-mode -1))
      ;; palette overrides (only once the theme's color alist exists)
      (when (boundp 'catppuccin-mocha-colors)
        (catppuccin-set-color 'base   "#282c34" 'mocha)
        (catppuccin-set-color 'mantle "#21252b" 'mocha)
        (catppuccin-set-color 'crust  "#1b1f27" 'mocha)
        (catppuccin-reload)))))

(add-hook 'doom-load-theme-hook #'+catppuccin-apply)
;; live reload: theme is already loaded, so apply right away
(when (memq 'catppuccin custom-enabled-themes) (+catppuccin-apply))

(setq display-line-numbers-type 'relative)   ; matches nvim relativenumber

;; The split divider ships near-invisible (Catppuccin sets its fg ~= the bg).
;; Bump it to a mid gray that reads against the OneDark base #282c34 but stays
;; subtle. `vertical-border' is the 1-col line between side-by-side windows;
;; the window-divider faces cover Doom's thicker dividers if enabled.
;; custom-set-faces! re-applies on every theme load, so the catppuccin reload
;; in +catppuccin-apply above won't clobber it.
(custom-set-faces!
  '(vertical-border            :foreground "#5c6370")
  '(window-divider             :foreground "#5c6370")
  '(window-divider-first-pixel :foreground "#5c6370")
  '(window-divider-last-pixel  :foreground "#5c6370")
  ;; flycheck's wavy error underline defaults to pure Red1 (#FF0000) — too hot
  ;; against the Mocha base. Soften to Catppuccin red, matching the echo-area
  ;; error message color so the two read as one signal. Keeps the wave style.
  '(flycheck-error :underline (:style wave :color "#f38ba8")))

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

;; vterm (the Claude Code backend) forwards nearly every key straight to the
;; terminal, so the global M-hjkl above never fires while focused in the Claude
;; pane — the keys get swallowed by the TUI. (C-hjkl nav works in there only
;; because C-h/C-l are in vterm's default keep-in-Emacs exceptions.) Reclaim the
;; resize chords in vterm-mode-map so they resize the window instead of being
;; sent to Claude. Once one fires, repeat-mode's transient map outranks vterm,
;; so bare h/j/k/l keep repeating in the Claude pane too.
(after! vterm
  (map! :map vterm-mode-map
        "M-h" #'shrink-window-horizontally
        "M-l" #'enlarge-window-horizontally
        "M-j" #'enlarge-window
        "M-k" #'shrink-window)
  ;; Paste into the Claude prompt the vim way. vterm only routes `yank' (C-y)
  ;; through `vterm-yank' (which sends kill-ring text to the PTY); evil's `p'
  ;; and `C-v' don't, so they silently fail. Wire normal-state `p' and an
  ;; insert-state `C-v' straight to `vterm-yank' so clipboard paste just works.
  (map! :map vterm-mode-map
        :n "p" #'vterm-yank
        :i "C-v" #'vterm-yank)

  ;; Right-edge cutoff fix: vterm clamps the PTY to `vterm-min-window-width'
  ;; (default 80) — `(max width vterm-min-window-width)' in vterm.el. So when you
  ;; shrink the Claude split below 80 cols, the PTY stays at 80 while the window
  ;; is narrower, and Claude's 80-col lines overflow and get sliced at the right
  ;; edge. Lower the floor so the PTY reflows down to match a shrunk window.
  (setq vterm-min-window-width 40)

  ;; Height sync fix: vterm's default size function
  ;; (`window-adjust-process-window-size-smallest') derives the pty row count
  ;; from `window-screen-lines', which divides the window body by the font's
  ;; intrinsic line-box height (char-cell + the font's built-in leading).
  ;; libvterm, though, lays out rows at `frame-char-height' (the pure char
  ;; cell). When a font's line-box exceeds its char-cell — common with fonts
  ;; that ship extra leading — screen-lines under-reports rows vs what libvterm
  ;; actually paints, so the pty is too short and full-screen TUIs (opencode,
  ;; btop, htop) render with a band of blank space below. Swap in a size
  ;; function that derives height from `window-text-height' (char-cell math,
  ;; matching libvterm's row layout). Symmetric to the width floor above.
  (defun +vterm/adjust-window-size-charcell (process windows)
    "Size PROCESS pty from char-cell metrics, not the font line-box.
Like `window-adjust-process-window-size-smallest' but uses
`window-text-height' / `window-body-width' (char-cell counts that
match libvterm's row layout) instead of `window-screen-lines' (which
bakes in the font's leading and under-reports rows)."
    (let ((width most-positive-fixnum)
          (height most-positive-fixnum))
      (dolist (w windows)
        (setq width  (min width  (window-body-width w)))
        (setq height (min height (window-text-height w))))
      (when (and (< width most-positive-fixnum)
                 (< height most-positive-fixnum))
        (cons width height))))
  (add-hook 'vterm-mode-hook
            (lambda ()
              (setq-local window-adjust-process-window-size-function
                          #'+vterm/adjust-window-size-charcell)))

  ;; Redraw throughput: vterm coalesces redraws on `vterm-timer-delay' (default
  ;; 0.1s = 100ms = 10fps) — app-streamed output (opencode's spinner, streaming
  ;; tokens, btop's gauges) only redraws when that timer fires, because the
  ;; immediate-redraw flag is set only by key sends, not by output arriving on
  ;; the process filter. tmux/zsh write straight to a rigid cell grid, so they
  ;; feel instant; vterm goes libvterm → Emacs buffer → redisplay with per-line
  ;; elastic glyph metrics (see the spinner-jitter note), which is inherently
  ;; heavier, and the 100ms cap makes it visibly choppy. Drop to 10ms (~100fps
  ;; ceiling) — bursts still coalesce within a frame, interactive output is
  ;; imperceptibly latent. Nil would redraw on every invalidation (maximally
  ;; responsive but can thrash on `cat`-style bursts); 0.01 is the sweet spot.
  (setq vterm-timer-delay 0.01)

  ;; Overlay shedding: `global-hl-line-mode' and `show-paren-mode' are on
  ;; globally and add per-redraw overlay work (highlight the cursor line, scan
  ;; for parens). Both are useless in a terminal buffer — there are no code
  ;; parens to match and no useful line highlight on app-rendered cells — but
  ;; they keep recomputing every redisplay. Disable them buffer-locally.
  (add-hook 'vterm-mode-hook
            (lambda ()
              (setq-local global-hl-line-mode nil)
              (setq-local show-paren-mode nil)))

  ;; Mouse wheel forwarding: Emacs' global `mouse-wheel-mode' binds
  ;; [wheel-up]/[wheel-down]/[mouse-4]/[mouse-5] to `mwheel-scroll', which
  ;; scrolls the vterm window's scrollback — but when a TUI app (opencode,
  ;; btop) has enabled mouse reporting, you want the wheel to reach the app so
  ;; it scrolls its own view. vterm has no native mouse-forwarding (only
  ;; click-to-point), so bind the wheel events in `vterm-mode-map' to commands
  ;; that translate each notch into an SGR mouse sequence (\e[<BTN;COL;ROWM)
  ;; and feed it to the pty. BTN 64 = wheel up, 65 = wheel down (xterm SGR
  ;; 1006, which opencode/Bubble Tea speaks). COL and ROW are 1-based, derived
  ;; from the pointer's pixel position divided by `frame-char-{width,height}'
  ;; — char-cell math matching libvterm's row layout (same alignment as the
  ;; height fix above). Gate on `vterm-copy-mode' so entering scrollback (C-')
  ;; restores Emacs-side wheel scrolling.
  (defun +vterm/mouse-wheel-forward (event button)
    "Forward mouse wheel EVENT to the pty as an SGR mouse sequence.
BUTTON is 64 (up) or 65 (down).  Writes directly to the pty via
`process-send-string' (the same fast path `vterm-send-return' uses)
rather than `vterm-send-string', which ends with a sync
`accept-process-output' round-trip — that blocks up to
`vterm-timer-delay' per notch and makes rapid wheel scrolling janky.
With the direct write, notches fire instantly and the app's render
response arrives on the process filter, redrawing on the (now 10ms)
timer.  In `vterm-copy-mode', scroll the Emacs window instead so
scrollback nav keeps working."
    (interactive "e")
    (if (bound-and-true-p vterm-copy-mode)
        (mwheel-scroll event)
      (let* ((pos (event-start event))
             (xy (posn-x-y pos))
             (frame (window-frame (posn-window pos)))
             (col (1+ (/ (car xy) (frame-char-width frame))))
             (row (1+ (/ (cdr xy) (frame-char-height frame)))))
        (process-send-string vterm--process
                             (format "\e[<%d;%d;%dM" button col row)))))
  (defun +vterm/mouse-wheel-up (event)
    "Forward wheel-up to the pty as SGR mouse button 64."
    (interactive "e")
    (+vterm/mouse-wheel-forward event 64))
  (defun +vterm/mouse-wheel-down (event)
    "Forward wheel-down to the pty as SGR mouse button 65."
    (interactive "e")
    (+vterm/mouse-wheel-forward event 65))
  (map! :map vterm-mode-map
        [wheel-up]   #'+vterm/mouse-wheel-up
        [wheel-down] #'+vterm/mouse-wheel-down
        [mouse-4]    #'+vterm/mouse-wheel-down
        [mouse-5]    #'+vterm/mouse-wheel-up)

  ;; Redraw fix: the global `line-spacing' 0.25 we set above (nice for prose)
  ;; makes vterm leave cursor trails and stale rows — libvterm lays out on tight
  ;; line boxes and the extra pixels desync it. Zero it out in terminal buffers.
  (add-hook 'vterm-mode-hook (lambda () (setq-local line-spacing nil)))

  ;; Show the evil state in the Claude window. Doom hides the modeline in every
  ;; vterm buffer via `mode-line-invisible-mode' on `vterm-mode-hook', which also
  ;; swallows the doom-modeline modal (NORMAL/INSERT) indicator — that's why you
  ;; can't tell your mode here, even though it shows fine in code buffers. Drop
  ;; that hook and give vterm the compact `minimal' modeline instead (bar +
  ;; modal state + buffer name), which fits the narrow side window.
  (remove-hook 'vterm-mode-hook #'mode-line-invisible-mode)
  (defun +vterm/use-minimal-modeline-h ()
    "Give vterm a compact modeline that still surfaces the evil state."
    (doom-modeline-set-modeline 'minimal))
  (add-hook 'vterm-mode-hook #'+vterm/use-minimal-modeline-h 90)

  ;; Cursor shape per evil state in the Claude window. This vterm build never
  ;; touches `cursor-type', so evil CAN own the cursor here — it just doesn't
  ;; auto-refresh on state change in vterm the way it does in code buffers
  ;; (verified: state was `insert' but cursor stayed `box' until a manual
  ;; `evil-refresh-cursor'). So refresh it on each state entry buffer-locally,
  ;; and once on open. Catppuccin colors make the box/bar switch unmissable.
  (setq evil-normal-state-cursor '(box "#89b4fa")      ; blue block
        evil-insert-state-cursor '(bar "#a6e3a1")      ; green beam
        evil-visual-state-cursor '(hollow "#f9e2af"))  ; yellow hollow
  (defun +vterm/track-evil-cursor-h ()
    "Refresh the evil cursor on state changes in vterm (no auto-refresh here)."
    (dolist (hook '(evil-normal-state-entry-hook
                    evil-insert-state-entry-hook
                    evil-visual-state-entry-hook
                    evil-operator-state-entry-hook))
      (add-hook hook #'evil-refresh-cursor nil t))
    (evil-refresh-cursor))
  (add-hook 'vterm-mode-hook #'+vterm/track-evil-cursor-h)

  ;; Image paste: vterm/claude-code-ide only move text through the PTY, so a
  ;; clipboard image can't be piped in like in a GUI terminal. Instead dump the
  ;; Wayland clipboard image to a temp PNG and type its path at the prompt —
  ;; Claude Code reads local image files referenced by path. Insert-state C-S-v.
  (defun +claude/vterm-paste-clipboard-image ()
    "Save a Wayland clipboard image to a temp PNG and insert its path at point."
    (interactive)
    (unless (string-match-p "image/" (shell-command-to-string "wl-paste --list-types 2>/dev/null"))
      (user-error "No image on the clipboard"))
    (let ((file (make-temp-file "claude-clip-" nil ".png")))
      (call-process-shell-command
       (format "wl-paste --type image/png > %s" (shell-quote-argument file)))
      (vterm-send-string file)
      (message "Pasted image path: %s" file)))
  (map! :map vterm-mode-map
        :i "C-S-v" #'+claude/vterm-paste-clipboard-image)

  ;; Keyboard-native scrollback for a vim brain. `vterm-copy-mode' freezes the
  ;; view (so streaming output stops yanking point to the bottom) and turns the
  ;; buffer into a read-only nav buffer. The one real gap: Doom leaves you in evil
  ;; INSERT state there, where hjkl self-insert and motions are dead. Switch to
  ;; NORMAL on entry — then k/j/C-u/C-d/gg/G/`/' all work (vim AND tmux copy-mode
  ;; muscle memory) — and back to INSERT on exit to resume typing to Claude.
  (defun +vterm/copy-mode-evil-state-h ()
    "Evil normal state inside `vterm-copy-mode', insert state outside it."
    (if (bound-and-true-p vterm-copy-mode) (evil-normal-state) (evil-insert-state)))
  (add-hook 'vterm-copy-mode-hook #'+vterm/copy-mode-evil-state-h)
  ;; Enter scrollback with one free chord: `C-'' is unbound in insert state, in
  ;; vterm-mode-map, and globally, so this fills a blank rather than shadowing a
  ;; load-bearing key. `q' quits (tmux habit + idiomatic special-buffer quit);
  ;; `C-c C-t' and RET still work too. C-' lives in vterm-mode-map, which is
  ;; shadowed once copy-mode is active, so it's enter-only — exit via `q'.
  (map! :map vterm-mode-map "C-'" #'vterm-copy-mode
        :map vterm-copy-mode-map :n "q" #'vterm-copy-mode-done)

  ;; Send Escape to Claude with a second Esc. Claude clears the input draft on
  ;; Escape, but evil eats bare ESC in insert state (→ normal state) so it never
  ;; reaches the PTY. `<escape>' (the GUI key — distinct from the ESC/Meta prefix
  ;; that powers M-x etc.) is idle in evil normal state (just re-asserts normal),
  ;; so rebinding it there — in vterm only — to send a real Escape makes "ESC ESC"
  ;; from insert = clear the prompt. `i' to start typing again. (Caveat: spamming
  ;; ESC in normal state now sends repeated escapes to Claude, which is its
  ;; double-Esc rewind menu — see the single-chord alternative if that bites.)
  (map! :map vterm-mode-map :n "<escape>" #'vterm-send-escape))

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

;; THE actual reason TSX looked flat: tsx-ts-mode *does* face parameters, `const`
;; bindings, and imports — but all with `font-lock-variable-name-face`, which
;; catppuccin-theme paints `text` (#cdd6f4 ≈ default fg), so they read as
;; uncolored. nvim-treesitter avoids this by giving `@variable.parameter` its own
;; maroon. Emacs's face set can't split param from binding (they share one face),
;; so recolor that shared face to Catppuccin maroon — params and bindings now
;; pop like nvim. custom-set-faces! re-applies on every theme load, so the
;; +catppuccin-apply reload above won't clobber it.
(custom-set-faces!
  '(font-lock-variable-name-face :foreground "#eba0ac"))   ; Catppuccin Mocha maroon

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
;;; Flycheck — inline diagnostics, colored by severity (popup-tip)
;;; ---------------------------------------------------------------------------

;; The diagnostic that rendered WHITE is `flycheck-popup-tip' — an inline popup.el
;; overlay (it reflows the buffer text below point; a posframe childframe would
;; overlay WITHOUT reflowing, which is how we know it's popup-tip, not posframe).
;; Two problems with the stock setup:
;;
;;   1. Doom's `+syntax-init-popups-h' tries to pick posframe vs popup-tip vs
;;      nothing (it no-ops under lsp-ui) — non-deterministic, and posframe won't
;;      even draw in a narrow window (Claude docked right). We don't want the
;;      guesswork: remove that picker and always use popup-tip, which is an
;;      overlay that ALWAYS draws regardless of window width.
;;   2. `flycheck-popup-tip-format-errors' paints the whole message with ONE flat
;;      `popup-tip-face' (flycheck-popup-tip.el:85-94) — no per-severity color, so
;;      under Catppuccin's dark `popup-tip-face' every error is white. Override it
;;      to propertize each line by level: red error / yellow warn / lavender info,
;;      the same ladder the nvim diagnostics use (theme.lua).
(after! flycheck
  (remove-hook 'flycheck-mode-hook #'+syntax-init-popups-h)
  (add-hook 'flycheck-mode-hook #'flycheck-popup-tip-mode))

(after! flycheck-popup-tip
  (defun flycheck-popup-tip-format-errors (errors)
    "Color each ERROR line by severity instead of one flat `popup-tip-face'."
    (let ((lines (mapcar
                  (lambda (err)
                    (let ((color (pcase (flycheck-error-level err)
                                   ('error   "#f38ba8")   ; Catppuccin red
                                   ('warning "#f9e2af")   ; yellow
                                   (_        "#b4befe")))) ; lavender (info)
                      (propertize (concat flycheck-popup-tip-error-prefix
                                          (flycheck-error-format-message-and-id err))
                                  'face `(:foreground ,color))))
                  (delete-dups errors))))
      (mapconcat #'identity (sort lines #'string-lessp) "\n"))))

;; INSURANCE: if a buffer is still rendering through `flycheck-posframe' (its
;; per-severity faces inherit `default' = white), color those too — via
;; `set-face-attribute' inside `after!' so it runs WHEN the package loads, not on
;; the theme hook (custom-set-faces! can miss lazily-loaded faces). Whichever
;; renderer a given buffer ended up with, the diagnostic is now colored.
(after! flycheck-posframe
  (set-face-attribute 'flycheck-posframe-error-face   nil :foreground "#f38ba8")
  (set-face-attribute 'flycheck-posframe-warning-face nil :foreground "#f9e2af")
  (set-face-attribute 'flycheck-posframe-info-face    nil :foreground "#b4befe"))

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

(after! magit
  ;; Word-level highlighting within hunks. (No magit-delta: it breaks
  ;; `magit-diff-visit-file' / RET with "Search failed" because delta rewrites
  ;; the diff text magit searches against. Step into the real file for tree-sitter.)
  (setq magit-diff-refine-hunk 'all))

;; Deep-review mode: after RET'ing into a file from magit, walk the diff in the
;; real (tree-sitter'd) buffer. vc-gutter is diff-hl under the hood.
;;   ]c / [c  step through hunks (vim :Gdiffsplit muscle memory; ]d/[d also work)
;;   =        pop the hunk's diff inline  (we have format-on-save, so the evil
;;            `=' indent operator is expendable here)
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
(defface +diff-hl-line-insert '((t :background "#26402b" :extend t))
  "gitsigns-style line wash for inserted lines.")
(defface +diff-hl-line-change '((t :background "#2b3650" :extend t))
  "gitsigns-style line wash for changed lines.")
(defface +diff-hl-line-delete '((t :background "#48262b" :extend t))
  "gitsigns-style line wash anchoring deleted lines.")

(defvar +diff-hl-inline-enabled t
  "When non-nil, wash diff-hl hunk overlays with a line background.")

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

;; gitsigns deleted-line preview for Emacs ------------------------------------
;; The wash above only colors lines that still EXIST. To "see what was removed"
;; (gitsigns deleted-preview, toggled with `='), render the removed lines as
;; phantom virtual lines ABOVE where they were, fontified in the buffer's OWN
;; major mode (so treesit highlights them) with a red `:extend' background
;; layered UNDER the syntax foreground. diff-hl-show-hunk's inline backend can't
;; do this (it strips faces and repaints lines flat), so we build it directly on
;; `diff-hl-changes-buffer' — the raw unified diff vs the reference revision.
(defface +diff-hl-deleted-face '((t :background "#48262b" :extend t))
  "Background for inline removed lines; fg nil so syntax shows through.")

(defvar-local +diff-hl-deleted--overlays nil
  "Phantom overlays currently showing removed lines in this buffer.")
(defvar-local +diff-hl-deleted-showing nil
  "Non-nil when inline removed-line previews are active in this buffer.")
(defvar-local +diff-hl-deleted--timer nil
  "Debounce timer for re-rendering removed-line previews.")

(defun +diff-hl-deleted--clear ()
  "Remove all phantom removed-line overlays from the current buffer."
  (mapc #'delete-overlay +diff-hl-deleted--overlays)
  (setq +diff-hl-deleted--overlays nil))

(defun +diff-hl-deleted--fontify (text mode)
  "Return TEXT fontified as if it were source in MODE (treesit-aware).
`delay-mode-hooks' keeps lsp/flycheck/etc. from activating in the scratch buffer."
  (condition-case nil
      (with-temp-buffer
        (insert text)
        (delay-mode-hooks (funcall mode))
        (font-lock-ensure)
        (buffer-string))
    (error text)))

(defun +diff-hl-deleted--block-string (lines mode)
  "Build the phantom string for removed LINES, fontified in MODE with a red bg."
  (let ((s (concat (+diff-hl-deleted--fontify (string-join lines "\n") mode) "\n")))
    ;; Prepend (not set) the bg so the syntax foreground underneath still wins.
    (font-lock-prepend-text-property 0 (length s) 'face '+diff-hl-deleted-face s)
    s))

(defun +diff-hl-deleted--collect (file backend)
  "Return a list of (NEW-LINE . REMOVED-LINES) blocks parsed from FILE's diff."
  (let ((diff-hl-update-async nil)          ; force the diff to run synchronously
        (blocks nil))
    (with-current-buffer (diff-hl-changes-buffer file backend)
      (goto-char (point-min))
      (while (re-search-forward
              "^@@ -[0-9]+\\(?:,[0-9]+\\)? \\+\\([0-9]+\\)\\(?:,[0-9]+\\)? @@" nil t)
        (let ((new-line (string-to-number (match-string 1)))
              (removed nil))
          (forward-line 1)
          (while (and (not (eobp)) (not (looking-at "^@@")))
            (cond
             ((looking-at "^-\\(.*\\)$")          ; removed line: collect, don't advance
              (push (match-string 1) removed))
             (t                                   ; context/added: flush, then advance
              (when removed
                (push (cons new-line (nreverse removed)) blocks)
                (setq removed nil))
              (when (memq (char-after (line-beginning-position)) '(?\s ?+))
                (setq new-line (1+ new-line)))))
            (forward-line 1))
          (when removed                           ; removals at the tail of the hunk
            (push (cons new-line (nreverse removed)) blocks)))))
    (nreverse blocks)))

(defun +diff-hl-deleted--render ()
  "Render removed lines for the current buffer as phantom virtual lines."
  (+diff-hl-deleted--clear)
  (let* ((file (buffer-file-name))
         (backend (and file (vc-backend file)))
         (mode major-mode))
    (when backend
      (dolist (block (+diff-hl-deleted--collect file backend))
        (save-excursion
          (goto-char (point-min))
          (forward-line (1- (car block)))
          (let ((ov (make-overlay (line-beginning-position) (line-beginning-position))))
            (overlay-put ov 'before-string
                         (+diff-hl-deleted--block-string (cdr block) mode))
            (overlay-put ov '+diff-hl-deleted t)
            (push ov +diff-hl-deleted--overlays)))))))

(defun +diff-hl-deleted--maybe-refresh (&rest _)
  "Debounced re-render of phantoms after a diff-hl update, when active."
  (when +diff-hl-deleted-showing
    (when (timerp +diff-hl-deleted--timer) (cancel-timer +diff-hl-deleted--timer))
    (let ((buf (current-buffer)))
      (setq +diff-hl-deleted--timer
            (run-with-idle-timer
             0.3 nil
             (lambda ()
               (when (buffer-live-p buf)
                 (with-current-buffer buf
                   (when +diff-hl-deleted-showing
                     (ignore-errors (+diff-hl-deleted--render)))))))))))

(defun +diff-hl-toggle-deleted ()
  "Toggle gitsigns-style inline preview of removed lines (treesit + red bg)."
  (interactive)
  (setq +diff-hl-deleted-showing (not +diff-hl-deleted-showing))
  (if +diff-hl-deleted-showing
      (+diff-hl-deleted--render)
    (+diff-hl-deleted--clear))
  (message "diff-hl removed-line preview %s"
           (if +diff-hl-deleted-showing "on" "off")))

(after! diff-hl
  ;; Show staged changes too (review-from-magit workflow stages first).
  (setq diff-hl-show-staged-changes t)
  ;; Paint the hunk lines after every (sync or async) overlay refresh.
  (advice-add 'diff-hl--update-overlays :after #'+diff-hl-paint-hunks)
  ;; Keep the removed-line phantoms in sync as you edit (debounced).
  (advice-add 'diff-hl--update :after #'+diff-hl-deleted--maybe-refresh)
  (map! :n "] c" #'diff-hl-next-hunk
        :n "[ c" #'diff-hl-previous-hunk
        :n "="   #'+diff-hl-toggle-deleted        ; toggle inline removed-line preview (treesit + red)
        :n "g L" #'+diff-hl-toggle-inline         ; toggle the ambient line wash (linehl)
        :n "g h" #'diff-hl-show-hunk              ; rich floating posframe popup (fallback)
        :n "g =" #'+git-diff-file-highlighted     ; full-file side-buffer syntax diff
        :n "-"   #'+vc-gutter/stage-hunk))   ; fugitive-style stage hunk at point

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

;; Make ediff look like vim's :Gdiffsplit: red = old/removed (buffer A), green =
;; new/added (buffer B), BACKGROUND-ONLY so treesitter foreground shows through
;; instead of ediff's flat opaque "peach" wash. `nil' foreground = inherit the
;; char's own syntax color. Catppuccin-ish reds/greens.
(custom-set-faces!
  '(ediff-current-diff-A :background "#48262b" :foreground nil :extend t)   ; removed line
  '(ediff-fine-diff-A    :background "#6e353d" :foreground nil)             ; exact removed text
  '(ediff-current-diff-B :background "#26402b" :foreground nil :extend t)   ; added line
  '(ediff-fine-diff-B    :background "#365a3d" :foreground nil)             ; exact added text
  '(ediff-even-diff-A    :background "#3a2c2e" :foreground nil :extend t)
  '(ediff-odd-diff-A     :background "#3a2c2e" :foreground nil :extend t)
  '(ediff-even-diff-B    :background "#2c3a2e" :foreground nil :extend t)
  '(ediff-odd-diff-B     :background "#2c3a2e" :foreground nil :extend t))

;;; ---------------------------------------------------------------------------
;;; Claude Code — the cockpit centerpiece
;;; ---------------------------------------------------------------------------

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
         :desc "Claude: paste clipboard image"   "v" #'+claude/vterm-paste-clipboard-image
         :desc "Claude: list sessions"           "L" #'claude-code-ide-list-sessions
         :desc "Claude: stop session"            "q" #'claude-code-ide-stop))
  ;; Upstream-style global chord, bound to the real entry command.
  (map! "C-c C-'" #'claude-code-ide)
  :config
  ;; vterm renders Claude's TUI colors better than the eat backend.
  (setq claude-code-ide-terminal-backend 'vterm)
  ;; Expose Emacs editor tools (xref, diagnostics, etc.) to Claude over MCP.
  (claude-code-ide-emacs-tools-setup))

(setq org-agenda-files '("~/org"))

(setq org-capture-templates
      '(("t" "Task" entry (file "~/org/inbox.org")
         "* TODO %?\n  %U\n  %i")))

(setq org-refile-targets '((org-agenda-files :maxlevel . 3))))

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

(use-package! md-roam
  :after org-roam
  :config
  (setq md-roam-file-extension "md")
  (md-roam-mode 1)
  ;; Re-arm autosync AFTER md-roam is active so the first scan picks up .md.
  (when (fboundp 'org-roam-db-autosync-mode)
    (org-roam-db-autosync-mode 1)))
