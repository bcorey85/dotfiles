local exclude = {
  "node_modules",
  "dist",
  "build",
  "__pycache__",
  ".venv",
  "*.pyc",
  ".mypy_cache",
  ".ruff_cache",
  "staticfiles",
  "media",
  "*.sqlite3",
  ".git",
  ".nuxt",
}

return {
  "folke/snacks.nvim",
  priority = 1000,
  lazy = false,
  opts = {
    bigfile = { enabled = true },
    dashboard = {
      enabled = vim.env.DIFFVIEW_POPUP == nil and vim.env.NEOGIT_POPUP == nil,
      preset = {
        keys = {
          { key = "s", action = ":lua require('persistence').load()" },
          { key = "c", action = ":lua Snacks.dashboard.pick('files', {cwd = vim.fn.stdpath('config')})" },
          { key = "l", action = ":Lazy" },
          { key = "u", action = ":Lazy update" },
          { key = "q", action = ":qa" },
        },
      },
      sections = {
        { section = "header" },
        {
          align = "center",
          padding = 1,
          text = {
            { "  Session [s]  ", hl = "String" },
            { "│ ", hl = "NonText" },
            { "  Config [c]  ", hl = "Function" },
            { "│ ", hl = "NonText" },
            { " Lazy [l]  ", hl = "Special" },
            { "│ ", hl = "NonText" },
            { "  Update [u]  ", hl = "Constant" },
            { "│ ", hl = "NonText" },
            { "  Quit [q]", hl = "DiagnosticError" },
          },
        },
        { icon = " ", title = "Recent Files", section = "recent_files", indent = 2, padding = 1 },
        { icon = " ", title = "Projects", section = "projects", indent = 2, padding = 1 },
        { section = "startup" },
      },
    },
    explorer = { enabled = false },
    indent = { enabled = true },
    input = { enabled = true },
    notifier = {
      enabled = true,
      timeout = 3000,
    },
    picker = {
      enabled = true,
      sources = {
        explorer = {
          hidden = true,
          ignored = true,
          exclude = { ".git" },
          watcher = true,
        },
        files = {
          hidden = true,
          ignored = false,
          follow = true,
          exclude = exclude,
        },
        grep = {
          hidden = true,
          ignored = false,
          follow = true,
          exclude = exclude,
        },
      },
    },
    quickfile = { enabled = true },
    scope = { enabled = true },
    scroll = { enabled = false },
    statuscolumn = { enabled = false },
    words = { enabled = true },
    lazygit = { enabled = false },
    styles = {
      notification = {},
    },
  },
  keys = {
    {
      "<leader><space>",
      function()
        Snacks.picker.smart({ cwd = require("util.root").get() })
      end,
      desc = "Smart Find Files",
    },
    {
      "<leader>,",
      function()
        Snacks.picker.buffers()
      end,
      desc = "Buffers",
    },
    {
      "<leader>/",
      function()
        Snacks.picker.grep({ cwd = require("util.root").get() })
      end,
      desc = "Grep (Root Dir)",
    },
    {
      "<leader>ff",
      function()
        Snacks.picker.files({ cwd = require("util.root").get() })
      end,
      desc = "Find files (Root Dir)",
    },
    {
      "<leader>fr",
      function()
        Snacks.picker.recent()
      end,
      desc = "Recent files",
    },
    {
      "<leader>fg",
      function()
        Snacks.picker.git_files()
      end,
      desc = "Find Files (git-files)",
    },
    {
      "<leader>fb",
      function()
        Snacks.picker.buffers()
      end,
      desc = "Buffers",
    },
    {
      "<leader>fh",
      function()
        Snacks.picker.help()
      end,
      desc = "Help pages",
    },
    {
      "<leader>fk",
      function()
        Snacks.picker.keymaps()
      end,
      desc = "Keymaps",
    },
    {
      "<leader>fc",
      function()
        Snacks.picker.command_history()
      end,
      desc = "Command history",
    },
    {
      "<leader>fo",
      function()
        Snacks.picker.colorschemes()
      end,
      desc = "Colorschemes",
    },
    {
      "<leader>fI",
      function()
        Snacks.picker.files({ hidden = true, ignored = true })
      end,
      desc = "Find files (including ignored)",
    },
    {
      "<leader>sd",
      function()
        Snacks.picker.diagnostics()
      end,
      desc = "Diagnostics",
    },
    {
      "<leader>ss",
      function()
        Snacks.picker.lsp_symbols()
      end,
      desc = "LSP symbols",
    },
    {
      "<leader>sw",
      function()
        Snacks.picker.grep_word({ cwd = require("util.root").get() })
      end,
      desc = "Grep word/selection (Root Dir)",
      mode = { "n", "x" },
    },
    {
      "<leader>sG",
      function()
        Snacks.picker.grep({ cwd = vim.fn.getcwd() })
      end,
      desc = "Grep (cwd)",
    },
    {
      "<leader>sW",
      function()
        Snacks.picker.grep_word({ cwd = vim.fn.getcwd() })
      end,
      desc = "Grep word/selection (cwd)",
      mode = { "n", "x" },
    },
    {
      "<leader>wm",
      function()
        Snacks.toggle.zoom():toggle()
      end,
      desc = "Toggle Zoom",
    },
  },
}
