"""アプリの設定の置き場所（利用者ごと）。%LOCALAPPDATA%\\DTX Syrup\\config.json。

exe にしても書ける場所に置く（リポジトリや exe の展開先には書かない）。環境変数があればそれが優先。
  songlist     DTXMania の songlist（曲フォルダの置き場）
  tubedtx_dir  TubeDTX のフォルダ（venv を含む）
"""
from __future__ import annotations

import json
import os
from pathlib import Path

DIR = Path(os.environ.get('DTX_SYRUP_HOME') or Path(os.environ.get('LOCALAPPDATA') or Path.home()) / 'DTX Syrup')
FILE = DIR / 'config.json'
LEGACY_TUBEDTX = Path(r'C:\tools\TubeDTX')           # 手で入れた TubeDTX の置き場（作者の環境）
DEFAULT_SONGLIST = Path.home() / 'Desktop' / 'dtxmania-4.15.1' / 'songlist'


def load() -> dict:
    try:
        return json.loads(FILE.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def save(data: dict) -> None:
    DIR.mkdir(parents=True, exist_ok=True)
    FILE.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')


def update(**kw) -> dict:
    data = load()
    data.update({k: str(v) for k, v in kw.items() if v is not None})
    save(data)
    return data


def songlist() -> Path:
    if os.environ.get('DTX_SYRUP_SONGLIST'):
        return Path(os.environ['DTX_SYRUP_SONGLIST'])
    v = load().get('songlist')
    return Path(v) if v else DEFAULT_SONGLIST


def tubedtx_dir() -> Path:
    if os.environ.get('TUBEDTX_DIR'):
        return Path(os.environ['TUBEDTX_DIR'])
    v = load().get('tubedtx_dir')
    if v:
        return Path(v)
    if (LEGACY_TUBEDTX / 'venv').exists():
        return LEGACY_TUBEDTX
    return DIR / 'TubeDTX'        # 自動セットアップの入れ先


def log_file() -> Path:
    DIR.mkdir(parents=True, exist_ok=True)
    return DIR / 'dtx-syrup.log'
