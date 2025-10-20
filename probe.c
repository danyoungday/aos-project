#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <sched.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/resource.h>
#include <time.h>
#include <unistd.h>

typedef struct {
    uint64_t thp_fault_alloc;
    uint64_t thp_fault_fallback;
    uint64_t thp_collapse_alloc;
    uint64_t thp_split_page;
    uint64_t pgfault;
    uint64_t pgmajfault;
} vmstats_t;

static int read_vmstat(const char *key, uint64_t *out) {
    FILE *f = fopen("/proc/vmstat", "r");
    if (!f) return -1;
    char k[128];
    unsigned long long v;
    int found = 0;
    while (fscanf(f, "%127s %llu", k, &v) == 2) {
        if (strcmp(k, key) == 0) { *out = v; found = 1; break; }
    }
    fclose(f);
    return found ? 0 : -2;
}

static void snapshot_vmstats(vmstats_t *s) {
    memset(s, 0, sizeof(*s));
    read_vmstat("thp_fault_alloc",    &s->thp_fault_alloc);
    read_vmstat("thp_fault_fallback", &s->thp_fault_fallback);
    read_vmstat("thp_collapse_alloc", &s->thp_collapse_alloc);
    read_vmstat("thp_split_page",     &s->thp_split_page);
    read_vmstat("pgfault",            &s->pgfault);
    read_vmstat("pgmajfault",         &s->pgmajfault);
}

static double now_sec(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + ts.tv_nsec / 1e9;
}

static void pin_to_cpu0(void) {
    cpu_set_t set;
    CPU_ZERO(&set);
    CPU_SET(0, &set);
    sched_setaffinity(0, sizeof(set), &set);
}

static void lower_nice(void) {
    setpriority(PRIO_PROCESS, 0, -10);
}

typedef enum { ADV_NONE, ADV_HUGE, ADV_NOHUGE } advise_t;

static void usage(const char *prog) {
    fprintf(stderr,
        "Usage: %s [--size MB] [--passes N] [--stride BYTES] [--advise none|huge|nohuge]\n"
        "Defaults: --size 1024 --passes 1 --stride 4096 --advise none\n", prog);
}

int main(int argc, char **argv) {
    size_t mb = 1024;
    int passes = 1;
    size_t stride = 4096;
    advise_t adv = ADV_NONE;

    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--size") && i+1 < argc) { mb = strtoull(argv[++i], NULL, 10); }
        else if (!strcmp(argv[i], "--passes") && i+1 < argc) { passes = atoi(argv[++i]); }
        else if (!strcmp(argv[i], "--stride") && i+1 < argc) { stride = strtoull(argv[++i], NULL, 10); }
        else if (!strcmp(argv[i], "--advise") && i+1 < argc) {
            const char *a = argv[++i];
            if (!strcmp(a, "huge")) adv = ADV_HUGE;
            else if (!strcmp(a, "nohuge")) adv = ADV_NOHUGE;
            else adv = ADV_NONE;
        } else { usage(argv[0]); return 2; }
    }

    pin_to_cpu0();
    lower_nice();

    size_t total_bytes = mb * 1024ULL * 1024ULL;
    void *buf = mmap(NULL, total_bytes, PROT_READ|PROT_WRITE,
                     MAP_PRIVATE|MAP_ANONYMOUS, -1, 0);
    if (buf == MAP_FAILED) { perror("mmap"); return 1; }

    if (adv == ADV_HUGE) {
#ifdef MADV_HUGEPAGE
        madvise(buf, total_bytes, MADV_HUGEPAGE);
#endif
    } else if (adv == ADV_NOHUGE) {
#ifdef MADV_NOHUGEPAGE
        madvise(buf, total_bytes, MADV_NOHUGEPAGE);
#endif
    }

    volatile char *p = buf;
    for (size_t off = 0; off < total_bytes; off += 4096) p[off] = 0;

    vmstats_t before, after;
    snapshot_vmstats(&before);

    double t0 = now_sec();
    for (int pass = 0; pass < passes; pass++) {
        for (size_t off = 0; off < total_bytes; off += stride) p[off] ^= 1;
        for (ssize_t off = total_bytes - 1; off >= 0; off -= stride)
            p[off & ~(stride - 1)] ^= 1;
    }
    double t1 = now_sec();
    snapshot_vmstats(&after);

    uint64_t d_thp_fault_alloc    = after.thp_fault_alloc    - before.thp_fault_alloc;
    uint64_t d_thp_fault_fallback = after.thp_fault_fallback - before.thp_fault_fallback;
    uint64_t d_thp_collapse_alloc = after.thp_collapse_alloc - before.thp_collapse_alloc;
    uint64_t d_thp_split_page     = after.thp_split_page     - before.thp_split_page;
    uint64_t d_pgfault            = after.pgfault            - before.pgfault;
    uint64_t d_pgmajfault         = after.pgmajfault         - before.pgmajfault;

    double sec = t1 - t0;
    double mb_touched = ((double)passes * (double)total_bytes) / (1024.0 * 1024.0);
    double mbps = (sec > 0.0) ? (mb_touched / sec) : 0.0;

    printf("{\"size_mb\": %zu, \"passes\": %d, \"stride\": %zu, "
           "\"advise\": \"%s\", \"time_sec\": %.6f, \"throughput_MBps\": %.2f, "
           "\"d_thp_fault_alloc\": %" PRIu64 ", \"d_thp_fault_fallback\": %" PRIu64 ", "
           "\"d_thp_collapse_alloc\": %" PRIu64 ", \"d_thp_split_page\": %" PRIu64 ", "
           "\"d_pgfault\": %" PRIu64 ", \"d_pgmajfault\": %" PRIu64 "}\n",
           mb, passes, stride,
           (adv==ADV_HUGE?"huge":(adv==ADV_NOHUGE?"nohuge":"none")),
           sec, mbps,
           d_thp_fault_alloc, d_thp_fault_fallback, d_thp_collapse_alloc,
           d_thp_split_page, d_pgfault, d_pgmajfault);

    munmap(buf, total_bytes);
    return 0;
}