/* 大題一：eBNN 推論核心（介面，不要修改）。完整規格見 README.md。
 *
 * 影像 img[0] = 像素 0..31（第 0..3 列），img[1] = 像素 32..63（第 4..7 列）；
 * 像素 (r, c) 在整張 64-bit 影像的 bit r*8 + c。權重在 common/model.h。
 */
#ifndef BNN_H
#define BNN_H

#include <stdint.h>

/* x 裡 1 的個數（0..32）。 */
int popcount32(uint32_t x);

/* 第一層：回傳 32 個隱藏神經元的輸出，bit j = 神經元 j。
 *   matches_j = popcount(XNOR(img, W1[j]))（64 位元裡相同的位數）
 *   神經元 j 輸出 1  <=>  matches_j >= T1[j] */
uint32_t bnn_hidden(const uint32_t img[2]);

/* 第二層：scores[k] = 2 * popcount(XNOR(hidden, W2[k])) - 32，k = 0..9 */
void bnn_scores(uint32_t hidden, int32_t scores[10]);

/* 完整推論：填好 scores，回傳分數最大的 k（同分取 index 最小者）。 */
int bnn_infer(const uint32_t img[2], int32_t scores[10]);

#endif
