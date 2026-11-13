# 成大資工特殊選才 上機考 模擬試題 v2（去年題型 × 今年新內容）

依據**去年考生分享的題型**（ROS 2 + eBNN、兩片板子平行、三片板子跑排序 / SHA-0 / CRC32、GitLab CI 評分）與**今年的考前練習**（2-1 ROS 2、2-2 位元運算與 RP2350 PIO、2-3 臨界區與搬運引擎）出的模擬考。

三個大題各 100 分，**總分 300**。每題都有自動評分，分數由多個面向加總：正確性、邊界情況、效率（PIO 週期、排序與 CRC 速度）、平行效能（吞吐量、延遲）、資源管理、分工規則。

> 第一版模擬考（v1）在 [ncku-mock-exam-v1](https://github.com/orange0730/ncku-mock-exam-v1)，題型照今年三份練習各出一題。v2 比較像去年的實際考法，兩份可以都做。

## 先讀這個

0. **考場速查筆記**：[`notes/`](notes/README.md)（demo 三章節 + 所有外部連結 + 去年題型做法與今年預測 + 範例程式）
1. **考前先讀** [`reading/`](reading/00_總覽與讀書計畫.md)，第 04 份是去年題型的背景，第 05 份是[除錯檢查清單](reading/05_除錯檢查清單.md)
2. 照下面「設定」把 repo 和 CI hook 裝好
3. 計時 **3 小時**寫三個大題，每修好一件事就 commit 一次，讓 CI 告訴你分數
4. 卡住時用 `--hint` 要分級提示（見下方），**不要問 AI**，練的就是自己找錯的能力
5. 最後才看 [`solutions/解說.md`](solutions/解說.md)

## 三個大題

| 大題 | 資料夾 | 對應去年 | 今年新東西 | 你要改的檔案 |
|---|---|---|---|---|
| 一 eBNN 推論 | [`q1_ebnn/`](q1_ebnn/README.md) | ROS 2 跑 eBNN | XNOR-popcount 用 PIO 做 | `bnn.c`、`xnorpop.pio`、`ebnn_node.py` |
| 二 兩片板子平行 | [`q2_parallel/`](q2_parallel/README.md) | 兩片 ESP32 | 封包位元欄位、快慢板子的負載平衡、pipeline | `firmware.c`、`coordinator.py` |
| 三 排序 / SHA-0 / CRC-32 | [`q3_algos/`](q3_algos/README.md) | 三片板子各跑一種 | DMA sniffer 算 CRC、與 qsort / 逐位元 CRC 比速度 | `algos.c`、`dispatcher.py` |

每個要改的檔案都**故意寫錯**：能編譯、能執行，但起始分數每題都在 10 分以下。

## 設定（在 Linux / 樹莓派上）

需要 Python 3.9+、gcc、git。從 GitHub 取得：`git clone https://github.com/orange0730/ncku-mock-exam-v2.git ncku_mock_exam_v2`。**不需要安裝 ROS 2**：評分用 `common/fake_ros/` 裡的 rclpy 替身，它會擋下真實 rclpy 也會擋的錯誤（型別錯、topic 名稱錯）。

```bash
cd ncku_mock_exam_v2
git init
git add -A
git commit -m "init: 起始檔"
python3 ci/install_hook.py
```

## 用 commit 觸發評分（模擬考場的 GitLab CI）

commit 訊息**開頭**寫題號，post-commit hook 就會跑那一題的評分：

```bash
git commit -am "Q1: 修好 popcount32 的第 31 位"
git commit -am "[Q3] radix sort"
git commit -am "Q1 Q2 一起交"
git commit -am "ALL: 全部評一次"
git commit -am "整理註解"          # 沒有題號：不評分
```

輸出類似：

```text
┌─ CI pipeline  commit 3f2a1c9：Q1: 修好 popcount32 的第 31 位
│
├─ job grade_q1：大題一 eBNN 推論
│  ✔  8/8  popcount32（含第 31 位、全 1）
│  ✘  0/15 bnn_hidden：XNOR、門檻、位元位置
│        影像 0x1C42C64A5222423D：期望 hidden=0x80000001，實際 0x00000000
│  ...
│  ── Q1 得分 23/100
└─ pipeline 完成：Q1=23
```

結果的 JSON 存在 `ci/results/`。[`.gitlab-ci.yml`](.gitlab-ci.yml) 是「考場那邊大概怎麼設定」的參考檔。也可以不 commit、直接跑：

```bash
python3 q2_parallel/grade.py            # 單題
python3 grade_all.py --detail           # 三題總分
python3 ci/run_ci.py --message "Q3"     # 模擬某個 commit 訊息
python3 selftest.py                     # 檢查評分程式本身（參考解答應拿滿分）
```

## 卡住時：分級提示

```bash
python3 q1_ebnn/grade.py --hint                      # 第 1 級：是哪一類錯
python3 q1_ebnn/grade.py --hint 2                    # 第 2 級：在哪裡
python3 q1_ebnn/grade.py --hint 3 --item bnn_hidden  # 第 3 級：怎麼改（只看某一項）
```

先只要第 1 級，搭配 [除錯檢查清單](reading/05_除錯檢查清單.md) 自己找；還是卡住才往上要。每次查看都會記在 `ci/results/hints.csv`，CI 輸出會顯示累計次數。練習的目標是這個數字一輪比一輪少。提示原文在 `solutions/hints_src.py`（寫完再看）。

## 在真的 ROS 2 上跑（選用）

所有 node 都只用標準的 rclpy API，在裝了 ROS 2 的環境（例如官方的 `srecruit-demo` Docker 映像）可以直接跑。每個指令開一個終端機：

```bash
python3 q2_parallel/boards.py 0
python3 q2_parallel/boards.py 1
python3 q2_parallel/coordinator.py
ros2 topic echo /ebnn/prediction
ros2 topic pub --once /camera/image std_msgs/msg/UInt64 "{data: 4342103635304399420}"   # 數字 3 的影像，應該預測 3
```

## 資料夾結構

```text
ncku_mock_exam_v2/
├── README.md、.gitlab-ci.yml、grade_all.py、selftest.py
├── ci/              run_ci.py（模擬 CI）、install_hook.py
├── common/          fake_ros/（rclpy 替身）、boardsim.py（模擬開發板）、model.py / model.h（eBNN 權重）、
│                    pio_sim.py（RP2350 PIO 模擬器）、algos_ref.py（SHA-0 / CRC 參考）、clib.py、report.py
├── q1_ebnn/         README、bnn.h、bnn.c ✎、xnorpop.pio ✎、ebnn_node.py ✎、bnn_lib.py、grade.py
├── q2_parallel/     README、firmware.h、firmware.c ✎、coordinator.py ✎、boards.py、grade.py
├── q3_algos/        README、algos.h、algos.c ✎、dispatcher.py ✎、engine.h / engine.c（含 sniffer）、
│                    bench.c、boards.py、grade.py
├── reading/         00 總覽、01 ROS 2、02 位元 / RISC-V / PIO、03 並行 / 鎖 / DMA、04 去年題型
└── solutions/       參考解答與解說（寫完再看）
                     ✎ = 你要修改的檔案
```
