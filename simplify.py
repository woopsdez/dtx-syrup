"""Master 譜面を Beginner / Easy 向けに間引く。試作（HTML）の JS 実装を同じ結果になるように移植。

ルール（params）
- grid:  1 小節を何分割に丸めるか（4 / 8 / 16 / 32）
- hh / sd / bd:  レーンごとの密度。'off' 消す / '1' 小節頭だけ / '2' 2 分 / '4' 4 分 / '8' 8 分 / '16' 16 分 /
                 'all' そのまま / sd だけ '24'（2・4 拍だけ）
- toms:  タム（HT / LT / FT）を残すか
- ghost: 弱い音（強さ 0〜1）を消すか
- chord: 同時押しの上限（残す優先順は SD > BD > HH > HT > LT）
"""
from __future__ import annotations

from dataclasses import dataclass

from dtx import Note, level

DEFAULTS = {
    'beginner': {'grid': 8, 'hh': '2', 'sd': '24', 'bd': '1', 'toms': False, 'ghost': True, 'chord': 1},
    'easy': {'grid': 16, 'hh': '8', 'sd': 'all', 'bd': '4', 'toms': True, 'ghost': True, 'chord': 2},
}
PRIORITY = ['12', '13', '11', '14', '15']
TOMS = {'14', '15', '17'}
DENSITY_LANES = {'11': 'hh', '12': 'sd', '13': 'bd'}


@dataclass(frozen=True)
class Kept:
    bar: int
    ch: str
    slot: int
    grid: int
    lvl: int
    chip: str
    src: int  # master.notes の添字

    def as_list(self) -> list:
        return [self.bar, self.ch, self.slot, self.grid, self.lvl]


def js_round(x: float) -> int:
    """JS の Math.round と同じ（.5 は切り上げ）。Python の round は偶数丸めなので使わない。"""
    return int(x + 0.5)


def normalize(params: dict | None, difficulty: str) -> dict:
    p = dict(DEFAULTS[difficulty])
    for k, v in (params or {}).items():
        if k not in p:
            continue
        if k in ('grid', 'chord'):
            p[k] = int(v)
        elif k in ('toms', 'ghost'):
            p[k] = bool(v)
        else:
            p[k] = str(v)
    return p


def allowed(mode: str, slot: int, grid: int) -> bool:
    if mode == 'all':
        return True
    if mode == 'off':
        return False
    if mode == '24':
        return slot == grid // 4 or slot == (3 * grid) // 4
    d = int(mode)
    if d >= grid:
        return True
    return slot % (grid // d) == 0


def simplify(notes: list[Note], params: dict) -> tuple[list[Kept], list[tuple[int, str, float]]]:
    """戻り値: (残したノート, 消したノート [(bar, ch, pos)])。"""
    g = int(params['grid'])
    removed: list[tuple[int, str, float]] = []
    by_slot: dict[tuple[int, str, int], Kept] = {}
    for idx, n in enumerate(notes):
        pos = n.pos
        lvl = level(n.ch, n.chip)
        if n.ch in TOMS and not params['toms']:
            removed.append((n.bar, n.ch, pos))
            continue
        if params['ghost'] and lvl <= 1:
            removed.append((n.bar, n.ch, pos))
            continue
        s, b = js_round(pos * g), n.bar
        if s >= g:
            s, b = 0, b + 1
        mode = params.get(DENSITY_LANES.get(n.ch, ''), 'all') if n.ch in DENSITY_LANES else 'all'
        if not allowed(mode, s, g):
            removed.append((n.bar, n.ch, pos))
            continue
        key = (b, n.ch, s)
        cur = by_slot.get(key)
        cand = Kept(b, n.ch, s, g, lvl, n.chip, idx)
        if cur is None:
            by_slot[key] = cand
        elif lvl > cur.lvl:  # 同じ位置に重なったら強いほうを残す
            removed.append((notes[cur.src].bar, cur.ch, notes[cur.src].pos))
            by_slot[key] = cand
        else:
            removed.append((n.bar, n.ch, pos))

    # 同時押しの上限
    groups: dict[tuple[int, int], list[Kept]] = {}
    for k in by_slot.values():
        groups.setdefault((k.bar, k.slot), []).append(k)
    kept: list[Kept] = []
    limit = int(params['chord'])
    rank = {ch: i for i, ch in enumerate(PRIORITY)}
    for grp in groups.values():
        grp.sort(key=lambda k: rank.get(k.ch, len(PRIORITY)))
        kept.extend(grp[:limit])
        for k in grp[limit:]:
            removed.append((notes[k.src].bar, k.ch, notes[k.src].pos))
    kept.sort(key=lambda k: (k.bar, k.slot, rank.get(k.ch, len(PRIORITY))))
    removed.sort()
    return kept, removed


def key_at_16(bar: int, ch: str, pos: float) -> str:
    s, b = js_round(pos * 16), bar
    if s >= 16:
        s, b = 0, b + 1
    return f'{b}:{ch}:{s}'


def match_rate(kept: list[Kept], hand: list[Note] | None) -> dict | None:
    """手作り（既存）譜面との一致率。16 分グリッドで位置とレーンが同じノートの Jaccard。"""
    if not hand:
        return None
    a = {key_at_16(k.bar, k.ch, k.slot / k.grid) for k in kept}
    b = {key_at_16(n.bar, n.ch, n.pos) for n in hand}
    inter = len(a & b)
    union = len(a | b)
    return {'rate': inter / union if union else 0.0, 'inter': inter, 'hand': len(b)}


def stats(kept: list[Kept], master: list[Note]) -> dict:
    counts: dict[int, int] = {}
    for k in kept:
        counts[k.bar] = counts.get(k.bar, 0) + 1
    master_counts: dict[int, int] = {}
    for n in master:
        master_counts[n.bar] = master_counts.get(n.bar, 0) + 1
    return {
        'notes': len(kept),
        'master': len(master),
        'ratio': (len(kept) / len(master)) if master else 0.0,
        'maxPerBar': max(counts.values()) if counts else 0,
        'counts': counts,
        'masterCounts': master_counts,
    }


def dlevel_for(kept: list[Kept], master: list[Note], master_level: int = 50) -> int:
    """#DLEVEL（難易度表示）。Master を基準にノート比で下げる。5〜100。"""
    if not master:
        return master_level
    return max(5, min(100, js_round(master_level * len(kept) / len(master))))
