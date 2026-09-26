/* Independent oracle for the FP-saturation kernels (NOT derived from the simulator).
 * Computes the exact float32 trajectories with IEEE RNE ops (x86-64 SSE, FLT_EVAL_METHOD=0;
 * fmaf -> hardware vfmadd, correctly rounded) and emits post.bin in the rtlmeter DPI
 * record format: (addr u64 LE, size u64 LE, bytes).
 * usage: oracle fma|div LOOPS post.bin
 */
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <math.h>

int main(int argc, char** argv) {
    if (argc != 4) { fprintf(stderr, "usage: oracle fma|div LOOPS out\n"); return 2; }
    int loops = atoi(argv[2]);
    uint8_t buf[1024];
    uint64_t size;
    if (!strcmp(argv[1], "fma")) {
        size = 512;
        const float r = 3.9f;  /* 0x4079999A */
        for (int g = 0; g < 16; ++g)
        for (int c = 0; c < 8; ++c) {
            float x = (float)(g*8 + c + 1) * 0x1p-8f;
            for (int i = 0; i < 4*loops; ++i) {
                float t = fmaf(-x, x, x);
                x = r * t;
                if (!(x > 0.0f && x < 1.0f) || !isnormal(x)) {
                    fprintf(stderr, "DEGENERATE g=%d c=%d i=%d x=%a\n", g, c, i, x);
                    return 1;
                }
            }
            memcpy(buf + g*32 + c*4, &x, 4);
        }
    } else {
        /* div variant: post.bin gates only the integer marker region (0x48000,128B);
         * the IEEE-RNE FP reference (1024B @0x40000) goes to <out>.fpref for an
         * offline ulp-bounded comparison (fpnew divsqrt is faithful, not RNE-exact). */
        size = 1024;
        const float A = 1.00048828125f;  /* 0x3F801000 */
        for (int g = 0; g < 16; ++g)
        for (int c = 0; c < 8; ++c) {
            float x = (float)(g*8 + c + 1) * 0x1p-8f;
            float y = 0.0f;
            for (int i = 0; i < 2*loops; ++i) {
                x = x / A;
                y = sqrtf(x);
                if (!isnormal(x) || !isnormal(y)) {
                    fprintf(stderr, "DEGENERATE g=%d c=%d i=%d x=%a y=%a\n", g, c, i, x, y);
                    return 1;
                }
            }
            memcpy(buf + g*64 + c*4, &x, 4);
            memcpy(buf + g*64 + 32 + c*4, &y, 4);
        }
        char refname[512];
        snprintf(refname, sizeof refname, "%s.fpref", argv[3]);
        FILE* rf = fopen(refname, "wb");
        if (!rf) { perror("open fpref"); return 1; }
        fwrite(buf, 1, size, rf);
        fclose(rf);
        /* build the gated marker region */
        uint32_t sum = (uint32_t)loops * (uint32_t)(loops + 1) / 2u;
        uint8_t mk[128];
        for (uint32_t g = 0; g < 16; ++g) {
            memcpy(mk + g*8, &sum, 4);
            uint32_t gp1 = g + 1;
            memcpy(mk + g*8 + 4, &gp1, 4);
        }
        FILE* f = fopen(argv[3], "wb");
        if (!f) { perror("open"); return 1; }
        uint64_t addr = 0x48000, sz = 128;
        fwrite(&addr, 8, 1, f);
        fwrite(&sz, 8, 1, f);
        fwrite(mk, 1, 128, f);
        fclose(f);
        printf("oracle div loops=%d: post.bin = markers(128B @0x48000, sum=%u); fpref=%s.fpref\n",
               loops, sum, argv[3]);
        return 0;
    }
    FILE* f = fopen(argv[3], "wb");
    if (!f) { perror("open"); return 1; }
    uint64_t addr = 0x40000;
    fwrite(&addr, 8, 1, f);
    fwrite(&size, 8, 1, f);
    fwrite(buf, 1, size, f);
    fclose(f);
    float s0, s1;
    memcpy(&s0, buf, 4); memcpy(&s1, buf + size - 4, 4);
    printf("oracle %s loops=%d: wrote %s (%llu bytes @0x40000), first=%a last=%a\n",
           argv[1], loops, argv[3], (unsigned long long)size, s0, s1);
    return 0;
}
