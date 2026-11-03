# DTX Syrup

DTXMania で遊ぶための、趣味の道具です。譜面に「シロップをかけて甘くする」＝簡単にします。

1. **楽曲追加** — YouTube の URL（または曲名検索）→ TubeDTX で Master 譜面を作る
2. **楽曲簡易化** — Master から Beginner / Easy を作る。打点は動かさず、曲のセクションごとに層を 1 枚ずつ剥がす（考え方は [docs/simplify-theory.md](docs/simplify-theory.md)）
3. **練習のリフレクション** — DTXMania の演奏記録を曲ごとに貯め、ミスが集中した区間だけ薄くする
4. **楽曲管理** — 曲リスト、難易度の set.def、DTXMania の箱（フォルダ）

ブラウザで曲を流しながら落下ノーツで確かめて、よければ曲フォルダに `score_beginner.dtx` / `score_easy.dtx` と `set.def` を書きます。

> DTX Syrup は TubeDTX および DTXMania の作者とは無関係の非公式ツールです。趣味の範囲で、自己責任で使ってください。

## 必要なもの
- Windows 10 / 11、Python 3.10 以上（標準ライブラリだけで動きます）
- [DTXMania 4](https://dtxmania.net/)（© FROM / Kenji Yamazaki）— 遊ぶ側。別途インストール
- [TubeDTX](https://github.com/kidonaru/TubeDTX)（kidonaru 氏、Apache-2.0）— 楽曲追加に使う。別途インストールし、`setup.bat` で venv を作っておく（既定の場所は `C:\tools\TubeDTX`、環境変数 `TUBEDTX_DIR` で変更）
- 電子ドラム（任意）。DTXMania 側でパッドの割り当てをしておく

TubeDTX も DTXMania も、このリポジトリには含まれていません。

## 始め方
```
git clone https://github.com/woopsdez/dtx-syrup.git
cd dtx-syrup
python dtx_syrup.py
```
http://127.0.0.1:8767 が開きます。songlist の既定は `~/Desktop/dtxmania-4.15.1/songlist`、環境変数 `DTX_SYRUP_SONGLIST` か `--songlist` で変えられます。
`dtx-syrup.cmd` をデスクトップのショートカットにしておくとコマンドを覚えなくて済みます。

## 使い方
- **曲を足す**: 曲リストの「＋ YouTube から作る」→ URL を貼るか曲名で検索 → サムネで試聴 → 「作る」。数分で Master / Beginner / Easy と set.def ができます
- **薄くする**: 曲を開いて BEGINNER / EASY を聴き比べ、「間引きルールを調整」でレベル（0〜5）や層（ハイハットの細分化、キック、スネア、フィル、同時打ち）、濃さの上限（1 秒あたりの打点数）を変えて「この設定で書く」。背景動画は既定で入れません（DTXMania 4 には動画をオフにする設定が無く、重い PC では引っかかるため。調整欄で入れられます）
- **振り返る**: DTXMania で遊ぶと記録が曲ごとに貯まります（`python dtx_syrup.py log` で一覧）。「ミスが集中した区間を 1 段薄く」にチェックして書き直すと、苦手な区間だけ薄くなります
- CLI: `python dtx_syrup.py list | generate --missing | add <URL> | check | log`

## 注意してほしいこと
- 動画の取得は TubeDTX（yt-dlp）が行います。YouTube の利用規約は、サービスが明示的に許可した場合を除きコンテンツのダウンロードを認めていません。**自分に権利があるか、権利者が許可した音源に限って**使ってください。違法にアップロードされたと知りながら取得することは日本の著作権法でも違法です
- **生成した音声ファイルや、音源入りの譜面を再配布しないでください**。DTX の界隈では譜面（.dtx / set.def）だけを配り、音源は各自が用意するのが作法です
- TubeDTX の作者は「趣味の範囲での使用目的・商用利用は推奨しない」としています。DTX Syrup も同じです
- 採譜の精度や法的な適合性は保証しません（MIT ライセンスの無保証条項のとおり）

## クレジット
- [TubeDTX](https://github.com/kidonaru/TubeDTX) — kidonaru 氏。Apache-2.0。DTX Syrup は TubeDTX を同梱せず、利用者が導入した TubeDTX の venv 内で関数を呼び出します。TubeDTX が使う yt-dlp（Unlicense）、demucs（MIT）、Magenta Onsets and Frames（Apache-2.0、E-GMD データセットは CC BY 4.0）、ffmpeg（LGPL 2.1+）、gradio（Apache-2.0）の各ライセンスは利用者が各自従うものです
- [DTXMania](https://dtxmania.net/) — FROM / Kenji Yamazaki。DTX 形式と set.def の仕様に従って譜面を書きます
- 調べた規約と界隈のマナーは [docs/project-policy.md](docs/project-policy.md) にまとめてあります

## ライセンス
MIT License — Copyright (c) 2026 woopsdez。[LICENSE](LICENSE)

## English
DTX Syrup is a hobby tool for DTXMania (a drum rhythm game): add songs via TubeDTX, simplify Master charts into Beginner / Easy without moving any hit (section-aware, layer by layer), keep per-song play logs from DTXMania to thin out the parts you miss, and manage your song folders. Python 3.10 standard library only; Windows. TubeDTX (Apache-2.0, by kidonaru) and DTXMania 4 (© FROM) are not bundled and must be installed separately. Not affiliated with or endorsed by their authors. Use only audio you have the rights to, never redistribute generated audio or charts with audio, personal use only. MIT License.
