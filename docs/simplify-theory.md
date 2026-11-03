# 間引きのセオリーと新ルール案（2026-11-03 調査）

目的: Master 譜面（TubeDTX の採譜）から Beginner / Easy を作るとき、**曲のリズムと印象的な譜面（サビ・キメ・フィルの着地）を残したまま**薄くする。
いまの `simplify.py` は「位置を拍に丸め、固定の密度マスクで均一に間引く」ので、どの曲も同じメトロノームになり曲とズレる。

## 0. 結論（3 行）
1. **引き算だけ、動かさない**: 元の打点の部分集合を残す。位置の丸め（`js_round(pos*g)`）をやめる
2. **層を 1 枚ずつ剥がす**: HH の細分化 → 裏拍キック → ゴースト/オープン HH → フィルの中身、の順。難易度 = どの層まで剥がすか
3. **セクション単位で同じ削り方**: 小節の自己類似で署名パターンを見つけ、同じセクションは同じマスク。骨格（スネアのバックビート・表拍キック・セクション頭のクラッシュ・フィルの着地）は最後まで守る

## 1. いまのルールの問題（simplify.py 2026-11-02 版）
- `js_round(pos * grid)` で 8 分 / 16 分に**丸めて動かす** → 16 分裏のキックが 8 分へ移り、曲と合わない
- 密度マスクが曲に無関係に固定: Beginner = HH 1・3 拍 / SD 2・4 拍 / BD 1 拍のみ。Easy = HH 8 分 / SD 全部 / BD 4 分
- セクションもフィルも区別しない → サビとイントロが同じ薄さ、フィルは均一に崩れる
- 残っているのは「同時打ちの上限（SD > BD > HH の優先）」「ゴースト削除」「タム削除」。この 3 つはセオリー通りで流用できる

## 2. 調べたセオリー
### 2a. ドラム教育（講師・教則・減譜の慣例）
- **骨格優先**: 曲の構成（イントロ / A / B / サビ）と各セクションのメイングルーヴは残す。初心者版は「同じ曲を薄く叩く」であって別のビートに差し替えない。Drumeo は 1 曲を 5 段階に分け、Lv1 = HH 4 分 + 単純キック + フィルはスネアとキックだけ → Lv2 = HH 8 分 → Lv3 = キック複雑化 → Lv4 = 16 分キック → Lv5 = ダブル、と**上に層を足す**順で示す [D1]
- **残す優先順位**: スネアの 2・4 拍 > 表拍のキック（1・3 拍 / 4 つ打ち） > ハイハット [D2][D3]
- **剥がす順**（Hein の段階的構築の逆順）: 4 分だけ → 8 分裏 HH → 8 分裏キック → 16 分裏 HH → スネアのゴースト → キックの先取り（シンコペ） → オープン HH [H1]。各段階が単体で音楽的に成立する
- **HH は 16 → 8 → 4 分**と段階的に。キック・スネアはそのまま HH だけ 4 分にする練習曲が定番 [D3][R1]
- **キックは表拍を残し、裏拍・16 分裏から落とす**。戻すときは 1 個ずつ [D4]。Rock Band の減譜は「小節内の 3 個目と 7 個目のキックを抜く」方式 [RB1]
- **同時打ち**: Easy = キックと手を同時に叩かせない、Medium = 3 点同時なし [RB1]。子ども指導も「同時なし → 2 肢」の順 [A1]
- **ゴースト・ダブル・フラムは最初に全部落とす**。オープン HH は閉じた HH 扱い [D1][R1]
- **フィル**: 長さと着地（次小節の 1 拍目）は変えず中身を減らす。16 分のタム回し → 8 分のビルドアップ（スネア / フロアタム 8 分 + 4 分キック）[E1]。中身はスネア → キック → タムの順に残す [D5]。最下位難易度ではフィルを省略して同じビートで通す [D4][S1]
- **クラッシュ**: 曲の区切り（A → B、サビ頭）の 1 拍目だけ残し、セクション内のクラッシュは落とす [SM1]。クラッシュは必ずキック / スネアのアクセントと同時 [C1][M1]
- **サビの 1 要素**: A メロ → サビの違いは「1 要素」（1 拍目クラッシュ、HH → ライド、HH 8 分 → 16 分）で出す。簡略化してもこの 1 要素は消さない [C1][M1]
- **均一に間引かず、小節単位で基本パターン（8 beat / 4 beat / 16 beat）のテンプレートへ**。法政大の初心者向け自動採譜研究（2014）は 3 点（SD / BD / HH）へ縮約し、フィルは分離して扱う [HO1]
- **密度の目安**（Rock Band の慣例）: Hard ≒ 8 分 7 個 / 小節、Medium ≒ 4 分 4 個、Easy ≒ 2 個。BPM > 160 や < 80 は曲げてよい [RB1]
- **子ども（6〜10 歳）**: 手足の同期は 6〜7 歳が目安 [B1]。HH / SD / BD の 3 点から、1 太鼓ずつ → 同時なし → 2 肢 [A1]。手の 8 ビートが BPM 80〜90 で安定してから足 [SM2]。正確さ > 速さ、15 分 / 日 [RO1]。テンポは 60 → 75 → 90 → 100% で上げる [S1]（譜面で落とせない分は DTXMania の再生速度で補う）

### 2b. リズムゲームの難度設計（Guitar Hero / Rock Band / DDR / 太鼓 / Rocksmith）
- 下位難易度は上位の**部分集合**として、Expert → Hard → Medium → Easy の順に写して削る。「細かい変奏を消してパターンを反復的に（グルーヴと一貫性のため）」「16 分の拾い音はグルーヴに不可欠なときだけ残し、周囲を薄くする」[GH1]
- Rock Band の減譜: Easy = 1〜2 セクションだけキック + スネア（シンバル抜き）、他のセクションはキックを全部消す、キックと手の同時打ち禁止（キック + クラッシュも不可）、目安 1 小節 2 音。Medium = 4 分主体（右手の 8 分刻みを 4 分に落とすのは 140 BPM 以上のときだけ）、3 肢同時なし、タイムキープの合間のキックは削る、通常ビート中の両手打ちを片手に変えない。Hard = 8 分グリッド（16 分は 8 分に間引く）、目安 8 分 7 個 / 小節。**右手の HH パターンは Hard と Medium で同型にする** [RB2]
- CAT（RBN 準拠の自動減譜ツール）: Expert → Hard → Medium → Easy と**段階的にコピーして間引く**。グリッド既定 Hard = 1/8、Medium = 1/4、Easy = 1/4（ドラム）。グリッド外は ±20 tick まで許容。「sparse」= 直前の残存ノートから 1 グリッド以上離れた裏ノートは残す。「same」= 直前と同じ音なら 1 段細かいグリッドでも残す。キックは Medium で「スネア / タムと重なるとき」、Easy で「何かと重なるとき」削る。ロール区間は保護 [CAT]
- EasyChartGenerator（Clone Hero 用の自動生成）: Hard = 4 分グリッドだが**直前の残存ノートから 1 拍以上空けば位置を問わず残す**（フレーズ頭の拾い音）。1・3 拍はキック + 手 1 音、2・4 拍は最大 2 音。Medium = キックは小節の 1 拍目だけ・単独。Easy = 1・3 拍のみ（1 小節 2 音）。裏拍が表拍より多い曲は半テンポとみなして BPM を 2 倍に [ECG]
- 日本語の DTX / GITADORA / 太鼓の「下位譜面の作り方」を明文化した資料は見つからなかった（DTXMania wiki は操作説明のみ）
- Dance Dance Convolution: 初心者譜面は主に 4 分 / 8 分、最易で 1 音 / 秒未満。「下位譜面は上位の部分集合ではない（人は再構成する）」→ 削除だけで近づけるにはセクション単位のテンプレートが要る [DDC]
- osu!taiko かんたん / ふつう: 音符間隔 ≥ 1/2 拍、連打は 7 個以下で直後に休み、32〜36 拍ごとに休憩、拍間隔を一定にして予測可能に、複数レイヤーを同時に追わせない [T1]
- Rocksmith の Dynamic Difficulty: **フレーズ単位**で難易度レベルを持ち、同じフレーズは曲中どこでも同じ簡略化。細分化は「奇数小節の新規音だけ先に足す」[RS1]
- Yamaha の特許（簡略化演奏データ）: (a) キック / スネアをより基本的なパターンへ置換、(b) キック・スネア・HH 以外を全削除 [Y1]

### 2c. 構造とパターンを計算で見つける（MIR の手法）
- **自己類似**: 小節ごとに（楽器 × 32 分）の 0/1 ベクトルを作り、小節間のハミング距離で自己類似行列。同じセクションのドラムは均質で、急変は転換直前に起きる → 似た小節のクラスタ = セクション、クラスタの最頻小節 = **署名パターン** [W1]
- **フィル = 新規性のピーク**: 各小節と前後 5 小節の正規化 L1 距離を重み平均し、隣との差 ≥ 0.1 の局所ピーク（曲の小節数の 10% 以下）をフィルとする [F1][F2]
- **1 拍目のクラッシュ = 上位の境界**: 3,739 曲の統計で、1 拍目クラッシュは 4 / 8 小節以上の境界に偏る。境界候補に加点する [B2]
- **拍節重み**（16 分、Toussaint 式）: `[5,1,2,1,3,1,2,1,4,1,2,1,3,1,2,1]`、32 分裏は 0。削るのは重みの小さい打点から [GT]
- **シンコペ度**（Longuet-Higgins & Lee）: 打点の直後が休符で、その休符のほうが重みが大きいときの重み差。シンコペ度の高い打点がグルーヴの正体なので**残し**、周囲の弱拍を先に間引く [SP]
- **楽器の重み**（Witek 型の多声シンコペーション）: 低域（キック）のシンコペが最も顕著 → 削除の優先は シンバル > HH > スネア > キック [GT][W2]
- **2 状態還元**: パターンは Low（キック）/ High（スネア）の交替として知覚される。簡略化の下限 = 各拍の Low / High 交替を壊さない（キック・スネアの骨格は最後まで保持）[I1]
- 小節平均の WNBD（最寄り拍までの距離の逆数）が高い小節は「初心者に難しい」→ 間引き率を上げる目安 [SP]

## 3. 新しい間引きの案（2026-11-03 に simplify.py として実装済み）
### A. 位置は動かさない
- `Kept` は元の 32 分の位置を持ち、出力も 32 分解像度のまま書く。grid パラメータは「どの細分化の層まで残すか」の意味に変える

### A'. 本当の小節の格子を先に探す（実装中に分かった前提の崩れ）
- TubeDTX の BPM が曲の 3/4（または 4/3）にずれている曲がある（ジョジョ 黄金の風、ごはん食べヨ）。DTX の 3 小節 = 曲の 4 小節になり、
  「拍頭」「2・4 拍」が DTX の小節では意味を持たない。これが「拍に合わせると曲と合わない」の一因
- 対策: キック・スネアの打点から、小節の長さ（DTX 小節比 1 / 0.75 / 4/3 / 0.5 / 2 / 1.5 / 2/3）と頭の位置を総当たりで決める
  （スネアが 2・4 拍、キックが 1 拍目に乗るほど高い点。はっきり勝るときだけ 1 以外を採る）。以後の解析はこの格子で数え、出力は動かさない
- ごはん食べヨは ×1.33 の格子で型が 6 → 4 にまとまり、手作り Beginner との一致が 19% → 34% に上がった

### B. 小節の署名 → セクション・フィル・境界
- 小節ごとに BD / SD の 16 分位置の集合（+ HH の数、シンバルの有無）を署名にする
- 隣接小節の署名の類似度（Jaccard ≥ 0.75）で連結してセクションにし、各セクションの最頻の署名を**署名パターン**とする
- フィル: タムを含む、または前後の小節との新規性が局所ピークの小節（上限 = 小節数の 10%）
- 境界: セクションの先頭小節。1 拍目のシンバル / クラッシュがあれば境界の確度を上げる
- 半テンポ: スネアが 3 拍目だけの曲（裏拍 > 表拍）は 2 小節を 1 小節として扱う（EasyChartGenerator の BPM 2 倍と同じ）
- 拾い音: 直前の残存打点から 1 拍以上空いている打点は、グリッド外でも残す（フレーズ頭を消さない）

### C. 層ごとの削除（難易度 = どの層まで剥がすか）
打点ごとに「拍節重み × 楽器の重み + シンコペ度 + 一貫性ボーナス（セクション内の小節の 80% 以上に同じ打点がある）」の点を付け、**セクションの署名パターンに対して 1 回だけ**目標密度まで低い点から削り、同じマスクをセクションの全小節に当てる。
目標密度は BPM で換算する（1 秒あたりの打点数の上限: Beginner ≈ 2 打 / 秒、Easy ≈ 4 打 / 秒）。

| 層 | Beginner | Easy |
|---|---|---|
| ゴースト・ダブル・フラム | 落とす | 落とす |
| オープン HH | 閉じた HH 扱い | そのまま |
| HH の細分化 | 4 分（打点の多い位相を選ぶ） | 8 分 |
| キック | 表拍 + 一貫性の高い裏拍 1 つまで（小節に 2 つまで） | 8 分位置まで（16 分裏は署名のときだけ） |
| スネア | 2・4 拍（無い曲は重みの高い 2 つ） | ゴースト以外すべて |
| タム・シンバル | セクション頭のクラッシュだけ | クラッシュ + ライドの 4 分 |
| 同時打ち | 1 肢（例外: セクション頭のクラッシュ + キック） | 2 肢（3 点同時なし） |

### D. フィル
- Beginner: フィルの中身は省略してビートを続け、**着地（次小節 1 拍目のクラッシュ + キック）だけ残す**。タムで遊ばせたい曲は「4 分のタム 2 つ」まで
- Easy: 8 分位置の打点だけ残す（スネア → フロアタム → キックの順に優先）。着地は必ず残す

### E. キメ（アクセント）
- 署名パターンに無い打点で、2 レーン以上が同時に鳴る裏拍の打点（例: キック + クラッシュ）はキメ。重みに関わらず残す（Beginner は優先の高い 1 レーンに縮約）

### F. プレイログで調整
- `play_dtxmania.json` の `plays[難易度][-1].map`（64 区間のミス地図）を小節に写し、**ミスが集中したセクション**を 1 層薄くする（小節単位ではなくセクション単位。一貫性を保つため）
- ミス率が低い（< 10%）セクションは次回 1 層戻す。書く → 遊ぶ → 記録 → 調整、の繰り返し

### G. UI の調整項目（grid / hh / sd / bd / toms / ghost / chord を置き換える）
- 層のスイッチ: HH の細分化（4 / 8 / 16）、裏拍キック（なし / 署名だけ / 8 分まで / 全部）、ゴースト、オープン HH、フィル（省略 / 8 分 / 全部）、同時打ち（1 / 2 / 3）
- 曲全体の濃さ（打 / 秒の上限）と、セクションごとの上書き（ミス地図から自動提案）

## 4. 検証の仕方
- 既存の手作り 4 曲（らんま・姫様・野原ひろし・ちゅ）との一致率（現状 5% 前後）が上がるか
- UI で曲を流して「同じ曲を叩いている感」（サビの 1 要素、フィルの着地）が残っているか
- `python play_dtxmania.py log` の Miss 率が、同じ曲で下がるか

## 5. 出典
- [D1] Drumeo: Smells Like Teen Spirit を 5 段階に https://www.drumeo.com/beat/?p=24183
- [D2] Drumeo: 練習の順序 https://www.drumeo.com/beat/?p=30547
- [D3] stemsplit: 初心者向けの曲 https://stemsplit.io/ja/blog/beginner-drum-songs
- [D4] Drumeo: 初心者が曲を覚える https://www.drumeo.com/beat/?p=40080
- [D5] Drumeo: フィルの覚え方 https://drumeo.com/beat/?p=28136
- [R1] Rockschool Drums Method for Beginners https://musicgurus.com/courses/rockschool-drums-method-for-beginners
- [H1] Ethan Hein: Funky Drummer を段階的に組む https://www.ethanhein.com/wp/2023/building-the-funky-drummer-beat/
- [E1] eMastered: フィルのパターン https://emastered.com/ja/blog/drum-fill-patterns
- [SM1] 島村楽器: クラッシュの使いどころ https://www.shimamura.co.jp/update/?p=25514
- [SM2] 島村楽器 武蔵村山: 子どものドラム https://www.shimamura.co.jp/shop/musashimurayama/article/lesson/20260110/7071
- [C1] Cursa: Rock drumming essentials（dynamics / crash & ride） https://cursa.app/en/page/rock-drumming-essentials-dynamics-simplicity-and-playing-with-a-band
- [M1] muzines: Stick Trix https://www.muzines.co.uk/articles/stick-trix/12812
- [A1] Alfred: 子どもにドラムを教える https://www.alfred.com/blogs/alfred-music-blog/creative-alternatives-teaching-young-drummers
- [B1] Bach to Rock: 何歳から https://www.bachtorock.com/?p=41624
- [RO1] Roland: 子どもと V-Drums Q&A https://www.roland.com/jp/lp/vdrums_for_child/qa/01/
- [S1] stemsplit（テンポの上げ方、同 D3）
- [HO1] 法政大 曽我 2014: 初心者向けドラム自動採譜 https://www.slp.k.hosei.ac.jp/doc/2014/11k1025_2.pdf
- [RB1][RB2] Rock Band 減譜の慣例（元スレは 404、検索要約のみ） https://rhythmgamingworld.com/?p=397118 https://rhythmgamingworld.com/?p=389964 https://rhythmgamingworld.com/?p=391313
- [GH1] Guitar Hero 下位難易度の作り方 https://mariteaux.somnolescent.net/modding/guitar-hero/tutorials/authoring-lower-difficulties/
- [CAT] C3 Automation Tools（RBN 準拠の減譜: `reduce_5lane` / `remove_notes` / `remove_kick`） https://github.com/abefacciazzi/CAT
- [ECG] EasyChartGenerator（`notes_to_diff_drums`） https://github.com/eerovil/EasyChartGenerator
- [DDC] Dance Dance Convolution https://arxiv.org/abs/1703.06891
- [T1] osu!taiko ランキング基準 https://osu.ppy.sh/wiki/en/Ranking_criteria/osu!taiko
- [RS1] Rocksmith DDC https://customsforge.com/topic/2863-dynamic-difficulty-creator/ https://customsforge.com/topic/10147-ddc-best-practices/
- [Y1] Yamaha US5650583 https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/5650583
- [W1] Wei+ ISMIR 2019（ドラムの自己類似とセクション） https://archives.ismir.net/ismir2019/paper/000104.pdf
- [F1] フィル検出（新規性） https://arxiv.org/abs/2209.00291 ／ [F2] https://doi.org/10.1007/978-3-030-70210-6_6
- [B2] 1 拍目クラッシュと構造境界 https://arxiv.org/pdf/2209.10259
- [GT] GrooveToolbox（拍節重み・多声シンコペ） https://github.com/fredbru/GrooveToolbox
- [SP] SynPy（LHL / WNBD） https://zenodo.org/record/851079
- [W2] Witek 型シンコペーション https://10053r.github.io/blog/files/7_CMMR_2017_paper_83.pdf
- [I1] 2 状態還元 ISMIR 2020 https://program.ismir2020.net/static/posters/359.pdf
