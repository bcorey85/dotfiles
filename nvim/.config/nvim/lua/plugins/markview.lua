-- markview.nvim — markdown previewer. Replaces render-markdown.nvim.
--
-- Tables use markview's STOCK renderer. We previously wired
-- markview-smart-tables.nvim to re-fit wide tables to the window, but it drew
-- tables as virt_lines over 0-height `conceal_lines` source rows, which broke
-- cursor navigation: <C-d> scrolling couldn't step into a table (the source
-- rows had no screen height and the render was non-interactive). Enabling
-- markview hybrid mode was needed just to reveal the raw table, which brought
-- back inline-marker snapping — not worth it. smart-tables was removed.
-- Tradeoff: the stock renderer draws tables at natural width, so a table wider
-- than the window soft-wraps and its row extmarks desync (shattered look) in
-- the <leader>m reading popup. Navigable-but-occasionally-ugly beats unusable.
--
-- Heading colours + list bullets use custom hl groups (MdHeading1..6, MdBullet)
-- defined in theme.lua's catppuccin custom_highlights. markview only REFERENCES
-- those names (it never defines them), so the theme's definitions always win —
-- unlike the built-in Markview* groups, which markview re-applies after setup
-- and would shadow a theme override made at startup.
--
-- Note vs the old render-markdown look: markview draws no full-width underline
-- rule beneath ATX headings (that was render-md's `below = "─"` + a monkey-patch;
-- markview only borders setext headings). Headings keep their per-level colour +
-- icon, just without the trailing rule.
return {
  src = "OXY2DEV/markview.nvim",
  deps = {
    "nvim-treesitter/nvim-treesitter", -- markdown + markdown_inline parsers
    "echasnovski/mini.nvim", -- icon provider (mini.icons mock satisfies devicons)
  },
  setup = function()
    require("markview").setup({
      preview = {
        -- Render in normal, command, and terminal modes (matches the old
        -- render_modes). hybrid_modes is OFF (empty): markers like ** and _
        -- stay concealed even on the cursor line, so scrolling doesn't make
        -- bold/italic spans expand and snap back. Enter insert mode to see/edit
        -- raw source (insert isn't in `modes`, so the whole buffer un-renders).
        modes = { "n", "c", "t" },
        hybrid_modes = {},
      },

      markdown = {
        headings = {
          enable = true,
          shift_width = 0, -- no per-level indent (render-md had indent disabled)

          heading_1 = { style = "inline", icon = "⌘ ", hl = "MdHeading1" },
          heading_2 = { style = "inline", icon = "λ ", hl = "MdHeading2" },
          heading_3 = { style = "inline", icon = "△ ", hl = "MdHeading3" },
          heading_4 = { style = "inline", icon = "⟐ ", hl = "MdHeading4" },
          heading_5 = { style = "inline", icon = "⊡ ", hl = "MdHeading5" },
          heading_6 = { style = "inline", icon = "∷ ", hl = "MdHeading6" },
        },

        code_blocks = {
          enable = true,
          style = "block",
          label_direction = "right",
          pad_amount = 2,
          min_width = 60,
          sign = false,
        },

        list_items = {
          enable = true,
          -- markview keys bullets by marker char (not nesting depth like
          -- render-md): - → », + → ›, * → ∘. Ordered markers left untouched.
          marker_minus = { text = "»", hl = "MdBullet" },
          marker_plus = { text = "›", hl = "MdBullet" },
          marker_star = { text = "∘", hl = "MdBullet" },
        },

        tables = {
          enable = true,
          strict = false,
          block_decorator = true, -- top & bottom rule (rounded box)
          use_virt_lines = false,
        },
      },

      markdown_inline = {
        checkboxes = {
          enable = true,
          checked = { text = "󰱒", hl = "MarkviewCheckboxChecked" },
          unchecked = { text = "󰄱", hl = "MarkviewCheckboxUnchecked" },
          -- Custom states ported from render-md (keyed by the char in brackets):
          ["-"] = { text = "󰥔", hl = "MarkviewCheckboxPending" }, -- todo  [-]
          ["~"] = { text = "󰔟", hl = "MarkviewCheckboxProgress" }, -- doing [~]
          ["/"] = { text = "󰜺", hl = "MarkviewCheckboxCancelled" }, -- cancel [/]
        },

        hyperlinks = {
          enable = true,
          default = { icon = "󰌹 ", hl = "MarkviewHyperlink" },
          ["github%.com"] = { priority = -9999, icon = "󰊤 ", hl = "MarkviewHyperlink" },
          ["youtu%.?be"] = { priority = -9999, icon = "󰗃 ", hl = "MarkviewHyperlink" },
        },

        images = {
          enable = true,
          default = { icon = "󰥶 ", hl = "MarkviewImage" },
        },

        emails = {
          enable = true,
          default = { icon = "󰀓 ", hl = "MarkviewEmail" },
        },
      },

      latex = { enable = false },
      yaml = { enable = false },
    })
  end,
}
