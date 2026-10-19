-- Snacks dashboard sections for plugins/snacks.lua: a milli.nvim splash,
-- the keys two per row, and the open org todos.
local M = {}

-- The left slot of a keyed row: the key, a space of icon width, a space of
-- padding. Key-grid cells match it so every key sits in one column.
local KEY_SLOT_WIDTH = 3

-- milli.play rewrites whole buffer lines, so in the dashboard buffer it would
-- wipe the pane beside it. It plays in a float instead, centered on the keys
-- pane, so the dashboard's height and centering follow that pane alone.
local function open_splash(dashboard, pos, splash)
  local splash_buf = vim.api.nvim_create_buf(false, true)
  vim.api.nvim_buf_set_lines(splash_buf, 0, -1, false, splash.frames[1])

  local content_height = #dashboard.lines - dashboard.row
  local row_offset = math.floor((content_height - splash.rows) / 2)
  local col_offset = math.floor((dashboard.opts.width - splash.cols) / 2)
  local splash_win = vim.api.nvim_open_win(splash_buf, false, {
    relative = "win",
    win = dashboard.win,
    bufpos = { pos[1] - 1, pos[2] + 1 },
    row = row_offset,
    col = col_offset,
    width = splash.cols,
    height = splash.rows,
    focusable = false,
    noautocmd = true,
    style = "minimal",
    border = "none",
    zindex = Snacks.config.styles.dashboard.zindex + 1,
  })
  vim.wo[splash_win].winhighlight = "NormalFloat:SnacksDashboardNormal"

  require("milli").play(splash_buf, { data = splash, loop = true })

  -- Every render opens a new float, so this one goes on re-render and on close.
  local function close()
    pcall(vim.api.nvim_win_close, splash_win, true)
    pcall(vim.api.nvim_buf_delete, splash_buf, { force = true })
    return true
  end
  dashboard.on("UpdatePre", close, dashboard.augroup)
  dashboard.on("Closed", close, dashboard.augroup)
end

-- The same test snacks' layout uses to decide whether panes stack.
local function panes_side_by_side(dashboard)
  local pane_span = dashboard.opts.width + dashboard.opts.pane_gap
  return dashboard._size.width + dashboard.opts.pane_gap >= pane_span * 2
end

-- Section: a milli splash by name, or a list of names to pick one from per
-- session. It shows only beside the keys pane, in a window tall enough for it.
-- Splashes wider than the pane spill past it.
function M.splash(splash_names)
  return function(dashboard)
    if not panes_side_by_side(dashboard) then
      return {}
    end

    local splash = require("milli").load({ splash = splash_names })
    if dashboard._size.height < splash.rows then
      return {}
    end

    return {
      text = "",
      render = function(_, pos)
        open_splash(dashboard, pos, splash)
      end,
    }
  end
end

local function key_cell(key, cell_width)
  return {
    { key.key, hl = "key", width = KEY_SLOT_WIDTH },
    { key.desc, hl = "desc", width = cell_width - KEY_SLOT_WIDTH },
  }
end

-- Section: `keys` ({ key, desc, action } each) two per row. A dashboard item
-- holds one action, so the rows are plain text and hidden items bind the keys.
function M.key_grid(keys)
  return function(dashboard)
    local cell_width = math.floor(dashboard.opts.width / 2)
    local items = {}
    for _, key in ipairs(keys) do
      table.insert(items, { hidden = true, key = key.key, action = key.action })
    end

    for first = 1, #keys, 2 do
      local row = key_cell(keys[first], cell_width)
      local second = keys[first + 1]
      if second then
        vim.list_extend(row, key_cell(second, cell_width))
      end
      table.insert(items, { text = row })
    end

    return items
  end
end

local function todo_line(todo, line_width)
  local keyword = todo.keyword .. " "
  local heading_width = line_width - vim.api.nvim_strwidth(keyword)
  local heading = Snacks.picker.util.truncate(todo.heading, heading_width)
  return { { keyword, hl = "dir" }, { heading, hl = "file" } }
end

local function open_todo(todo)
  vim.cmd.edit(vim.fn.fnameescape(todo.path))
  vim.api.nvim_win_set_cursor(0, { todo.lnum, 0 })
  vim.cmd("normal! zv")
end

-- Section: up to `limit` open org todos on autokeys, cut to the pane width.
function M.todos(limit)
  return function(dashboard)
    local line_width = dashboard.opts.width - KEY_SLOT_WIDTH
    local items = {}
    for _, todo in ipairs(require("util.org_agenda").open_todos(limit)) do
      table.insert(items, {
        icon = "key",
        autokey = true,
        desc = todo_line(todo, line_width),
        action = function()
          open_todo(todo)
        end,
      })
    end
    return items
  end
end

return M
