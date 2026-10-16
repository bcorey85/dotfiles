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
