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

      -- ── JS/TS: vscode-js-debug via Mason's js-debug-adapter ──────────────
      -- `pwa-node` is Microsoft's modern Node debugger (replaces the legacy
      -- `node2` adapter). It speaks DAP over a TCP port that the dapDebugServer
      -- script spawns for us; `${port}` is interpolated by nvim-dap.
      dap.adapters["pwa-node"] = {
        type = "server",
        host = "127.0.0.1",
        port = "${port}",
        executable = {
          command = "node",
          args = {
            vim.fn.stdpath("data") .. "/mason/packages/js-debug-adapter/js-debug/src/dapDebugServer.js",
            "${port}",
          },
        },
      }

      for _, lang in ipairs({ "typescript", "javascript", "typescriptreact", "javascriptreact" }) do
        dap.configurations[lang] = {
          {
            name = "Launch current file (node)",
            type = "pwa-node",
            request = "launch",
            program = "${file}",
            cwd = "${workspaceFolder}",
            sourceMaps = true,
            protocol = "inspector",
            console = "integratedTerminal",
            skipFiles = { "<node_internals>/**", "node_modules/**" },
          },
          {
            -- Requires `tsx` (npm i -g tsx, or in project devDeps).
            -- Lets you debug .ts files directly without a compile step.
            name = "Launch current file (tsx)",
            type = "pwa-node",
            request = "launch",
            runtimeExecutable = "tsx",
            program = "${file}",
            cwd = "${workspaceFolder}",
            sourceMaps = true,
            protocol = "inspector",
            console = "integratedTerminal",
            skipFiles = { "<node_internals>/**", "node_modules/**" },
          },
          {
            name = "Attach to process",
            type = "pwa-node",
            request = "attach",
            processId = require("dap.utils").pick_process,
            cwd = "${workspaceFolder}",
            sourceMaps = true,
          },
          {
            -- For `node --inspect` or `node --inspect-brk` (default port 9229).
            name = "Attach to :9229 (node --inspect)",
            type = "pwa-node",
            request = "attach",
            address = "localhost",
            port = 9229,
            cwd = "${workspaceFolder}",
            sourceMaps = true,
            skipFiles = { "<node_internals>/**", "node_modules/**" },
          },
        }
      end

      dap.listeners.after.event_initialized["dapui_config"] = function()
        vim.fn.system("tmux resize-pane -Z")
        dapui.open()
      end

      local function close_dap()
        dapui.close()
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
