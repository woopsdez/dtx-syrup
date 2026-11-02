"""TubeDTX を裏で動かす。URL → 曲フォルダ作成 → ダウンロード → 分離 → MIDI → score.dtx → Beginner / Easy。

TubeDTX は Gradio アプリなので、その venv の python で `tubedtx_driver.py` を実行し、
Gradio 用の関数（new_score_gr / _batch_convert_gr）を UI 抜きで呼ぶ。
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import uuid
from pathlib import Path

TUBEDTX_DIR = Path(os.environ.get('TUBEDTX_DIR', r'C:\tools\TubeDTX'))
VENV_PYTHON = TUBEDTX_DIR / 'venv' / 'Scripts' / 'python.exe'
DRIVER = Path(__file__).with_name('tubedtx_driver.py')


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
            return [dict(j, log=j['log'][-4000:]) for j in self.items]

    def start(self, url: str) -> dict:
        job = {'id': uuid.uuid4().hex[:8], 'url': url, 'state': 'queued', 'log': '', 'dir': None,
               'started': time.time(), 'finished': None}
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

    def _run(self, job: dict) -> None:
        import songs as songs_mod  # 循環 import を避ける

        def on_line(line):
            job['log'] += line + '\n'

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
        for d in songs_mod.FILES:
            res = songs_mod.generate(song, d, song.rules(d))
            job['log'] += f"\n{d}: {'ok' if res.get('ok') else res.get('message')}"
        self.state.rescan()
        job['state'] = 'done'
