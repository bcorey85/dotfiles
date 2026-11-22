# Sourced by hunk-notes and nvim-jump. Fills the parallel arrays files, lines and notes;
# allow_push=1 also accepts --push (sets push). The caller defines usage().

parse_location_args() {
    files=(); lines=(); notes=()
    local pending_note=
    push=v:false
    while [ $# -gt 0 ]; do
        if [ "${allow_push:-}" = 1 ] && [ "$1" = --push ]; then
            # shellcheck disable=SC2034
            push=v:true; shift; continue
        fi
        if [ "$1" = --note ]; then
            [ $# -ge 2 ] || usage
            pending_note=$2; shift 2; continue
        fi
        if [[ $1 =~ ^[0-9]+(-[0-9]+)?$ && ${#files[@]} -gt 0 ]]; then
            lines[${#lines[@]}-1]=$1
        else
            case "$1" in
                *:[0-9]*) files+=("${1%:*}"); lines+=("${1##*:}") ;;
                *) files+=("$1"); lines+=(1) ;;
            esac
            notes+=("$pending_note"); pending_note=
        fi
        shift
    done
    [ ${#files[@]} -ge 1 ] || usage
    [ -z "$pending_note" ] || notes[${#notes[@]}-1]=$pending_note
}

# Checks each parsed location (exit 2 "bad line", exit 1 "no such directory"), rewrites
# files[] to absolute paths, fills firsts[] and lasts[] with each LINE-END split, and sets
# file and line from the first location.
resolve_location_files() {
    local i first last file_dir
    firsts=(); lasts=()
    for i in "${!files[@]}"; do
        first=${lines[$i]%-*}; last=${lines[$i]#*-}
        [[ $first =~ ^[0-9]+$ && $last =~ ^[0-9]+$ ]] || { echo "bad line: ${lines[$i]}" >&2; exit 2; }
        firsts+=("$first"); lasts+=("$last")
        file_dir=$(cd "$(dirname "${files[$i]}")" 2>/dev/null && pwd -P) || { echo "no such directory: ${files[$i]}" >&2; exit 1; }
        files[i]=$file_dir/$(basename "${files[$i]}")
    done
    file=${files[0]}; line=${lines[0]}
}
