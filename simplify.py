"""Master 譜面を Beginner / Easy 向けに薄くする（考え方は docs/simplify-theory.md の 3 章）。

方針: 引き算だけ（打点は動かさない）、層を 1 枚ずつ剥がす、同じセクションは同じ削り方。

手順
0. 本当の小節の長さと頭の位置を打点から探す（TubeDTX の BPM が 3/4 や 4/3 にずれている曲があり、
   DTX の小節と曲の小節が合っていない。以後の「小節」「拍」はこの検出した格子で数える）
1. 小節ごとの骨格（キック・スネアの 8 分位置）を比べてセクションに分け、似たセクションは同じ「型」にまとめる
2. 型ごとに位置の出現率（型の小節の何割が叩いているか）を数え、層のスイッチで残す位置（マスク）を 1 回だけ決める。
   1 秒あたりの打点数の予算を超えるときは上の層から 1 段ずつ剥がす（STEPS）
3. マスクを型の全小節に当てる。型から外れた小節（フィル・変奏）は fill の設定で縮め、次の小節頭（着地）は残す
4. キメ（型に無い裏拍でキックとスネアが同時）は残す。最後に同時打ちの上限

params（難易度ごとの既定は DEFAULTS。level を変えると層のスイッチは LEVELS の値になる）
- level: 0〜5（0 = 手だけの最初の一歩、2 = Beginner、4 = Easy、5 = ほぼそのまま）
- hh:    'off' / '2'（1・3 拍）/ '4'（4 分）/ '8'（8 分）/ '16'（そのまま）
- kick:  'off' / '1'（小節頭だけ）/ 'on'（表拍）/ 'sig'（表拍 + 型の裏拍 1 つ）/ '8'（8 分位置 + 型の 16 分裏 1 つ）/ 'all'
- sd:    '24'（2・4 拍。無い型は重い 2 つ）/ 'on'（8 分位置まで）/ 'all'
- toms:  ビート中のタムを残すか
- fill:  'skip'（中身を省略して着地だけ）/ 'toms2'（4 分のタム 2 つまで）/ '8'（8 分位置）/ 'all'
- chord: 同時打ちの上限 1 / 2 / 3（残す順は SD > BD > HH > FT > LT > HT）
- ghost: 弱い音（強さ 0〜1）を消す
- nps:   1 秒あたりの打点数の上限（0 = 無制限）。曲の速さに合わせた予算
- offsets: {型番号: ±n}。その型だけ level を上下する（プレイログのミス区間から）
"""
from __future__ import annotations

from dataclasses import dataclass, field

from dtx import Note

W16 = [5, 1, 2, 1, 3, 1, 2, 1, 4, 1, 2, 1, 3, 1, 2, 1]   # 拍節重み（16 分、Toussaint）
GROUP = {'11': 'H', '12': 'S', '13': 'B', '14': 'T', '15': 'T', '17': 'T'}
GROUP_W = {'S': 3.0, 'B': 2.5, 'H': 1.0, 'T': 1.5}
GROUP_ORDER = ['S', 'B', 'H', 'T']                       # 同じ位置で残す順
PRIORITY = ['12', '13', '11', '17', '15', '14']          # 同時打ちで残す順（ビート）
FILL_PRIORITY = ['12', '17', '15', '14', '13', '11']     # フィルで残す順（手が先）
TOMS = {'14', '15', '17'}
SIM = 0.6                                                # 同じ型とみなす類似度（Jaccard）
ON_BEATS = (0, 4, 8, 12)
GRID_CANDIDATES = (1.0, 0.75, 4 / 3, 0.5, 2.0, 1.5, 2 / 3)   # 本当の小節の長さ（DTX の小節 = 1）

LEVELS = [
    {'hh': 'off', 'kick': 'off', 'sd': '24', 'toms': False, 'fill': 'skip', 'chord': 1, 'nps': 1.5},
    {'hh': '2', 'kick': '1', 'sd': '24', 'toms': False, 'fill': 'skip', 'chord': 1, 'nps': 2.0},
    {'hh': '4', 'kick': 'on', 'sd': '24', 'toms': False, 'fill': 'toms2', 'chord': 1, 'nps': 3.0},
    {'hh': '4', 'kick': 'sig', 'sd': 'on', 'toms': True, 'fill': '8', 'chord': 2, 'nps': 5.0},
    {'hh': '8', 'kick': '8', 'sd': 'all', 'toms': True, 'fill': '8', 'chord': 2, 'nps': 7.0},
    {'hh': '16', 'kick': 'all', 'sd': 'all', 'toms': True, 'fill': 'all', 'chord': 3, 'nps': 0.0},
]
LAYER_KEYS = ('hh', 'kick', 'sd', 'toms', 'fill', 'chord', 'nps')
DEFAULT_LEVEL = {'beginner': 2, 'easy': 4}
DEFAULTS = {d: {'level': lv, 'ghost': True, 'movie': True, 'offsets': {}, **LEVELS[lv]} for d, lv in DEFAULT_LEVEL.items()}
HH_LADDER = ['off', '2', '4', '8', '16']
KICK_LADDER = ['off', '1', 'on', 'sig', '8', 'all']
SD_LADDER = ['24', 'on', 'all']
FILL_LADDER = ['skip', 'toms2', '8', 'all']
OLD_VALUES = {'hh': {'1': '2', 'all': '16'}}             # 2026-11-02 版の params の値
STEPS = [   # 予算を超えたときに剥がす順（上の層から 1 枚ずつ。docs/simplify-theory.md 2a の逆順）
    ('hh', '16', '8'), ('kick', 'all', '8'), ('toms', True, False), ('kick', '8', 'sig'), ('hh', '8', '4'),
    ('kick', 'sig', 'on'), ('sd', 'all', 'on'), ('hh', '4', '2'), ('kick', 'on', '1'), ('sd', 'on', '24'),
    ('hh', '2', 'off'), ('kick', '1', 'off'),
]


@dataclass(frozen=True)
class Kept:
    bar: int
    ch: str
    slot: int   # 元の位置（slot / grid）。動かさない
    grid: int
    lvl: int
    chip: str
    src: int    # master.notes の添字

    def as_list(self) -> list:
        return [self.bar, self.ch, self.slot, self.grid, self.lvl]


@dataclass(frozen=True)
class Grid:
    """解析用の小節の格子。length = 本当の小節の長さ（DTX 小節 = 1）、phase = 最初の小節頭（DTX の時刻、小節単位）。"""
    length: float = 1.0
    phase: float = 0.0

    def locate(self, t: float) -> tuple[int, int]:
        """DTX の時刻（小節単位）→ (小節番号, 16 分位置)。"""
        u = (t - self.phase) / self.length
        vb = int(u // 1)
        s = js_round((u - vb) * 16)
        if s >= 16:
            vb, s = vb + 1, 0
        return vb, s

    def start_of(self, vb: int) -> float:
        return self.phase + vb * self.length

    def as_dict(self) -> dict:
        return {'length': self.length, 'phase': self.phase, 'tempoRatio': 1 / self.length}


@dataclass
class Section:
    start: int
    end: int
    cluster: int
    fills: list[int] = field(default_factory=list)

    def as_dict(self, grid: Grid) -> dict:
        return {'start': grid.start_of(self.start), 'end': grid.start_of(self.end + 1), 'cluster': self.cluster,
                'fills': [[grid.start_of(b), grid.start_of(b + 1)] for b in self.fills]}


@dataclass
class Structure:
    grid: Grid = field(default_factory=Grid)
    sections: list[Section] = field(default_factory=list)
    cluster_of: dict[int, int] = field(default_factory=dict)            # 小節 → 型
    fill_bars: set[int] = field(default_factory=set)
    presence: dict[int, dict[tuple[str, int], float]] = field(default_factory=dict)   # 型 → (グループ, 16 分位置) → 出現率
    bars_of: dict[int, list[int]] = field(default_factory=dict)         # 型 → 型どおりの小節

    @property
    def clusters(self) -> list[int]:
        return sorted(self.presence)

    def as_dict(self) -> dict:
        return {'grid': self.grid.as_dict(), 'sections': [s.as_dict(self.grid) for s in self.sections]}


def js_round(x: float) -> int:
    """JS の Math.round と同じ（.5 は切り上げ）。"""
    return int(x + 0.5)


def ntime(n: Note) -> float:
    return n.bar + n.pos


def normalize(params: dict | None, difficulty: str) -> dict:
    src = dict(params or {})
    try:
        lv = int(src.get('level', DEFAULT_LEVEL[difficulty]))
    except (TypeError, ValueError):
        lv = DEFAULT_LEVEL[difficulty]
    lv = max(0, min(len(LEVELS) - 1, lv))
    p = {'level': lv, 'ghost': True, 'movie': True, 'offsets': {}, **LEVELS[lv]}
    ladders = {'hh': HH_LADDER, 'kick': KICK_LADDER, 'sd': SD_LADDER, 'fill': FILL_LADDER}
    for k, v in src.items():
        if k in ('ghost', 'toms', 'movie'):
            p[k] = bool(v)
        elif k == 'chord':
            p[k] = max(1, min(3, int(v)))
        elif k == 'nps':
            p[k] = max(0.0, float(v))
        elif k in ladders:
            v = OLD_VALUES.get(k, {}).get(str(v), str(v))
            if v in ladders[k]:
                p[k] = v
        elif k == 'offsets' and isinstance(v, dict):
            p[k] = {str(c): int(o) for c, o in v.items() if int(o)}
    return p


# ---- 0. 格子（本当の小節）を探す ----
def _grid_score(times_sd: list[float], times_bd: list[float], grid: Grid) -> float:
    """スネアが 2・4 拍、キックが 1 拍目に乗るほど高い。16 分裏に乗るほど低い。"""
    score = 0.0
    for t in times_sd:
        s = grid.locate(t)[1]
        score += 2.0 if s in (4, 12) else 0.5 if s in (0, 8) else -1.0 if s % 2 else 0.0
    for t in times_bd:
        s = grid.locate(t)[1]
        score += 2.0 if s == 0 else 1.0 if s == 8 else 0.5 if s in (4, 12) else -0.5 if s % 2 else 0.0
    return score / max(1, len(times_sd) + len(times_bd))


def detect_grid(notes: list[Note]) -> Grid:
    """キック・スネアの打点から、本当の小節の長さ（DTX 小節比）と頭の位置を決める。はっきり勝るときだけ 1.0 以外にする。"""
    sd = [ntime(n) for n in notes if n.ch == '12' and n.level > 1]
    bd = [ntime(n) for n in notes if n.ch == '13' and n.level > 1]
    if len(sd) + len(bd) < 16:
        return Grid()
    best: dict[float, tuple[float, Grid]] = {}
    for length in GRID_CANDIDATES:
        cands = [Grid(length, k * length / 32) for k in range(32)]
        best[length] = max(((_grid_score(sd, bd, g), g) for g in cands), key=lambda x: x[0])
    base_score, base = best[1.0]
    plain = _grid_score(sd, bd, Grid())
    top_score, top = max(best.values(), key=lambda x: x[0])
    if top.length != 1.0 and top_score >= base_score + 0.25:
        return top
    return base if base_score >= plain + 0.1 else Grid()


# ---- 1. 構造（セクション・型・フィル） ----
def jaccard(a: frozenset, b: frozenset) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def analyze(notes: list[Note], max_bar: int | None = None, ghost: bool = True, grid: Grid | None = None) -> Structure:
    grid = grid or detect_grid(notes)
    st = Structure(grid=grid)
    live = [(n, *grid.locate(ntime(n))) for n in notes if n.ch in GROUP and not (ghost and n.level <= 1)]
    by_bar: dict[int, list[tuple[Note, int]]] = {}   # 小節 → [(Note, 16 分位置)]
    for n, vb, vs in live:
        by_bar.setdefault(vb, []).append((n, vs))
    if not by_bar:
        return st
    b0, b1 = min(by_bar), max(by_bar)
    sigs = {b: frozenset((GROUP[n.ch], vs) for n, vs in by_bar.get(b, ())) for b in range(b0, b1 + 1)}
    # 骨格 = (スネアの 8 分位置, キックの 8 分位置)。スネアの型が同じなら、キックの細かい違いは同じセクションとみなす
    skel = {b: (frozenset(vs // 2 for n, vs in by_bar.get(b, ()) if n.ch == '12'),
                frozenset(vs // 2 for n, vs in by_bar.get(b, ()) if n.ch == '13')) for b in range(b0, b1 + 1)}
    toms = {b: sum(1 for n, _ in by_bar.get(b, ()) if n.ch in TOMS) for b in range(b0, b1 + 1)}

    def sim(a: int, c: int) -> float:
        return 0.6 * jaccard(skel[a][0], skel[c][0]) + 0.4 * jaccard(skel[a][1], skel[c][1])

    def like(b: int, ref: list[int]) -> bool:
        """直前 2 小節のどちらかに似ていれば同じセクション（2 小節で 1 つのパターンも拾う）。"""
        return any(sim(b, r) >= SIM for r in ref)

    runs: list[list[int]] = []
    cur: list[int] = []
    ref: list[int] = []
    for b in range(b0, b1 + 1):
        if not cur:
            cur, ref = [b], [b]
            continue
        if like(b, ref):
            cur.append(b)
            ref = (ref + [b])[-2:]
            continue
        if b + 1 <= b1 and like(b + 1, ref):
            cur.append(b)   # 1 小節だけの変化（フィル・変奏）
            continue
        runs.append(cur)
        cur, ref = [b], [b]
    if cur:
        runs.append(cur)

    cluster_rep: list[int] = []   # 型の代表小節
    for run in runs:
        medoid = max(run, key=lambda b: (sum(sim(b, o) for o in run), -b))
        tom_med = sorted(toms[b] for b in run)[len(run) // 2]
        fills = [b for b in run if sim(b, medoid) < SIM or (toms[b] >= 3 and toms[b] > 1.5 * tom_med)]
        if len(fills) == len(run):
            fills = []
        cid = next((i for i, rep in enumerate(cluster_rep) if sim(rep, medoid) >= SIM), None)
        if cid is None:
            cid = len(cluster_rep)
            cluster_rep.append(medoid)
        st.sections.append(Section(run[0], run[-1], cid, fills))
        st.fill_bars.update(fills)
        for b in run:
            st.cluster_of[b] = cid
            if b not in fills:
                st.bars_of.setdefault(cid, []).append(b)
        st.presence.setdefault(cid, {})
    for cid, bars in st.bars_of.items():
        counts: dict[tuple[str, int], int] = {}
        for b in bars:
            for e in sigs[b]:
                counts[e] = counts.get(e, 0) + 1
        st.presence[cid] = {e: c / len(bars) for e, c in counts.items()}
    return st


# ---- 2. 型ごとのマスク ----
def _score(e: tuple[str, int], rate: float) -> float:
    return W16[e[1]] * GROUP_W[e[0]] + 3 * rate


def build_mask(pres: dict[tuple[str, int], float], p: dict) -> dict[tuple[str, int], float]:
    """層のスイッチから残す位置を決める。戻り値: (グループ, 16 分位置) → 点。"""
    def rate(g, s):
        return pres.get((g, s), 0.0)

    def pick(g, slots, th, limit=None):
        ent = sorted(((g, s) for s in slots if rate(g, s) >= th), key=lambda e: (-rate(*e), -W16[e[1]], e[1]))
        return ent[:limit] if limit else ent

    def phase(g, sets, th):
        best = max(sets, key=lambda ss: (sum(rate(g, s) for s in ss), -min(ss)))
        return pick(g, best, th)

    def top(g, slots, th, k):
        ent = sorted(((g, s) for s in slots if rate(g, s) >= th), key=lambda e: (-rate(*e) * W16[e[1]], e[1]))
        return ent[:k]

    hh, kick, sd = p['hh'], p['kick'], p['sd']
    ent: list[tuple[str, int]] = []
    if hh == '16':
        ent += pick('H', range(16), 0.3)
    elif hh == '8':
        ent += phase('H', [tuple(range(0, 16, 2)), tuple(range(1, 16, 2))], 0.4)
    elif hh == '4':
        ent += phase('H', [ON_BEATS, (2, 6, 10, 14)], 0.4)
    elif hh == '2':
        ent += phase('H', [(0, 8), (4, 12)], 0.4)
    if sd == '24':
        ent += pick('S', (4, 12), 0.4) or top('S', range(16), 0.4, 2)
    elif sd == 'on':
        ent += pick('S', [s for s in range(16) if W16[s] >= 2], 0.3, 4)
    else:
        ent += pick('S', range(16), 0.3, 8)
    off = [s for s in range(16) if W16[s] <= 2]
    if kick == '1':
        ent += pick('B', (0,), 0.3) or top('B', range(16), 0.4, 1)
    elif kick in ('on', 'sig'):
        ent += pick('B', ON_BEATS, 0.4) or top('B', range(16), 0.4, 1)
        if kick == 'sig':
            ent += pick('B', off, 0.7, 1)
    elif kick == '8':
        ent += pick('B', [s for s in range(16) if W16[s] >= 2], 0.4) + pick('B', [s for s in range(16) if W16[s] == 1], 0.8, 1)
    elif kick == 'all':
        ent += pick('B', range(16), 0.3)
    if p['toms']:
        ent += pick('T', [s for s in range(16) if W16[s] >= 2], 0.4)
    mask = {e: _score(e, rate(*e)) for e in ent}
    by_slot: dict[int, list[tuple[str, int]]] = {}
    for e in mask:
        by_slot.setdefault(e[1], []).append(e)
    for es in by_slot.values():   # 同じ位置の同時打ちは上限まで（残す順 S > B > H > T）
        es.sort(key=lambda e: GROUP_ORDER.index(e[0]))
        for e in es[p['chord']:]:
            del mask[e]
    return mask


def step_down(p: dict) -> dict | None:
    """予算を超えたとき、層を 1 段剥がした params を返す。剥がすものが無ければ None。"""
    for k, frm, to in STEPS:
        if p[k] == frm:
            return {**p, k: to}
    return None


def fit_mask(pres: dict, p: dict, bar_seconds: float) -> tuple[dict, dict]:
    """予算（nps × 小節の秒数）に収まるまで層を剥がす。戻り値: (マスク, 実際に使った params)。"""
    mask = build_mask(pres, p)
    if not p.get('nps') or not bar_seconds:
        return mask, p
    limit = max(2, js_round(p['nps'] * bar_seconds))
    while len(mask) > limit:
        q = step_down(p)
        if q is None:
            break
        p, mask = q, build_mask(pres, q)
    return mask, p


def layer_params(p: dict, cluster: int) -> dict:
    """型ごとの実効 params。offsets があればその型だけ LEVELS を上下した値にする。"""
    off = p.get('offsets', {}).get(str(cluster), 0)
    if not off:
        return p
    lv = max(0, min(len(LEVELS) - 1, p['level'] + off))
    return {**p, 'level': lv, **LEVELS[lv]}


# ---- 3. 当てる ----
def simplify_full(notes: list[Note], params: dict, bar_seconds: float = 0.0, max_bar: int | None = None
                  ) -> tuple[list[Kept], list[tuple[int, str, float]], Structure, dict]:
    """戻り値: (残したノート, 消したノート [(bar, ch, pos)], 構造, 型ごとの実効 params)。"""
    p = params
    st = analyze(notes, max_bar, p['ghost'])
    grid = st.grid
    masks: dict[int, dict] = {}
    used: dict[int, dict] = {}
    for cid in st.clusters:
        masks[cid], used[cid] = fit_mask(st.presence[cid], layer_params(p, cid), bar_seconds * grid.length)

    by_bar: dict[int, list[tuple[int, Note, int]]] = {}   # 小節 → [(添字, Note, 16 分位置)]
    for idx, n in enumerate(notes):
        if n.ch in GROUP and not (p['ghost'] and n.level <= 1):
            vb, vs = grid.locate(ntime(n))
            by_bar.setdefault(vb, []).append((idx, n, vs))
    keep: dict[int, Note] = {}
    rank = {ch: i for i, ch in enumerate(PRIORITY)}
    frank = {ch: i for i, ch in enumerate(FILL_PRIORITY)}

    for b, items in by_bar.items():
        cid = st.cluster_of.get(b)
        mask = masks.get(cid, {})
        q = used.get(cid, p)
        chosen: dict[tuple[str, int], tuple[int, Note, int]] = {}   # 同じレーン・位置は強いほうだけ

        def put(it):
            key = (it[1].ch, it[2])
            cur = chosen.get(key)
            if cur is None or (it[1].level, -it[1].i) > (cur[1].level, -cur[1].i):
                chosen[key] = it

        if b in st.fill_bars:
            mode = q['fill']
            if mode == 'all':
                for it in items:
                    put(it)
            elif mode == '8':
                for it in items:
                    if W16[it[2]] >= 2:
                        put(it)
            else:   # skip / toms2: ビートは型どおり、タムは省略（toms2 は 4 分のタム 2 つまで）
                toms = []
                for it in items:
                    if it[1].ch in TOMS:
                        if mode == 'toms2' and W16[it[2]] >= 3:
                            toms.append(it)
                    elif (GROUP[it[1].ch], it[2]) in mask:
                        put(it)
                toms.sort(key=lambda it: (-W16[it[2]], it[2]))
                for it in toms[:2]:
                    put(it)
        else:
            for it in items:
                if (GROUP[it[1].ch], it[2]) in mask:
                    put(it)
            # キメ: 型に無い裏拍で BD と SD が同時 → 残す（小節に 2 つまで）
            both: dict[int, dict[str, tuple]] = {}
            for it in items:
                if it[1].ch in ('12', '13'):
                    both.setdefault(it[2], {})[it[1].ch] = it
            kime = 0
            for s in sorted(both):
                if kime >= 2 or len(both[s]) < 2 or W16[s] > 2 or ('S', s) in mask or ('B', s) in mask:
                    continue
                put(both[s]['12'])
                if q['chord'] >= 2:
                    put(both[s]['13'])
                kime += 1
        groups: dict[int, list[tuple]] = {}
        for it in chosen.values():
            groups.setdefault(it[2], []).append(it)
        order = frank if b in st.fill_bars else rank
        for its in groups.values():   # 同時打ちの上限
            its.sort(key=lambda it: (order.get(it[1].ch, 9), -it[1].level, it[1].i))
            for it in its[:q['chord']]:
                keep[it[0]] = it[1]

    # 着地: フィルの次の小節頭は必ず 1 つ残す
    for b in st.fill_bars:
        heads = [it for it in by_bar.get(b + 1, []) if it[2] == 0 and it[1].ch in ('12', '13', '14', '15', '17')]
        if heads and not any(it[0] in keep for it in heads):
            it = min(heads, key=lambda it: rank.get(it[1].ch, 9))
            keep[it[0]] = it[1]

    # 締め: 曲の最後の位置にある打点（HH 以外）は必ず 1 つ残す
    if by_bar:
        tail = by_bar[max(by_bar)]
        last_vs = max(it[2] for it in tail)
        ends = [it for it in tail if it[2] == last_vs and it[1].ch != '11']
        if ends and not any(it[0] in keep for it in ends):
            it = min(ends, key=lambda it: rank.get(it[1].ch, 9))
            keep[it[0]] = it[1]

    kept = [Kept(n.bar, n.ch, n.i, n.n, n.level, n.chip, idx) for idx, n in keep.items()]
    kept.sort(key=lambda k: (k.bar, k.slot / k.grid, rank.get(k.ch, 9)))
    removed = sorted((n.bar, n.ch, n.pos) for idx, n in enumerate(notes) if idx not in keep and n.ch in GROUP)
    return kept, removed, st, used


def simplify(notes: list[Note], params: dict, bar_seconds: float = 0.0, max_bar: int | None = None
             ) -> tuple[list[Kept], list[tuple[int, str, float]]]:
    kept, removed, _st, _used = simplify_full(notes, params, bar_seconds, max_bar)
    return kept, removed


# ---- プレイログ → 型ごとの上下 ----
def offsets_from_map(st: Structure, count_map: str, max_bar: int, min_segments: int = 2, ratio: float = 0.5) -> dict[str, int]:
    """DTXMania の 64 区間のミス地図（'C' = ミスなし / '1' = ミスあり）から、ミスが集中した型を 1 段薄くする offsets を作る。"""
    if not count_map or not max_bar or not st.cluster_of:
        return {}
    n = len(count_map)
    hit: dict[int, list[int]] = {}
    for k, c in enumerate(count_map):
        t = 1 + (k + 0.5) / n * max_bar          # 区間の中央の時刻（DTX 小節単位）
        cid = st.cluster_of.get(st.grid.locate(t)[0])
        if cid is None:
            continue
        hit.setdefault(cid, []).append(1 if c == '1' else 0)
    return {str(cid): -1 for cid, xs in hit.items() if len(xs) >= min_segments and sum(xs) / len(xs) >= ratio}


# ---- 数字 ----
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
    ratio = (len(kept) / len(master)) if master else 0.0
    return max(5, min(100, round(master_level * ratio)))
