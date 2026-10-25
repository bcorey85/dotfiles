#!/usr/bin/env bash
# _kv.sh — key=value argument parsing shared by the metrics writers. Source it; do not run it.
#
# usage: kv_fold <free_text_keys> <hook> [key=value ...]
#
# Folds each key=value into the JSON object in the caller's `json` variable, every
# value a string. The caller sets `json` first (to '{}' or a seeded object) and needs jq.
#
#   out=<path>   never folded. kv_out_seen is 1 when any was given and kv_out holds the
#                last one, so each writer decides what a redirect means.
#   no `=`       a stderr warning, then skipped.
#   one arg, many pairs
#                `key=a b=2 c=3`, where every word after the first is name=value and the
#                key is not free text, is folded as the pairs key=a, b=2 and c=3. zsh does
#                not split an unquoted variable, so `C="a=1 b=2"; writer $C` sends this shape.
#   spaces       any other value with a space is refused (stderr, exit 1) unless its key is
#                in <free_text_keys>: a space-separated key list, or `*` for every key. A
#                space in any other value means the caller quoted too much and swallowed
#                the next key=value pairs into this one.
#   <hook>       "" or the name of a function called as `<hook> <key> <value>` for every
#                other pair. It folds the pair into `json` itself and returns 0, or
#                returns 1 to leave the pair to the default string fold.
#
# kv_fold exits the calling script on a refusal, as the writers' own loops did.
kv_fold() {
  local free_keys="$1" hook="$2" kv key value hint free_key
  shift 2
  kv_out=""
  kv_out_seen=""

  kv_pairs=()
  for kv in "$@"; do
    kv_unfold "$free_keys" "$kv"
  done

  for kv in ${kv_pairs[@]+"${kv_pairs[@]}"}; do
    case "$kv" in
      out=*) kv_out_seen=1; kv_out="${kv#out=}"; continue ;;
      *=*) ;;
      *) echo "skipping malformed arg (want key=value): $kv" >&2; continue ;;
    esac
    key="${kv%%=*}"
    value="${kv#*=}"

    if ! kv_is_free "$free_keys" "$key" && [ "$value" != "${value#* }" ]; then
      echo "refusing to log: $key= contains a space: '$value'" >&2
      hint=""
      for free_key in $free_keys; do
        hint="${hint:+$hint and }$free_key="
      done
      echo "Quote each key=value separately${hint:+; only $hint may contain spaces}." >&2
      exit 1
    fi

    if [ -n "$hook" ] && "$hook" "$key" "$value"; then
      continue
    fi
    json=$(jq -c --arg k "$key" --arg v "$value" '.[$k] = $v' <<< "$json")
  done
}

# kv_is_free <free_text_keys> <key>: true when the key may hold spaces.
kv_is_free() {
  [ "$1" = "*" ] && return 0
  [ -n "$2" ] || return 1
  case " $1 " in
    *" $2 "*) return 0 ;;
  esac
  return 1
}

# kv_unfold <free_text_keys> <arg>: appends the arg to kv_pairs, split into its pairs when
# it is the one-arg, many-pairs shape. Any other arg is appended whole, for kv_fold to judge.
kv_unfold() {
  local free_keys="$1" kv="$2" key value word
  local -a words
  key="${kv%%=*}"
  value="${kv#*=}"

  if [[ $kv != *=* || $value != *" "* || $value == [[:space:]]* || $value == *[$'\n\r\t']* ]] \
    || kv_is_free "$free_keys" "$key"; then
    kv_pairs+=("$kv")
    return
  fi

  read -r -a words <<< "$value"
  if [ "${#words[@]}" -lt 2 ]; then
    kv_pairs+=("$kv")
    return
  fi
  for word in "${words[@]:1}"; do
    if ! [[ $word =~ ^[A-Za-z_][A-Za-z0-9_]*= ]]; then
      kv_pairs+=("$kv")
      return
    fi
  done
  kv_pairs+=("$key=${words[0]}" "${words[@]:1}")
}
