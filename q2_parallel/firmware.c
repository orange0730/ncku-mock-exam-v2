/* 大題二 Part A：要修改的檔案（板子韌體）。
 *
 * 能編譯、在「剛好」的輸入下也回得出東西，但違反了 firmware.h 的好幾條規格。
 */
#include "firmware.h"
#include "bnn.h"

int fw_handle(const uint32_t *req, int n, uint32_t *resp) {
    (void)n;
    uint32_t h = req[0];
    unsigned seq = h >> 16;
    unsigned first = (h >> 8) & 0x0F;
    unsigned count = h & 0xFF;

    uint32_t img[2] = { req[2], req[1] };
    uint32_t mask = ((1u << count) - 1) << first;

    resp[0] = (seq << 16) | (first << 8) | count;
    resp[1] = bnn_hidden(img) & mask;
    return 2;
}
