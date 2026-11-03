"""DTXMania の演奏記録（RecordDB.sqlite3）を曲ごとの履歴に写す。

DTXMania 4 は結果画面のときに RecordDB.sqlite3 を書くが、譜面ごとに最後の 1 回しか残さない
（判定数・最大コンボ・曲を 64 区間に割ったミスの地図。レーン別は無い）。
ここでは DTXMania4 フォルダの書き込みを監視し、新しい記録を曲フォルダの dtx_syrup.json の
plays[難易度] に追記する。監視は ReadDirectoryChangesW（書き込みがあったときだけ動く）。
"""
from __future__ import annotations

import ctypes
import json
import os
import shutil
import sqlite3
import struct
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path

import dtx
import songs as songs_mod

DTXMANIA_DATA = Path(os.environ.get('DTX_SYRUP_DTXDATA') or (Path(os.environ.get('LOCALAPPDATA', '.')) / 'DTXMania4'))
RECORD_DB = 'RecordDB.sqlite3'
COLUMNS = ('ScorePath', 'Timestamp', 'TotalNotes', 'Perfect', 'Great', 'Good', 'Ok', 'Miss', 'MaxCombo', 'CountMap',
           'AutoLeftCrash', 'AutoHiHat', 'AutoFoot', 'AutoSnare', 'AutoBass', 'AutoTom1', 'AutoTom2', 'AutoTom3', 'AutoRightCrash')


def normalize_path(p: str) -> str:
    """DTXMania の ScorePath（\\\\?\\ 付き）を比較用に揃える。"""
    if p.startswith('\\\\?\\'):
        p = p[4:]
    return os.path.normcase(os.path.normpath(p))


def to_local(ts: str) -> str:
    """RecordDB の Timestamp は「ローカル時刻 + UTC オフセット」で入っている（4.15.1 で確認）。ローカル時刻に戻す。"""
    try:
        t = datetime.fromisoformat(ts[:26])
    except ValueError:
        return ts
    off = datetime.now().astimezone().utcoffset()
    return (t - off).isoformat(sep=' ', timespec='seconds') if off else ts[:19]


def read_records(db: Path) -> list[dict]:
    """RecordDB を一時ファイルに写してから読む（DTXMania が開いていても邪魔しない）。"""
    if not db.exists():
        return []
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / RECORD_DB
        shutil.copyfile(db, copy)
        con = sqlite3.connect(copy)
        try:
            rows = con.execute(f'select {", ".join(COLUMNS)} from Records').fetchall()
        finally:
            con.close()
    return [dict(zip(COLUMNS, r)) for r in rows]


def marker_params(path: Path) -> dict | None:
    """DTX Syrup が書いた譜面なら、2 行目の印からそのときのルールを取り出す。"""
    try:
        head = dtx.read_text_guess(path).splitlines()[:5]
    except OSError:
        return None
    for ln in head:
        marker = next((m for m in dtx.MARKERS if ln.startswith(m)), None)
        if marker:
            rest = ln[len(marker):].strip()
            i = rest.find('{')
            if i >= 0:
                try:
                    return json.loads(rest[i:])
                except ValueError:
                    return None
    return None


def to_play(row: dict, chart: Path) -> dict:
    return {
        'key': row['Timestamp'],
        'at': to_local(row['Timestamp']),
        'file': chart.name,
        'notes': row['TotalNotes'],
        'perfect': row['Perfect'], 'great': row['Great'], 'good': row['Good'], 'ok': row['Ok'], 'miss': row['Miss'],
        'combo': row['MaxCombo'],
        'map': row['CountMap'],
        'auto': any(row[c] for c in COLUMNS if c.startswith('Auto')),
        'rules': marker_params(chart),
    }


def difficulty_of(song: songs_mod.Song, filename: str) -> str | None:
    for d, fn in songs_mod.FILES.items():
        if filename.lower() == fn:
            return d
    if filename.lower() == song.master_path.name.lower():
        return 'master'
    return None


def ingest(found: list[songs_mod.Song], db: Path | None = None) -> list[tuple[songs_mod.Song, str, dict]]:
    """新しい記録を各曲の dtx_syrup.json に追記し、追記した分を返す。"""
    db = db or (DTXMANIA_DATA / RECORD_DB)
    by_folder = {normalize_path(str(s.folder)): s for s in found}
    added = []
    touched: dict[Path, dict] = {}
    for row in read_records(db):
        p = normalize_path(row['ScorePath'])
        song = by_folder.get(os.path.dirname(p))
        if song is None:
            continue
        chart = song.folder / os.path.basename(row['ScorePath'])
        diff = difficulty_of(song, chart.name)
        if diff is None:
            continue
        settings = touched.get(song.folder) or songs_mod.load_settings(song.folder)
        plays = settings.setdefault('plays', {}).setdefault(diff, [])
        if any(pl.get('key') == row['Timestamp'] for pl in plays):
            continue
        play = to_play(row, chart)
        plays.append(play)
        plays.sort(key=lambda pl: pl['key'])
        touched[song.folder] = settings
        added.append((song, diff, play))
    for folder, settings in touched.items():
        songs_mod.save_settings(folder, settings)
    return added


def latest(settings: dict) -> dict:
    """難易度ごとの直近の記録（UI の一覧用）。"""
    return {d: (pl[-1] if pl else None) for d, pl in settings.get('plays', {}).items()}


# ---- 監視 ----
_FILE_LIST_DIRECTORY = 0x0001
_FILE_SHARE_ALL = 0x0007
_OPEN_EXISTING = 3
_FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
_NOTIFY = 0x0001 | 0x0008 | 0x0010   # FILE_NAME | SIZE | LAST_WRITE


class Watcher(threading.Thread):
    """DTXMania4 フォルダの書き込みを待ち、RecordDB が変わったら ingest する。"""

    def __init__(self, state, data_dir: Path | None = None, settle: float = 1.5):
        super().__init__(name='records', daemon=True)
        self.state = state
        self.data_dir = data_dir or DTXMANIA_DATA
        self.db = self.data_dir / RECORD_DB
        self.settle = settle
        self.added_total = 0

    def ingest(self) -> int:
        with self.state.lock:
            found = list(self.state.songs)
        try:
            added = ingest(found, self.db)
        except Exception as e:  # noqa: BLE001 - 監視は止めない
            print('records:', e)
            return 0
        for s, d, pl in added:
            print(f"記録: {s.title} / {d}  Miss {pl['miss']}/{pl['notes']}  combo {pl['combo']}  ({pl['at']})")
        self.added_total += len(added)
        return len(added)

    def run(self):
        if not self.db.exists():
            print('records: RecordDB がありません:', self.db)
            return
        self.ingest()
        if not self._watch_windows():
            self._poll()

    def _watch_windows(self) -> bool:
        try:
            k32 = ctypes.windll.kernel32
        except AttributeError:
            return False
        k32.CreateFileW.restype = ctypes.c_void_p
        h = k32.CreateFileW(str(self.data_dir), _FILE_LIST_DIRECTORY, _FILE_SHARE_ALL, None, _OPEN_EXISTING,
                            _FILE_FLAG_BACKUP_SEMANTICS, None)
        if not h or h == ctypes.c_void_p(-1).value:
            return False
        buf = ctypes.create_string_buffer(64 * 1024)
        n = ctypes.c_ulong()
        while True:
            ok = k32.ReadDirectoryChangesW(ctypes.c_void_p(h), buf, len(buf), False, _NOTIFY, ctypes.byref(n), None, None)
            if not ok:
                return False
            if self._mentions_db(buf.raw[:n.value]):
                time.sleep(self.settle)   # DTXMania の書き込み完了を待つ
                self.ingest()

    @staticmethod
    def _mentions_db(data: bytes) -> bool:
        off = 0
        while off + 12 <= len(data):
            nxt, _action, length = struct.unpack_from('III', data, off)
            name = data[off + 12: off + 12 + length].decode('utf-16-le', 'replace')
            if name.lower().startswith(RECORD_DB.lower()):
                return True
            if not nxt:
                break
            off += nxt
        return False

    def _poll(self, every: float = 15):
        last = None
        while True:
            try:
                m = self.db.stat().st_mtime
            except OSError:
                m = None
            if m != last:
                last = m
                time.sleep(self.settle)
                self.ingest()
            time.sleep(every)
