-- codediff.nvim — THE word-level diff surface (VS Code's actual diff engine,
-- C FFI, prebuilt binary auto-downloaded on first use; needs curl only).
-- Opened via neogit (diff_viewer = "codediff" in neogit.lua) or :CodeDiff.
-- Two-tier highlighting: theme DiffAdd/DiffDelete line washes + auto-derived
-- char-level emphasis (1.4x brighter on dark, 0.92x on light) — tracks
-- colorscheme changes with zero config. `t` toggles side-by-side ↔ inline.
--
-- Consolidation note: this is deliberately the ONLY surface with word-level
-- emphasis, and the ONLY diff/merge/history viewer (diffview is retired).
-- Status buffers (neogit + diffs.nvim), terminal git (delta), and magit show
-- calm line-level washes. <leader>gm resolves conflicts (or opens the
-- working-tree explorer when there are none); <leader>gh is file history
-- (visual: line-range history, git log -L); `git mergetool` opens this too
-- (git/.gitconfig).
return {
  "esmuellert/codediff.nvim",
  cmd = "CodeDiff",
  keys = {
    {
      "<leader>gm",
      function()
        -- During a merge: open the conflict view for the current file if it's
        -- conflicted, else the first conflicted file (the old diffview <leader>gm
        -- auto-detect). No conflicts: the working-tree explorer. q closes.
        local conflicted = vim.fn.systemlist({ "git", "diff", "--name-only", "--diff-filter=U" })
        if vim.v.shell_error ~= 0 then
          conflicted = {}
        end
        if #conflicted > 0 then
          local root = vim.fn.systemlist({ "git", "rev-parse", "--show-toplevel" })[1]
          local cur = vim.fn.expand("%:p")
          local target
          for _, f in ipairs(conflicted) do
            if root .. "/" .. f == cur then
              target = cur
              break
            end
          end
          target = target or (root .. "/" .. conflicted[1])
          vim.cmd.edit(vim.fn.fnameescape(target))
          vim.cmd("CodeDiff merge " .. vim.fn.fnameescape(target))
        else
          vim.cmd("CodeDiff")
        end
      end,
      desc = "Codediff: resolve conflicts / working-tree diff",
    },
    -- <leader>gd — straight to the review explorer (replaces gitsigns'
    -- diffthis on this key; that stays reachable via :Gitsigns diffthis).
    { "<leader>gd", "<cmd>CodeDiff<cr>", desc = "Codediff: review explorer (working tree)" },
    { "<leader>gh", "<cmd>CodeDiff history %<cr>", desc = "Codediff: file history" },
    -- Visual mode: `:` seeds the '<,'> range, which :CodeDiff (range=true)
    -- turns into line-range history — git log -L, "who changed these lines".
    { "<leader>gh", ":CodeDiff history %<cr>", mode = "v", desc = "Codediff: history for selection" },
  },
  opts = {
    diff = {
      -- Default to the inline (vertical stacked / unified) layout; `t`
      -- (toggle_layout) still flips to side-by-side per session. Line wrap is
      -- forced on for this layout only — see the inline-wrap glue in config().
      layout = "inline",
      -- ]c/[c at a file boundary hop to the next/prev file's first/last hunk
      -- (explorer/history mode) instead of wrapping within the file — one key
      -- walks the entire changeset. In-file wrap remains the fallback when
      -- there's no adjacent file; cycle_next_file (default true) wraps the
      -- tour at the last file.
      -- cycle_hunks_across_files = true,
      -- conflict_ours_position stays at its DEFAULT ("right": incoming/theirs
      -- left, current/ours right — VS Code's convention). Do NOT flip it:
      -- codediff's conflict actions are bound to pane SLOTS, not git roles,
      -- so "left" silently inverts accept_current/accept_incoming (verified
      -- empirically; upstream bug).
    },
    -- Default the sidebar to the directory tree instead of the flat file
    -- list; `i` (toggle_view_mode) still flips back to list at runtime.
    explorer = {
      view_mode = "tree",
    },
    history = {
      view_mode = "tree",
    },
    keymaps = {
      -- Conflict keys: SPATIAL semantics (deliberate change from the retired
      -- diffview set) — <leader>ch takes the LEFT pane, <leader>cl the RIGHT,
      -- whatever they contain. In codediff's default layout left = incoming
      -- (theirs), right = current (ours) — VS Code's convention — so this is
      -- the opposite ours/theirs assignment from diffview, but h/l stay
      -- honest to the screen. a=both, n=reset-to-base, j/k=next/prev; caps =
      -- whole file. Two semantic deltas from diffview inherent to codediff:
      -- `ca` is ours+theirs WITHOUT base, and `cn` resets TO BASE rather than
      -- deleting the region. Replaces codediff's ct/co/cb/cx and ]x/[x.
      conflict = {
        accept_incoming = "<leader>ch", -- LEFT pane (theirs, in default layout)
        accept_current = "<leader>cl", -- RIGHT pane (ours, in default layout)
        accept_both = "<leader>ca",
        discard = "<leader>cn", -- keep base
        accept_all_incoming = "<leader>cH",
        accept_all_current = "<leader>cL",
        accept_all_both = "<leader>cA",
        discard_all = "<leader>cN",
        next_conflict = "<leader>cj",
        prev_conflict = "<leader>ck",
      },
      view = {
        -- Verdict keys, aligned with the neogit + gitsigns dialects:
        --   s = stage/unstage whole file (neogit's key; shadows vim's
        --       substitute in the editable pane — accepted, `cl` is the
        --       synonym and editing inside a review tab is rare)
        --   - = stage hunk, _ = unstage hunk (gitsigns' in-buffer keys)
        -- Auto-advance to the next unreviewed file is NOT done here — it's
        -- wired at the git layer in config() below, so these stay stock.
        toggle_stage = "s",
        stage_hunk = "-",
        unstage_hunk = "_",
      },
    },
  },
  config = function(_, opts)
    -- tmux `prefix d` popup (see .tmux.conf): the whole nvim is disposable,
    -- so q anywhere quits it — the popup dismisses lazygit-style, like the
    -- NEOGIT_POPUP / GIT_QF_POPUP siblings. codediff's own q (tab-close) is
    -- config-disabled so the global map has no buffer-local competition
    -- (codediff re-binds its keys per file-select, so out-binding it is a
    -- losing race — removing its binding is the reliable path). `qa` without
    -- bang: unsaved buffers still block the quit.
    if vim.env.CODEDIFF_POPUP then
      opts.keymaps = opts.keymaps or {}
      opts.keymaps.view = opts.keymaps.view or {}
      opts.keymaps.view.quit = false
      vim.keymap.set("n", "q", "<cmd>qa<cr>", { desc = "Close codediff popup" })
      -- A = ask-the-diff (scripts/.local/bin/diffask) in a floating terminal.
      -- The popup is bare nvim — no tmux client inside — so the tmux
      -- `prefix A` binding can never fire here; this is its in-popup stand-in.
      -- `A` is free real estate in this nvim: every codediff buffer is
      -- non-modifiable, so append is dead anyway. Popup-gated to keep normal
      -- editing sessions' A intact.
      vim.keymap.set("n", "A", function()
        -- Tell diffask which file is on screen so "this file" questions
        -- resolve. The selected file is EXPLICIT STATE on the explorer
        -- instance (render.lua keeps ex.current_file_path via its
        -- on_file_select wrapper; the plugin reads the same field in
        -- view/keymaps.lua) — buffer names can't answer this (staged views
        -- are all codediff:// virtual buffers). Repo-relative, matching
        -- diffask's cwd. PRIVATE internals (lifecycle/current_file_path),
        -- pcall-guarded per this file's degradation contract: a miss means
        -- no focus context, asks still work. setenv so the :terminal child
        -- inherits it; this nvim is a disposable popup, the env leak is
        -- contained.
        local ok, lifecycle = pcall(require, "codediff.ui.lifecycle")
        local ex = ok and lifecycle.get_explorer(vim.api.nvim_get_current_tabpage()) or nil
        vim.fn.setenv("DIFFASK_FILE", ex and ex.current_file_path or nil)
        -- Plain :terminal, deliberately NOT Snacks.terminal: snacks keys
        -- terminals by command and reattaches, so after a diffask exits you
        -- get the dead "[Process exited]" buffer back instead of a fresh
        -- ask — and a stale DIFFASK_FILE with it. Fresh spawn per press.
        vim.cmd("botright vsplit")
        vim.cmd("vertical resize " .. math.floor(vim.o.columns * 0.35))
        vim.cmd("terminal diffask")
        vim.cmd("startinsert")
      end, { desc = "Ask the diff (diffask)" })
    end

    require("codediff").setup(opts)

    -- Mass-review ergonomics, wired at the GIT LAYER (codediff.core.git) so
    -- every staging path — s (file), - (hunk), explorer toggles — funnels
    -- through, with no keymap races. Two behaviors ride the wrappers:
    --
    -- 1. AUTO-ADVANCE: stock staging re-files the entry into the staged
    --    group and the current-file pointer follows it, so `]f` says "last
    --    file" while unreviewed files sit above (the mass-review clunk).
    --    After any successful stage/apply, advance to the next unreviewed
    --    (unstaged/conflicts) file — but only when the current file has
    --    nothing left to review: a partially-staged file stays put for more
    --    `-` picks, and unstaging (which puts the file BACK under review)
    --    naturally stays too.
    --
    -- 2. NEOGIT SYNC: codediff mutates the index via subprocess; neogit's
    --    status buffer doesn't notice and reports nothing staged. Kick
    --    dispatch_refresh() after every index mutation.
    --
    -- DEGRADATION CONTRACT: everything here rides codediff's PRIVATE
    -- internals (core.git functions, explorer refresh/get_all_files,
    -- on_file_select). A plugin update may rename any of them. Every touch
    -- is pcall-guarded so the failure mode is "staging still works, the
    -- sugar (advance / neogit sync) silently stops" — plus a one-time
    -- warning so the breakage is noticed, not mysterious. Run
    -- `verify-review-stack` after :Lazy update.
    local function glue_broke(what)
      vim.notify(
        "codediff review glue: " .. what .. " — plugin internals changed (update?); staging still works, see plugins/codediff.lua",
        vim.log.levels.WARN
      )
    end

    local ok_git, cd_git = pcall(require, "codediff.core.git")
    if not ok_git then
      glue_broke("core.git module missing; auto-advance + neogit sync disabled")
      cd_git = nil
    end

    local function neogit_refresh()
      local ok, neogit = pcall(require, "neogit")
      if ok and neogit.dispatch_refresh then
        pcall(neogit.dispatch_refresh)
      end
    end

    local function advance_after(ref_path)
      vim.defer_fn(function()
        local ok, lifecycle = pcall(require, "codediff.ui.lifecycle")
        if not ok then
          return
        end
        local ex = lifecycle.get_explorer(vim.api.nvim_get_current_tabpage())
        if not (ex and ex.tree and ex.git_root) then
          return
        end
        -- git is the truth for "is ref fully reviewed" — the explorer tree
        -- refreshes asynchronously and a stale tree made this check lie
        -- ("stay" on a fully-staged file). The tree is only used below to
        -- pick the NEXT target, where staleness merely affects ordering
        -- (ref itself is excluded explicitly).
        local unstaged = vim.fn.systemlist({ "git", "-C", ex.git_root, "diff", "--name-only", "--", ref_path })
        if #unstaged > 0 then
          return -- file still has working-tree changes: stay for more picks
        end
        local ok_adv, err = pcall(function()
          local all = require("codediff.ui.explorer.refresh").get_all_files(ex.tree)
          local idx = 0
          for i, f in ipairs(all) do
            if f.data.path == ref_path then
              idx = i
            end
          end
          local n = #all
          for step = 1, n do
            local f = all[((idx - 1 + step) % n) + 1]
            if (f.data.group == "unstaged" or f.data.group == "conflicts") and f.data.path ~= ref_path then
              if ex.on_file_select then
                ex.on_file_select(f.data)
              end
              return
            end
          end
          vim.notify("Review queue empty — everything staged", vim.log.levels.INFO)
        end)
        if not ok_adv and not vim.g.codediff_glue_warned then
          vim.g.codediff_glue_warned = true
          glue_broke("auto-advance failed (" .. tostring(err):sub(1, 80) .. ")")
        end
      end, 150)
    end

    -- Wrap a git-layer async fn whose last arg is callback(err, ...): run
    -- `after(...call args...)` only on success.
    local function wrap(fn, after)
      return function(...)
        local args = { ... }
        local cb = args[#args]
        local has_cb = type(cb) == "function"
        local wrapped = function(err, ...)
          if has_cb then
            cb(err, ...)
          end
          if not err then
            after(args)
          end
        end
        args[has_cb and #args or #args + 1] = wrapped
        return fn(unpack(args))
      end
    end

    -- Only wrap functions that still exist under their expected names; warn
    -- once about any that vanished (renamed upstream) instead of erroring.
    local missing = {}
    local function wrap_if_present(name, after)
      if cd_git and type(cd_git[name]) == "function" then
        cd_git[name] = wrap(cd_git[name], after)
      else
        table.insert(missing, name)
      end
    end

    wrap_if_present("stage_file", function(args)
      neogit_refresh()
      advance_after(args[2]) -- (git_root, rel_path, cb)
    end)
    wrap_if_present("unstage_file", function()
      neogit_refresh() -- no advance: the file is back under review
    end)
    wrap_if_present("apply_patch", function()
      neogit_refresh()
      -- Hunk staged/unstaged/discarded: advance iff the current file ended
      -- up fully reviewed (advance_after's still-unstaged check handles the
      -- partial case).
      local ok, lifecycle = pcall(require, "codediff.ui.lifecycle")
      if ok then
        local ex = lifecycle.get_explorer(vim.api.nvim_get_current_tabpage())
        if ex and ex.current_file_path then
          advance_after(ex.current_file_path)
        end
      end
    end)

    if #missing > 0 then
      glue_broke("core.git." .. table.concat(missing, "/") .. " not found; their sugar is disabled")
    end

    -- <Tab>/<S-Tab> = next/prev file (diffview muscle memory), as ALIASES of
    -- the stock ]f/[f binds: wrap lifecycle.set_tab_keymap (call-time table
    -- access from view/keymaps.lua, so the shared-module patch survives any
    -- load order) and whenever codediff binds its configured next_file /
    -- prev_file key, bind Tab/S-Tab to the same rhs. Riding the real bind
    -- call means the alias follows codediff's rebind-per-file-select cycle
    -- and its session keymap cleanup for free. Same degradation contract as
    -- the git-layer glue above.
    local ok_lc, lifecycle = pcall(require, "codediff.ui.lifecycle")
    local ok_cfg, cd_config = pcall(require, "codediff.config")
    local view_keys = ok_cfg and ((cd_config.options.keymaps or {}).view or {}) or {}
    if ok_lc and type(lifecycle.set_tab_keymap) == "function" and view_keys.next_file and view_keys.prev_file then
      local aliases = {
        [view_keys.next_file] = "<Tab>",
        [view_keys.prev_file] = "<S-Tab>",
      }
      local stock_set = lifecycle.set_tab_keymap
      lifecycle.set_tab_keymap = function(tabpage, mode, lhs, rhs, kopts)
        local result = stock_set(tabpage, mode, lhs, rhs, kopts)
        if mode == "n" and aliases[lhs] then
          stock_set(tabpage, mode, aliases[lhs], rhs, kopts)
        end
        return result
      end
    else
      glue_broke("<Tab>/<S-Tab> next/prev-file aliases disabled")
    end

    -- <C-d>/<C-u> in the explorer/history panels scroll the DIFF panes
    -- (ports the retired diffview file-panel scroll_view binds).
    -- codediff has no scroll action of its own, so: find the first
    -- non-panel, non-floating window in the tab and scroll it; codediff's
    -- synchronized scrolling carries the sibling pane along.
    local PANEL_FTS = { ["codediff-explorer"] = true, ["codediff-history"] = true, ["codediff-help"] = true }
    local function scroll_diff(key)
      local termcode = vim.api.nvim_replace_termcodes(key, true, false, true)
      return function()
        local cur = vim.api.nvim_get_current_win()
        for _, win in ipairs(vim.api.nvim_tabpage_list_wins(0)) do
          if win ~= cur and vim.api.nvim_win_get_config(win).relative == "" then
            local ft = vim.bo[vim.api.nvim_win_get_buf(win)].filetype
            if not PANEL_FTS[ft] then
              vim.api.nvim_win_call(win, function()
                vim.cmd("normal! " .. termcode)
              end)
              return
            end
          end
        end
      end
    end
    vim.api.nvim_create_autocmd("FileType", {
      pattern = { "codediff-explorer", "codediff-history" },
      group = vim.api.nvim_create_augroup("CodediffPanelScroll", { clear = true }),
      callback = function(args)
        vim.keymap.set("n", "<C-d>", scroll_diff("<C-d>"), { buffer = args.buf, desc = "Scroll the diff down" })
        vim.keymap.set("n", "<C-u>", scroll_diff("<C-u>"), { buffer = args.buf, desc = "Scroll the diff up" })
      end,
    })

    -- INLINE WRAP. codediff hardcodes `wrap = false` on every diff pane and has
    -- no option for it (v2.49.2) — it's re-asserted at each render (view/
    -- render.lua, view/inline_view.lua) AND from a lifecycle/session.lua
    -- autocmd on BufWinEnter/BufEnter/WinEnter/FileType, whose own comment says
    -- it exists to undo "ftplugins/autocmds". A plain wrap=true autocmd loses
    -- that race on every window enter, so we re-assert from inside vim.schedule:
    -- the set lands on the next event-loop tick, after codediff's synchronous
    -- wrap=false, regardless of autocmd definition order.
    --
    -- INLINE ONLY, and that restriction is load-bearing. Side-by-side aligns its
    -- panes with scrollbind + filler lines, which assume one screen row per
    -- buffer line; wrap makes a long line eat extra rows in one pane and desyncs
    -- both. Inline has no original_win and no scrollbind at all (it's a single
    -- unified buffer), so there is nothing to desync. `t` back to side-by-side
    -- re-renders with codediff's stock wrap=false and this no-ops.
    --
    -- Same degradation contract as the git-layer glue: get_layout/get_windows
    -- are lifecycle accessors, not guaranteed API. If they vanish, wrap silently
    -- reverts to stock off (warned once) — nothing else breaks.
    local function inline_wrap()
      local ok, lc = pcall(require, "codediff.ui.lifecycle")
      if not ok or type(lc.get_layout) ~= "function" or type(lc.get_windows) ~= "function" then
        if not vim.g.codediff_wrap_warned then
          vim.g.codediff_wrap_warned = true
          glue_broke("inline wrap disabled (lifecycle accessors missing)")
        end
        return
      end
      -- Cheap synchronous bail: get_layout is a table lookup returning nil for
      -- every non-codediff tab, so the global BufEnter/WinEnter hooks below cost
      -- ~nothing. It tests only "does a session exist"; the layout and the
      -- window are resolved inside the schedule instead, against post-render
      -- state — which is also what makes this a no-op when a toggle lands on
      -- side-by-side.
      local tab = vim.api.nvim_get_current_tabpage()
      if lc.get_layout(tab) == nil then
        return
      end
      vim.schedule(function()
        if lc.get_layout(tab) ~= "inline" then
          return
        end
        local _, modified_win = lc.get_windows(tab)
        if modified_win and vim.api.nvim_win_is_valid(modified_win) then
          vim.wo[modified_win].wrap = true
        end
      end)
    end

    local wrap_group = vim.api.nvim_create_augroup("CodediffInlineWrap", { clear = true })
    -- CodeDiffOpen covers open + file-select; the window events cover
    -- session.lua's re-assert guard.
    vim.api.nvim_create_autocmd("User", {
      pattern = "CodeDiffOpen",
      group = wrap_group,
      callback = inline_wrap,
    })
    vim.api.nvim_create_autocmd({ "BufWinEnter", "BufEnter", "WinEnter", "FileType" }, {
      group = wrap_group,
      callback = inline_wrap,
    })

    -- The autocmds above are not enough on their own: the `t` layout toggle
    -- emits NOTHING — no CodeDiffOpen, and no window events either, since it
    -- reuses the current window (verified: zero autocmds fire on side-by-side
    -- -> inline). So re-assert after every inline render entry point too.
    -- create() is ASYNC (an on_ready callback), so it gets its callback wrapped
    -- rather than its return.
    --
    -- (An OptionSet/wrap autocmd is the tempting catch-all here. It does not
    -- work: OptionSet never fires for `vim.wo[win].opt = v` writes — verified,
    -- zero events — only for `:set`.)
    --
    -- Both patches below target module TABLES, whose fields codediff resolves
    -- with a call-time `require(...)` (view/keymaps.lua:591, view/init.lua:63),
    -- so they land regardless of load order — the same property the <Tab> alias
    -- glue above relies on.
    local wrap_missing = {}
    local function patch_after(mod, mod_name, fn_name)
      if not (mod and type(mod[fn_name]) == "function") then
        table.insert(wrap_missing, mod_name .. "." .. fn_name)
        return
      end
      local stock = mod[fn_name]
      mod[fn_name] = function(...)
        local result = stock(...)
        inline_wrap() -- no-ops unless the session's layout is inline
        return result
      end
    end

    local ok_iv, cd_inline = pcall(require, "codediff.ui.view.inline_view")
    cd_inline = ok_iv and cd_inline or nil
    if cd_inline and type(cd_inline.create) == "function" then
      -- Async: assert once the render actually reports ready, not when create returns.
      local stock_create = cd_inline.create
      cd_inline.create = function(session_config, filetype, on_ready)
        return stock_create(session_config, filetype, function(...)
          local result
          if on_ready then
            result = on_ready(...)
          end
          inline_wrap()
          return result
        end)
      end
    else
      table.insert(wrap_missing, "inline_view.create")
    end
    patch_after(cd_inline, "inline_view", "update")
    patch_after(cd_inline, "inline_view", "rerender")
    patch_after(cd_inline, "inline_view", "show_single_file")

    local ok_view, cd_view = pcall(require, "codediff.ui.view")
    patch_after(ok_view and cd_view or nil, "view", "toggle_layout")

    -- The one that actually decides it. Everything above schedules its
    -- re-assert from BEFORE codediff's own deferred render, which then stamps
    -- wrap=false a tick later (inline_view.lua:55, whose neighbouring comment
    -- confirms "this code can run from a scheduled callback"). That write is
    -- executed synchronously right after inline.render_inline_diff() returns,
    -- so a vim.schedule issued from inside a patched render_inline_diff is the
    -- one hook guaranteed to land after it.
    local ok_inl, cd_inl = pcall(require, "codediff.ui.inline")
    patch_after(ok_inl and cd_inl or nil, "inline", "render_inline_diff")

    if #wrap_missing > 0 then
      glue_broke("inline wrap partially disabled (" .. table.concat(wrap_missing, "/") .. " not found)")
    end
  end,
}
