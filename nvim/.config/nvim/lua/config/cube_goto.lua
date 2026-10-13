-- `gd` for Cube model YAML (model/cubes, model/views). yamlls has no definitions for these files, so the
-- LSP `gd` is a no-op there. Two things are navigable: the Jinja helpers (`fk_join`, `measure_meta`, ...), which are
-- plain Python functions at the repo root, and cube/view/member references (`bills.matters`,
-- `{billing_entries.hours_billed_sum}`), which are `- name:` entries in the model files. Anything unresolved falls
-- through to the LSP so the map never makes `gd` worse than it was.
local M = {}

local function in_model_file(bufnr)
  local path = vim.api.nvim_buf_get_name(bufnr)
  return path:find("/model/cubes/", 1, true) ~= nil or path:find("/model/views/", 1, true) ~= nil
end

-- <cword> splits on `.`, which would hide the cube/member pair, and <cWORD> drags in braces, quotes and commas.
-- Scan the identifier-and-dot run ourselves: braces and quotes fall away because they are not in the class.
local function token_under_cursor()
  local line = vim.api.nvim_get_current_line()
  local col = vim.api.nvim_win_get_cursor(0)[2] + 1
  if not line:sub(col, col):match("[%w_%.]") then
    return nil
  end
  local first, last = col, col
  while first > 1 and line:sub(first - 1, first - 1):match("[%w_%.]") do
    first = first - 1
  end
  while last < #line and line:sub(last + 1, last + 1):match("[%w_%.]") do
    last = last + 1
  end
  local parts = {}
  local part_index
  local start = first
  for part in (line:sub(first, last) .. "."):gmatch("([^%.]*)%.") do
    local stop = start + #part - 1
    if part_index == nil and col <= stop + 1 then
      part_index = #parts + 1
    end
    if part ~= "" then
      parts[#parts + 1] = part
    elseif part_index == #parts + 1 then
      part_index = nil
    end
    start = stop + 2
  end
  return { parts = parts, index = part_index or #parts, line = line }
end

local function rg(args, cwd)
  local cmd = { "rg", "--no-heading", "--line-number", "--column", "--color=never" }
  vim.list_extend(cmd, args)
  local result = vim.system(cmd, { cwd = cwd, text = true }):wait()
  local matches = {}
  for _, hit in ipairs(vim.split(result.stdout or "", "\n", { trimempty = true })) do
    local file, lnum, col = hit:match("^(.-):(%d+):(%d+):")
    if file then
      matches[#matches + 1] = { file = cwd .. "/" .. file, lnum = tonumber(lnum), col = tonumber(col) }
    end
  end
  return matches
end

local function find_function(name, root)
  return rg({ "-e", "^def " .. name .. "\\(", "--max-depth", "1", "-g", "*.py", ".", "model/globals.py" }, root)
end

local function find_cube(cube, root)
  return rg({ "-e", "^  - name: " .. cube .. "\\s*$", "model/cubes", "model/views" }, root)
end

-- A member is a `- name:` indented deeper than the cube's own `- name:`, before the next entry at or above that
-- indent. This also lands on a `joins:` entry of the same name, which is the right place to look anyway.
local function find_member(cube_match, member)
  local lines = vim.fn.readfile(cube_match.file)
  local cube_indent = #lines[cube_match.lnum]:match("^%s*")
  for lnum = cube_match.lnum + 1, #lines do
    local indent, name = lines[lnum]:match("^(%s*)%- name:%s*([%w_]+)%s*$")
    if indent and #indent <= cube_indent then
      return nil
    end
    if name == member then
      return { file = cube_match.file, lnum = lnum, col = #indent + 3 }
    end
  end
  return nil
end

local function find_reference(token, root)
  local parts, index = token.parts, token.index
  -- In a join_path the right-hand part is a cube, not a member of the left-hand one.
  local is_join_path = token.line:match("^%s*%-?%s*join_path:") ~= nil
  if index > 1 and not is_join_path then
    local found = {}
    for _, cube_match in ipairs(find_cube(parts[index - 1], root)) do
      local member_match = find_member(cube_match, parts[index])
      if member_match then
        found[#found + 1] = member_match
      end
    end
    if #found > 0 then
      return found
    end
  end
  return find_cube(parts[index], root)
end

local function jump(match)
  vim.cmd("normal! m'")
  if vim.api.nvim_buf_get_name(0) ~= match.file then
    vim.cmd("edit " .. vim.fn.fnameescape(match.file))
  end
  vim.api.nvim_win_set_cursor(0, { match.lnum, match.col - 1 })
  vim.cmd("normal! zz")
end

local function show_all(matches, title)
  if _G.Snacks and Snacks.picker then
    local items = {}
    for _, match in ipairs(matches) do
      items[#items + 1] = { text = match.file, file = match.file, pos = { match.lnum, match.col - 1 } }
    end
    Snacks.picker.pick({ title = title, items = items, format = "file" })
    return
  end
  vim.fn.setqflist({}, " ", {
    title = title,
    items = vim.tbl_map(function(match)
      return { filename = match.file, lnum = match.lnum, col = match.col, text = title }
    end, matches),
  })
  vim.cmd("copen")
end

function M.goto_definition()
  local bufnr = vim.api.nvim_get_current_buf()
  local root = vim.fs.root(bufnr, ".git")
  local token = token_under_cursor()
  local matches = {}
  if root and token and #token.parts > 0 then
    local word = token.parts[token.index]
    matches = find_function(word, root)
    if #matches == 0 then
      matches = find_reference(token, root)
    end
  end
  if #matches == 0 then
    vim.lsp.buf.definition()
  elseif #matches == 1 then
    jump(matches[1])
  else
    show_all(matches, "Definitions: " .. token.parts[token.index])
  end
end

local member_sections = { measures = "measure", dimensions = "dimension", segments = "segment" }

-- Every def, cube/view and measure/dimension/segment, as picker items. Cubes sit at indent 2 (`- name:`), their
-- sections (`measures:` ...) at indent 4 and members at indent 6; `joins:` and a view's `includes:` also hold
-- `- name:` lines, so members count only directly under a member section.
function M.build_index(root)
  local items = {}
  local function add(kind, label, file, lnum, col)
    items[#items + 1] = {
      kind = kind,
      text = kind .. " " .. label .. " " .. vim.fn.fnamemodify(file, ":t"),
      label = label,
      file = file,
      pos = { lnum, col - 1 },
    }
  end
  local defs = rg({ "-e", "^def ([A-Za-z_0-9]+)\\(", "--max-depth", "1", "-g", "*.py", ".", "model/globals.py" }, root)
  for _, def in ipairs(defs) do
    local line = vim.fn.readfile(def.file, "", def.lnum)[def.lnum]
    add("function", line:match("^def ([%w_]+)"), def.file, def.lnum, def.col)
  end
  local files = vim.fn.glob(root .. "/model/cubes/*.yml", false, true)
  vim.list_extend(files, vim.fn.glob(root .. "/model/views/*.yml", false, true))
  for _, file in ipairs(files) do
    local cube, section
    for lnum, line in ipairs(vim.fn.readfile(file)) do
      local indent, name = line:match("^(%s*)%- name:%s*([%w_]+)%s*$")
      if indent and #indent == 2 then
        cube, section = name, nil
        add("cube", name, file, lnum, 5)
      elseif cube then
        local key = line:match("^    ([a-z_]+):")
        if key then
          section = member_sections[key]
        elseif indent and #indent == 6 and section then
          add(section, cube .. "." .. name, file, lnum, 9)
        end
      end
    end
  end
  return items
end

function M.workspace_symbols()
  local root = vim.fs.root(0, ".git")
  if not root or not (_G.Snacks and Snacks.picker) then
    return Snacks.picker.lsp_workspace_symbols({ filter = { default = true } })
  end
  Snacks.picker.pick({
    title = "Cube model symbols",
    items = M.build_index(root),
    format = function(item)
      return {
        { string.format("%-9s", item.kind), "Comment" },
        { item.label },
        { "  " .. vim.fn.fnamemodify(item.file, ":t"), "Comment" },
      }
    end,
  })
end

function M.attach(bufnr)
  if in_model_file(bufnr) then
    vim.keymap.set("n", "gd", M.goto_definition, { buffer = bufnr, desc = "Go to definition (Cube model)" })
    vim.keymap.set("n", "<leader>ss", M.workspace_symbols, { buffer = bufnr, desc = "Cube model symbols" })
  end
end

function M.setup()
  local group = vim.api.nvim_create_augroup("cube_goto", { clear = true })
  -- lsp.lua maps `gd` buffer-locally on LspAttach, and yamlls attaches after FileType, so a FileType map alone gets
  -- overwritten. Re-set it on LspAttach too. lsp.lua loads on VeryLazy, after this module, so its LspAttach handler is
  -- registered AFTER ours and would win by autocmd order; vim.schedule defers our map until every handler has run.
  vim.api.nvim_create_autocmd("FileType", {
    group = group,
    pattern = "yaml",
    callback = function(args)
      M.attach(args.buf)
    end,
  })
  vim.api.nvim_create_autocmd("LspAttach", {
    group = group,
    callback = function(args)
      vim.schedule(function()
        if vim.api.nvim_buf_is_valid(args.buf) then
          M.attach(args.buf)
        end
      end)
    end,
  })
end

return M
