# play-dtxmania

TubeDTX が作った Master 譜面（score.dtx）から Beginner / Easy を間引いて書き、set.def を整える。
ブラウザで曲を流しながら落下ノーツで確かめる。振るまいの規約は `~/.claude/CLAUDE.md`。

## 動かす
- `python play_dtxmania.py`（= serve。http://127.0.0.1:8767 を開く）
- `python play_dtxmania.py list` / `generate --missing` / `add <YouTube URL>` / `check` / `log`（演奏記録の履歴）
- 標準ライブラリだけ。Python 3.10（システムの `python`）。TubeDTX の venv は `add` のときだけ使う
- テスト: `python -m unittest discover -s tests -v`（songlist には触らない。一時フォルダにコピーして試す）

## 場所
- songlist: `C:\Users\woops\Desktop\dtxmania-4.15.1\songlist`（env `PLAY_DTXMANIA_SONGLIST` で変更）
- TubeDTX: `C:\tools\TubeDTX`（`tubedtx.py` が venv の python で `tubedtx_driver.py` を回す）
- TubeDTX 製の曲 = `tube_dtx_config.json` があるフォルダ。Master は `score_master.dtx` → `score.dtx` の順で探す

## 構成
- `dtx.py` 読み書き（cp932 / CRLF）。自分が書いたファイルは 2 行目に `; play-dtxmania` の印
- `simplify.py` 間引き（docs/simplify-theory.md 3 章の実装）: 本当の小節の格子を検出 → セクション・型・フィル → 層のマスク → 予算で層を剥がす。打点は動かさない
- `songs.py` 走査・set.def・曲ごとの設定 `play_dtxmania.json`
- `server.py` API と配信（音源は Range 対応）。`web/index.html` が UI（1 ファイル）
- `tubedtx.py` URL → TubeDTX 一括変換 → Beginner / Easy
- `records.py` DTXMania の `%LOCALAPPDATA%\DTXMania4\RecordDB.sqlite3`（譜面ごとに最後の 1 回だけ）を書き込み時に写し、
  曲の `play_dtxmania.json` の `plays[難易度]` に追記（時刻はローカル + 9h で入っているので戻す）
- 間引きの考え方（セオリー・新ルール案）は `docs/simplify-theory.md`

## 守ること
- 印の無い score_beginner / score_easy（手作り・別ツール）は絶対に上書きしない
- DTX / set.def は Shift_JIS・CRLF。JSON（設定）は UTF-8
- UI の見た目の決定事項はメモリ `dtx-chart-pipeline` にある（無彩色の黒、黄色・枠線・プリセットは不評）
