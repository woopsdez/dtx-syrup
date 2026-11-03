"""DTX Syrup.exe を作る（PyInstaller、1 ファイル、コンソール無し）。

    py -3.10 tools\\build_exe.py

ビルド用の仮想環境 .venv-build に PyInstaller を入れて dist\\DTX Syrup.exe を書く（どちらも .gitignore 済み）。
exe は Python が無い PC でも動く。TubeDTX は含まない（初回起動の「設定」で本家から自動で入れる）。
"""
from __future__ import annotations

import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / '.venv-build'
PY = VENV / 'Scripts' / 'python.exe'
SEP = ';'   # Windows の --add-data 区切り


def main() -> int:
    if sys.version_info[:2] != (3, 10):
        print('Python 3.10 で実行してください（例: py -3.10 tools\\build_exe.py）。いまは', sys.version.split()[0])
    if not PY.exists():
        venv.create(VENV, with_pip=True)
    subprocess.check_call([str(PY), '-m', 'pip', 'install', '--quiet', '--upgrade', 'pip', 'pyinstaller'])
    cmd = [str(PY), '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile', '--windowed',
           '--name', 'DTX Syrup', '--icon', str(ROOT / 'assets' / 'icon.ico'),
           '--add-data', f'{ROOT / "web"}{SEP}web',
           '--add-data', f'{ROOT / "tubedtx_driver.py"}{SEP}.',
           '--add-data', f'{ROOT / "assets" / "icon.ico"}{SEP}assets',
           '--distpath', str(ROOT / 'dist'), '--workpath', str(ROOT / 'build'), '--specpath', str(ROOT / 'build'),
           str(ROOT / 'dtx_syrup.py')]
    subprocess.check_call(cmd, cwd=str(ROOT))
    exe = ROOT / 'dist' / 'DTX Syrup.exe'
    print('wrote', exe, f'{exe.stat().st_size / 1e6:.1f} MB')
    return 0


if __name__ == '__main__':
    sys.exit(main())
