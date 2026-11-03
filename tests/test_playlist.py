"""playlist（再生リストの見張り）と、ジョブの進み具合（%）。YouTube と TubeDTX は呼ばない。"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ['DTX_SYRUP_NOTIFY'] = '0'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import playlist  # noqa: E402
import tubedtx  # noqa: E402


class PlaylistUrlTest(unittest.TestCase):
    def test_normalize(self):
        want = 'https://www.youtube.com/playlist?list=PLabcdefghij123'
        self.assertEqual(playlist.playlist_url('https://www.youtube.com/playlist?list=PLabcdefghij123&si=x'), want)
        self.assertEqual(playlist.playlist_url('https://youtube.com/watch?v=abc123XYZ_-&list=PLabcdefghij123&index=2'), want)
        self.assertEqual(playlist.playlist_url('PLabcdefghij123'), want)
        self.assertEqual(playlist.playlist_url('https://www.youtube.com/watch?v=abc123XYZ_-'), '')          # list が無い
        self.assertEqual(playlist.playlist_url('https://www.youtube.com/watch?v=x&list=RDabcdefghijk'), '')  # 自動のミックス


class PendingTest(unittest.TestCase):
    def test_only_new_ones(self):
        found = [{'id': f'v{i}', 'url': f'https://www.youtube.com/watch?v=v{i}', 'title': f't{i}'} for i in range(5)]
        found.append(dict(found[0]))   # 同じ動画が 2 回入っていても 1 回だけ
        r = playlist.pending(found, have={'v1'}, busy={'v2'}, failed={'v3': 2, 'v4': 1})
        self.assertEqual([x['id'] for x in r], ['v0', 'v4'])

    def test_config_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'local.json'
            cfg = playlist.load_config(p)
            self.assertEqual((cfg['playlists'], cfg['interval']), ([], playlist.DEFAULT_INTERVAL))
            cfg['playlists'].append({'url': 'u', 'box': 'こども'})
            playlist.save_config(cfg, p)
            self.assertEqual(playlist.load_config(p)['playlists'], [{'url': 'u', 'box': 'こども'}])


class ProgressTest(unittest.TestCase):
    def test_phases_and_tqdm(self):
        self.assertEqual(len(tubedtx.PHASE_PROGRESS), len(tubedtx.PHASES))
        self.assertEqual(tubedtx.progress('', 'done', None, None), 100)
        self.assertEqual(tubedtx.progress('', 'queued', None, None), 0)
        i = tubedtx.phase_index('separate_music_gr(...)')
        self.assertEqual(tubedtx.progress('x', 'running', i, 1000.0, now=1000.0), 20)          # 分離の始まり
        log = 'separate_music_gr(...)\n 50%|█████     | 10/20\n'
        self.assertEqual(tubedtx.progress(log, 'running', i, 1000.0, now=1000.0), 50)          # demucs の % を使う
        late = tubedtx.progress('download_video_gr(', 'running', 2, 0.0, now=10_000.0)
        self.assertLess(late, tubedtx.PHASE_PROGRESS[3][0])                                    # 長引いても次の段階を超えない


if __name__ == '__main__':
    unittest.main()
