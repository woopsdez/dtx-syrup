"""DTX Syrup: TubeDTX の Master 譜面から Beginner / Easy を作り、ブラウザで確かめる。

python dtx_syrup.py                       # serve（既定）。exe / pythonw からは app
python dtx_syrup.py app                   # 黒いウィンドウ無し。アプリの窓で開き、画面の「終了」で止める
python dtx_syrup.py serve [--port 8767] [--no-browser]
python dtx_syrup.py list                  # 曲と難易度の状態
python dtx_syrup.py generate --missing    # 足りない難易度を既定ルールで書く
python dtx_syrup.py generate "曲フォルダ名" [--diff beginner,easy]
python dtx_syrup.py add <YouTube URL>     # TubeDTX → score.dtx → Beginner / Easy
python dtx_syrup.py check                 # 置き場所と TubeDTX の確認
python dtx_syrup.py log ["曲フォルダ名"]   # DTXMania の演奏記録を取り込んで曲ごとの履歴を出す
共通: --songlist PATH（既定は Desktop の dtxmania-4.15.1/songlist、env DTX_SYRUP_SONGLIST）
"""
from __future__ import annotations

import argparse
import sys
import threading
import webbrowser
from pathlib import Path

import records
import songs as songs_mod
import tubedtx


def cmd_list(root: Path) -> int:
    found = songs_mod.scan(root)
    for i, s in enumerate(found):
        st = s.status()
        mark = ''.join((d[0].upper() if st[d] == 'auto' else d[0] if st[d] == 'hand' else '-') for d in songs_mod.FILES) if s.tube else '  '
        box = f'[{s.box}] ' if s.box else ''
        print(f'{i:3d} [{mark}] {box}{s.title}  -  {s.artist or "?"}  (BPM {s.master.bpm:g}, {len(s.master.notes)} notes, {s.name})')
    tube = sum(s.tube for s in found)
    print(f'{len(found)} songs（TubeDTX 製 {tube}）  ([B]/[E] = DTX Syrup 製, [b]/[e] = 手作り/別ツール, - = 無し, [  ] = TubeDTX 製でない）')
    for b in songs_mod.boxes(root, found):
        print(f"  箱 {b['name']}: {b['count']} 曲")
    return 0


def cmd_generate(root: Path, names: list[str], diffs: list[str], missing: bool) -> int:
    found = [s for s in songs_mod.scan(root) if s.tube]   # 簡易化できるのは TubeDTX 製だけ
    targets = found if missing or not names else [s for s in found if s.name in names or s.title in names]
    if not targets:
        print('対象の曲がありません')
        return 1
    n = 0
    for s in targets:
        for d in diffs:
            if missing and s.status()[d] is not None:
                continue
            r = songs_mod.generate(s, d, s.rules(d))
            print(f"{'ok ' if r.get('ok') else 'skip'} {s.title} / {d}: {r.get('message') or r.get('path')}")
            n += bool(r.get('ok'))
    print(f'{n} ファイル書きました')
    return 0


def cmd_add(root: Path, url: str, dry_run: bool) -> int:
    info = tubedtx.available()
    if not info['ok']:
        print('TubeDTX が見つかりません:', info)
        return 1
    r = tubedtx.run(tubedtx.clean_url(url), on_line=print, dry_run=dry_run)
    if not r['ok']:
        print('TubeDTX が失敗しました')
        return 1
    if dry_run:
        return 0
    folder = Path(r['project_path'])
    song = next((s for s in songs_mod.scan(root) if s.folder == folder), None)
    if song is None:
        print('score.dtx が見つかりません:', folder)
        return 1
    for d in songs_mod.FILES:
        res = songs_mod.generate(song, d, song.rules(d))
        print(d, 'ok' if res.get('ok') else res.get('message'))
    return 0


def cmd_check(root: Path) -> int:
    print('songlist:', root, '(exists)' if root.exists() else '(見つかりません)')
    print('TubeDTX :', tubedtx.available())
    found = songs_mod.scan(root)
    print('曲:', len(found), '/ TubeDTX 製:', sum(s.tube for s in found),
          '/ 箱:', ', '.join(f"{b['name']}({b['count']})" for b in songs_mod.boxes(root, found)) or 'なし')
    return 0


def cmd_log(root: Path, names: list[str]) -> int:
    """DTXMania の記録を取り込んで、曲ごとの履歴（直近 5 回まで）を出す。"""
    found = songs_mod.scan(root)
    added = records.ingest(found)
    if added:
        found = songs_mod.scan(root)   # 追記した分を読み直す
    shown = 0
    for s in found:
        if names and s.name not in names and s.title not in names:
            continue
        plays = s.settings.get('plays', {})
        if not any(plays.values()):
            continue
        print(s.title)
        for d in ('beginner', 'easy', 'master'):
            for pl in plays.get(d, [])[-5:]:
                hit = pl['notes'] - pl['miss']
                rate = hit / pl['notes'] * 100 if pl['notes'] else 0
                auto = '  [auto]' if pl.get('auto') else ''
                print(f"  {pl['at']}  {d:8s} {hit:4d}/{pl['notes']:<4d} ({rate:3.0f}%)  combo {pl['combo']:3d}{auto}")
        shown += 1
    print(f'{len(added)} 件を取り込み、{shown} 曲に記録あり')
    return 0


def _log_to_file() -> None:
    """pythonw / exe（コンソール無し）では print の行き先が無いので、%LOCALAPPDATA%\\DTX Syrup\\dtx-syrup.log に書く。"""
    if sys.stdout is not None and sys.stderr is not None:
        return
    import appconfig
    f = open(appconfig.log_file(), 'a', encoding='utf-8', buffering=1)  # noqa: SIM115 - 終了まで開いておく
    sys.stdout = sys.stderr = f


def cmd_app(root: Path, port: int) -> int:
    """黒いウィンドウを出さずに動かし、画面はアプリの窓（Edge / Chrome の --app）で開く。止めるのは画面の「終了」。"""
    import server
    import window

    _log_to_file()
    url = f'http://127.0.0.1:{port}/'
    try:
        srv = server.make_server(root, port)
    except OSError as e:
        if getattr(e, 'winerror', None) == 10048 or getattr(e, 'errno', None) in (48, 98):
            window.open_app(url)   # もう動いている。窓だけ開く
            return 0
        raise
    print('DTX Syrup:', url, ' songlist:', root, flush=True)
    threading.Timer(0.3, window.open_app, args=(url,)).start()
    try:
        srv.serve_forever()
    finally:
        srv.server_close()
    return 0


def cmd_serve(root: Path, port: int, open_browser: bool) -> int:
    import server

    url = f'http://127.0.0.1:{port}/'
    try:
        srv = server.make_server(root, port)
    except OSError as e:
        if getattr(e, 'winerror', None) == 10048 or getattr(e, 'errno', None) in (48, 98):
            print(f'DTX Syrup はもう起動しています: {url}（ポート {port} が使用中）')
            if open_browser:
                webbrowser.open(url)
            return 0
        raise
    print('DTX Syrup:', url, ' songlist:', root, ' (Ctrl+C で終了)')
    if open_browser:
        threading.Timer(0.5, webbrowser.open, args=(url,)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    if sys.stdout is not None and hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(errors='replace')   # cp932 のコンソールで題名の記号が出せなくても落ちない
    common = argparse.ArgumentParser(add_help=False)  # --songlist はサブコマンドの前後どちらでも
    common.add_argument('--songlist', type=Path, default=None)
    ap = argparse.ArgumentParser(prog='dtx-syrup', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter, parents=[common])
    sub = ap.add_subparsers(dest='cmd')
    p = sub.add_parser('app', parents=[common])
    p.add_argument('--port', type=int, default=8767)
    p = sub.add_parser('serve', parents=[common])
    p.add_argument('--port', type=int, default=8767)
    p.add_argument('--no-browser', action='store_true')
    sub.add_parser('list', parents=[common])
    p = sub.add_parser('generate', parents=[common])
    p.add_argument('names', nargs='*')
    p.add_argument('--diff', default='beginner,easy')
    p.add_argument('--missing', action='store_true')
    p = sub.add_parser('add', parents=[common])
    p.add_argument('url')
    p.add_argument('--dry-run', action='store_true')
    sub.add_parser('check', parents=[common])
    p = sub.add_parser('log', parents=[common])
    p.add_argument('names', nargs='*')
    a = ap.parse_args(argv)
    root = a.songlist or songs_mod.DEFAULT_SONGLIST
    if a.cmd == 'app' or (a.cmd is None and (getattr(sys, 'frozen', False) or sys.stdout is None)):
        return cmd_app(root, getattr(a, 'port', 8767))   # exe / pythonw から引数なしで起動したとき
    if a.cmd in (None, 'serve'):
        return cmd_serve(root, getattr(a, 'port', 8767), not getattr(a, 'no_browser', False))
    if a.cmd == 'list':
        return cmd_list(root)
    if a.cmd == 'generate':
        return cmd_generate(root, a.names, [d.strip() for d in a.diff.split(',') if d.strip()], a.missing)
    if a.cmd == 'add':
        return cmd_add(root, a.url, a.dry_run)
    if a.cmd == 'check':
        return cmd_check(root)
    if a.cmd == 'log':
        return cmd_log(root, a.names)
    ap.print_help()
    return 2


if __name__ == '__main__':
    sys.exit(main())
