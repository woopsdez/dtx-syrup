"""DTXMania の箱（songlist 直下の DTXFiles.<名前> フォルダ）へ曲フォルダを移す / お気に入り（★）。

お気に入りや分類は道具の中のタグではなく、DTXMania の箱そのもの。★ を付けると曲フォルダを
DTXFiles.★お気に入り へ動かし、外すと元の箱（曲の dtx_syrup.json に box として控える）へ戻す。
移動は同じドライブ内の rename（shutil.move）。DTXMania が起動中は曲フォルダを掴んでいることがあるので断る。
TubeDTX や DTXMania 本体は動かさない。
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import songs as songs_mod

PROCESS_NAME = 'dtxmania.exe'
BUSY_MESSAGE = 'DTXMania が起動中なので曲フォルダを動かせません。DTXMania を終了してからもう一度どうぞ'
_BAD_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


class Busy(Exception):
    """DTXMania が動いているので移動しない。"""


def dtxmania_running() -> bool:
    """DTXMania（dtxmania.exe）が動いているか。Windows 以外では常に False。"""
    if sys.platform != 'win32':
        return False
    try:
        out = subprocess.run(['tasklist', '/FI', f'IMAGENAME eq {PROCESS_NAME}', '/NH', '/FO', 'CSV'],
                             capture_output=True, text=True, timeout=10, creationflags=0x08000000).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return PROCESS_NAME in out.lower()


def guard() -> None:
    if dtxmania_running():
        raise Busy(BUSY_MESSAGE)


def check_box_name(name: str | None) -> str:
    """箱の名前を整える。空 = 箱なし（songlist 直下）。フォルダ名に使えない文字は ValueError。"""
    name = (name or '').strip()
    if not name:
        return ''
    if _BAD_CHARS.search(name) or name in ('.', '..') or name.endswith('.') or len(name) > 80:
        raise ValueError(f'箱の名前に使えません: {name}')
    return name


def resolve_box(root: Path, name: str) -> Path:
    """箱の名前 → フォルダ。既にある箱（box.def のものも）はそれ、無ければ DTXFiles.<名前>（まだ作らない）。"""
    if not name:
        return root
    for p in root.iterdir():
        if songs_mod.is_box(p) and songs_mod.box_title(p) == name:
            return p
    return root / f'{songs_mod.BOX_PREFIX}{name}'


def move_song(root: Path, song: songs_mod.Song, box: str) -> dict:
    """曲フォルダ（zip の包み紙ごと）を箱へ。同じ箱なら何もしない。移動先に同名があれば断る（上書きしない）。"""
    box = check_box_name(box)
    if box == song.box:
        return {'ok': True, 'moved': False, 'box': box, 'dir': song.name}
    unit = song.move_unit()
    dest = resolve_box(root, box)
    target = dest / unit.name
    if target.exists():
        return {'ok': False, 'box': box, 'dir': song.name, 'message': f'移動先に同じ名前のフォルダがあります: {target}'}
    dest.mkdir(parents=True, exist_ok=True)
    shutil.move(str(unit), str(target))
    return {'ok': True, 'moved': True, 'box': box, 'dir': song.name, 'from': str(unit), 'to': str(target)}


def _remember(song: songs_mod.Song, box: str | None) -> None:
    """元の箱の控え（dtx_syrup.json の box）を書く / 消す。移動の前に書く（ファイルはフォルダごと動く）。"""
    if box is None:
        if 'box' not in song.settings:
            return
        song.settings.pop('box')
    else:
        song.settings['box'] = box
    songs_mod.save_settings(song.folder, song.settings)


def set_favorite(root: Path, song: songs_mod.Song, on: bool) -> dict:
    """★ を付ける = ★お気に入り の箱へ移す（元の箱を控える）。外す = 控えた箱へ戻す。"""
    guard()
    if on:
        if song.favorite:
            return {'ok': True, 'moved': False, 'box': song.box, 'dir': song.name}
        before = song.settings.get('box')
        _remember(song, song.box)
        r = move_song(root, song, songs_mod.FAVORITE_BOX)
        if not r['ok']:
            _remember(song, before)
        return r
    if not song.favorite:
        return {'ok': True, 'moved': False, 'box': song.box, 'dir': song.name}
    back = song.settings.get('box', '')
    _remember(song, None)
    r = move_song(root, song, back)
    if not r['ok']:
        r = move_song(root, song, '')   # 元の箱に同名ができていたら songlist 直下へ
    return r


def move(root: Path, targets: list[songs_mod.Song], box: str) -> list[dict]:
    """まとめて箱へ。★お気に入り へ移すときは控えも書く。★ の曲を別の箱へ移したら控えは消す（★ が外れる）。"""
    guard()
    box = check_box_name(box)
    results = []
    for s in targets:
        if box == songs_mod.FAVORITE_BOX:
            results.append(set_favorite(root, s, True))
            continue
        before = s.settings.get('box')
        _remember(s, None)
        r = move_song(root, s, box)
        if not r['ok'] and before is not None:
            _remember(s, before)
        results.append(r)
    return results
