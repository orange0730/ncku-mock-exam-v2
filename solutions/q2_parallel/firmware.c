/* 大題二 Part A 參考解答。 */
#include "firmware.h"
#include "bnn.h"

int fw_handle(const uint32_t *req, int n, uint32_t *resp) {
    if (n != 3) return -1;                         /* 錯 1：沒檢查長度，req[1]、req[2] 可能讀出界 */
    uint32_t h = req[0];
    unsigned first = (h >> 8) & 0xFFu;             /* 錯 2：first 是 8 位元欄位，& 0x0F 會把 16..31 變成 0..15 */
    unsigned count = h & 0xFFu;
    if (count == 0 || count > 32 || first + count > 32) return -1;   /* 錯 3：沒檢查範圍 */

    uint32_t img[2] = { req[1], req[2] };          /* 錯 4：img[0] 是低 32 位 = req[1] */
    /* 錯 5：count == 32 時 1u << 32 是未定義行為（ARM / x86 實際上都會得到錯的 mask） */
    uint32_t low = count >= 32 ? 0xFFFFFFFFu : ((1u << count) - 1u);
    uint32_t mask = low << first;                  /* first + count <= 32，所以這裡不會出界 */

    resp[0] = h;                                   /* 錯 6：header 要「原樣」送回；重組會把錯的 first 也一起送回去 */
    resp[1] = bnn_hidden(img) & mask;
    return 2;
}
