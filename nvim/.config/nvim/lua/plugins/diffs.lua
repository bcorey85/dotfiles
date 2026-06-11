-- diffs.nvim — treesitter-driven, language-aware syntax highlighting for diffs.
--
-- This is a presentation layer, NOT a replacement for anything: gitsigns still
-- owns in-buffer signs/hunks/staging and fugitive still owns status/commit/
-- history. diffs.nvim only re-colors diff output — fugitive's `dv` vertical
-- diffs, `:Git log` patch buffers, and Neovim's native diff mode get real
-- per-language syntax highlighting plus char/word-level intra-line diffs,
-- instead of flat green/red.
--
-- Division of responsibilities (extends the gitsigns.lua / fugitive.lua note):
--   gitsigns   → signs, hunk nav, in-buffer staging, hunk quickfix
--   fugitive   → status staging, commit, 3-way merge, history
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
vim.g.diffs = {
  integrations = {
    fugitive = true,
  },
  conflict = {
    enabled = false,
  },
}

return {
  src = "barrettruth/diffs.nvim",
}
