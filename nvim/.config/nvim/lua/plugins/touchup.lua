-- touchup.nvim — non-invasive live markdown rendering. Replaces markview.nvim.
--
-- Architecture note vs markview: touchup is a global decoration provider
-- (nvim_set_decoration_provider), not a mode-based renderer. It re-parses
-- treesitter each window redraw and draws ephemeral extmarks for whatever is
-- visible, in every mode — so there is no hybrid/insert un-render step and no
-- per-buffer enable/disable command. Rendering is gated only by `filetypes`.
--
-- Deliberately dropped from the old markview config (touchup has no module for
-- them): ATX heading icons + per-level heading colours, and table rendering.
-- Heading COLOUR is preserved a different way — theme-sync.lua now paints the
-- native @markup.heading.N.markdown treesitter groups (see its set_headings),
-- so headings stay coloured, just without the ⌘/λ/△ icons and trailing rule.
--
-- conceallevel: touchup disables its markers + links rendering whenever
-- conceallevel > 0 (concealing shifts visual columns and desyncs its extmark
-- coordinates). The global default is 2, so autocmds.lua forces conceallevel=0
-- in markdown buffers — without that, `**`/`_` marker hiding and link styling
-- silently no-op and touchup emits a one-time warning.
--
-- Bullets: touchup picks the icon by NESTING DEPTH (cycling the `icons` list)
-- and the highlight by MARKER CHAR (TouchupBulletDash/Plus/Star). markview did
-- the opposite (icon per char), so the per-char glyph mapping can't be ported
-- 1:1 — depth-cycled glyphs below, colour still driven by MdBullet→Touchup*
-- links set in theme-sync.
return {
  "noisesfromspace/touchup.nvim",
  ft = "markdown",
  dependencies = {
    "nvim-treesitter/nvim-treesitter", -- markdown + markdown_inline parsers
  },
  opts = {
    filetypes = { "markdown" },

    bullets = {
      enabled = true,
      -- Cycled by depth; colour comes from TouchupBullet{Dash,Plus,Star}
      -- (theme-sync links these to the heading accent, matching old MdBullet).
      icons = { "»", "›", "∘", "·" },
    },

    checkboxes = {
      enabled = true,
      -- Custom states ported from the markview config (keyed by the char in
      -- brackets). touchup's built-in defaults for the other states are kept
      -- via deep-merge. `[ ]` unchecked is not customizable in touchup — it
      -- always renders as a plain space (the old 󰄱 box is gone).
      icons = {
        ["x"] = { text = "󰱒", hl = "TouchupCheckboxChecked" },
        ["X"] = { text = "󰱒", hl = "TouchupCheckboxChecked" },
        ["-"] = { text = "󰥔", hl = "TouchupCheckboxPending" }, -- todo  [-]
        ["~"] = { text = "󰔟", hl = "TouchupCheckboxProgress" }, -- doing [~]
        ["/"] = { text = "󰜺", hl = "TouchupCheckboxCancelled" }, -- cancel [/]
      },
    },

    code_blocks = { enabled = true },
    markers = { enabled = true }, -- hides **/_/etc — needs conceallevel=0
    quotes = { enabled = true },
    admonitions = { enabled = true },
    links = { enabled = true }, -- styles link labels — needs conceallevel=0
    enter = { enabled = true }, -- smart <CR>: continue lists / checkboxes
  },
}
