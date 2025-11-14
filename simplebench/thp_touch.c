#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

long get_anon_huge_kb(void) {
    FILE *f = fopen("/proc/self/smaps_rollup", "r");
    if (!f) {
        perror("open smaps_rollup");
        return -1;
    }

    char line[256];
    long kb = -1;

    while (fgets(line, sizeof(line), f)) {
        if (strncmp(line, "AnonHugePages:", 14) == 0) {
            // Line looks like: "AnonHugePages:    524288 kB"
            if (sscanf(line, "AnonHugePages: %ld kB", &kb) == 1) {
                break;
            }
        }
    }

    fclose(f);
    return kb;  // in kB, or -1 on failure
}

int main(int argc, char *argv[]) {

    if (argc != 2) {
        printf("Usage: %s <size_in_MB>\n", argv[0]);
        return 1;
    }

    int size_mb = atoi(argv[1]);
    if (size_mb <= 0) {
        printf("Invalid size.\n");
        return 1;
    }

    long kb_before = get_anon_huge_kb();

    size_t total_bytes = (size_t)size_mb * 1024 * 1024;
    printf("Allocating %d MB (%zu bytes)\n", size_mb, total_bytes);

    void *region = mmap(NULL, total_bytes,
                        PROT_READ | PROT_WRITE,
                        MAP_PRIVATE | MAP_ANONYMOUS,
                        -1, 0);

    if (region == MAP_FAILED) {
        perror("mmap failed");
        return 1;
    }

    printf("Touching pages...\n");

    size_t page_size = 4096;
    char *p = (char *)region;

    for (size_t offset = 0; offset < total_bytes; offset += page_size) {
        p[offset] = 1;               // write one byte per page
    }

    long kb_after = get_anon_huge_kb();
    printf("AnonHugePages before: %ld kB, after: %ld kB, delta: %ld kB\n",
        kb_before, kb_after, kb_after - kb_before);
    printf("Approx THPs used: %ld\n", (kb_after - kb_before) / 2048); // 2 MB = 2048 kB

    
    munmap(region, total_bytes);

    return 0;
}