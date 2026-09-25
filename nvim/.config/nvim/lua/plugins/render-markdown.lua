-- render-markdown.nvim — in-buffer markdown rendering (conceals markers, heading
-- icons, tables, checkbox states). Replaces touchup.nvim, which only dimmed
-- markers and never concealed. Browser preview is live-preview.lua.
--
-- Colours come from theme-sync.lua (set_headings / set_prose), so they track
-- every family/mode switch. Icons resolve through mini.icons' devicons mock.
return {
  "MeanderingProgrammer/render-markdown.nvim",
  ft = "markdown",
  dependencies = {
    "nvim-treesitter/nvim-treesitter", -- markdown + markdown_inline parsers
    "nvim-mini/mini.nvim",
  },
  ---@module 'render-markdown'
  ---@type render.md.UserConfig
  opts = {
    heading = {
      sign = false,
      width = "block",
      right_pad = 1,
    },
    bullet = {
      icons = { "»", "›", "∘", "·" },
    },
    checkbox = {
      checked = { icon = "󰱒 " },
      custom = {
        todo = { raw = "[-]", rendered = "󰥔 ", highlight = "RenderMarkdownTodo" },
        doing = { raw = "[~]", rendered = "󰔟 ", highlight = "RenderMarkdownWarn" },
        cancel = { raw = "[/]", rendered = "󰜺 ", highlight = "Comment" },
      },
    },
    code = {
      sign = false,
      width = "block",
      right_pad = 2,
    },
    latex = { enabled = false },
  },
}
