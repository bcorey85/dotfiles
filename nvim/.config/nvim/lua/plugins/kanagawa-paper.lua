-- kanagawa-paper (thesimonho/kanagawa-paper) — theme-mode family
-- "kanagawa-paper": kanagawa-paper-ink dark, kanagawa-paper-canvas light. The
-- installable runtime lives on the `neovim` branch. Loads eagerly (lazy = false,
-- priority = 1000) so it's on the rtp before theme-sync.start().
return {
  "thesimonho/kanagawa-paper",
  branch = "neovim",
  lazy = false,
  priority = 1000,
}
