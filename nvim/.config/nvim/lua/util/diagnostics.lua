-- Project-wide diagnostic runner for TS/Vue (vue-tsc/tsc) and Python (pyright).
-- Scans the cwd and its immediate subdirs for tsconfig.json / pyproject.toml,
-- builds one shell command per project root, and streams output into the quickfix
-- list. Kept in util/ so keymaps.lua stays as a thin dispatch layer.
local M = {}

function M.project()
  local cwd = vim.fn.getcwd()
  local cmds = {}
  local dirs = { cwd }
  for _, entry in ipairs(vim.fn.readdir(cwd)) do
    local path = cwd .. "/" .. entry
    if vim.fn.isdirectory(path) == 1 and entry ~= "node_modules" and entry ~= ".venv" then
      table.insert(dirs, path)
    end
  end
  local seen = {}
  for _, dir in ipairs(dirs) do
    if not seen[dir] then
      seen[dir] = true
      if vim.fn.filereadable(dir .. "/tsconfig.json") == 1 then
        table.insert(cmds, "cd " .. vim.fn.shellescape(dir) .. " && npx vue-tsc --noEmit 2>&1 || npx tsc --noEmit 2>&1")
      end
      if vim.fn.filereadable(dir .. "/pyproject.toml") == 1 then
        table.insert(cmds, "cd " .. vim.fn.shellescape(dir) .. " && uv run pyright 2>&1")
      end
    end
  end
  if #cmds == 0 then
    vim.notify("No supported project found", vim.log.levels.WARN)
    return
  end
  local cmd = table.concat(cmds, "; ")
  vim.notify("Running project diagnostics...")
  vim.fn.jobstart(cmd, {
    cwd = cwd,
    stdout_buffered = true,
    on_stdout = function(_, data)
      vim.schedule(function()
        local lines = table.concat(data, "\n")
        if lines == "" then
          vim.notify("No errors found!")
          return
        end
        vim.fn.setqflist({}, " ", { title = "Project Diagnostics", lines = data })
        vim.cmd("copen")
      end)
    end,
  })
end

return M
