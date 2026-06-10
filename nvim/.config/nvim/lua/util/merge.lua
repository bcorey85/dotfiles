-- Native (plugin-free) git merge-conflict resolution. Operates directly on the
-- conflict markers git writes into the working file — no plugins required.
-- Also works on the middle/working buffer inside a `:Gdiffsplit!` 3-way split.
-- choose ours / theirs / both, per-conflict or whole-file, plus navigation.
-- Handles diff3/zdiff3 style (with a ||||||| base section) and the default style.
local M = {}

local START, BASE, SEP, END = "^<<<<<<<", "^|||||||", "^=======", "^>>>>>>>"

-- Find the first conflict block whose END is at or after `from_line`. Returns
-- start_line, end_line (1-indexed, inclusive of markers), ours, theirs (line
-- lists) — or nil if none.
local function find_conflict(buf, from_line)
  local lines = vim.api.nvim_buf_get_lines(buf, 0, -1, false)
  local i = 1
  while i <= #lines do
    if lines[i]:match(START) then
      local s, base_i, sep_i, end_i = i, nil, nil, nil
      local j = i + 1
      while j <= #lines do
        if lines[j]:match(BASE) and not base_i then
          base_i = j
        elseif lines[j]:match(SEP) and not sep_i then
          sep_i = j
        elseif lines[j]:match(END) then
          end_i = j
          break
        end
        j = j + 1
      end
      if end_i and sep_i and end_i >= from_line then
        local ours = vim.list_slice(lines, s + 1, (base_i or sep_i) - 1)
        local theirs = vim.list_slice(lines, sep_i + 1, end_i - 1)
        return s, end_i, ours, theirs
      end
      i = (end_i or s) + 1
    else
      i = i + 1
    end
  end
  return nil
end

local function repl_for(kind, ours, theirs)
  if kind == "ours" then
    return ours
  elseif kind == "theirs" then
    return theirs
  elseif kind == "both" then
    return vim.list_extend(vim.list_slice(ours, 1, #ours), theirs)
  elseif kind == "none" then
    return {}
  end
end

-- Resolve the conflict at/after the cursor.
function M.choose(kind)
  local buf = vim.api.nvim_get_current_buf()
  local cur = vim.api.nvim_win_get_cursor(0)[1]
  local s, e, ours, theirs = find_conflict(buf, cur)
  if not s then
    vim.notify("No conflict at or after cursor", vim.log.levels.WARN)
    return
  end
  vim.api.nvim_buf_set_lines(buf, s - 1, e, false, repl_for(kind, ours, theirs))
  vim.api.nvim_win_set_cursor(0, { math.min(s, vim.api.nvim_buf_line_count(buf)), 0 })
end

-- Resolve EVERY conflict in the buffer with the same choice.
function M.choose_all(kind)
  local buf = vim.api.nvim_get_current_buf()
  local guard = 0
  while guard < 1000 do
    guard = guard + 1
    local s, e, ours, theirs = find_conflict(buf, 1)
    if not s then
      break
    end
    vim.api.nvim_buf_set_lines(buf, s - 1, e, false, repl_for(kind, ours, theirs))
  end
end

-- Jump to the next / previous conflict marker and center.
function M.next()
  if vim.fn.search(START, "W") == 0 then
    vim.notify("No more conflicts", vim.log.levels.INFO)
  else
    vim.cmd("normal! zz")
  end
end

function M.prev()
  if vim.fn.search(START, "bW") == 0 then
    vim.notify("No previous conflict", vim.log.levels.INFO)
  else
    vim.cmd("normal! zz")
  end
end

-- Buffer-local keymaps for conflict resolution. Idempotent.
function M.attach(buf)
  if vim.b[buf].merge_keys then
    return
  end
  vim.b[buf].merge_keys = true
  local function map(lhs, fn, desc)
    vim.keymap.set("n", lhs, fn, { buffer = buf, desc = desc })
  end
  map("<leader>ch", function() M.choose("ours") end, "Conflict: choose ours (left)")
  map("<leader>cl", function() M.choose("theirs") end, "Conflict: choose theirs (right)")
  map("<leader>cb", function() M.choose("both") end, "Conflict: keep both (ours+theirs)")
  map("<leader>cn", function() M.choose("none") end, "Conflict: keep neither")
  map("<leader>cH", function() M.choose_all("ours") end, "Conflict: ours, whole file")
  map("<leader>cL", function() M.choose_all("theirs") end, "Conflict: theirs, whole file")
  map("<leader>cB", function() M.choose_all("both") end, "Conflict: both, whole file")
  map("<leader>cj", M.next, "Conflict: next")
  map("<leader>ck", M.prev, "Conflict: prev")
end

return M
