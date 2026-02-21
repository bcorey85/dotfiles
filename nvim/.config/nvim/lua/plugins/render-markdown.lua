return {
  "MeanderingProgrammer/render-markdown.nvim",
  ft = "markdown",
  dependencies = {
    "nvim-treesitter/nvim-treesitter",
    "nvim-tree/nvim-web-devicons",
  },
  config = function(_, opts)
    -- Sonokai Maia heading colors (bg tinted with accent, fg = accent)
    local colors = {
      { fg = "#f76c7c", bg = "#55393d" }, -- H1: red
      { fg = "#f3a96a", bg = "#4e432f" }, -- H2: orange
      { fg = "#e3d367", bg = "#4e432f" }, -- H3: yellow
      { fg = "#9cd57b", bg = "#394634" }, -- H4: green
      { fg = "#78cee9", bg = "#354157" }, -- H5: blue
      { fg = "#baa0f8", bg = "#404256" }, -- H6: purple
    }
    for i, c in ipairs(colors) do
      vim.api.nvim_set_hl(0, "RenderMarkdownH" .. i, { fg = c.fg, bold = true })
      vim.api.nvim_set_hl(0, "RenderMarkdownH" .. i .. "Bg", { bg = c.bg })
    end

    require("render-markdown").setup(opts)
  end,
  opts = {
    render_modes = { "n", "c", "t" },
    latex = { enabled = false },
    anti_conceal = {
      enabled = true,
      ignore = {
        code_background = true,
        sign = true,
      },
    },
    win_options = {
      conceallevel = { default = vim.o.conceallevel, rendered = 3 },
    },
    heading = {
      sign = false,
      icons = { "󰎤 ", "󰎧 ", "󰎪 ", "󰎭 ", "󰎱 ", "󰎳 " },
      width = "full",
      border = true,
      border_virtual = true,
      backgrounds = {
        "RenderMarkdownH1Bg",
        "RenderMarkdownH2Bg",
        "RenderMarkdownH3Bg",
        "RenderMarkdownH4Bg",
        "RenderMarkdownH5Bg",
        "RenderMarkdownH6Bg",
      },
      foregrounds = {
        "RenderMarkdownH1",
        "RenderMarkdownH2",
        "RenderMarkdownH3",
        "RenderMarkdownH4",
        "RenderMarkdownH5",
        "RenderMarkdownH6",
      },
    },
    code = {
      style = "full",
      width = "block",
      right_pad = 2,
      left_pad = 2,
      border = "thick",
    },
    bullet = {
      icons = { "●", "○", "◆", "◇" },
    },
    checkbox = {
      position = "inline",
      unchecked = { icon = "󰄱 ", highlight = "RenderMarkdownUnchecked" },
      checked = { icon = "󰱒 ", highlight = "RenderMarkdownChecked" },
      custom = {
        todo = { raw = "[-]", rendered = "󰥔 ", highlight = "RenderMarkdownTodo" },
        in_progress = { raw = "[~]", rendered = "󰔟 ", highlight = "RenderMarkdownWarn" },
        canceled = { raw = "[/]", rendered = "󰜺 ", highlight = "RenderMarkdownError" },
      },
    },
    link = {
      hyperlink = "󰌹 ",
      image = "󰥶 ",
      email = "󰀓 ",
      wiki = { icon = "󱗖 " },
      custom = {
        github = { pattern = "github%.com", icon = "󰊤 " },
        youtube = { pattern = "youtu%.be", icon = "󰗃 " },
      },
    },
    pipe_table = {
      preset = "round",
      cell = "padded",
    },
    dash = {
      icon = "─",
      width = "full",
    },
    quote = {
      icon = "▋",
    },
    overrides = {
      buftype = {
        nofile = {
          render_modes = true,
          code = { left_pad = 0, right_pad = 0 },
          sign = { enabled = false },
        },
      },
    },
  },
}
