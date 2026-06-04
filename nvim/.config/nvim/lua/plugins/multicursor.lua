-- multicursor.nvim: multiple simultaneous cursors (replaces macros, q/Q are <nop>)
--
-- KEYMAP SUMMARY
-- ─────────────────────────────────────────────────────────────────────────────
--   <C-Up>   / <C-Down>   add cursor above / below main cursor
--   <M-n>    / <M-N>      add cursor at next / prev match of word or selection
--   <M-x>    / <M-X>      skip (no cursor) next / prev match
--   <leader>A             add cursors for ALL matches of word/selection in buffer
--   <M-q>                 toggle/disable individual cursor under main cursor
--
--   (active only when multicursors are live — via addKeymapLayer)
--   <Left>   / <Right>    cycle through cursors
--   <leader>X             delete the cursor under main cursor
--   <Esc>                 enable disabled cursors; or clear all cursors
--
-- WHY these keys:
--   <C-n>/<C-p>  → yanky  (yanky.lua:40-41) — off-limits
--   <C-d>/<C-u>  → scroll+center             — off-limits
--   <C-h/j/k/l>  → smart-splits              — off-limits
--   <A-j>/<A-k>  → move-lines                — off-limits
--   <C-s>        → save                      — off-limits
--   s/S          → flash                     — off-limits
--   <leader>s    → search group              — off-limits
--   <leader>n/<leader>N and <leader>s/<leader>S are the plugin defaults but
--   <leader>n conflicts with notes group and <leader>s is the search group,
--   so we use <M-n>/<M-N> (Alt+n) for match navigation instead.
return {
  {
    "jake-stewart/multicursor.nvim",
    branch = "1.0",
    -- Lazy-load only when one of the trigger keys is pressed.
    keys = {
      { "<C-Up>", mode = { "n", "x" } },
      { "<C-Down>", mode = { "n", "x" } },
      { "<M-n>", mode = { "n", "x" } },
      { "<M-N>", mode = { "n", "x" } },
      { "<M-x>", mode = { "n", "x" } },
      { "<M-X>", mode = { "n", "x" } },
      { "<leader>A", mode = { "n", "x" } },
      { "<M-q>", mode = { "n", "x" } },
    },
    config = function()
      local mc = require("multicursor-nvim")
      mc.setup()

      local set = vim.keymap.set

      -- Add / skip cursor above or below main cursor.
      set({ "n", "x" }, "<C-Up>", function()
        mc.lineAddCursor(-1)
      end, { desc = "Multicursor: add cursor above" })
      set({ "n", "x" }, "<C-Down>", function()
        mc.lineAddCursor(1)
      end, { desc = "Multicursor: add cursor below" })

      -- Add / skip next or previous match of word under cursor (Sublime <C-d> style).
      set({ "n", "x" }, "<M-n>", function()
        mc.matchAddCursor(1)
      end, { desc = "Multicursor: add cursor at next match" })
      set({ "n", "x" }, "<M-N>", function()
        mc.matchAddCursor(-1)
      end, { desc = "Multicursor: add cursor at prev match" })
      set({ "n", "x" }, "<M-x>", function()
        mc.matchSkipCursor(1)
      end, { desc = "Multicursor: skip next match" })
      set({ "n", "x" }, "<M-X>", function()
        mc.matchSkipCursor(-1)
      end, { desc = "Multicursor: skip prev match" })

      -- Add cursors for every match of word/selection in the buffer.
      set({ "n", "x" }, "<leader>A", mc.matchAllAddCursors, { desc = "Multicursor: add cursors for all matches" })

      -- Toggle/disable individual cursor (leaves others active).
      set({ "n", "x" }, "<M-q>", mc.toggleCursor, { desc = "Multicursor: toggle cursor" })

      -- Keymaps that only apply when multiple cursors are active.
      -- addKeymapLayer installs a buffer-local layer so these bindings do NOT
      -- shadow <Left>/<Right>/<leader>X/<Esc> during normal single-cursor use.
      -- The <Esc> binding here re-enables disabled cursors or clears all cursors
      -- and does NOT permanently override the global <esc>→noh map in keymaps.lua
      -- because the layer is only active while multicursor is running.
      mc.addKeymapLayer(function(layerSet)
        layerSet({ "n", "x" }, "<Left>", mc.prevCursor, { desc = "Multicursor: prev cursor" })
        layerSet({ "n", "x" }, "<Right>", mc.nextCursor, { desc = "Multicursor: next cursor" })
        layerSet({ "n", "x" }, "<leader>X", mc.deleteCursor, { desc = "Multicursor: delete cursor" })

        layerSet("n", "<Esc>", function()
          if not mc.cursorsEnabled() then
            mc.enableCursors()
          else
            mc.clearCursors()
          end
        end, { desc = "Multicursor: enable or clear cursors" })
      end)

      -- Highlight groups matching the Catppuccin Mocha theme used by this config.
      local hl = vim.api.nvim_set_hl
      hl(0, "MultiCursorCursor", { reverse = true })
      hl(0, "MultiCursorVisual", { link = "Visual" })
      hl(0, "MultiCursorSign", { link = "SignColumn" })
      hl(0, "MultiCursorMatchPreview", { link = "Search" })
      hl(0, "MultiCursorDisabledCursor", { reverse = true })
      hl(0, "MultiCursorDisabledVisual", { link = "Visual" })
      hl(0, "MultiCursorDisabledSign", { link = "SignColumn" })
    end,
  },
}
