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
-- alacritty and WSL do NOT support it — images will not render there.
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

    -- Terminal toggle, keyed by cwd (one float per project). Lives in the
    -- <leader>t tasks namespace as <leader>tt — "tasks → terminal" — alongside
    -- the dispatch maps (tm/tr/td/…). Bare <leader>t is their prefix, so the
    -- toggle takes the doubled key to avoid shadowing the group.
    vim.keymap.set("n", "<leader>tt", function()
      Snacks.terminal()
    end, { desc = "Toggle terminal (cwd)" })

    -- Dismiss-from-inside uses a chord, not <leader>: in terminal mode <leader>
    -- (space) would intercept every space you type in the shell. <C-/> (sent as
    -- <C-_> by kitty/alacritty) hides the terminal split without leaving insert.
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
  end,
}
