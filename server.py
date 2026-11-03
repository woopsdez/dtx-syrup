"""ローカル Web UI の配信と API。標準ライブラリの http.server だけで動く（127.0.0.1 のみ）。

GET  /                 web/index.html
GET  /api/songs        曲一覧（状態・ルール・既定値）
GET  /api/song?i=N     1 曲のノート（master と、比較用の既存譜面）
POST /api/simplify     {i, diff, params} → 間引き結果
POST /api/write        {i, diff, params} → score_<diff>.dtx と set.def を書く（ルールも保存）
POST /api/batch        {items:[i], diffs:[..], params?} → まとめて書く
POST /api/settings     {i, title?, artist?} → 題名の直し
POST /api/add          {url} → TubeDTX で譜面を作る（裏で実行）
GET  /api/jobs         実行中・終了した add の状態
GET  /api/boxes        箱（DTXFiles.*）の一覧と曲数
POST /api/move         {items:[i], box} → チェックした曲のフォルダを箱へ移す（'' = songlist 直下）
POST /api/favorite     {i, on} → ★（DTXFiles.★お気に入り へ移す / 元の箱へ戻す）
GET  /api/playlists   見張る再生リストと直近の確認結果
POST /api/playlists   {url, box} 追加 / {remove: url} 削除 / {interval} 確認の間隔（分）
POST /api/playlists/sync  今すぐ確認して、新しい動画をジョブに入れる
GET  /media/N/name     曲フォルダの画像・音源（pre.jpg, bgm.ogg など。Range 対応）
DTXMania が起動中のときは move / favorite を 409 で断る。
"""
from __future__ import annotations

import json
import threading
import traceback
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import boxes
import playlist
import records
import simplify
import songs as songs_mod
import tubedtx

WEB_DIR = Path(__file__).with_name('web')


class State:
    def __init__(self, root: Path, watch_records: bool = True):
        self.root = root
        self.lock = threading.Lock()
        self.songs: list[songs_mod.Song] = []
        self.jobs = tubedtx.Jobs(self)
        self.rescan()
        self.records = records.Watcher(self)
        self.playlists = playlist.Syncer(self)
        if watch_records:
            self.records.start()
            self.playlists.start()   # 再生リストを定期的に確かめて、新しい動画を譜面にする   # DTXMania が結果を書いたら曲ごとの履歴に写す

    def rescan(self) -> list[songs_mod.Song]:
        found = songs_mod.scan(self.root)
        with self.lock:
            self.songs = found
        return found

    def song(self, i) -> songs_mod.Song:
        with self.lock:
            return self.songs[int(i)]

    def summaries(self) -> list[dict]:
        with self.lock:
            return [s.summary(i) for i, s in enumerate(self.songs)]

    def boxes(self) -> list[dict]:
        with self.lock:
            return songs_mod.boxes(self.root, self.songs)

    def listing(self) -> dict:
        """一覧の応答（曲・箱）。書いた後や移した後にも同じ形で返す。"""
        return {'songs': self.summaries(), 'boxes': self.boxes(), 'favoriteBox': songs_mod.FAVORITE_BOX}


def per_bar(counts: dict[int, int], max_bar: int) -> list[int]:
    out = [0] * (max_bar + 2)
    for b, c in counts.items():
        if 0 <= b < len(out):
            out[b] = c
    return out


class Handler(BaseHTTPRequestHandler):
    state: State  # make_server で差し込む
    protocol_version = 'HTTP/1.1'

    # ---- 共通 ----
    def handle(self):
        """ブラウザが keep-alive の接続を途中で切るのは普通のこと。コンソールに例外を吐かない。"""
        try:
            super().handle()
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass

    def log_message(self, fmt, *args):  # noqa: D401 - 静かに。エラーだけ出す
        if args and str(args[1:2]).startswith("('5"):
            super().log_message(fmt, *args)

    def send_json(self, obj, status: int = 200) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict:
        n = int(self.headers.get('Content-Length') or 0)
        if not n:
            return {}
        return json.loads(self.rfile.read(n).decode('utf-8'))

    def send_file(self, path: Path, ctype: str) -> None:
        """Range 対応でファイルを返す（<audio> のシークに必要）。"""
        size = path.stat().st_size
        start, end, status = 0, size - 1, 200
        rng = self.headers.get('Range')
        if rng and rng.startswith('bytes='):
            a, _, b = rng[6:].partition('-')
            try:
                if a:
                    start, end = int(a), (int(b) if b else size - 1)
                else:
                    start, end = max(0, size - int(b)), size - 1
            except ValueError:
                start, end = 0, size - 1
            end = min(end, size - 1)
            if start > end or start >= size:
                self.send_response(416)
                self.send_header('Content-Range', f'bytes */{size}')
                self.send_header('Content-Length', '0')
                self.end_headers()
                return
            status = 206
        self.send_response(status)
        self.send_header('Content-Type', ctype)
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Content-Length', str(end - start + 1))
        if status == 206:
            self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        if self.command == 'HEAD':
            return
        with path.open('rb') as f:
            f.seek(start)
            left = end - start + 1
            while left > 0:
                chunk = f.read(min(1 << 16, left))
                if not chunk:
                    break
                self.wfile.write(chunk)
                left -= len(chunk)

    # ---- ルーティング ----
    def do_HEAD(self):  # noqa: N802
        self.do_GET()

    def do_GET(self):  # noqa: N802
        try:
            u = urlparse(self.path)
            q = parse_qs(u.query)
            if u.path in ('/', '/index.html'):
                return self.send_file(WEB_DIR / 'index.html', 'text/html; charset=utf-8')
            if u.path == '/api/songs':
                self.state.rescan()
                return self.send_json({**self.state.listing(), 'defaults': simplify.DEFAULTS,
                                       'levels': simplify.LEVELS, 'tubedtx': tubedtx.available()})
            if u.path == '/api/boxes':
                self.state.rescan()
                return self.send_json({'boxes': self.state.boxes(), 'favoriteBox': songs_mod.FAVORITE_BOX})
            if u.path == '/api/song':
                s = self.state.song(q['i'][0])
                return self.send_json({'notes': {
                    'master': [n.as_list() for n in s.master.notes],
                    'hand': {d: [n.as_list() for n in c.notes] for d, c in s.hand_variants().items()},
                }, 'plays': s.settings.get('plays', {})})
            if u.path == '/api/playlists':
                cfg = playlist.load_config(self.state.playlists.path)
                return self.send_json({'playlists': cfg['playlists'], 'interval': cfg['interval'],
                                       'last': self.state.playlists.last})
            if u.path == '/api/jobs':
                return self.send_json({'jobs': self.state.jobs.list()})
            if u.path == '/api/search':
                query = (q.get('q') or [''])[0].strip()
                if not tubedtx.available()['ok']:
                    return self.send_json({'error': f'TubeDTX が見つかりません: {tubedtx.TUBEDTX_DIR}'}, 400)
                results = tubedtx.search(query, n=12) if query else []
                with self.state.lock:
                    have = {s.video_id for s in self.state.songs if s.video_id}
                for r in results:
                    r['exists'] = r['id'] in have   # もう songlist にある動画
                return self.send_json({'query': query, 'results': results})
            if u.path.startswith('/media/'):
                parts = unquote(u.path).split('/')
                name = parts[3] if len(parts) == 4 else ''
                ext = Path(name).suffix.lower()
                if name and name == Path(name).name and name not in ('.', '..') and ext in songs_mod.MEDIA:
                    s = self.state.song(parts[2])
                    p = s.folder / name
                    if p.is_file():
                        return self.send_file(p, songs_mod.MEDIA[ext])
                return self.send_json({'error': 'not found'}, 404)
            return self.send_json({'error': 'not found'}, 404)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self.send_json({'error': str(e)}, 500)

    def do_POST(self):  # noqa: N802
        try:
            u = urlparse(self.path)
            body = self.read_json()
            if u.path == '/api/simplify':
                s = self.state.song(body['i'])
                if not s.tube:
                    return self.send_json({'error': f'{s.title} は TubeDTX 製ではないので簡易化しません'}, 400)
                diff = body['diff']
                p = simplify.normalize(body.get('params'), diff)
                m = s.master
                play = (s.settings.get('plays', {}).get(diff) or [None])[-1]
                if body.get('adapt') and play:   # 直近のプレイのミス区間から、型ごとに 1 段薄く
                    structure = simplify.analyze(m.notes, m.max_bar, p['ghost'])
                    p['offsets'] = simplify.offsets_from_map(structure, play.get('map', ''), m.max_bar)
                kept, removed, structure, used = simplify.simplify_full(m.notes, p, m.beat_seconds(), m.max_bar)
                st = simplify.stats(kept, m.notes)
                hand = s.hand_variants().get(diff)
                return self.send_json({
                    'kept': [k.as_list() for k in kept],
                    'removed': [[b, ch, pos] for b, ch, pos in removed],
                    'counts': per_bar(st.pop('counts'), m.max_bar),
                    'masterCounts': per_bar(st.pop('masterCounts'), m.max_bar),
                    'match': simplify.match_rate(kept, hand.notes if hand else None),
                    'stats': st,
                    'params': p,
                    'structure': structure.as_dict(),
                    'used': {str(c): {k: q[k] for k in ('level', *simplify.LAYER_KEYS)} for c, q in used.items()},
                    'play': play,
                })
            if u.path == '/api/write':
                s = self.state.song(body['i'])
                diff = body['diff']
                result = songs_mod.generate(s, diff, body.get('params'), save_rules=True)
                self.state.rescan()
                return self.send_json({**result, **self.state.listing()})
            if u.path == '/api/batch':
                diffs = body.get('diffs') or list(songs_mod.FILES)
                params = body.get('params')
                results = []
                for i in body.get('items', []):
                    s = self.state.song(i)
                    for d in diffs:
                        r = songs_mod.generate(s, d, params if params is not None else s.rules(d),
                                               save_rules=params is not None)
                        results.append({'i': i, 'dir': s.name, 'diff': d, **r})
                self.state.rescan()
                return self.send_json({'results': results, **self.state.listing()})
            if u.path == '/api/move':
                with self.state.lock:
                    targets = [self.state.songs[int(i)] for i in body.get('items', [])]
                if not targets:
                    return self.send_json({'error': '移す曲がありません'}, 400)
                try:
                    results = boxes.move(self.state.root, targets, body.get('box', ''))
                except boxes.Busy as e:
                    return self.send_json({'error': str(e)}, 409)
                except ValueError as e:
                    return self.send_json({'error': str(e)}, 400)
                finally:
                    self.state.rescan()
                return self.send_json({'results': results, **self.state.listing()})
            if u.path == '/api/favorite':
                s = self.state.song(body['i'])
                try:
                    result = boxes.set_favorite(self.state.root, s, bool(body.get('on')))
                except boxes.Busy as e:
                    return self.send_json({'error': str(e)}, 409)
                finally:
                    self.state.rescan()
                return self.send_json({**result, **self.state.listing()})
            if u.path == '/api/settings':
                s = self.state.song(body['i'])
                for k in ('title', 'artist'):
                    if k in body:
                        v = (body[k] or '').strip()
                        if v:
                            s.settings[k] = v
                        else:
                            s.settings.pop(k, None)
                songs_mod.save_settings(s.folder, s.settings)
                if (s.folder / 'set.def').exists():
                    songs_mod.write_setdef(s)
                self.state.rescan()
                return self.send_json(self.state.listing())
            if u.path == '/api/playlists':
                syncer = self.state.playlists
                with syncer.lock:
                    cfg = playlist.load_config(syncer.path)
                    if body.get('remove'):
                        cfg['playlists'] = [pl for pl in cfg['playlists'] if pl['url'] != body['remove']]
                    if body.get('url'):
                        url = playlist.playlist_url(body['url'])
                        if not url:
                            return self.send_json({'error': '再生リストの URL ではありません（list= が入った URL を貼ってください）'}, 400)
                        cfg['playlists'] = [pl for pl in cfg['playlists'] if pl['url'] != url]
                        cfg['playlists'].append({'url': url, 'box': (body.get('box') or '').strip()})
                    if body.get('interval'):
                        cfg['interval'] = max(1, int(body['interval']))
                    playlist.save_config(cfg, syncer.path)
                if body.get('url'):
                    syncer.wake.set()   # 足したらすぐ確認
                return self.send_json({'playlists': cfg['playlists'], 'interval': cfg['interval'], 'last': syncer.last})
            if u.path == '/api/playlists/sync':
                if not tubedtx.available()['ok']:
                    return self.send_json({'error': f'TubeDTX が見つかりません: {tubedtx.TUBEDTX_DIR}'}, 400)
                return self.send_json(self.state.playlists.sync())
            if u.path == '/api/add':
                url = tubedtx.clean_url(body.get('url'))
                if not url:
                    return self.send_json({'error': 'URL がありません'}, 400)
                if not tubedtx.available()['ok']:
                    return self.send_json({'error': f"TubeDTX が見つかりません: {tubedtx.TUBEDTX_DIR}"}, 400)
                return self.send_json({'job': self.state.jobs.start(url)})
            return self.send_json({'error': 'not found'}, 404)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self.send_json({'error': str(e)}, 500)


class _Server(ThreadingHTTPServer):
    allow_reuse_address = False   # 同じポートに 2 つ目を起動させない（古いサーバーが残っていると応答が古いままになる）


def make_server(root: Path, port: int, watch_records: bool = True) -> ThreadingHTTPServer:
    state = State(root, watch_records)
    handler = type('BoundHandler', (Handler,), {'state': state})
    srv = _Server(('127.0.0.1', port), handler)
    srv.daemon_threads = True
    return srv
