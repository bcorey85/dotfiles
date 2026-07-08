-- zenbones — the "zenbones" theme family (dark/light via vim.o.background;
-- light is the paper-cream look). Switch with `theme-use zenbones [mode]`;
-- scheme mapping, accents, and floor fixups live in
-- lua/config/theme-sync.lua's FAMILIES table. Re-admitted 2026-07-07 after
-- the warm-text preference relaxed (audition note: "spartan" — few colors is
-- the design: prose-first, syntax mostly shades of the body ink).
return {
  "zenbones-theme/zenbones.nvim",
  lazy = true,
  dependencies = { "rktjmp/lush.nvim" },
}
