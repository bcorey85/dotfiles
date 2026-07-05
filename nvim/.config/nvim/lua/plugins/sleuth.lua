-- vim-sleuth — auto-detects shiftwidth/expandtab per buffer from file content,
-- modelines, and EditorConfig. The global shiftwidth=4 in options.lua becomes
-- the fallback for new/unrecognized files; Vue/TS/React repos (2-space) are
-- corrected automatically before conform's on-save format runs.
return {
  "tpope/vim-sleuth",
  event = { "BufReadPost", "BufNewFile" },
}
