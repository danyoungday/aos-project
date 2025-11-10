#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 /path/to/thp_bench [key=val]..." >&2
  exit 1
fi

BENCH="$1"; shift || true
if [[ ! -x "$BENCH" ]]; then
  echo "Benchmark not found or not executable: $BENCH" >&2
  exit 1
fi

THP_BASE="/sys/kernel/mm/transparent_hugepage"
KHP_BASE="${THP_BASE}/khugepaged"

declare -A PATHS=(
  ["enabled"]="${THP_BASE}/enabled"
  ["defrag"]="${THP_BASE}/defrag"
  ["shmem_enabled"]="${THP_BASE}/shmem_enabled"
  ["khugepaged.pages_to_scan"]="${KHP_BASE}/pages_to_scan"
  ["khugepaged.scan_sleep_millisecs"]="${KHP_BASE}/scan_sleep_millisecs"
  ["khugepaged.alloc_sleep_millisecs"]="${KHP_BASE}/alloc_sleep_millisecs"
  ["khugepaged.max_ptes_none"]="${KHP_BASE}/max_ptes_none"
  ["khugepaged.max_ptes_shared"]="${KHP_BASE}/max_ptes_shared"
  ["khugepaged.max_ptes_swap"]="${KHP_BASE}/max_ptes_swap"
  ["khugepaged.defrag"]="${KHP_BASE}/defrag" # present on some kernels
  ["khugepaged.collapse_pte_mapped_thp"]="${KHP_BASE}/collapse_pte_mapped_thp"
)

write_param() {
  local path="$1" val="$2"
  if [[ -w "$path" ]]; then
    # For files like 'enabled' that list options with [current], we just echo the option we want.
    echo "$val" > "$path"
  fi
}

read_raw() {
  local path="$1"
  if [[ -r "$path" ]]; then
    cat "$path"
  else
    echo ""
  fi
}

# Parse key=val pairs
declare -A CONFIG=()
for kv in "$@"; do
  key="${kv%%=*}"
  val="${kv#*=}"
  CONFIG["$key"]="$val"
done

# Capture originals (only for keys we're changing)
declare -A ORIGINAL=()
for key in "${!CONFIG[@]}"; do
  path="${PATHS[$key]:-}"
  if [[ -n "$path" && -e "$path" ]]; then
    ORIGINAL["$key"]="$(read_raw "$path")"
  fi
done

cleanup() {
  # Restore originals
  for key in "${!ORIGINAL[@]}"; do
    path="${PATHS[$key]:-}"
    if [[ -n "$path" && -w "$path" ]]; then
      # For 'enabled'/'defrag' style files, originals include brackets; best-effort to extract current token
      orig="${ORIGINAL[$key]}"
      # Extract the [current] token if present; else use as-is
      cur="$(sed -E 's/.*\[([^]]+)\].*/\1/;t;d' <<<"$orig" || true)"
      if [[ -n "$cur" ]]; then
        echo "$cur" > "$path" || true
      else
        # strip whitespace
        echo "$orig" | tr -d '\n' > "$path" || true
      fi
    fi
  done
}
trap cleanup EXIT

# Apply new config
for key in "${!CONFIG[@]}"; do
  path="${PATHS[$key]:-}"
  val="${CONFIG[$key]}"
  if [[ -z "${path}" || ! -e "$path" ]]; then
    echo "Warning: skipping unknown or missing key '$key' ($path)" >&2
    continue
  fi
  if [[ ! -w "$path" ]]; then
    echo "Warning: '$path' not writable (need root?)" >&2
    continue
  fi
  write_param "$path" "$val"
done

# Helper to run and capture JSON from benchmark
run_case() {
  local pattern="$1"
  "$BENCH" -S 4096 -t "$(nproc)" -p "$pattern" -m auto -i 2
}

# Run the two contrasting workloads
SEQ_JSON="$(run_case seq)"
RAND_JSON="$(run_case rand)"

# Emit combined JSON
# Normalize config into a JSON object
CONFIG_JSON="{"
first=1
for key in "${!CONFIG[@]}"; do
  val="${CONFIG[$key]}"
  [[ $first -eq 0 ]] && CONFIG_JSON+=","
  CONFIG_JSON+="\"$key\":\"$val\""
  first=0
done
CONFIG_JSON+="}"

# include a snapshot of effective values after applying, useful when kernel normalizes inputs
EFFECTIVE_JSON="{"
first=1
for key in "${!CONFIG[@]}"; do
  path="${PATHS[$key]:-}"
  if [[ -n "$path" && -r "$path" ]]; then
    raw="$(read_raw "$path" | tr -d '\n')"
    # try to extract [current] token
    cur="$(sed -E 's/.*\[([^]]+)\].*/\1/;t;d' <<<"$raw" || true)"
    [[ -z "$cur" ]] && cur="$raw"
    [[ $first -eq 0 ]] && EFFECTIVE_JSON+=","
    EFFECTIVE_JSON+="\"$key\":\"$cur\""
    first=0
  fi
done
EFFECTIVE_JSON+="}"

echo "{"
echo "  \"config\": $CONFIG_JSON,"
echo "  \"effective\": $EFFECTIVE_JSON,"
echo "  \"results\": {"
echo "    \"seq\": $SEQ_JSON,"
echo "    \"rand\": $RAND_JSON"
echo "  }"
echo "}"