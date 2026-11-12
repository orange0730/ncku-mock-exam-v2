# 大題三：三片板子跑排序 / SHA-0 / CRC-32（100 分）

> 對應去年第 3 小題「用三片 ESP32 跑一堆演算法：排序、SHA-0、CRC32，三個要在三片不同的板子跑」。
> 今年的新東西：2-3 的搬運引擎，以及 PDF 特別提到的「資料搬運／**校驗**周邊」：DMA 的 sniffer 可以在搬資料的同時算 CRC。
> 題型：**修改有錯誤的程式碼**（四個演算法都有錯）＋**效率優化**（排序、CRC 速度）＋**平行與 pipeline 的協調者**。
> 建議時間：60 分鐘。commit 訊息以 `Q3` 開頭即觸發評分。

## 1. 系統

```text
                        ┌──> board_sort ──┐
/jobs/request ──> [dispatcher] ──> board_sha0 ──> [dispatcher] ──> /jobs/result
 (UInt8MultiArray)      └──> board_crc  ──┘                          (String)
```

每片板子**只會跑一種演算法**（`boards.py` 已提供）。訊息格式：

```text
/jobs/request、/board_*/request ：[job id：4 bytes little-endian] + payload
/board_*/response               ：[job id：4 bytes little-endian] + 結果
    board_sort：payload 視為 little-endian uint32 陣列，回傳排序後的陣列（同格式）
    board_sha0：20 bytes 的 SHA-0 摘要
    board_crc ：4 bytes 的 CRC-32（little-endian），板子上用 crc32_dma 算
```

板子速度：每筆 request 1 ms，再加上 sort `n·log2(n) × 1 µs`、sha0 每 64-byte 區塊 0.15 ms、crc 每 byte 2 µs；連線單程 1 ms；各自 FIFO。

## 2. Part A：修好 `algos.c`（55 分）

| 函式 | 規格 | 配分 |
|---|---|---:|
| `sort_u32` | 由小到大，n 可能是 0 | 正確 8、效率 7（100 萬筆，與 `qsort` 比：`<=0.8` 倍時間 → 7、`<=1.5` → 5、`<=4` → 2） |
| `sha0` | FIPS 180 原始版（1993）。與 SHA-1 只差訊息排程少一個左旋 | 12（含 55 / 56 / 63 / 64 bytes 等填充邊界） |
| `crc32_sw` | 標準 CRC-32（`"123456789"` → `cbf43926`） | 正確 6、效率 6（4 MB，與逐位元版比：`>=3` 倍快 → 6、`>=1.8` → 3） |
| `crc32_dma` | 同樣的 CRC-32，但要用搬運引擎的 **sniffer** 算（API 見 `engine.h`） | 正確 8（含未對齊位址、0 bytes）、確實用 sniffer 並歸還通道、關閉 sniffer 4 |
| 全部 | `-Wall -Wextra` 零警告 | 4 |

sniffer 的提示：sniffer 算的是「不反射、MSB-first」的 CRC-32，但標準 CRC-32 是「反射」的。`engine.h` 提供的選項（資料位元反轉的模式、累加器初值、讀出時反轉 / 反相）剛好夠你把它湊成標準版。這正是 RP2350 上用 DMA 算 CRC-32 要做的設定。

## 3. Part B：重寫 `dispatcher.py`（30 分）

| 項目 | 規格 |
|---|---|
| node | 名稱 `dispatcher`，類別 `Dispatcher` |
| 輸入 | `/jobs/request`（`UInt8MultiArray`）：4 bytes job id（little-endian）＋ payload（長度是 4 的倍數，至少 4） |
| 分工 | 每個工作都要送到**三片**板子，各自算自己的那一種；dispatcher 不能自己算（評分會檢查：三片都收到、而且三片都回覆之後才發布） |
| 輸出 | `/jobs/result`（`String`），**依工作到達順序**，每個工作一行：<br>`id=<十進位> min=<十進位> median=<十進位> max=<十進位> crc32=<8 位小寫 hex> sha0=<40 位小寫 hex>`<br>min / median / max 取自排序後的陣列，median = 排序後 index `n // 2` 的元素 |

| 項目 | 配分 |
|---|---:|
| 稀疏到達：10 個不同大小的工作，字串完全正確且依序 | 12 |
| 一次湧入：20 個 4 KB 工作，正確且依序 | 10 |
| 分工檢查 | 8 |

## 4. Part C：效能（15 分）

20 個 4 KB 工作同時到達。加速比 = 「三個演算法輪流做」的時間 ÷ 你的完成時間。`>=2.7` → 15、`>=2.2` → 10、`>=1.5` → 5。

## 5. 評分

```bash
python3 grade.py
python3 grade.py --hint                           # 卡住時：第 1 級提示（--hint 2、--hint 3 更具體）
git commit -am "Q3: radix sort + 查表 CRC"
```
