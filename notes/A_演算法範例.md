# 附錄 A：演算法範例（CRC-32、SHA-0 / SHA-1、排序、二值神經網路、popcount）

> 去年考題的三種演算法（排序、SHA-0、CRC32）與 eBNN 推論都在這裡。
> `algolab.c` 是一支完整、可編譯、內含自我測試的程式，已在樹莓派上用 `gcc -std=c11 -O2 -Wall -Wextra` 驗證；
> 每個函式都可以單獨複製到板子的韌體裡用（只依賴 `<stdint.h>`、`<string.h>`、`<stdlib.h>`）。

## 目錄

1. [測試向量（先背這些）](#1-測試向量先背這些)
2. [CRC-32](#2-crc-32)
3. [SHA-0 / SHA-1](#3-sha-0--sha-1)
4. [排序](#4-排序)
5. [二值神經網路（eBNN）層](#5-二值神經網路ebnn層)
6. [完整程式 algolab.c](#6-完整程式-algolabc)
7. [Python 對照實作（在電腦上驗證板子的輸出）](#7-python-對照實作在電腦上驗證板子的輸出)

---

## 1. 測試向量（先背這些）

| 演算法 | 輸入 | 輸出 |
|---|---|---|
| CRC-32（IEEE / zlib / Ethernet） | `"123456789"` | `0xCBF43926` |
| CRC-32 | 空字串 | `0x00000000` |
| SHA-0 | `"abc"` | `0164b8a914cd2a5e74c4f7ff082c4d97f1edf880` |
| SHA-1 | `"abc"` | `a9993e364706816aba3e25717850c26c9cd0d89d` |
| SHA-1 | 空字串 | `da39a3ee5e6b4b0d3255bfef95601890afd80709` |
| SHA-256 | `"abc"` | `ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad` |
| SHA-256 | 空字串 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

電腦上快速驗證：`python3 -c "import zlib,hashlib; print(hex(zlib.crc32(b'123456789')), hashlib.sha1(b'abc').hexdigest())"`。

---

## 2. CRC-32

**參數**：poly `0x04C11DB7`（反射寫法 `0xEDB88320`）、init `0xFFFFFFFF`、refin = true、refout = true、xorout `0xFFFFFFFF`。

| 寫法 | 速度 | 記憶體 |
|---|---|---|
| 逐位元（每 byte 8 次迴圈） | 慢 | 0 |
| 查表（256 × 4 bytes = 1 KB） | 約快 3–8 倍 | 1 KB（可放 flash，`const`） |
| slicing-by-4 / by-8 | 更快 | 4 KB / 8 KB |
| RP2350 DMA sniffer | 硬體算，CPU 空出來 | 0（見 [2-3 的 DMA 章節](2-3_臨界區_DMA.md)） |

- **反射版（右移）一定配 `0xEDB88320`**；不反射版（左移、MSB-first）配 `0x04C11DB7`。兩者混用就是錯的。
- 可以分段算：`crc = crc32_update(crc, chunk)`，最後再 XOR `0xFFFFFFFF`。

## 3. SHA-0 / SHA-1

1. **填充**：補 `0x80`，補 0 直到長度 ≡ 56 (mod 64)，最後 8 bytes 放原始長度的**位元數**（big-endian）。剩餘 ≥ 56 bytes 時要多一個區塊（55、56、63、64 bytes 是邊界測資）。
2. **每個 64-byte 區塊**：16 個 big-endian word 擴展成 80 個：
   - SHA-0：`W[t] = W[t-3] ^ W[t-8] ^ W[t-14] ^ W[t-16]`
   - SHA-1：`W[t] = ROTL1(W[t-3] ^ W[t-8] ^ W[t-14] ^ W[t-16])` ← **唯一差別**
3. **80 輪**：

| 輪 | f(b, c, d) | K |
|---|---|---|
| 0–19 | `(b & c) \| (~b & d)` | `0x5A827999` |
| 20–39 | `b ^ c ^ d` | `0x6ED9EBA1` |
| 40–59 | `(b & c) \| (b & d) \| (c & d)` | `0x8F1BBCDC` |
| 60–79 | `b ^ c ^ d` | `0xCA62C1D6` |

   每輪：`T = ROTL5(a) + f + e + K + W[t]; e = d; d = c; c = ROTL30(b); b = a; a = T;`
4. 初值 `67452301 EFCDAB89 98BADCFE 10325476 C3D2E1F0`；每個區塊做完把 a..e 加回 h0..h4；輸出 h0..h4 的 big-endian，共 20 bytes。

**SHA-256（RP2350 有硬體加速器）**：填充方式相同（`1` 位、0、64 位長度），輸出 32 bytes。硬體使用步驟見 [3_去年題型與今年預測.md](3_去年題型與今年預測.md#62-sha-256-硬體加速器)。

## 4. 排序

| 方法 | 時間 | 額外記憶體 | MCU 上的考量 |
|---|---|---|---|
| 插入排序 | O(n²)，n 小時最快 | O(1) | n < 32 或資料幾乎排好時用 |
| quicksort | 平均 O(n log n)，最差 O(n²) | O(log n) 堆疊 | 遞迴吃堆疊；挑好 pivot |
| heapsort | O(n log n) 保證 | O(1) | 記憶體最省、時間有保證 |
| merge sort | O(n log n)，穩定 | O(n) | 要一倍 RAM |
| LSD radix（每輪 8 位，4 輪） | O(n) | O(n) + 256 計數 | 32 位整數最快，不用比較函式 |
| `qsort()` | O(n log n) | — | 每次比較都經函式指標，較慢 |

## 5. 二值神經網路（eBNN）層

- 權重、啟動值都是 ±1，用 1 位元存（1 = +1、0 = −1）；32 個打包成一個 `uint32_t`。
- **內積 = 2 × popcount(XNOR(x, w)) − n**（相同 +1、不同 −1）。
- BatchNorm + sign 摺疊成整數門檻：`輸出 = (matches >= T) ? 1 : 0`（γ < 0 時不等號反向，或把權重整組反相）。
- 最後一層通常取原始分數、argmax（注意同分規則）。

## 6. 完整程式 algolab.c

```c
// file: algolab.c
// 編譯：gcc -std=c11 -O2 -Wall -Wextra algolab.c -o algolab && ./algolab
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ---------------- popcount ---------------- */
static int popcount32(uint32_t x) {
    x = x - ((x >> 1) & 0x55555555u);
    x = (x & 0x33333333u) + ((x >> 2) & 0x33333333u);
    x = (x + (x >> 4)) & 0x0F0F0F0Fu;
    return (int)((x * 0x01010101u) >> 24);
}

/* ---------------- CRC-32 ---------------- */
static uint32_t crc32_bitwise(const uint8_t *p, size_t len) {
    uint32_t crc = 0xFFFFFFFFu;
    for (size_t i = 0; i < len; i++) {
        crc ^= p[i];
        for (int k = 0; k < 8; k++) crc = (crc & 1u) ? (crc >> 1) ^ 0xEDB88320u : crc >> 1;
    }
    return crc ^ 0xFFFFFFFFu;
}

static uint32_t crc_table[256];
static void crc32_init_table(void) {
    for (uint32_t i = 0; i < 256; i++) {
        uint32_t c = i;
        for (int k = 0; k < 8; k++) c = (c & 1u) ? (c >> 1) ^ 0xEDB88320u : c >> 1;
        crc_table[i] = c;
    }
}
/* 可分段：crc = 0xFFFFFFFF; 多次 crc = crc32_update(crc, ...); 最後 crc ^ 0xFFFFFFFF */
static uint32_t crc32_update(uint32_t crc, const uint8_t *p, size_t len) {
    for (size_t i = 0; i < len; i++) crc = (crc >> 8) ^ crc_table[(crc ^ p[i]) & 0xFFu];
    return crc;
}
static uint32_t crc32_table(const uint8_t *p, size_t len) {
    return crc32_update(0xFFFFFFFFu, p, len) ^ 0xFFFFFFFFu;
}

/* ---------------- SHA-0 / SHA-1 ---------------- */
static uint32_t rotl(uint32_t x, unsigned k) { return (x << k) | (x >> ((32 - k) & 31)); }

static void sha_block(uint32_t h[5], const uint8_t *p, int sha1) {
    uint32_t w[80];
    for (int t = 0; t < 16; t++)
        w[t] = ((uint32_t)p[4 * t] << 24) | ((uint32_t)p[4 * t + 1] << 16) |
               ((uint32_t)p[4 * t + 2] << 8) | (uint32_t)p[4 * t + 3];
    for (int t = 16; t < 80; t++) {
        uint32_t v = w[t - 3] ^ w[t - 8] ^ w[t - 14] ^ w[t - 16];
        w[t] = sha1 ? rotl(v, 1) : v;                     /* SHA-0 與 SHA-1 唯一的差別 */
    }
    uint32_t a = h[0], b = h[1], c = h[2], d = h[3], e = h[4];
    for (int t = 0; t < 80; t++) {
        uint32_t f, k;
        if (t < 20)      { f = (b & c) | (~b & d);          k = 0x5A827999u; }
        else if (t < 40) { f = b ^ c ^ d;                   k = 0x6ED9EBA1u; }
        else if (t < 60) { f = (b & c) | (b & d) | (c & d); k = 0x8F1BBCDCu; }
        else             { f = b ^ c ^ d;                   k = 0xCA62C1D6u; }
        uint32_t tmp = rotl(a, 5) + f + e + k + w[t];
        e = d; d = c; c = rotl(b, 30); b = a; a = tmp;
    }
    h[0] += a; h[1] += b; h[2] += c; h[3] += d; h[4] += e;
}

static void sha(const uint8_t *msg, size_t len, uint8_t out[20], int sha1) {
    uint32_t h[5] = {0x67452301u, 0xEFCDAB89u, 0x98BADCFEu, 0x10325476u, 0xC3D2E1F0u};
    size_t full = len / 64;
    for (size_t i = 0; i < full; i++) sha_block(h, msg + 64 * i, sha1);
    uint8_t last[128] = {0};
    size_t rest = len % 64;
    memcpy(last, msg + 64 * full, rest);
    last[rest] = 0x80;
    size_t blocks = rest < 56 ? 1 : 2;                     /* 剩 >= 56 bytes 要多一個區塊 */
    uint64_t bits = (uint64_t)len * 8;
    for (int i = 0; i < 8; i++) last[64 * blocks - 1 - i] = (uint8_t)(bits >> (8 * i));   /* big-endian */
    for (size_t i = 0; i < blocks; i++) sha_block(h, last + 64 * i, sha1);
    for (int i = 0; i < 5; i++) {
        out[4 * i] = (uint8_t)(h[i] >> 24); out[4 * i + 1] = (uint8_t)(h[i] >> 16);
        out[4 * i + 2] = (uint8_t)(h[i] >> 8); out[4 * i + 3] = (uint8_t)h[i];
    }
}

/* ---------------- 排序 ---------------- */
static void insertion_sort(uint32_t *a, size_t n) {
    for (size_t i = 1; i < n; i++) {                       /* i < n，不是 n - 1；n = 0 也安全 */
        uint32_t key = a[i];
        size_t j = i;
        while (j > 0 && a[j - 1] > key) { a[j] = a[j - 1]; j--; }
        a[j] = key;
    }
}

static void quick_sort(uint32_t *a, long lo, long hi) {    /* 呼叫：quick_sort(a, 0, n - 1)，n >= 1 */
    while (lo < hi) {
        if (hi - lo < 16) { insertion_sort(a + lo, (size_t)(hi - lo + 1)); return; }
        uint32_t pivot = a[lo + (hi - lo) / 2];
        long i = lo, j = hi;
        while (i <= j) {
            while (a[i] < pivot) i++;
            while (a[j] > pivot) j--;
            if (i <= j) { uint32_t t = a[i]; a[i] = a[j]; a[j] = t; i++; j--; }
        }
        if (j - lo < hi - i) { quick_sort(a, lo, j); lo = i; }   /* 先遞迴小的那邊，堆疊深度 O(log n) */
        else { quick_sort(a, i, hi); hi = j; }
    }
}

static int radix_sort(uint32_t *a, size_t n) {             /* 回傳 -1 = 記憶體不足 */
    if (n < 2) return 0;
    uint32_t *tmp = malloc(n * sizeof *tmp);
    if (!tmp) return -1;
    uint32_t *src = a, *dst = tmp;
    for (int shift = 0; shift < 32; shift += 8) {
        size_t count[257] = {0};
        for (size_t i = 0; i < n; i++) count[((src[i] >> shift) & 0xFFu) + 1]++;
        for (int b = 0; b < 256; b++) count[b + 1] += count[b];
        for (size_t i = 0; i < n; i++) dst[count[(src[i] >> shift) & 0xFFu]++] = src[i];
        uint32_t *t = src; src = dst; dst = t;
    }
    free(tmp);                                              /* 4 輪後資料回到 a */
    return 0;
}

/* ---------------- 二值全連接層 ---------------- */
/* in_words 個 word 的輸入、n_out 個神經元；W[j] 是神經元 j 的權重（in_words 個 word）、T[j] 門檻。
 * 輸出第 j 位 = (popcount(XNOR(x, W[j])) >= T[j])。 */
static uint32_t bnn_dense(const uint32_t *x, int in_words, const uint32_t *W, const int *T, int n_out) {
    uint32_t h = 0;
    for (int j = 0; j < n_out; j++) {
        int matches = 0;
        for (int k = 0; k < in_words; k++) matches += popcount32(~(x[k] ^ W[j * in_words + k]));
        if (matches >= T[j]) h |= 1u << j;
    }
    return h;
}
/* 最後一層：score_k = 2 * popcount(XNOR(h, W2[k])) - n_bits；回傳 argmax（同分取最小 k） */
static int bnn_argmax(uint32_t h, const uint32_t *W2, int n_cls, int n_bits, int32_t *scores) {
    uint32_t mask = n_bits >= 32 ? 0xFFFFFFFFu : ((1u << n_bits) - 1u);
    int best = 0;
    for (int k = 0; k < n_cls; k++) {
        scores[k] = 2 * popcount32(~(h ^ W2[k]) & mask) - n_bits;
        if (scores[k] > scores[best]) best = k;
    }
    return best;
}

/* ---------------- 自我測試 ---------------- */
static void hex(const uint8_t *p, int n) { for (int i = 0; i < n; i++) printf("%02x", p[i]); printf("\n"); }

int main(void) {
    const uint8_t *s9 = (const uint8_t *)"123456789";
    crc32_init_table();
    printf("crc32 bitwise = %08x  table = %08x  (expect cbf43926)\n",
           (unsigned)crc32_bitwise(s9, 9), (unsigned)crc32_table(s9, 9));
    uint32_t c = 0xFFFFFFFFu;                               /* 分段計算 */
    c = crc32_update(c, s9, 4);
    c = crc32_update(c, s9 + 4, 5);
    printf("crc32 in two chunks = %08x\n", (unsigned)(c ^ 0xFFFFFFFFu));

    uint8_t d[20];
    sha((const uint8_t *)"abc", 3, d, 0); printf("sha0(abc) = "); hex(d, 20);   /* 0164b8a9... */
    sha((const uint8_t *)"abc", 3, d, 1); printf("sha1(abc) = "); hex(d, 20);   /* a9993e36... */
    sha((const uint8_t *)"", 0, d, 1);    printf("sha1('')  = "); hex(d, 20);   /* da39a3ee... */

    enum { N = 1000 };
    static uint32_t a[N], b[N], r[N];
    uint32_t seed = 12345;
    for (int i = 0; i < N; i++) { seed = seed * 1664525u + 1013904223u; a[i] = b[i] = r[i] = seed; }
    insertion_sort(a, N); quick_sort(b, 0, N - 1); radix_sort(r, N);
    int ok = 1;
    for (int i = 0; i < N; i++) {
        if (i && a[i - 1] > a[i]) ok = 0;
        if (a[i] != b[i] || a[i] != r[i]) ok = 0;
    }
    printf("sort: %s (min=%u max=%u median=%u)\n", ok ? "ok" : "WRONG",
           (unsigned)a[0], (unsigned)a[N - 1], (unsigned)a[N / 2]);

    /* 二值網路小例子：輸入 64 位（2 個 word），2 個隱藏神經元，2 個類別 */
    const uint32_t x[2] = {0xFFFF0000u, 0x0000FFFFu};
    const uint32_t W1[4] = {0xFFFF0000u, 0x0000FFFFu,       /* 神經元 0：跟 x 一模一樣 → 64 個相同 */
                            0x0000FFFFu, 0xFFFF0000u};      /* 神經元 1：完全相反 → 0 個相同 */
    const int T1[2] = {48, 48};
    uint32_t h = bnn_dense(x, 2, W1, T1, 2);
    const uint32_t W2[2] = {0x1u, 0x2u};
    int32_t sc[2];
    int pred = bnn_argmax(h, W2, 2, 2, sc);
    printf("bnn: hidden=0x%x scores=[%d,%d] pred=%d (expect hidden=0x1 pred=0)\n",
           (unsigned)h, (int)sc[0], (int)sc[1], pred);
    return 0;
}
```

預期輸出：

```text
crc32 bitwise = cbf43926  table = cbf43926  (expect cbf43926)
crc32 in two chunks = cbf43926
sha0(abc) = 0164b8a914cd2a5e74c4f7ff082c4d97f1edf880
sha1(abc) = a9993e364706816aba3e25717850c26c9cd0d89d
sha1('')  = da39a3ee5e6b4b0d3255bfef95601890afd80709
sort: ok (min=... max=... median=...)
bnn: hidden=0x1 scores=[2,-2] pred=0 (expect hidden=0x1 pred=0)
```

## 7. Python 對照實作（在電腦上驗證板子的輸出）

```python
# file: algoref.py
import hashlib
import struct
import zlib


def rotl(x, k):
    return ((x << k) | (x >> (32 - k))) & 0xFFFFFFFF


def sha0(msg: bytes, sha1=False) -> bytes:
    h = [0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476, 0xC3D2E1F0]
    ml = len(msg) * 8
    msg = msg + b'\x80' + b'\x00' * ((55 - len(msg)) % 64) + struct.pack('>Q', ml)
    for off in range(0, len(msg), 64):
        w = list(struct.unpack('>16I', msg[off:off + 64]))
        for t in range(16, 80):
            v = w[t - 3] ^ w[t - 8] ^ w[t - 14] ^ w[t - 16]
            w.append(rotl(v, 1) if sha1 else v)
        a, b, c, d, e = h
        for t in range(80):
            if t < 20:
                f, k = (b & c) | (~b & d), 0x5A827999
            elif t < 40:
                f, k = b ^ c ^ d, 0x6ED9EBA1
            elif t < 60:
                f, k = (b & c) | (b & d) | (c & d), 0x8F1BBCDC
            else:
                f, k = b ^ c ^ d, 0xCA62C1D6
            a, b, c, d, e = (rotl(a, 5) + (f & 0xFFFFFFFF) + e + k + w[t]) & 0xFFFFFFFF, a, rotl(b, 30), c, d
        h = [(x + y) & 0xFFFFFFFF for x, y in zip(h, (a, b, c, d, e))]
    return b''.join(struct.pack('>I', x) for x in h)


assert sha0(b'abc').hex() == '0164b8a914cd2a5e74c4f7ff082c4d97f1edf880'
assert sha0(b'abc', sha1=True) == hashlib.sha1(b'abc').digest()
assert zlib.crc32(b'123456789') == 0xCBF43926
print('CRC32:', hex(zlib.crc32(b'123456789')), ' SHA-0:', sha0(b'abc').hex(),
      ' SHA-256:', hashlib.sha256(b'abc').hexdigest())
print('sorted:', sorted([5, 3, 9, 1]))
```
