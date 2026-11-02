"""DTX ファイルの読み書き。TubeDTX が出す score.dtx を入力に、間引いた譜面を同じ体裁で書き出す。

- 文字コードは Shift_JIS（cp932）、改行は CRLF。DTXMania / DTXCreator と同じ
- データ行は `#bbbCC: 0102..`（bbb = 小節 3 桁、CC = チャンネル、2 文字ずつチップ番号）
- ドラムチャンネル 11〜1C だけ作り直し、BGM（01）や動画（54）などの行は元のまま写す
- 自分が書いたファイルには 2 行目に MARKER を入れ、手作りの譜面と区別する（手作りは上書きしない）
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

ENCODING = 'cp932'
EOL = '\r\n'
MARKER = '; play-dtxmania'
DATA_LINE = re.compile(r'^#(\d{3})([0-9A-Z]{2}):\s*([0-9A-Za-z]*)\s*$')
HEADER_LINE = re.compile(r'^#([A-Za-z0-9_]+):\s*(.*?)\s*$')
DRUM_CHANNELS = {'11', '12', '13', '14', '15', '16', '17', '18', '19', '1A', '1B', '1C'}
# TubeDTX は楽器ごとに 4 段階の強さでチップ番号を変える。基準番号を引くと 0〜3 の強さになる
CHIP_BASE = {'11': 2, '12': 6, '13': 10, '14': 14, '15': 18, '17': 22, '16': 26}
LANE_NAMES = {'11': 'HH', '12': 'SD', '13': 'BD', '14': 'HT', '15': 'LT', '16': 'CY', '17': 'FT',
              '18': 'HHO', '19': 'RD', '1A': 'LC', '1B': 'LP', '1C': 'LBD'}


def level(ch: str, chip: str) -> int:
    """チップ番号（36 進 2 桁）から強さ 0〜3 を返す。未知のチャンネルは番号そのまま。"""
    return int(chip, 36) - CHIP_BASE.get(ch, 0)


@dataclass(frozen=True)
class Note:
    bar: int
    ch: str
    i: int      # 小節内の位置（i / n）
    n: int
    chip: str

    @property
    def pos(self) -> float:
        return self.i / self.n

    @property
    def level(self) -> int:
        return level(self.ch, self.chip)

    def as_list(self) -> list:
        return [self.bar, self.ch, self.i, self.n, self.chip]


@dataclass
class Chart:
    path: Path
    lines: list[str]
    header: dict[str, str] = field(default_factory=dict)   # 大文字キー → 値（最初の出現）
    notes: list[Note] = field(default_factory=list)        # ドラムチャンネルのチップ
    bgm: tuple[int, int, int] | None = None                # (bar, i, n) チャンネル 01 の最初のチップ

    @property
    def bpm(self) -> float:
        try:
            return float(self.header.get('BPM', '0') or 0)
        except ValueError:
            return 0.0

    @property
    def max_bar(self) -> int:
        bars = [n.bar for n in self.notes]
        for ln in self.lines:
            m = DATA_LINE.match(ln)
            if m:
                bars.append(int(m.group(1)))
        return max(bars) if bars else 0

    def beat_seconds(self) -> float:
        """1 小節の秒数（4/4・BPM 固定を前提）。"""
        return 240.0 / self.bpm if self.bpm else 0.0

    def bgm_start(self) -> float:
        """BGM チップが鳴る時刻（秒）。譜面時刻 = 音源の再生位置 + この値。"""
        if not self.bgm:
            return 0.0
        bar, i, n = self.bgm
        return (bar - 1 + i / n) * self.beat_seconds()

    def is_generated(self) -> bool:
        return any(MARKER in ln for ln in self.lines[:5])


def parse_text(text: str, path: Path | None = None) -> Chart:
    chart = Chart(path=path or Path(''), lines=text.splitlines())
    for ln in chart.lines:
        m = DATA_LINE.match(ln)
        if m:
            bar, ch, data = int(m.group(1)), m.group(2), m.group(3)
            n = len(data) // 2
            for i in range(n):
                chip = data[2 * i:2 * i + 2]
                if chip == '00':
                    continue
                if ch == '01':
                    if chart.bgm is None:
                        chart.bgm = (bar, i, n)
                elif ch in DRUM_CHANNELS:
                    chart.notes.append(Note(bar, ch, i, n, chip))
            continue
        m = HEADER_LINE.match(ln)
        if m:
            chart.header.setdefault(m.group(1).upper(), m.group(2))
    return chart


def read_text_guess(path: Path) -> str:
    """Shift_JIS が基本だが、手作りや他ツールのファイルが UTF-8 のことがある（例: らんま の set.def）。
    UTF-8 として厳密に読めればそれ、だめなら cp932。日本語の cp932 が UTF-8 として通ることはまず無い。"""
    data = path.read_bytes()
    try:
        return data.decode('utf-8-sig')
    except UnicodeDecodeError:
        return data.decode(ENCODING, errors='replace')


def parse(path: Path) -> Chart:
    return parse_text(read_text_guess(path), path)


def is_generated_file(path: Path) -> bool:
    """自分（play-dtxmania）が書いたファイルか。先頭 5 行の MARKER で判定。"""
    try:
        return any(MARKER in ln for ln in read_text_guess(path).splitlines()[:5])
    except OSError:
        return False


def render(master: Chart, kept, *, difficulty: str, params: dict, dlevel: int | None = None) -> str:
    """間引き結果 kept（bar, ch, slot, grid, chip を持つ列）から DTX 本文を作る。

    ヘッダとドラム以外のデータ行は master をそのまま写す。ドラム行は kept から作り直す。
    """
    header_lines: list[str] = []
    other_data: dict[tuple[int, str], str] = {}
    for ln in master.lines:
        m = DATA_LINE.match(ln)
        if m:
            if m.group(2) not in DRUM_CHANNELS:
                other_data[(int(m.group(1)), m.group(2))] = ln.rstrip()
            continue
        if MARKER in ln:
            continue  # 二重に印を付けない（生成物を入力にしたとき）
        header_lines.append(ln.rstrip())

    # 1 行目のコメントの直後に印。ヘッダ内の #DLEVEL は難易度に合わせて差し替える
    marker = f'{MARKER} {difficulty} {json.dumps(params, ensure_ascii=False, separators=(",", ":"))}'
    out: list[str] = []
    inserted = False
    for ln in header_lines:
        hm = HEADER_LINE.match(ln)
        if hm and hm.group(1).upper() == 'DLEVEL' and dlevel is not None:
            ln = f'#DLEVEL: {dlevel}'
        out.append(ln)
        if not inserted:
            out.append(marker)
            inserted = True
    if not inserted:
        out.insert(0, marker)
    # 末尾の空行を整える
    while out and out[-1] == '':
        out.pop()
    out.append('')

    drum_data: dict[tuple[int, str], dict[int, str]] = {}
    grids: dict[tuple[int, str], int] = {}
    for k in kept:
        key = (k.bar, k.ch)
        drum_data.setdefault(key, {})[k.slot] = k.chip
        grids[key] = max(grids.get(key, 0), k.grid)
    data_lines: dict[tuple[int, str], str] = dict(other_data)
    for key, slots in drum_data.items():
        g = grids[key]
        data_lines[key] = f'#{key[0]:03d}{key[1]}: ' + ''.join(slots.get(s, '00') for s in range(g))
    for key in sorted(data_lines):
        out.append(data_lines[key])
    out.append('')
    return EOL.join(out)


def write(path: Path, text: str) -> None:
    """Shift_JIS で書く。変換できない文字は '?' に落とす（DTXMania が読めることを優先）。"""
    path.write_bytes(text.encode(ENCODING, errors='replace'))
