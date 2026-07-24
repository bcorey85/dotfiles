-- theme-sync — keep nvim in sync with the shared theme state written by the
-- `theme-mode` script (scripts/.local/bin/theme-mode):
--   ~/.cache/theme-mode    "dark" | "light"
--   ~/.cache/theme-family  family name (FAMILIES below)
-- Both files are fs_poll'ed (~1s), so `theme-mode use one` or a prefix T
-- toggle from tmux flips every running instance with no sockets to manage.
-- <leader>ut shells out to the same script, so a toggle from nvim flips tmux
-- and ghostty too — one source of truth, all ways.
--
-- This module also owns every theme-reactive highlight override (markview
-- headings, gitsigns word-diff, per-family fixups), re-applied on ColorScheme,
-- so a family switch always lands with the right set. Plugin specs stay pure
-- plugin declarations. Keep FAMILIES in sync with theme-mode's registry and
-- the ~/.config/tmux/<family>-<mode>.conf files.

local M = {}

local MODE_FILE = vim.env.HOME .. "/.cache/theme-mode"
local FAMILY_FILE = vim.env.HOME .. "/.cache/theme-family"
local DEFAULT_FAMILY = "nightfox"

-- alpha-blend two hex colours (a = share of c1).
local function blend(c1, c2, a)
  local out = {}
  for i = 2, 6, 2 do
    local v = tonumber(c1:sub(i, i + 1), 16) * a + tonumber(c2:sub(i, i + 1), 16) * (1 - a)
    out[#out + 1] = string.format("%02x", math.floor(v + 0.5))
  end
  return "#" .. table.concat(out)
end

local FAMILIES = {
  nightfox = {
    -- EdenEast/nightfox.nvim: the namesake nightfox (cool blue-slate night)
    -- dark / dayfox (warm linen paper) light. The family also ships duskfox,
    -- nordfox, terafox, carbonfox darks and a dawnfox light — swap the schemes
    -- below to re-pin. Each variant registers its own colors_name.
    schemes = { dark = "nightfox", light = "dayfox" },
    accents = {
      dark = { heading1 = "#9d79d6", heading = "#719cd6" }, -- magenta + blue
      light = { heading1 = "#6e33ce", heading = "#2848a9" },
    },
    -- Comment floor: stock #738091 is 3.95:1 dark / #837a72 is 3.78:1 light,
    -- both under 4.5. Unlike solarized/tokyonight-day, body has plenty of room
    -- in BOTH modes (10.06 / 11.15), so lift the comment alone — no Normal
    -- deepening needed. Dark blends 30% toward fg1 (5.37:1); light deepens
    -- 30% toward fg1 (5.20:1). Comments stay
    -- upright: nightfox ships styles.comments = "NONE", so italic would be an
    -- invention, not a preservation.
    -- Diff washes: dayfox (light) ships 0.20/0.40 and is left stock, but the
    -- dark namesake blends at just 0.15 toward the *dim* accents — the faintest
    -- in the family, and DiffText (0.20) barely clears DiffChange (0.15), so
    -- word-diff reads as one flat block. Rebuild the DARK washes at family
    -- strength (dayfox's 0.22/0.40), keeping nightfox's own hues (green/red
    -- add/delete, blue change, cyan text) so only contrast lifts, not character.
    -- Checked: DiffText now leads DiffChange 2.52:1 vs 1.35:1 against bg (was
    -- 1.59 vs 1.31, nearly equal); body fg stays >=3.99:1 on every wash.
    fixup = function(mode)
      local hl = vim.api.nvim_set_hl
      local c = mode == "dark" and blend("#cdcecf", "#738091", 0.3) or blend("#3d2b5a", "#837a72", 0.3)
      hl(0, "Comment", { fg = c })
      if mode == "dark" then
        local bg = "#192330"
        hl(0, "DiffAdd", { bg = blend("#81b29a", bg, 0.22) })
        hl(0, "DiffDelete", { bg = blend("#c94f6d", bg, 0.22) })
        hl(0, "DiffChange", { bg = blend("#719cd6", bg, 0.18) })
        hl(0, "DiffText", { bg = blend("#63cdcf", bg, 0.40), bold = true })
      end
    end,
  },
  duskfox = {
    -- EdenEast/nightfox.nvim, duskfox (a rose-pine-moon derivative: iris-on-
    -- #232136 purple-black night — near-identical to duskbox's dusk) paired with
    -- dawnfox (rosé-dawn light, the same light the terafox family uses). Shares
    -- the already-installed nightfox plugin (plugins/nightfox.lua) — no separate
    -- spec. Each variant registers its own colors_name, matching schemes[mode].
    schemes = { dark = "duskfox", light = "dawnfox" },
    accents = {
      dark = { heading1 = "#c4a7e7", heading = "#65b1cd" }, -- iris + blue
      light = { heading1 = "#907aa9", heading = "#286983" }, -- iris + pine
    },
    -- Comment floor: duskfox #817c9c is ~4.0:1 on #232136, dawnfox #9893a5 is
    -- 2.73:1 on #faf4ed (floor 4.5). Body has room in both (10.5 dark / 6.66
    -- light), so lift the comment alone. Dark blends 20% toward fg (~4.9:1);
    -- light reuses the terafox-light recipe (60% toward fg1, 4.56:1). Upright:
    -- nightfox ships styles.comments = "NONE". Diff* left stock (real bg washes).
    fixup = function(mode)
      local c = mode == "dark" and blend("#e0def4", "#817c9c", 0.2) or blend("#575279", "#9893a5", 0.6)
      vim.api.nvim_set_hl(0, "Comment", { fg = c })
    end,
  },
  nordfox = {
    -- EdenEast/nightfox.nvim, nordfox (the Nord palette — cool blue-grey
    -- #2e3440 night, NOT purple-black). Nord ships no light, so it pairs with
    -- dayfox (warm-linen light, the nightfox namesake's own light — reused here).
    -- Shares the installed nightfox plugin; each variant registers its own
    -- colors_name, matching schemes[mode].
    schemes = { dark = "nordfox", light = "dayfox" },
    accents = {
      dark = { heading1 = "#b48ead", heading = "#8cafd2" }, -- aurora purple + frost
      light = { heading1 = "#6e33ce", heading = "#2848a9" }, -- magenta + blue (dayfox)
    },
    -- Comment floor: nordfox #60728a is only 2.51:1 on #2e3440 — Nord's signature
    -- low-contrast comment, well under the house 4.5 floor. Body #cdcecf has
    -- room (7.97:1), so lift the comment alone, blending 50% toward fg (4.70:1).
    -- Light is dayfox: same #837a72-on-#f6f2ee case the nightfox family solves —
    -- reuse its 30%-toward-fg1 lift (5.20:1). Upright: nightfox ships
    -- styles.comments = "NONE". Diff* left stock (real bg-only washes).
    fixup = function(mode)
      local c = mode == "dark" and blend("#cdcecf", "#60728a", 0.5) or blend("#3d2b5a", "#837a72", 0.3)
      vim.api.nvim_set_hl(0, "Comment", { fg = c })
    end,
  },
  terafox = {
    -- EdenEast/nightfox.nvim, terafox (teal-and-rust autumn-rain dark) paired
    -- with dawnfox (rosé-dawn light, the rose-pine-dawn palette). A second
    -- nightfox-project family alongside nightfox/dayfox; each variant registers
    -- its own colors_name.
    schemes = { dark = "terafox", light = "dawnfox" },
    accents = {
      dark = { heading1 = "#ad5c7c", heading = "#5a93aa" }, -- rose + teal-blue
      light = { heading1 = "#907aa9", heading = "#286983" }, -- iris + pine
    },
    -- Comment floor: terafox #6d7f8b is 3.81:1 on #152528, dawnfox #9893a5 is
    -- 2.73:1 on #faf4ed (floor 4.5). Body has room in both (13.05 dark / 6.66
    -- light), so lift the comment alone — no Normal deepening. Dark blends 25%
    -- toward fg1 (5.46:1); light needs 60% toward fg1 (4.56:1, still clear of
    -- body's 6.66). Comments stay upright: nightfox ships styles.comments =
    -- "NONE", so italic would be an invention, not a preservation.
    -- Diff* are left stock: both palettes build them as real bg-only blends
    -- (generate_spec's spec.diff).
    fixup = function(mode)
      local c = mode == "dark" and blend("#e6eaea", "#6d7f8b", 0.25) or blend("#575279", "#9893a5", 0.6)
      vim.api.nvim_set_hl(0, "Comment", { fg = c })
    end,
  },
  carbonfox = {
    -- EdenEast/nightfox.nvim, carbonfox (IBM Carbon — a near-black neutral
    -- #161616 mono-slate dark, the darkest of the family) paired with dayfox
    -- (warm linen light, the nightfox namesake's own light). Each variant
    -- registers its own colors_name.
    schemes = { dark = "carbonfox", light = "dayfox" },
    accents = {
      dark = { heading1 = "#be95ff", heading = "#8cb6ff" }, -- purple + blue
      light = { heading1 = "#6e33ce", heading = "#2848a9" }, -- magenta + blue (dayfox)
    },
    -- Comment floor: carbonfox #6e6f70 is 3.48:1 on #161616 (floor 4.5) — body
    -- #f2f4f8 has ample room (~17:1), so lift the comment alone, blending 20%
    -- toward fg (5.1:1). Light is dayfox: same #837a72-on-#f6f2ee case the
    -- nightfox family solves — reuse its 30%-toward-fg1 lift (5.20:1). Upright:
    -- nightfox ships styles.comments = "NONE". Diff* left stock (real bg washes).
    fixup = function(mode)
      local c = mode == "dark" and blend("#f2f4f8", "#6e6f70", 0.2) or blend("#3d2b5a", "#837a72", 0.3)
      vim.api.nvim_set_hl(0, "Comment", { fg = c })
    end,
  },
}

local applied ---@type string|nil  last family+mode we set, to skip redundant reloads

-- Read a state file's first line, trimmed; nil if missing.
local function read_state(path)
  local f = io.open(path, "r")
  if not f then
    return nil
  end
  local raw = f:read("l") or ""
  f:close()
  return (raw:gsub("%s+", ""))
end

local function normalize_mode(mode)
  return mode == "light" and "light" or "dark"
end

local function normalize_family(family)
  return FAMILIES[family] and family or DEFAULT_FAMILY
end

function M.read_state()
  return normalize_family(read_state(FAMILY_FILE)), normalize_mode(read_state(MODE_FILE))
end

-- markview heading colours (referenced by markview.lua's headings config).
local function set_headings(a)
  local hl = vim.api.nvim_set_hl
  hl(0, "MdHeading1", { fg = a.heading1, bold = true })
  for i = 2, 6 do
    hl(0, "MdHeading" .. i, { fg = a.heading, bold = true })
  end
  hl(0, "MdBullet", { fg = a.heading })
end

-- gitsigns word-diff readability (the `=` whole-file inline overlay, keymaps.lua).
-- gitsigns' inline word-diff groups (GitSigns{Change,Add,Delete}LnInline)
-- default to `reverse = true`, which paints dim token fgs (comments worst)
-- as unreadable blocks. Replace reverse with the theme's own diff
-- backgrounds + a forced bright Normal fg, so the emphasised word reads on
-- ANY underlying token. Reads the resolved palette at ColorScheme time, so
-- it is theme-agnostic and tracks every family/mode switch.
local function set_word_diff()
  local hl = vim.api.nvim_set_hl
  local function bg_of(name)
    return vim.api.nvim_get_hl(0, { name = name, link = false }).bg
  end
  local fg = vim.api.nvim_get_hl(0, { name = "Normal", link = false }).fg
  -- DiffText (word-emphasis) sits a shade lighter than DiffChange (the
  -- line bg), so the changed word still pops out of its own changed line.
  hl(0, "GitSignsChangeLnInline", { fg = fg, bg = bg_of("DiffText"), bold = true })
  hl(0, "GitSignsAddLnInline", { fg = fg, bg = bg_of("DiffAdd"), bold = true })
  hl(0, "GitSignsDeleteLnInline", { fg = fg, bg = bg_of("DiffDelete"), bold = true })
end

-- Runs on every ColorScheme. A manual :colorscheme (theme audition) won't
-- match the active family's scheme — skip its fixup/accents and apply only
-- the theme-agnostic word-diff glue, so auditions aren't painted over.
-- nvim-orgmode agenda readability (prefix n a / n t popups). The plugin
-- samples its @org.agenda.* colors from whatever the active theme defines,
-- which under minimal, low-colour families lands scheduled-item text
-- near-invisible. Pin them to semantic groups every family paints; the
-- plugin's own versions are `hi default`, so these explicit links win
-- regardless of load order.
local function set_org_agenda()
  local links = {
    ["@org.agenda.scheduled"] = "Normal",
    ["@org.agenda.scheduled_past"] = "WarningMsg",
    ["@org.agenda.deadline.upcoming"] = "WarningMsg",
    ["@org.agenda.deadline"] = "ErrorMsg",
  }
  for group, target in pairs(links) do
    vim.api.nvim_set_hl(0, group, { link = target })
  end
end

local function apply_overrides()
  local family, mode = M.read_state()
  local fam = FAMILIES[family]
  -- colors_name: guard override for a family whose light/dark variants both
  -- register ONE shared colors_name (!= schemes[mode]); set fam.colors_name to
  -- it so this match still fires. All current families register a per-variant
  -- name equal to schemes[mode], so none set it — kept for that future case.
  if vim.g.colors_name == (fam.colors_name or fam.schemes[mode]) then
    if fam.fixup then
      fam.fixup(mode) -- before word-diff: it reads the Diff* bgs set here
    end
    set_headings(fam.accents[mode])
  end
  set_word_diff()
  set_org_agenda()
end

-- Apply family+mode by setting background and re-running :colorscheme. Skips
-- the reload if already active (a reload clears user highlights and re-runs
-- the theme build), unless `force` is set (used for the initial apply).
function M.apply(family, mode, force)
  family, mode = normalize_family(family), normalize_mode(mode)
  local key = family .. "/" .. mode
  if not force and key == applied then
    return
  end
  applied = key
  local fam = FAMILIES[family]
  if fam.pre then
    fam.pre(mode) -- variant globals the theme reads at :colorscheme time
  end
  vim.o.background = mode
  vim.cmd.colorscheme(fam.schemes[mode])
end

function M.apply_from_file(force)
  local family, mode = M.read_state()
  M.apply(family, mode, force)
end

local polls = {} -- libuv fs_poll handles, created lazily in start()

-- Apply the current state now and start watching both state files.
function M.start()
  -- Ensure the state files exist so fs_poll has targets.
  local defaults = { [MODE_FILE] = "dark", [FAMILY_FILE] = DEFAULT_FAMILY }
  for path, value in pairs(defaults) do
    if not vim.uv.fs_stat(path) then
      local f = io.open(path, "w")
      if f then
        f:write(value .. "\n")
        f:close()
      end
    end
  end

  vim.api.nvim_create_autocmd("ColorScheme", {
    group = vim.api.nvim_create_augroup("ThemeOverrides", { clear = true }),
    callback = apply_overrides,
  })

  M.apply_from_file(true)

  if next(polls) then
    return
  end
  for _, path in ipairs({ MODE_FILE, FAMILY_FILE }) do
    local poll = vim.uv.new_fs_poll()
    if poll then
      -- 1s cadence: imperceptible for a manual toggle, negligible overhead.
      poll:start(
        path,
        1000,
        vim.schedule_wrap(function()
          M.apply_from_file(false)
        end)
      )
      polls[#polls + 1] = poll
    end
  end
end

return M
