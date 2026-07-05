-- Debug Adapter Protocol: nvim-dap + dap-ui + dap-python.
--
-- DEFERRED LOADING PATTERN — all three packages are installed to the runtimepath
-- by vim.pack at startup (so :PackUpdate manages them), but NO dap module is
-- required until the first <leader>d keypress. The setup() below only registers
-- keymaps; configure() does the real work the first time any of them fires.
-- Cost at startup: zero (no require("dap"), no adapter registration, no autocmds
-- from dap itself). Cost on first debug action: one-time configure() call.
return {
  -- ── core ──────────────────────────────────────────────────────────────────
  {
    src = "mfussenegger/nvim-dap",
    setup = function()
      local configured = false

      local function configure()
        if configured then
          return
        end
        configured = true

        local dap = require("dap")
        local dapui = require("dapui")

        -- dap-ui: plain defaults are fine; layout is configured inside dapui.
        dapui.setup({})

        -- dap-virtual-text: inline values next to variables while stepping,
        -- so you don't have to jump to the dap-ui scopes pane to read one.
        require("nvim-dap-virtual-text").setup({})

        -- Signs: the stock "B" breakpoint marker is near-invisible against the
        -- Catppuccin Mocha gutter. Use a bold filled dot in theme-matched colors
        -- so breakpoints actually read at a glance. Highlights are set explicitly
        -- (not linked) so they survive colorscheme reloads.
        vim.api.nvim_set_hl(0, "DapBreakpoint", { fg = "#ff5f59" }) -- red
        vim.api.nvim_set_hl(0, "DapBreakpointCondition", { fg = "#db7b5f" }) -- orange
        vim.api.nvim_set_hl(0, "DapBreakpointRejected", { fg = "#6e768a" }) -- muted
        vim.api.nvim_set_hl(0, "DapLogPoint", { fg = "#2fafff" }) -- blue
        vim.api.nvim_set_hl(0, "DapStopped", { fg = "#44bc44" }) -- green
        vim.api.nvim_set_hl(0, "DapStoppedLine", { bg = "#303030" }) -- alt

        vim.fn.sign_define("DapBreakpoint", { text = "●", texthl = "DapBreakpoint" })
        vim.fn.sign_define("DapBreakpointCondition", { text = "●", texthl = "DapBreakpointCondition" })
        vim.fn.sign_define("DapBreakpointRejected", { text = "●", texthl = "DapBreakpointRejected" })
        vim.fn.sign_define("DapLogPoint", { text = "◆", texthl = "DapLogPoint" })
        -- Stopped: arrow marker + a subtle full-line highlight on the paused line.
        vim.fn.sign_define("DapStopped", { text = "▶", texthl = "DapStopped", linehl = "DapStoppedLine" })

        -- Auto-open dap-ui when a debug session attaches or launches; auto-close
        -- on termination / exit so the layout cleans up without a manual toggle.
        dap.listeners.before.attach.dapui_config = function()
          dapui.open()
        end
        dap.listeners.before.launch.dapui_config = function()
          dapui.open()
        end
        dap.listeners.before.event_terminated.dapui_config = function()
          dapui.close()
        end
        dap.listeners.before.event_exited.dapui_config = function()
          dapui.close()
        end

        -- ── Python (debugpy via Mason) ──────────────────────────────────────
        -- Mason installs debugpy into its own venv; point dap-python at that
        -- Python so it can launch "python -m debugpy.adapter" correctly.
        require("dap-python").setup(vim.fn.stdpath("data") .. "/mason/packages/debugpy/venv/bin/python")

        -- Per-project fixed launch configs: lets a project define its own
        -- ".vscode/launch.json" (e.g. a fixed entry-point script) instead of
        -- always falling back to dap-python's generic "launch current buffer"
        -- default, which only works if the buffer you're in is the entry point.
        require("dap.ext.vscode").load_launchjs(nil, {})

        -- ── JavaScript / TypeScript (js-debug-adapter via Mason) ───────────
        -- js-debug-adapter is a DAP server (not a raw executable): nvim-dap
        -- connects to it over a TCP port. We use adapter type "server" with an
        -- executable that starts the server on a random free port and returns
        -- that port to nvim-dap via stdout.
        local js_adapter = {
          type = "server",
          host = "localhost",
          port = "${port}",
          executable = {
            command = "node",
            args = {
              vim.fn.stdpath("data") .. "/mason/packages/js-debug-adapter/js-debug/src/dapDebugServer.js",
              "${port}",
            },
          },
        }
        -- Register the adapter under every type that pwa-node configs use.
        for _, adapter_type in ipairs({ "pwa-node", "node" }) do
          dap.adapters[adapter_type] = js_adapter
        end

        -- Shared pwa-node configurations for JS and TS files.
        local js_configs = {
          {
            type = "pwa-node",
            request = "launch",
            name = "Launch file",
            program = "${file}",
            cwd = "${workspaceFolder}",
          },
          {
            type = "pwa-node",
            request = "attach",
            name = "Attach",
            processId = require("dap.utils").pick_process,
            cwd = "${workspaceFolder}",
          },
        }
        for _, ft in ipairs({ "javascript", "typescript", "javascriptreact", "typescriptreact" }) do
          dap.configurations[ft] = js_configs
        end
      end

      -- ── Keymaps ────────────────────────────────────────────────────────────
      -- Every keymap calls configure() first (no-op after first call) so the
      -- adapters and listeners are registered before any dap action is taken.
      local map = function(lhs, fn, desc)
        vim.keymap.set("n", lhs, function()
          configure()
          fn()
        end, { desc = desc })
      end

      map("<leader>db", function()
        require("dap").toggle_breakpoint()
      end, "Toggle breakpoint")

      map("<leader>dB", function()
        vim.ui.input({ prompt = "Breakpoint condition: " }, function(input)
          if input then
            require("dap").set_breakpoint(input)
          end
        end)
      end, "Conditional breakpoint")

      map("<leader>de", function()
        require("dap").set_exception_breakpoints()
      end, "Set exception breakpoints")

      map("<leader>dc", function()
        require("dap").continue()
      end, "Continue / start")

      map("<leader>dC", function()
        require("dap").run_to_cursor()
      end, "Run to cursor")

      map("<leader>di", function()
        require("dap").step_into()
      end, "Step into")

      map("<leader>dO", function()
        require("dap").step_over()
      end, "Step over")

      map("<leader>do", function()
        require("dap").step_out()
      end, "Step out")

      map("<leader>dr", function()
        require("dap").repl.toggle()
      end, "Toggle REPL")

      map("<leader>dl", function()
        require("dap").run_last()
      end, "Run last")

      map("<leader>du", function()
        require("dapui").toggle()
      end, "Toggle DAP UI")

      map("<leader>dt", function()
        require("dap").terminate()
      end, "Terminate")
    end,
  },

  -- ── dap-ui (depends on nvim-nio) ──────────────────────────────────────────
  {
    src = "rcarriga/nvim-dap-ui",
    deps = { { src = "nvim-neotest/nvim-nio" } },
  },

  -- ── dap-python ────────────────────────────────────────────────────────────
  {
    src = "mfussenegger/nvim-dap-python",
  },

  -- ── dap-virtual-text (depends on nvim-treesitter, installed separately) ───
  {
    src = "theHamsta/nvim-dap-virtual-text",
  },
}
