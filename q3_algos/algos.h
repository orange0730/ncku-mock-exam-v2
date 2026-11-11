/* 大題三：三片板子上各跑一個演算法（介面，不要修改）。完整規格見 README.md。 */
#ifndef ALGOS_H
#define ALGOS_H

#include <stddef.h>
#include <stdint.h>

/* 把 a[0..n-1] 由小到大排序（unsigned 比較）。n 可能是 0。
 * 效率：評分時會和 C 標準函式庫的 qsort 比速度（100 萬筆）。 */
void sort_u32(uint32_t *a, size_t n);

/* SHA-0（FIPS 180，1993 年原始版本）：對 msg[0..len-1] 算出 20 bytes 的摘要。
 * 與 SHA-1 只差在訊息排程（message schedule）少了一個「左旋 1 位」。 */
void sha0(const uint8_t *msg, size_t len, uint8_t out[20]);

/* 標準 CRC-32（Ethernet / zip / PNG 用的那個；"123456789" -> 0xCBF43926）。
 * 用軟體算。效率：評分時會和逐位元（bit-by-bit）版本比速度。 */
uint32_t crc32_sw(const uint8_t *p, size_t len);

/* 同樣的 CRC-32，但必須用搬運引擎的 sniffer 算（見 engine.h）：
 * 讓引擎把資料「搬」一遍，sniffer 在旁邊順便算 CRC。len 可能是 0。
 * 返回前要 disable sniffer、release 通道。 */
uint32_t crc32_dma(const uint8_t *p, size_t len);

#endif
