# 大題二：兩片板子平行跑 eBNN（100 分）

> 對應去年第 2 小題「用 ROS 2 跑上面那個東西，但要用兩片 ESP32 跑，有點像平行計算」。
> 今年的新東西：2-2 的封包位元欄位、2-3 的「把工作描述出去、啟動、等待、收結果」與有限資源排程。
> 題型：**修改有錯誤的韌體 (C)** ＋ **重寫協調者 (Python)** ＋ **效能優化**（吞吐量、延遲）。
> 建議時間：60 分鐘。commit 訊息以 `Q2` 開頭即觸發評分。

## 1. 系統

```text
                       ┌──> /board0/request ──> [board0：每神經元 1.0 ms] ──> /board0/response ──┐
/camera/image ──> [coordinator]                                                                  ├──> [coordinator] ──> /ebnn/prediction
   (UInt64)            └──> /board1/request ──> [board1：每神經元 2.0 ms] ──> /board1/response ──┘          (Int32)
```

- 兩片板子由 `boards.py`（已提供）模擬。板上跑的韌體就是你的 `firmware.c`，第一層的計算呼叫大題一的 `bnn_hidden()`。
- **板子規格**：board0 每個神經元 1.0 ms；board1 是舊板子，每個神經元 **2.0 ms**；每筆 request 固定再加 2.0 ms；連線單程延遲 1.0 ms；每片板子一次只處理一筆，其餘 FIFO 排隊。
- 在 Linux 上跑真的 ROS 2：`python3 boards.py 0`、`python3 boards.py 1`、`python3 coordinator.py` 各開一個終端機。

## 2. Part A：修好 `firmware.c`（35 分）

封包格式寫在 `firmware.h`：

```text
request  = [header, img_lo, img_hi]     header: bits 31..16 seq | 15..8 first | 7..0 count
response = [header（原樣送回）, bits]    bits: 神經元 first..first+count-1 的輸出，放在原本的位元位置
不合法（n != 3、count == 0、count > 32、first + count > 32）→ 回傳 -1，不寫 resp
```

| 項目 | 配分 |
|---|---:|
| header 原樣送回（含 `first >= 16`） | 10 |
| 部分神經元的輸出與位元位置 | 15 |
| 不合法請求回傳 -1 且不寫入 | 5 |
| `count = 32` 的完整範圍 | 5 |

> 韌體會連結你**大題一**的 `bnn.c`。若它的 `bnn_hidden` 還不正確，評分會改用參考解答的 `bnn.c`，並在結果裡註明。

## 3. Part B：重寫 `coordinator.py`（40 分）

| 項目 | 規格 |
|---|---|
| node | 名稱 `coordinator`，類別 `Coordinator` |
| 輸入 | `/camera/image`（`UInt64`），依到達順序給 seq = 0, 1, 2, …（16 bit） |
| 分工 | 每張影像的 32 個神經元，**每個剛好交給某一片板子算一次**（可以切開給兩片，也可以整張給一片）。協調者**不能自己算第一層**（評分時會擋） |
| 組合 | 收齊 32 個神經元後，用 `common/model.py` 的 `scores_from_hidden`、`argmax` 算第二層（第二層很便宜，協調者自己算即可） |
| 輸出 | `/ebnn/prediction`（`Int32`），**依影像順序**發布，每張一次 |

| 項目 | 配分 |
|---|---:|
| 稀疏到達：每 100 ms 一張、共 20 張，預測正確且依序 | 15 |
| 一次湧入：40 張同時到達，預測正確且依序 | 15 |
| 工作分配：每張 32 個神經元剛好算一次，兩片板子都有用到 | 10 |

## 4. Part C：效能（25 分）

正確性全部通過後才計算。全部在「模擬時間」裡量測，結果是確定的、沒有雜訊。

| 指標 | 量法 | 分級 |
|---|---|---|
| 吞吐量（15） | 40 張同時到達，最後一個預測發布的時間。加速比 = 只用 board0 的時間（40 × 34 ms）÷ 你的時間 | `>=1.49` → 15、`>=1.44` → 11、`>=1.3` → 7、`>=1.1` → 3 |
| 延遲（10） | 每 100 ms 一張時，從影像發布到預測發布的平均時間 | `<=27 ms` → 10、`<=30` → 6、`<=37` → 3 |

想一想：

- 兩片板子速度不同，對半切會怎樣？
- 一次只送一張，送出去後就在等網路回來，板子在這段時間做什麼？
- 「讓單張影像最快做完」和「讓一大批影像最快做完」是同一件事嗎？

## 5. 評分

```bash
python3 grade.py
python3 grade.py --hint                           # 卡住時：第 1 級提示（--hint 2、--hint 3 更具體）
git commit -am "Q2: pipeline + 依速度切分"
```
