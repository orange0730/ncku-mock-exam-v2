"""分級提示的原文（寫完再看）。修改後執行 `python3 solutions/hints_src.py` 重新產生 common/hints.dat。

每一項：keywords = 評分項目名稱裡必須「全部」出現的字（依序比對，先比對到的先用），
levels = [第 1 級：方向, 第 2 級：位置, 第 3 級：解法]。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'common'))

WALL = {'keywords': ['-Wall'], 'levels': [
    '看評分輸出列出的那一個警告，以及它指到的那一行。編譯器的警告常常就是 bug 本身。',
    '常見的有：有號 / 無號比較（-Wsign-compare）、沒用到的變數或參數、運算子優先順序（-Wparentheses）、函式少了 return。',
    '照警告改：沒用到的參數寫 (void)x;，比較時兩邊型別一致（例如都用 size_t 或都轉成 int），有疑慮的位元運算加括號。']}

HINTS = {
    'Q1': [
        {'keywords': ['popcount32'], 'levels': [
            '32 個位元每一個都有算到嗎？用全 1（0xFFFFFFFF）在紙上跑一次，應該得到 32。',
            '看迴圈：從 0 開始、到哪裡結束？總共跑幾次？',
            '起始檔 i < 31 只跑 31 次，漏掉第 31 位。改成 i < 32（或用 SWAR / __builtin_popcount）。']},
        {'keywords': ['bnn_hidden'], 'levels': [
            '這個函式有三個獨立的錯，三個都對才給分：比對方式、門檻比較、輸出的位元位置。把評分訊息裡「期望」和「實際」的 hidden 寫成二進位比一比。',
            '① popcount 要數的是「相同」的位數，XOR 的結果裡 1 代表什麼？② 規格是 matches >= T1[j]。③ 規格說 bit j = 神經元 j，第二層 W2 也是照這個順序排的。',
            '① popcount32(img[0] ^ W1[j][0]) 改成 popcount32(~(img[0] ^ W1[j][0]))（兩個 word 都要）；② > 改成 >=；③ 1u << (31 - j) 改成 1u << j。']},
        {'keywords': ['bnn_scores'], 'levels': [
            '二值內積：相同 +1、不同 −1。如果有 p 個相同、32 − p 個不同，總和是多少？',
            '把 p − (32 − p) 化簡，跟程式裡的 popcount(...) − 32 比較。',
            'scores[k] = 2 * popcount32(~(hidden ^ W2[k])) - 32;']},
        {'keywords': ['bnn_infer'], 'levels': [
            '兩件事：分數一樣時要選哪一個？迴圈有沒有讀到陣列外面？',
            '用 >= 比較時，同分會被後面的 k 取代；scores 只有 index 0..9，N_OUT 是 10。',
            '比較改用 >（同分保留最小 index）；迴圈條件是 k < N_OUT，不能是 <=。']},
        {'keywords': ['整體'], 'levels': [
            '這一項是前面四個函式的綜合結果，先讓前面四項都通過。',
            '前面都過了這一項還錯：檢查有沒有越界讀取、沒初始化的變數，或只在特定影像才會走到的分支。',
            '參考解答的 bnn_infer 對 1000 張含雜訊數字的預測，與 Python 參考模型逐張相同；對照 bnn.h 的規格逐行檢查。']},
        WALL,
        {'keywords': ['效率', '週期'], 'levels': [
            '把 0-bit 和 1-bit 的路徑各走一次，數數每個 bit 要幾條指令。',
            '能不能讓「計數」那條 jmp x-- 同時負責「回到迴圈開頭」？想想如果最後一個 bit 走這條路、多跑一次 out 會怎樣：沒開 autopull 時，空的 OSR 會移出 0。',
            '先 mov osr, ~osr 把問題變成「數 1」；1-bit 路徑用 jmp x--, loop 直接回迴圈，0-bit 路徑才走 jmp !osre, loop。每個 bit 3 週期，約 102.5 週期 / word。']},
        {'keywords': ['效率', '指令'], 'levels': [
            '有沒有可以拿掉的 jmp？.wrap 會免費跳回 .wrap_target。',
            '每一條指令都必要嗎？迴圈展開會增加指令數。',
            '參考解答 9 條：pull、mov osr ~osr、mov x ~null、out y 1、jmp !y、jmp x--、jmp !osre、mov isr ~x、push。']},
        {'keywords': ['edge_values'], 'levels': [
            '要數的是 d 裡「0」的個數。先跑 python3 ../common/pio_sim.py xnorpop.pio 0x0 0xFFFFFFFF：輸入 0 應得到 32，全 1 應得到 0。',
            '兩個問題：① jmp !y skip 讓哪一種 bit 被數到？② jmp x-- 只能減；x 從 31 開始，最後的 ~x 會是多少？PIO 的慣用法是從 0xFFFFFFFF 往下數。',
            '① 讓數到的是 0：例如 jmp y-- skip（y 為 1 時跳過），或先 mov osr, ~osr 改成數 1；② set x, 31 改成 mov x, ~null，最後 mov isr, ~x 就是次數。']},
        {'keywords': ['random_'], 'levels': [
            '先讓 edge_values 通過。edge 過了這一項還沒過的話：每個輸入是不是剛好輸出一個 word？',
            'host 讀得慢或斷斷續續時，push 會停住等；檢查迴圈結束條件，以及有沒有在等待時弄亂 x / OSR。',
            '同 edge_values 的修正；只要每個輸入剛好 pull 一次、push 一次，stall 不會影響結果。']},
        {'keywords': ['node 名稱'], 'levels': ['規格表的 node 名稱是什麼？', '看 super().__init__(...) 的參數。', "super().__init__('ebnn')"]},
        {'keywords': ['訂閱'], 'levels': [
            '影像是 64 位元，你訂閱用的訊息型別放得下嗎？',
            '看 import 與 create_subscription 用的型別。兩端型別不同時 ROS 根本不會連上，callback 永遠不會被呼叫。',
            "from std_msgs.msg import UInt64，然後 create_subscription(UInt64, '/camera/image', self.on_image, 10)。"]},
        {'keywords': ['發布'], 'levels': [
            '逐字對照規格表的 topic 名稱與型別，單複數也要一樣。',
            '分數是 /ebnn/scores（Int32MultiArray），預測是 /ebnn/prediction（Int32）。',
            "create_publisher(Int32MultiArray, '/ebnn/scores', 10) 與 create_publisher(Int32, '/ebnn/prediction', 10)。"]},
        {'keywords': ['30 張影像'], 'levels': [
            '先看評分訊息是哪一種：完全沒輸出、callback 拋出例外、還是數值不對？',
            '拋 AssertionError → 訊息欄位型別不對（ctypes 陣列不是 list）；數值不對 → 影像的高低 32 位有沒有對調（img[0] 是低 32 位）。',
            "lo = img & 0xFFFFFFFF、hi = img >> 32；s.data = [int(v) for v in scores]。"]},
        {'keywords': ['先 scores'], 'levels': ['規格要求每張影像先發哪一個？', '看 on_image 裡兩個 publish 的先後。', '先 publish scores，再 publish prediction。']},
        {'keywords': ['邊界影像'], 'levels': [
            '全 0、全 1、只有最高位（1 << 63）的影像：最高位落在哪一個 32 位元字？',
            '1 << 63 拆開後應該是 hi 的 bit 31、lo 為 0。',
            '同「30 張影像」那一項的修正：高低位要對、訊息型別要對。']},
    ],
    'Q2': [
        {'keywords': ['header'], 'levels': [
            'header 的三個欄位各佔幾個位元？first 最大可以到多少？',
            'first 是 bits 15..8，共 8 個位元，你的 mask 寬度對嗎？另外規格要求 resp[0]「原樣」送回 req[0]。',
            'first = (h >> 8) & 0xFF；resp[0] = h;']},
        {'keywords': ['部分神經元'], 'levels': [
            '影像的兩個 word 哪一個是低位？mask 要涵蓋哪幾個位元？',
            'img[0] 應該是 req[1]（像素 0..31）。mask = 從 bit first 開始、連續 count 個 1。',
            'uint32_t img[2] = { req[1], req[2] }; mask = (count >= 32 ? 0xFFFFFFFFu : ((1u << count) - 1u)) << first;']},
        {'keywords': ['不合法'], 'levels': [
            '不合法的請求有哪幾種？你在什麼時候檢查它們？',
            'n 可能小於 3。還沒檢查 n 之前就讀 req[1]、req[2]，就已經讀到陣列外面了（評分會讓它當掉）。檢查要放在函式最開頭。',
            '函式第一行 if (n != 3) return -1;；解出 first、count 後立刻 if (count == 0 || count > 32 || first + count > 32) return -1;；之後才讀 req[1]、req[2]、寫 resp。']},
        {'keywords': ['count = 32'], 'levels': [
            '1u << 32 在 C 裡是什麼？',
            '移位量等於型別寬度是未定義行為；ARM 和 x86 實際上都會算出錯的 mask。',
            'count == 32 時 mask 直接用 0xFFFFFFFFu（或用 1ULL 在 64 位元下算完再截斷）。']},
        {'keywords': ['稀疏到達'], 'levels': [
            '先檢查送出的 header：三個欄位放對位置了嗎？用回應裡的 seq 對帳時，兩片的回應對得起來嗎？',
            'seq 在 bits 31..16、first 在 15..8、count 在 7..0。起始檔把 seq 和 first 的位置放錯，回應的 seq 對不上，永遠等不到第二片。',
            'header = (seq << 16) | (first << 8) | count；收到回應用 seq = header >> 16 對帳，32 個神經元湊齊才算第二層並發布。']},
        {'keywords': ['一次湧入'], 'levels': [
            '40 張同時到達時，你的預測會不會發布得亂掉順序？',
            '一次送很多張（pipeline）時，回應到達的順序可能和影像順序不同。要用 seq 排隊，依序發布。',
            '用 dict 存「已完成的 seq → 預測」，維護一個 next_out；while next_out in ready: 發布並 next_out += 1。']},
        {'keywords': ['工作分配'], 'levels': [
            '每張影像的 32 個神經元，是不是剛好每個都交給某片板子算了一次？兩片都有用到嗎？',
            '切分的 (first, count) 不能重疊、合起來要剛好是 0..31；協調者不能自己算第一層。',
            '例如 board0 算 (0, 21)、board1 算 (21, 11)；或整張 (0, 32) 輪流交給兩片。']},
        {'keywords': ['吞吐量'], 'levels': [
            '兩片板子速度不同（board1 慢一倍），每筆 request 還有 2 ms 固定成本。',
            '① 不要送一張、等一張（pipeline）；② 依速度切，讓兩片同時做完；③ 有積壓時，整張給一片只要付一次固定成本。',
            '參考解答自己記每片板子「預計何時有空」：兩片都閒時依速度切（約 21 / 11），有積壓時整張給最早能做完的那片。加速比約 1.50。']},
        {'keywords': ['延遲'], 'levels': [
            '單張影像什麼時候做得最快？',
            '兩片同時算同一張（依速度切）時，單張延遲最低；整張丟給一片會比較慢。',
            '兩片都閒著時切成約 21 / 11，平均延遲約 26 ms。']},
    ],
    'Q3': [
        {'keywords': ['排序正確'], 'levels': [
            'n = 0、n = 1 時你的程式做什麼？迴圈有沒有處理到最後一個元素？',
            'size_t 是無號的：n = 0 時 n − 1 是一個極大的數。插入排序的外層迴圈應該跑到哪裡？',
            '外層改成 for (size_t i = 1; i < n; i++)，或在開頭加 if (n < 2) return;。']},
        {'keywords': ['排序效率'], 'levels': [
            '插入排序是 O(n²)，100 萬筆跑不完。',
            '可以用 quicksort / heapsort（O(n log n)），或 32 位元整數專用的 radix sort（O(n)）。qsort 每次比較都要呼叫函式指標，所以手寫的特化版本常常比它快。',
            'LSD radix sort：每輪看 8 位元、共 4 輪；每輪用 count[256] 做穩定的計數分配，需要一塊 malloc(n) 的暫存陣列。參考解答約比 qsort 快 9 倍。']},
        {'keywords': ['SHA-0'], 'levels': [
            'SHA-0 和 SHA-1 差在哪一行？另外還有三個跟規格不符的地方：第 40–59 輪的 f、長度欄位的位元組順序、填充需要幾個區塊。',
            '① 訊息排程不該有 rotl(…, 1)；② 40–59 輪的 f 是 majority；③ 長度要 big-endian；④ 剩下 >= 56 bytes 時，0x80 和長度放不進同一個區塊。',
            'w[t] = w[t-3] ^ w[t-8] ^ w[t-14] ^ w[t-16]；f = (b & c) | (b & d) | (c & d)；last 開 128 bytes、blocks = rest < 56 ? 1 : 2、last[64 * blocks - 1 - i] = (uint8_t)(bits >> (8 * i))。']},
        {'keywords': ['CRC-32 軟體版正確'], 'levels': [
            '標準 CRC-32 有五個參數：多項式、初值、輸入反射、輸出反射、最後 XOR。先用 "123456789" 測，應得到 cbf43926。',
            '右移（反射）的寫法要用反射後的多項式 0xEDB88320；初值與最後的 XOR 都是 0xFFFFFFFF。',
            'crc = 0xFFFFFFFF；每個 byte：crc ^= p[i]，做 8 次 crc = (crc & 1) ? (crc >> 1) ^ 0xEDB88320 : crc >> 1；最後 return crc ^ 0xFFFFFFFF。']},
        {'keywords': ['CRC-32', '效率'], 'levels': [
            '每個 byte 都要做 8 次迴圈。能不能一次處理一整個 byte？',
            '事先算好一張 256 項的表。',
            'table[i] = 對 i 做 8 次逐位元運算的結果；主迴圈 crc = (crc >> 8) ^ table[(crc ^ p[i]) & 0xFF]。']},
        {'keywords': ['DMA sniffer 版正確'], 'levels': [
            '先看評分訊息：是「引擎中止」（違反哪一條規則？）還是數值不對？',
            '中止：count 是筆數不是 bytes；位址要對齊傳輸大小（sniffer 逐 byte 算，用 XFER_8 最簡單）；len = 0 不能交給引擎；release 前要先 disable sniffer。數值不對：硬體算的是不反射的 CRC，標準 CRC-32 是反射的。',
            'XFER_8、count = len、src_increment = true、dst_increment = false；engine_sniff_enable(ch, SNIFF_CRC32_REV)、engine_sniff_set_accumulator(0xFFFFFFFF)、engine_sniff_set_output(true, true)；做完先 engine_sniff_disable() 再 release；len == 0 直接回傳 0。']},
        {'keywords': ['真的用 sniffer'], 'levels': [
            '有沒有真的讓引擎把全部資料搬過一遍？結束後通道和 sniffer 都收乾淨了嗎？',
            '不能偷偷用軟體算；engine_release 之前要 engine_sniff_disable。',
            '參考上一項的 3 級提示，確認 claim → configure → sniff 設定 → start → wait → 讀結果 → disable → release 每一步都在。']},
        WALL,
        {'keywords': ['稀疏到達'], 'levels': [
            '逐字比對評分訊息裡期望與實際的字串：id、median、crc32 哪裡不一樣？',
            'job id 是 little-endian；median 是排序後 index n // 2；crc32 要 8 位小寫、補零；crc 要從 board_crc 的回應拿（4 bytes little-endian）。',
            "struct.unpack('<I', data[:4])、values[n // 2]、f'{crc:08x}'。"]},
        {'keywords': ['一次湧入'], 'levels': [
            '很多個工作同時在路上時，結果的順序靠什麼保證？',
            '記下工作到達的順序；三片都回來的工作，要等排在它前面的先發布。',
            '用 list 記 job id 的到達順序、dict 存每個 job 已收到的三種結果；while order and 第一個已收齊: 發布並移除。']},
        {'keywords': ['分工'], 'levels': [
            '三種演算法都要在自己的板子上跑。每個工作都送到三片板子了嗎？',
            '起始檔沒有送到 board_crc，而是在 dispatcher 裡用 zlib 自己算；也沒有訂閱 board_crc 的回應。',
            '對 /board_sort/request、/board_sha0/request、/board_crc/request 都 publish 同一份資料，並訂閱三個 response。']},
        {'keywords': ['吞吐量'], 'levels': [
            '三片板子是同時在工作，還是輪流？',
            '把三個 request 同時送出（平行），也不要等上一個工作做完才送下一個（pipeline）。',
            'on_job 時立刻對三片 publish，結果收齊後依序發布。加速比約 2.75；上限約 2.8，由最慢的 board_sort 決定。']},
    ],
}

if __name__ == '__main__':
    from hints import DATA, encode
    DATA.write_text(encode(HINTS) + '\n', encoding='ascii')
    print(f'wrote {DATA}（{sum(len(v) for v in HINTS.values())} 項提示）')
