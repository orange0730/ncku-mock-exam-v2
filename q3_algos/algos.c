/* 大題三 Part A：要修改的檔案。
 *
 * 四個函式都「寫了」，但每一個都有錯，有的錯在邊界、有的錯在規格、有的錯在效率。
 * 函式名稱與參數不要改；可以新增 static 函式與表格。
 */
#include "algos.h"

#include <string.h>

#include "engine.h"

/* ------------------------------------------------------------------ 排序 */
void sort_u32(uint32_t *a, size_t n) {
    for (size_t i = 1; i < n - 1; i++) {
        uint32_t key = a[i];
        size_t j = i;
        while (j > 0 && a[j - 1] > key) {
            a[j] = a[j - 1];
            j--;
        }
        a[j] = key;
    }
}

/* ------------------------------------------------------------------ SHA-0 */
static uint32_t rotl(uint32_t x, unsigned k) { return (x << k) | (x >> (32 - k)); }

static void sha_block(uint32_t h[5], const uint8_t *p) {
    uint32_t w[80];
    for (int t = 0; t < 16; t++)
        w[t] = ((uint32_t)p[4 * t] << 24) | ((uint32_t)p[4 * t + 1] << 16) |
               ((uint32_t)p[4 * t + 2] << 8) | p[4 * t + 3];
    for (int t = 16; t < 80; t++)
        w[t] = rotl(w[t - 3] ^ w[t - 8] ^ w[t - 14] ^ w[t - 16], 1);

    uint32_t a = h[0], b = h[1], c = h[2], d = h[3], e = h[4];
    for (int t = 0; t < 80; t++) {
        uint32_t f, k;
        if (t < 20)      { f = (b & c) | (~b & d);  k = 0x5A827999u; }
        else if (t < 40) { f = b ^ c ^ d;           k = 0x6ED9EBA1u; }
        else if (t < 60) { f = b ^ c ^ d;           k = 0x8F1BBCDCu; }
        else             { f = b ^ c ^ d;           k = 0xCA62C1D6u; }
        uint32_t tmp = rotl(a, 5) + f + e + k + w[t];
        e = d; d = c; c = rotl(b, 30); b = a; a = tmp;
    }
    h[0] += a; h[1] += b; h[2] += c; h[3] += d; h[4] += e;
}

void sha0(const uint8_t *msg, size_t len, uint8_t out[20]) {
    uint32_t h[5] = {0x67452301u, 0xEFCDAB89u, 0x98BADCFEu, 0x10325476u, 0xC3D2E1F0u};
    size_t full = len / 64;
    for (size_t i = 0; i < full; i++) sha_block(h, msg + 64 * i);

    uint8_t last[64] = {0};
    size_t rest = len % 64;
    memcpy(last, msg + 64 * full, rest);
    last[rest] = 0x80;
    uint64_t bits = (uint64_t)len * 8;
    for (int i = 0; i < 8; i++) last[56 + i] = (uint8_t)(bits >> (8 * i));
    sha_block(h, last);

    for (int i = 0; i < 5; i++) {
        out[4 * i] = (uint8_t)(h[i] >> 24);
        out[4 * i + 1] = (uint8_t)(h[i] >> 16);
        out[4 * i + 2] = (uint8_t)(h[i] >> 8);
        out[4 * i + 3] = (uint8_t)h[i];
    }
}

/* ------------------------------------------------------------------ CRC-32（軟體） */
uint32_t crc32_sw(const uint8_t *p, size_t len) {
    uint32_t crc = 0;
    for (size_t i = 0; i < len; i++) {
        crc ^= p[i];
        for (int k = 0; k < 8; k++)
            crc = (crc & 1) ? (crc >> 1) ^ 0x04C11DB7u : crc >> 1;
    }
    return crc;
}

/* ------------------------------------------------------------------ CRC-32（DMA sniffer） */
uint32_t crc32_dma(const uint8_t *p, size_t len) {
    static uint32_t sink;
    int ch = engine_claim();
    engine_job_t job = {
        .src = p, .dst = &sink, .count = len, .size = XFER_32,
        .src_increment = true, .dst_increment = false,
    };
    engine_configure(ch, &job);
    engine_sniff_enable(ch, SNIFF_CRC32);
    engine_sniff_set_accumulator(0);
    engine_start(ch);
    engine_wait(ch);
    uint32_t crc = engine_sniff_get_accumulator();
    engine_release(ch);
    return crc;
}
