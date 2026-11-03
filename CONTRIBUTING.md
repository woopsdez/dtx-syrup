# 開発に参加するとき

趣味の道具です。Issue と Pull Request はどちらも歓迎しますが、次のことだけ守ってください。

- **曲データを添付しない**: 市販曲の音声・動画・譜面（.dtx / set.def）・プレイログは Issue にも PR にも入れない。再現に譜面が要るときは、自作曲か、`tests/` のように小さな人工データを使う
- **他人のソフトを同梱しない**: TubeDTX（Apache-2.0）と DTXMania 4 は利用者が自分で入れるもの。コードや exe をこのリポジトリに入れない。TubeDTX 側の不具合は本家（kidonaru/TubeDTX）へ
- **標準ライブラリだけ**: 依存を増やさない（Python 3.10 で動くこと）。UI は `web/index.html` 1 ファイル
- **テスト**: `python -m unittest discover -s tests -v` が通ること。songlist には触らず、一時フォルダに曲を作って試す
- **生成した譜面の印**: 自分が書いたファイルには 2 行目に `; dtx-syrup` を付け、印の無い譜面（手作り・別ツール）は絶対に上書きしない
- **DTX の文字コード**: DTX と set.def は Shift_JIS・CRLF。設定 JSON は UTF-8

書き方の決めごとや間引きの考え方は `CLAUDE.md` と `docs/` にあります。
