;;; init.el -*- lexical-binding: t; -*-

;; Weekend test-drive config: port the nvim + tmux + Claude Code cockpit into a
;; single GUI Emacs (daemon) instance. Module choices mirror the nvim plugin set
;; in ~/dotfiles/nvim/.config/nvim/lua/plugins/.
;;
;; After changing this file or packages.el, run:  doom sync

(doom! :input

       :completion
       (vertico +icons)            ; snacks picker / fuzzy finder equiv (+ consult)
       (corfu +orderless +icons)   ; blink.cmp equiv

       :ui
       doom                        ; theme scaffolding
       doom-dashboard
       hl-todo
       ligatures                   ; font ligatures only; -extra (no import->↩, function->ƒ, return->⮐ word swaps)
       indent-guides               ; mini.indentscope equiv
       modeline                    ; custom statusline equiv
       ophints
       (popup +defaults)
       vc-gutter                   ; gitsigns equiv
       vi-tilde-fringe
       (window-select +numbers)
       workspaces                  ; tmux-session-like workspaces inside Emacs

       :editor
       (evil +everywhere)          ; vim everywhere incl. evil-collection (magit, dired, …)
       file-templates
       fold
       (format +onsave)            ; conform.nvim equiv (apheleia)
       snippets
       word-wrap

       :emacs
       (dired +icons)              ; oil.nvim equiv
       electric
       (undo +tree)                ; undotree equiv
       vc

       :term
       vterm                       ; real terminal backend for Claude Code

       :checkers
       (syntax +childframe)        ; nvim-lint / diagnostics equiv

       :tools
       (eval +overlay)
       lookup
       (lsp +peek)                 ; lspconfig + mason equiv
       (magit +forge)              ; fugitive + gitsigns + diffs, but better
       tree-sitter                 ; treesitter equiv

       :lang
       (emacs-lisp)
       (sh +lsp +tree-sitter)      ; bash-language-server + treesitter highlighting
       (lua +lsp)                  ; lua-language-server (lua_ls)
       (python +lsp +tree-sitter +pyright)
       (javascript +lsp +tree-sitter)  ; js/ts/jsx/tsx (ts-ls + eslint)
       (web +lsp)                  ; cssls + html-language-server
       (json +lsp)                 ; vscode-json-languageserver
       (yaml +lsp)                 ; yaml-language-server
       (markdown)                  ; markview equiv
       (org +roam2)                ; org-roam v2 — md-roam layered on top in config.el for ~/vault markdown

       :config
       (default +bindings +smartparens))
