return {
  src = "catppuccin/nvim",
  name = "catppuccin",
  setup = function()
    require("catppuccin").setup({
      flavour = "mocha",
      color_overrides = {
        mocha = {
          base = "#282c34",
          mantle = "#21252b",
          crust = "#1b1f27",
        },
      },
      -- custom_highlights is re-applied by catppuccin on every :colorscheme
      -- call, so these survive re-application unlike bare nvim_set_hl() calls.
      custom_highlights = function()
        return {
          -- Float chrome baseline: teal borders, red titles on mantle. Every float that
          -- links to FloatBorder/FloatTitle (tiny-cmdline, LSP floats,
          -- ui-input, blink docs) inherits this — single source of truth, no blue UI.
          -- Small red pop keeps red-as-accent without red-framing every float.
          FloatBorder = { fg = "#94e2d5", bg = "#21252b" },
          FloatTitle = { fg = "#f38ba8", bg = "#21252b" },
          -- catppuccin paints the blink menu border blue directly (not via link);
          -- re-link it to the FloatBorder baseline so the completion menu matches.
          BlinkCmpMenuBorder = { link = "FloatBorder" },
          -- mini.clue: Catppuccin Mocha palette ported to MiniClue* groups.
          MiniClueNextKey = { fg = "#94e2d5" },
          MiniClueDescGroup = { fg = "#b4befe" },
          MiniClueDescSingle = { fg = "#cdd6f4" },
          MiniClueSeparator = { fg = "#6c7086" },
          MiniClueBorder = { link = "FloatBorder" },
          MiniClueTitle = { link = "FloatTitle" },
          -- Submode keys (e.g. <C-w> resize): red so it's obvious these keys repeat
          -- without re-entering the prefix.
          MiniClueNextKeyWithPostkeys = { fg = "#f38ba8", bold = true },
          ["@tag"] = { fg = "#94e2d5" },
          ["@tag.builtin"] = { fg = "#94e2d5" },
          ["@tag.attribute"] = { fg = "#b4befe" },
          ["@tag.delimiter"] = { fg = "#6c7086" },
          Directory = { fg = "#cdd6f4" },
          MiniIconsAzure = { fg = "#a6e3a1" },
          MiniIndentscopeSymbol = { fg = "#6c7086" },
          -- Selected row in the snacks.picker list: bg-only surface0, matching
          -- blink's PmenuSel, so "current item" reads identically in the picker
          -- and the completion menu.
          SnacksPickerListCursorLine = { bg = "#313244", fg = "NONE" },
          -- Picker title/border text: lavender (palette: teal chrome, red titles,
          -- lavender identity). Titles are red globally, but picker identity stays
          -- lavender per design.
          SnacksPickerTitle = { fg = "#b4befe", bg = "#21252b" },
          -- LSP document-highlight: underline instead of Catppuccin's
          -- background block (these are the groups document_highlight renders with).
          LspReferenceText = { underline = true },
          LspReferenceRead = { underline = true },
          LspReferenceWrite = { underline = true },
          -- Word-level diff: changed words (DiffText, used by diffopt "inline:word")
          -- default to a near-white wash that's hard to read. Paint them on a
          -- saturated green background so reworded text stands out in diff splits.
          -- ── Single diff palette, used EVERYWHERE ────────────────────────────
          -- The four native groups below are the one source of truth for diff
          -- colors. neogit (status inline diffs / log buffers), :Gitsigns
          -- diffthis, native diff mode, diffview, and diffs.nvim all render
          -- through them — so the `=` inline overlay must too, instead of
          -- gitsigns' own (washed-out: its inline word groups even default to
          -- TermCursor / near-white). Linking the gitsigns overlay groups to
          -- Diff{Add,Change,Text,Delete} makes every diff surface identical. To
          -- re-tune diffs anywhere, edit only these four — the links follow.
          -- DiffText kept green+bold (the changed-region emphasis); the other
          -- three are Catppuccin's muted defaults, left as-is for a calm, standard look.
          DiffText = { bg = "#2e5d3a", bold = true },
          -- `=` overlay → standard diff groups. Line bgs: added/changed/deleted
          -- lines. Inline (word_diff) regions: added & changed words take the
          -- DiffText emphasis; removed words take DiffDelete. (DeleteInline also
          -- cascades to the virtual deleted lines' words via
          -- GitSignsDeleteVirtLnInLine → …DeleteLnInline → …DeleteInline.)
          GitSignsAddLn = { link = "DiffAdd" },
          GitSignsChangeLn = { link = "DiffChange" },
          GitSignsDeleteVirtLn = { link = "DiffDelete" },
          GitSignsAddInline = { link = "DiffText" },
          GitSignsChangeInline = { link = "DiffText" },
          GitSignsDeleteInline = { link = "DiffDelete" },
          -- Neogit status-buffer diffs use its own NeogitDiff* highlight groups,
          -- NOT the native Diff* groups every other surface (gitsigns =, diffthis,
          -- native diff mode, diffs.nvim) renders through. Unlinked, neogit
          -- derives fg from `get_fg("String")` (Catppuccin's bright green) and
          -- ends up "bright green text on the muted green DiffAdd background" —
          -- readable but loud. Linking the four line-groups to the same single
          -- source of truth makes the status buffer match the `=` overlay and
          -- every other diff surface. (Neogit's hl.lua checks `is_set()` before
          -- defining — these links win, neogit respects them.)
          --
          -- NeogitDiffAddHighlight / NeogitDiffDeleteHighlight are the cursor-
          -- LINE variants; linking them too keeps the active hunk visually
          -- consistent with the inactive ones (no jarring fg flip on hover).
          NeogitDiffAdd = { link = "DiffAdd" },
          NeogitDiffAddHighlight = { link = "DiffAdd" },
          NeogitDiffAddCursor = { link = "DiffAdd" },
          NeogitDiffDelete = { link = "DiffDelete" },
          NeogitDiffDeleteHighlight = { link = "DiffDelete" },
          NeogitDiffDeleteCursor = { link = "DiffDelete" },
          -- Inline (word-diff) regions inside a diff hunk — match the `=`
          -- overlay and gitsigns word-diff: added/changed words take the
          -- DiffText emphasis (green+bold), removed words take DiffDelete.
          NeogitDiffAddInline = { link = "DiffText" },
          NeogitDiffDeleteInline = { link = "DiffDelete" },
          -- treesitter-context sticky header: lift it off the buffer with the same
          -- surface tone the statusline badges use (#313244) so it reads as chrome,
          -- not code, and underline the bottom edge in teal to mark exactly where
          -- the sticky block ends and real buffer lines begin.
          TreesitterContext = { bg = "#313244" },
          TreesitterContextLineNumber = { fg = "#6c7086", bg = "#313244" },
          TreesitterContextBottom = { underline = true, sp = "#94e2d5" },
          TreesitterContextLineNumberBottom = { underline = true, sp = "#94e2d5" },

          -- De-blue pass: swap catppuccin blue (#89b4fa) and sky (#89dceb) out of
          -- every UI group that actually renders in this config. Rule: chrome/controls
          -- → teal #94e2d5; names/identity/info → lavender #b4befe.

          -- ── Teal chrome/controls ────────────────────────────────────────────────
          -- Title, MoreMsg, Question: blue → teal; preserve bold on Title.
          Title = { fg = "#94e2d5", bold = true },
          MoreMsg = { fg = "#94e2d5" },
          Question = { fg = "#94e2d5" },
          -- SpellLocal: sp only (undercurl style kept); blue sp → teal.
          SpellLocal = { sp = "#94e2d5", undercurl = true },
          -- markview list bullets: teal (bullet is chrome punctuation). Custom
          -- group referenced by markview.lua's list_items config — markview never
          -- defines MdBullet, so this theme definition always wins.
          MdBullet = { fg = "#94e2d5" },
          -- markview heading per-level colours (fg + bold, no background bar).
          -- Custom groups referenced by markview.lua's headings config so they
          -- survive markview re-applying its own Markview* groups after setup.
          MdHeading1 = { fg = "#f76c7c", bold = true },
          MdHeading2 = { fg = "#f3a96a", bold = true },
          MdHeading3 = { fg = "#e3d367", bold = true },
          MdHeading4 = { fg = "#9cd57b", bold = true },
          MdHeading5 = { fg = "#78cee9", bold = true },
          MdHeading6 = { fg = "#baa0f8", bold = true },
          -- nvim wildmenu popup border: link to the established FloatBorder baseline.
          PmenuBorder = { link = "FloatBorder" },
          -- DAP UI: sky/blue → teal (debugger chrome).
          DapUIStepBack = { fg = "#94e2d5" },
          DapUIStepInto = { fg = "#94e2d5" },
          DapUIStepOut = { fg = "#94e2d5" },
          DapUIStepOver = { fg = "#94e2d5" },
          DapUIScope = { fg = "#94e2d5" },
          DapUILineNumber = { fg = "#94e2d5" },
          DapUIDecoration = { fg = "#94e2d5" },
          DapUIBreakpointsPath = { fg = "#94e2d5" },
          DapUIStoppedThread = { fg = "#94e2d5" },
          DapUIValue = { fg = "#94e2d5" },
          DapLogPoint = { fg = "#94e2d5" },
          -- BlinkCmpKindOperator: sky → teal (operator is punctuation/chrome).
          BlinkCmpKindOperator = { fg = "#94e2d5" },

          -- ── Lavender names/identity/info ────────────────────────────────────────
          -- qfFileName: blue → lavender (file identity).
          qfFileName = { fg = "#b4befe" },
          -- Folded: blue fg → lavender; preserve catppuccin bg blend (#45475a).
          Folded = { fg = "#b4befe", bg = "#45475a" },
          -- Diagnostic severity ladder: red error / yellow warn / lavender info / teal hint.
          -- DiagnosticInfo: sky fg → lavender; preserve italic.
          DiagnosticInfo = { fg = "#b4befe", italic = true },
          DiagnosticSignInfo = { fg = "#b4befe" },
          -- DiagnosticVirtualTextInfo: sky fg → lavender; preserve italic + bg blend (#313d45).
          DiagnosticVirtualTextInfo = { fg = "#b4befe", italic = true, bg = "#313d45" },
          DiagnosticFloatingInfo = { fg = "#b4befe" },
          -- Diagnostic squiggles: Catppuccin (this version) defines the
          -- DiagnosticUnderline* groups with flat `underline`, which renders as a
          -- straight line, not a squiggle. Force `undercurl` back on all four so
          -- lint/LSP diagnostics squiggle again (kitty draws undercurl natively;
          -- tmux passes it via usstyle). Colors preserved: red/yellow/lavender/teal.
          DiagnosticUnderlineError = { sp = "#f38ba8", undercurl = true },
          DiagnosticUnderlineWarn = { sp = "#f9e2af", undercurl = true },
          DiagnosticUnderlineInfo = { sp = "#b4befe", undercurl = true },
          DiagnosticUnderlineHint = { sp = "#94e2d5", undercurl = true },
          -- BlinkCmp kind icons: blue → lavender (symbol identity).
          BlinkCmpKindFunction = { fg = "#b4befe" },
          BlinkCmpKindMethod = { fg = "#b4befe" },
          BlinkCmpKindModule = { fg = "#b4befe" },
          BlinkCmpKindProperty = { fg = "#b4befe" },
          BlinkCmpKindStruct = { fg = "#b4befe" },
          BlinkCmpKindFile = { fg = "#b4befe" },
          BlinkCmpKindFolder = { fg = "#b4befe" },
          BlinkCmpKindConstructor = { fg = "#b4befe" },
          BlinkCmpKindEvent = { fg = "#b4befe" },
          -- Fallback for any kind without a specific BlinkCmpKind* group (was catppuccin blue).
          BlinkCmpKind = { fg = "#b4befe" },
          -- Changed/diff: blue → lavender (file identity in diff context).
          Changed = { fg = "#b4befe" },
          diffChanged = { fg = "#b4befe" },
          diffFile = { fg = "#b4befe" },
        }
      end,
    })
    vim.cmd.colorscheme("catppuccin")
  end,
}
