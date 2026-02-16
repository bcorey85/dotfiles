return {
  {
    "mfussenegger/nvim-dap",
    dependencies = {
      "mfussenegger/nvim-dap-python",
      "rcarriga/nvim-dap-ui",
      "nvim-neotest/nvim-nio",
    },
    keys = {
      { "<leader>db", function() require("dap").toggle_breakpoint() end, desc = "Toggle breakpoint" },
      { "<leader>dc", function() require("dap").continue() end, desc = "Start/Continue debugger" },
      { "<leader>do", function() require("dap").step_over() end, desc = "Step over" },
      { "<leader>di", function() require("dap").step_into() end, desc = "Step into" },
      { "<leader>dO", function() require("dap").step_out() end, desc = "Step out" },
      { "<leader>dx", function() require("dap").terminate() end, desc = "Stop debugger" },
      { "<leader>dB", function() require("dap").set_breakpoint(vim.fn.input("Condition: ")) end, desc = "Conditional breakpoint" },
      { "<leader>dC", function() require("dap").clear_breakpoints() end, desc = "Clear all breakpoints" },
      { "<leader>du", function() require("dapui").toggle() end, desc = "Toggle DAP UI" },
    },
    config = function()
      local dap = require("dap")
      local dapui = require("dapui")

      -- Find python: check VIRTUAL_ENV, then .venv in cwd, then system python3
      local function get_python()
        local venv = os.getenv("VIRTUAL_ENV")
        if venv then
          return venv .. "/bin/python"
        end
        local cwd_venv = vim.fn.getcwd() .. "/.venv/bin/python"
        if vim.fn.executable(cwd_venv) == 1 then
          return cwd_venv
        end
        return "python3"
      end

      require("dap-python").setup(get_python())
      dapui.setup()

      dap.listeners.after.event_initialized["dapui_config"] = function()
        dapui.open()
      end
    end,
  },
}
