-- tempus (protesilaos/tempus-themes-vim) — theme-mode family. WCAG-tuned
-- palettes; per-variant colors_name (tempus_dusk/tempus_dawn), so theme-sync
-- needs no colors_name pin. Vimscript colorschemes; eager + high priority so
-- they are on the rtp before theme-sync's first apply.
return {
  "protesilaos/tempus-themes-vim",
  name = "tempus",
  lazy = false,
  priority = 1000,
}
