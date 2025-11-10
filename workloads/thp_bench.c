// thp_bench.c
#define _GNU_SOURCE
#include <errno.h>
#include <inttypes.h>
#include <math.h>
#include <pthread.h>
#include <sched.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/resource.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>

typedef struct {
    uint8_t *base;
    size_t   len;
    size_t   page_sz;
    size_t   stride;
    int      pattern;   // 0=seq, 1=rand
    int      iters;
    int      cpu;       // -1 for no pin
} worker_arg_t;

static inline uint64_t nsecs_now(void){
    struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec*1000000000ull + (uint64_t)ts.tv_nsec;
}

static int cmp_u64(const void *a, const void *b){
    uint64_t x = *(const uint64_t*)a, y = *(const uint64_t*)b;
    return (x>y)-(x<y);
}

static void* worker(void* argp){
    worker_arg_t *a = (worker_arg_t*)argp;

    if (a->cpu >= 0) {
        cpu_set_t set; CPU_ZERO(&set); CPU_SET(a->cpu, &set);
        sched_setaffinity(0, sizeof(set), &set);
    }

    // Build an index list of page offsets
    size_t n_pages = a->len / a->page_sz;
    uint64_t *idx = (uint64_t*)malloc(n_pages*sizeof(uint64_t));
    for(size_t i=0;i<n_pages;i++) idx[i] = i * (uint64_t)a->page_sz;

    if (a->pattern == 1) { // random
        // Fisher–Yates
        for (size_t i = n_pages-1; i > 0; i--) {
            size_t j = (size_t)(rand() % (i+1));
            uint64_t tmp = idx[i]; idx[i]=idx[j]; idx[j]=tmp;
        }
    } else {
        // seq already
    }

    // Touch memory: one byte per stride, starting at each page
    volatile uint8_t acc = 0;
    for(int it=0; it<a->iters; it++){
        for(size_t p=0; p<n_pages; p++){
            size_t start = (size_t)idx[p];
            for(size_t off = start; off < start + a->page_sz && off < a->len; off += a->stride){
                acc += a->base[off];
                a->base[off] = (uint8_t)(acc + 1);
            }
        }
    }
    // Prevent compiler from optimizing away
    if (acc == 255) fprintf(stderr, "acc=255\n");

    free(idx);
    return NULL;
}

static void usage(const char* prog){
    fprintf(stderr,
      "Usage: %s [-S size_mb] [-t threads] [-p seq|rand] [-m auto|huge|nohuge] [-i iters] [-a pin]\n"
      "Defaults: size=4096MB, threads=1, pattern=seq, madvise=auto, iters=1, pin=0 (pin first N CPUs)\n", prog);
}

int main(int argc, char**argv){
    size_t size_mb = 4096;
    int threads = 1;
    int iters = 1;
    size_t stride = 4096;       // 4K stride to emphasize page walks
    int pattern = 0;            // 0 seq, 1 rand
    enum {MADV_AUTO, MADV_HUGE, MADV_NOHUGE} madv = MADV_AUTO;
    int pin = 1;

    int opt;
    while ((opt=getopt(argc, argv, "S:t:p:m:i:a:h")) != -1){
        switch(opt){
            case 'S': size_mb = (size_t)strtoull(optarg, NULL, 10); break;
            case 't': threads = atoi(optarg); break;
            case 'p': pattern = (!strcmp(optarg,"rand")) ? 1 : 0; break;
            case 'm':
                if (!strcmp(optarg,"huge")) madv = MADV_HUGE;
                else if (!strcmp(optarg,"nohuge")) madv = MADV_NOHUGE;
                else madv = MADV_AUTO;
                break;
            case 'i': iters = atoi(optarg); break;
            case 'a': pin = atoi(optarg); break;
            case 'h': default: usage(argv[0]); return 1;
        }
    }

    size_t bytes = size_mb * 1024ull * 1024ull;
    size_t page_sz = (size_t)sysconf(_SC_PAGESIZE);

    // Allocate anonymously; THP can back this when enabled
    uint8_t *buf = mmap(NULL, bytes, PROT_READ|PROT_WRITE, MAP_PRIVATE|MAP_ANONYMOUS, -1, 0);
    if (buf == MAP_FAILED) { perror("mmap"); return 1; }

    if (madv == MADV_HUGE) {
        if (madvise(buf, bytes, MADV_HUGEPAGE) != 0) perror("madvise(MADV_HUGEPAGE)");
    } else if (madv == MADV_NOHUGE) {
        if (madvise(buf, bytes, MADV_NOHUGEPAGE) != 0) perror("madvise(MADV_NOHUGEPAGE)");
    }

    // Prefault first byte each 2MB to encourage THP collapse later and avoid major faults during timing
    size_t thp = 2*1024*1024;
    for (size_t off=0; off<bytes; off+=thp) buf[off] = 1;

    struct rusage ru0, ru1;
    getrusage(RUSAGE_SELF, &ru0);
    uint64_t t0 = nsecs_now();

    // Launch threads
    pthread_t *ths = (pthread_t*)malloc(threads*sizeof(pthread_t));
    worker_arg_t *args = (worker_arg_t*)calloc(threads, sizeof(worker_arg_t));
    size_t chunk = bytes / (size_t)threads;

    for(int i=0;i<threads;i++){
        args[i].base = buf + (size_t)i * chunk;
        args[i].len = (i == threads-1) ? (bytes - (size_t)i*chunk) : chunk;
        args[i].page_sz = page_sz;
        args[i].stride = stride;
        args[i].pattern = pattern;
        args[i].iters = iters;
        args[i].cpu = pin ? i : -1;
        pthread_create(&ths[i], NULL, worker, &args[i]);
    }
    for(int i=0;i<threads;i++) pthread_join(ths[i], NULL);

    uint64_t t1 = nsecs_now();
    getrusage(RUSAGE_SELF, &ru1);

    double elapsed_s = (t1 - t0) / 1e9;
    double bytes_touched = (double)iters * (double)bytes; // conservative lower-bound for our access pattern
    double bw_gbps = (bytes_touched / elapsed_s) / (1024.0*1024.0*1024.0);

    long minflt = ru1.ru_minflt - ru0.ru_minflt;
    long majflt = ru1.ru_majflt - ru0.ru_majflt;

    // Emit JSON (two contrasting objectives): maximize bandwidth, minimize faults
    printf("{");
    printf("\"size_mb\":%zu,", size_mb);
    printf("\"threads\":%d,", threads);
    printf("\"pattern\":\"%s\",", pattern? "rand":"seq");
    printf("\"madvise\":\"%s\",", madv==MADV_HUGE?"huge":(madv==MADV_NOHUGE?"nohuge":"auto"));
    printf("\"iters\":%d,", iters);
    printf("\"elapsed_seconds\":%.6f,", elapsed_s);
    printf("\"bandwidth_GBps\":%.6f,", bw_gbps);
    printf("\"minor_faults\":%ld,", minflt);
    printf("\"major_faults\":%ld", majflt);
    printf("}\n");

    munmap(buf, bytes);
    free(ths); free(args);
    return 0;
}