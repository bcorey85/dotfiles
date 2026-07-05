return {
  "stevearc/conform.nvim",
  event = { "BufWritePre" },
  cmd = { "ConformInfo", "FormatDisable", "FormatEnable" },
  keys = { { "<leader>lf", desc = "Format buffer (conform)" } },
  config = function()
    require("conform").setup({
      formatters_by_ft = {
        lua = { "stylua" },
        -- bashls provides no formatting, so shell would otherwise go
        -- unformatted (lsp_format="fallback" has nothing to fall back to).
        -- shfmt rounds out the toolchain for this shell-heavy dotfiles repo.
        sh = { "shfmt" },
        bash = { "shfmt" },
        -- Mirror the repo's pre-commit (ruff-check --fix → ruff-format) so a
        -- saved buffer is already commit-clean. ruff reads pyproject.toml
        -- (e.g. line-length = 120) and owns import sorting via the I rules —
        -- black (wraps at 88) + isort would fight it and churn the diff.
        python = { "ruff_fix", "ruff_format" },
        javascript = { "prettier" },
        javascriptreact = { "prettier" },
        typescript = { "prettier" },
        typescriptreact = { "prettier" },
        vue = { "prettier" },
        css = { "prettier" },
        scss = { "prettier" },
        html = { "prettier" },
        json = { "prettier" },
        jsonc = { "prettier" },
        yaml = { "prettier" },
        markdown = { "prettier" },
      },
      -- format_on_save as a function so we can respect the disable escape hatch
      -- (vim.g.disable_autoformat / vim.b.disable_autoformat) per the conform README.
      format_on_save = function(bufnr)
        if vim.g.disable_autoformat or vim.b[bufnr].disable_autoformat then
          return
        end
        -- format_on_save is synchronous (it must finish before the write), so the
        -- timeout is also the worst-case UI freeze on save — and autowrite=true
        -- means buffer switches / :make trigger it too. lsp_format="fallback"
        -- routes filetypes with no conform formatter through the LSP, which is the
        -- slowest/least predictable path; 1000ms caps the stall without tripping
        -- the fast CLI formatters (stylua/ruff/prettier finish well under it).
        return { timeout_ms = 1000, lsp_format = "fallback" }
      end,
    })

    -- Gate prettier on project config presence so it doesn't reformat repos
    -- that don't use prettier. require_cwd makes the formatter a no-op when
    -- no prettier config is found in the project root.
    require("conform").formatters.prettier = { require_cwd = true }

    vim.keymap.set("n", "<leader>lf", function()
      require("conform").format({ async = true, lsp_format = "fallback" })
    end, { desc = "Format buffer (conform)" })

    -- Escape hatch: :FormatDisable (global) or :FormatDisable! (buffer-local).
    -- :FormatEnable clears both flags. Follows the conform README recipe verbatim.
    vim.api.nvim_create_user_command("FormatDisable", function(args)
      if args.bang then
        vim.b.disable_autoformat = true
      else
        vim.g.disable_autoformat = true
      end
    end, {
      desc = "Disable autoformat-on-save",
      bang = true,
    })
    vim.api.nvim_create_user_command("FormatEnable", function()
      vim.b.disable_autoformat = false
      vim.g.disable_autoformat = false
    end, {
      desc = "Re-enable autoformat-on-save",
    })
  end,
}
