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
        vim.fn.system("tmux resize-pane -Z")
        dapui.open()
      end

      local function close_dap()
        dapui.close()
        -- Unzoom if we're still zoomed
        local zoomed = vim.fn.system("tmux display-message -p '#{window_zoomed_flag}'"):gsub("%s+", "")
        if zoomed == "1" then
          vim.fn.system("tmux resize-pane -Z")
        end
      end

      dap.listeners.before.event_terminated["dapui_config"] = close_dap
      dap.listeners.before.event_exited["dapui_config"] = close_dap
    end,
  },
}
