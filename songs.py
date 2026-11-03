"""songlist の走査と、曲フォルダへの書き込み（score_beginner.dtx / score_easy.dtx / set.def / dtx_syrup.json）。"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import audio
import dtx
import simplify

SILENCE_NAME = 'silence.wav'           # 終端の無音チップ用（write_variant が曲フォルダに作る）
DEFAULT_SONGLIST = Path(os.environ.get('DTX_SYRUP_SONGLIST', r'C:\Users\woops\Desktop\dtxmania-4.15.1\songlist'))
CONFIG_NAME = 'tube_dtx_config.json'   # これがあるフォルダ = TubeDTX 製
SETTINGS_NAME = 'dtx_syrup.json'   # 曲ごとの設定（題名の直し、難易度ごとのルール、演奏の履歴）
LEGACY_SETTINGS_NAME = 'play_dtxmania.json'   # 改名前の名前。見つけたら新しい名前に変える
FILES = {'beginner': 'score_beginner.dtx', 'easy': 'score_easy.dtx'}
LABELS = {'beginner': 'Beginner', 'easy': 'Easy', 'master': 'Master'}
MEDIA = {'pre.jpg': 'image/jpeg', 'bgm.ogg': 'audio/ogg', 'pre.ogg': 'audio/ogg'}

_BRACKET = re.compile(r'\s*[\[【(（].*?[\]】)）]\s*')
_QUOTED = re.compile(r'「([^」]+)」')
_ARTIST_BEFORE_QUOTE = re.compile(r'[|｜│]\s*([^|｜│「]+?)\s*「')
# 「…」が作品名のとき: 直前が「アニメ」「映画」など、または直後が「オープニングテーマ」「OP」など
_WORK_BEFORE = re.compile(r'(アニメ|アニメーション|映画|劇場版|ドラマ|番組|ゲーム|作品|シリーズ)\s*$')
_WORK_AFTER = re.compile(r'^\s*(オープニング|エンディング|主題歌|テーマ|挿入歌|イメージソング|OP|ED)')


def clean_title(title: str, artist: str) -> str:
    """YouTube の題名から曲名を取り出す。

    「…」があればそれを曲名とみなす。複数あるときは、作品名と分かるもの
    （アニメ「ポケットモンスター」エンディングテーマ、など）を除いた最後のもの。
    「…」が無ければ括弧書きを落とす。
    """
    joined = f'{title} {artist or ""}'
    quoted = list(_QUOTED.finditer(joined))
    if quoted:
        songs = [m for m in quoted
                 if not _WORK_BEFORE.search(joined[:m.start()]) and not _WORK_AFTER.match(joined[m.end():])]
        return (songs or quoted)[-1].group(1)
    t = re.sub(r'\s+', ' ', _BRACKET.sub(' ', title)).strip()
    return t or title


def clean_artist(title: str, artist: str) -> str:
    joined = f'{title} {artist or ""}'
    m = _ARTIST_BEFORE_QUOTE.search(joined)
    if m:
        return m.group(1).strip()
    return '' if '「' in (artist or '') else (artist or '')


def find_master(folder: Path) -> Path | None:
    for name in ('score_master.dtx', 'score.dtx'):
        if (folder / name).exists():
            return folder / name
    for p in sorted(folder.glob('*.dtx')):
        if p.name not in FILES.values():
            return p
    return None


def load_settings(folder: Path) -> dict:
    p = folder / SETTINGS_NAME
    old = folder / LEGACY_SETTINGS_NAME
    if not p.exists() and old.exists():
        try:
            old.replace(p)
        except OSError:
            p = old
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def save_settings(folder: Path, data: dict) -> None:
    (folder / SETTINGS_NAME).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')


def variant_status(folder: Path, difficulty: str) -> str | None:
    """None = 無い / 'auto' = DTX Syrup が書いた / 'hand' = それ以外（手作りや別ツール。上書きしない）。"""
    p = folder / FILES[difficulty]
    if not p.exists():
        return None
    return 'auto' if dtx.is_generated_file(p) else 'hand'


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


@dataclass
class Song:
    folder: Path
    master_path: Path
    master: dtx.Chart
    settings: dict = field(default_factory=dict)
    config: dict = field(default_factory=dict)   # tube_dtx_config.json（movie_url など）

    @property
    def video_id(self) -> str:
        import tubedtx
        return tubedtx.video_id(self.config.get('movie_url') or '')

    @property
    def name(self) -> str:
        return self.folder.name

    @property
    def audio_seconds(self) -> float | None:
        """bgm.ogg の長さ（秒）。無ければ None。"""
        if not hasattr(self, '_audio_seconds'):
            p = self.folder / 'bgm.ogg'
            self._audio_seconds = audio.duration(p) if p.exists() else None
        return self._audio_seconds

    @property
    def raw_title(self) -> str:
        return self.master.header.get('TITLE', self.folder.name)

    @property
    def raw_artist(self) -> str:
        return self.master.header.get('ARTIST', '')

    @property
    def title(self) -> str:
        return self.settings.get('title') or clean_title(self.raw_title, self.raw_artist)

    @property
    def artist(self) -> str:
        return self.settings.get('artist') or clean_artist(self.raw_title, self.raw_artist)

    def status(self) -> dict:
        return {d: variant_status(self.folder, d) for d in FILES}

    def hand_variants(self) -> dict[str, dtx.Chart]:
        """DTX Syrup 以外が書いた既存の難易度譜面（比較用）。"""
        out = {}
        for d, fn in FILES.items():
            p = self.folder / fn
            if p.exists() and not dtx.is_generated_file(p):
                out[d] = dtx.parse(p)
        return out

    def rules(self, difficulty: str) -> dict:
        return simplify.normalize(self.settings.get('rules', {}).get(difficulty), difficulty)

    def summary(self, index: int) -> dict:
        m = self.master
        return {
            'i': index,
            'dir': self.name,
            'title': self.title,
            'artist': self.artist,
            'rawTitle': self.raw_title,
            'rawArtist': self.raw_artist,
            'bpm': m.bpm,
            'maxBar': m.max_bar,
            'bgmStart': m.bgm_start(),
            'total': max(m.max_bar * m.beat_seconds(), (m.bgm_start() + self.audio_seconds) if self.audio_seconds else 0.0),
            'master': self.master_path.name,
            'masterNotes': len(m.notes),
            'thumb': f'/media/{index}/pre.jpg' if (self.folder / 'pre.jpg').exists() else None,
            'audio': f'/media/{index}/bgm.ogg' if (self.folder / 'bgm.ogg').exists() else None,
            'has': self.status(),
            'videoId': self.video_id,
            'rules': {d: self.rules(d) for d in FILES},
            'customRules': {d: d in self.settings.get('rules', {}) for d in FILES},
            'plays': {d: (pl[-1] if pl else None) for d, pl in self.settings.get('plays', {}).items()},  # 難易度ごとの直近の記録
        }


def scan(root: Path = DEFAULT_SONGLIST) -> list[Song]:
    songs: list[Song] = []
    if not root.exists():
        return songs
    for folder in sorted(p for p in root.rglob(CONFIG_NAME)):
        folder = folder.parent
        master_path = find_master(folder)
        if master_path is None:
            continue
        master = dtx.parse(master_path)
        if not master.notes:
            continue
        songs.append(Song(folder, master_path, master, load_settings(folder), load_json(folder / CONFIG_NAME)))
    return songs


def write_variant(song: Song, difficulty: str, params: dict | None = None, *, force: bool = False) -> dict:
    """score_<difficulty>.dtx を書く。手作りのファイルがあるときは force でも上書きしない。"""
    p = simplify.normalize(params, difficulty)
    target = song.folder / FILES[difficulty]
    status = variant_status(song.folder, difficulty)
    if status == 'hand':
        return {'ok': False, 'skipped': 'hand', 'path': str(target),
                'message': f'{target.name} は手作り（または別ツール）の譜面なので上書きしません'}
    kept, _removed = simplify.simplify(song.master.notes, p, song.master.beat_seconds(), song.master.max_bar)
    end_time = None
    if song.audio_seconds:   # 音源の終わりまで演奏を続ける（終端の無音チップ）
        end_time = song.master.bgm_start() + song.audio_seconds + 0.5
        if not (song.folder / SILENCE_NAME).exists():
            audio.write_silence(song.folder / SILENCE_NAME)
    text = dtx.render(song.master, kept, difficulty=difficulty, params=p,
                      dlevel=simplify.dlevel_for(kept, song.master.notes), end_time=end_time, silence=SILENCE_NAME)
    dtx.write(target, text)
    return {'ok': True, 'path': str(target), 'notes': len(kept), 'master': len(song.master.notes),
            'replaced': status == 'auto'}


_SETDEF_LINE = re.compile(r'^#(TITLE|L(\d)(LABEL|FILE))\s*:?\s*(.*?)\s*$', re.IGNORECASE)


def write_setdef(song: Song) -> Path:
    """set.def を書く。既にあれば #TITLE など他の行を保ち、L1 Beginner / L2 Easy / L3 Master を入れ直す。"""
    target = song.folder / 'set.def'
    title = song.title
    kept_lines: list[str] = []
    if target.exists():
        for ln in dtx.read_text_guess(target).splitlines():
            m = _SETDEF_LINE.match(ln.strip())
            if m and m.group(1).upper() == 'TITLE':
                if 'title' not in song.settings:
                    title = m.group(4) or title   # set.def に手で付けた題名があればそれを保つ（UI で直した題名はさらに優先）
                continue
            if m:
                continue  # L*LABEL / L*FILE は作り直す
            if ln.strip():
                kept_lines.append(ln.rstrip())
    levels = []
    for d in ('beginner', 'easy'):
        if (song.folder / FILES[d]).exists():
            levels.append((LABELS[d], FILES[d]))
    levels.append((LABELS['master'], song.master_path.name))
    out = [ln for ln in kept_lines if ln.startswith(';')] or [f'{dtx.MARKER} set.def']
    out += ['', f'#TITLE: {title}', '']
    for n, (label, fn) in enumerate(levels, start=1):
        out += [f'#L{n}LABEL: {label}', f'#L{n}FILE: {fn}', '']
    dtx.write(target, dtx.EOL.join(out) + dtx.EOL)
    return target


def generate(song: Song, difficulty: str, params: dict | None = None, *, save_rules: bool = False) -> dict:
    """1 難易度を書いて set.def も更新する。save_rules で使ったルールを曲の設定に残す。"""
    result = write_variant(song, difficulty, params)
    if result.get('ok'):
        if save_rules and params is not None:
            song.settings.setdefault('rules', {})[difficulty] = simplify.normalize(params, difficulty)
            save_settings(song.folder, song.settings)
        result['setdef'] = str(write_setdef(song))
    return result
