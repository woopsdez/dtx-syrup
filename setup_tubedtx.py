"""TubeDTX を自動で入れる（同梱はしない。本家 GitHub から取ってきて、TubeDTX の setup.bat と同じ手順を踏む）。

1. Python 3.10 を探す（無ければ winget で入れる。TubeDTX は TensorFlow の都合で 3.10 が要る）
2. git を探す（無ければ winget で入れる）
3. kidonaru/TubeDTX を clone し、動作を確かめたコミットに合わせてサブモジュールも取る
4. venv を作り、requirements.txt と 3 つのサブモジュール（pytube / magenta / pyfluidsynth）を入れる（約 3 GB）
5. yt-dlp を最新に（古いと YouTube が 403 を返す）
6. TubeDTX の保存先（workspace_path）を songlist にし、DTX Syrup の設定に TubeDTX の場所を書く

TubeDTX: https://github.com/kidonaru/TubeDTX（Apache-2.0、kidonaru 氏）。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

import appconfig
import tubedtx

REPO = 'https://github.com/kidonaru/TubeDTX.git'
TESTED_COMMIT = 'f5310a957df9eb8254a6b23f4b350d5dbb66b194'   # v1.4.0。DTX Syrup のドライバはこの版の関数を呼ぶ
WINGET_ARGS = ['--silent', '--accept-package-agreements', '--accept-source-agreements', '--disable-interactivity']
STEPS = [   # (キー, 表示, 全体に占める %)
    ('python', 'Python 3.10 を用意', 4),
    ('git', 'git を用意', 3),
    ('clone', 'TubeDTX を取ってくる', 8),
    ('venv', 'TubeDTX 用の Python 環境を作る', 4),
    ('pip', '部品を入れる（約 3 GB。いちばん長い）', 66),
    ('modules', 'TubeDTX の部品（pytube / magenta / pyfluidsynth）を入れる', 9),
    ('ytdlp', 'yt-dlp を最新にする', 3),
    ('config', '保存先を設定', 3),
]
PIP_EXPECTED = 150   # requirements.txt で入る部品のおおよその数（「Collecting」の行数）
_NOWIN = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def find_python310() -> str | None:
    try:
        out = subprocess.run(['py', '-3.10', '-c', 'import sys;print(sys.executable)'], capture_output=True, text=True,
                             timeout=20, creationflags=_NOWIN)
        p = out.stdout.strip()
        if out.returncode == 0 and p and Path(p).exists():
            return p
    except (OSError, subprocess.TimeoutExpired):
        pass
    for c in (r'%LOCALAPPDATA%\Programs\Python\Python310\python.exe', r'%ProgramFiles%\Python310\python.exe', r'C:\Python310\python.exe'):
        c = os.path.expandvars(c)
        if Path(c).exists():
            return c
    return None


def find_git() -> str | None:
    p = shutil.which('git')
    if p:
        return p
    c = os.path.expandvars(r'%ProgramFiles%\Git\cmd\git.exe')
    return c if Path(c).exists() else None


def has_winget() -> bool:
    return shutil.which('winget') is not None


def ytdlp_version(venv_python: Path) -> str | None:
    if not venv_python.exists():
        return None
    try:
        out = subprocess.run([str(venv_python), '-m', 'yt_dlp', '--version'], capture_output=True, text=True,
                             timeout=60, creationflags=_NOWIN)
        return out.stdout.strip() or None
    except (OSError, subprocess.TimeoutExpired):
        return None


def check(songlist: Path, target: Path | None = None) -> dict:
    """セットアップ画面の確認欄。重い確認（yt-dlp の版）は含めない。"""
    target = target or tubedtx.TUBEDTX_DIR
    venv = target / 'venv' / 'Scripts' / 'python.exe'
    try:
        free = shutil.disk_usage(target.anchor or '/').free / 1e9
    except OSError:
        free = None
    dtxmania = songlist.parent / 'dtxmania.exe'
    return {
        'python310': find_python310(),
        'git': find_git(),
        'winget': has_winget(),
        'tubedtx': {'dir': str(target), 'cloned': (target / 'scripts').exists(), 'venv': venv.exists(),
                    'ok': tubedtx.available()['ok'] and Path(tubedtx.TUBEDTX_DIR) == target},
        'songlist': {'path': str(songlist), 'exists': songlist.exists()},
        'dtxmania': {'exe': str(dtxmania), 'exists': dtxmania.exists()},
        'diskFreeGB': round(free, 1) if free is not None else None,
        'needGB': 5,
    }


class Setup:
    """1 回分のセットアップ。thread で回し、state / step / percent / log を画面に出す。"""

    def __init__(self, songlist: Path, target: Path | None = None):
        self.songlist = Path(songlist)
        self.target = Path(target or appconfig.tubedtx_dir())
        self.state = 'idle'        # idle / running / done / failed
        self.step = ''
        self.percent = 0
        self.log = ''
        self.error = ''
        self.thread: threading.Thread | None = None
        self._pip_seen = 0

    def as_dict(self) -> dict:
        return {'state': self.state, 'step': self.step, 'percent': self.percent, 'log': self.log[-6000:],
                'error': self.error, 'dir': str(self.target)}

    def start(self) -> None:
        if self.state == 'running':
            return
        self.state, self.error, self.log, self.percent = 'running', '', '', 0
        self.thread = threading.Thread(target=self.run, name='setup-tubedtx', daemon=True)
        self.thread.start()

    # ---- 中身 ----
    def _emit(self, line: str) -> None:
        self.log += line.rstrip() + '\n'
        if self.step == 'pip' and line.startswith('Collecting '):
            self._pip_seen += 1
            self._set_frac(min(0.95, self._pip_seen / PIP_EXPECTED))

    def _set_frac(self, frac: float) -> None:
        done = 0
        for key, _name, w in STEPS:
            if key == self.step:
                self.percent = int(done + w * frac)
                return
            done += w

    def _sh(self, cmd: list[str], cwd: Path | None = None, ok_codes=(0,), tries: int = 1) -> int:
        """tries: ネットワークの一時的な失敗に備えて、取ってくる系（git / pip）は 3 回まで試す。"""
        for n in range(1, tries + 1):
            try:
                return self._sh_once(cmd, cwd, ok_codes)
            except RuntimeError:
                if n == tries:
                    raise
                self._emit(f'… 失敗したのでもう一度（{n + 1} 回目）')
                time.sleep(3 * n)
        return 0

    def _sh_once(self, cmd: list[str], cwd: Path | None, ok_codes) -> int:
        self._emit('> ' + ' '.join(str(c) for c in cmd))
        env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1', PIP_DISABLE_PIP_VERSION_CHECK='1',
                   GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='never')
        proc = subprocess.Popen([str(c) for c in cmd], cwd=str(cwd) if cwd else None, env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', creationflags=_NOWIN)
        assert proc.stdout is not None
        for line in proc.stdout:
            self._emit(line)
        code = proc.wait()
        if code not in ok_codes:
            raise RuntimeError(f'{Path(str(cmd[0])).name} が失敗しました（終了コード {code}）')
        return code

    def run(self) -> None:
        try:
            for key, name, _w in STEPS:
                self.step = key
                self._set_frac(0)
                self._emit(f'== {name}')
                getattr(self, f'_step_{key}')()
            self.step, self.percent, self.state = 'done', 100, 'done'
            self._emit('== できました')
        except Exception as e:  # noqa: BLE001 - 画面に理由を出して止める
            self.state, self.error = 'failed', str(e)
            self._emit(f'!! {e}')
        try:
            import notify
            notify.toast('DTX Syrup: TubeDTX のセットアップ' + ('が終わりました' if self.state == 'done' else 'に失敗しました'),
                         '曲を YouTube から作れるようになりました' if self.state == 'done' else self.error)
        except Exception:  # noqa: BLE001
            pass

    def _step_python(self) -> None:
        self.py = find_python310()
        if not self.py:
            if not has_winget():
                raise RuntimeError('Python 3.10 がありません。https://www.python.org/downloads/release/python-31011/ から入れてください')
            self._sh(['winget', 'install', '-e', '--id', 'Python.Python.3.10', '--scope', 'user', *WINGET_ARGS], ok_codes=(0, -1978335189))
            self.py = find_python310()
        if not self.py:
            raise RuntimeError('Python 3.10 を入れられませんでした')
        self._emit(f'Python 3.10: {self.py}')

    def _step_git(self) -> None:
        self.git = find_git()
        if not self.git:
            if not has_winget():
                raise RuntimeError('git がありません。https://git-scm.com/download/win から入れてください')
            self._sh(['winget', 'install', '-e', '--id', 'Git.Git', *WINGET_ARGS], ok_codes=(0, -1978335189))
            self.git = find_git()
        if not self.git:
            raise RuntimeError('git を入れられませんでした（入れたあと DTX Syrup を起動し直すと見つかることがあります）')
        self._emit(f'git: {self.git}')

    def _step_clone(self) -> None:
        if not (self.target / '.git').exists():
            if self.target.exists() and any(self.target.iterdir()):
                raise RuntimeError(f'入れ先のフォルダが空ではありません: {self.target}')
            self.target.parent.mkdir(parents=True, exist_ok=True)
            self._sh([self.git, 'clone', REPO, str(self.target)], tries=3)
        self._sh([self.git, '-C', str(self.target), 'checkout', '-q', TESTED_COMMIT])
        self._sh([self.git, '-C', str(self.target), 'submodule', 'update', '--init', '--recursive'], tries=3)

    def _step_venv(self) -> None:
        self.vpy = self.target / 'venv' / 'Scripts' / 'python.exe'
        if not self.vpy.exists():
            self._sh([self.py, '-m', 'venv', str(self.target / 'venv')])
        self._sh([self.vpy, '-m', 'pip', 'install', '--upgrade', 'pip'])

    def _step_pip(self) -> None:
        self._pip_seen = 0
        self._sh([self.vpy, '-m', 'pip', 'install', '--upgrade', '-r', 'requirements.txt'], cwd=self.target, tries=3)

    def _step_modules(self) -> None:
        for sub, extra in (('pytube', []), ('magenta', ['--no-dependencies']), ('pyfluidsynth', [])):
            self._sh([self.vpy, '-m', 'pip', 'install', '-e', '.', *extra], cwd=self.target / 'modules' / sub)

    def _step_ytdlp(self) -> None:
        self._sh([self.vpy, '-m', 'pip', 'install', '--upgrade', 'yt-dlp'], tries=3)

    def _step_config(self) -> None:
        cfg_path = self.target / 'config.json'
        try:
            cfg = json.loads(cfg_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            cfg = {}
        cfg['workspace_path'] = str(self.songlist)
        cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=4), encoding='utf-8')
        version = (self.target / 'VERSION')
        if version.exists():   # TubeDTX の run.bat が「セットアップ済み」と判断する印
            (self.target / '.locel_version').write_text(version.read_text(encoding='utf-8'), encoding='utf-8')
        self.songlist.mkdir(parents=True, exist_ok=True)
        appconfig.update(tubedtx_dir=self.target, songlist=self.songlist)
        tubedtx.set_dir(self.target)
        self._emit(f'TubeDTX: {self.target}\n保存先（songlist）: {self.songlist}')


_WINDOWS_BAD = re.compile(r'[<>"|?*]')


def valid_dir(p: str) -> Path | None:
    p = (p or '').strip().strip('"')
    if not p or _WINDOWS_BAD.search(p[2:] if len(p) > 2 else p):
        return None
    return Path(os.path.expandvars(os.path.expanduser(p)))
