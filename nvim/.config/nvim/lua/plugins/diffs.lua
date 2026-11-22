-- diffs.nvim — treesitter-driven, language-aware syntax highlighting for diffs.
--
-- This is a presentation layer, NOT a replacement for anything: gitsigns
-- owns in-buffer signs/hunks/staging and neogit owns status/commit/history.
-- diffs.nvim only re-colors diff output — neogit's inline status diffs,
-- `git log`-style patch buffers, and Neovim's native diff mode get real
-- per-language syntax highlighting plus char/word-level intra-line diffs,
-- instead of flat green/red.
--
-- Division of responsibilities (extends the gitsigns.lua / neogit.lua note):
--   gitsigns   → signs, hunk nav, in-buffer staging, hunk quickfix
--   neogit     → status, commit, push/pull/fetch/rebase popups, history
--   util/merge → plugin-free conflict resolution (THE single conflict path)
--   diffs.nvim → syntax-aware highlighting of diffs/diff-mode (display only)
--
-- WHY vim.g.diffs is set here at top level and not inside setup():
-- diffs.nvim has no setup() — its plugin/diffs.lua reads `vim.g.diffs`
-- synchronously the moment it is sourced, and vim.pack sources plugin/ files
-- during vim.pack.add(). Our pack wrapper (config/pack.lua) evaluates each
-- spec file's body BEFORE add() but runs setup() AFTER it. So the config must
-- land at file-evaluation time (here), or the plugin loads with stale defaults.
--
-- conflict.enabled = false: defaults turn on conflict highlighting + virtual
-- text + diagnostic suppression on files with raw markers, which would shadow
-- util/merge. We keep util/merge as the only conflict UI, so this stays off.
--
-- integrations.fugitive = false: fugitive has been replaced by neogit.
-- integrations.neogit = true: enables diffs.nvim's treesitter highlighting
-- on NeogitStatus / NeogitCommitView / NeogitDiffView buffers (the filetype
-- pattern is `^Neogit`). Without this the neogit integration defaults to
-- false (diffs.nvim/lua/diffs/integrations.lua), and neogit's inline status
-- diffs render with neogit's own flatter colors — the contrast regression
-- that sent us looking here.
vim.g.diffs = {
  integrations = {
    fugitive = false,
    neogit = true,
  },
  conflict = false,
}

-- Word-level emphasis lives in ONE surface only: codediff.nvim, opened from
-- neogit (see plugins/codediff.lua). diffs.nvim has no switch for it apart
-- from the global 'diffopt', which native diff mode needs at inline:word, so
-- its word groups take the line wash and draw nothing.
local function hide_word_emphasis()
  vim.api.nvim_set_hl(0, "DiffsAddText", { link = "DiffsAdd" })
  vim.api.nvim_set_hl(0, "DiffsDeleteText", { link = "DiffsDelete" })
end

return {
  "https://forge.barrettruth.com/barrettruth/diffs.nvim",
  event = "VeryLazy",
  config = function()
    hide_word_emphasis()
    -- Scheduled: the plugin resets its groups on the same event.
    vim.api.nvim_create_autocmd("ColorScheme", {
      group = vim.api.nvim_create_augroup("diffs_hide_word_emphasis", { clear = true }),
      callback = vim.schedule_wrap(hide_word_emphasis),
    })
  end,
}
