return {
  src = "MeanderingProgrammer/render-markdown.nvim",
  deps = {
    "nvim-treesitter/nvim-treesitter",
    "nvim-tree/nvim-web-devicons",
  },
  setup = function()
    local colors = {
      "#f76c7c",
      "#f3a96a",
      "#e3d367",
      "#9cd57b",
      "#78cee9",
      "#baa0f8",
    }
    for i, fg in ipairs(colors) do
      vim.api.nvim_set_hl(0, "RenderMarkdownH" .. i, { fg = fg, bold = true })
      vim.api.nvim_set_hl(0, "RenderMarkdownH" .. i .. "Bg", { bg = fg })
    end

    require("render-markdown").setup({
      render_modes = { "n", "c", "t" },
      latex = { enabled = false },
      yaml = { enabled = false },
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
      indent = { enabled = false },
      heading = {
        sign = false,
        icons = { "⌘ ", "λ ", "△ ", "⟐ ", "⊡ ", "∷ " },
        position = "inline",
        width = "full",
        border = true,
        border_virtual = true,
        border_prefix = false,
        above = "",
        below = "─",
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
        icons = { "»", "›", "∘", "·" },
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
    })

    local ok, Heading = pcall(require, "render-markdown.render.markdown.heading")
    if ok then
      Heading.run = function(self)
        local saved_bg = self.data.bg
        self.data.bg = nil
        self:sign(self.config, self.config.sign, self.data.sign, self.data.fg)
        local box = self:box(self:marker())
        self:padding(box)
        self.data.bg = saved_bg
        if self.data.atx then
          self:border(box, true)
          self:border(box, false)
        else
          local node = self.data.marker
          self.marks:over(self.config, true, node, { conceal = "" })
          self.marks:over(self.config, true, node, { conceal_lines = "" })
        end
      end
    end
  end,
}
