/* 大題三 Part A 參考解答。 */
#include "algos.h"

#include <stdlib.h>
#include <string.h>

#include "engine.h"

/* ------------------------------------------------------------------ 排序
 * 起始檔：插入排序，迴圈條件 i < n - 1 漏掉最後一個元素；n == 0 時 n - 1 會變成 SIZE_MAX，直接讀出界。
 * 而且 O(n^2)，100 萬筆根本跑不完。
 * 這裡用 LSD radix sort（4 輪，每輪 8 位元）：O(n)、穩定、不需要比較函式，比 qsort 快很多。
 * 代價是需要 n 個 uint32_t 的暫存空間（在 MCU 上要考慮 RAM 夠不夠）。 */
void sort_u32(uint32_t *a, size_t n) {
    if (n < 2) return;
    uint32_t *tmp = malloc(n * sizeof *tmp);
    if (!tmp) {                                   /* 配置失敗時退回插入排序，至少保證正確 */
        for (size_t i = 1; i < n; i++) {
            uint32_t key = a[i];
            size_t j = i;
            while (j > 0 && a[j - 1] > key) { a[j] = a[j - 1]; j--; }
            a[j] = key;
        }
        return;
    }
    uint32_t *src = a, *dst = tmp;
    for (int shift = 0; shift < 32; shift += 8) {
        size_t count[257] = {0};
        for (size_t i = 0; i < n; i++) count[((src[i] >> shift) & 0xFFu) + 1]++;
        for (int b = 0; b < 256; b++) count[b + 1] += count[b];
        for (size_t i = 0; i < n; i++) dst[count[(src[i] >> shift) & 0xFFu]++] = src[i];
        uint32_t *t = src; src = dst; dst = t;
    }
    /* 4 輪（偶數）之後資料剛好回到 a */
    free(tmp);
}

/* ------------------------------------------------------------------ SHA-0
 * 起始檔的錯：
 *   1. 訊息排程多了 rotl(…, 1) —— 那是 SHA-1。SHA-0 沒有這個旋轉。
 *   2. 第 40..59 輪的 f 要用 majority：(b&c) | (b&d) | (c&d)，不是 parity。
 *   3. 長度欄位要 big-endian（高位元組在前）。
 *   4. 剩餘 >= 56 bytes 時，0x80 和長度放不進同一個區塊，要多補一個區塊。 */
static uint32_t rotl(uint32_t x, unsigned k) { return (x << k) | (x >> ((32 - k) & 31)); }

static void sha_block(uint32_t h[5], const uint8_t *p) {
    uint32_t w[80];
    for (int t = 0; t < 16; t++)
        w[t] = ((uint32_t)p[4 * t] << 24) | ((uint32_t)p[4 * t + 1] << 16) |
               ((uint32_t)p[4 * t + 2] << 8) | p[4 * t + 3];
    for (int t = 16; t < 80; t++)
        w[t] = w[t - 3] ^ w[t - 8] ^ w[t - 14] ^ w[t - 16];      /* SHA-0：不旋轉 */

    uint32_t a = h[0], b = h[1], c = h[2], d = h[3], e = h[4];
    for (int t = 0; t < 80; t++) {
        uint32_t f, k;
        if (t < 20)      { f = (b & c) | (~b & d);           k = 0x5A827999u; }
        else if (t < 40) { f = b ^ c ^ d;                    k = 0x6ED9EBA1u; }
        else if (t < 60) { f = (b & c) | (b & d) | (c & d);  k = 0x8F1BBCDCu; }
        else             { f = b ^ c ^ d;                    k = 0xCA62C1D6u; }
        uint32_t tmp = rotl(a, 5) + f + e + k + w[t];
        e = d; d = c; c = rotl(b, 30); b = a; a = tmp;
    }
    h[0] += a; h[1] += b; h[2] += c; h[3] += d; h[4] += e;
}

void sha0(const uint8_t *msg, size_t len, uint8_t out[20]) {
    uint32_t h[5] = {0x67452301u, 0xEFCDAB89u, 0x98BADCFEu, 0x10325476u, 0xC3D2E1F0u};
    size_t full = len / 64;
    for (size_t i = 0; i < full; i++) sha_block(h, msg + 64 * i);

    uint8_t last[128] = {0};
    size_t rest = len % 64;
    memcpy(last, msg + 64 * full, rest);
    last[rest] = 0x80;
    size_t blocks = rest < 56 ? 1 : 2;
    uint64_t bits = (uint64_t)len * 8;
    for (int i = 0; i < 8; i++) last[64 * blocks - 1 - i] = (uint8_t)(bits >> (8 * i));
    for (size_t i = 0; i < blocks; i++) sha_block(h, last + 64 * i);

    for (int i = 0; i < 5; i++) {
        out[4 * i] = (uint8_t)(h[i] >> 24);
        out[4 * i + 1] = (uint8_t)(h[i] >> 16);
        out[4 * i + 2] = (uint8_t)(h[i] >> 8);
        out[4 * i + 3] = (uint8_t)h[i];
    }
}

/* ------------------------------------------------------------------ CRC-32（軟體）
 * 起始檔的錯：
 *   1. 反射版（LSB-first）要用反射後的多項式 0xEDB88320，不是 0x04C11DB7。
 *   2. 初值是 0xFFFFFFFF，最後還要再 XOR 0xFFFFFFFF。
 *   3. 逐位元每個 byte 要 8 次迴圈；改用 256 項查表，每個 byte 只要一次查表。 */
static uint32_t table[256];
static int table_ready;

static void build_table(void) {
    for (uint32_t i = 0; i < 256; i++) {
        uint32_t c = i;
        for (int k = 0; k < 8; k++) c = (c & 1u) ? (c >> 1) ^ 0xEDB88320u : c >> 1;
        table[i] = c;
    }
    table_ready = 1;
}

uint32_t crc32_sw(const uint8_t *p, size_t len) {
    if (!table_ready) build_table();
    uint32_t crc = 0xFFFFFFFFu;
    for (size_t i = 0; i < len; i++) crc = (crc >> 8) ^ table[(crc ^ p[i]) & 0xFFu];
    return crc ^ 0xFFFFFFFFu;
}

/* ------------------------------------------------------------------ CRC-32（DMA sniffer）
 * 起始檔的錯：
 *   1. count 填了 bytes，又用 XFER_32：搬了 4 倍的量，而且位址不一定對齊 → 引擎中止。
 *      sniffer 是逐 byte 算的，用 XFER_8、count = len 最簡單也最安全。
 *   2. 標準 CRC-32 是「反射」的：資料要用 SNIFF_CRC32_REV（每個 byte 先反轉），
 *      初值 0xFFFFFFFF，讀出來時要位元反轉再反相（output reverse + invert）。
 *   3. len == 0 時引擎不接受 count 0；空資料的 CRC-32 是 0。
 *   4. 沒有檢查 claim 失敗；用完沒有 disable sniffer（release 時引擎會中止）。 */
uint32_t crc32_dma(const uint8_t *p, size_t len) {
    if (len == 0) return 0;
    int ch = engine_claim();
    if (ch < 0) return crc32_sw(p, len);           /* 沒有通道就退回軟體算 */
    static uint8_t sink;
    engine_job_t job = {
        .src = p, .dst = &sink, .count = len, .size = XFER_8,
        .src_increment = true, .dst_increment = false,   /* 目的地不前進：只是要讓資料「流過」sniffer */
    };
    engine_configure(ch, &job);
    engine_sniff_enable(ch, SNIFF_CRC32_REV);
    engine_sniff_set_accumulator(0xFFFFFFFFu);
    engine_sniff_set_output(true, true);
    engine_start(ch);
    engine_wait(ch);
    uint32_t crc = engine_sniff_get_accumulator();
    engine_sniff_disable();
    engine_release(ch);
    return crc;
}
