-- nvim-lint: non-LSP linting for shell, markdown, and yaml.
--
-- WHY: LSP covers type/reference errors but not shell safety (shellcheck),
-- markdown style (markdownlint), or yaml schema (yamllint). A markdownlint.jsonc
-- was already present in the repo with no runner — this wires it up.
--
-- Tool installation: shellcheck, markdownlint-cli, and yamllint are added to
-- mason-tool-installer in mason.lua so Mason keeps them current without touching
-- system package managers.
return {
  {
    "mfussenegger/nvim-lint",
    -- Load as soon as a buffer is opened so the first BufReadPost autocmd fires.
    event = { "BufReadPre", "BufNewFile" },
    config = function()
      local lint = require("lint")

      -- MD013 (line length) is noise for prose; disable it globally. A CLI
      -- --disable overrides config files and applies to every markdown buffer.
      lint.linters.markdownlint.args = { "--stdin", "--disable", "MD013" }

      lint.linters_by_ft = {
        sh = { "shellcheck" },
        bash = { "shellcheck" },
        markdown = { "markdownlint" },
        yaml = { "yamllint" },
      }

      vim.api.nvim_create_autocmd({ "BufWritePost", "BufReadPost", "InsertLeave" }, {
        group = vim.api.nvim_create_augroup("nvim_lint", { clear = true }),
        callback = function()
          -- Only run linters whose binary is actually installed, so a missing
          -- tool (e.g. before mason finishes installing) can't throw ENOENT
          -- inside BufReadPost and break buffer loads / harpoon jumps.
          local names = lint.linters_by_ft[vim.bo.filetype] or {}
          local available = {}
          for _, name in ipairs(names) do
            local linter = lint.linters[name]
            if type(linter) == "function" then
              linter = linter()
            end
            local cmd = linter and linter.cmd
            if cmd and vim.fn.executable(cmd) == 1 then
              table.insert(available, name)
            end
          end
          if #available > 0 then
            lint.try_lint(available)
          end
        end,
      })
    end,
  },
}
