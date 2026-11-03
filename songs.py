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
BOX_PREFIX = 'DTXFiles.'            # songlist 直下のこの名前のフォルダ = DTXMania の選曲画面の「箱」
BOXDEF_NAME = 'box.def'            # こちらでも箱になる（#TITLE が箱の名前）
FAVORITE_BOX = '★お気に入り'        # ★ を付けた曲を入れる箱（フォルダは DTXFiles.★お気に入り）
FILES = {'beginner': 'score_beginner.dtx', 'easy': 'score_easy.dtx'}
LABELS = {'beginner': 'Beginner', 'easy': 'Easy', 'master': 'Master'}
MEDIA = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.bmp': 'image/bmp', '.gif': 'image/gif',
         '.ogg': 'audio/ogg', '.wav': 'audio/wav', '.mp3': 'audio/mpeg'}   # /media/N/<名前> で配れる拡張子

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
        if p.name.lower() not in FILES.values():
            return p
    return None


_SETDEF_LINE = re.compile(r'^#(TITLE|L(\d)(LABEL|FILE))\s*:?\s*(.*?)\s*$', re.IGNORECASE)


def read_setdef(folder: Path) -> dict:
    """set.def の #TITLE と L1..L5（{'title': str, 'levels': [(label, file)]}）。無ければ空。大文字の SET.DEF もある。"""
    with os.scandir(folder) as it:
        p = next((Path(e.path) for e in it if e.name.lower() == 'set.def' and e.is_file()), None)
    if p is None:
        return {}
    title, levels = '', {}
    for ln in dtx.read_text_guess(p).splitlines():
        m = _SETDEF_LINE.match(ln.strip())
        if not m:
            continue
        if m.group(1).upper() == 'TITLE':
            title = m.group(4)
        else:
            lv = levels.setdefault(int(m.group(2)), {})
            lv[m.group(3).upper()] = m.group(4)
    out = [(lv.get('LABEL') or f'L{n}', lv['FILE']) for n, lv in sorted(levels.items()) if lv.get('FILE')]
    return {'title': title, 'levels': out}


def is_box(p: Path) -> bool:
    return p.is_dir() and (p.name.lower().startswith(BOX_PREFIX.lower()) or (p / BOXDEF_NAME).exists())


def box_title(p: Path) -> str:
    """箱の名前。DTXFiles.<名前> ならその名前、box.def なら #TITLE（無ければフォルダ名）。"""
    if p.name.lower().startswith(BOX_PREFIX.lower()):
        return p.name[len(BOX_PREFIX):]
    try:
        for ln in dtx.read_text_guess(p / BOXDEF_NAME).splitlines():
            m = re.match(r'^#TITLE\s*:?\s*(.*?)\s*$', ln.strip(), re.IGNORECASE)
            if m and m.group(1):
                return m.group(1)
    except OSError:
        pass
    return p.name


def is_song_folder(p: Path) -> bool:
    """set.def か *.dtx を直接持つフォルダ。TubeDTX 製でなくても曲として数える。"""
    try:
        with os.scandir(p) as it:
            return any((e.name.lower() == 'set.def' or e.name.lower().endswith('.dtx')) and e.is_file() for e in it)
    except OSError:
        return False


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
    tube: bool = True                            # TubeDTX 製（tube_dtx_config.json がある）。簡易化できるのはこれだけ
    box: str = ''                                # 入っている箱の名前（'' = songlist 直下。入れ子は 'A/B'）
    box_dir: Path | None = None                  # 箱のフォルダ（直下なら songlist）
    rel: str = ''                                # songlist からの相対パス（UI の鍵。フォルダ名だけだと箱違いで重なり得る）
    levels: list = field(default_factory=list)   # set.def の [(難易度名, ファイル)]（TubeDTX 製でない曲の表示用）
    setdef_title: str = ''                       # set.def の #TITLE（TubeDTX 製でない曲の題名。表示だけで保存しない）

    @property
    def video_id(self) -> str:
        import tubedtx
        return tubedtx.video_id(self.config.get('movie_url') or '')

    @property
    def name(self) -> str:
        return self.folder.name

    @property
    def favorite(self) -> bool:
        return self.box == FAVORITE_BOX

    def move_unit(self) -> Path:
        """箱へ移すときに動かすフォルダ。zip の包み紙（曲フォルダ 1 つだけを包む透過フォルダ）ごと動かす。"""
        p = self.folder
        base = self.box_dir or p.parent
        while p.parent != base and p.parent != p:
            parent = p.parent
            if any(q.is_dir() and q != p for q in parent.iterdir()):
                break
            p = parent
        return p

    @property
    def added(self) -> float:
        """songlist に入れた日時（フォルダの作成時刻。Windows では移動しても変わらない）。"""
        try:
            st = self.move_unit().stat()
            return getattr(st, 'st_birthtime', None) or st.st_ctime
        except OSError:
            return 0.0

    def last_play(self) -> dict | None:
        """難易度を問わず一番新しい記録。"""
        plays = [pl for pls in self.settings.get('plays', {}).values() for pl in pls]
        return max(plays, key=lambda pl: pl.get('at', '')) if plays else None

    @property
    def audio_seconds(self) -> float | None:
        """bgm.ogg の長さ（秒）。無ければ None。"""
        if not hasattr(self, '_audio_seconds'):
            p = self.folder / 'bgm.ogg'
            self._audio_seconds = audio.duration(p) if p.exists() else None
        return self._audio_seconds

    @property
    def preimage(self) -> str | None:
        """一覧のサムネ。pre.jpg か、DTX の #PREIMAGE（配布譜面は rb.JPG など名前がまちまち）。"""
        for name in ('pre.jpg', self.master.header.get('PREIMAGE', '').strip()):
            if name and '/' not in name and '\\' not in name and (self.folder / name).is_file() \
                    and (self.folder / name).suffix.lower() in MEDIA:
                return name
        return None

    @property
    def raw_title(self) -> str:
        return self.setdef_title or self.master.header.get('TITLE', self.folder.name)

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
        last = self.last_play()
        return {
            'i': index,
            'dir': self.name,
            'rel': self.rel,
            'box': self.box,
            'fav': self.favorite,
            'tube': self.tube,
            'levels': [label for label, _ in self.levels],
            'added': self.added,
            'lastPlayed': last['at'] if last else None,
            'missRate': (last['miss'] / last['notes']) if last and last.get('notes') else None,
            'playCount': sum(len(pls) for pls in self.settings.get('plays', {}).values()),
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
            'thumb': f'/media/{index}/{self.preimage}' if self.preimage else None,
            'audio': f'/media/{index}/bgm.ogg' if (self.folder / 'bgm.ogg').exists() else None,
            'has': self.status(),
            'videoId': self.video_id,
            'rules': {d: self.rules(d) for d in FILES},
            'customRules': {d: d in self.settings.get('rules', {}) for d in FILES},
            'plays': {d: (pl[-1] if pl else None) for d, pl in self.settings.get('plays', {}).items()},  # 難易度ごとの直近の記録
        }


_PARSE_CACHE: dict[Path, tuple[tuple[int, int], dtx.Chart]] = {}


def cached_parse(path: Path) -> dtx.Chart:
    """同じファイル（更新時刻とサイズが同じ）は読み直さない。/api/songs のたびに全曲を走査するため。"""
    st = path.stat()
    key = (st.st_mtime_ns, st.st_size)
    hit = _PARSE_CACHE.get(path)
    if hit and hit[0] == key:
        return hit[1]
    chart = dtx.parse(path)
    _PARSE_CACHE[path] = (key, chart)
    return chart


def load_song(folder: Path, root: Path, box: str = '', box_dir: Path | None = None) -> Song | None:
    """曲フォルダ 1 つを読む。TubeDTX 製は Master（score.dtx）、それ以外は set.def の一番上の難易度を代表にする。"""
    tube = (folder / CONFIG_NAME).exists()
    setdef = read_setdef(folder)
    levels = [(label, fn) for label, fn in setdef.get('levels', []) if (folder / fn).is_file()]
    master_path = find_master(folder) if tube else None
    if master_path is None and levels:
        master_path = folder / levels[-1][1]
    if master_path is None:
        master_path = find_master(folder)
    if master_path is None:
        return None
    master = cached_parse(master_path)
    if tube and not master.notes:
        return None   # 途中で止まった TubeDTX のフォルダ
    try:
        rel = folder.relative_to(root).as_posix()
    except ValueError:
        rel = folder.name
    return Song(folder, master_path, master, load_settings(folder), load_json(folder / CONFIG_NAME) if tube else {},
                tube=tube, box=box, box_dir=box_dir or root, rel=rel, levels=levels,
                setdef_title=setdef.get('title', '') if not tube else '')


def _walk(d: Path, root: Path, box: str, box_dir: Path, out: list[Song]) -> None:
    try:
        with os.scandir(d) as it:
            children = sorted((Path(e.path) for e in it if e.is_dir()), key=lambda p: p.name.lower())
    except OSError:
        return
    for p in children:
        if is_box(p):
            name = box_title(p)
            _walk(p, root, f'{box}/{name}' if box else name, p, out)
        elif is_song_folder(p):
            song = load_song(p, root, box, box_dir)
            if song is not None:
                out.append(song)
        else:
            _walk(p, root, box, box_dir, out)   # 箱でも曲でもない = 透過フォルダ（zip の包み紙など）。DTXMania も中を辿る


def scan(root: Path = DEFAULT_SONGLIST) -> list[Song]:
    """songlist の全曲（箱の中も）。TubeDTX 製かどうかは Song.tube。"""
    songs: list[Song] = []
    if not root.exists():
        return songs
    _walk(root, root, '', root, songs)
    return songs


def boxes(root: Path = DEFAULT_SONGLIST, found: list[Song] | None = None) -> list[dict]:
    """箱の一覧（songlist 直下の DTXFiles.*、空の箱も）と曲数。入れ子の箱は曲から拾う。"""
    counts: dict[str, int] = {}
    for s in (found if found is not None else scan(root)):
        if s.box:
            counts[s.box] = counts.get(s.box, 0) + 1
    names = set(counts)
    if root.exists():
        names.update(box_title(p) for p in root.iterdir() if is_box(p))
    return [{'name': n, 'count': counts.get(n, 0), 'favorite': n == FAVORITE_BOX}
            for n in sorted(names, key=lambda n: (n != FAVORITE_BOX, n.lower()))]


def write_variant(song: Song, difficulty: str, params: dict | None = None, *, force: bool = False) -> dict:
    """score_<difficulty>.dtx を書く。手作りのファイルがあるときは force でも上書きしない。"""
    p = simplify.normalize(params, difficulty)
    target = song.folder / FILES[difficulty]
    if not song.tube:
        return {'ok': False, 'skipped': 'tube', 'path': str(target),
                'message': f'{song.title} は TubeDTX 製ではないので簡易化しません'}
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
