-- The org agenda's file allowlist, read by plugins/orgmode.lua and the
-- dashboard's TODO List, plus a plain-text scan for open todo headlines.
-- plugins/orgmode.lua explains the allowlist.
local M = {}

M.files = { "~/vault/org/inbox.org", "~/vault/org/projects/*.org" }

-- Open keywords from org_todo_keywords, in dashboard order.
local open_keyword_rank = { NEXT = 1, TODO = 2, WAITING = 3 }

-- Drop the priority cookie and trailing tags from a headline title.
local function clean_heading(title)
  local without_priority = title:gsub("^%[#%w%]%s*", "")
  local without_tags = without_priority:gsub("%s+:[%w_@#%%:]+:%s*$", "")
  return without_tags
end

local function file_todos(path)
  local todos = {}
  for lnum, line in ipairs(vim.fn.readfile(path)) do
    local keyword, title = line:match("^%*+%s+(%u+)%s+(.-)%s*$")
    if keyword and open_keyword_rank[keyword] then
      table.insert(todos, { keyword = keyword, heading = clean_heading(title), path = path, lnum = lnum })
    end
  end
  return todos
end

-- Open todos across M.files: NEXT, then TODO, then WAITING, file order
-- within each keyword. At most `limit` of them.
function M.open_todos(limit)
  local todos = {}
  for _, pattern in ipairs(M.files) do
    for _, path in ipairs(vim.fn.glob(pattern, false, true)) do
      vim.list_extend(todos, file_todos(path))
    end
  end

  -- table.sort is unstable, so file order rides along as the tiebreak.
  for order, todo in ipairs(todos) do
    todo.order = order
  end
  table.sort(todos, function(a, b)
    local a_rank, b_rank = open_keyword_rank[a.keyword], open_keyword_rank[b.keyword]
    if a_rank ~= b_rank then
      return a_rank < b_rank
    end
    return a.order < b.order
  end)

  return vim.list_slice(todos, 1, limit)
end

return M
