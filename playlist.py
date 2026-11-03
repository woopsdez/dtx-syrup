"""YouTube の再生リストを見張り、新しく入った動画を自動で譜面にする（TubeDTX → Beginner / Easy）。

子どもがタブレットの YouTube アプリで再生リストに曲を足す → サーバーが定期的に確かめて、
まだ songlist に無い動画だけ TubeDTX のジョブに入れる。できた曲は指定の箱（DTXFiles.<名前>）へ移す。
再生リストは「公開」か「限定公開」にしておく（yt-dlp はログインしないので非公開は読めない）。

設定は %LOCALAPPDATA%\DTX Syrup\playlists.json（個人の URL を公開リポジトリに入れない）:
  {"playlists": [{"url": "...", "box": "こども"}], "interval": 15, "failed": {"<動画ID>": 回数}}
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import tubedtx

import appconfig  # noqa: E402

CONFIG = Path(os.environ.get('DTX_SYRUP_LOCAL') or appconfig.DIR / 'playlists.json')
_LEGACY = Path(__file__).with_name('dtx_syrup.local.json')   # 2026-11-03 まではリポジトリ直下に置いていた
DEFAULT_INTERVAL = 15          # 分
MAX_FAILURES = 2               # 同じ動画は 2 回失敗したらもう試さない
_LIST_ID = re.compile(r'^[A-Za-z0-9_-]{10,64}$')
_UNAVAILABLE = ('[Private video]', '[Deleted video]', '[Unavailable video]')


def playlist_url(url: str) -> str:
    """再生リストの URL（watch?v=…&list=… でも可）を https://www.youtube.com/playlist?list=ID に揃える。違えば ''。"""
    url = (url or '').strip()
    if _LIST_ID.match(url):
        return f'https://www.youtube.com/playlist?list={url}'
    q = parse_qs(urlparse(url).query)
    lid = (q.get('list') or [''])[0]
    if not lid or not _LIST_ID.match(lid) or lid.startswith('RD'):   # RD… は自動生成のミックス
        return ''
    return f'https://www.youtube.com/playlist?list={lid}'


def load_config(path: Path | None = None) -> dict:
    p = path or CONFIG
    if path is None and not p.exists() and _LEGACY.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        _LEGACY.replace(p)
    try:
        data = json.loads(p.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        data = {}
    data.setdefault('playlists', [])
    data.setdefault('interval', DEFAULT_INTERVAL)
    data.setdefault('failed', {})
    return data


def save_config(data: dict, path: Path | None = None) -> None:
    (path or CONFIG).parent.mkdir(parents=True, exist_ok=True)
    (path or CONFIG).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')


def items(url: str, timeout: int = 120) -> list[dict]:
    """再生リストの動画（新しく足したものが後ろ）。非公開・削除済みは除く。"""
    cmd = [str(tubedtx.VENV_PYTHON), '-X', 'utf8', '-m', 'yt_dlp', '--flat-playlist', '-j', '--no-warnings', url]
    env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
    proc = subprocess.run(cmd, cwd=str(tubedtx.TUBEDTX_DIR), env=env, capture_output=True, text=True,
                          encoding='utf-8', errors='replace', timeout=timeout)
    found = [r for r in tubedtx.parse_search(proc.stdout) if r['title'] not in _UNAVAILABLE]
    if not found and proc.returncode != 0:
        err = [ln for ln in proc.stderr.splitlines() if ln.strip()]
        raise RuntimeError(err[-1] if err else f'yt-dlp exited with {proc.returncode}')
    return found


def pending(found: list[dict], have: set[str], busy: set[str], failed: dict[str, int]) -> list[dict]:
    """まだ作っていない動画だけ。songlist にある / ジョブに入っている / 失敗し続けたものは除く。"""
    out, seen = [], set()
    for r in found:
        vid = r['id']
        if vid in have or vid in busy or vid in seen or failed.get(vid, 0) >= MAX_FAILURES:
            continue
        seen.add(vid)
        out.append(r)
    return out


class Syncer(threading.Thread):
    """interval 分ごとに再生リストを確かめる。sync() は UI の「今すぐ確認」からも呼ぶ。"""

    def __init__(self, state, config_path: Path | None = None):
        super().__init__(name='playlist', daemon=True)
        self.state = state
        self.path = config_path or CONFIG
        self.lock = threading.Lock()
        self.last: dict = {}          # url → {'at', 'count', 'started', 'error'}
        self.wake = threading.Event()

    def busy_ids(self) -> set[str]:
        return {tubedtx.video_id(j['url']) for j in self.state.jobs.list() if j['state'] in ('queued', 'running', 'done')}

    def sync(self) -> dict:
        with self.lock:
            cfg = load_config(self.path)
            with self.state.lock:
                have = {s.video_id for s in self.state.songs if s.video_id}
            busy = self.busy_ids()
            report = []
            for pl in cfg['playlists']:
                entry = {'url': pl['url'], 'box': pl.get('box') or '', 'at': time.strftime('%Y-%m-%d %H:%M'), 'count': 0,
                         'started': [], 'error': ''}
                try:
                    found = items(pl['url'])
                    entry['count'] = len(found)
                    for r in pending(found, have, busy, cfg['failed']):
                        self.state.jobs.start(r['url'], box=pl.get('box') or None, title=r['title'], source='playlist')
                        busy.add(r['id'])
                        entry['started'].append(r['title'])
                except Exception as e:  # noqa: BLE001 - 1 つの再生リストの失敗で全体を止めない
                    entry['error'] = str(e)[-300:]
                self.last[pl['url']] = entry
                report.append(entry)
            return {'playlists': report}

    def record_failure(self, url: str) -> None:
        vid = tubedtx.video_id(url)
        if not vid:
            return
        with self.lock:
            cfg = load_config(self.path)
            cfg['failed'][vid] = cfg['failed'].get(vid, 0) + 1
            save_config(cfg, self.path)

    def run(self):
        while True:
            cfg = load_config(self.path)
            if cfg['playlists']:
                self.sync()
            self.wake.wait(max(1, int(cfg.get('interval') or DEFAULT_INTERVAL)) * 60)
            self.wake.clear()
