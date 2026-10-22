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
#   spaces       a value with a space is refused (stderr, exit 1) unless its key is in
#                <free_text_keys>: a space-separated key list, or `*` for every key. A
#                space in any other value means the caller quoted too much and swallowed
#                the next key=value pairs into this one.
#   <hook>       "" or the name of a function called as `<hook> <key> <value>` for every
#                other pair. It folds the pair into `json` itself and returns 0, or
#                returns 1 to leave the pair to the default string fold.
#
# kv_fold exits the calling script on a refusal, as the writers' own loops did.
kv_fold() {
  local free_keys="$1" hook="$2" kv key value hint free free_key
  shift 2
  kv_out=""
  kv_out_seen=""

  for kv in "$@"; do
    case "$kv" in
      out=*) kv_out_seen=1; kv_out="${kv#out=}"; continue ;;
      *=*) ;;
      *) echo "skipping malformed arg (want key=value): $kv" >&2; continue ;;
    esac
    key="${kv%%=*}"
    value="${kv#*=}"

    free=""
    if [ "$free_keys" = "*" ]; then
      free=1
    elif [ -n "$key" ]; then
      case " $free_keys " in
        *" $key "*) free=1 ;;
      esac
    fi
    if [ -z "$free" ] && [ "$value" != "${value#* }" ]; then
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
