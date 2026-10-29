-- Keep links concealed on the cursor line in normal mode, so moving the cursor
-- doesn't unhide the URL and rewrap the line. Insert mode still shows raw text.
vim.opt_local.concealcursor = "nc"

-- gf — open the destination of the [text](dest) link under the cursor. The
-- destination is concealed, so plain gf only sees the link text. Relative
-- paths resolve from this file's folder; URLs go to the system opener.
local function link_destination_under_cursor()
  local node = vim.treesitter.get_node({ ignore_injections = false })
  while node and node:type() ~= "inline_link" do
    node = node:parent()
  end
  if not node then
    return nil
  end

  for child in node:iter_children() do
    if child:type() == "link_destination" then
      return vim.treesitter.get_node_text(child, 0)
    end
  end
  return nil
end

vim.keymap.set("n", "gf", function()
  local destination = link_destination_under_cursor()
  if not destination then
    vim.cmd("normal! gf")
    return
  end

  if destination:match("^%a[%w+.-]*://") then
    vim.ui.open(destination)
    return
  end

  local path = destination:gsub("#.*$", "")
  local folder = vim.fn.expand("%:p:h")
  local full_path = vim.fs.normalize(vim.fs.joinpath(folder, path))
  vim.cmd.edit(vim.fn.fnameescape(full_path))
end, { buffer = true, desc = "Follow markdown link" })

-- ]] / [[ — nvim's markdown heading jumps — also scroll the heading to the top.
local heading_jump_descs = { ["]]"] = "Next heading to top", ["[["] = "Previous heading to top" }

for lhs, desc in pairs(heading_jump_descs) do
  local heading_jump = vim.fn.maparg(lhs, "n", false, true).callback
  if heading_jump then
    vim.keymap.set("n", lhs, function()
      heading_jump()
      vim.cmd("normal! zt")
    end, { buffer = true, desc = desc })
  end
end
