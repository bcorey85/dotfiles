-- aura (baliestri/aura-theme) — theme-mode family, DARK-ONLY dimmed variant.
-- Aura ships no light scheme, so both modes use "aura-dark-soft-text" (the
-- spore pattern: bg #15141b, soft-text fg, muted accents). The colors live in
-- the repo's packages/neovim subdir, hence the rtp append (upstream README
-- pattern). Loads eagerly (lazy = false, priority = 1000) so it's on the rtp
-- before config.lazy.lua's theme-sync.start(). theme-sync owns :colorscheme.
return {
  "baliestri/aura-theme",
  lazy = false,
  priority = 1000,
  config = function(plugin)
    vim.opt.rtp:append(plugin.dir .. "/packages/neovim")
  end,
}
