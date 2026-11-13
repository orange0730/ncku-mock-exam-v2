# 考場速查筆記（索引）

整理自成大給的考前練習（`demo/` 三個章節與 README、演練試題 PDF）與其中所有外部連結，加上去年題型分析與今年預測。考場上用 **Ctrl+F** 搜關鍵字最快。

| 檔案 | 內容 |
|---|---|
| [00_環境與Docker.md](00_環境與Docker.md) | demo 專案結構、Docker 指令、Dockerfile、安裝、Linux / git 常用指令 |
| [2-1_ROS2.md](2-1_ROS2.md) | ROS 2 概念、CLI 完整速查（list / info / echo / hz / bw / find / pub 選項與 YAML）、官方練習逐步預期輸出、rclpy 範本、訊息型別規則、package / colcon、除錯流程、想一想 |
| [2-2_位元運算_RISC-V_PIO.md](2-2_位元運算_RISC-V_PIO.md) | demo_asm.c 輸出、C 運算子優先順序完整表、UB 與整數提升、位元配方、bitlab.c；RISC-V 暫存器 / 格式 / RV32I 全表 / 虛擬指令 / M / A / Zbb / Zbs / Zba / Zbkb / 組語範例；PIO 全章（指令語意、directive、autopull 虛擬碼、SDK API、範例） |
| [2-3_臨界區_DMA.md](2-3_臨界區_DMA.md) | critical section demo、pthread / spinlock API（含 man page 錯誤碼）、平行範例 parlab.c、OSTEP Ch.28 全章、RP2350 spinlock / multicore、transfer engine、RP2350 DMA datasheet 重點、Pico SDK DMA API、sniffer CRC、DMA 餵 PIO、想一想 |
| [3_去年題型與今年預測.md](3_去年題型與今年預測.md) | 去年三題的實際做法（micro-ROS 韌體骨架、協調者、dispatcher）、今年推測、雙核心、SHA-256 硬體、考場 SOP |
| [A_演算法範例.md](A_演算法範例.md) | 測試向量、CRC-32、SHA-0 / SHA-1、排序（插入 / quick / radix）、二值神經網路層、algolab.c、Python 對照 |

## 我想找…

| 想找 | 去哪 |
|---|---|
| ros2 某個指令怎麼用、輸出長怎樣 | 2-1 §3 |
| topic 收不到資料 | 2-1 §8 |
| rclpy 範本（訂閱 → 處理 → 發布） | 2-1 §5.2 |
| `Float32` / MultiArray 塞值出錯 | 2-1 §6 |
| `&` 和 `==` 誰先算 | 2-2 A2 |
| 取欄位、反轉、popcount、rotl、大小端 | 2-2 A4、A5 |
| RISC-V 某指令意思、`li` 怎麼展開、ABI | 2-2 B1–B4 |
| `cpop`、`xnor`、`rev8`、`amoswap`、`lr/sc` | 2-2 B5 |
| PIO `jmp x--`、`!osre`、`mov ::`、autopull | 2-2 C3、C5 |
| PIO 程式怎麼載入、`sm_config_set_out_shift` 參數 | 2-2 C6 |
| PIO popcount / 數 0 / 拆 byte 範例 | 2-2 C7 |
| race condition、鎖要短、本地累計 | 2-3 §2、§4 |
| spin_lock 的錯誤碼、mutex vs spinlock | 2-3 §3 |
| test-and-set、CAS、LL/SC、ticket lock、futex | 2-3 §5 |
| RP2350 雙核心、FIFO、硬體 spinlock | 2-3 §6、3 §4.5 |
| DMA `count` 單位、`dma_channel_configure` 參數順序 | 2-3 §7–§9 |
| DMA 算 CRC（sniffer） | 2-3 §10 |
| 板子怎麼接 ROS 2（micro-ROS、agent） | 3 §2 |
| eBNN 推論怎麼算 | 3 §3、A §5 |
| 兩片板子怎麼切工作、協調者程式 | 3 §4 |
| 三片板子 / dispatcher / 排序 SHA CRC | 3 §5、A |
| SHA-256 硬體 | 3 §6.2 |
| CRC / SHA 的標準答案（測試向量） | A §1 |

## 驗證狀態

- 標 `// file:` 的 C 程式（`bitlab.c`、`algolab.c`、`parlab.c`）與 Python 程式（`template_node.py`、`coordinator.py`、`dispatcher.py`、`ebnn_pc_node.py` 等）都在樹莓派上實際執行驗證過；ROS 程式用 rclpy 替身與模擬考評分程式驗證。
- PIO 範例用 `common/pio_sim.py` 驗證過（需要腳位的除外）。
- 需要 Pico SDK / micro-ROS 函式庫的程式（標 ⚠）沒有實機驗證；API 名稱已對照官方 SDK 標頭與 datasheet。
- 去年題型與今年預測是推測，**以考場給的 repository 為準**。
