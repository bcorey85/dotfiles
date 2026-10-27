#!/usr/bin/env bash
set -euo pipefail
# CB Security Hooks
# Version: 0.1.6
# ==========
# GENERATED — do not edit directly
# PreToolUse hook: bash-safety-gate
if [[ -n "${BASH_TRACE_OUT:-}" ]]; then
    exec {__trace_fd}>>"${BASH_TRACE_OUT}"
    export BASH_XTRACEFD=$__trace_fd
    export PS4='+ ${BASH_SOURCE}:${LINENO}: '
    set -x
fi
trap 'printf '"'"'{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"bash-safety-gate encountered an unexpected error — denying for safety"}}\n'"'"'; exit 0' ERR
[[ -n "${CLAUDE_SKIP_HOOKS:-}" ]] && exit 0
HOOK_LOGGING=1  # set to 1 via: ./unix/install.sh --add-logging
INPUT=$(cat)

block() {
    local reason
    reason=$(printf '%s' "$1" | sed 's/"/\\"/g')
    printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"}}\n' "$reason"
    if [[ "$HOOK_LOGGING" == "1" ]]; then
        local _ts _line _val
        _ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || printf "unknown")
        _val="${CMD:-${RESOLVED:-}}"
        if command -v jq &>/dev/null; then
            _line=$(jq -cn \
                --arg ts "$_ts" \
                --arg hook "bash-safety-gate" \
                --arg reason "$1" \
                --arg value "$_val" \
                '{ts:$ts,hook:$hook,reason:$reason,value:$value}' 2>/dev/null) || true
        else
            local _sv _sr
            _sv=$(printf '%s' "$_val" | head -c 300 | sed 's/\\/\\\\/g; s/"/\\"/g')
            _sr=$(printf '%s' "$1"   | sed 's/\\/\\\\/g; s/"/\\"/g')
            _line=$(printf '{"ts":"%s","hook":"%s","reason":"%s","value":"%s"}' \
                "$_ts" "bash-safety-gate" "$_sr" "$_sv")
        fi
        [[ -n "${_line:-}" ]] && printf '%s\n' "$_line" >> "$HOME/.claude/security-hook-block-log.jsonl" 2>/dev/null || true
    fi
    exit 0
}


# Try jq first, then python3, then sed as last resort
if command -v jq &>/dev/null; then
    CMD=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)
elif command -v python3 &>/dev/null; then
    CMD=$(printf '%s' "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('command',''))" 2>/dev/null)
else
    block "jq and python3 are unavailable — cannot safely parse hook input"
fi

if [ -z "$CMD" ]; then
    block "Could not parse command from hook input — denying for safety"
fi

# Quote mask: two views of $CMD.
# $CMD_UNQUOTED is $CMD with each quoted span blanked to ""; command-shape rules (match_unquoted) match it.
# $CMD_DEQUOTED is $CMD with each span unquoted unless it holds whitespace, | & ; < > ( ) or an escaped double quote (then ""); a $ in a single-quoted span is written \$ (it is literal there); path rules (match_dequoted) match it.
# Both are $CMD whole when it cannot be parsed safely (unclosed quote, heredoc, nested substitution).
# Both are also $CMD whole when the text is not read-only: it holds ( (a $( <( >( substitution, a subshell, a zsh glob qualifier), ${ or $[, a backtick or a write redirect (other than to /dev/null, /dev/stdout, /dev/stderr),
# or a simple command (split on | & ; and newline) does not start with a read-only program (rg, grep, ls, head, cat, uniq with one operand, python/node on a script file ...;
# sed only as sed -n <line range>p with file operands, such as sed -n 1,20p f).
# The list of programs that run text can never be closed, so the views apply only to programs that cannot run it, plus the script runners (python, node, uv run) on a script file.
CMD_UNQUOTED="$CMD"
CMD_DEQUOTED="$CMD"
case "$CMD" in
    *\'*|*\"*|*\\*)
        if CMD_VIEWS=$(printf '%s' "$CMD" | awk 'function runs_script(w, m, start,    j) {
    if (w[start] != "node" && w[start] !~ PYTHON_WORD_RE) return 0
    for (j = start + 1; j <= m; j++) {
        if (substr(w[j], 1, 1) == "-") return 0
        return w[j] ~ SCRIPT_SUFFIX_RE
    }
    return 0
}
function is_operand(t) {
    return t == "-" || substr(t, 1, 1) != "-"
}
# sed is read-only only as: sed -n <line range>p <operands...>.  A backslash-dollar in the script reads as a dollar; an unescaped dollar is a variable.
function is_sed_line_range_print(w, m,    j, script, rest) {
    if (m < 3 || w[2] != "-n") return 0
    script = w[3]
    rest = script
    gsub(/\\[$]/, "", rest)
    if (index(rest, "$") > 0) return 0
    gsub(/\\[$]/, "$", script)
    if (script !~ SED_LINE_RANGE_PRINT_RE) return 0
    for (j = 4; j <= m; j++) if (!is_operand(w[j])) return 0
    return 1
}
function blank_allowed_redirects(line,    out, last) {
    out = ""
    while (match(line, ALLOWED_REDIRECT_RE)) {
        out = out substr(line, 1, RSTART - 1) " "
        last = substr(line, RSTART + RLENGTH - 1, 1)
        if (last == ";" || last == "|" || last == "&") line = substr(line, RSTART + RLENGTH - 1)
        else line = substr(line, RSTART + RLENGTH)
    }
    return out line
}
function command_is_read_only(cmd, blank_cmd,    w, bw, m, name, j, operand_count, options_ended) {
    m = split(cmd, w, " ")
    # A command word that is quoted, or holds a quote, reads differently once every span is blanked.
    if (split(blank_cmd, bw, " ") == 0) return 1
    if (m == 0 || w[1] != bw[1]) return 0
    name = w[1]
    if (name == "uv") return (m >= 3 && w[2] == "run") ? runs_script(w, m, 3) : 0
    if (name == "node" || name ~ PYTHON_WORD_RE) return runs_script(w, m, 1)
    if (name == "rg") {
        for (j = 2; j <= m; j++) if (w[j] ~ RG_RUN_FLAGS_RE) return 0
        return 1
    }
    if (name == "sort") {
        for (j = 2; j <= m; j++) if (w[j] ~ SORT_FLAGS_RE) return 0
        return 1
    }
    if (name == "uniq") {
        operand_count = 0
        options_ended = 0
        for (j = 2; j <= m; j++) {
            if (options_ended || is_operand(w[j])) operand_count++
            else if (w[j] == "--") options_ended = 1
        }
        return operand_count < 2
    }
    if (name == "sed") return is_sed_line_range_print(w, m)
    return index(" " PLAIN " ", " " name " ") > 0
}
function text_is_read_only(text, blank_text,    pos, lines, blank_lines, line_count, k, line, blank_line, markers, marker_count, cmds, blank_cmds, cmd_count, i) {
    marker_count = split(UNSAFE_MARKERS, markers, " ")
    while ((pos = index(text, "\134\n")) > 0) text = substr(text, 1, pos - 1) substr(text, pos + 2)
    while ((pos = index(blank_text, "\134\n")) > 0) blank_text = substr(blank_text, 1, pos - 1) substr(blank_text, pos + 2)
    line_count = split(text, lines, "\n")
    if (split(blank_text, blank_lines, "\n") != line_count) return 0
    for (k = 1; k <= line_count; k++) {
        line = blank_allowed_redirects(lines[k])
        blank_line = blank_allowed_redirects(blank_lines[k])
        for (i = 1; i <= length(WORD_SEPARATORS); i++) {
            gsub(substr(WORD_SEPARATORS, i, 1), " ", line)
            gsub(substr(WORD_SEPARATORS, i, 1), " ", blank_line)
        }
        for (i = 1; i <= marker_count; i++) if (index(line, markers[i]) > 0) return 0
        cmd_count = split(line, cmds, SIMPLE_COMMAND_SPLIT_RE)
        if (split(blank_line, blank_cmds, SIMPLE_COMMAND_SPLIT_RE) != cmd_count) return 0
        for (i = 1; i <= cmd_count; i++) if (!command_is_read_only(cmds[i], blank_cmds[i])) return 0
    }
    return 1
}
BEGIN {
    WORD_SEPARATORS = " \011\015\013\014"
    PLAIN = "grep egrep fgrep ls head tail wc cut tr cat nl column jq"
    UNSAFE_MARKERS = "( ` > ${ $["
    SIMPLE_COMMAND_SPLIT_RE = "[|&;]"
    ALLOWED_REDIRECT_RE = "([0-9&]?>>?[|]?[ \011]*/dev/(null|stdout|stderr)|[0-9]?>&[0-9]+)([ \011;|&]|$)"
    PYTHON_WORD_RE = "^(python(3([.][0-9]+)?)?)$"
    SCRIPT_SUFFIX_RE = "([.](py|js|mjs))$"
    RG_RUN_FLAGS_RE = "^(--pre|--hostname-bin|--search-zip|-[A-Za-z]*z)"
    SORT_FLAGS_RE = "^(--co|--o|-[A-Za-z0-9]*o)"
    SED_LINE_RANGE_PRINT_RE = "^(([0-9]+|[$])(,([0-9]+|[$]))?p)$"
}

function substitution(content) {
    return index(content, "$(") > 0 || index(content, "${") > 0 || index(content, "`") > 0
}
function render(content,    k) {
    if (index(content, BS DQ) > 0) return DQ DQ
    for (k = 1; k <= length(BLANKING); k++) if (index(content, substr(BLANKING, k, 1)) > 0) return DQ DQ
    return content
}
# dequoted: a span without whitespace or an operator is unquoted (the view the read-only check reads and the path rules match); blanked: every span is "".
function emit(text) { dequoted = dequoted text; blanked = blanked text }
function escape_dollars(content,    out, p) {
    out = ""
    while ((p = index(content, "$")) > 0) { out = out substr(content, 1, p - 1) BS "$"; content = substr(content, p + 1) }
    return out content
}
function emit_span(content) { dequoted = dequoted render(content); blanked = blanked DQ DQ }
BEGIN { SQ = "\047"; DQ = "\042"; BS = "\134"; SEP = "\001"; BLANKING = " \011\015\012\013\014|&;<>()"; WORD_START = " \011\015\012\013\014;&|()"; mode = 0; dequoted = ""; blanked = ""; span = ""; first = 1; fail = 0; word_start = 1; bs_end = 0 }
{
    # The output joins the two views with SEP, so a command that holds it is not masked.
    if (index($0, SEP) > 0) { fail = 1; exit 1 }
    # A backslash that ended the previous line joined it to this one: the join can hide a "#" or "<<" from this scan.
    if (bs_end) { fail = 1; exit 1 }
    if (!first) { if (mode == 0) { emit("\n"); word_start = 1 } else span = span "\n" }
    first = 0
    n = length($0)
    # run_start marks the first character not yet appended to dequoted or span: text is appended in runs at a boundary, not per character.
    run_start = 1
    for (i = 1; i <= n; i++) {
        c = substr($0, i, 1)
        if (mode == 0) {
            at_word_start = word_start; word_start = (index(WORD_START, c) > 0)
            if (c == "#" && at_word_start) { emit(substr($0, run_start, i - run_start) substr($0, i)); i = n; run_start = n + 1 }
            else if (c == "<" && substr($0, i + 1, 1) == "<") {
                if (substr($0, i + 2, 1) != "<") { fail = 1; exit 1 }
                emit(substr($0, run_start, i - run_start) "<<<"); i += 2; run_start = i + 1
            }
            else if (c == "`") { fail = 1; exit 1 }
            else if (c == BS) { if (i == n) bs_end = 1; emit(substr($0, run_start, i - run_start) (i == n ? c : substr($0, i + 1, 1))); i++; run_start = i + 1 }
            else if (c == SQ) { emit(substr($0, run_start, i - run_start)); mode = 1; span = ""; run_start = i + 1 }
            else if (c == DQ) { emit(substr($0, run_start, i - run_start)); mode = 2; span = ""; run_start = i + 1 }
            else if (c == "$" && substr($0, i + 1, 1) == SQ) { emit(substr($0, run_start, i - run_start)); mode = 3; span = ""; i++; run_start = i + 1 }
        } else if (mode == 1) {
            if (c == SQ) { span = span substr($0, run_start, i - run_start); if (substitution(span)) { fail = 1; exit 1 } emit_span(escape_dollars(span)); mode = 0; run_start = i + 1 }
        } else {
            if (c == BS) { if (i == n) bs_end = 1; span = span substr($0, run_start, i - run_start) c substr($0, i + 1, 1); i++; run_start = i + 1 }
            else if (mode == 2 && (c == "`" || (c == "$" && (substr($0, i + 1, 1) == "(" || substr($0, i + 1, 1) == "{")))) { fail = 1; exit 1 }
            else if ((mode == 2 && c == DQ) || (mode == 3 && c == SQ)) { span = span substr($0, run_start, i - run_start); if (substitution(span)) { fail = 1; exit 1 } emit_span(span); mode = 0; run_start = i + 1 }
        }
    }
    if (mode == 0) emit(substr($0, run_start))
    else span = span substr($0, run_start)
}
END {
    if (fail || mode != 0) exit 1
    # Output: the blanked view, SEP, the dequoted view; only SEP when the command is not read-only (the caller then uses the raw text for both).
    if (text_is_read_only(dequoted, blanked)) printf "%s%s%s", blanked, SEP, dequoted
    else printf "%s", SEP
}
'); then
            CMD_UNQUOTED=${CMD_VIEWS%%$'\001'*}
            CMD_DEQUOTED=${CMD_VIEWS#*$'\001'}
            [ -n "$CMD_UNQUOTED" ] || CMD_UNQUOTED="$CMD"
            [ -n "$CMD_DEQUOTED" ] || CMD_DEQUOTED="$CMD"
        fi
        ;;
esac
# Fast path: if nothing in the input can match any rule, allow immediately
if ! grep -qiE '(((^|[^[:alnum:]_.-])(bash|sh|dash|zsh|ksh|csh|tcsh|fish)(\.exe)?|\$\{?SHELL\}?)(\s+-[-a-zA-Z]+|\s+[-+]o\s+\w+|\s+--(rcfile|init-file)\s+[^[:space:]]+)*\s+-[a-zA-Z]*[cs][a-zA-Z]*\b)|((^|\|\||&&|;|\s\|\s)\s*eval\s)|((^|\|\||&&|;|\|)\s*(\w+=[^\s$()`]*\s+)*exec\s)|((^|\|\||&&|;)\s*(source\s|\.\s+\S)|\|&?\s*((builtin|nohup|nice(\s+-[^[:space:]]+(\s+[0-9][^[:space:]]*)?)?|timeout(\s+-[^[:space:]]+(\s+[^-[:space:]][^[:space:]]*)?)*\s+[^[:space:]]+|time|command|stdbuf(\s+-[^[:space:]]+)+|setsid(\s+-[^[:space:]]+)*|ionice(\s+-[^[:space:]]+(\s+[0-9][^[:space:]]*)?)*|chrt(\s+-[^[:space:]]+)*\s+[0-9]+|taskset(\s+-[^[:space:]]+)*\s+[^[:space:]]+|sudo(\s+(-u|--user)\s+[^[:space:]]+)+|env(\s+\w+=[^[:space:]]*)*)\s+)*[({]?\s*(source\s|\.\s+\S))|(\b(python3?|node|perl|ruby|php)\b[^;|&]*(\s-(c|e|r)\b|\s--?(eval|command)\b))|((^|[^[:alnum:]_.-])(python[0-9.]*|node|perl|ruby|php)(\.exe)?(\s+-[a-zA-Z0-9_-]+)*(\s+-(\s|$)|\s+(/dev/stdin|/dev/fd/0)\b|\s*<<|\s*<\()|\|&?\s*((nohup|nice(\s+-[^[:space:]]+(\s+[0-9][^[:space:]]*)?)?|timeout(\s+-[^[:space:]]+(\s+[^-[:space:]][^[:space:]]*)?)*\s+[^[:space:]]+|time|command|stdbuf(\s+-[^[:space:]]+)+|setsid(\s+-[^[:space:]]+)*|ionice(\s+-[^[:space:]]+(\s+[0-9][^[:space:]]*)?)*|chrt(\s+-[^[:space:]]+)*\s+[0-9]+|taskset(\s+-[^[:space:]]+)*\s+[^[:space:]]+|sudo(\s+(-u|--user)\s+[^[:space:]]+)+|env(\s+\w+=[^[:space:]]*)*)\s+)*[({=]?\s*([^[:space:]|;&]*/)?(python[0-9.]*|node|perl|ruby|php)(\.exe)?(\s+-[a-zA-Z0-9_-]+)*(\s+-)?\s*([0-9]*[<>]|$|[;&|)]))|(((^|\|\||&&|;|\|)\s*(scp|sftp|ssh)([ \t]|$)|\$\([ \t]*ssh([ \t]|$)|\([ \t]*ssh([ \t]|$)|`[ \t]*ssh([ \t]|$)))|((^|\|\||&&|;|\|)\s*rsync\s([^;|&]*\s)?([^-[:space:];|&/:][^[:space:]/:]*:|-[a-zA-Z]*e(\s|=|$)|--rsh|--del(ete[^[:space:]]*)?(\s|=|$)|--remove-source-files|[^[:space:];|&]*\$))|(ansible-vault\s+(view|decrypt)\b)|((cat|head|tail|less|more|sort|diff|jq|cut|strings|uniq|nl|tac|rev|od|xxd|hexdump|grep|rg|egrep|fgrep|awk|sed)\s+[^;|&]*(\.aws/(credentials|config)|\.kube/config|\.docker/config\.json|\.boto|\.s3cfg|\.netrc|\.git-credentials|\.npmrc|\.pypirc|\.gem/credentials|vault/password|1pass\.txt|github\.txt|\.(pem|key|p12|pfx)\b|\.ssh/(id_(rsa|ed25519|ecdsa|dsa)|authorized_keys|config)|\.gnupg/|\.config/gcloud/|\.azure/(accessTokens|azureProfile|msal_token_cache)|\.config/gh/hosts\.yml|\.env(rc|(\.[a-z]+)*)?\b|(credentials|service[._]account|application_default_credentials)\.json|\.tfstate|\.vault-token|\.dev\.vars|\.htpasswd|token\.json))|((cat|head|tail|less|more|sort|grep|rg|strings|diff)\s+.*\.(bash_history|zsh_history|sh_history|python_history|node_repl_history|mysql_history|psql_history|irb_history|rediscli_history))|(\b(grep|rg|ack|ag)\b.*(\s-[a-zA-Z]*[rRl]|--recursive|--files-with-matches).*(\bAKIA|sk-[a-zA-Z0-9]|PRIVATE KEY|password\s*[=:]|secret.?key\s*[=:]|api.?key\s*[=:]|access.?token\s*[=:]|auth.?token\s*[=:]|BEGIN RSA|BEGIN EC|BEGIN OPENSSH|BEGIN DSA|BEGIN PGP))|(git\s+push\b.*--(force|force-with-lease)\b|git\s+push\s+-f\b)|(git\s+(reset\s+--hard|clean\s+(-f|--force)|checkout\s+--\s+\.|restore\s+(--(staged|worktree)\s+)*\.\s*$))|(git\s+push\b)|(git\s+(commit|push|merge)\b.*--no-verify)|((^|[^-[:alnum:]_])rm\b[^;|&[:space:]]*([[:blank:]]+(\$'"'"'([^'"'"'\\]|\\.)*'"'"'|'"'"'[^'"'"']*'"'"'|"([^"\\]|\\.)*"|\\.|[<>]&|&>|>\||[^;|&[:space:]'"'"'"\\])+)*[[:blank:]]+(-[a-zA-Z]*r[a-zA-Z]*|--r(e(c(u(r(s(i(ve?)?)?)?)?)?)?)?)\b)|(\|&?\s*((nohup|nice(\s+-[^[:space:]]+(\s+[0-9][^[:space:]]*)?)?|timeout(\s+-[^[:space:]]+(\s+[^-[:space:]][^[:space:]]*)?)*\s+[^[:space:]]+|time|command|stdbuf(\s+-[^[:space:]]+)+|setsid(\s+-[^[:space:]]+)*|ionice(\s+-[^[:space:]]+(\s+[0-9][^[:space:]]*)?)*|chrt(\s+-[^[:space:]]+)*\s+[0-9]+|taskset(\s+-[^[:space:]]+)*\s+[^[:space:]]+|sudo(\s+(-u|--user)\s+[^[:space:]]+)+|env(\s+\w+=[^[:space:]]*)*)\s+)*[({=]?\s*([^[:space:]|;&]*/)?(bash|sh|dash|zsh|ksh|csh|tcsh|fish)(\.exe)?($|[^[:alnum:]_.-]))|(curl\b.*(--output\b|-o\b)|wget\b.*(-O\b|--output-document\b))|(curl\b.*(-d\b|--data|--upload-file|-F\b|-T\b|--form))|(wget\b.*--post-(data|file))|((^|[^a-zA-Z0-9_-])(socat|telnet)($|[^a-zA-Z0-9_-]))|((^|[^a-zA-Z0-9_-])(nc|ncat)($|[^a-zA-Z0-9_-]))|(\b(dig|nslookup|host)\b.*\$\()|(curl\b.*(-o\b|--output\b))|(wget\b.*(-O\b|--output-document\b))|(\bsudo\b)|(chmod\s+(777|666|a\+[rwx]|o\+[rwx]|\+s)\b)|(chmod\s+(\+x|[0-7]*[1357])\b)|((^|\|\||&&|;|\s\|\s)\s*\b(DROP\s+(TABLE|DATABASE|SCHEMA)|TRUNCATE\s+TABLE|DELETE\s+FROM\s+\S+\s*(;|$)))|(docker\s+run\b.*--(privileged|net(work)?=host|network\s+host|pid=host|ipc=host|cap-add\s+(ALL|SYS_ADMIN|SYS_PTRACE|NET_ADMIN)\b)|docker\s+run\b.*-v\s+/:/)|((terraform|pulumi|cdktf)\s+destroy)|((pip|pip3)\s+install\s+https?://|npm\s+install\s+https?://|yarn\s+add\s+https?://)|(gh\s+(secret|variable)\s+(set|remove|delete)\b)|(gh\s+repo\s+(delete|rename|transfer)\b)|(gh\s+workflow\s+run\b)|(gh\s+release\s+create\b)|(gh\s+api\b)|((pnpm|npm|yarn|bun)\s+publish\b)|((pnpm|npm|yarn|bun)\s+run\s+(deploy|release|publish|postinstall|prepublish)\b)|((export\s+)?ANTHROPIC_(BASE_URL|AUTH_TOKEN|API_KEY)\s*=)|(^\s*(env|printenv|set)\s*$)|((^|\|\||&&|;|\s\|\s)\s*(env|printenv)\s*\|)|(printenv\s+\S*(ANTHROPIC_|AWS_SECRET|AWS_SESSION|GITHUB_TOKEN|GH_TOKEN|NPM_TOKEN|PYPI_TOKEN|DATABASE_URL|_SECRET|_PASSWORD|_KEY|_TOKEN|_CREDENTIAL))|((cat|head|tail|less|more|strings|xxd|od|tac|hexdump)\s+/proc/(self|\$\$|[0-9]+)/environ)|((crontab\s+(-e|[^-\s])|(^|\|\||&&|;|\s\|\s)\s*at\s+[0-9]|\blaunchctl\s+load\b|\bsystemctl\s+(enable|start)\b))|(\$\([^)]*\b(curl|wget|nc|ncat|socat|telnet|ssh|scp|rsync|fetch)\b)|(`[^`]*\b(curl|wget|nc|ncat|socat|telnet|ssh|scp|rsync|fetch)\b)|(sed\s+(-[a-zA-Z]*i|-i\b))|((tee[[:space:]]+(-{1,2}[a-zA-Z][a-zA-Z0-9-]*(=[^[:space:]]+)?[[:space:]]+)*|>>?[[:space:]]*)(~|\.\.?/|/)?[^[:space:]|;&<>]*(\.zshrc|\.bashrc|\.bash_profile|\.zprofile|\.zshenv|/\.ssh/|/\.aws/|/\.kube/|/\.docker/config|\.gitconfig|\.git-credentials|\.github/workflows|\.claude/settings\.json|/etc/|Library/LaunchAgents|\.git/hooks/))|((python3?|node|perl)\b.*-(c|e)\b.*(write|open|writeFile|writeSync))|(\bsecurity\s+(find-generic-password|find-internet-password|dump-keychain)\b)|(\bsecret-tool\s+lookup\b)|(\bosascript\b)|(aws\s+(s3\s+rm\b.*--recursive|s3\s+rb\b|ec2\s+terminate-instances|rds\s+delete-db-(instance|cluster)|iam\s+delete-|lambda\s+delete-function|cloudformation\s+delete-stack|ecs\s+delete-(cluster|service))\b)|(gcloud\s+(projects\s+delete|compute\s+instances\s+delete|sql\s+instances\s+delete|container\s+clusters\s+delete|functions\s+delete|run\s+services\s+delete|app\s+services\s+delete)\b)|(az\s+(group\s+delete|vm\s+delete|sql\s+server\s+delete|aks\s+delete|storage\s+(account\s+delete|blob\s+delete-batch)|webapp\s+delete|functionapp\s+delete)\b)|(kubectl\s+(delete|drain|replace)\b)|(helm\s+(uninstall|delete|rollback)\b)|(\bdd\b.*\bof=)|(\b(mkfs(\.[a-z0-9]+)?|fdisk|gdisk|parted|diskutil\s+(eraseDisk|partitionDisk|eraseVolume))\b)|(\bxargs\b)|(\bfind\b.*-delete\b)|(\bfind\b.*-(exec|execdir)\b)|(\b[gmn]?awk\b.*\b(system\s*\(|getline))|(\bg?sed\b[^;|&]*([^[:alnum:]/][0-9$,]*[0-9$]e([[:space:]]|$)|/e[^[:alnum:]]|/e$))|(git\s+config\b)|(git\s+config\b)|((bash|sh|zsh|ksh)\s+<<<|\|\s*(bash|sh|zsh|ksh)\s+<<)' <<< "$CMD"$'\n'"$CMD_UNQUOTED"$'\n'"$CMD_DEQUOTED"; then
    exit 0
fi
# Indirect execution — bypasses all keyword-based rules
if grep -qiE '((^|[^[:alnum:]_.-])(bash|sh|dash|zsh|ksh|csh|tcsh|fish)(\.exe)?|\$\{?SHELL\}?)(\s+-[-a-zA-Z]+|\s+[-+]o\s+\w+|\s+--(rcfile|init-file)\s+[^[:space:]]+)*\s+-[a-zA-Z]*[cs][a-zA-Z]*\b' <<< "$CMD_UNQUOTED"; then
    block "[indirect_shell] [threat:7] Indirect shell execution (sh -c) is not allowed — prevents rule bypass"
fi
if grep -qiE '(^|\|\||&&|;|\s\|\s)\s*eval\s' <<< "$CMD"; then
    block "[eval] [threat:7] eval is not allowed — prevents rule bypass via dynamic command construction"
fi
if grep -qiE '(^|\|\||&&|;|\|)\s*(\w+=[^\s$()`]*\s+)*exec\s' <<< "$CMD"; then
    block "[exec_shell] [threat:7] exec replaces the current process and can bypass future hooks"
fi
if grep -qiE '(^|\|\||&&|;)\s*(source\s|\.\s+\S)|\|&?\s*((builtin|nohup|nice(\s+-[^[:space:]]+(\s+[0-9][^[:space:]]*)?)?|timeout(\s+-[^[:space:]]+(\s+[^-[:space:]][^[:space:]]*)?)*\s+[^[:space:]]+|time|command|stdbuf(\s+-[^[:space:]]+)+|setsid(\s+-[^[:space:]]+)*|ionice(\s+-[^[:space:]]+(\s+[0-9][^[:space:]]*)?)*|chrt(\s+-[^[:space:]]+)*\s+[0-9]+|taskset(\s+-[^[:space:]]+)*\s+[^[:space:]]+|sudo(\s+(-u|--user)\s+[^[:space:]]+)+|env(\s+\w+=[^[:space:]]*)*)\s+)*[({]?\s*(source\s|\.\s+\S)' <<< "$CMD_UNQUOTED"; then
    if ! grep -qiE '\.(venv|virtualenv|env)/bin/activate|/virtualenvs/|nvm\.sh|\.cargo/env' <<< "$CMD"; then
        block "[source_dot] [threat:7] source/dot-source is not allowed — prevents rule bypass via external scripts"
    fi
fi
# Interpreter inline execution — runs arbitrary code, bypasses all keyword rules
if grep -qiE '\b(python3?|node|perl|ruby|php)\b[^;|&]*(\s-(c|e|r)\b|\s--?(eval|command)\b)' <<< "$CMD_UNQUOTED"; then
    if ! grep -qiE 'import\s+(json|sys|os\.path|pathlib|re|math|hashlib|base64|urllib|collections|struct|platform|sysconfig|ast|tomllib?|configparser|csv|io|textwrap|shutil|tempfile|glob|fnmatch|copy|pprint|inspect|importlib|pkg_resources|packaging|setuptools|distutils)|JSON\.(parse|stringify)|require\(|console\.(log|error|warn|dir)|process\.(version|arch|platform|cwd)|Buffer\.(from|alloc)' <<< "$CMD"; then
        block "[interpreter_inline] [threat:7] Interpreter inline execution (python -c, node -e, perl -e) is not allowed — prevents rule bypass"
    fi
fi
if grep -qiE '(^|[^[:alnum:]_.-])(python[0-9.]*|node|perl|ruby|php)(\.exe)?(\s+-[a-zA-Z0-9_-]+)*(\s+-(\s|$)|\s+(/dev/stdin|/dev/fd/0)\b|\s*<<|\s*<\()|\|&?\s*((nohup|nice(\s+-[^[:space:]]+(\s+[0-9][^[:space:]]*)?)?|timeout(\s+-[^[:space:]]+(\s+[^-[:space:]][^[:space:]]*)?)*\s+[^[:space:]]+|time|command|stdbuf(\s+-[^[:space:]]+)+|setsid(\s+-[^[:space:]]+)*|ionice(\s+-[^[:space:]]+(\s+[0-9][^[:space:]]*)?)*|chrt(\s+-[^[:space:]]+)*\s+[0-9]+|taskset(\s+-[^[:space:]]+)*\s+[^[:space:]]+|sudo(\s+(-u|--user)\s+[^[:space:]]+)+|env(\s+\w+=[^[:space:]]*)*)\s+)*[({=]?\s*([^[:space:]|;&]*/)?(python[0-9.]*|node|perl|ruby|php)(\.exe)?(\s+-[a-zA-Z0-9_-]+)*(\s+-)?\s*([0-9]*[<>]|$|[;&|)])' <<< "$CMD_UNQUOTED"; then
    block "[interpreter_stdin] [threat:7] Interpreter code from stdin or a heredoc (python3 - <<EOF, echo x | python3) is not allowed — prevents rule bypass"
fi
# SSH connections to remote hosts
if grep -qiE '((^|\|\||&&|;|\|)\s*(scp|sftp|ssh)([ \t]|$)|\$\([ \t]*ssh([ \t]|$)|\([ \t]*ssh([ \t]|$)|`[ \t]*ssh([ \t]|$))' <<< "$CMD"; then
    block "[ssh_scp_rsync] [threat:7] SSH connections (ssh, scp, sftp) to remote hosts are not allowed"
fi
if grep -qiE '(^|\|\||&&|;|\|)\s*rsync\s([^;|&]*\s)?([^-[:space:];|&/:][^[:space:]/:]*:|-[a-zA-Z]*e(\s|=|$)|--rsh|--del(ete[^[:space:]]*)?(\s|=|$)|--remove-source-files|[^[:space:];|&]*\$)' <<< "$CMD"; then
    block "[rsync_remote] [threat:7] rsync to a remote host is not allowed; a local-to-local rsync is fine"
fi
# Ansible vault operations
if grep -qiE 'ansible-vault\s+(view|decrypt)\b' <<< "$CMD"; then
    block "[ansible_vault_view] [threat:5] ansible-vault view/decrypt is not allowed — use ansible-vault edit instead"
fi
# Reading credential/secret files via shell
if grep -qiE '(cat|head|tail|less|more|sort|diff|jq|cut|strings|uniq|nl|tac|rev|od|xxd|hexdump|grep|rg|egrep|fgrep|awk|sed)\s+[^;|&]*(\.aws/(credentials|config)|\.kube/config|\.docker/config\.json|\.boto|\.s3cfg|\.netrc|\.git-credentials|\.npmrc|\.pypirc|\.gem/credentials|vault/password|1pass\.txt|github\.txt|\.(pem|key|p12|pfx)\b|\.ssh/(id_(rsa|ed25519|ecdsa|dsa)|authorized_keys|config)|\.gnupg/|\.config/gcloud/|\.azure/(accessTokens|azureProfile|msal_token_cache)|\.config/gh/hosts\.yml|\.env(rc|(\.[a-z]+)*)?\b|(credentials|service[._]account|application_default_credentials)\.json|\.tfstate|\.vault-token|\.dev\.vars|\.htpasswd|token\.json)' <<< "$CMD_DEQUOTED"; then
    if ! grep -qiE '\.env(rc)?\.(example|sample|template|test|dist)\b' <<< "$CMD"; then
        block "[cat_creds] [threat:5] Reading credential/secret files via shell is not allowed"
    fi
fi
if grep -qiE '(cat|head|tail|less|more|sort|grep|rg|strings|diff)\s+.*\.(bash_history|zsh_history|sh_history|python_history|node_repl_history|mysql_history|psql_history|irb_history|rediscli_history)' <<< "$CMD"; then
    block "[shell_history_read] [threat:7] Reading shell history files is not allowed — may contain credentials (MITRE T1552.003)"
fi
# Credential content sweeping — searching for secret patterns across files
if grep -qiE '\b(grep|rg|ack|ag)\b.*(\s-[a-zA-Z]*[rRl]|--recursive|--files-with-matches).*(\bAKIA|sk-[a-zA-Z0-9]|PRIVATE KEY|password\s*[=:]|secret.?key\s*[=:]|api.?key\s*[=:]|access.?token\s*[=:]|auth.?token\s*[=:]|BEGIN RSA|BEGIN EC|BEGIN OPENSSH|BEGIN DSA|BEGIN PGP)' <<< "$CMD"; then
    if ! grep -qiE '\b(src|frontend|backend|worker|app|lib|tests?|specs?|packages|services|components|node_modules|dist|build)/' <<< "$CMD"; then
        block "[grep_cred_patterns] [threat:7] Searching for credential patterns across files is not allowed — potential credential harvesting"
    fi
fi
# Destructive git operations
if grep -qiE 'git\s+push\b.*--(force|force-with-lease)\b|git\s+push\s+-f\b' <<< "$CMD"; then
    block "[git_force_push] [threat:5] Destructive git push (--force, --force-with-lease, -f) is not allowed"
fi
if grep -qiE 'git\s+(reset\s+--hard|clean\s+(-f|--force)|checkout\s+--\s+\.|restore\s+(--(staged|worktree)\s+)*\.\s*$)' <<< "$CMD"; then
    block "[git_reset_clean] [threat:5] Destructive git commands (reset --hard, clean -f, checkout -- .) are not allowed"
fi
if grep -qiE 'git\s+push\b' <<< "$CMD" && \
   grep -qiE '\b(main|master)\b' <<< "$CMD"; then
    block "[git_push_main] [threat:5] Pushing directly to main/master is not allowed"
fi
if grep -qiE 'git\s+(commit|push|merge)\b.*--no-verify' <<< "$CMD"; then
    block "[git_no_verify] [threat:5] git --no-verify bypasses pre-commit security hooks and is not allowed"
fi
# rm with -r/-R or --recursive on non-safe paths
if grep -qiE '(^|[^-[:alnum:]_])rm\b[^;|&[:space:]]*([[:blank:]]+(\$'"'"'([^'"'"'\\]|\\.)*'"'"'|'"'"'[^'"'"']*'"'"'|"([^"\\]|\\.)*"|\\.|[<>]&|&>|>\||[^;|&[:space:]'"'"'"\\])+)*[[:blank:]]+(-[a-zA-Z]*r[a-zA-Z]*|--r(e(c(u(r(s(i(ve?)?)?)?)?)?)?)?)\b' <<< "$CMD_UNQUOTED"; then
    if ! grep -qiE '(git(\s+-C\s+\S+)?\s+rm\b|node_modules|/dist\b|\bdist/|(^|/|\s)\.cache(/[a-zA-Z0-9_-][^/\s]*)*/?(\s|$)|/tmp/|\bcoverage\b|\.next\b|\.nuxt\b|\.turbo\b|\.pytest_cache|\.mypy_cache|\.ruff_cache|\.tox|\.DS_Store)' <<< "$CMD"; then
        block "[rm_recursive_force] [threat:7] rm -r or --recursive may delete untracked files — not git-recoverable"
    fi
fi
# Generic pipe-to-shell
if grep -qiE '\|&?\s*((nohup|nice(\s+-[^[:space:]]+(\s+[0-9][^[:space:]]*)?)?|timeout(\s+-[^[:space:]]+(\s+[^-[:space:]][^[:space:]]*)?)*\s+[^[:space:]]+|time|command|stdbuf(\s+-[^[:space:]]+)+|setsid(\s+-[^[:space:]]+)*|ionice(\s+-[^[:space:]]+(\s+[0-9][^[:space:]]*)?)*|chrt(\s+-[^[:space:]]+)*\s+[0-9]+|taskset(\s+-[^[:space:]]+)*\s+[^[:space:]]+|sudo(\s+(-u|--user)\s+[^[:space:]]+)+|env(\s+\w+=[^[:space:]]*)*)\s+)*[({=]?\s*([^[:space:]|;&]*/)?(bash|sh|dash|zsh|ksh|csh|tcsh|fish)(\.exe)?($|[^[:alnum:]_.-])' <<< "$CMD_UNQUOTED"; then
    block "[pipe_shell] [threat:7] Pipe-to-shell is not allowed — piping any command into a shell interpreter"
fi
if grep -qiE 'curl\b.*(--output\b|-o\b)|wget\b.*(-O\b|--output-document\b)' <<< "$CMD" && \
   grep -qiE '\b(bash|sh|dash|zsh|ksh)\s+\S' <<< "$CMD"; then
    block "[download_then_execute] [threat:7] Downloading a script then executing it bypasses pipe-to-shell protection — not allowed"
fi
# Network exfiltration — outbound data transfer
if grep -qiE 'curl\b.*(-d\b|--data|--upload-file|-F\b|-T\b|--form)' <<< "$CMD"; then
    if ! grep -qiE 'https?://(localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\])(:[0-9]+)?(/|$|\s)' <<< "$CMD"; then
        block "[curl_upload] [threat:5] curl with data upload flags to external hosts may exfiltrate sensitive data"
    fi
fi
if grep -qiE 'wget\b.*--post-(data|file)' <<< "$CMD"; then
    if ! grep -qiE 'https?://(localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\])(:[0-9]+)?(/|$|\s)' <<< "$CMD"; then
        block "[wget_post] [threat:5] wget with POST flags to external hosts may exfiltrate sensitive data"
    fi
fi
if grep -qiE '(^|[^a-zA-Z0-9_-])(socat|telnet)($|[^a-zA-Z0-9_-])' <<< "$CMD"; then
    block "[raw_network_tools_never] [threat:6] socat/telnet are not allowed"
fi
while IFS= read -r _seg; do
    if grep -qiE '(^|[^a-zA-Z0-9_-])(nc|ncat)($|[^a-zA-Z0-9_-])' <<< "$_seg"; then
        if ! grep -qiE '\bnc(at)?\s+[^|;&]*-\w*z\w*\b' <<< "$_seg"; then
            block "[raw_network_tools_nc] [threat:6] Raw netcat is not allowed — use nc -z for port probes"
        fi
    fi
done < <(printf '%s\n' "$CMD" | tr ';|&' '\n')
if grep -qiE '\b(dig|nslookup|host)\b.*\$\(' <<< "$CMD"; then
    block "[dns_exfiltration] [threat:5] DNS lookup tools (dig, nslookup, host) may be used for data exfiltration"
fi
if grep -qiE 'curl\b.*(-o\b|--output\b)' <<< "$CMD" && \
   grep -qiE '(\.zshrc|\.bashrc|\.bash_profile|\.zprofile|\.zshenv|/\.ssh/|/\.aws/|/\.kube/|/\.docker/config|\.gitconfig|\.git-credentials|\.github/workflows|\.claude/settings\.json|\.claude/scripts/|/etc/|Library/LaunchAgents|\.env\b|\.git/hooks/)' <<< "$CMD"; then
    block "[curl_download_write] [threat:5] curl download to protected paths can overwrite critical config files"
fi
if grep -qiE 'wget\b.*(-O\b|--output-document\b)' <<< "$CMD" && \
   grep -qiE '(\.zshrc|\.bashrc|\.bash_profile|\.zprofile|\.zshenv|/\.ssh/|/\.aws/|/\.kube/|/\.docker/config|\.gitconfig|\.git-credentials|\.github/workflows|\.claude/settings\.json|\.claude/scripts/|/etc/|Library/LaunchAgents|\.env\b|\.git/hooks/)' <<< "$CMD"; then
    block "[wget_download_write] [threat:5] wget download to protected paths can overwrite critical config files"
fi
# Privilege escalation commands
if grep -qiE '\bsudo\b' <<< "$CMD"; then
    block "[sudo] [threat:7] Running commands as root is not allowed"
fi
# Dangerous chmod modes
if grep -qiE 'chmod\s+(777|666|a\+[rwx]|o\+[rwx]|\+s)\b' <<< "$CMD"; then
    block "[chmod_world_writable] [threat:5] Dangerous chmod mode (777, 666, world-writable, setuid) — use a safer mode"
fi
if grep -qiE 'chmod\s+(\+x|[0-7]*[1357])\b' <<< "$CMD" && \
   grep -qiE '(\.zshrc|\.bashrc|\.bash_profile|\.zprofile|\.zshenv|/\.ssh/|/\.aws/|/\.kube/|/\.docker/config|\.gitconfig|\.git-credentials|\.github/workflows|\.claude/settings\.json|/etc/|Library/LaunchAgents|\.git/hooks/)' <<< "$CMD"; then
    block "[chmod_protected_paths] [threat:5] chmod +x on protected/system paths is not allowed"
fi
# Destructive database operations
if grep -qiE '(^|\|\||&&|;|\s\|\s)\s*\b(DROP\s+(TABLE|DATABASE|SCHEMA)|TRUNCATE\s+TABLE|DELETE\s+FROM\s+\S+\s*(;|$))' <<< "$CMD"; then
    block "[db_drop_truncate] [threat:6] Destructive database operations (DROP, TRUNCATE, unfiltered DELETE) are not allowed"
fi
# Dangerous Docker configurations
if grep -qiE 'docker\s+run\b.*--(privileged|net(work)?=host|network\s+host|pid=host|ipc=host|cap-add\s+(ALL|SYS_ADMIN|SYS_PTRACE|NET_ADMIN)\b)|docker\s+run\b.*-v\s+/:/' <<< "$CMD"; then
    block "[docker_privileged] [threat:7] Docker privileged mode, host networking, and root volume mounts are not allowed"
fi
# Infrastructure destroy commands
if grep -qiE '(terraform|pulumi|cdktf)\s+destroy' <<< "$CMD"; then
    block "[infra_destroy] [threat:7] Infrastructure destroy commands are not allowed"
fi
# Package installation from arbitrary URLs
if grep -qiE '(pip|pip3)\s+install\s+https?://|npm\s+install\s+https?://|yarn\s+add\s+https?://' <<< "$CMD"; then
    block "[pkg_install_url] [threat:6] Installing packages from arbitrary URLs is not allowed — use a registry"
fi
# GitHub CLI mutations
if grep -qiE 'gh\s+(secret|variable)\s+(set|remove|delete)\b' <<< "$CMD"; then
    block "[gh_secret_variable] [threat:5] gh secret/variable mutation is not allowed"
fi
if grep -qiE 'gh\s+repo\s+(delete|rename|transfer)\b' <<< "$CMD"; then
    block "[gh_repo_destructive] [threat:6] gh repo destructive operations are not allowed"
fi
if grep -qiE 'gh\s+workflow\s+run\b' <<< "$CMD"; then
    block "[gh_workflow_run] [threat:5] gh workflow run triggers external CI — not git-reversible"
fi
if grep -qiE 'gh\s+release\s+create\b' <<< "$CMD"; then
    block "[gh_release_create] [threat:5] gh release create publishes artifacts — not git-reversible"
fi
if grep -qiE 'gh\s+api\b' <<< "$CMD" && \
   grep -qiE '(-X\s*(POST|PUT|PATCH|DELETE)\b|--method\s+(POST|PUT|PATCH|DELETE)\b|--input\b)' <<< "$CMD"; then
    block "[gh_api_mutate] [threat:6] gh api with mutation methods (POST, PUT, PATCH, DELETE) can bypass specific gh subcommand blocks"
fi
# Package publishing
if grep -qiE '(pnpm|npm|yarn|bun)\s+publish\b' <<< "$CMD"; then
    block "[npm_publish] [threat:5] Package publishing is not git-reversible"
fi
if grep -qiE '(pnpm|npm|yarn|bun)\s+run\s+(deploy|release|publish|postinstall|prepublish)\b' <<< "$CMD"; then
    block "[lifecycle_scripts] [threat:5] Running deploy/release/publish scripts is not git-reversible"
fi
# Environment variable mutation and dumping
if grep -qiE '(export\s+)?ANTHROPIC_(BASE_URL|AUTH_TOKEN|API_KEY)\s*=' <<< "$CMD"; then
    block "[anthropic_env] [threat:7] Mutating ANTHROPIC_* environment variables may redirect API traffic or exfiltrate auth tokens"
fi
if grep -qiE '^\s*(env|printenv|set)\s*$' <<< "$CMD"; then
    block "[env_dump] [threat:7] Dumping environment variables may expose secrets"
fi
if grep -qiE '(^|\|\||&&|;|\s\|\s)\s*(env|printenv)\s*\|' <<< "$CMD"; then
    block "[env_dump_piped] [threat:5] Piped env/printenv commands may expose secrets"
fi
if grep -qiE 'printenv\s+\S*(ANTHROPIC_|AWS_SECRET|AWS_SESSION|GITHUB_TOKEN|GH_TOKEN|NPM_TOKEN|PYPI_TOKEN|DATABASE_URL|_SECRET|_PASSWORD|_KEY|_TOKEN|_CREDENTIAL)' <<< "$CMD"; then
    block "[printenv_sensitive] [threat:6] Reading sensitive environment variables may expose API keys and credentials"
fi
if grep -qiE '(cat|head|tail|less|more|strings|xxd|od|tac|hexdump)\s+/proc/(self|\$\$|[0-9]+)/environ' <<< "$CMD"; then
    block "[proc_environ] [threat:5] Reading /proc/self/environ exposes all environment variables"
fi
# Persistence mechanisms
if grep -qiE '(crontab\s+(-e|[^-\s])|(^|\|\||&&|;|\s\|\s)\s*at\s+[0-9]|\blaunchctl\s+load\b|\bsystemctl\s+(enable|start)\b)' <<< "$CMD"; then
    block "[persistence_mechanisms] [threat:7] Persistence mechanisms (cron, at, launchd, systemctl) are not allowed"
fi
# Network commands inside command substitution — exfiltration via path injection
if grep -qiE '\$\([^)]*\b(curl|wget|nc|ncat|socat|telnet|ssh|scp|rsync|fetch)\b' <<< "$CMD"; then
    block "[cmd_sub_network_dollar] [threat:6] Network commands inside command substitution can exfiltrate data via path arguments"
fi
if grep -qiE '`[^`]*\b(curl|wget|nc|ncat|socat|telnet|ssh|scp|rsync|fetch)\b' <<< "$CMD"; then
    block "[cmd_sub_network_backtick] [threat:6] Network commands inside backtick command substitution can exfiltrate data"
fi
# File-write primitives to protected paths (bypass route when Edit is blocked)
if grep -qiE 'sed\s+(-[a-zA-Z]*i|-i\b)' <<< "$CMD" && \
   grep -qiE '(\.zshrc|\.bashrc|\.bash_profile|\.zprofile|\.zshenv|/\.ssh/|/\.aws/|/\.kube/|/\.docker/config|\.gitconfig|\.git-credentials|\.github/workflows|\.claude/settings\.json|/etc/|Library/LaunchAgents|\.git/hooks/)' <<< "$CMD"; then
    block "[sed_inplace_protected] [threat:5] sed -i on protected paths is not allowed"
fi
if grep -qiE '(tee[[:space:]]+(-{1,2}[a-zA-Z][a-zA-Z0-9-]*(=[^[:space:]]+)?[[:space:]]+)*|>>?[[:space:]]*)(~|\.\.?/|/)?[^[:space:]|;&<>]*(\.zshrc|\.bashrc|\.bash_profile|\.zprofile|\.zshenv|/\.ssh/|/\.aws/|/\.kube/|/\.docker/config|\.gitconfig|\.git-credentials|\.github/workflows|\.claude/settings\.json|/etc/|Library/LaunchAgents|\.git/hooks/)' <<< "$CMD"; then
    block "[tee_redirect_protected] [threat:5] Shell redirection to protected paths is not allowed"
fi
if grep -qiE '(python3?|node|perl)\b.*-(c|e)\b.*(write|open|writeFile|writeSync)' <<< "$CMD" && \
   grep -qiE '(\.zshrc|\.bashrc|\.bash_profile|\.zprofile|\.zshenv|/\.ssh/|/\.aws/|/\.kube/|/\.docker/config|\.gitconfig|\.git-credentials|\.github/workflows|\.claude/settings\.json|/etc/|Library/LaunchAgents|\.git/hooks/)' <<< "$CMD"; then
    block "[scripted_write_protected] [threat:5] Scripted file writes to protected paths are not allowed"
fi
# OS credential manager / keychain access
if grep -qiE '\bsecurity\s+(find-generic-password|find-internet-password|dump-keychain)\b' <<< "$CMD"; then
    block "[macos_keychain] [threat:6] Keychain credential extraction is not allowed — exposes stored passwords and tokens"
fi
if grep -qiE '\bsecret-tool\s+lookup\b' <<< "$CMD"; then
    block "[linux_secret_tool] [threat:6] Secret store credential extraction is not allowed"
fi
# macOS scripting interpreters (MITRE T1059.002)
if grep -qiE '\bosascript\b' <<< "$CMD"; then
    block "[osascript] [threat:7] osascript execution is not allowed — can control any application and execute arbitrary shell commands"
fi
# Cloud CLI destructive mutations (aws, gcloud, az)
if grep -qiE 'aws\s+(s3\s+rm\b.*--recursive|s3\s+rb\b|ec2\s+terminate-instances|rds\s+delete-db-(instance|cluster)|iam\s+delete-|lambda\s+delete-function|cloudformation\s+delete-stack|ecs\s+delete-(cluster|service))\b' <<< "$CMD"; then
    block "[aws_destructive] [threat:6] AWS destructive operations (s3 rm --recursive, ec2 terminate, rds delete, etc.) are not allowed"
fi
if grep -qiE 'gcloud\s+(projects\s+delete|compute\s+instances\s+delete|sql\s+instances\s+delete|container\s+clusters\s+delete|functions\s+delete|run\s+services\s+delete|app\s+services\s+delete)\b' <<< "$CMD"; then
    block "[gcloud_destructive] [threat:6] GCloud destructive operations are not allowed"
fi
if grep -qiE 'az\s+(group\s+delete|vm\s+delete|sql\s+server\s+delete|aks\s+delete|storage\s+(account\s+delete|blob\s+delete-batch)|webapp\s+delete|functionapp\s+delete)\b' <<< "$CMD"; then
    block "[az_destructive] [threat:6] Azure destructive operations are not allowed"
fi
# Kubernetes destructive operations
if grep -qiE 'kubectl\s+(delete|drain|replace)\b' <<< "$CMD"; then
    block "[kubectl_destructive] [threat:5] Kubernetes destructive operations (delete, drain, replace) are not allowed"
fi
if grep -qiE 'helm\s+(uninstall|delete|rollback)\b' <<< "$CMD"; then
    block "[helm_destructive] [threat:5] Helm destructive operations are not allowed"
fi
# Disk/device destructive operations
if grep -qiE '\bdd\b.*\bof=' <<< "$CMD"; then
    block "[dd_write] [threat:7] dd can overwrite disk devices or files — not allowed"
fi
if grep -qiE '\b(mkfs(\.[a-z0-9]+)?|fdisk|gdisk|parted|diskutil\s+(eraseDisk|partitionDisk|eraseVolume))\b' <<< "$CMD"; then
    block "[disk_format] [threat:7] Disk formatting and partitioning commands are not allowed"
fi
# Indirect command execution via pre-approved utilities (xargs, find -exec, awk, sed e-flag)
if grep -qiE '\bxargs\b' <<< "$CMD"; then
    if ! grep -qiE '\bxargs\s+(-[a-zA-Z0-9]+\s+|-I\s*\S+\s+)*(grep|rg|ack|ag|wc|ls|stat|file|head|tail|basename|dirname|echo)\b' <<< "$CMD"; then
        block "[xargs_exec] [threat:6] xargs executes commands from stdin — bypasses keyword-based rules"
    fi
fi
if grep -qiE '\bfind\b.*-delete\b' <<< "$CMD"; then
    if ! grep -qiE '(^|/|\s)\.cache(/[a-zA-Z0-9_-][^/\s]*)*/?(\s|$)|node_modules|/tmp/|\.pytest_cache|\.mypy_cache|\.ruff_cache|\.DS_Store' <<< "$CMD"; then
        block "[find_delete] [threat:6] find -delete removes matched files unconditionally — high blast-radius destructive operation"
    fi
fi
if grep -qiE '\bfind\b.*-(exec|execdir)\b' <<< "$CMD"; then
    if ! grep -qiE '\b(exec|execdir)\s+(/usr/bin/|/bin/)?(wc|grep|rg|ack|ag|cat|head|tail|ls|stat|file|basename|dirname|echo)\s' <<< "$CMD"; then
        block "[find_exec] [threat:6] find -exec/-execdir executes commands on matched files — bypasses keyword-based rules"
    fi
fi
if grep -qiE '\b[gmn]?awk\b.*\b(system\s*\(|getline)' <<< "$CMD"; then
    block "[awk_system] [threat:6] awk system()/getline executes arbitrary commands — bypasses keyword-based rules"
fi
if grep -qiE '\bg?sed\b[^;|&]*([^[:alnum:]/][0-9$,]*[0-9$]e([[:space:]]|$)|/e[^[:alnum:]]|/e$)' <<< "$CMD"; then
    block "[sed_execute] [threat:5] sed e-flag executes the pattern space as a shell command — bypasses keyword-based rules"
fi
# Git config mutations that create persistence or redirect hooks
if grep -qiE 'git\s+config\b' <<< "$CMD" && \
   grep -qiE '\balias\.' <<< "$CMD"; then
    block "[git_config_alias] [threat:6] git aliases with ! prefix execute arbitrary shell commands — persistence vector"
fi
if grep -qiE 'git\s+config\b' <<< "$CMD" && \
   grep -qiE '\bcore\.hookspath\b\s+\S' <<< "$CMD"; then
    block "[git_config_hooks_path] [threat:6] Redirecting git hooks path allows executing arbitrary scripts on git operations"
fi
# Bash here-string and here-doc piped to shell — indirect arbitrary code execution
if grep -qiE '(bash|sh|zsh|ksh)\s+<<<|\|\s*(bash|sh|zsh|ksh)\s+<<' <<< "$CMD"; then
    block "[here_string_shell] [threat:7] Here-strings and here-docs fed to a shell interpreter execute arbitrary code — bypasses keyword-based rules"
fi
