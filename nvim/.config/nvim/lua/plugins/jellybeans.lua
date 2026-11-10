-- jellybeans (WTFox/jellybeans.nvim) — theme-mode family: :colorscheme jellybeans follows
-- 'background' (#151515 dark / sepia #f5e6d3 light). The rest are auditions: jellybeans-muted,
-- -warm, -hc and -mono, with -muted-light, -hc-light and -mono-light. Loads eagerly
-- (lazy = false, priority = 1000) so it's on the rtp before theme-sync.start().
return {
  "WTFox/jellybeans.nvim",
  lazy = false,
  priority = 1000,
}
