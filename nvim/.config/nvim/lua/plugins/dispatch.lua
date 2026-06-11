-- vim-dispatch — async :Make/:Dispatch, results land in quickfix.
-- Runs builds/tests in a tmux pane (or background job) without blocking Neovim.
-- Default maps (m<CR>, m<Space>, `<CR>, '<CR>, g'<CR> etc.) are kept — they
-- don't conflict with existing config (q→<nop>/Q→macro, C-hjkl→smart-splits).
return {
  src = "tpope/vim-dispatch",
  setup = function()
    -- <leader>t = tasks. <leader>d is deliberately left free: it's the de-facto
    -- DAP/debug namespace, reserved for if nvim-dap ever lands (C#/.NET future).
    vim.keymap.set("n", "<leader>tm", "<cmd>Make<cr>", { desc = "Make (compiler → quickfix)" })
    vim.keymap.set("n", "<leader>tM", "<cmd>Make!<cr>", { desc = "Make (background)" })
    vim.keymap.set("n", "<leader>tr", "<cmd>Dispatch<cr>", { desc = "Re-run focused task" })

    -- Open-cmdline mappings: pre-fill the command so the user can type args.
    vim.keymap.set("n", "<leader>td", ":Dispatch ", { desc = "Dispatch task…" })
    vim.keymap.set("n", "<leader>tf", ":FocusDispatch ", { desc = "Set focused task…" })
    vim.keymap.set("n", "<leader>ts", ":Start ", { desc = "Start process in tmux…" })

    -- Per-filetype defaults so <leader>dr / `<CR> work with zero typing.
    -- These are *defaults*; :FocusDispatch (or <leader>df) overrides per session.
    -- Guard `vim.b.dispatch == nil` is safe: FocusDispatch writes b:dispatch at a
    -- higher precedence, so any session override is already in place by the time
    -- this BufEnter fires on a revisited buffer.
    local dispatch_group = vim.api.nvim_create_augroup("dispatch_ft_defaults", { clear = true })
    vim.api.nvim_create_autocmd("FileType", {
      group = dispatch_group,
      pattern = { "typescript", "typescriptreact", "javascript", "javascriptreact" },
      callback = function()
        if vim.b.dispatch == nil then
          vim.b.dispatch = "npx tsc --noEmit"
        end
        -- tsc compiler ships in the Neovim runtime; sets makeprg + errorformat.
        pcall(vim.cmd.compiler, "tsc")
      end,
    })
    vim.api.nvim_create_autocmd("FileType", {
      group = dispatch_group,
      pattern = { "vue" },
      callback = function()
        if vim.b.dispatch == nil then
          vim.b.dispatch = "npx vue-tsc --noEmit"
        end
        -- No vue-tsc compiler in runtime; b:dispatch covers the workflow via
        -- :Dispatch auto-selecting errorformat by command name.
      end,
    })
    vim.api.nvim_create_autocmd("FileType", {
      group = dispatch_group,
      pattern = { "python" },
      callback = function()
        if vim.b.dispatch == nil then
          vim.b.dispatch = "uv run pyright"
        end
        -- pyright compiler ships in the Neovim runtime; sets makeprg + errorformat.
        -- b:pyright_makeprg routes :Make through uv so it matches b:dispatch
        -- (bare `pyright` would miss the project venv).
        vim.b.pyright_makeprg = "uv run pyright"
        pcall(vim.cmd.compiler, "pyright")
      end,
    })
  end,
}
