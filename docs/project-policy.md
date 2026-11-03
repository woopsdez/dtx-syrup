# 公開の方針（2026-11-03 調査）

DTX Syrup を GitHub で公開するにあたり、DTXMania・TubeDTX・依存ソフトの規約と、DTX 界隈のマナーを調べてまとめたもの。
結論: **MIT で公開し、他人のソフト・音源・譜面は一切同梱せず、「非公式・趣味用・自己責任」を README に明記する**。

## 1. 規約として確認できたこと
| 相手 | 事実 | DTX Syrup への影響 |
|---|---|---|
| DTXMania 4（dtxmania.net、© FROM / Kenji Yamazaki） | 配布は exe 1 つの zip。利用規約・ライセンス文なし、ソース非公開。曲データは「別途用意」 | 権利留保として扱う。リンクと © 表記のみ。本体・スキン・音源・譜面を同梱しない [D1] |
| 旧 DTXMania（OSDN） | 2010 年に MIT でオープンソース化。派生版の登場を作者が肯定 | 派生ではなく周辺ツールだが、同じ精神で MIT を選ぶ [D2][D3] |
| DTX / set.def 形式 | ライセンスや実装制限の記述なし。第三者実装が多数（dtx2midi、DTX Charter、TubeDTX…）。set.def の公式仕様は dtxmania.net にある | 書いてよい。仕様は公式文書に従う [D4][D5] |
| TubeDTX（kidonaru、v1.4.0） | Apache-2.0（NOTICE ファイル無し）。README の注意は「趣味の範囲での使用目的・商用利用は推奨されません」の 1 文 | 同梱せず venv 内の関数を呼ぶだけなので Apache の義務は無し（§1 で「インターフェースで結合するだけの作品」は派生物に含まれない）。作者の「趣味目的」の方針は引き継ぐ [T1][T2][O1] |
| TubeDTX の依存 | yt-dlp = Unlicense、demucs = MIT、Magenta（Onsets and Frames）= Apache-2.0、E-GMD データセット = CC BY 4.0、ffmpeg = LGPL 2.1+（GPL ビルドあり）、gradio = Apache-2.0 | 下流利用を禁じるものは無し。利用者が各自従う旨を README に書く [T3][T4] |
| YouTube 利用規約 | 「サービスが明示的に許可した場合を除き Content のダウンロード禁止」（旧規約の「download ボタンがあれば可」の文言は現行版に無い） | 動画取得は TubeDTX（yt-dlp）が行うが、README で「自分に権利がある・許諾のある音源に限る」「自己責任」を明記 [T5] |
| 日本の著作権法 | 私的使用の複製（30 条）は原則適法。違法アップロードと知りながらの DL は 2021 年から全著作物で違法（有償著作物は刑事罰） | 「違法アップロードと知りながらの取得はしない」「生成した音声・音源入り譜面を再配布しない」を README に書く [T6] |
| Segoe UI Emoji（いまのアイコンの元） | Microsoft のフォント FAQ はロゴ画像化を許すが「文字を個別に扱う」画像は不可。1 グリフのアイコンは明文化なし＝グレー | 公開前に microsoft/fluentui-emoji（MIT、Windows 11 と同じデザイン）の Drum に差し替える [O2][O3] |

## 2. 界隈のマナー（規約ではないが守る）
- 曲データ（音楽・動画）は本人作か許諾がある場合を除き同梱しない。版権曲は「著作権的にかなり黒いグレー」「自己責任」が界隈の共通認識 [D6][D7]
- 譜面を配るときは **.dtx と set.def だけ**（「曲ファイルは付属しておりません」「BGM を別途用意」が定着）[D8]
- DTXMania AL は「公開・販売されている著作権つきの楽曲を引用した DTX のプレイ動画公開はご遠慮下さい」[D9]
- 名乗り方: 「DTXMania 〜」「TubeDTX 〜」のような、作者の承認を示唆する名前にしない（DTX は譜面形式名なので「DTX Syrup」は可）。README に「TubeDTX / DTXMania の作者とは無関係で、公式でも承認済みでもない」を 1 行 [O4][O5]
- 自分が TubeDTX を直したいときは、この道具に取り込まず本家へ Issue / PR（Apache-2.0 なので可能）

## 3. リポジトリに入れないもの
- 市販曲の音声・動画・譜面（.ogg / .mp3 / .mp4 / .webm / .dtx / .bms）。GitHub は DMCA 通知で無効化され、繰り返すとアカウント停止 [O6]
- 個人のプレイログ（曲フォルダの dtx_syrup.json）、songlist そのもの、TubeDTX の作業フォルダ
- ユーザー名入りの絶対パス、トークン。置き場所は環境変数か、無視対象のローカル設定ファイルで渡す [O7]
- 他人のバイナリ（dtxmania.exe、チップ音 chips\*.xa、TubeDTX のコード）

## 4. 形
- **ライセンス**: MIT（`LICENSE`、Copyright 2026 の表示名は本人が決める）。特許条項も同梱もないので Apache-2.0 にする理由は無い [O1][O8]
- **README**: 何をするか（4 つの役割）/ 必要なもの（TubeDTX = Apache-2.0 by kidonaru、DTXMania 4 © FROM。各自導入）/ セットアップ / 使い方 / 注意（上記 1〜3）/ クレジットと非公式表明 / ライセンス / 末尾に短い English [O9]
- **THIRD_PARTY_NOTICES.md**: アイコン（fluentui-emoji、MIT）の表記。TubeDTX・DTXMania は同梱しないのでクレジットのみ
- **.gitignore**: Python の定番 + 音声・動画・譜面 + ローカル設定 + `.claude/`
- **CONTRIBUTING.md**: Issue / PR の作法、テストの走らせ方（`python -m unittest discover -s tests`）、「版権曲の譜面や音源を添付しない」
- **CI**: `.github/workflows/test.yml` で windows-latest + Python 3.10 の unittest。`tests/__init__.py` を置く（3.11 以降の discover 互換）[O10][O11]
- **リリース**: SemVer。`git tag -a v0.1.0` → `gh release create v0.1.0 --generate-notes` [O12]

## 出典
- [D1] https://dtxmania.net/ ／ https://dtxmania.net/documents/install-and-uninstall/
- [D2] https://dtxmania.net/documents/what-dtxmania-has-aimed-for/
- [D3] https://ja.wikipedia.org/wiki/DTXMania ／ https://github.com/yyagi8864/dtxmania
- [D4] https://github.com/limyz/DTXmaniaNX/wiki/Extended-DTX-Data-Format
- [D5] https://dtxmania.net/documents/create-setdef/
- [D6] https://w.atwiki.jp/dtxmaniawiki/pages/19.html
- [D7] https://ja.wikipedia.org/wiki/DTXMania（曲データの同梱について）
- [D8] https://hiiro-game.seesaa.net/article/518327813.html
- [D9] https://senamih.com/dtxal
- [T1] https://github.com/kidonaru/TubeDTX ／ [T2] https://raw.githubusercontent.com/kidonaru/TubeDTX/main/LICENSE
- [T3] https://github.com/yt-dlp/yt-dlp#readme ／ https://github.com/facebookresearch/demucs ／ https://github.com/magenta/magenta ／ https://magenta.tensorflow.org/datasets/e-gmd
- [T4] https://ffmpeg.org/legal.html ／ https://github.com/gradio-app/gradio/blob/main/LICENSE
- [T5] https://www.youtube.com/t/terms?hl=ja ／ https://www.youtube.com/t/terms?hl=en&gl=US
- [T6] https://www.bunka.go.jp/seisaku/chosakuken/hokaisei/r02_hokaisei/ ／ https://www.bunka.go.jp/seisaku/chosakuken/hokaisei/92735201.html
- [O1] https://www.apache.org/licenses/LICENSE-2.0 ／ https://choosealicense.com/licenses/mit/
- [O2] https://learn.microsoft.com/en-us/typography/fonts/font-faq ／ [O3] https://github.com/microsoft/fluentui-emoji
- [O4] https://www.apache.org/foundation/license-faq.html ／ [O5] https://creativecommons.org/licenses/by/4.0/
- [O6] https://docs.github.com/en/site-policy/content-removal-policies/dmca-takedown-policy
- [O7] https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository
- [O8] https://choosealicense.com/licenses/apache-2.0/ ／ [O9] https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes
- [O10] https://docs.github.com/en/actions/use-cases-and-examples/building-and-testing/building-and-testing-python ／ [O11] https://docs.python.org/3/library/unittest.html#test-discovery
- [O12] https://semver.org/ ／ https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository
