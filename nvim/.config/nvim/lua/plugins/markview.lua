-- markview.nvim + markview-smart-tables.nvim — markdown previewer.
--
-- Replaces render-markdown.nvim. The reason for the swap is tables: render-md
-- renders a table at its natural width and then lets Neovim's `wrap` soft-wrap
-- the over-long line, which desyncs its row-by-row extmarks and shatters wide
-- tables in the prefix-m reading popup. markview-smart-tables re-lays-out the
-- table to FIT the window — shrinks the widest columns first, then word-wraps
-- overflowing cells INSIDE the cell borders — so wide tables stay intact.
--
-- Wiring: smart-tables is a companion that takes over markview's table renderer
-- via the `renderers.markdown_table` hook (see setup below).
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
    "gunasekar/markview-smart-tables.nvim",
  },
  setup = function()
    -- Auto-fit wide tables to the window. wrap_width: max table width as a
    -- fraction of the window; wrap_minwidth: floor a column shrinks to before
    -- long words are hard-broken.
    require("markview-smart-tables").setup({
      wrap_width = 0.9,
      wrap_minwidth = 5,
    })

    require("markview").setup({
      preview = {
        -- Render in normal, command, and terminal modes (matches the old
        -- render_modes). Enter insert mode to see/edit raw source (insert isn't
        -- in `modes`, so the whole buffer un-renders).
        modes = { "n", "c", "t" },

        -- Hybrid mode reveals a node's raw source when the cursor is ON it.
        -- smart-tables REQUIRES this to enter/edit a wide table: it draws the
        -- fitted table as virt_lines over 0-height `conceal_lines` source rows,
        -- so with no reveal the cursor falls into the concealed rows and <C-d>
        -- scrolling desyncs — it can't step into the table (smart-tables
        -- table.lua:353 documents hybrid mode as the edit path).
        hybrid_modes = { "n" },
        -- Block (all-or-nothing) reveal, NOT linewise: smart-tables falls back
        -- to the stock renderer when linewise hybrid mode is on (table.lua:
        -- 372-378), and the stock renderer shatters overflowing tables. Keep
        -- false (also the default) — pinned here to document the constraint.
        linewise_hybrid_mode = false,
        -- Scope the reveal to ONLY tables, preserving the old "markers stay
        -- concealed on the cursor line so scrolling doesn't snap **/_ spans"
        -- behaviour everywhere else. raw_previews is per-language and an
        -- UNLISTED language reveals ALL its nodes, so both markdown (tables
        -- only) and markdown_inline (nothing) must be pinned. Bold/italic live
        -- in markdown_inline; "none" is a sentinel class that matches nothing,
        -- so the inclusion filter leaves that language revealing zero nodes.
        raw_previews = {
          markdown = { "tables" },
          markdown_inline = { "none" },
        },
      },

      -- Hand table rendering to smart-tables.
      renderers = {
        markdown_table = function(buffer, item)
          require("markview-smart-tables").render(buffer, item)
        end,
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
