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

      lint.linters_by_ft = {
        sh = { "shellcheck" },
        bash = { "shellcheck" },
        markdown = { "markdownlint" },
        yaml = { "yamllint" },
      }

      vim.api.nvim_create_autocmd({ "BufWritePost", "BufReadPost", "InsertLeave" }, {
        group = vim.api.nvim_create_augroup("nvim_lint", { clear = true }),
        callback = function()
          -- try_lint without args uses linters_by_ft for the current filetype.
          lint.try_lint()
        end,
      })
    end,
  },
}
