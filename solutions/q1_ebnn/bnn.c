/* 大題一 Part A 參考解答。每個函式上方註明起始檔錯在哪。 */
#include "bnn.h"
#include "model.h"

/* 錯：迴圈只跑 31 次，第 31 位永遠沒算到。
 * 這裡用 SWAR（一次處理所有位元、沒有迴圈）；也可以用 __builtin_popcount。 */
int popcount32(uint32_t x) {
    x = x - ((x >> 1) & 0x55555555u);
    x = (x & 0x33333333u) + ((x >> 2) & 0x33333333u);
    x = (x + (x >> 4)) & 0x0F0F0F0Fu;
    return (int)((x * 0x01010101u) >> 24);
}

/* 錯 1：XOR 算的是「不同」的位數，eBNN 要的是 XNOR（相同的位數）= ~(a ^ w)。
 * 錯 2：門檻是 >=，不是 >。
 * 錯 3：神經元 j 要放在 bit j，不是 bit 31-j（第二層的 W2 是照 bit j 排的）。 */
uint32_t bnn_hidden(const uint32_t img[2]) {
    uint32_t h = 0;
    for (int j = 0; j < N_HIDDEN; j++) {
        int matches = popcount32(~(img[0] ^ W1[j][0])) + popcount32(~(img[1] ^ W1[j][1]));
        if (matches >= T1[j]) {
            h |= 1u << j;
        }
    }
    return h;
}

/* 錯：二值內積 = (相同數) - (不同數) = p - (32 - p) = 2p - 32。 */
void bnn_scores(uint32_t hidden, int32_t scores[10]) {
    for (int k = 0; k < N_OUT; k++) {
        scores[k] = 2 * popcount32(~(hidden ^ W2[k])) - 32;
    }
}

/* 錯：>= 會在同分時選到 index 較大的；規格是同分取最小的，所以用 >。 */
int bnn_infer(const uint32_t img[2], int32_t scores[10]) {
    bnn_scores(bnn_hidden(img), scores);
    int best = 0;
    for (int k = 1; k < N_OUT; k++) {
        if (scores[k] > scores[best]) best = k;
    }
    return best;
}
