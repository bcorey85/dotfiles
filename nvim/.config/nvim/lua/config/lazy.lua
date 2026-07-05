-- lazy.nvim bootstrap — replaces the native vim.pack loader (was config.pack).
--
-- Migration notes (from vim.pack):
--   * Each lua/plugins/<name>.lua now returns a lazy.nvim spec: the repo is the
--     first positional string (was `src`), `setup` became `config`, `deps`
--     became `dependencies`, and load triggers (event/ft/cmd/keys) were added
--     per plugin so most plugins no longer load at startup.
--   * A plugin with NO trigger and no `lazy = true` loads eagerly at startup
--     (same as vim.pack did) — that's the safe fallback for anything unconverted.
--   * lazy installs to ~/.local/share/nvim/lazy/ (NOT the old vim.pack dir at
--     site/pack/core/opt). The first launch re-clones everything; the old dir is
--     orphaned and can be deleted once this is confirmed working.
--   * Revisions pin to lazy-lock.json now (was nvim-pack-lock.json).
--
-- LSP: config.lsp calls vim.lsp.config()/enable() and reads
-- vim.lsp.config.eslint.root_dir, so it REQUIRES nvim-lspconfig on the rtp. It is
-- invoked from the lspconfig spec's config() (plugins/lspconfig.lua), gated on
-- BufReadPre — not here — so servers still activate lazily on file open.

local lazypath = vim.fn.stdpath("data") .. "/lazy/lazy.nvim"
if not (vim.uv or vim.loop).fs_stat(lazypath) then
  local out = vim.fn.system({
    "git",
    "clone",
    "--filter=blob:none",
    "--branch=stable",
    "https://github.com/folke/lazy.nvim.git",
    lazypath,
  })
  if vim.v.shell_error ~= 0 then
    error("Failed to clone lazy.nvim:\n" .. out)
  end
end
vim.opt.rtp:prepend(lazypath)

require("lazy").setup({
  spec = { { import = "plugins" } },
  -- No defaults.lazy = true: an unconverted spec (no trigger) then loads eagerly
  -- like it did under vim.pack, rather than silently never loading.
  install = { colorscheme = { "terafox" } },
  checker = { enabled = false }, -- no background update checks
  change_detection = { enabled = false }, -- don't watch/reload spec files
  ui = { border = "rounded" },
  performance = {
    rtp = {
      disabled_plugins = {
        "gzip",
        "tarPlugin",
        "tohtml",
        "tutor",
        "zipPlugin",
        "netrwPlugin",
      },
    },
  },
})

-- Convenience: keep muscle-memory for the old pack commands pointing at lazy.
vim.api.nvim_create_user_command("PackUpdate", "Lazy update", { desc = "(compat) -> Lazy update" })
vim.api.nvim_create_user_command("PackStatus", "Lazy", { desc = "(compat) -> Lazy" })
vim.api.nvim_create_user_command("PackClean", "Lazy clean", { desc = "(compat) -> Lazy clean" })
