"""箱（DTXFiles.*）の走査・移動・お気に入り。本物の songlist には触らず、一時フォルダに箱と曲を作って確かめる。"""
import json
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import boxes  # noqa: E402
import songs  # noqa: E402
from test_core import MASTER, make_song  # noqa: E402

FAV = songs.BOX_PREFIX + songs.FAVORITE_BOX

CHART = '\r\n'.join([
    '#TITLE: 配布の曲',
    '#ARTIST: 誰か',
    '#BPM: 140',
    '#PREIMAGE: rb.JPG',
    '',
    '#00111: 0101',
    '',
]) + '\r\n'


def make_plain_song(folder: Path, setdef: bool = True) -> None:
    """TubeDTX 製でない曲（set.def + 2 譜面。SET.DEF は大文字、Shift_JIS）。"""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'a.dtx').write_bytes(CHART.encode('cp932'))
    (folder / 'b.dtx').write_bytes(CHART.replace('#TITLE: 配布の曲', '#TITLE: 配布の曲 (上)').encode('cp932'))
    (folder / 'rb.JPG').write_bytes(b'\xff\xd8\xff\xd9')
    if setdef:
        (folder / 'SET.DEF').write_bytes('\r\n'.join([
            '#TITLE: 秘密', '', '#L1LABEL: Advanced', '#L1FILE: a.dtx', '', '#L2LABEL: Extreme', '#L2FILE: b.dtx', '',
        ]).encode('cp932'))


class BoxSongs(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='dtxsyrup-box-'))
        make_song(self.tmp / 'loose1')                       # TubeDTX 製、直下
        make_song(self.tmp / 'wrap' / 'loose2')              # TubeDTX 製、zip の包み紙の中
        make_plain_song(self.tmp / 'DTXFiles.J-pop' / 'himitsu' / 'himitsu')   # 配布譜面、箱の中の包み紙
        make_plain_song(self.tmp / 'DTXFiles.Rockband' / 'Aero - Train', setdef=False)
        (self.tmp / 'DTXFiles.アニメ').mkdir()               # 空の箱
        half = self.tmp / 'half'; half.mkdir()               # 途中で止まった TubeDTX（dtx が無い）
        (half / 'tube_dtx_config.json').write_text('{}', encoding='utf-8')
        self.running = False
        self._orig = boxes.dtxmania_running
        boxes.dtxmania_running = lambda: self.running

    def tearDown(self):
        boxes.dtxmania_running = self._orig
        shutil.rmtree(self.tmp, ignore_errors=True)

    def find(self, name: str) -> songs.Song:
        return next(s for s in songs.scan(self.tmp) if s.name == name)

    def test_scan_includes_boxes_and_wrappers(self):
        found = songs.scan(self.tmp)
        self.assertEqual(sorted(s.name for s in found), ['Aero - Train', 'himitsu', 'loose1', 'loose2'])
        by = {s.name: s for s in found}
        self.assertEqual(by['himitsu'].box, 'J-pop')
        self.assertEqual(by['himitsu'].rel, 'DTXFiles.J-pop/himitsu/himitsu')
        self.assertFalse(by['himitsu'].tube)
        self.assertEqual(by['himitsu'].title, '秘密')                    # set.def の #TITLE
        self.assertEqual(by['himitsu'].master_path.name, 'b.dtx')         # 一番上の難易度を代表に
        self.assertEqual([lb for lb, _ in by['himitsu'].levels], ['Advanced', 'Extreme'])
        self.assertEqual(by['Aero - Train'].title, '配布の曲')             # set.def が無ければ dtx の #TITLE
        self.assertEqual(by['Aero - Train'].master_path.name, 'a.dtx')
        self.assertTrue(by['loose2'].tube)
        self.assertEqual(by['loose2'].box, '')
        self.assertEqual(by['loose2'].move_unit().name, 'wrap')            # 包み紙ごと動かす
        self.assertEqual(by['himitsu'].move_unit(), self.tmp / 'DTXFiles.J-pop' / 'himitsu')
        self.assertEqual(by['loose1'].move_unit().name, 'loose1')

    def test_summary_and_boxes(self):
        found = songs.scan(self.tmp)
        sm = next(s for s in found if s.name == 'himitsu').summary(3)
        self.assertEqual((sm['box'], sm['tube'], sm['fav'], sm['levels']), ('J-pop', False, False, ['Advanced', 'Extreme']))
        self.assertEqual(sm['thumb'], '/media/3/rb.JPG')                   # #PREIMAGE
        self.assertGreater(sm['added'], 0)
        self.assertIsNone(sm['lastPlayed'])
        self.assertEqual(sm['has'], {'beginner': None, 'easy': None})
        bx = songs.boxes(self.tmp, found)
        self.assertEqual([(b['name'], b['count']) for b in bx], [('J-pop', 1), ('Rockband', 1), ('アニメ', 0)])

    def test_last_play_in_summary(self):
        s = self.find('loose1')
        songs.save_settings(s.folder, {'plays': {
            'easy': [{'at': '2026-11-01 10:00:00', 'notes': 100, 'miss': 30}],
            'beginner': [{'at': '2026-11-02 09:00:00', 'notes': 50, 'miss': 5}],
        }})
        sm = self.find('loose1').summary(0)
        self.assertEqual(sm['lastPlayed'], '2026-11-02 09:00:00')
        self.assertAlmostEqual(sm['missRate'], 0.1)
        self.assertEqual(sm['playCount'], 2)

    def test_move_to_new_box_and_back(self):
        r = boxes.move(self.tmp, [self.find('loose1'), self.find('loose2')], 'ロック')
        self.assertTrue(all(x['ok'] and x['moved'] for x in r))
        self.assertTrue((self.tmp / 'DTXFiles.ロック' / 'loose1' / 'score.dtx').exists())
        self.assertTrue((self.tmp / 'DTXFiles.ロック' / 'wrap' / 'loose2' / 'score.dtx').exists())
        self.assertEqual({s.name: s.box for s in songs.scan(self.tmp)}['loose2'], 'ロック')
        r = boxes.move(self.tmp, [self.find('loose2')], '')
        self.assertTrue(r[0]['moved'])
        self.assertTrue((self.tmp / 'wrap' / 'loose2' / 'score.dtx').exists())
        self.assertFalse(boxes.move(self.tmp, [self.find('loose1')], 'ロック')[0]['moved'])   # 同じ箱なら何もしない

    def test_move_refusals(self):
        (self.tmp / 'DTXFiles.J-pop' / 'loose1').mkdir()          # 移動先に同名
        r = boxes.move(self.tmp, [self.find('loose1')], 'J-pop')
        self.assertFalse(r[0]['ok'])
        self.assertIn('同じ名前', r[0]['message'])
        self.assertTrue((self.tmp / 'loose1' / 'score.dtx').exists())
        with self.assertRaises(ValueError):
            boxes.move(self.tmp, [self.find('loose1')], '../外')
        self.running = True
        with self.assertRaises(boxes.Busy):
            boxes.move(self.tmp, [self.find('loose1')], 'ロック')
        with self.assertRaises(boxes.Busy):
            boxes.set_favorite(self.tmp, self.find('loose1'), True)
        self.assertFalse((self.tmp / 'DTXFiles.ロック').exists())

    def test_favorite_round_trip(self):
        r = boxes.set_favorite(self.tmp, self.find('himitsu'), True)
        self.assertTrue(r['ok'] and r['moved'])
        moved = self.tmp / FAV / 'himitsu' / 'himitsu'
        self.assertTrue((moved / 'SET.DEF').exists())
        self.assertEqual(json.loads((moved / songs.SETTINGS_NAME).read_text(encoding='utf-8'))['box'], 'J-pop')
        s = self.find('himitsu')
        self.assertTrue(s.favorite)
        self.assertEqual(s.summary(0)['fav'], True)
        self.assertEqual(songs.boxes(self.tmp)[0]['name'], songs.FAVORITE_BOX)   # ★ は一覧の先頭
        r = boxes.set_favorite(self.tmp, s, False)
        self.assertTrue(r['moved'])
        back = self.tmp / 'DTXFiles.J-pop' / 'himitsu' / 'himitsu'
        self.assertTrue((back / 'SET.DEF').exists())
        self.assertNotIn('box', json.loads((back / songs.SETTINGS_NAME).read_text(encoding='utf-8')))
        self.assertFalse(self.find('himitsu').favorite)

    def test_favorite_from_root_and_move_away_clears_memo(self):
        boxes.set_favorite(self.tmp, self.find('loose2'), True)
        self.assertTrue((self.tmp / FAV / 'wrap' / 'loose2' / 'score.dtx').exists())
        self.assertEqual(json.loads((self.tmp / FAV / 'wrap' / 'loose2' / songs.SETTINGS_NAME).read_text(encoding='utf-8'))['box'], '')
        boxes.move(self.tmp, [self.find('loose2')], 'ロック')          # ★ の曲を別の箱へ = ★ が外れる
        s = self.find('loose2')
        self.assertEqual(s.box, 'ロック')
        self.assertNotIn('box', s.settings)
        boxes.move(self.tmp, [s], songs.FAVORITE_BOX)                  # 箱の選択で ★ へ入れても控えが書かれる
        self.assertEqual(self.find('loose2').settings['box'], 'ロック')

    def test_generate_refuses_plain_song(self):
        s = self.find('himitsu')
        before = (s.folder / 'SET.DEF').read_bytes()
        r = songs.generate(s, 'beginner', None)
        self.assertEqual(r.get('skipped'), 'tube')
        self.assertFalse((s.folder / 'score_beginner.dtx').exists())
        self.assertEqual((s.folder / 'SET.DEF').read_bytes(), before)


class BoxApi(unittest.TestCase):
    """server.py の API を実際に HTTP で叩く（空きポート、記録の監視は止める）。"""

    def setUp(self):
        import server
        self.tmp = Path(tempfile.mkdtemp(prefix='dtxsyrup-api-'))
        make_song(self.tmp / 'loose1')
        make_plain_song(self.tmp / 'DTXFiles.J-pop' / 'himitsu')
        self.running = False
        self._orig = boxes.dtxmania_running
        boxes.dtxmania_running = lambda: self.running
        self.srv = server.make_server(self.tmp, 0, watch_records=False)
        self.base = f'http://127.0.0.1:{self.srv.server_address[1]}'
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def tearDown(self):
        self.srv.shutdown(); self.srv.server_close()
        boxes.dtxmania_running = self._orig
        shutil.rmtree(self.tmp, ignore_errors=True)

    def call(self, path, body=None):
        data = json.dumps(body).encode('utf-8') if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, headers={'Content-Type': 'application/json'} if data else {})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, json.loads(r.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode('utf-8'))

    def test_songs_boxes_move_favorite(self):
        st, d = self.call('/api/songs')
        self.assertEqual(st, 200)
        self.assertEqual([s['rel'] for s in d['songs']], ['DTXFiles.J-pop/himitsu', 'loose1'])
        self.assertEqual(d['boxes'], [{'name': 'J-pop', 'count': 1, 'favorite': False}])
        self.assertEqual(d['favoriteBox'], songs.FAVORITE_BOX)
        self.assertEqual([s['tube'] for s in d['songs']], [False, True])
        i_loose = next(s['i'] for s in d['songs'] if s['dir'] == 'loose1')
        st, r = self.call('/api/simplify', {'i': 0, 'diff': 'beginner'})     # 配布譜面は簡易化しない
        self.assertEqual(st, 400)
        self.running = True
        st, r = self.call('/api/move', {'items': [i_loose], 'box': 'ロック'})
        self.assertEqual(st, 409)
        self.assertIn('DTXMania', r['error'])
        self.running = False
        st, r = self.call('/api/move', {'items': [i_loose], 'box': 'ロック'})
        self.assertEqual(st, 200)
        self.assertTrue(r['results'][0]['moved'])
        self.assertEqual([b['name'] for b in r['boxes']], ['J-pop', 'ロック'])
        self.assertTrue((self.tmp / 'DTXFiles.ロック' / 'loose1' / 'score.dtx').exists())
        i_loose = next(s['i'] for s in r['songs'] if s['dir'] == 'loose1')
        st, r = self.call('/api/favorite', {'i': i_loose, 'on': True})
        self.assertEqual(st, 200)
        self.assertTrue((self.tmp / FAV / 'loose1' / 'score.dtx').exists())
        self.assertEqual(r['boxes'][0]['name'], songs.FAVORITE_BOX)
        self.assertTrue(next(s for s in r['songs'] if s['dir'] == 'loose1')['fav'])
        st, r = self.call('/api/move', {'items': [], 'box': 'x'})
        self.assertEqual(st, 400)
        with urllib.request.urlopen(self.base + '/media/0/rb.JPG', timeout=10) as resp:   # #PREIMAGE を配る
            self.assertEqual(resp.headers.get('Content-Type'), 'image/jpeg')
        self.assertEqual(self.call('/media/0/..%2F..%2Fx.jpg')[0], 404)   # 曲フォルダの外は出さない
        self.assertEqual(self.call('/media/0/score.dtx')[0], 404)         # 画像・音源以外も出さない


if __name__ == '__main__':
    unittest.main()
