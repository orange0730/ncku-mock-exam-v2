"""檢查「評分程式本身」：參考解答要拿滿分、起始檔要拿很低的分、參考實作要對得上公開的測試向量。

    python3 selftest.py

需要 Linux（或其他能執行剛編譯出來程式的環境）與 gcc。這不是幫你解題。
"""
import json
import os
import subprocess
import sys
import unittest
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOL = HERE / 'solutions'
sys.path.insert(0, str(HERE / 'common'))
sys.path.insert(0, str(HERE / 'ci'))

import algos_ref  # noqa: E402
import model  # noqa: E402
from pio_sim import assemble, run  # noqa: E402
from run_ci import parse_questions  # noqa: E402


def grade(script, *args):
    proc = subprocess.run([sys.executable, str(script), '--json', *map(str, args)], capture_output=True,
                          text=True, encoding='utf-8', errors='replace')
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise AssertionError(proc.stderr[-2000:]) from None


def failures(result):
    return [(r['name'], r['detail']) for r in result['rows'] if not r['passed']]


class References(unittest.TestCase):
    def test_sha0_published_vector(self):
        self.assertEqual(algos_ref.sha0(b'abc').hex(), '0164b8a914cd2a5e74c4f7ff082c4d97f1edf880')

    def test_sha1_matches_hashlib(self):
        import hashlib
        for n in (0, 55, 56, 64, 200):
            m = os.urandom(n)
            self.assertEqual(algos_ref.sha1(m), hashlib.sha1(m).digest())

    def test_sniffer_recipe_is_standard_crc32(self):
        self.assertEqual(algos_ref.sniff_crc(b'123456789', 0xFFFFFFFF, True, True, True), 0xCBF43926)
        m = os.urandom(777)
        self.assertEqual(algos_ref.sniff_crc(m, 0xFFFFFFFF, True, True, True), zlib.crc32(m))

    def test_model_is_a_real_classifier(self):
        data = model.dataset(500, seed=11)
        acc = sum(model.infer(v)[0] == d for v, d in data) / len(data)
        self.assertGreater(acc, 0.9)

    def test_pio_x_decrement_semantics(self):
        prog = 'pull\nset x, 0\njmp x-- skip\nskip:\nmov isr, x\npush'
        self.assertEqual(run(assemble(prog), [0], 'fast')[0], [0xFFFFFFFF])

    def test_ci_prefix(self):
        self.assertEqual(parse_questions('Q2: fix'), ['Q2'])
        self.assertEqual(parse_questions('[Q1] x'), ['Q1'])
        self.assertEqual(parse_questions('ALL'), ['Q1', 'Q2', 'Q3'])
        self.assertEqual(parse_questions('fix Q1'), [])
        self.assertEqual(parse_questions('Q12'), [])


class Graders(unittest.TestCase):
    def test_q1(self):
        good = grade(HERE / 'q1_ebnn' / 'grade.py', '--bnn', SOL / 'q1_ebnn' / 'bnn.c',
                     '--pio', SOL / 'q1_ebnn' / 'xnorpop.pio', '--node', SOL / 'q1_ebnn' / 'ebnn_node.py')
        self.assertEqual(good['total'], 100, failures(good))
        self.assertLess(grade(HERE / 'q1_ebnn' / 'grade.py')['total'], 10)

    def test_q2(self):
        good = grade(HERE / 'q2_parallel' / 'grade.py', '--firmware', SOL / 'q2_parallel' / 'firmware.c',
                     '--coordinator', SOL / 'q2_parallel' / 'coordinator.py')
        self.assertEqual(good['total'], 100, failures(good))
        self.assertLess(grade(HERE / 'q2_parallel' / 'grade.py')['total'], 10)

    def test_q3(self):
        good = grade(HERE / 'q3_algos' / 'grade.py', '--algos', SOL / 'q3_algos' / 'algos.c',
                     '--dispatcher', SOL / 'q3_algos' / 'dispatcher.py')
        self.assertEqual(good['total'], 100, failures(good))
        self.assertLess(grade(HERE / 'q3_algos' / 'grade.py')['total'], 10)


class OutOfBounds(unittest.TestCase):
    """拿參考解答，只注入一個「多一格」的越界存取，評分程式必須抓到（不能靠運氣）。"""

    def variant(self, source, old, new):
        import tempfile
        text = source.read_text(encoding='utf-8')
        self.assertIn(old, text)
        tmp = Path(tempfile.mkdtemp()) / source.name
        tmp.write_text(text.replace(old, new), encoding='utf-8')
        return tmp

    def item(self, result, keyword):
        return next(r for r in result['rows'] if keyword in r['name'])

    def test_q1_scores_read_past_end(self):
        bad = self.variant(SOL / 'q1_ebnn' / 'bnn.c', 'for (int k = 1; k < N_OUT; k++)', 'for (int k = 1; k <= N_OUT; k++)')
        r = grade(HERE / 'q1_ebnn' / 'grade.py', '--bnn', bad, '--pio', SOL / 'q1_ebnn' / 'xnorpop.pio',
                  '--node', SOL / 'q1_ebnn' / 'ebnn_node.py')
        self.assertFalse(self.item(r, 'bnn_infer')['passed'])

    def test_q2_reads_req_before_checking_n(self):
        bad = self.variant(SOL / 'q2_parallel' / 'firmware.c', 'if (n != 3) return -1;',
                           'volatile uint32_t peek = req[2]; (void)peek; if (n != 3) return -1;')
        r = grade(HERE / 'q2_parallel' / 'grade.py', '--firmware', bad,
                  '--coordinator', SOL / 'q2_parallel' / 'coordinator.py')
        self.assertFalse(self.item(r, '不合法請求')['passed'])

    def test_q3_crc_reads_one_extra_byte(self):
        bad = self.variant(SOL / 'q3_algos' / 'algos.c', 'for (size_t i = 0; i < len; i++) crc = (crc >> 8)',
                           'for (size_t i = 0; i <= len && (i < len || p[i] != 0x5A); i++) if (i < len) crc = (crc >> 8)')
        r = grade(HERE / 'q3_algos' / 'grade.py', '--algos', bad, '--dispatcher', SOL / 'q3_algos' / 'dispatcher.py')
        self.assertFalse(self.item(r, 'CRC-32 軟體版正確')['passed'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
