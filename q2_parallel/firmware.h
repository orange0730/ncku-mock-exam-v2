/* 大題二：板子韌體的請求處理函式（介面，不要修改）。
 *
 * 請求（/boardN/request，std_msgs/msg/UInt32MultiArray，共 3 個 word）：
 *   req[0] = header：bits 31..16 = seq（0..65535）
 *                    bits 15..8  = first（第一個神經元編號，0..31）
 *                    bits  7..0  = count（神經元個數，1..32）
 *   req[1] = 影像低 32 位（像素 0..31）
 *   req[2] = 影像高 32 位（像素 32..63）
 *
 * 回應（/boardN/response，UInt32MultiArray，共 2 個 word）：
 *   resp[0] = 與 req[0] 完全相同的 header（原樣送回，協調者靠它對帳）
 *   resp[1] = 神經元 first .. first+count-1 的輸出，放在「原本的」位元位置
 *             （bit j = 神經元 j），其他位元一律為 0
 *
 * 回傳值：成功回傳回應的 word 數（2）；請求不合法時回傳 -1，且不得寫入 resp：
 *   n != 3、count == 0、count > 32、first + count > 32。
 *
 * 記憶體：req 只保證有 n 個 word（n 可能小於 3！先檢查 n 再讀 req[1]、req[2]），
 *         resp 只保證有 2 個 word。評分時多讀、多寫一格都會讓程式當掉。
 *
 * 第一層的計算請直接呼叫大題一的 bnn_hidden()（評分時會連結你的 q1_ebnn/bnn.c）。
 */
#ifndef FIRMWARE_H
#define FIRMWARE_H

#include <stdint.h>

int fw_handle(const uint32_t *req, int n, uint32_t *resp);

#endif
