-- Word-match SQL coloring for Cube `sql:` values.
--
-- Why not the sql treesitter grammar: a Cube `sql:` value is an expression
-- fragment with `{CUBE}` / `{member}` placeholders and `{{ }}` tags, not a
-- statement, so the grammar error-recovers and silently drops keywords
-- (`NOT ({CUBE}.x IS NOT NULL AND )` loses the leading NOT; COALESCE, CASE, SELECT
-- and DATE vanish in other values). Keywords then color inconsistently. A plain
-- word match colors the same word the same way everywhere, which matters more
-- here than parser-aware accuracy. after/queries/yaml/injections.scm therefore
-- never injects sql.
--
-- The yaml tree is used only to find the `sql:` value ranges; the words inside
-- are matched by hand. `{{ }}` / `{% %}` spans are skipped so the jinja injection
-- keeps coloring them (the SQL text inside a tag's string arguments is Python, not
-- this query's SQL). Extmarks sit above treesitter's default priority (100) so the
-- yaml string color underneath does not win.

local M = {}

local ns = vim.api.nvim_create_namespace("cube_sql")
local PRIORITY = 200
local DEBOUNCE_MS = 150

-- Placeholders get their own group; ColorScheme re-applies the link after a theme reset.
local function link_ref_group()
  vim.api.nvim_set_hl(0, "CubeSqlRef", { link = "@constant", default = true })
end
link_ref_group()
vim.api.nvim_create_autocmd("ColorScheme", { callback = link_ref_group })

local function word_set(group, words)
  local set = {}
  for word in words:gmatch("%S+") do
    set[word] = group
  end
  return set
end

local KEYWORDS = word_set(
  "@keyword",
  [[
  select from where and or not is null in case when then else end as on join left right inner outer full cross
  with between like ilike similar exists distinct date timestamp timestamptz interval true false cast over
  partition by order group having union intersect except all any some limit offset asc desc nulls first last
  filter within using lateral unbounded preceding following current row rows range escape collate at time zone
  ]]
)

local BUILTINS = word_set(
  "@function.builtin",
  [[
  coalesce nullif sum count min max avg greatest least date_trunc date_part extract round ceil ceiling floor abs
  length lower upper trim ltrim rtrim substr substring concat replace split_part position array_agg string_agg
  bool_or bool_and every json_agg jsonb_agg to_char to_date to_timestamp now current_date current_timestamp
  age row_number rank dense_rank lag lead first_value last_value ntile percentile_cont percentile_disc
  generate_series unnest jsonb_extract_path_text
  ]]
)

local function classify(word)
  local lowered = word:lower()
  return KEYWORDS[lowered] or BUILTINS[lowered]
end

-- Parsed on first use, not at require time: this module loads before lazy.nvim
-- puts the treesitter parsers on the runtimepath, so an eager parse would throw.
local value_query
local function get_value_query()
  if not value_query then
    value_query = vim.treesitter.query.parse(
      "yaml",
      [[
      (block_mapping_pair
        key: (flow_node) @key
        (#eq? @key "sql")
        value: [
          (block_node (block_scalar) @value)
          (flow_node [(plain_scalar) (double_quote_scalar) (single_quote_scalar)] @value)
        ])
      ]]
    )
  end
  return value_query
end

-- Color one `sql:` value. `text` is the value, `start_row` / `start_col` is where
-- its first byte sits in the buffer.
local function color_value(buf, text, start_row, start_col)
  -- Byte offset -> buffer position. Only the first line carries the column offset.
  local line_starts = { 1 }
  for newline in text:gmatch("()\n") do
    line_starts[#line_starts + 1] = newline + 1
  end
  local function position(offset)
    local line = #line_starts
    while line_starts[line] > offset do
      line = line - 1
    end
    local col = offset - line_starts[line]
    if line == 1 then
      col = col + start_col
    end
    return start_row + line - 1, col
  end

  local function mark(first, last, group, priority)
    local row, col = position(first)
    local end_row, end_col = position(last + 1)
    vim.api.nvim_buf_set_extmark(buf, ns, row, col, {
      end_row = end_row,
      end_col = end_col,
      hl_group = group,
      priority = priority or PRIORITY,
    })
  end

  -- End of a `{{ }}` / `{% %}` / `{# #}` span starting at `i`, or nil.
  local function tag_end(i)
    local closers = { ["{{"] = "}}", ["{%"] = "%}", ["{#"] = "#}" }
    local closer = closers[text:sub(i, i + 1)]
    if not closer then
      return nil
    end
    local _, close = text:find(closer, i + 2, true)
    return close or #text
  end

  -- Color every `{ident}` placeholder in text[first..last]. `{{` never matches.
  local function mark_refs(first, last)
    local from = first
    while true do
      local ref_first, ref_last = text:find("{[%w_.]+}", from)
      if not ref_first or ref_last > last then
        return
      end
      mark(ref_first, ref_last, "CubeSqlRef")
      from = ref_last + 1
    end
  end

  -- SQL text outside tags is plain, not the yaml string colour; tags keep jinja's.
  local plain_start = 1
  local k = 1
  while k <= #text do
    local tag_close = tag_end(k)
    if tag_close then
      if k > plain_start then
        mark(plain_start, k - 1, "@variable", PRIORITY - 1)
      end
      plain_start = tag_close + 1
      k = tag_close + 1
    else
      k = k + 1
    end
  end
  if plain_start <= #text then
    mark(plain_start, #text, "@variable", PRIORITY - 1)
  end

  local i = 1
  while i <= #text do
    local char = text:sub(i, i)
    local tag_close = tag_end(i)
    if tag_close then
      mark_refs(i + 2, tag_close)
      i = tag_close + 1
    elseif char == "{" and text:find("^{[%w_.]+}", i) then
      -- `{CUBE}` / `{member}` placeholders: their words are names, not SQL.
      local _, ref_last = text:find("^{[%w_.]+}", i)
      mark(i, ref_last, "CubeSqlRef")
      i = ref_last + 1
    elseif char == "'" then
      -- SQL string literal ('' escapes a quote). A tag inside it is left to jinja.
      local segment_start = i
      local j = i + 1
      while j <= #text do
        local inner_tag_close = tag_end(j)
        if inner_tag_close then
          if j > segment_start then
            mark(segment_start, j - 1, "@string")
            mark_refs(segment_start, j - 1)
          end
          mark_refs(j + 2, inner_tag_close)
          j = inner_tag_close + 1
          segment_start = j
        elseif text:sub(j, j) == "'" then
          if text:sub(j + 1, j + 1) == "'" then
            j = j + 2
          else
            break
          end
        else
          j = j + 1
        end
      end
      local last = math.min(j, #text)
      if last >= segment_start then
        mark(segment_start, last, "@string")
        mark_refs(segment_start, last)
      end
      i = j + 1
    elseif char:match("[%a_]") then
      local first, last = text:find("^[%a_][%w_]*", i)
      -- A word after a dot is a column or schema name (`{CUBE}.date`), never SQL.
      if text:sub(first - 1, first - 1) ~= "." then
        local group = classify(text:sub(first, last))
        if group then
          mark(first, last, group)
        end
      end
      i = last + 1
    elseif char:match("%d") then
      local first, last = text:find("^%d+%.?%d*", i)
      if text:sub(first - 1, first - 1) ~= "." then
        mark(first, last, "@number")
      end
      i = last + 1
    else
      i = i + 1
    end
  end
end

local function eligible(buf)
  local name = vim.api.nvim_buf_get_name(buf)
  return name:match("%.ya?ml$") ~= nil
    and (name:find("/model/cubes/", 1, true) or name:find("/model/views/", 1, true)) ~= nil
end

function M.refresh(buf)
  if not vim.api.nvim_buf_is_valid(buf) then
    return
  end
  vim.api.nvim_buf_clear_namespace(buf, ns, 0, -1)
  if not eligible(buf) then
    return
  end
  -- The parser is missing until :TSInstall has built it; a miss retries on the next event.
  local ok, parser = pcall(vim.treesitter.get_parser, buf, "yaml")
  if not ok or not parser then
    return
  end
  -- parse(false): the yaml tree alone. Injections are not needed to find `sql:` values.
  local tree = parser:parse(false)[1]
  if not tree then
    return
  end
  local query_ok, query = pcall(get_value_query)
  if not query_ok then
    return
  end
  for id, node in query:iter_captures(tree:root(), buf) do
    if query.captures[id] == "value" then
      local start_row, start_col, end_row, end_col = node:range()
      local node_type = node:type()
      -- Quoted scalars: leave the surrounding quote characters out of the scan, or
      -- a single-quoted yaml value would read as one SQL string.
      if node_type == "double_quote_scalar" or node_type == "single_quote_scalar" then
        start_col = start_col + 1
        end_col = end_col - 1
      end
      -- A block scalar at end of file ends one row past the last line.
      local line_count = vim.api.nvim_buf_line_count(buf)
      if end_row >= line_count then
        end_row = line_count - 1
        end_col = #vim.api.nvim_buf_get_lines(buf, end_row, end_row + 1, false)[1]
      end
      local lines = vim.api.nvim_buf_get_text(buf, start_row, start_col, end_row, end_col, {})
      color_value(buf, table.concat(lines, "\n"), start_row, start_col)
    end
  end
end

local timers = {}

local function refresh_debounced(buf)
  local timer = timers[buf]
  if not timer then
    timer = vim.uv.new_timer()
    timers[buf] = timer
  end
  timer:stop()
  timer:start(
    DEBOUNCE_MS,
    0,
    vim.schedule_wrap(function()
      M.refresh(buf)
    end)
  )
end

function M.setup()
  local group = vim.api.nvim_create_augroup("CubeSql", { clear = true })
  vim.api.nvim_create_autocmd({ "BufReadPost", "BufEnter", "FileType" }, {
    group = group,
    pattern = { "*/model/cubes/*", "*/model/views/*" },
    callback = function(args)
      -- Scheduled so the buffer's filetype and treesitter attach have settled.
      vim.schedule(function()
        M.refresh(args.buf)
      end)
    end,
  })
  vim.api.nvim_create_autocmd({ "TextChanged", "TextChangedI" }, {
    group = group,
    pattern = { "*/model/cubes/*", "*/model/views/*" },
    callback = function(args)
      refresh_debounced(args.buf)
    end,
  })
  vim.api.nvim_create_autocmd("BufWipeout", {
    group = group,
    callback = function(args)
      local timer = timers[args.buf]
      if timer then
        timer:stop()
        timer:close()
        timers[args.buf] = nil
      end
    end,
  })
end

M.setup()

return M
