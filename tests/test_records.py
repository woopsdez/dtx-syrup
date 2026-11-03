"""records: DTXMania の RecordDB を曲ごとの履歴に写す。本物の DB には触らず、一時フォルダに作る。"""
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import records  # noqa: E402
import songs  # noqa: E402

SCHEMA = ('CREATE TABLE Records( Key INTEGER NOT NULL PRIMARY KEY, ScorePath NVARCHAR NOT NULL, Timestamp TEXT NOT NULL, '
          'TotalNotes INTEGER NOT NULL, Perfect INTEGER NOT NULL, Great INTEGER NOT NULL, Good INTEGER NOT NULL, Ok INTEGER NOT NULL, '
          'Miss INTEGER NOT NULL, MaxCombo INTEGER NOT NULL, CountMap NVARCHAR NOT NULL, IdealCountMap NVARCHAR NOT NULL, '
          'AutoLeftCrash INTEGER NOT NULL, AutoHiHat INTEGER NOT NULL, AutoFoot INTEGER NOT NULL, AutoSnare INTEGER NOT NULL, '
          'AutoBass INTEGER NOT NULL, AutoTom1 INTEGER NOT NULL, AutoTom2 INTEGER NOT NULL, AutoTom3 INTEGER NOT NULL, '
          'AutoRightCrash INTEGER NOT NULL, IdealPerfect INTEGER NOT NULL, IdealGreat INTEGER NOT NULL, IdealMaxCombo INTEGER NOT NULL)')
MASTER = '\r\n'.join(['; Created by TubeDTX', '', '#TITLE: 曲「テスト」', '#BPM: 120', '#DLEVEL: 50', '',
                      '#00211: ' + '05' + '00' * 31, ''])


class RecordsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='pd-rec-'))
        self.folder = self.tmp / 'song'
        self.folder.mkdir()
        (self.folder / 'tube_dtx_config.json').write_text('{}', encoding='utf-8')
        (self.folder / 'score.dtx').write_bytes(MASTER.encode('cp932'))
        (self.folder / 'score_easy.dtx').write_bytes(('; Created by TubeDTX\r\n; play-dtxmania easy {"grid": 8}\r\n#TITLE: x\r\n#BPM: 120\r\n').encode('cp932'))
        self.db = self.tmp / 'RecordDB.sqlite3'
        con = sqlite3.connect(self.db)
        con.execute(SCHEMA)
        rows = [
            (1, '\\\\?\\' + str(self.folder / 'score_easy.dtx'), '2026-11-03 23:05:56.429965', 322, 70, 41, 34, 44, 133, 5, 'C' * 64, 'C' * 64),
            (2, '\\\\?\\' + str(self.folder / 'score.dtx'), '2026-11-03 23:03:33.416638', 493, 78, 51, 17, 45, 302, 4, '1' * 64, '1' * 64),
            (3, '\\\\?\\' + str(self.tmp / 'other' / 'score.dtx'), '2026-11-03 23:00:00.000000', 10, 1, 1, 1, 1, 6, 1, 'C' * 64, 'C' * 64),
        ]
        for r in rows:
            con.execute('insert into Records values (' + ','.join('?' * 24) + ')', r + (0,) * 9 + (0, 0, 0))
        con.commit()
        con.close()

    def test_ingest_adds_once(self):
        found = songs.scan(self.tmp)
        added = records.ingest(found, self.db)
        self.assertEqual(sorted(d for _s, d, _p in added), ['easy', 'master'])
        s = json.loads((self.folder / songs.SETTINGS_NAME).read_text('utf-8'))
        easy = s['plays']['easy'][0]
        self.assertEqual((easy['notes'], easy['miss'], easy['combo'], easy['file']), (322, 133, 5, 'score_easy.dtx'))
        self.assertEqual(easy['rules'], {'grid': 8})          # 譜面の印からそのときのルールを控える
        self.assertEqual(easy['key'], '2026-11-03 23:05:56.429965')
        self.assertRegex(easy['at'], r'^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d$')
        self.assertIsNone(s['plays']['master'][0]['rules'])  # TubeDTX 製の Master には印が無い
        # 2 回目は増えない
        self.assertEqual(records.ingest(songs.scan(self.tmp), self.db), [])
        self.assertEqual(len(json.loads((self.folder / songs.SETTINGS_NAME).read_text('utf-8'))['plays']['easy']), 1)

    def test_legacy_settings_name_is_renamed(self):
        old = self.folder / 'play_dtxmania.json'
        old.write_text('{"title": "x"}', encoding='utf-8')
        self.assertEqual(songs.load_settings(self.folder), {'title': 'x'})
        self.assertFalse(old.exists())
        self.assertTrue((self.folder / songs.SETTINGS_NAME).exists())
        self.assertEqual(records.marker_params(self.folder / 'score_easy.dtx'), {'grid': 8})   # 改名前の印も読める

    def test_latest_and_normalize(self):
        self.assertEqual(records.normalize_path('\\\\?\\C:\\A\\b\\c.dtx'), records.normalize_path('c:/a/B/c.dtx'))
        self.assertEqual(records.latest({'plays': {'easy': [{'miss': 1}, {'miss': 2}], 'master': []}}),
                         {'easy': {'miss': 2}, 'master': None})

    def test_watcher_parses_change_buffer(self):
        name = 'RecordDB.sqlite3-journal'.encode('utf-16-le')
        buf = (0).to_bytes(4, 'little') + (3).to_bytes(4, 'little') + len(name).to_bytes(4, 'little') + name
        self.assertTrue(records.Watcher._mentions_db(buf))
        other = 'Configuration.yaml'.encode('utf-16-le')
        buf2 = (0).to_bytes(4, 'little') + (3).to_bytes(4, 'little') + len(other).to_bytes(4, 'little') + other
        self.assertFalse(records.Watcher._mentions_db(buf2))


if __name__ == '__main__':
    unittest.main()
