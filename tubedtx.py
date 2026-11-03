"""TubeDTX を裏で動かす。URL → 曲フォルダ作成 → ダウンロード → 分離 → MIDI → score.dtx → Beginner / Easy。

TubeDTX は Gradio アプリなので、その venv の python で `tubedtx_driver.py` を実行し、
Gradio 用の関数（new_score_gr / _batch_convert_gr）を UI 抜きで呼ぶ。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import parse_qsl, urlparse

TUBEDTX_DIR = Path(os.environ.get('TUBEDTX_DIR', r'C:\tools\TubeDTX'))
VENV_PYTHON = TUBEDTX_DIR / 'venv' / 'Scripts' / 'python.exe'
DRIVER = Path(__file__).with_name('tubedtx_driver.py')

# ログの行 → 今どの段階か。TubeDTX の debug_args が関数呼び出しを 1 行ずつ出すのを利用する
PHASES = [
    ('new_score_gr(', '動画の情報を取得中'),
    ('PROJECT_PATH=', '曲フォルダを用意'),
    ('download_video_gr(', '動画をダウンロード中'),
    ('convert_video_gr(', '音声に変換中'),
    ('create_preview_gr(', 'プレビュー音源を作成中'),
    ('separate_music_gr(', 'ドラムを分離中（数分かかります）'),
    ('convert_to_midi_gr(', 'MIDI に変換中'),
    ('midi_to_dtx_gr(', 'DTX を書き出し中'),
    ('beginner:', 'Beginner / Easy を生成中'),
]
# 進み具合（%）: 段階ごとの開始位置と、ふつうにかかる秒数（実測: URL → 3 難易度で約 4 分、うちドラム分離が大半）
PHASE_PROGRESS = [(0, 5), (2, 3), (4, 25), (12, 10), (16, 6), (20, 150), (80, 25), (90, 8), (96, 6)]
_TQDM = re.compile(r'(\d{1,3})%\|')


def progress(log: str, state: str, phase_i: int | None, phase_at: float | None, now: float | None = None) -> int:
    """0〜100。段階の位置 + 段階内は経過時間（ドラム分離は demucs の % 表示があればそれ）で埋める。"""
    if state == 'done':
        return 100
    if phase_i is None or phase_i < 0:
        return 0
    start, expect = PHASE_PROGRESS[phase_i]
    end = PHASE_PROGRESS[phase_i + 1][0] if phase_i + 1 < len(PHASE_PROGRESS) else 99
    frac = min(0.95, max(0.0, ((now or time.time()) - (phase_at or time.time())) / expect))
    if PHASES[phase_i][0] == 'separate_music_gr(':
        seen = _TQDM.findall(log[log.rfind('separate_music_gr('):])
        if seen:
            frac = min(1.0, int(seen[-1]) / 100)
    return int(start + (end - start) * frac)


def phase_index(line: str) -> int | None:
    for i, (key, _name) in enumerate(PHASES):
        if key in line:
            return i
    return None


HINTS = [
    ('HTTP Error 403', 'YouTube に拒否されました（403）。TubeDTX の yt-dlp が古いときに起きます。venv で yt-dlp を更新すると直ります'),
    ('Sign in to confirm', 'YouTube がボット判定しています。しばらく待つか yt-dlp を更新してください'),
    ('すでに同名ディレクトリ', '同じ曲のフォルダが既にあります'),
]


def clean_url(url: str) -> str:
    """YouTube の URL を watch?v=ID だけにする（list / start_radio / si / t を落とす）。youtu.be や shorts も直す。"""
    url = (url or '').strip()
    pr = urlparse(url)
    host = (pr.netloc or '').lower()
    parts = [p for p in pr.path.split('/') if p]
    if host.endswith('youtu.be') and parts:
        return f'https://www.youtube.com/watch?v={parts[0]}'
    if 'youtube.com' in host:
        if len(parts) >= 2 and parts[0] in ('shorts', 'live', 'embed'):
            return f'https://www.youtube.com/watch?v={parts[1]}'
        vid = dict(parse_qsl(pr.query)).get('v')
        if vid:
            return f'https://www.youtube.com/watch?v={vid}'
    return url


def video_id(url: str) -> str:
    """YouTube の URL から動画 ID。取れなければ ''。"""
    u = clean_url(url)
    return u.split('watch?v=', 1)[1] if 'watch?v=' in u else ''


def parse_search(text: str) -> list[dict]:
    """yt-dlp -j --flat-playlist の出力（1 行 1 JSON）を検索結果に整える。"""
    out: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith('{'):
            continue
        try:
            e = json.loads(line)
        except ValueError:
            continue
        vid = e.get('id')
        if not vid or e.get('_type') not in (None, 'url', 'video'):
            continue
        out.append({
            'id': vid,
            'url': f'https://www.youtube.com/watch?v={vid}',
            'title': e.get('title') or '',
            'channel': e.get('channel') or e.get('uploader') or '',
            'duration': e.get('duration'),
            'views': e.get('view_count'),
            'thumb': f'https://i.ytimg.com/vi/{vid}/mqdefault.jpg',
        })
    return out


def search(query: str, n: int = 12, timeout: int = 60) -> list[dict]:
    """YouTube を yt-dlp の ytsearch で検索する（API キー不要）。TubeDTX venv の yt-dlp を使う。"""
    query = (query or '').strip()
    if not query:
        return []
    cmd = [str(VENV_PYTHON), '-X', 'utf8', '-m', 'yt_dlp', '--flat-playlist', '-j', '--no-warnings', f'ytsearch{int(n)}:{query}']
    env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
    proc = subprocess.run(cmd, cwd=str(TUBEDTX_DIR), env=env, capture_output=True, text=True,
                          encoding='utf-8', errors='replace', timeout=timeout)
    results = parse_search(proc.stdout)
    if not results and proc.returncode != 0:
        err = [ln for ln in proc.stderr.splitlines() if ln.strip()]
        raise RuntimeError(err[-1] if err else f'yt-dlp exited with {proc.returncode}')
    return results


def describe(log: str, state: str) -> dict:
    """ジョブのログから、段階・失敗の要点・直し方のヒントを拾う（UI の表示用）。"""
    lines = [ln for ln in log.splitlines() if ln.strip()]
    phase = ''
    for ln in lines:
        for key, name in PHASES:
            if key in ln:
                phase = name
    error = ''
    if state == 'failed':
        for ln in reversed(lines):
            if ln.startswith('RESULT=') or ln.startswith('  File') or ln.startswith('Traceback'):
                continue
            if re.search(r'Error|Exception|失敗|エラー|ありません', ln):
                error = ln.strip()[:200]
                break
        if not error and lines:
            error = lines[-1].strip()[:200]
    hint = next((h for key, h in HINTS if key in log), '')
    return {'phase': phase, 'error': error, 'hint': hint}


def available() -> dict:
    """TubeDTX が使える状態か。UI の「作る」ボタンの可否と、check コマンドに使う。"""
    cfg = TUBEDTX_DIR / 'config.json'
    workspace = None
    if cfg.exists():
        try:
            workspace = json.loads(cfg.read_text(encoding='utf-8')).get('workspace_path')
        except (OSError, ValueError):
            workspace = None
    ok = TUBEDTX_DIR.exists() and VENV_PYTHON.exists() and DRIVER.exists()
    return {'ok': ok, 'dir': str(TUBEDTX_DIR), 'python': str(VENV_PYTHON), 'workspace': workspace}


def command(url: str, dry_run: bool = False) -> list[str]:
    cmd = [str(VENV_PYTHON), '-X', 'utf8', str(DRIVER), url]
    if dry_run:
        cmd.append('--dry-run')
    return cmd


def run(url: str, on_line=None, dry_run: bool = False) -> dict:
    """同期実行。stdout を 1 行ずつ on_line に渡し、PROJECT_PATH= と RESULT= を拾う。"""
    env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
    proc = subprocess.Popen(command(url, dry_run), cwd=str(TUBEDTX_DIR), env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            encoding='utf-8', errors='replace', bufsize=1)
    project_path, result = None, None
    lines: list[str] = []
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.rstrip('\r\n')
        lines.append(line)
        if line.startswith('PROJECT_PATH='):
            project_path = line[len('PROJECT_PATH='):]
        elif line.startswith('RESULT='):
            result = line[len('RESULT='):]
        if on_line:
            on_line(line)
    code = proc.wait()
    return {'ok': code == 0 and result != 'fail', 'code': code, 'project_path': project_path, 'log': '\n'.join(lines)}


class Jobs:
    """add の実行状態。1 本ずつ順に動かす（分離は重いので並列にしない）。"""

    def __init__(self, state):
        self.state = state
        self.items: list[dict] = []
        self.lock = threading.Lock()
        self.worker: threading.Thread | None = None

    def list(self) -> list[dict]:
        with self.lock:
            return [dict(j, log=j['log'][-4000:], **describe(j['log'], j['state']),
                         percent=progress(j['log'], j['state'], j.get('phase_i'), j.get('phase_at')))
                    for j in self.items]

    def start(self, url: str, box: str | None = None, title: str = '', source: str = 'manual') -> dict:
        """box: できた曲を移す箱（DTXFiles.<box>）。source: 'manual'（UI / CLI）か 'playlist'（再生リストの見張り）。"""
        url = clean_url(url)
        with self.lock:
            for j in self.items:  # 同じ URL が動いていれば二重に始めない
                if j['url'] == url and j['state'] in ('queued', 'running'):
                    return dict(j)
        job = {'id': uuid.uuid4().hex[:8], 'url': url, 'state': 'queued', 'log': '', 'dir': None,
               'started': time.time(), 'finished': None, 'box': box, 'title': title, 'source': source}
        with self.lock:
            self.items.append(job)
            if self.worker is None or not self.worker.is_alive():
                self.worker = threading.Thread(target=self._loop, daemon=True)
                self.worker.start()
        return dict(job)

    def _next(self) -> dict | None:
        with self.lock:
            for j in self.items:
                if j['state'] == 'queued':
                    j['state'] = 'running'
                    return j
        return None

    def _loop(self) -> None:
        while (job := self._next()) is not None:
            try:
                self._run(job)
            except Exception as e:  # noqa: BLE001
                job['state'] = 'failed'
                job['log'] += f'\n{e}'
            job['finished'] = time.time()
            self._finished(job)

    def _finished(self, job: dict) -> None:
        """できた / 失敗したことを Windows の通知で知らせる（ブラウザを開いていなくても気づける）。"""
        import notify
        name = job.get('song') or job.get('title') or job.get('dir') or job['url']
        if job['state'] == 'done':
            where = f"（箱: {job['box']}）" if job.get('moved') else ''
            notify.toast('DTX Syrup: 譜面ができました', f'{name}{where} — DTXMania を起動し直すと選べます')
            return
        notify.toast('DTX Syrup: 譜面を作れませんでした',
                     f"{name} — {describe(job['log'], 'failed').get('error') or '詳しくは画面のログで'}")
        syncer = getattr(self.state, 'playlists', None)
        if syncer is not None and job.get('source') == 'playlist':
            syncer.record_failure(job['url'])

    def _run(self, job: dict) -> None:
        import songs as songs_mod  # 循環 import を避ける

        def on_line(line):
            job['log'] += line + '\n'
            i = phase_index(line)
            if i is not None and i != job.get('phase_i'):
                job['phase_i'], job['phase_at'] = i, time.time()

        r = run(job['url'], on_line)
        if not r['ok'] or not r['project_path']:
            job['state'] = 'failed'
            return
        folder = Path(r['project_path'])
        job['dir'] = folder.name
        self.state.rescan()
        song = next((s for s in self.state.songs if s.folder == folder), None)
        if song is None:
            job['state'] = 'failed'
            job['log'] += '\nscore.dtx が見つかりません'
            return
        job['phase_i'], job['phase_at'] = len(PHASES) - 1, time.time()
        for d in songs_mod.FILES:
            res = songs_mod.generate(song, d, song.rules(d))
            job['log'] += f"\n{d}: {'ok' if res.get('ok') else res.get('message')}"
        job['song'] = song.title
        if job.get('box'):   # 再生リストごとの箱へ。DTXMania が起動中なら移さず songlist 直下に置いたまま
            import boxes
            try:
                r = boxes.move(self.state.root, [song], job['box'])[0]
                job['moved'] = bool(r.get('ok'))
                job['log'] += f"\n箱へ移動: {r.get('to') or r.get('message')}"
            except Exception as e:  # noqa: BLE001
                job['log'] += f'\n箱へ移せませんでした（あとで「箱へ移す」で）: {e}'
        self.state.rescan()
        job['state'] = 'done'
