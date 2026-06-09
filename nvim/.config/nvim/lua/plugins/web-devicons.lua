-- Loaded eagerly (not lazy) because the winbar (lua/config/winbar.lua) renders
-- a file icon on every window and needs the icon table available from the first
-- buffer. Still serves as the shared dependency for oil and render-markdown.
return {
  "nvim-tree/nvim-web-devicons",
  lazy = false,
}
