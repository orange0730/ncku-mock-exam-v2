# 03 並行、鎖與 DMA（搬運引擎）

對應：官方練習 `demo/section2-3`、參考文獻 [2] [3] [5]、v1 第三題、v2 大題三（DMA sniffer）。

---

## 1. Race condition：為什麼 `counter++` 會少

`counter++` 在機器上是三步：

```text
執行緒 A                 執行緒 B
load  r = counter (=5)
                        load  r = counter (=5)
add   r = 6
                        add   r = 6
store counter = 6
                        store counter = 6     ← A 的那次更新消失了
```

- 只要「讀 → 改 → 寫」中間可能被插隊，就會**遺失更新（lost update）**。
- `volatile` **不能**解決這件事。它只保證每次真的去讀寫記憶體，不保證三步不可分割。
- 單核心機器上很少發生（兩個執行緒沒有真的同時跑），但「很少」不是「不會」。官方 demo 也特別提醒這一點。
- 共用資料只要**至少一方在寫**，所有存取都要同步（鎖、原子操作，或用 join 隔開）。

## 2. 臨界區與鎖

**臨界區（critical section）**：存取共用資料、必須「一次只有一個執行緒在裡面」的那段程式。

OSTEP Ch.28 [3] 評估一把鎖的三個標準：

1. **正確（mutual exclusion）**：同一時間最多一個執行緒持有。
2. **公平（fairness）**：等待的執行緒最終拿得到，不會餓死。
3. **效能（performance）**：沒有競爭時的成本、多執行緒競爭時的成本、多核心時的成本。

鎖怎麼做出來的（OSTEP 的脈絡）：關中斷（單核心才有用）→ 純讀寫旗標（錯，因為檢查與設定之間會被插隊）→ 硬體原子指令 **test-and-set**、**compare-and-swap**、**fetch-and-add**（ticket lock，公平）→ 自旋太浪費時改成 yield 或睡眠（futex、two-phase lock）。

### 2.1 mutex vs spinlock

| | `pthread_mutex_t` | `pthread_spinlock_t`（[5]） |
|---|---|---|
| 拿不到時 | 進入睡眠，讓出 CPU | **原地打轉（busy-wait）**直到拿到 |
| 適合 | 臨界區可能很長、執行緒可能比核心多 | 臨界區**極短**、每條執行緒都有自己的核心 |
| 風險 | 切換有成本 | 持有者被排程走時，其他人白白燒 CPU；可能造成 priority inversion |
| 同一執行緒重複上鎖 | 依類型而定 | **未定義**（可能直接死結） |
| 試著拿 | `pthread_mutex_trylock` → `EBUSY` | `pthread_spin_trylock` → `EBUSY` |

硬體上的「spinlock」：RP2350 有硬體 spinlock 給兩顆核心之間使用（SDK 的 `hardware_sync`），保護的正是這種很短的共用資料讀寫。

### 2.2 pthread 速查

```c
#include <pthread.h>

pthread_t th[N];
pthread_create(&th[i], NULL, worker, &args[i]);   // worker: void *worker(void *arg)
pthread_join(th[i], NULL);                        // 等它結束；join 之後它寫的資料你都看得到

pthread_mutex_t mu = PTHREAD_MUTEX_INITIALIZER;
pthread_mutex_lock(&mu);   /* 臨界區 */   pthread_mutex_unlock(&mu);

pthread_spinlock_t sl;
pthread_spin_init(&sl, PTHREAD_PROCESS_PRIVATE);
pthread_spin_lock(&sl);    /* 臨界區 */   pthread_spin_unlock(&sl);
pthread_spin_destroy(&sl);
```

常見錯誤：傳給每條執行緒的參數用同一個區域變數的位址（迴圈跑完值都一樣）；忘了 join（main 結束時執行緒還在跑）；`gcc` 忘了 `-pthread`。

## 3. 鎖要抓得越短越好（官方 demo 第 3 行）

```c
// 差：耗時計算也在鎖裡，等於退回單執行緒
lock(); h = heavy(x); hist[h & 15]++; unlock();

// 好：只鎖共用資料那一行
h = heavy(x);
lock(); hist[h & 15]++; unlock();

// 更好：每條執行緒先自己累計，最後合併一次（鎖的次數從 n 降到「執行緒數」）
uint64_t local[16] = {0};
for (...) local[heavy(x) & 15]++;
lock(); for (b = 0; b < 16; b++) hist[b] += local[b]; unlock();
```

第三種寫法的觀念是**減少共享**：能不共享就不共享，必須共享時才同步。這也避免了 *false sharing*（不同執行緒頻繁寫同一條 cache line）。

**切工作的公式**：把 n 筆分給 T 條執行緒，第 t 條負責 `[n*t/T, n*(t+1)/T)`。這樣餘數會平均分散，最後一段剛好到 n，不會漏掉最後幾筆（`chunk = n / T` 的寫法會漏掉餘數）。T > n 時有些執行緒會分到空區間，最好直接少開幾條。

## 4. 死結（deadlock）速記

四個條件同時成立才會死結：互斥、持有並等待、不可搶奪、循環等待。最實用的預防方法是**所有人都用同一個順序拿多把鎖**。另一個常見的死結來源：持有鎖時去等某件事（join、等待 I/O、等另一把鎖），而那件事又需要這把鎖。

---

## 5. DMA：把搬運「描述」出去

### 5.1 四拍節奏

```text
描述 (configure) → 啟動 (start) → 等待 (wait / busy) → 取用結果
```

搬運引擎（DMA）是 CPU 以外的獨立單元。CPU 不寫複製迴圈，而是描述「從哪讀、寫到哪、幾筆、每筆多大、位址要不要前進」，啟動後就可以去做別的事。真的硬體消耗的是**匯流排頻寬**，不是 CPU 指令。demo 用執行緒模擬，所以仍然占一顆核心，這是 demo 無法呈現的地方。

### 5.2 對照表：demo / 模擬考 ↔ Pico SDK（[2]）

| 概念 | demo / 第三題 `engine.h` | Pico SDK `hardware_dma` |
|---|---|---|
| 取得通道 | `engine_claim()`，沒有就回傳 -1 | `dma_claim_unused_channel(bool required)`：required = false 時沒有就回傳 -1 |
| 預設設定 | `engine_job_t job = {...}` | `dma_channel_config c = dma_channel_get_default_config(ch);` |
| 每筆大小 | `.size = XFER_8 / 16 / 32` | `channel_config_set_transfer_data_size(&c, DMA_SIZE_8 / 16 / 32);` |
| 來源位址是否前進 | `.src_increment` | `channel_config_set_read_increment(&c, true);` |
| 目的位址是否前進 | `.dst_increment` | `channel_config_set_write_increment(&c, true);` |
| 幾筆 | `.count`（**筆數**） | `dma_channel_configure(ch, &c, write_addr, read_addr, transfer_count, trigger)` 的 `transfer_count`（**筆數**） |
| 啟動 | `engine_start(ch)` | `trigger = true`，或之後 `dma_channel_start(ch)` |
| 還在跑嗎 | `engine_busy(ch)` | `dma_channel_is_busy(ch)` |
| 等它完成 | `engine_wait(ch)` | `dma_channel_wait_for_finish_blocking(ch)` |
| 歸還通道 | `engine_release(ch)` | `dma_channel_unclaim(ch)` |
| 跟周邊同步速度 | （demo 沒有） | `channel_config_set_dreq(&c, pio_get_dreq(pio, sm, true));` |

注意 `dma_channel_configure` 的參數順序是**寫入位址在前、讀取位址在後**，和 `memcpy(dst, src, n)` 一樣。demo 的 engine 也是這個結構。

### 5.3 四個要記住的點（官方 2-3）與延伸

1. **`count` 是筆數不是 bytes。** 把 bytes 填進去，引擎會忠實地搬 2 倍或 4 倍的量，寫爆緩衝區，而且**不會抱怨**（`make mistake`）。
2. **位址前進與否是描述的一部分。** 兩邊都前進 = 複製；來源不前進 = 填值（memset）；目的不前進 = 一直寫同一個位址（例如寫進 PIO 的 TX FIFO）。
3. **每筆只能 1 / 2 / 4 bytes，位址要對齊。** 筆數 = bytes ÷ 每筆大小，所以每筆越大越省；但這個大小必須能同時整除 `src` 位址、`dst` 位址與長度。（想想看：怎麼用一個位元運算同時檢查三個數的低 2 位？）

   進一步：如果 `src` 與 `dst` 的「錯位量」相同（`(src ^ dst) & 3 == 0`），可以把頭尾零頭用小單位搬、中間用 4 bytes 搬。
4. **通道是有限資源。** 用之前 claim、用完 release。忘了 release 的話，第五次 claim 就拿不到；拿到 -1 卻直接拿去用，程式就會出錯。

### 5.4 有限資源排程：比通道多的工作怎麼派

```text
while 還有工作:
    ch = claim()
    while ch == -1:            # 通道滿了
        等「最早開始」的那個完成、release 它
        ch = claim()
    configure + start          # 不要在這裡 wait！
    記下 ch（FIFO 佇列）
最後把佇列裡剩下的全部 wait + release
```

重點是**不要每派一個就馬上等它**（那樣並行度永遠是 1，等於沒用 DMA），也不要一次 claim 超過上限。這和執行緒池、連線池、檔案描述子是同一個模式。

### 5.5 DMA × PIO

真實系統裡常把兩者接起來：DMA 以 PIO 的 TX FIFO 為目的地（`write_increment = false`），用 DREQ 讓 DMA 只在 FIFO 有空位時才送下一筆。CPU 只要描述一次，資料就源源不絕地流進 PIO，PIO 再以精確時序把位元打到腳位上。考場若有開發板，第二題與第三題的概念可能會在這裡會合。

---

## 6. 官方「想一想」參考答案

1. **critical section 範例改成只鎖讀取、不鎖寫回，會怎樣？**
   一樣會遺失更新。A 在鎖內讀到 5、解鎖，B 也在鎖內讀到 5、解鎖，兩人都寫回 6。鎖必須涵蓋整個「讀 → 改 → 寫」，否則等於沒鎖。
2. **四個通道都被占用，第五個搬運請求怎麼辦？**
   幾種策略：(a) 等某個通道完成並歸還再派（阻塞等待，第三題 B 的做法）；(b) 立刻回報失敗（-1）讓呼叫者決定（第三題 A 的做法、SDK `required = false`）；(c) 排進佇列，有通道歸還時再派；(d) 退回由 CPU 自己搬。這和所有「使用前取得、用完歸還」的有限資源一樣：執行緒池、資料庫連線池、檔案描述子、記憶體。共同的紀律是：**一定要歸還**，取得失敗要處理，等待時不要握著別的資源（避免死結）。

## 7. 自我檢查

<details><summary>1. 為什麼 <code>pthread_join</code> 之後，main 讀執行緒寫的區域陣列不需要鎖？</summary>
join 建立了 happens-before 關係：執行緒結束前的所有寫入，對 join 返回後的呼叫者都可見，而且那之後不再有並行的寫入。
</details>

<details><summary>2. 搬 1000 bytes，src 位址 % 4 == 2，dst 位址 % 4 == 2。單一工作最少幾筆？拆成多個工作呢？</summary>
單一工作：三者 OR 起來低 2 位是 2，最大合法大小是 2 bytes，500 筆。拆開：頭 2 bytes 用 1 筆 16-bit 搬，對齊到 4 之後 996 bytes 用 249 筆 32-bit 搬，尾端 2 bytes 再 1 筆 16-bit，共 251 筆。
</details>

<details><summary>3. 每條執行緒 n/T 筆、heavy 很慢、每筆都上鎖但 heavy 在鎖外。鎖會成為瓶頸嗎？</summary>
heavy 很慢時，鎖的競爭不嚴重，平行效果還不錯；但 heavy 很快時（第三題壓力測試的情況），鎖的成本占了主要部分，各執行緒輪流排隊，甚至比單執行緒還慢。所以「先本地累計、最後合併」在兩種情況都好。
</details>
