# ツムグ 実装手順書（Salesforce 勘案版）— 収集 → 貯める → 分析 → 検索・ランキング → 表示 → デプロイ

作成: 2026-09-22　対象: 9班 もしのゆ（もっちゃん／しの／ゆき）　元: 企画書 v4・合成データ（もっちゃん）＋ 1_ 設計書（ゆき）
完成品: `moshinoyu_claude_test/tsumugu_sf/`（この手順書と同じコード。困ったら見比べる）

> この手順書は `docs/build_guide.py` が実際のコードから自動生成しています。コードを直したら `python docs/build_guide.py` で手順書も更新されます。
> **AI（Claude Code 等）に実装させるときは、この手順書をそのまま渡し、「コードブロックの中身を一字も変えずにファイルを作る」と指示してください。** 説明文は短くしてありますが、コードは全文です。

---

## 0. 全体像

### 0.1 守ること（先に読む）

1. **★3-1 の開発手順 6 段を全部残す**：収集（html スクレイピング・BeautifulSoup）→ DB（SQLite）→ 整理・加工・分析（pandas）→ 検索・ランキング（TF-IDF）→ Web アプリ（Streamlit）→ GitHub・Streamlit Cloud。どれか 1 段を「要らない」と思っても消さない
2. **企業は並べない、ナレッジは並べる**：TF-IDF で並べるのは事例・勘所・支援メニュー。企業の危険度・点数・ランキングは画面にも DB にも持たない
3. **担当者が触るのは SFA の画面だけ**：プロトタイプは Streamlit で SFA の 3 画面を模す。ツムグは「読む」「反応が返る」領域だけを持つ
4. **AI の提案には必ず出典**：判定理由・事例・人には、どの記録のいつの記述かを付ける。出典の無い項目は捨てる（if 文で守る）
5. **気づき欄は評価に使わない／融資判断・信用格付に使わない／融資審査系へ自動連携しない**
6. **LLM が無くても全工程が動く**：キーがあるときだけ ①' ② ④ ⑦ が LLM に切り替わる

### 0.2 作るファイルは 8 つ（PROJECT ZERO W4 の answers と同じ粒度）

| ★3-1 の段 | ファイル | 役割 | 元 |
|---|---|---|---|
| 収集 | `crawler.py` | 公開の事業承継ナレッジ（支援事例・支援メニュー・ガイド）を集める | W2 `crawler.py` そのまま＋2 関数 |
| DB として保存 | `data.json` `schema.sql` `database.py` | 合成の行内データと公開ナレッジを SQLite に貯める | W1 JSON・W3 |
| 設定 | `rules.json` | 予兆語彙 8 語・発火条件・禁止語・判定基準の言葉・クロール先 | — |
| 整理・加工・分析／検索 | `tsumugu.py` | ①'〜⑦ の関数（pandas で照合、if 文で判定、TF-IDF で検索）。全部 dict を返す | W4 `search.py`・tech0-search `who.py` |
| 検索・ランキング | `ranking.py` | TF-IDF | W4 そのまま |
| Web アプリ | `app.py` | SFA の 3 画面（取引先／日報／支店長）＋履歴 | W4 `app.py` |

補助（作らなくてよい）：`requirements.txt`、`.gitignore`、`.streamlit/secrets.toml.example`、`tests/test_tsumugu.py`（証拠用）、
`docs/convert_source_data.py`（もっちゃんの合成データ →`data.json`/`rules.json`）、`docs/knowhow.json`（勘所 8 件）、`docs/build_guide.py`（この手順書の生成）、`data/raw/`（クロール結果のキャッシュ）

**データの出どころ**：`ツムグ合成データ（企画書v4準拠）/`（もっちゃん作成・すべて架空）。10 社・行員 10 名・日報 79 件・事例 6 件・タグ定義・判定基準・デモ入力 3 件が入っている。
`data.json` と `rules.json` はこのフォルダから `python docs/convert_source_data.py` で作る（手で書かない）。

### 0.3 4 日の進み方（全員が同じ工程を通る）

| 日 | ★3-1 の段 | 作るもの | できたら確認すること |
|---|---|---|---|
| **Day 0** | — | フォルダ・requirements | `pip install -r requirements.txt` が通る |
| **Day 1 貯める** | DB として保存 | `schema.sql` `database.py`＋変換（`data.json` `rules.json`） | `python database.py --reset` で 10 社・79 件 |
| **Day 2 集める** | 収集 | `crawler.py` | `python crawler.py` で `knowledge public: 16` 前後 |
| **Day 3 意味をつける・計算する** | 整理・加工・分析／検索・ランキング | `tsumugu.py` `ranking.py` | `python tsumugu.py` でカナイ精工が「反応④」、`pytest -q` が 14 passed |
| **Day 4 見せる** | Web アプリ・デプロイ | `app.py` | 3 画面が動く。GitHub → Streamlit Cloud |

### 0.4 工程間の受け渡し（言葉合わせ）

受け渡しは全部 dict。形は `tsumugu.py` の各関数の docstring と `schema.sql` にだけ書いてある（FB 取り込みシート①）。ここに転記はしない。同じファイルを見る。

```
⓪ crawl_all()                                  → knowledge(public) と sources に行が増える（日報とは独立）
① new_post(...)                                → post{id, company_id, contact_id, author_id, posted_at, text, report_draft}
①' draft_report(post)                          → 文字列（業務報告の下書き）
② extract(post)                                → ext{formal[], candidate[], value[], unclassified}
③ collate(post, ext)                           → profile{timeline[], tag_table[], static{}, value_assets[], assignments[]}
④ assess(profile, ext)                         → signal{fired, reaction 1〜4, tags[], reason, lost_values[], context[], candidates[]}
⑤ retrieve(profile, signal, text)              → knowledge{items[]（行内）, public[]（公開・url 付き）}
⑥ who_to_ask(knowledge, profile, signal)       → people{targets[], predecessors[], dept_fallback[], external[]}（各人に how[]）
⑦ recommend(signal, knowledge, people)         → next_actions{questions[], options[], actions[], public_refs[], grounded_on[]}
run(post)                                      → 上の全部を 1 つの dict に
```

---

## Day 0｜準備

1. `moshinoyu_claude_test/tsumugu_sf/` を作る（W4 版 `tsumugu_w4/` は残す）
2. その中に `tests/` `docs/` `data/raw/` `.streamlit/` を作る
3. 次の 3 ファイルを置く

{{file:requirements.txt}}

{{file:.gitignore}}

{{file:.streamlit/secrets.toml.example}}

4. `pip install -r requirements.txt`（PowerShell は先に `$env:PYTHONUTF8="1"`）
5. **GitHub リポジトリを用意する**（9/15 の「GitHub Flow ハンズオン」と同じ簡易版）
   - 班長：GitHub で New repository（Private 可・README あり）→ Settings > Collaborators で班員 2 名を追加 → 班員は招待を承認
   - 全員：SourceTree（または `git clone`）でローカルに clone し、その中に `3_tsumugu_sf/` を作る
   - 班長：`.gitignore` を最初にコミットして push（**`data/tsumugu.db` と `.streamlit/secrets.toml` を上げないため**）→ 班員は pull

> **道具をそろえ、置き場所を 1 つに決めることで、この後の 4 日間、環境の違いで止まらず、3 人の成果を同じ場所に持ち寄れるようになります。**

---

## GitHub Flow｜毎日の終わりに持ち寄る（全員・4 日間くり返す）

**1 日 1 ブランチ。** その日の作業を自分のブランチで作り、PR を出し、別の人が見て main に入れる。翌日は必ず pull してから始める。

| 日 | ブランチ名の例 | 入るもの |
|---|---|---|
| Day 1 | `feature/day1-database` | `data.json` `rules.json` `schema.sql` `database.py` `docs/convert_source_data.py` |
| Day 2 | `feature/day2-crawler` | `crawler.py`、`data/raw/`（取得済みキャッシュ。**共有する**） |
| Day 3 | `feature/day3-tsumugu` | `ranking.py` `tsumugu.py` `docs/knowhow.json` `tests/` |
| Day 4 | `feature/day4-app` | `app.py`、手順書の再生成 |

**手順（SourceTree でも下のコマンドでも同じことです）**

1. 始める前に main を最新にする

```bash
git switch main
```

```bash
git pull origin main
```

2. その日のブランチを作る（例：Day 1）

```bash
git switch -c feature/day1-database
```

3. 作業 → 動くところまで確認（各 Day の「確認」を通してから）→ コミット

```bash
git add -A
```

```bash
git commit -m "Day1: DB と変換スクリプト"
```

4. push して、GitHub で Pull request を出す（宛先は `main`。何を作ったかを 2〜3 行書く）

```bash
git push -u origin feature/day1-database
```

5. **別の人**が中身を見て承認 → Merge pull request（自分のものを自分で入れない）
6. 全員が main を pull して、翌日はそこから始める

**競合（conflict）が出たら**（9/15 ハンズオンの「班員 B」と同じ状況です）

```bash
git fetch origin
```

```bash
git merge origin/main
```

→ 衝突したファイルを開いて手で直す → `git add` → `git commit` → もう一度 push。**古い main から分けたブランチで長く作業すると起きます。毎日必ず持ち寄るのはこれを小さくするためです。**

**上げてはいけないもの**：`data/tsumugu.db`（毎回作り直せる）、`.streamlit/secrets.toml`（API キー）。どちらも `.gitignore` に入っています。
**上げるもの**：`data.json` `rules.json`（3 人が同じデータで動かすため）、`data/raw/`（クラウドで再クロールしないため）。

> **毎日ブランチを分けて PR を出すことで、3 人が同時に書いても上書き事故が起きず、「誰が何を入れたか」が後から追えるようになります。**

---

## Day 1｜貯める（DB として保存）

### 1-1 `data.json` — 合成の行内データ（W1 の pages_w1.json と同じ位置づけ）

**手で書かない。** もっちゃんの `ツムグ合成データ（企画書v4準拠）/` を `python docs/convert_source_data.py` で変換して作る。
変換がやること：ID はそのまま（C001 / E001 / R0001 / K001）、`reports.json` の 気づき欄（insight）を記録の本文に・業務報告（business_report）を `report_draft` に、
`case_cards.json`（全行共有可）は kind=case・`cases.json`（閲覧制限あり）は kind=case_detail として入れ、`employees.json` の上司（reports_to）と閲覧範囲（access_scope）も持つ。
**答え合わせ用の `reference_tags` / `reference_candidate` は data.json に入れない**（テストだけが元ファイルから読む）。

```bash
python docs/convert_source_data.py
```

> **もっちゃんのデータを変換しておくことで、3 人が同じ企業・同じ日報・同じ答え合わせで開発できるようになります。**

{{file:docs/convert_source_data.py}}

できあがる `data.json` の形（**全文は長いので、1 件ずつの例だけ**。実物は変換で作られる）：

| キー | 件数 | 中身 |
|---|---|---|
| `companies` | 10 | 企業（静的要因の年齢・業歴を含む） |
| `contacts` | 15 | 面談相手 |
| `staff` | 10 | 行員（上司・閲覧範囲つき） |
| `assignments` | 18 | 担当履歴 |
| `consultations` | 4 | 相談履歴 |
| `posts` | 79 | 日報（気づき欄＝本文、業務報告＝report_draft） |
| `knowledge` | 20 | 事例カード 6＋案件詳細 6（非表示）＋勘所 8 |

```json
{
  "companies": [
    {
      "id": "C001",
      "name": "株式会社カナイ精工",
      "industry": "金属加工",
      "founded_year": 1974,
      "employees": 38,
      "owner_name": "金井 健三",
      "owner_age": 72,
      "key_customers": "上州自動車部品株式会社、東毛プレス工業株式会社",
      "dependency": "main",
      "region": "群馬県太田市",
      "branch": "太田支店",
      "tech_note": "特殊薄板加工／地域内で代替先が限られる薄板加工技術を保有",
      "successor_status": "未定",
      "support_status": "記録のみ"
    }
  ],
  "staff": [
    {
      "id": "E001",
      "name": "佐々木 涼太",
      "dept": "太田支店",
      "branch": "太田支店",
      "role": "法人担当",
      "expertise_tags": [],
      "reports_to": "E004",
      "access_scope": "assigned_companies"
    }
  ],
  "posts": [
    {
      "id": "R0063",
      "company_id": "C001",
      "author_id": "E001",
      "contact_id": "C001-P1",
      "posted_at": "2026-04-21",
      "text": "取引先への対応で社内が相当疲弊した様子。社長は「もう若い者に任せられればいいんだが」とおっしゃっていました。",
      "report_draft": "着任のご挨拶。昨年秋の部品不具合の件について伺った。",
      "source_label": "SFA日報（パイロット期間）"
    }
  ],
  "knowledge": [
    {
      "id": "K001",
      "kind": "case",
      "title": "金属加工・40〜49名・従業員承継（前橋支店 2022）",
      "industry": "金属加工",
      "size": "40〜49名",
      "branch": "前橋支店",
      "year": 2022,
      "summary": "工場長への代表交代と技術の文書化",
      "signals": [
        "後継者未定",
        "技術継承の属人化"
      ],
      "actions": [],
      "outcome": "従業員承継。雇用と主要取引を維持",
      "questions": [],
      "handled_by": [
        "E008",
        "E002"
      ],
      "source": "internal",
      "visibility": "全行共有可",
      "url": "",
      "full_text": "工場長への代表交代と技術の文書化 従業員承継。雇用と主要取引を維持 金属加工 従業員承継 後継者未定 技術継承の属人化"
    }
  ]
}
```

### 1-2 `rules.json` — 業務側が書き換える設定

- `formal`：正式タグ **4 語**（もっちゃんの `tags.json` の予兆タグ）。`patterns` は正規表現（変換時の初期値。答え合わせに合わせてある）、`questions` は次回確認する言葉
- `static`：静的要因 2（S01 経営者の高齢化 70 歳以上／S02 長い業歴 50 年以上）。顧客マスタから実行時に判定する
- `candidate`：候補タグの種（海外展開への関心・事業拡大の意欲）。判定には使わない
- `watchlist`：FB 取り込みシート②の 8 語のうち、まだ正式タグでない 4 語。昇格運用で上げる候補（判定には使わない）
- `gate`：発火条件（種類が 3 つ以上。静的要因の「経営者の高齢化」も 1 種として数える。うち 2 系統以上が直近 12 ヶ月）
- `criteria`：判定基準の言葉（`judgment_criteria.md` から変換。LLM にそのまま渡す）
- `forbidden_words`：出力に含めない語（与信転用の防止）
- `sources`：⓪ 収集のクロール先。**公開ページだけ。robots.txt を確認したものだけ載せる**

{{file:rules.json}}

### 1-3 `schema.sql` — W3 を写して、テーブルを足す

W4 版との差分：`sources`（クロール先）、`knowledge.source / visibility / url / crawled_at`、`posts.report_draft / source_label`、
`staff.reports_to / access_scope`、`companies.successor_status / support_status`、`consultations`（相談履歴）、`signals.reaction`、`feedback.kind` が 4 段階。

> **`schema.sql` を書き換えたときは、`data/tsumugu.db` を削除してから作り直す**
>
> - **何の話か**：`schema.sql` は「表の設計図」、`data/tsumugu.db` は「その設計図で作られた実物の表（SQLite のファイル 1 個）」です。
>   設計図に列や表を足しても、**すでに出来ている実物には反映されません**（`CREATE TABLE IF NOT EXISTS` は「無ければ作る」なので、
>   すでに在る表は何もせず素通りします）。そのまま動かすと `table companies has no column named branch` のようなエラーになります。
> - **どうするか**：`data/tsumugu.db` を削除 → `python database.py --reset` で作り直す。
> - **消して大丈夫か**：**大丈夫です。** このファイルは `data.json`（合成データ）と `data/raw/`（クロール結果）から毎回作り直せます。
>   人が手で入れたものは何も入っていません（デモで登録した記録も合成データの一部です）。**消えて困るのは `data.json` と `data/raw/` の方**で、
>   そちらは触りません。心配なら削除ではなく `tsumugu.db` を `tsumugu_backup.db` に名前を変えておけば元に戻せます。
> - **やらなくてよい場合**：`schema.sql` を変えていないなら削除は不要です。`python database.py --reset` だけで中身が入れ替わります。

```bash
python database.py --reset
```

{{file:schema.sql}}

### 1-4 `database.py` — W3 を写して、関数を足す

W4 版との差分：`insert_knowledge`（公開ナレッジを 1 件）、`upsert_source`、`count_knowledge`、`get_sources`。`ingest(reset=True)` は公開ナレッジを消さない。

{{file:database.py}}

**確認**：`python database.py --reset` → `取り込み: {'companies': 10, 'contacts': 15, 'staff': 10, 'assignments': 18, 'consultations': 4, 'posts': 79, 'knowledge': 20}`

> **Day 1 で「貯める」ところまで作ることで、担当者が代わっても企業ごとに記録が残り、後から時系列で読み返せるようになります。**

**この日の終わり**：`feature/day1-database` を push → PR → 別の人が承認 → 全員 pull（§GitHub Flow）

---

## Day 2｜集める（収集：html スクレイピング）

### 2-1 `crawler.py` — W2 の 3 関数はそのまま。2 関数を足す

- `fetch_page / parse_html / crawl_url`：PROJECT ZERO W2 の完成版のまま（1 文字も変えない）
- `to_knowledge(page, source)`：取ってきたページを `knowledge` の 1 行にする
- `crawl_all()`：`rules.json` の `sources` を順に取り、`data/raw/` に保存し、DB に入れる。取得済みは再取得しない。1 件ごとに 2 秒待つ

{{file:crawler.py}}

**確認**：`python crawler.py` → 1 行ずつ `success` / `failed` が出て、最後に `knowledge public: 16`（404 が 1 件混ざるのは正常。失敗は `sources.status` に残る）。
ネットが無い環境では 0 件でもよい。行内ナレッジ 24 件だけで Day 3 以降は動く。

**やってはいけないこと**：行内データ（SFA の日報・顧客マスタ）をスクレイピングで取ること。中小企業庁（chusho.meti.go.jp）などボットを拒否するサイトを `sources` に足すこと。

> **Day 2 で公開ナレッジを集めておくことで、行内に事例が少ない場面でも「参考になる支援メニュー・事例」を出典つきで示せるようになります。**

**この日の終わり**：`feature/day2-crawler` を push → PR → 承認 → 全員 pull。`data/raw/` も一緒に上げる（他の 2 人が再クロールしなくて済む）

---

## Day 3｜意味をつける・計算する（整理・加工・分析／検索・ランキング）

### 3-1 `ranking.py` — W4 をそのまま

`pages` → `knowledge` の読み替えだけ。行内（internal）も公開（public）も同じ索引に入る。

{{file:ranking.py}}

### 3-2 `tsumugu.py` — ①'〜⑦ と run

ポイント：
- **③ collate は SQL で読んで pandas で集計**：記録×正式タグの表を作り、タグごとに初出・最新・件数・担当者を出す（`tag_table`）。担当者をまたぐ「輪郭」がここでできる
- **④ assess は if 文**：`gate()` が G-00〜G-03 を返し、G-03 だけ発火。反応の層（`judgment_criteria.md` の 4 層）は
  ④ 予兆が立つ ＞ ③ 同じ候補タグが 3 回以上 ＞ ② 正式タグはあるが種類の重なりが不十分 ＞ ① 何も付かない（＝正常動作）
- **⑤ retrieve は TF-IDF**：行内を上位 5 件（kind ごとに最低 1 件）、公開を最大 2 件（url 付き）。混ぜない。
  索引に入れるのは **全行共有可の事例カードと公開ナレッジだけ**（`cases.json` 由来の案件詳細は入れない。企画書 v4 §12.3）
- **⑥ who_to_ask は関係の情報だけで選ぶ**：事例カードの担当者＋前任担当＋**相談履歴**（誰が誰に相談したか）。
  各人に「直接相談する／上司に相談する」と上司の名前（`staff.reports_to`）を添える。順位は付けない
- **⑦ recommend は根拠 ID の無い項目を捨てる**。公開の支援メニューは `public_refs` として出典 URL ごと返す
- LLM は `llm_chat()` 1 か所。無ければ全部テンプレ

{{file:tsumugu.py}}

**確認**：`python -c "import tsumugu; tsumugu.retag_all()"` のあと `python tsumugu.py` →
`④ 4 予兆が立つ ['G-03']`、理由文に林・宮本・佐々木の 3 人、`⑤` に公開 2 件（url）、`⑥` に大原・林。

### 3-3 テスト（証拠）

{{file:tests/test_tsumugu.py}}

`pytest -q` → `14 passed`。期待値はもっちゃんの答え合わせ用データそのもの：
**79 件すべての `reference_tags` / `reference_candidate` と一致**、`demo_inputs.json` の D1 反応④／D2 反応②／D3 反応③、
事例は全行共有可のカードだけ、相談先は林（E002）・大原（E007）・前任の宮本（E003）、禁止語 0 件。

> **Day 3 で「意味をつける・計算する」を作ることで、3 人の担当者が別々に書いた記録が 1 つの予兆としてつながり、
> その判断が正しいかどうかをテストで毎回確かめられるようになります。**

**この日の終わり**：`feature/day3-tsumugu` を push → PR → 承認 → 全員 pull。**PR を出す前に `pytest -q` が通っていること**（壊れたものを main に入れない）

---

## Day 4｜見せる（Web アプリ・デプロイ）

### 4-1 `app.py` — SFA の 3 画面を模す

| タブ | SFA の画面 | ツムグの領域 |
|---|---|---|
| 🏢 取引先 | 取引先の画面（訪問前） | 訪問前のまとめ（出典付き）、担当交代が分かるタイムライン |
| 📝 日報 | 日報（訪問後）：一言 → 下書き → 登録 | 反応 ①〜④。④ なら予兆・出典・確認事項・事例・公開メニュー・相談できる人・ボタン 4 つ |
| 👀 支店長 | 支店の担当先一覧 | 対話の状況（段ごと：支援の検討が挙がっている／対話が始まっている／本部に相談中／案件になった／特段の動きなし／今回は見送り。点数・ランキングなし） |
| 🧾 履歴 | — | 監査ログ（秒数付き）・候補タグ・クロール先 |

「SFA の領域（これまで通り）」は枠付きの箱、「〰 ツムグ」は点線の見出し。DB が空なら起動時に取り込み→クロール→タグ付けを自動で行う。

**画面に出す 4 つの状態（`app.py` の `BADGE`）**：①予兆は出ていません（記録は蓄積しています）②過去に関連する記録があります
③これまでにない変化が続いています ④支援の検討が必要かもしれません。**企業を評価する言い方（「静かです」など）は使わず、シグナルの状態を述べる**形で揃える。

**ダッシュボードの部品（`app.py` の上のほうにある小さな関数）**：`badge()` 状態バッジ（反応の 4 層。**点数ではない**）／`tiles()` 数字タイル／
`chips()` 予兆チップ（● 記録 ◆ 顧客データ ＋ 候補）／`memo_list()` 面談メモ履歴（担当交代の区切り入り）／`show_people()`／`show_knowledge()`。
CSS は先頭の `st.markdown("<style>…")` 1 か所だけ（新しいライブラリは入れない）。
取引先の画面は `tsumugu.company_state()` を呼ぶ。**バッジは「実際に出たシグナル」を映す**（蓄積だけで先に「支援の検討」と言わない）。

{{file:app.py}}

**確認**（`demo_inputs.json` の 3 件をそのまま入れる）：`streamlit run app.py` →
① 取引先タブで「株式会社カナイ精工」を開く（訪問前のまとめ・担当交代 林→宮本→佐々木）
② 日報タブ：カナイ精工／2026-09-15／一言「定例訪問。受注状況を確認。斎藤工場長が来春での退職を考えていると、雑談の中で聞いた。」→ 下書き → 登録 → **反応④**
③ 太田電装（宮本）で「決算の説明を受けた。社長から、専務には技術を任せ、経営は外から人を招くことも考え始めたと聞いた。」→ **反応②（立たない）**
④ ヤマト化成（阿部）で「定例訪問。社長がベトナムの展示会への出展を決めたとのこと。現地の通訳を探している。」→ **反応③（候補タグ 4 回目）**
「本部に相談した」を押す → 支店長タブで「本部に相談中」に移る。

> **Day 4 で画面を作ることで、担当者は SFA を開いたまま「読む・書く・反応を受け取る」が一度に済むようになります。**

**この日の終わり**：`feature/day4-app` を push → PR → 承認 → main にマージ。**デプロイは main から行う**（次の 4-3）

### 4-2 LLM を足す（①' ② ④ ⑦。09.08 の run_gpt と同じ）

`.streamlit/secrets.toml.example` を `secrets.toml` にコピーしてキーを書く。サイドバーの「LLM: 使用（OpenAI）」で確認。キー無しと同じ画面が出ることを確認する（差は理由文と下書きの文章だけ）。

> **LLM を後から足せる形にしておくことで、キーが無い環境でもデモができ、キーがあるときだけ文章の質が上がるようになります。**

### 4-3 デプロイ（main → Streamlit Community Cloud）

1. **4 つの PR が全部 main にマージされている**ことを確認し、main を pull しておく（`data/tsumugu.db` と `secrets.toml` は `.gitignore` で除外済み。`data/raw/` は上げてある＝クラウドで再クロールしない）
2. Streamlit Community Cloud で New app → リポジトリ・ブランチ `main`・`app.py` を指定
3. Secrets に `OPENAI_API_KEY` を入れる（任意。無くても全部動く）
4. 以後は main にマージされるたびに自動で再デプロイされる。**当日直前の変更も、必ずブランチ → PR → マージの順で入れる**

> **デプロイしておくことで、役員会の当日に自分の PC を持ち込まなくても、URL を開くだけでデモができるようになります。**

---

## 付録 A：つまずきポイント

| 症状 | 原因 | 直し方 |
|---|---|---|
| `UnicodeEncodeError` | Windows のコンソールが cp932 | `$env:PYTHONUTF8="1"` を先に実行 |
| クロールが全部 `failed` | ネット無し／プロキシ | Day 3 以降は行内ナレッジだけで動く。後で `python crawler.py --refresh` |
| 面談相手の候補が変わらない | selectbox を `st.form` の中に置いた | form の外に置く（app.py のとおり） |
| 直しても画面が変わらない | Streamlit はモジュールを再読込しない | サーバーを止めて `streamlit run` し直す |
| 9 月でも反応④にならない | `retag_all()` を忘れて過去の記録にタグが無い | `python -c "import tsumugu; tsumugu.retag_all()"` |
| LLM を入れたら項目が消えた | 根拠 ID の無い項目を if 文で捨てている | 正常。プロンプトに ID を付けさせる |

## 付録 B：v4 からの変更点（1_ 設計書 §2 と同じ）

1. 「各種データ」に名前：①行内データ ②行内ナレッジ ③**公開ナレッジ（crawler.py）**
2. 処理を反応層（日報ごと）とナレッジ層（⓪収集→貯める→索引）に分ける
3. 反応パネルに「参考になる公開の支援メニュー・事例（出典 URL）」を足す
4. 予兆語彙は **もっちゃんの `tags.json` の 4 語＋静的要因 2**（合成データの答え合わせがこの 4 語のため）。
   FB 取り込みシート②の 8 語のうち残り 4 語は `rules.json` の `watchlist` に置き、昇格運用で正式タグに上げる
5. ボタンに「本部に相談した／案件になった」を足し、支店長画面を 5 段に（攻めの ROI の証拠。ユーザー決定）
6. プロトタイプは Streamlit で 3 画面を模す（v4 のまま）

## 付録 C：拡張性（今回は作らない）

| 困りごと | 選択肢 |
|---|---|
| 言い回しの揺れで検索が外れる | `ranking.py` を埋め込み（ベクトル検索）に差し替え |
| 候補タグを正式タグに昇格させたい | `candidate_tags.count` が閾値を超えたら承認 → `rules.json` に追記 → `retag_all()` |
| 本番（SFA の中に表示） | `tsumugu.py` の関数を API にして SFA の画面拡張から呼ぶ。UI と処理は最初から分けてある（v4 §12.6） |
| 音声入力 | `st.audio_input` ＋ 文字起こし API を ① の前に 1 段 |
| クロール先を増やす | `rules.json` の `sources` に追記するだけ（robots.txt を確認してから） |
