-- grug-far.nvim — project-wide find & replace in an editable, previewable buffer.
-- Complements (doesn't replace) the two existing search paths:
--   • LSP rename (<leader>lr) — semantic, single-symbol, the correct first reach.
--   • Snacks grep → <C-q> → :cdo s/// — quickfix-driven one-shot sweeps.
-- grug-far is the persistent scratchpad for iterative regex/structural replaces:
-- edit the search/replace/files-filter fields like text, watch matches stream in,
-- delete result lines to scope the replace, then apply. ripgrep is the engine
-- (already installed); ast-grep is auto-detected if present (pacman/brew) for
-- structural rewrites.
return {
  src = "MagicDuck/grug-far.nvim",
  setup = function()
    require("grug-far").setup({
      -- Search hidden files (dotfiles!) but never descend into .git — mirrors
      -- how ripgrep is used elsewhere in this config.
      engines = { ripgrep = { extraArgs = "--hidden --glob=!**/.git/*" } },
      -- The 'lua' replacement interpreter stays available on demand: inside the
      -- buffer, `\x` swaps the replace field to a Lua function (e.g.
      -- `return match:upper()`) for logic regex can't express.
    })

    -- Lives in the snacks "search" namespace (<leader>s*). Opening from visual
    -- mode prefills the search field with the current selection.
    vim.keymap.set({ "n", "x" }, "<leader>sr", function()
      require("grug-far").open()
    end, { desc = "Search & replace (grug-far)" })

    -- Same, but pre-scoped to the current file's extension — for big sweeps
    -- you want confined to one filetype.
    vim.keymap.set("n", "<leader>sR", function()
      local ext = vim.fn.expand("%:e")
      require("grug-far").open({
        prefills = { filesFilter = ext ~= "" and ("*." .. ext) or nil },
      })
    end, { desc = "Search & replace in filetype (grug-far)" })
  end,
}
