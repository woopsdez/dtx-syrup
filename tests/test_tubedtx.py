"""tubedtx の純粋関数（URL の掃除、ログの読み取り）。TubeDTX 本体は動かさない。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tubedtx  # noqa: E402


class CleanUrlTest(unittest.TestCase):
    def test_strips_playlist_params(self):
        self.assertEqual(tubedtx.clean_url('https://www.youtube.com/watch?v=xgWr4cKD4AU&list=RDxgWr4cKD4AU&start_radio=1'),
                         'https://www.youtube.com/watch?v=xgWr4cKD4AU')

    def test_short_and_shorts(self):
        self.assertEqual(tubedtx.clean_url('https://youtu.be/abc123XYZ_-?si=zzz'), 'https://www.youtube.com/watch?v=abc123XYZ_-')
        self.assertEqual(tubedtx.clean_url('https://www.youtube.com/shorts/abc123XYZ_-'), 'https://www.youtube.com/watch?v=abc123XYZ_-')

    def test_other_urls_pass_through(self):
        self.assertEqual(tubedtx.clean_url('  https://example.com/x?y=1 '), 'https://example.com/x?y=1')


class SearchParseTest(unittest.TestCase):
    def test_parse_flat_playlist_lines(self):
        text = '\n'.join([
            '{"_type": "url", "id": "abc123XYZ_-", "title": "Song A", "channel": "Ch A", "duration": 215, "view_count": 1000}',
            'not json',
            '{"id": "def456", "title": "Song B", "uploader": "Up B"}',
            '{"_type": "playlist", "id": "ytsearch", "title": "x"}',
        ])
        r = tubedtx.parse_search(text)
        self.assertEqual([x['id'] for x in r], ['abc123XYZ_-', 'def456'])
        self.assertEqual(r[0]['url'], 'https://www.youtube.com/watch?v=abc123XYZ_-')
        self.assertEqual(r[0]['channel'], 'Ch A')
        self.assertEqual(r[1]['channel'], 'Up B')
        self.assertTrue(r[0]['thumb'].endswith('/abc123XYZ_-/mqdefault.jpg'))

    def test_video_id(self):
        self.assertEqual(tubedtx.video_id('https://youtu.be/abc123XYZ_-?si=1'), 'abc123XYZ_-')
        self.assertEqual(tubedtx.video_id('https://example.com/'), '')


class DescribeTest(unittest.TestCase):
    def test_phase_and_403_hint(self):
        log = '\n'.join([
            'new_score_gr(https://www.youtube.com/watch?v=x, )',
            'PROJECT_PATH=C:\\songs\\x',
            'download_video_gr(...)',
            'Traceback (most recent call last):',
            '  File "x.py", line 1, in <module>',
            'yt_dlp.utils.DownloadError: ERROR: unable to download video data: HTTP Error 403: Forbidden',
            'RESULT=fail',
        ])
        d = tubedtx.describe(log, 'failed')
        self.assertEqual(d['phase'], '動画をダウンロード中')
        self.assertIn('403', d['error'])
        self.assertIn('yt-dlp', d['hint'])

    def test_running_phase(self):
        d = tubedtx.describe('new_score_gr(u, )\nPROJECT_PATH=p\ndownload_video_gr(...)\nseparate_music_gr(...)', 'running')
        self.assertEqual(d['phase'], 'ドラムを分離中（数分かかります）')
        self.assertEqual(d['error'], '')
        self.assertEqual(d['hint'], '')


if __name__ == '__main__':
    unittest.main()
