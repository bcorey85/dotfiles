return {
  "nvim-neotest/neotest",
  dependencies = {
    "nvim-neotest/nvim-nio",
    "nvim-lua/plenary.nvim",
    "antoinemadec/FixCursorHold.nvim",
    "nvim-treesitter/nvim-treesitter",
    "nvim-neotest/neotest-python",
    "marilari88/neotest-vitest",
  },
  config = function()
    require("neotest").setup({
      adapters = {
        require("neotest-python")({
          dap = { justMyCode = false },
          runner = "pytest",
          args = { "-vv" },
        }),
        require("neotest-vitest"),
      },
      status = { virtual_text = true, signs = true },
      output = { open_on_run = false },
      quickfix = { open = false },
      icons = {
        passed = " ",
        failed = " ",
        running = " ",
        skipped = " ",
        unknown = " ",
      },
    })
  end,
  keys = {
    { "<leader>tt", function() require("neotest").run.run(vim.fn.expand("%")) end, desc = "Test file" },
    { "<leader>tT", function() require("neotest").run.run(vim.uv.cwd()) end, desc = "Test all (cwd)" },
    { "<leader>tr", function() require("neotest").run.run() end, desc = "Test nearest" },
    { "<leader>tl", function() require("neotest").run.run_last() end, desc = "Test last" },
    { "<leader>ts", function() require("neotest").summary.toggle() end, desc = "Test summary" },
    { "<leader>to", function() require("neotest").output.open({ enter = true, auto_close = true }) end, desc = "Test output (float)" },
    { "<leader>tO", function() require("neotest").output_panel.toggle() end, desc = "Test output panel" },
    { "<leader>tx", function() require("neotest").run.stop() end, desc = "Test stop" },
    { "<leader>tw", function() require("neotest").watch.toggle(vim.fn.expand("%")) end, desc = "Test watch (file)" },
    { "<leader>td", function() require("neotest").run.run({ strategy = "dap" }) end, desc = "Debug nearest test" },
    { "]t", function() require("neotest").jump.next({ status = "failed" }) end, desc = "Next failed test" },
    { "[t", function() require("neotest").jump.prev({ status = "failed" }) end, desc = "Prev failed test" },
  },
}
