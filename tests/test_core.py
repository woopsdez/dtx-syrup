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

    def test_normalize_levels_and_old_params(self):
        p = simplify.normalize(None, 'beginner')
        self.assertEqual((p['level'], p['hh'], p['kick'], p['sd'], p['chord']), (2, '4', 'on', '24', 1))
        p = simplify.normalize({'level': 4, 'hh': '4', 'nps': 0}, 'beginner')   # level の既定を個別に上書き
        self.assertEqual((p['level'], p['hh'], p['kick'], p['nps']), (4, '4', '8', 0.0))
        p = simplify.normalize({'grid': 8, 'hh': 'all', 'bd': '1', 'chord': 2}, 'easy')   # 2026-11-02 版の params
        self.assertEqual((p['hh'], p['chord'], p['level']), ('16', 2, 4))
        self.assertNotIn('grid', p)
        self.assertEqual(simplify.normalize({'offsets': {'0': -1, '1': 0}}, 'easy')['offsets'], {'0': -1})

    def test_step_down_peels_from_the_top(self):
        p = simplify.normalize(None, 'easy')
        seq = []
        while p is not None and len(seq) < 6:
            p = simplify.step_down(p)
            if p:
                seq.append((p['hh'], p['kick'], p['toms'], p['sd']))
        self.assertEqual(seq[:4], [('8', '8', False, 'all'), ('8', 'sig', False, 'all'), ('4', 'sig', False, 'all'), ('4', 'on', False, 'all')])
        self.assertIsNone(simplify.step_down(simplify.normalize({'level': 0}, 'beginner')))


class GridTest(unittest.TestCase):
    @staticmethod
    def pattern(length: float, bars: int, phase: float = 0.0) -> list:
        """本当の小節が DTX 小節 × length の 8 ビート（キック 1・3 拍、スネア 2・4 拍、HH 8 分）。"""
        notes = []
        for vb in range(bars):
            for ch, slots, chip in (('13', (0, 8), '0D'), ('12', (4, 12), '09'), ('11', range(0, 16, 2), '05')):
                for s in slots:
                    t = phase + (vb + s / 16) * length
                    bar = int(t)
                    notes.append(dtx.Note(bar, ch, simplify.js_round((t - bar) * 32), 32, chip))
        return notes

    def test_detects_three_quarter_bars(self):
        notes = self.pattern(0.75, 16)
        g = simplify.detect_grid(notes)
        self.assertAlmostEqual(g.length, 0.75)
        self.assertAlmostEqual(g.phase, 0.0)
        st = simplify.analyze(notes)
        self.assertEqual(len(st.presence), 1)                 # 全部同じ型
        self.assertEqual(st.fill_bars, set())
        self.assertAlmostEqual(st.presence[0][('S', 4)], 1.0)

    def test_plain_bars_stay_plain(self):
        g = simplify.detect_grid(self.pattern(1.0, 16))
        self.assertEqual((g.length, g.phase), (1.0, 0.0))

    def test_consistent_mask_and_fill_landing(self):
        notes = self.pattern(1.0, 8)
        # 小節 4 をフィルに（タム 16 分 6 発）、小節 5 の頭にキック
        for i in range(16, 32, 3):
            notes.append(dtx.Note(4, '14', i, 32, '0H'))
        notes.sort(key=lambda n: (n.bar, n.i))
        p = simplify.normalize(None, 'beginner')
        kept, removed, st, used = simplify.simplify_full(notes, p, 2.0)
        self.assertIn(4, st.fill_bars)
        fill_toms = [k.slot for k in kept if k.ch == '14' and k.bar == 4]
        self.assertLessEqual(len(fill_toms), 2)                # fill = toms2: 4 分の位置のタムを 2 つまで
        self.assertTrue(all(s % 8 == 0 for s in fill_toms))
        per_bar = {b: sorted((k.ch, k.slot) for k in kept if k.bar == b) for b in (1, 2, 3, 5, 6)}
        self.assertEqual(len({tuple(v) for v in per_bar.values()}), 1)   # 型の小節は全部同じ削り方
        self.assertIn(('13', 0), per_bar[5])                   # 着地（フィルの次の小節頭）
        self.assertEqual(len(kept) + len(removed), len(notes))
        easy, _ = simplify.simplify(notes, simplify.normalize(None, 'easy'), 2.0)
        self.assertTrue(any(k.ch == '14' and k.bar == 4 for k in easy))   # Easy はフィルを 8 分に縮めて残す


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
        kept, removed = simplify.simplify(self.master.notes, p, 2.0, self.master.max_bar)
        by = {(k.bar, k.ch, k.slot, k.grid) for k in kept}
        # 位置は元のまま（32 分解像度）。SD は 2・4 拍、BD は表拍（1・3 拍）、弱い BD（レベル 1）とタムは消える
        self.assertIn((2, '12', 8, 32), by)
        self.assertIn((2, '12', 24, 32), by)
        self.assertIn((2, '13', 0, 32), by)
        self.assertIn((2, '13', 16, 32), by)
        self.assertNotIn((2, '13', 20, 32), by)
        self.assertFalse(any(k.ch == '14' for k in kept))
        # 同時打ち 1 個: HH の 4 分は全部 BD / SD と重なるので残らない（手足を同時にしない）
        self.assertFalse(any(k.ch == '11' and k.bar == 2 for k in kept))
        # 小節 3 末尾の HH（32 分の拾い）は残っても動かさない（丸めて次の小節頭に移したりしない）
        self.assertFalse(any(k.bar == 4 for k in kept))
        self.assertTrue(all(k.slot == 31 for k in kept if k.bar == 3))
        self.assertEqual(len(kept) + len(removed), len(self.master.notes))
        self.assertTrue(all(k.grid == 32 for k in kept))

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
        self.tmp = Path(tempfile.mkdtemp(prefix='dtx-syrup-'))
        self.folder = self.tmp / 'テスト曲'
        make_song(self.folder)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_clean_names(self):
        self.assertEqual(songs.clean_title('テスト曲「サンプル」', 'ARTIST│歌手「サンプル」'), 'サンプル')
        self.assertEqual(songs.clean_artist('テスト曲「サンプル」', 'ARTIST│歌手「サンプル」'), '歌手')
        self.assertEqual(songs.clean_title('Some Song [Official MV]', 'Band'), 'Some Song')
        self.assertEqual(songs.clean_artist('Some Song [Official MV]', 'Band'), 'Band')

    def test_clean_title_skips_work_name(self):
        """「…」が 2 つあるとき、作品名（アニメ「…」エンディングテーマ）ではなく曲名を取る。"""
        self.assertEqual(songs.clean_title('「バツグンタイプ」 アニメ「ポケットモンスター」エンディングテーマ', 'ポケモン公式YouTubeチャンネル'),
                         'バツグンタイプ')
        self.assertEqual(songs.clean_title('サトシ＆ゴウ「１・２・３」テレビアニメ「ポケットモンスター」オープニングテーマ', ''),
                         '１・２・３')
        self.assertEqual(songs.clean_title('アニメ「ワンピース」主題歌「ウィーアー！」', ''), 'ウィーアー！')
        self.assertEqual(songs.clean_title('「推しの子」OP主題歌 YOASOBI「アイドル」', ''), 'アイドル')
        # 作品名しか無いときは今まで通りそれを使う
        self.assertEqual(songs.clean_title('TVアニメ「ジョジョの奇妙な冒険 黄金の風」 OP映像', ''), 'ジョジョの奇妙な冒険 黄金の風')

    def test_scan_and_generate(self):
        found = songs.scan(self.tmp)
        self.assertEqual(len(found), 1)
        s = found[0]
        self.assertEqual(s.title, 'サンプル')
        self.assertEqual(s.status(), {'beginner': None, 'easy': None})
        summary = s.summary(0)
        self.assertEqual(summary['thumb'], None)
        self.assertAlmostEqual(summary['bgmStart'], 0.5)

        r = songs.generate(s, 'beginner', {'level': 1, 'hh': '2'}, save_rules=True)
        self.assertTrue(r['ok'])
        self.assertEqual(s.status()['beginner'], 'auto')
        saved = json.loads((self.folder / songs.SETTINGS_NAME).read_text(encoding='utf-8'))
        self.assertEqual(saved['rules']['beginner']['level'], 1)
        self.assertEqual(saved['rules']['beginner']['hh'], '2')
        self.assertEqual(saved['rules']['beginner']['sd'], '24')  # 省略分は level の既定で埋まる

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
