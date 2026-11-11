# 大題一：用 ROS 2 跑 eBNN 推論（100 分）

> 對應去年第 1 小題「用 ROS 2 跑 eBNN 推論」，加上今年練習的新東西：2-2 的位元運算與 PIO、2-1 的 ROS 2。
> 題型：**修改有錯誤的程式碼**（C 核心、PIO、ROS node 三份都有錯）＋**效率優化**（PIO 週期數）。
> 建議時間：60 分鐘。commit 訊息以 `Q1` 開頭即觸發評分。

## 1. 背景：eBNN 是什麼

eBNN（embedded Binarized Neural Network）是為**記憶體極小的微控制器**設計的二值化神經網路：權重和中間結果都只有 1 bit。乘加運算因此變成位元運算：

```text
一般神經元：  Σ x_i · w_i                      （浮點乘加，很貴）
二值神經元：  popcount( XNOR(x, w) )           （一條 XOR、一次反相、一次數 1）
```

把 BatchNorm 與 sign 函數「摺疊」成一個整數門檻，第一層每個神經元只剩一行：`matches >= T`。

## 2. 模型規格（`common/model.h` 已提供權重）

- **輸入**：8×8 黑白影像，打包成 64-bit 整數，像素 (r, c) 在 bit `r*8 + c`。傳給 C 時 `img[0]` = 低 32 位（第 0..3 列），`img[1]` = 高 32 位（第 4..7 列）。
- **第一層**：32 個神經元。神經元 j：`matches_j = popcount(~(img XOR W1[j]))`（64 位元裡相同的位數），`matches_j >= T1[j]` 時輸出 1。32 個輸出打包成 `hidden`，**bit j = 神經元 j**。
- **第二層**：10 個輸出。`score_k = 2 * popcount(~(hidden XOR W2[k])) - 32`（二值內積：相同 +1、不同 −1）。
- **預測**：分數最大的 k；**同分取 index 最小者**。

這個模型是手工設計的：神經元 3d..3d+2 是數字 d 的模板，所以它真的能辨識加了雜訊的數字（約 97%）。

## 3. 三個部分

### Part A：修好 `bnn.c`（45 分）

`bnn.h` 有四個函式的規格。`bnn.c` 編譯得過、也跑得出數字，但辨識結果和參考模型對不起來。

| 項目 | 配分 |
|---|---:|
| `popcount32`（含第 31 位、全 1） | 8 |
| `bnn_hidden`：XNOR、門檻、位元位置 | 15 |
| `bnn_scores`：`2p − 32` | 8 |
| `bnn_infer`：預測與分數（含同分取最小 index） | 8 |
| 1000 張含雜訊數字，每張都與參考模型一致 | 4 |
| `-Wall -Wextra` 零警告 | 2 |

### Part B：修正並優化 `xnorpop.pio`（25 分）

在真的板子上，可以把 popcount 交給 PIO。CPU 先算 `d = a XOR w`（一條指令）送進 TX FIFO，PIO 對每個 `d` 輸出 **d 裡 0 的個數**（= a、w 相同的位數）。

`common/pio_sim.py` 是依照 RP2350 PIO 真實語意寫的模擬器（只有 X / Y、沒有加法、`jmp x--` 先檢查後遞減）：

```bash
python3 ../common/pio_sim.py xnorpop.pio 0x0 0xFFFFFFFF 0xF0      # 看輸出與週期數
python3 ../common/pio_sim.py xnorpop.pio 0x5 --trace               # 逐 tick 追蹤
```

| 項目 | 配分 |
|---|---:|
| edge_values（fast）/ random_256（slow_rx）/ random_512（bursty） | 5 + 5 + 5 |
| 效率：週期數 / word（`<=106` → 6、`<=125` → 4、`<=170` → 2） | 6 |
| 效率：指令數（`<=9` → 4、`<=16` → 2、`<=32` → 1） | 4 |

效率分數要三組正確性都通過才給。提示：「數 0」比「數 1」難優化。想想為什麼，再想想有沒有辦法把問題變成「數 1」。

### Part C：修好 `ebnn_node.py`（30 分）

| 項目 | 規格 |
|---|---|
| node | 名稱 `ebnn`，類別 `EbnnNode`（建構子不帶參數） |
| 訂閱 | `/camera/image`，`std_msgs/msg/UInt64` |
| 發布 | `/ebnn/scores`（`std_msgs/msg/Int32MultiArray`，10 個分數），然後 `/ebnn/prediction`（`std_msgs/msg/Int32`） |
| 順序 | 每張影像：**先 scores 再 prediction**，各一次 |

`bnn_lib.py`（已提供）會把你的 `bnn.c` 編譯成共享函式庫並載入。注意它回傳的 `scores` 是 **ctypes 陣列**。評分 node 時會改用 Python 參考模型（`BNN_BACKEND=ref`），所以 Part C 的分數不受 Part A 影響。

| 項目 | 配分 |
|---|---:|
| node 名稱 / 訂閱型別 / 發布型別 | 2 + 3 + 3 |
| 30 張影像的分數與預測正確 | 12 |
| 每張先 scores 後 prediction，各一次 | 5 |
| 邊界影像（全 0、全 1、只有最高位） | 5 |

## 4. 評分

```bash
python3 grade.py                                  # 本題
git commit -am "Q1: 修好 popcount"                # 或：commit 觸發 CI（先裝 hook，見根目錄 README）
```
