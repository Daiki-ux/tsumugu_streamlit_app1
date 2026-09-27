-- =============================================================
-- schema.sql — ツムグ Salesforce 勘案版のテーブル定義（SQLite）。書き方は PROJECT ZERO W3 の schema.sql と同じ
--   新規入力は posts（SFA の日報の「気づき欄」に相当）だけ。
--   companies / contacts / staff / assignments / knowledge(internal) は「銀行が既に持っているデータ」の役（合成）。
--   knowledge(public) と sources は ⓪ 収集（crawler.py）が入れる公開ナレッジ。
-- =============================================================

-- 担当先企業（静的要因を含む）
CREATE TABLE IF NOT EXISTS companies (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    industry        TEXT,
    founded_year    INTEGER,
    employees       INTEGER,
    owner_name      TEXT,
    owner_age       INTEGER,
    key_customers   TEXT,
    dependency      TEXT,           -- 合成データの category（main | emerging | normal | positive）
    region          TEXT,
    branch          TEXT,
    tech_note       TEXT,
    successor_status TEXT,          -- 顧客マスタの後継者欄（未定 | 検討中 | 子息が入社済 …）
    support_status  TEXT            -- 導入時点の対話状況（記録のみ | 対話中）
);

-- 面談相手（企業側の人物）
CREATE TABLE IF NOT EXISTS contacts (
    id          TEXT PRIMARY KEY,
    company_id  TEXT NOT NULL,
    name        TEXT NOT NULL,
    role        TEXT,
    FOREIGN KEY (company_id) REFERENCES companies(id)
);

-- 行員マスタ
CREATE TABLE IF NOT EXISTS staff (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    dept            TEXT,
    branch          TEXT,
    role            TEXT,
    expertise_tags  TEXT,           -- カンマ区切り
    reports_to      TEXT,           -- 上司の staff.id（「上司に相談する」で使う）
    access_scope    TEXT            -- assigned_companies | branch | consulted | all（閲覧範囲の想定）
);

-- 担当履歴（前任担当の導出に使う）
CREATE TABLE IF NOT EXISTS assignments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id  TEXT NOT NULL,
    staff_id    TEXT NOT NULL,
    from_date   TEXT NOT NULL,      -- YYYY-MM-DD
    to_date     TEXT                -- NULL = 現任
);

-- SFA の日報。text が業務報告（いつも書いているもの）。ツムグは新しい入力欄を持たず、これをそのまま読む
--   （変更記録 6_… の CH-05：気づき欄・小耳欄は置かない）
CREATE TABLE IF NOT EXISTS posts (
    id            TEXT PRIMARY KEY,
    company_id    TEXT NOT NULL,
    contact_id    TEXT,
    author_id     TEXT NOT NULL,
    posted_at     TEXT NOT NULL,    -- YYYY-MM-DD
    text          TEXT NOT NULL,    -- 業務報告
    activity      TEXT,             -- 活動区分（定例訪問 | 決算説明 | …）
    source_label  TEXT,             -- 過去日報（導入時に取り込み） | SFA日報（パイロット期間）
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 記録から抽出したタグ（正式 / 候補 / 価値）
CREATE TABLE IF NOT EXISTS post_tags (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id           TEXT NOT NULL,
    tag_id            TEXT NOT NULL,
    tier              TEXT NOT NULL,   -- formal | candidate | value
    evidence          TEXT,
    confidence        REAL DEFAULT 0.0,
    method            TEXT,            -- rule | llm
    origin            TEXT,            -- report | hearsay（引用した文が「雑談で」「らしい」等の伝聞＝未確認）
    confirmed_by_user INTEGER DEFAULT 0,
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE
);

-- 候補タグの出現回数（昇格提案の材料。v4 §9.1）
CREATE TABLE IF NOT EXISTS candidate_tags (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    count       INTEGER DEFAULT 0,
    first_seen  TEXT,
    last_seen   TEXT,
    status      TEXT DEFAULT 'candidate'  -- candidate | proposed | formal
);

-- クロール先（⓪ 収集）。どこから・いつ・成否
CREATE TABLE IF NOT EXISTS sources (
    id               TEXT PRIMARY KEY,
    url              TEXT NOT NULL,
    kind             TEXT NOT NULL,     -- case | knowhow | option
    label            TEXT,
    last_crawled_at  TEXT,
    status           TEXT               -- success | failed | error
);

-- ナレッジ（行内 internal ＋ 公開 public を 1 テーブルに。W4 の pages に相当）
--   visibility が「全行共有可」の行だけを検索・表示に使う（企画書 v4 §12.3。case_detail は閲覧制限あり）
CREATE TABLE IF NOT EXISTS knowledge (
    id           TEXT PRIMARY KEY,
    kind         TEXT NOT NULL,     -- case | case_detail | knowhow | option
    title        TEXT NOT NULL,
    industry     TEXT,
    size         TEXT,
    branch       TEXT,
    year         INTEGER,
    summary      TEXT,
    signals      TEXT,              -- カンマ区切り（TF-IDF の keywords 相当）
    actions      TEXT,              -- 改行区切り
    outcome      TEXT,
    questions    TEXT,              -- 改行区切り（knowhow）
    handled_by   TEXT,              -- カンマ区切りの staff.id（internal のみ）
    full_text    TEXT,
    source       TEXT,              -- internal | public
    visibility   TEXT,              -- 全行共有可 | 案件関係者・事業承継支援室のみ
    url          TEXT,              -- public の出典 URL
    crawled_at   TEXT,
    license_note TEXT
);

-- 判定結果の履歴（④）
CREATE TABLE IF NOT EXISTS signals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id  TEXT NOT NULL,
    post_id     TEXT NOT NULL,
    fired       INTEGER NOT NULL,
    reaction    INTEGER,            -- 1 そっと蓄積 | 2 過去の文脈 | 3 候補タグ | 4 予兆が立つ（v4 §9.3）
    gate_hit    TEXT,
    tag_summary TEXT,               -- JSON
    reason_text TEXT,
    lost_values TEXT,               -- JSON
    model       TEXT,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ワンクリック FB（4 段階：started | hq_consulted | deal | skipped）
CREATE TABLE IF NOT EXISTS feedback (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id  TEXT NOT NULL,
    staff_id    TEXT,
    kind        TEXT NOT NULL,
    at          DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 本部・他支店への相談履歴（相談先を「関係の情報」で選ぶ材料。企画書 v4 §12.3）
CREATE TABLE IF NOT EXISTS consultations (
    id          TEXT PRIMARY KEY,
    at          TEXT,
    from_staff  TEXT,
    to_staff    TEXT,
    to_dept     TEXT,
    company_id  TEXT,
    case_id     TEXT,
    theme       TEXT
);

-- 監査ログ（閲覧・検索・出力。detail に処理秒数・件数）
CREATE TABLE IF NOT EXISTS audit_logs (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    user    TEXT,
    action  TEXT,
    target  TEXT,
    detail  TEXT
);

CREATE INDEX IF NOT EXISTS idx_posts_company ON posts(company_id, posted_at);
CREATE INDEX IF NOT EXISTS idx_post_tags_post ON post_tags(post_id);
CREATE INDEX IF NOT EXISTS idx_assign_company ON assignments(company_id);

-- 日報の下書き（取引先 × 担当者ごとに 1 件。SFA に登録すると消える）
CREATE TABLE IF NOT EXISTS post_drafts (
    company_id  TEXT NOT NULL,
    author_id   TEXT NOT NULL,
    text        TEXT,
    activity    TEXT,
    contact_id  TEXT,
    saved_at    TEXT,
    PRIMARY KEY (company_id, author_id)
);
