/* 由 common/model.py 產生的 eBNN 權重（不要手改）。 */
#ifndef MODEL_H
#define MODEL_H

#include <stdint.h>

#define N_HIDDEN 32
#define N_OUT 10

/* W1[j][0] = 權重低 32 位（像素 0..31），W1[j][1] = 高 32 位（像素 32..63） */
static const uint32_t W1[N_HIDDEN][2] = {
    {0x5262423Cu, 0x3C42464Au},  /* neuron  0 */
    {0x2931211Eu, 0x1E212325u},  /* neuron  1 */
    {0xA4C48478u, 0x78848C94u},  /* neuron  2 */
    {0x18181C18u, 0x3C181818u},  /* neuron  3 */
    {0x0C0C0E0Cu, 0x1E0C0C0Cu},  /* neuron  4 */
    {0x30303830u, 0x78303030u},  /* neuron  5 */
    {0x2040423Cu, 0x7E040810u},  /* neuron  6 */
    {0x1020211Eu, 0x3F020408u},  /* neuron  7 */
    {0x40808478u, 0xFC081020u},  /* neuron  8 */
    {0x3840423Cu, 0x3C424040u},  /* neuron  9 */
    {0x1C20211Eu, 0x1E212020u},  /* neuron 10 */
    {0x70808478u, 0x78848080u},  /* neuron 11 */
    {0x22242830u, 0x2020207Eu},  /* neuron 12 */
    {0x11121418u, 0x1010103Fu},  /* neuron 13 */
    {0x44485060u, 0x404040FCu},  /* neuron 14 */
    {0x3E02027Eu, 0x3C424040u},  /* neuron 15 */
    {0x1F01013Fu, 0x1E212020u},  /* neuron 16 */
    {0x7C0404FCu, 0x78848080u},  /* neuron 17 */
    {0x3E020438u, 0x3C424242u},  /* neuron 18 */
    {0x1F01021Cu, 0x1E212121u},  /* neuron 19 */
    {0x7C040870u, 0x78848484u},  /* neuron 20 */
    {0x1020407Eu, 0x08080808u},  /* neuron 21 */
    {0x0810203Fu, 0x04040404u},  /* neuron 22 */
    {0x204080FCu, 0x10101010u},  /* neuron 23 */
    {0x3C42423Cu, 0x3C424242u},  /* neuron 24 */
    {0x1E21211Eu, 0x1E212121u},  /* neuron 25 */
    {0x78848478u, 0x78848484u},  /* neuron 26 */
    {0x4242423Cu, 0x1C20407Cu},  /* neuron 27 */
    {0x2121211Eu, 0x0E10203Eu},  /* neuron 28 */
    {0x84848478u, 0x384080F8u},  /* neuron 29 */
    {0xFFFFFFFFu, 0xFFFFFFFFu},  /* neuron 30 */
    {0xD2447CB9u, 0xBED9C258u},  /* neuron 31 */
};

/* 第一層門檻：相同的位數 >= T1[j] 時輸出 1 */
static const int T1[N_HIDDEN] = {60, 60, 60, 60, 60, 60, 60, 60, 60, 60, 60, 60, 60, 60, 60, 60, 60, 60, 60, 60, 60, 60, 60, 60, 60, 60, 60, 60, 60, 60, 44, 36};

/* 第二層權重：每個輸出一個 32-bit 字 */
static const uint32_t W2[N_OUT] = {0x00000007u, 0x00000038u, 0x000001C0u, 0x00000E00u, 0x00007000u, 0x00038000u, 0x001C0000u, 0x00E00000u, 0x07000000u, 0x38000000u};

#endif
