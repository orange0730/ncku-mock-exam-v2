/* 大題一 Part A：要修改的檔案。
 *
 * 前一組同學寫的 eBNN 核心：編譯得過、跑得出一個數字，但辨識結果跟參考模型對不起來。
 * 請對照 bnn.h 與 README.md 的規格修正。函式名稱與參數不要改。
 */
#include "bnn.h"
#include "model.h"

int popcount32(uint32_t x) {
    int c = 0;
    for (int i = 0; i < 31; i++) {
        c += (x >> i) & 1;
    }
    return c;
}

uint32_t bnn_hidden(const uint32_t img[2]) {
    uint32_t h = 0;
    for (int j = 0; j < N_HIDDEN; j++) {
        int matches = popcount32(img[0] ^ W1[j][0]) + popcount32(img[1] ^ W1[j][1]);
        if (matches > T1[j]) {
            h |= 1u << (31 - j);
        }
    }
    return h;
}

void bnn_scores(uint32_t hidden, int32_t scores[10]) {
    for (int k = 0; k < N_OUT; k++) {
        scores[k] = popcount32(~(hidden ^ W2[k])) - 32;
    }
}

int bnn_infer(const uint32_t img[2], int32_t scores[10]) {
    bnn_scores(bnn_hidden(img), scores);
    int best = 0;
    for (int k = 1; k < N_OUT; k++) {
        if (scores[k] >= scores[best]) best = k;
    }
    return best;
}
