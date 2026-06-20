-- snacks.nvim — image, zen, scratch, terminal, and gitbrowse keymaps.
--
-- image: renders markdown image links and ```mermaid fences inline via the
-- Kitty Graphics Protocol. Degrades gracefully when dependencies are absent.
--
-- zen: centered floating window for focused reading. Width is 120 (the zen
-- default) — fits most markdown tables; render-markdown tables shatter when
-- soft-wrap splits a row, so wider matters more than ideal prose measure.
-- Revert to 100 if prose comfort wins.
--
-- Runtime binary deps (image):
--   ImageMagick — installed via install/deps on all platforms
--   mermaid-cli — npm-only, manual install: npm i -g @mermaid-js/mermaid-cli (mmdc binary)
--
-- Terminals: kitty and ghostty support Kitty Graphics Protocol.
-- WSL does NOT support it — images will not render there.
--
-- tmux: requires `set -g allow-passthrough on` in .tmux.conf (see tmux/.tmux.conf).
--
-- render-markdown.nvim coexists without conflict: it handles text decoration
-- (headings, bullets, tables), snacks.image handles pixel-level graphics.
-- No render-markdown options need changing.
--
-- Math/LaTeX rendering is disabled (math.enabled = false) — requires tectonic
-- or pdflatex which are not part of this setup.
return {
  src = "folke/snacks.nvim",
  setup = function()
    require("snacks").setup({
      -- bigfile: above ~1.5MB, disable the expensive per-buffer machinery
      -- (treesitter highlight + foldexpr folds, LSP attach, etc.) so opening a
      -- minified bundle, a huge lockfile, or a generated dump doesn't freeze the
      -- editor. No-op on normal files.
      bigfile = { enabled = true },
      -- picker: fuzzy finder (replaced mini.pick + mini.extra + mini.visits).
      -- Telescope-style layout — narrow result list + preview pane — so grep
      -- hits show the matched line, not just long monorepo paths. ui_select
      -- defaults to true: enabling the picker also routes vim.ui.select through
      -- it (code-action / rename / obsidian / oil prompts), replacing the old
      -- MiniPick.ui_select wiring. Keymaps live below.
      picker = {
        ui_select = true,
        -- <C-d>/<C-u> scroll the PREVIEW (snacks defaults them to list half-page
        -- scroll; preview scroll lives on <C-f>/<C-b>). Override per-window so
        -- they hit the preview whether focus is in the input or the list — snacks
        -- merges these key-by-key, so every other default binding is preserved.
        win = {
          input = {
            keys = {
              ["<c-d>"] = { "preview_scroll_down", mode = { "i", "n" } },
              ["<c-u>"] = { "preview_scroll_up", mode = { "i", "n" } },
            },
          },
          list = {
            keys = {
              ["<c-d>"] = "preview_scroll_down",
              ["<c-u>"] = "preview_scroll_up",
            },
          },
        },
      },
      image = {
        enabled = true,
        math = { enabled = false },
      },
      zen = {
        -- dim is off: we don't need the dim module and don't want other windows
        -- darkened — pane zoom already provides visual isolation.
        toggles = { dim = false },
        win = { style = "zen", width = 120 },
        -- on_close: every exit path (q, <leader>z, :q, prefix-m) triggers this;
        -- cleanup restores readonly/modifiable and removes the q map.
        on_close = function(_win)
          require("util.reading").cleanup()
        end,
      },
      -- terminal: toggleable bottom-split terminal keyed by cwd (one per
      -- project). A split (not a float) so smart-splits <C-hjkl> can navigate
      -- between it and your code windows — floats sit outside the split tree.
      terminal = {
        win = {
          position = "bottom",
          height = 0.3,
        },
      },
    })

    -- Toggle zen mode: centered 120-col window, pairs with tmux prefix-m zoom.
    vim.keymap.set("n", "<leader>z", function()
      Snacks.zen()
    end, { desc = "Zen mode (centered, width-capped)" })

    -- Delete the current buffer without disturbing the window layout. Snacks owns
    -- this now (replaced mini.bufremove); a modified buffer prompts rather than
    -- silently discarding.
    vim.keymap.set("n", "<leader>bd", function()
      Snacks.bufdelete()
    end, { desc = "Delete buffer" })

    -- Terminal toggle, keyed by cwd (one float per project). Lives in the
    -- <leader>t tasks namespace as <leader>tt — "tasks → terminal".
    vim.keymap.set("n", "<leader>tt", function()
      Snacks.terminal()
    end, { desc = "Toggle terminal (cwd)" })

    -- Dismiss-from-inside uses a chord, not <leader>: in terminal mode <leader>
    -- (space) would intercept every space you type in the shell. <C-/> (sent as
    -- <C-_> by kitty/ghostty) hides the terminal split without leaving insert.
    for _, key in ipairs({ "<C-/>", "<C-_>" }) do
      vim.keymap.set("t", key, function()
        Snacks.terminal()
      end, { desc = "Hide terminal" })
    end

    -- scratch: persistent per-project scratch buffers, keyed by cwd + branch +
    -- filetype (stored in stdpath("data")/scratch). The scratch inherits the
    -- current buffer's filetype (markdown fallback); lua scratches get <cr> to
    -- source the buffer. <leader>. is taken by picker-resume, so toggle lives
    -- on <leader>S and select joins the <leader>f find namespace.
    vim.keymap.set("n", "<leader>S", function()
      Snacks.scratch()
    end, { desc = "Toggle scratch buffer" })

    vim.keymap.set("n", "<leader>fs", function()
      Snacks.scratch.select()
    end, { desc = "Find scratch buffer" })

    -- gitbrowse keymaps — replaced gitlinker.nvim.
    -- gitbrowse defaults to what = "commit" (commit-pinned permalink URLs),
    -- matching the permalink behavior gitlinker provided.
    vim.keymap.set({ "n", "v" }, "<leader>go", function()
      Snacks.gitbrowse()
    end, { desc = "Open git permalink in browser" })

    vim.keymap.set({ "n", "v" }, "<leader>yg", function()
      Snacks.gitbrowse({
        open = function(url)
          vim.fn.setreg("+", url)
          vim.notify("Copied: " .. url)
        end,
        notify = false,
      })
    end, { desc = "Yank git permalink" })

    -- ── picker keymaps (ported 1:1 from the old mini.pick layout) ──────────────
    -- Show hidden files + gitignored dotfiles (.env, .env.local) but exclude junk
    -- dirs (node_modules, dist, caches…). hidden → --hidden, ignored → --no-ignore;
    -- exclude globs come from util.search (shared with grepprg in options.lua).
    -- <C-q> → send to quickfix is a snacks built-in; no custom action needed.
    local exclude = require("util.search").exclude_patterns()
    local search_opts = { hidden = true, ignored = true, exclude = exclude }

    local pmap = function(lhs, fn, desc)
      vim.keymap.set("n", lhs, fn, { desc = desc })
    end

    -- <leader>/: project-wide live grep over file CONTENTS.
    pmap("<leader>/", function()
      Snacks.picker.grep(search_opts)
    end, "Live grep")

    -- <leader><space>: file finder.
    pmap("<leader><space>", function()
      Snacks.picker.files(search_opts)
    end, "Find files")

    pmap("<leader>o", function()
      Snacks.picker.buffers()
    end, "Buffers")

    pmap("<leader>.", function()
      Snacks.picker.resume()
    end, "Resume last picker")

    -- <leader>sw: one-shot grep for the word under the cursor.
    pmap("<leader>sw", function()
      Snacks.picker.grep_word(search_opts)
    end, "Grep word under cursor")

    pmap("<leader>ss", function()
      Snacks.picker.lsp_symbols()
    end, "Symbols (document)")

    pmap("<leader>sS", function()
      Snacks.picker.lsp_workspace_symbols()
    end, "Symbols (workspace)")

    pmap("<leader>sk", function()
      Snacks.picker.keymaps()
    end, "Keymaps")

    -- <leader>: — the Emacs M-x: fuzzy-search and run any Ex command by name,
    -- the "I don't remember the binding, just find the command" escape hatch.
    -- Pairs with <leader>sk (keymaps) for full command discoverability. Mnemonic:
    -- mirrors the `:` cmdline. <leader>s: gives the command HISTORY (M-x repeat).
    pmap("<leader>:", function()
      Snacks.picker.commands()
    end, "Commands (M-x)")

    pmap("<leader>s:", function()
      Snacks.picker.command_history()
    end, "Command history")

    pmap("<leader>sb", function()
      Snacks.picker.lines()
    end, "Search in buffer")

    pmap("<leader>sh", function()
      Snacks.picker.help()
    end, "Help tags")

    pmap("<leader>fr", function()
      Snacks.picker.recent()
    end, "Recent files")

    -- <leader>fv: frecency-ranked smart picker (buffers + recent + files),
    -- replacing the old mini.visits visit_paths finder.
    pmap("<leader>fv", function()
      Snacks.picker.smart()
    end, "Frecent files")
  end,
}
