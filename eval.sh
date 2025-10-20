#!/bin/bash
# Quick-and-dirty THP benchmark runner
# Usage: ./run_thp_trial.sh <scan_sleep_ms> <pages_to_scan> <defrag_mode> <result_file>

SCAN_SLEEP=${1:-1000}
PAGES_TO_SCAN=${2:-4096}
RESULTS=${3:-results.jsonl}

# 1️⃣ Apply the tunables (requires sudo privileges)
echo "$SCAN_SLEEP" | sudo tee /sys/kernel/mm/transparent_hugepage/khugepaged/scan_sleep_millisecs >/dev/null
echo "$PAGES_TO_SCAN" | sudo tee /sys/kernel/mm/transparent_hugepage/khugepaged/pages_to_scan >/dev/null

# 2️⃣ Reset caches between runs to avoid contamination
sudo sync
echo 3 | sudo tee /proc/sys/vm/drop_caches >/dev/null
echo 1 | sudo tee /proc/sys/vm/compact_memory >/dev/null
sleep 1  # let background daemons settle

# 3️⃣ Run the benchmark
# Adjust args as needed for your use case
OUT=$(./probe --size 1024 --passes 2 --stride 4096 --advise none)

# Get number of THPs
AHK=$(awk '/^AnonHugePages:/ {print $2}' /proc/meminfo)
SHK=$(awk '/^ShmemHugePages:/ {print $2}' /proc/meminfo)  # may be empty
SHK=${SHK:-0}
THP_COUNT=$(( (AHK + SHK) / 2048 ))

# 4️⃣ Write results with knob metadata and timestamp
TS=$(date +"%Y-%m-%dT%H:%M:%S")
echo "{\"timestamp\": \"$TS\", \"scan_sleep\": $SCAN_SLEEP, \"pages_to_scan\": $PAGES_TO_SCAN, \"thp_count\": $THP_COUNT, \"result\": $OUT}" > "$RESULTS"