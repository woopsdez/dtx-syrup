# DTX Syrup

DTXMania で遊ぶための道具。(1) 楽曲追加（YouTube → TubeDTX → 譜面）、(2) 楽曲簡易化（Master から Beginner / Easy）、
(3) 練習のリフレクション（DTXMania の演奏記録を曲ごとに貯めて譜面に反映）、(4) 楽曲管理（曲リスト・set.def）。
ブラウザで曲を流しながら落下ノーツで確かめる。振るまいの規約は `~/.claude/CLAUDE.md`。

## 動かす
- `python dtx_syrup.py`（= serve。http://127.0.0.1:8767 を開く）
- `python dtx_syrup.py list` / `generate --missing` / `add <YouTube URL>` / `check` / `log`（演奏記録の履歴）
- 標準ライブラリだけ。Python 3.10（システムの `python`）。TubeDTX の venv は `add` のときだけ使う
- テスト: `python -m unittest discover -s tests -v`（songlist には触らない。一時フォルダにコピーして試す）

## 場所
- songlist: 既定は `~/Desktop/dtxmania-4.15.1/songlist`（env `DTX_SYRUP_SONGLIST` か `--songlist` で変更）
- TubeDTX: `C:\tools\TubeDTX`（`tubedtx.py` が venv の python で `tubedtx_driver.py` を回す）
- 曲 = `set.def` か `*.dtx` があるフォルダ。箱 = songlist 直下の `DTXFiles.<名前>`（箱の中も、zip の包み紙も辿る。箱・包み紙ごと動かす）
- TubeDTX 製の曲 = `tube_dtx_config.json` があるフォルダ。Master は `score_master.dtx` → `score.dtx` の順で探す。簡易化できるのはこれだけ
  （配布譜面は一覧・表示・★・箱移動だけ。set.def は読むだけで書き換えない。DTXCreatorAL の DTX は UTF-16）

## 構成
- `dtx.py` 読み書き（cp932 / CRLF）。自分が書いたファイルは 2 行目に `; dtx-syrup` の印（改名前の `; play-dtxmania` も自分の印として読む）
- `simplify.py` 間引き（docs/simplify-theory.md 3 章の実装）: 本当の小節の格子を検出 → セクション・型・フィル → 層のマスク → 予算で層を剥がす。打点は動かさない
- `songs.py` 走査（箱・全曲）・set.def・曲ごとの設定 `dtx_syrup.json`。`boxes.py` 箱へ曲フォルダを移す / ★お気に入り
  （= `DTXFiles.★お気に入り` へ移し、元の箱は `dtx_syrup.json` の `box` に控える。`shutil.move`、dtxmania.exe 起動中は拒否）
- `server.py` API と配信（音源は Range 対応）。`web/index.html` が UI（1 ファイル）
- `tubedtx.py` URL → TubeDTX 一括変換 → Beginner / Easy
- `playlist.py` YouTube の再生リストを見張り（既定 15 分ごと）、songlist に無い動画だけ TubeDTX のジョブへ → 指定の箱へ移す。
  設定は `dtx_syrup.local.json`（.gitignore 済み）。`notify.py` 完了・失敗を Windows の通知で（PowerShell の WinRT）。
  ジョブの % は `tubedtx.progress`（段階の位置 + 経過時間。ドラム分離は demucs の % 表示）
- `appconfig.py` 利用者ごとの設定 `%LOCALAPPDATA%\DTX Syrup\config.json`（songlist / tubedtx_dir）。`window.py` Edge / Chrome の --app で開く
- `setup_tubedtx.py` TubeDTX の自動セットアップ（Python 3.10・git を winget、本家を v1.4.0 のコミットで clone、setup.bat と同じ pip）。画面の「設定」と `setup` コマンド
- 起動: `pythonw dtx_syrup.py app`（黒いウィンドウ無し、画面の「終了」で止める）。exe は `py -3.10 toolsuild_exe.py` → dist\DTX Syrup.exe（7 MB）
- `audio.py` bgm.ogg の長さ（Ogg のページを読む）。DTXMania は最後のチップで結果画面へ移るので、書くときは音源の終わりに無音チップ
  （曲フォルダの silence.wav、#WAVZZ、ch 61）を置いて歌が終わるまで演奏を続ける
- 背景動画: DTXMania 4.15.1 の設定は「全画面 / 中央寄せ」の 2 択でオフが無い（動画のデコードが重い）。外したい曲だけ書く譜面から `#AVI` と ch 54 / 5A を外せる（params `movie`、既定 True = 入れる。本人は演奏中の動画は残したい）
- `records.py` DTXMania の `%LOCALAPPDATA%\DTXMania4\RecordDB.sqlite3`（譜面ごとに最後の 1 回だけ）を書き込み時に写し、
  曲の `dtx_syrup.json` の `plays[難易度]` に追記（時刻はローカル + 9h で入っているので戻す）
- 間引きの考え方（セオリー・新ルール案）は `docs/simplify-theory.md`

## 守ること
- 印の無い score_beginner / score_easy（手作り・別ツール）は絶対に上書きしない
- DTX / set.def は Shift_JIS・CRLF。JSON（設定）は UTF-8
- UI の見た目の決定事項はメモリ `dtx-chart-pipeline` にある（無彩色の黒、黄色・枠線・プリセットは不評）
- お気に入り・分類は道具の中のタグにしない。DTXMania の箱（フォルダ）そのものを動かす（本人の選択）。曲リストの設定は localStorage `pd.list`
