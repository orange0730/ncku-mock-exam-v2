/* 評分用的對照組（提供，不要修改）：和你的實作編譯在同一個函式庫裡比速度。 */
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>

static int cmp_u32(const void *a, const void *b) {
    uint32_t x = *(const uint32_t *)a, y = *(const uint32_t *)b;
    return (x > y) - (x < y);
}

void bench_qsort_u32(uint32_t *a, size_t n) { qsort(a, n, sizeof *a, cmp_u32); }

uint32_t bench_crc32_bitwise(const uint8_t *p, size_t len) {
    uint32_t crc = 0xFFFFFFFFu;
    for (size_t i = 0; i < len; i++) {
        crc ^= p[i];
        for (int k = 0; k < 8; k++) crc = (crc & 1u) ? (crc >> 1) ^ 0xEDB88320u : crc >> 1;
    }
    return crc ^ 0xFFFFFFFFu;
}
