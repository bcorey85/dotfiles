-- Pull test failures out of a tmux pane into the quickfix list.
--
-- The return path of the tests-run-in-tmux workflow. The outbound path is
-- typing the test command in a tmux pane; after a failure, <leader>tq captures
-- that pane's scrollback, runs it through errorformat, and turns every
-- file:line reference that resolves to a real project file into a quickfix
-- entry — failures become ]q/[q jump targets (rendered by quicker.nvim) instead
-- of text to read, remember, and retype.
--
-- Pane selection: every pane in the current tmux session is a candidate except
-- this one and any other pane running nvim. One candidate → used directly;
-- several → vim.ui.select (snacks) prompts once and caches the choice for this
-- nvim session (<leader>tQ re-picks; a dead cached pane re-prompts on its own).
--
-- Parsing is errorformat-based (python tracebacks + pytest summaries, node/
-- jest/vitest stacks, tsc, generic file:line:col). Precision comes from the
-- FILTER, not the patterns: an entry survives only if its file exists on disk
-- and isn't dependency/runtime code (node_modules, site-packages, .venv,
-- /usr/). Random colon-separated text ("16:04:32") dies at the filereadable
-- check, so the patterns can afford to be greedy.

local M = {}

local efm = table.concat({
  [[%*[ ]File "%f"\, line %l%.%#]], -- python traceback frame
  [[%*[ ]at%.%#(%f:%l:%c)]], -- node stack frame: at fn (file:l:c)
  [[%*[ ]at %f:%l:%c]], -- node stack frame without wrapping parens
  [[%*[ ]❯ %f:%l:%c]], -- vitest failure location marker
  [[FAILED %f::%m]], -- pytest short test summary line
  [[%f(%l\,%c): %m]], -- tsc: file(l,c): error TS…
  [[%f:%l:%c: %m]],
  [[%f:%l: %m]],
}, ",")

-- Dependency/runtime frames: real files, but never where the failure lives.
local exclude = { "/node_modules/", "/site%-packages/", "/%.venv/", "^/usr/" }

local function project_items(items)
  local seen, kept = {}, {}
  for _, it in ipairs(items) do
    if it.valid == 1 and it.bufnr and it.bufnr > 0 then
      local name = vim.api.nvim_buf_get_name(it.bufnr)
      local excluded = false
      for _, pat in ipairs(exclude) do
        if name:find(pat) then
          excluded = true
          break
        end
      end
      if not excluded and vim.fn.filereadable(name) == 1 then
        local key = it.bufnr .. ":" .. (it.lnum or 0) .. ":" .. (it.col or 0)
        if not seen[key] then
          seen[key] = true
          kept[#kept + 1] = it
        end
      end
    end
  end
  return kept
end

-- Parse raw pane lines and fill the quickfix list. Public so a non-tmux
-- source (e.g. a log file) can reuse the same parse+filter pipeline.
function M.fill_from_lines(lines, label)
  -- getqflist({lines=…}) parses through efm WITHOUT touching the real list;
  -- only the filtered survivors get set.
  local parsed = vim.fn.getqflist({ lines = lines, efm = efm })
  local items = project_items(parsed.items or {})
  if #items == 0 then
    vim.notify("No test failures found in " .. label, vim.log.levels.INFO)
    return false
  end
  vim.fn.setqflist({}, " ", { items = items, title = "Test failures (" .. label .. ")" })
  vim.cmd("botright copen")
  return true
end

local cached ---@type {id: string, label: string}|nil

local function pane_alive(id)
  vim.fn.system({ "tmux", "display-message", "-p", "-t", id, "" })
  return vim.v.shell_error == 0
end

local function capture(pane)
  -- -S -2000: last 2000 scrollback lines; plain text (no -e = escapes dropped).
  local lines = vim.fn.systemlist({ "tmux", "capture-pane", "-p", "-t", pane.id, "-S", "-2000" })
  if vim.v.shell_error ~= 0 then
    cached = nil
    vim.notify("tmux capture-pane failed for " .. pane.label, vim.log.levels.ERROR)
    return
  end
  M.fill_from_lines(lines, pane.label)
end

local function candidates()
  local own = vim.env.TMUX_PANE
  local raw = vim.fn.systemlist({
    "tmux",
    "list-panes",
    "-s",
    "-F",
    "#{pane_id}\t#{window_name}\t#{pane_current_command}",
  })
  local out = {}
  for _, l in ipairs(raw) do
    local id, win, cmd = l:match("^([^\t]+)\t([^\t]*)\t(.*)$")
    if id and id ~= own and cmd ~= "nvim" then
      out[#out + 1] = { id = id, label = win .. " · " .. cmd .. " (" .. id .. ")" }
    end
  end
  return out
end

local function choose_and_capture()
  local panes = candidates()
  if #panes == 0 then
    vim.notify("No other tmux panes to capture", vim.log.levels.WARN)
    return
  end
  if #panes == 1 then
    cached = panes[1]
    capture(cached)
    return
  end
  vim.ui.select(panes, {
    prompt = "Test pane: ",
    format_item = function(p)
      return p.label
    end,
  }, function(choice)
    if not choice then
      return
    end
    cached = choice
    capture(choice)
  end)
end

-- <leader>tq — capture the (cached or auto/selected) test pane into quickfix.
function M.pull()
  if not vim.env.TMUX then
    vim.notify("Not inside tmux", vim.log.levels.WARN)
    return
  end
  if cached then
    if pane_alive(cached.id) then
      capture(cached)
      return
    end
    cached = nil
  end
  choose_and_capture()
end

-- <leader>tQ — drop the cached pane and re-pick (e.g. after moving the test
-- pane or switching which window runs the suite).
function M.repick()
  if not vim.env.TMUX then
    vim.notify("Not inside tmux", vim.log.levels.WARN)
    return
  end
  cached = nil
  choose_and_capture()
end

return M
