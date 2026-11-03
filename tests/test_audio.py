"""audio（音源の長さ）と、終端の無音チップ。"""
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import audio  # noqa: E402
import dtx  # noqa: E402
import simplify  # noqa: E402
from test_core import MASTER  # noqa: E402


def ogg_page(granule: int, body: bytes, seq: int) -> bytes:
    head = b'OggS' + bytes([0, 2 if seq == 0 else 4]) + struct.pack('<q', granule) + struct.pack('<III', 1, seq, 0)
    return head + bytes([1, len(body)]) + body


class OggTest(unittest.TestCase):
    def test_vorbis_duration(self):
        ident = b'\x01vorbis' + struct.pack('<I', 0) + bytes([2]) + struct.pack('<I', 44100) + b'\x00' * 12
        data = ogg_page(0, ident, 0) + ogg_page(44100 * 3, b'\x00' * 10, 1)
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'bgm.ogg'
            p.write_bytes(data)
            self.assertAlmostEqual(audio.duration(p), 3.0)
            self.assertIsNone(audio.duration(Path(tmp) / 'none.ogg'))

    def test_silence_wav(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = audio.write_silence(Path(tmp) / 'silence.wav', 0.05)
            self.assertAlmostEqual(audio.duration(p), 0.05, places=3)


class EndChipTest(unittest.TestCase):
    def test_render_puts_silence_after_last_note(self):
        master = dtx.parse_text(MASTER)   # BPM 120 = 1 小節 2 秒
        p = simplify.normalize(None, 'easy')
        kept, _ = simplify.simplify(master.notes, p, 2.0, master.max_bar)
        text = dtx.render(master, kept, difficulty='easy', params=p, end_time=7.0)   # 最後の打点（小節 3 末）より後
        self.assertIn('#WAVZZ: silence.wav', text)
        line = next(ln for ln in text.splitlines() if ln.startswith('#00461:'))   # 7 秒 = 小節 4 の半分
        self.assertEqual(line[len('#00461: '):].index('ZZ') // 2, 32)
        again = dtx.parse_text(text)
        self.assertEqual({(n.bar, n.ch, n.pos) for n in again.notes}, {(k.bar, k.ch, k.slot / k.grid) for k in kept})
        # 最後の打点より前の end_time なら何も足さない
        self.assertNotIn('silence.wav', dtx.render(master, kept, difficulty='easy', params=p, end_time=1.0))

    def test_simplify_keeps_the_last_hit(self):
        notes = [dtx.Note(b, ch, i, 32, chip) for b in range(1, 5)
                 for ch, i, chip in (('13', 0, '0D'), ('12', 8, '09'), ('13', 16, '0D'), ('12', 24, '09'))]
        notes.append(dtx.Note(4, '12', 30, 32, '09'))   # 曲の締めのスネア（型には無い位置）
        kept, _ = simplify.simplify(notes, simplify.normalize(None, 'beginner'), 2.0)
        self.assertIn((4, '12', 30), {(k.bar, k.ch, k.slot) for k in kept})


if __name__ == '__main__':
    unittest.main()
