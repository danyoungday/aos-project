# gcc -Wall -o workloads/randwrite workloads/randwrite.c

ON=$1
SCAN_SLEEP=$2
PAGES_TO_SCAN=$3

# Apply thp tunables
echo "$ON" | sudo tee /sys/kernel/mm/transparent_hugepage/enabled > /dev/null
echo "$SCAN_SLEEP" | sudo tee /sys/kernel/mm/transparent_hugepage/khugepaged/scan_sleep_millisecs > /dev/null
echo "$PAGES_TO_SCAN" | sudo tee /sys/kernel/mm/transparent_hugepage/khugepaged/pages_to_scan > /dev/null

# Reset caches between runs to avoid contamination
sudo sync
echo 3 | sudo tee /proc/sys/vm/drop_caches > /dev/null
echo 1 | sudo tee /proc/sys/vm/compact_memory > /dev/null
sleep 1  # let background daemons settle

# Run benchmark
# /usr/bin/time -f "{\"time\": %e, \"res\": %M, \"maj\": %F, \"min\": %R}" -a taskset -c 0 ./workloads/randwrite 1024 1 r
/usr/bin/time -f "{\"time\": %e, \"res\": %M, \"maj\": %F, \"min\": %R}" -a taskset -c 0 sysbench memory --memory-block-size=64M --memory-total-size=4096GB --memory-access-mode=rnd run