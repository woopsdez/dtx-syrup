"""dtx / simplify / songs の動作。songlist には触らず、一時フォルダに作った曲で確かめる。"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import dtx  # noqa: E402
import simplify  # noqa: E402
import songs  # noqa: E402

MASTER = '\r\n'.join([
    '; Created by TubeDTX',
    '',
    '#TITLE: テスト曲「サンプル」',
    '#ARTIST: ARTIST│歌手「サンプル」',
    '#PREVIEW: pre.ogg',
    '#PREIMAGE: pre.jpg',
    '#BPM: 120',
    '#DLEVEL: 50',
    '',
    '#WAV01: bgm.ogg',
    '#VOLUME01: 100',
    '#BGMWAV: 01',
    '#WAV02: chips\\close.xa',
    '#WAV05: chips\\close.xa',
    '#WAV06: chips\\snare.xa',
    '#WAV09: chips\\snare.xa',
    '#WAV0A: chips\\bd.xa',
    '#WAV0D: chips\\bd.xa',
    '#WAV0E: chips\\high.xa',
    '#WAV0H: chips\\high.xa',
    '',
    # 小節 1: BGM は 2 拍目（128 分解能の 32 番目）から
    '#00101: ' + '00' * 32 + '01' + '00' * 95,
    '#00154: ' + '00' * 32 + '01' + '00' * 95,
    # 小節 2: HH 8 分で強弱、SD 2・4 拍、BD 1・3 拍 + 弱い BD、HT 1 つ（32 分解能）
    '#00211: ' + ''.join(('05' if i % 8 == 0 else '03' if i % 4 == 0 else '00') for i in range(32)),
    '#00212: ' + ''.join(('09' if i in (8, 24) else '00') for i in range(32)),
    '#00213: ' + ''.join(('0D' if i in (0, 16) else '0B' if i == 20 else '00') for i in range(32)),
    '#00214: ' + ''.join(('0H' if i == 28 else '00') for i in range(32)),
    # 小節 3: 小節末ぎりぎりの HH（次の小節頭に丸まる）
    '#00311: ' + ''.join(('05' if i == 31 else '00') for i in range(32)),
    '',
]) + '\r\n'


def make_song(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'score.dtx').write_bytes(MASTER.encode('cp932'))
    (folder / 'tube_dtx_config.json').write_text('{}', encoding='utf-8')


class RoundTest(unittest.TestCase):
    def test_js_round(self):
        self.assertEqual(simplify.js_round(0.5), 1)
        self.assertEqual(simplify.js_round(1.5), 2)
        self.assertEqual(simplify.js_round(2.4), 2)
        self.assertEqual(simplify.js_round(2.6), 3)

    def test_allowed(self):
        self.assertTrue(simplify.allowed('all', 3, 8))
        self.assertFalse(simplify.allowed('off', 0, 8))
        self.assertTrue(simplify.allowed('24', 2, 8))
        self.assertTrue(simplify.allowed('24', 6, 8))
        self.assertFalse(simplify.allowed('24', 4, 8))
        self.assertTrue(simplify.allowed('2', 4, 8))
        self.assertFalse(simplify.allowed('2', 2, 8))
        self.assertTrue(simplify.allowed('16', 1, 8))  # 密度 >= グリッドなら全部通す


class ParseTest(unittest.TestCase):
    def setUp(self):
        self.chart = dtx.parse_text(MASTER)

    def test_header_and_bgm(self):
        self.assertEqual(self.chart.bpm, 120)
        self.assertEqual(self.chart.header['TITLE'], 'テスト曲「サンプル」')
        self.assertEqual(self.chart.bgm, (1, 32, 128))
        self.assertAlmostEqual(self.chart.bgm_start(), 0.5)  # 1 小節 2 秒の 1/4
        self.assertEqual(self.chart.max_bar, 3)

    def test_notes(self):
        chans = sorted({n.ch for n in self.chart.notes})
        self.assertEqual(chans, ['11', '12', '13', '14'])
        hh = [n for n in self.chart.notes if n.ch == '11' and n.bar == 2]
        self.assertEqual(len(hh), 8)
        self.assertEqual({n.level for n in hh}, {1, 3})


class SimplifyTest(unittest.TestCase):
    def setUp(self):
        self.master = dtx.parse_text(MASTER)

    def test_beginner_defaults(self):
        p = simplify.normalize(None, 'beginner')
        kept, removed = simplify.simplify(self.master.notes, p)
        by = {(k.bar, k.ch, k.slot) for k in kept}
        # HH は 2 分（8 分割の 0 と 4）。0 は BD と重なり同時押し上限 1 で BD に譲る。弱い HH（レベル 1）は消える
        self.assertIn((2, '11', 4), by)
        self.assertNotIn((2, '11', 0), by)
        self.assertNotIn((2, '11', 2), by)
        # SD は 2・4 拍、BD は小節頭だけ、タムは消える、弱い BD は消える
        self.assertIn((2, '12', 2), by)
        self.assertIn((2, '12', 6), by)
        self.assertIn((2, '13', 0), by)
        self.assertNotIn((2, '13', 4), by)
        self.assertFalse(any(k.ch == '14' for k in kept))
        # 同時押し 1 個: 小節頭は SD が無いので BD > HH で BD が残る
        head = [k for k in kept if (k.bar, k.slot) == (2, 0)]
        self.assertEqual([k.ch for k in head], ['13'])
        # 小節 3 末尾の HH は小節 4 の頭に丸まる
        self.assertIn((4, '11', 0), by)
        self.assertEqual(len(kept) + len(removed), len(self.master.notes))

    def test_easy_keeps_more(self):
        kb, _ = simplify.simplify(self.master.notes, simplify.normalize(None, 'beginner'))
        ke, _ = simplify.simplify(self.master.notes, simplify.normalize(None, 'easy'))
        self.assertGreater(len(ke), len(kb))
        self.assertTrue(any(k.ch == '14' for k in ke))  # Easy はタムを残す

    def test_match_and_stats(self):
        kept, _ = simplify.simplify(self.master.notes, simplify.normalize(None, 'easy'))
        m = simplify.match_rate(kept, self.master.notes)
        self.assertIsNotNone(m)
        self.assertGreater(m['rate'], 0.5)
        st = simplify.stats(kept, self.master.notes)
        self.assertEqual(st['notes'], len(kept))
        self.assertGreaterEqual(st['maxPerBar'], 1)
        self.assertEqual(simplify.dlevel_for([], self.master.notes), 5)


class RenderTest(unittest.TestCase):
    def test_roundtrip(self):
        master = dtx.parse_text(MASTER)
        p = simplify.normalize(None, 'easy')
        kept, _ = simplify.simplify(master.notes, p)
        text = dtx.render(master, kept, difficulty='easy', params=p, dlevel=30)
        self.assertIn('\r\n', text)
        self.assertEqual(text.splitlines()[1][:len(dtx.MARKER)], dtx.MARKER)
        self.assertIn('#DLEVEL: 30', text)
        self.assertIn('#TITLE: テスト曲「サンプル」', text)
        self.assertIn('#00101: ', text)  # BGM 行はそのまま
        self.assertIn('#00154: ', text)
        text.encode('cp932')  # Shift_JIS に落ちる
        again = dtx.parse_text(text)
        self.assertTrue(again.is_generated())
        self.assertEqual(again.bgm, master.bgm)
        got = {(n.bar, n.ch, n.pos, n.chip) for n in again.notes}
        want = {(k.bar, k.ch, k.slot / k.grid, k.chip) for k in kept}
        self.assertEqual(got, want)


class SongsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='play-dtxmania-'))
        self.folder = self.tmp / 'テスト曲'
        make_song(self.folder)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_clean_names(self):
        self.assertEqual(songs.clean_title('テスト曲「サンプル」', 'ARTIST│歌手「サンプル」'), 'サンプル')
        self.assertEqual(songs.clean_artist('テスト曲「サンプル」', 'ARTIST│歌手「サンプル」'), '歌手')
        self.assertEqual(songs.clean_title('Some Song [Official MV]', 'Band'), 'Some Song')
        self.assertEqual(songs.clean_artist('Some Song [Official MV]', 'Band'), 'Band')

    def test_scan_and_generate(self):
        found = songs.scan(self.tmp)
        self.assertEqual(len(found), 1)
        s = found[0]
        self.assertEqual(s.title, 'サンプル')
        self.assertEqual(s.status(), {'beginner': None, 'easy': None})
        summary = s.summary(0)
        self.assertEqual(summary['thumb'], None)
        self.assertAlmostEqual(summary['bgmStart'], 0.5)

        r = songs.generate(s, 'beginner', {'grid': 4, 'hh': '1'}, save_rules=True)
        self.assertTrue(r['ok'])
        self.assertEqual(s.status()['beginner'], 'auto')
        saved = json.loads((self.folder / songs.SETTINGS_NAME).read_text(encoding='utf-8'))
        self.assertEqual(saved['rules']['beginner']['grid'], 4)
        self.assertEqual(saved['rules']['beginner']['hh'], '1')
        self.assertEqual(saved['rules']['beginner']['sd'], '24')  # 省略分は既定で埋まる

        setdef = (self.folder / 'set.def').read_bytes()
        self.assertIn(b'\r\n', setdef)
        txt = setdef.decode('cp932')
        self.assertIn('#TITLE: サンプル', txt)
        self.assertIn('#L1LABEL: Beginner', txt)
        self.assertIn('#L1FILE: score_beginner.dtx', txt)
        self.assertIn('#L2LABEL: Master', txt)   # Easy はまだ無いので Master が L2
        self.assertIn('#L2FILE: score.dtx', txt)
        self.assertNotIn('#L3', txt)

        songs.generate(s, 'easy')
        txt = (self.folder / 'set.def').read_bytes().decode('cp932')
        self.assertIn('#L2LABEL: Easy', txt)
        self.assertIn('#L3LABEL: Master', txt)

        # 書き直し（自分のファイルは上書きできる）
        r2 = songs.generate(s, 'beginner')
        self.assertTrue(r2['ok'])
        self.assertTrue(r2['replaced'])

    def test_hand_made_is_protected(self):
        hand = (self.folder / 'score_beginner.dtx')
        hand.write_bytes('; Created by DTXCreator 025(verK)\r\n#TITLE: x\r\n#00111: 05\r\n'.encode('cp932'))
        s = songs.scan(self.tmp)[0]
        self.assertEqual(s.status()['beginner'], 'hand')
        r = songs.write_variant(s, 'beginner', None, force=True)
        self.assertFalse(r['ok'])
        self.assertEqual(r['skipped'], 'hand')
        self.assertIn('DTXCreator', hand.read_bytes().decode('cp932'))
        self.assertIn('beginner', s.hand_variants())

    def test_setdef_keeps_existing_title(self):
        (self.folder / 'set.def').write_bytes('; Created by DTXCreatorAL 013\r\n\r\n#TITLE: 手で付けた題名\r\n\r\n#L1LABEL: Master\r\n#L1FILE: score.dtx\r\n'.encode('cp932'))
        s = songs.scan(self.tmp)[0]
        songs.generate(s, 'easy')
        txt = (self.folder / 'set.def').read_bytes().decode('cp932')
        self.assertIn('#TITLE: 手で付けた題名', txt)
        self.assertIn('#L1LABEL: Easy', txt)
        self.assertIn('#L2LABEL: Master', txt)
        self.assertIn('; Created by DTXCreatorAL 013', txt)
        # UI から題名を直したら、それが set.def にも入る
        s.settings['title'] = '直した題名'
        songs.save_settings(s.folder, s.settings)
        songs.write_setdef(s)
        txt = (self.folder / 'set.def').read_bytes().decode('cp932')
        self.assertIn('#TITLE: 直した題名', txt)

    def test_setdef_in_utf8_is_read_correctly(self):
        # 手作りの set.def が UTF-8 のことがある。題名を化かさずに引き継ぎ、Shift_JIS で書き直す
        (self.folder / 'set.def').write_text('#TITLE: ユニコードの題名\r\n#L1LABEL: Master\r\n#L1FILE: score.dtx\r\n', encoding='utf-8')
        s = songs.scan(self.tmp)[0]
        songs.generate(s, 'beginner')
        raw = (self.folder / 'set.def').read_bytes()
        self.assertIn('#TITLE: ユニコードの題名'.encode('cp932'), raw)
        self.assertNotIn('ユニコード'.encode('utf-8'), raw)


if __name__ == '__main__':
    unittest.main()
