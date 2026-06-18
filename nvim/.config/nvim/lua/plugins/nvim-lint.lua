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
  src = "mfussenegger/nvim-lint",
  setup = function()
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

    -- Memoize the executable() check by linter name. Availability is stable for
    -- the session once mason finishes installing, so there's no need to re-probe
    -- PATH on every BufWritePost/BufReadPost/InsertLeave. A nil entry means "not
    -- yet resolved"; once a linter resolves to true it's cached, and false
    -- results are retried (so a tool that installs mid-session is picked up).
    local available_cache = {}
    local function is_available(name)
      if available_cache[name] then
        return true
      end
      local linter = lint.linters[name]
      if type(linter) == "function" then
        linter = linter()
      end
      local cmd = linter and linter.cmd
      local ok = cmd ~= nil and vim.fn.executable(cmd) == 1
      available_cache[name] = ok
      return ok
    end

    vim.api.nvim_create_autocmd({ "BufWritePost", "BufReadPost", "InsertLeave" }, {
      group = vim.api.nvim_create_augroup("nvim_lint", { clear = true }),
      callback = function()
        -- Only run linters whose binary is actually installed, so a missing
        -- tool (e.g. before mason finishes installing) can't throw ENOENT
        -- inside BufReadPost and break buffer loads / harpoon jumps.
        local names = lint.linters_by_ft[vim.bo.filetype] or {}
        local available = {}
        for _, name in ipairs(names) do
          if is_available(name) then
            table.insert(available, name)
          end
        end
        if #available > 0 then
          lint.try_lint(available)
        end
      end,
    })
  end,
}
