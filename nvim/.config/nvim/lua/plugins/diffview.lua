-- diffview.nvim — the 3-way merge tool neogit delegates conflict resolution to.
-- Restores the visual 3-way merge view fugitive's `:Gdiffsplit!` used to give
-- (lost when fugitive was dropped). neogit's diffview integration is enabled in
-- plugins/neogit.lua; during a merge, :DiffviewOpen auto-detects the conflicted
-- files and opens them in the diff3 merge tool.
--
-- Source: dlyongemallo/diffview-plus.nvim — the actively-maintained fork.
-- Upstream sindrets/diffview.nvim has been stale for ~2 years. Drop-in: same
-- `diffview` module + Diffview* commands.
--
-- Conflict keys are aligned 1:1 with util/merge.lua (the plugin-free path) so
-- both feel identical: <leader>ch ours, cl theirs, cb BOTH (ours+theirs, no
-- base), cn none, cj/ck next/prev; caps = whole file. See conflict_keymaps().

-- Neovim 0.12 forbids Vimscript-y getenv in fast-event/async contexts. diffview's
-- PathLib:expand resolves `$VAR` path segments via vim.env (getenv) from inside
-- its async git jobs, raising E5560 and breaking every diff. Override that one
-- method to use os.getenv (pure Lua, fast-event-safe — same semantics). Harmless
-- if the fork already fixed it; this just redefines one method identically.
local function patch_pathlib_expand()
  local PathLib = require("diffview.path").PathLib
  function PathLib:expand(path)
    local segments = self:explode(path)
    local idx = 1
    if segments[1] == "~" then
      segments[1] = vim.uv.os_homedir()
      idx = 2
    end
    for i = idx, #segments do
      local env_var = segments[i]:match("^%$(%S+)$")
      if env_var then
        local value = os.getenv(env_var)
        if value ~= nil then
          segments[i] = value
        end
      end
    end
    return self:join(unpack(segments))
  end
end

-- Conflict keys: h=ours(left), l=theirs(right), a=keep-all (ours+theirs+base,
-- the standard 3-way-merge semantics — same as magit's smerge-keep-all and
-- ediff's `+`), n=none(delete region), j/k=next/prev; caps = whole file.
local function conflict_keymaps()
  local actions = require("diffview.actions")
  return {
    { "n", "<leader>ch", actions.conflict_choose("ours"), { desc = "Conflict: choose ours (left)" } },
    { "n", "<leader>cl", actions.conflict_choose("theirs"), { desc = "Conflict: choose theirs (right)" } },
    { "n", "<leader>ca", actions.conflict_choose("all"), { desc = "Conflict: keep all (ours+theirs+base)" } },
    { "n", "<leader>cn", actions.conflict_choose("none"), { desc = "Conflict: keep neither" } },
    { "n", "<leader>cH", actions.conflict_choose_all("ours"), { desc = "Conflict: ours, whole file" } },
    { "n", "<leader>cL", actions.conflict_choose_all("theirs"), { desc = "Conflict: theirs, whole file" } },
    { "n", "<leader>cA", actions.conflict_choose_all("all"), { desc = "Conflict: keep all, whole file" } },
    { "n", "<leader>cj", actions.next_conflict, { desc = "Conflict: next" } },
    { "n", "<leader>ck", actions.prev_conflict, { desc = "Conflict: prev" } },
  }
end

local function close_diffview()
  vim.cmd("DiffviewClose")
end

return {
  src = "dlyongemallo/diffview-plus.nvim",
  setup = function()
    patch_pathlib_expand()

    local opts = {
      view = {
        merge_tool = {
          -- diff3_horizontal: OURS | BASE | THEIRS panes with conflict
          -- highlighting — the proper layout for resolving (diffview default).
          layout = "diff3_horizontal",
          disable_diagnostics = true,
        },
      },
      keymaps = {
        view = { { "n", "q", close_diffview, { desc = "Close Diffview" } } },
        file_panel = { { "n", "q", close_diffview, { desc = "Close Diffview" } } },
      },
      hooks = {
        -- Soft-wrap long lines and collapse unchanged regions to just the
        -- changed hunks (foldmethod=diff, foldlevel=0 counters the global
        -- foldlevel=99 from options.lua). zR expands all inside a diff.
        diff_buf_win_enter = function(bufnr, winid)
          vim.wo[winid].wrap = true
          vim.wo[winid].linebreak = true
          vim.wo[winid].foldenable = true
          vim.wo[winid].foldmethod = "diff"
          vim.wo[winid].foldlevel = 0
          -- markview renders the markdown SOURCE inside these panes (# → ⌘,
          -- - → », per-level heading colors, and hybrid_modes reveals raw text
          -- on the cursor line) — which collides with diffview's diff/conflict
          -- highlighting and makes the panes look wildly inconsistent. Turn it
          -- off for every diff buffer so they show plain text under clean diff
          -- colors. Scheduled so it lands after markview's own attach.
          vim.schedule(function()
            if not vim.api.nvim_buf_is_valid(bufnr) then
              return
            end
            pcall(function()
              require("markview.commands").disable(bufnr)
            end)
            -- Conflict markers break the treesitter parser, which then smears
            -- @markup.heading (and other) highlights inconsistently across the
            -- merged pane (the "random red" — confirmed via :Inspect). The
            -- ConflictDiagnostics autocmd (config/autocmds.lua) handles this on
            -- BufReadPost, but diffview may reuse an already-loaded buffer where
            -- that never fires — so stop the highlighter here too, on any diff
            -- pane that has markers (i.e. the merged/working buffer). The clean
            -- OURS/THEIRS panes have no markers, so they keep their syntax.
            local has_markers = vim.api.nvim_buf_call(bufnr, function()
              return vim.fn.search([[^<<<<<<<]], "nw") ~= 0
            end)
            if has_markers then
              pcall(vim.treesitter.stop, bufnr)
            end
          end)
        end,
      },
    }
    -- Splice the conflict keys into the `view` context, NOT diff1/diff3/diff4.
    -- In this fork the editable MERGED window (where you resolve) only receives
    -- the `view` context — verified: the default `]x`/`[x` (view) bind there but
    -- `dx`/conflict_choose (diff1/diff3/diff4) do NOT. `view` reaches every diff
    -- window in the tabpage; the conflict actions are merge_only, so they're a
    -- harmless no-op in non-merge diff/file-history views. Also seed the layout
    -- contexts so the side panes carry them too (and survive a layout cycle).
    local keys = conflict_keymaps()
    opts.keymaps.view = vim.list_extend(opts.keymaps.view or {}, keys)
    for _, ctx in ipairs({ "diff1", "diff3", "diff4" }) do
      opts.keymaps[ctx] = vim.list_extend(opts.keymaps[ctx] or {}, keys)
    end

    require("diffview").setup(opts)

    -- <leader>gm — open/close diffview. During a merge this IS the conflict
    -- resolver (auto-detects unmerged files → diff3 tool); otherwise a working-
    -- tree diff. Sits in the <leader>g git cluster beside gg/gr/gt (gd/gD/gB are
    -- gitsigns). Mirrors the old <leader>dm "Merge Conflicts" — <leader>d is now
    -- the DAP prefix, so it moved here.
    vim.keymap.set("n", "<leader>gm", function()
      if require("diffview.lib").get_current_view() then
        close_diffview()
      else
        vim.cmd("DiffviewOpen")
      end
    end, { desc = "Diffview: open/close (resolve merge conflicts)" })
  end,
}
