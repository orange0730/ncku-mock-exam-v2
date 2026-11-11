# 04 去年的題型：eBNN、多板分工、SHA-0、CRC-32、CI 評分

去年考生分享的三個小題：(1) 用 ROS 2 跑 eBNN 推論；(2) 同一件事改用兩片 ESP32，有點像平行計算；(3) 用三片 ESP32 各跑排序、SHA-0、CRC32。評分方式是自架 GitLab，每人一個 repository，commit 訊息開頭寫題號，GitLab CI 就跑那一題。

這份資料整理這些題目需要的背景，並對照今年三份考前練習可能「換成什麼」。

---

## 1. eBNN：把神經網路變成位元運算

### 1.1 為什麼要二值化

微控制器的 RAM 以 KB 計，沒有浮點加速器也很常見。二值化神經網路（BNN）把權重與啟動值都限制在 {−1, +1}，用 1 bit 存（1 代表 +1、0 代表 −1）：

| | 一般網路 | BNN |
|---|---|---|
| 每個權重 | 32-bit float | 1 bit（省 32 倍記憶體） |
| 內積 | n 次乘加 | `popcount(XNOR(x, w))`，每 32 個一次 |
| 硬體需求 | FPU、乘法器 | AND / XOR / 移位 / popcount |

**為什麼內積 = XNOR + popcount？** 兩個 ±1 相乘：相同得 +1，不同得 −1。XNOR 正好在「相同」時為 1。所以：

```text
內積 = (相同的個數) − (不同的個數) = p − (n − p) = 2p − n，   p = popcount(XNOR(x, w))
```

這就是大題一第二層的 `2 * popcount(...) - 32`。

### 1.2 BatchNorm 摺疊成門檻

BNN 每層後面通常接 BatchNorm 再取 sign：`y = sign(γ·(dot − μ)/σ + β)`。γ > 0 時，整理之後等價於 `dot >= 某個常數`。所以推論時每個神經元只要和一個**整數門檻**比較（大題一的 `T1[j]`），完全不需要浮點。γ < 0 時不等號反向，實作上常把權重整組反相，讓它回到 `>=`。

eBNN 論文（McDanel、Teerapittayanon、Kung，2017）的重點，正是把卷積、池化、BatchNorm、sign 融合成一個步驟，並調整計算順序，讓中間結果不必全部存下來，以塞進只有幾 KB RAM 的晶片。

### 1.3 實作要點

- **打包順序要一致。** 影像、權重、隱藏層都約定好「哪一位是哪一個像素 / 神經元」。大題一起始檔把神經元放在 `31 - j` 而不是 `j`，第二層就整個對不上了。
- **popcount 的寫法**：迴圈、Kernighan、SWAR、`__builtin_popcount`（見 02 的 1.5 節）。RISC-V Zbb 有 `cpop`，ARM 有 NEON `vcnt`。
- **PIO 算 popcount**：只有遞減，所以從 `0xFFFFFFFF` 往下數，最後取反（見 02 的 3.3 節）。

---

## 2. 多板分工：平行計算的兩種切法

### 2.1 模型平行 vs 資料平行

| | 模型平行（model parallel） | 資料平行（data parallel） |
|---|---|---|
| 切什麼 | 同一張影像的神經元：板子 A 算 0..20、B 算 21..31 | 不同的影像：影像 1 給 A、影像 2 給 B |
| 好處 | **單張延遲低**（兩片一起做一張） | **吞吐量高**（每張只付一次通訊與固定成本） |
| 代價 | 每張都要付兩次 request 成本，還要等最慢的那片 | 單張影像的延遲沒有變短 |
| 合併 | 把兩邊的位元 OR 起來 | 依序號重新排序 |

大題二故意讓兩種都要：稀疏到達時比延遲，一次湧入時比吞吐量。

### 2.2 負載平衡：快慢不同的板子怎麼切

讓兩片**同時做完**。若 board0 每單位 1 ms、board1 2 ms，固定成本都是 c：

```text
c + a·1 = c + (32 − a)·2   →   a ≈ 21.3，切成 21 / 11
```

對半切（16 / 16）時，board1 要 34 ms，board0 早早做完在旁邊等，結果跟只用 board0 一樣慢。這是 **Amdahl / 最慢者決定一切**的直覺：平行化後的時間 = 最慢那一份的時間。

### 2.3 Pipeline 與序號

- **不要送一張、等一張。** 網路來回的時間裡板子是閒著的。把下一張先送出去，讓板子的佇列裡一直有工作。
- **一定要有序號。** 一旦多個請求同時在路上，回應的順序就不保證。回應要帶序號（大題二的 header 原樣送回），協調者靠它對帳，再**依原始順序**發布。
- 這和第三題「通道是有限資源」是同一個模式：記住誰在外面、回來一個就補一個。

### 2.4 在 ROS 2 上的樣子

真正的 ESP32 / RP2350 上跑的是 **micro-ROS**：板子上用 C 的 `rclc` API 建 node、publisher、subscriber，透過序列埠或 Wi-Fi 連到電腦上的 **micro-ROS agent**，agent 再把它們接進 ROS 2 網路。所以從 `ros2 node list` 看，每片板子就是一個 node：

```text
[ESP32 / RP2350：rclc node] ──UART / UDP──> [micro-ROS agent] ──DDS──> ROS 2 網路（你的協調者 node）
```

本模擬考的 `boards.py` 扮演「板子 + agent」，`/boardN/request`、`/boardN/response` 就是板子上 subscriber / publisher 的 topic。除錯時一樣用 `ros2 node list`、`ros2 topic info`、`ros2 topic echo`。

---

## 3. SHA-0

### 3.1 結構（Merkle–Damgård）

1. **填充（padding）**：訊息後面加一個 `0x80`，補 0 直到長度 ≡ 56 (mod 64)，最後 8 bytes 放「原始長度的**位元數**」，**big-endian**。剩餘部分已經 ≥ 56 bytes 時，要多補一整個區塊。這是最常錯的邊界：55、56、63、64 bytes。
2. **每個 64-byte 區塊**：拆成 16 個 big-endian 的 32-bit 字 `W[0..15]`，擴展成 80 個：

   ```text
   SHA-0：W[t] = W[t-3] ^ W[t-8] ^ W[t-14] ^ W[t-16]
   SHA-1：W[t] = ROTL1( W[t-3] ^ W[t-8] ^ W[t-14] ^ W[t-16] )   ← 唯一的差別
   ```

3. **80 輪**，四段各 20 輪：

   | 輪 | f(b, c, d) | K |
   |---|---|---|
   | 0–19 | `(b & c) \| (~b & d)`（choose） | `0x5A827999` |
   | 20–39 | `b ^ c ^ d`（parity） | `0x6ED9EBA1` |
   | 40–59 | `(b & c) \| (b & d) \| (c & d)`（majority） | `0x8F1BBCDC` |
   | 60–79 | `b ^ c ^ d`（parity） | `0xCA62C1D6` |

   每輪：`tmp = ROTL5(a) + f + e + K + W[t]`；`e = d; d = c; c = ROTL30(b); b = a; a = tmp`。
4. 每個區塊做完，把 a..e 加回 h0..h4；最後 h0..h4 以 big-endian 輸出，共 20 bytes。

測試向量：`SHA-0("abc") = 0164b8a914cd2a5e74c4f7ff082c4d97f1edf880`。若你算出 `a9993e36…`，那是 SHA-1。

### 3.2 會用到的位元工具

`ROTL`（02 的 1.4 節，注意移位量 0 / 32 的 UB）、big-endian 讀寫（`load_be32`，注意 `char` 的符號延伸）。這就是今年 2-2 練習「從位元流中取出固定寬度欄位」與「把欄位填入固定位置」的實際應用。

---

## 4. CRC-32

### 4.1 本質

把資料看成 GF(2) 上的多項式，除以生成多項式 `0x04C11DB7`，取餘數。GF(2) 的加減法都是 XOR，所以只需要移位與 XOR。

### 4.2 「標準 CRC-32」的五個參數

| 參數 | 值 | 意義 |
|---|---|---|
| poly | `0x04C11DB7` | 生成多項式（反射寫法 `0xEDB88320`） |
| init | `0xFFFFFFFF` | 暫存器初值 |
| refin | true | 每個輸入 byte 先位元反轉（LSB 先處理） |
| refout | true | 結果位元反轉 |
| xorout | `0xFFFFFFFF` | 最後再 XOR |

check value：`CRC32("123456789") = 0xCBF43926`。寫完先測這個。

### 4.3 三種軟體寫法

```c
// 1) 逐位元（反射版：右移、用 0xEDB88320）
crc = 0xFFFFFFFF;
for each byte b: { crc ^= b; repeat 8: crc = (crc & 1) ? (crc >> 1) ^ 0xEDB88320 : crc >> 1; }
return ~crc;

// 2) 查表：先算好 256 項，每個 byte 一次查表
crc = (crc >> 8) ^ table[(crc ^ b) & 0xFF];

// 3) slicing-by-4 / by-8：多張表，一次處理 4 / 8 bytes，更快但表更大（4 KB / 8 KB）
```

在 MCU 上，表格要放 flash 還是 RAM、要不要用 slicing，都是空間與時間的權衡。

### 4.4 用 DMA 的 sniffer 算（今年練習暗示的方向）

RP2350 的 DMA 有一個 **sniffer**：被指定的通道在搬資料時，順便把資料餵進 CRC 計算器。CPU 只要描述工作、啟動、等待，再讀累加器（Pico SDK：`dma_sniffer_enable`、`dma_sniffer_set_data_accumulator`、`dma_sniffer_get_data_accumulator`、`dma_sniffer_set_output_reverse_enabled`、`dma_sniffer_set_output_invert_enabled`）。

硬體算的是「不反射」的 CRC-32，要湊成標準版：

1. 選「資料位元反轉」的模式（對應 refin）
2. 累加器初值 `0xFFFFFFFF`（init）
3. 讀出時位元反轉（refout）再反相（xorout）

只要「搬」就能算，所以目的地可以是一個**不前進**的暫存變數（`dst_increment = false`）。這就是 2-3「位址要不要前進是描述的一部分」的實際用途。

---

## 5. MCU 上的排序

| 方法 | 時間 | 額外空間 | 備註 |
|---|---|---|---|
| 插入排序 | O(n²) | O(1) | n 很小（< 32）時最快；常用來收尾 |
| quicksort | 平均 O(n log n)，最差 O(n²) | O(log n) 堆疊 | 堆疊在 MCU 上很珍貴，遞迴要小心 |
| heapsort | O(n log n) | O(1) | 穩定的時間上界，適合記憶體緊的時候 |
| merge sort | O(n log n) | O(n) | 穩定，但要一倍空間 |
| radix sort（LSD，每輪 8 位元） | O(n)，4 輪 | O(n) + 256 計數 | 32-bit 整數最快；不需要比較函式 |

C 標準函式庫的 `qsort` 每次比較都要呼叫一次函式指標，所以通常比手寫的特化版本慢。大題三的效率分數就是在比這個。

---

## 6. GitLab CI 評分流程

```text
你 git commit -m "Q2: …" → git push → GitLab 讀 .gitlab-ci.yml
   → rules 比對 $CI_COMMIT_MESSAGE 開頭 → 建立 grade_q2 job → runner 跑評分 → 看 pipeline 頁面的結果
```

考場上的實用習慣：

- **題號寫在 commit 訊息的最開頭**，格式照考場規定（`Q2: …`、`[Q2] …`），寫在中間通常不算。
- **小步提交。** 每修好一件事就 commit 一次，pipeline 結果會告訴你分數有沒有往上；分數掉了，`git diff HEAD~1` 一眼就看得出改了什麼。
- **先在本機跑過評分再 push**（如果考場給了評分腳本），不要拿 CI 當編譯器用：pipeline 要排隊。
- `git log --oneline` 是你的進度表；`git stash`、`git checkout -- 檔案` 是後悔藥。

本模擬考用 `ci/run_ci.py` + git post-commit hook 模擬這個流程。`.gitlab-ci.yml` 是參考用的設定檔，讀懂它就知道考場的 CI 在做什麼。

---

## 7. 自我檢查

<details><summary>1. 32 個 ±1 的內積，XNOR 後 popcount 得到 20，內積是多少？</summary>
2 × 20 − 32 = 8。
</details>

<details><summary>2. board0 每神經元 1 ms、board1 3 ms、固定成本相同，32 個神經元怎麼切最好？</summary>
a = 3(32 − a) → a = 24，切成 24 / 8（兩邊都約 24 ms）。
</details>

<details><summary>3. 訊息剛好 56 bytes，SHA-0 填充後有幾個區塊？</summary>
2 個。56 + 1（0x80）已經超過 56，長度欄位放不下，要多補一個區塊：56 + 1 + 63 個 0 + 8 = 128 bytes。
</details>

<details><summary>4. CRC-32 的 init 和 xorout 都是 0xFFFFFFFF，空字串的 CRC 是多少？</summary>
0。暫存器沒有被任何資料改變，0xFFFFFFFF XOR 0xFFFFFFFF = 0。
</details>

<details><summary>5. 為什麼大題二一次湧入時，「整張給一片板子」比「每張都切開」快？</summary>
每筆 request 都有固定成本（2 ms）。切開時每張付兩次，整張給一片只付一次；積壓時兩片都不會閒著，所以省下來的固定成本直接變成吞吐量。
</details>
