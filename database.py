# =============================================================
# database.py — データ（W3 の database.py と同じ作り ＋ テーブル追加 ＋ data.json の取り込み）
#   役割は「貯める・読む」だけ。判定や検索の処理は tsumugu.py に、収集は crawler.py に、画面は app.py に置く。
#   SQL はこのファイルにだけ書く（W3 と同じ約束）。
# =============================================================
import json
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "tsumugu.db"       # W3 と同じく data/ サブフォルダに置く
SCHEMA_PATH = BASE_DIR / "schema.sql"
DATA_PATH = BASE_DIR / "data.json"


# ── 接続・初期化（W3 そのまま） ─────────────────────────────
def get_connection():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    # 古い形の DB（activity 列が無い）なら作り直す。data/tsumugu.db は data.json と data/raw/ から毎回作れるので消して安全
    if DB_PATH.exists():
        conn = sqlite3.connect(str(DB_PATH))
        cols = [r[1] for r in conn.execute("PRAGMA table_info(posts)").fetchall()]
        conn.close()
        if cols and "activity" not in cols:
            DB_PATH.unlink()
    conn = get_connection()
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()
    conn.close()


def _rows(sql, params=()):
    """SELECT の結果を dict のリストで返す"""
    conn = get_connection()
    rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    conn.close()
    return rows


def _exec(sql, params=()):
    conn = get_connection()
    conn.execute(sql, params)
    conn.commit()
    conn.close()


def _join(xs):
    """リスト → "A,B,C"（W3 の keywords と同じ保存の仕方）"""
    return ",".join(str(x) for x in xs) if isinstance(xs, list) else (xs or "")


def _split(s):
    return [x.strip() for x in (s or "").split(",") if x.strip()]


# ── 取り込み（data.json → DB）。W1 の pages_w1.json を読む動きと同じ ──
def ingest(reset=False):
    """data.json の中身（合成の行内データ）を全部テーブルに入れる。戻り値は件数の dict。
    reset=True でも knowledge の public 行と sources は消さない（クロール結果は別管理）"""
    init_db()
    if reset:
        conn = get_connection()
        for t in ["post_tags", "posts", "signals", "feedback", "audit_logs", "candidate_tags",
                  "assignments", "consultations", "staff", "contacts", "companies"]:
            conn.execute(f"DELETE FROM {t}")
        conn.execute("DELETE FROM knowledge WHERE source = 'internal'")
        conn.commit()
        conn.close()

    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    conn = get_connection()
    for c in data["companies"]:
        conn.execute("""INSERT OR REPLACE INTO companies
            (id, name, industry, founded_year, employees, owner_name, owner_age, key_customers, dependency, region,
             branch, tech_note, successor_status, support_status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (c["id"], c["name"], c.get("industry"), c.get("founded_year"), c.get("employees"), c.get("owner_name"),
             c.get("owner_age"), c.get("key_customers"), c.get("dependency"), c.get("region"), c.get("branch"),
             c.get("tech_note"), c.get("successor_status"), c.get("support_status")))
    for k in data["contacts"]:
        conn.execute("INSERT OR REPLACE INTO contacts (id, company_id, name, role) VALUES (?,?,?,?)",
                     (k["id"], k["company_id"], k["name"], k.get("role")))
    for s in data["staff"]:
        conn.execute("""INSERT OR REPLACE INTO staff (id, name, dept, branch, role, expertise_tags, reports_to, access_scope)
                        VALUES (?,?,?,?,?,?,?,?)""",
                     (s["id"], s["name"], s.get("dept"), s.get("branch"), s.get("role"), _join(s.get("expertise_tags", [])),
                      s.get("reports_to"), s.get("access_scope")))
    for a in data["assignments"]:
        conn.execute("INSERT INTO assignments (company_id, staff_id, from_date, to_date) VALUES (?,?,?,?)",
                     (a["company_id"], a["staff_id"], a["from_date"], a.get("to_date")))
    for k in data["knowledge"]:
        _insert_knowledge(conn, {**k, "source": "internal"})
    for c in data.get("consultations", []):
        conn.execute("INSERT OR REPLACE INTO consultations (id, at, from_staff, to_staff, to_dept, company_id, case_id, theme) VALUES (?,?,?,?,?,?,?,?)",
                     (c["id"], c["at"], c["from_staff"], c["to_staff"], c.get("to_dept"), c.get("company_id"), c.get("case_id"), c.get("theme")))
    for p in data["posts"]:
        conn.execute("""INSERT OR REPLACE INTO posts (id, company_id, contact_id, author_id, posted_at, text, activity, source_label)
                        VALUES (?,?,?,?,?,?,?,?)""",
                     (p["id"], p["company_id"], p.get("contact_id"), p["author_id"], p["posted_at"], p["text"],
                      p.get("activity"), p.get("source_label")))
    conn.commit()
    conn.close()
    # 導入時点の対話状況（companies.support_status）を feedback の初期値として入れる
    for c in data["companies"]:
        if c.get("support_status") == "対話中":
            who = next((a["staff_id"] for a in data["assignments"] if a["company_id"] == c["id"] and not a.get("to_date")), None)
            insert_feedback(c["id"], who, "started")
    return {k: len(v) for k, v in data.items() if isinstance(v, list)}


def _insert_knowledge(conn, k):
    full_text = k.get("full_text") or " ".join([k["title"], k.get("summary", ""), k.get("outcome", "") or "", " ".join(k.get("actions", []))])
    conn.execute("""INSERT OR REPLACE INTO knowledge
        (id, kind, title, industry, size, branch, year, summary, signals, actions, outcome, questions, handled_by,
         full_text, source, visibility, url, crawled_at, license_note) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (k["id"], k["kind"], k["title"], k.get("industry"), k.get("size"), k.get("branch"), k.get("year"),
         k.get("summary"), _join(k.get("signals", [])), "\n".join(k.get("actions", [])), k.get("outcome"),
         "\n".join(k.get("questions", [])), _join(k.get("handled_by", [])), full_text,
         k.get("source", "internal"), k.get("visibility", "全行共有可"), k.get("url", ""), k.get("crawled_at"), k.get("license_note")))


def insert_knowledge(k):
    """⓪ 収集の結果（public）を 1 件入れる。キーは data.json の knowledge と同じ"""
    conn = get_connection()
    _insert_knowledge(conn, k)
    conn.commit()
    conn.close()


def upsert_source(src, status, crawled_at):
    _exec("INSERT OR REPLACE INTO sources (id, url, kind, label, last_crawled_at, status) VALUES (?,?,?,?,?,?)",
          (src["id"], src["url"], src["kind"], src.get("label"), crawled_at, status))


def prune_public_sources(keep_ids):
    """クロール先（rules.json の sources）から外した公開ページを knowledge と sources から消す"""
    keep = set(keep_ids)
    conn = get_connection()
    for r in conn.execute("SELECT id FROM sources").fetchall():
        if r["id"] not in keep:
            conn.execute("DELETE FROM sources WHERE id = ?", (r["id"],))
            conn.execute("DELETE FROM knowledge WHERE id = ?", ("PUB-" + r["id"],))
    conn.commit()
    conn.close()


# ── 読む ─────────────────────────────────────────────────────
def get_companies():
    return _rows("SELECT * FROM companies ORDER BY name")


def get_company(company_id):
    rows = _rows("SELECT * FROM companies WHERE id = ?", (company_id,))
    return rows[0] if rows else None


def get_contacts(company_id):
    return _rows("SELECT * FROM contacts WHERE company_id = ? ORDER BY id", (company_id,))


def get_staff_all():
    return _rows("SELECT * FROM staff ORDER BY dept, name")


def get_staff(staff_id):
    rows = _rows("SELECT * FROM staff WHERE id = ?", (staff_id,))
    return rows[0] if rows else None


def get_assignments(company_id):
    return _rows("""SELECT a.*, s.name AS staff_name, s.dept FROM assignments a JOIN staff s ON s.id = a.staff_id
                    WHERE a.company_id = ? ORDER BY a.from_date""", (company_id,))


def get_posts(company_id, since=None, until=None):
    """同一企業の記録を古い順に。各記録に tags（post_tags の行のリスト）を付けて返す"""
    sql = "SELECT p.*, s.name AS author_name FROM posts p LEFT JOIN staff s ON s.id = p.author_id WHERE p.company_id = ?"
    params = [company_id]
    if since:
        sql += " AND p.posted_at >= ?"
        params.append(since)
    if until:
        sql += " AND p.posted_at <= ?"
        params.append(until)
    posts = _rows(sql + " ORDER BY p.posted_at", tuple(params))
    for p in posts:
        p["tags"] = _rows("SELECT * FROM post_tags WHERE post_id = ? ORDER BY tier, tag_id", (p["id"],))
    return posts


def get_posts_without_tags():
    """タグがまだ付いていない記録（Day 3 の「意味をつける」で使う）"""
    return _rows("SELECT * FROM posts WHERE id NOT IN (SELECT DISTINCT post_id FROM post_tags) ORDER BY posted_at")


def get_all_knowledge(shareable_only=False):
    """shareable_only=True なら「全行共有可」と公開ナレッジだけ（＝検索・表示に使ってよい行。企画書 v4 §12.3）"""
    sql = "SELECT * FROM knowledge"
    if shareable_only:
        sql += " WHERE source = 'public' OR visibility = '全行共有可'"
    rows = _rows(sql)
    for r in rows:
        r["signals"] = _split(r["signals"])
        r["handled_by"] = _split(r["handled_by"])
        r["actions"] = [x for x in (r["actions"] or "").split("\n") if x]
        r["questions"] = [x for x in (r["questions"] or "").split("\n") if x]
    return rows


def count_knowledge(source=None):
    sql = "SELECT COUNT(*) AS n FROM knowledge" + (" WHERE source = ?" if source else "")
    return _rows(sql, (source,) if source else ())[0]["n"]


def get_sources():
    return _rows("SELECT * FROM sources ORDER BY id")


def get_consultations(company_id=None, case_ids=None):
    """相談履歴。company_id か case_id（事例カードの ID）で引く"""
    rows = []
    if company_id:
        rows += _rows("SELECT * FROM consultations WHERE company_id = ?", (company_id,))
    for cid in (case_ids or []):
        rows += _rows("SELECT * FROM consultations WHERE case_id = ?", (cid,))
    seen, out = set(), []
    for r in rows:
        if r["id"] not in seen:
            seen.add(r["id"])
            out.append(r)
    return out


# ── 書く ─────────────────────────────────────────────────────
def insert_post(p):
    _exec("""INSERT OR REPLACE INTO posts (id, company_id, contact_id, author_id, posted_at, text, activity, source_label)
             VALUES (?,?,?,?,?,?,?,?)""",
          (p["id"], p["company_id"], p.get("contact_id"), p["author_id"], p["posted_at"], p["text"],
           p.get("activity"), "SFA日報（パイロット期間）"))


def find_same_post(company_id, author_id, posted_at, text):
    """同じ企業・同じ担当者・同じ訪問日・同じ本文の日報があればその ID（二重登録を防ぐ）"""
    rows = _rows("SELECT id, text FROM posts WHERE company_id = ? AND author_id = ? AND posted_at = ?", (company_id, author_id, posted_at))
    return next((r["id"] for r in rows if (r["text"] or "").strip() == (text or "").strip()), None)   # 全角の空白も揃える


def next_post_id():
    """パイロット期間に登録する日報の ID（P-9001 から連番）。数値で最大を取る（文字列順だと P-9999 の次で止まるため）"""
    n = _rows("SELECT MAX(CAST(SUBSTR(id, 3) AS INTEGER)) AS n FROM posts WHERE id GLOB 'P-[0-9]*'")[0]["n"]
    return f"P-{max((n or 0) + 1, 9001)}"


def replace_post_tags(post_id, tags):
    """tags = [{"tag","tier","evidence","confidence","method","origin"}, ...]。その記録のタグを入れ替える"""
    conn = get_connection()
    conn.execute("DELETE FROM post_tags WHERE post_id = ?", (post_id,))
    for t in tags:
        conn.execute("INSERT INTO post_tags (post_id, tag_id, tier, evidence, confidence, method, origin) VALUES (?,?,?,?,?,?,?)",
                     (post_id, t["tag"], t["tier"], t.get("evidence"), t.get("confidence", 0), t.get("method"), t.get("origin", "report")))
    conn.commit()
    conn.close()


def set_tag_confirmed(post_id, tag_id, confirmed):
    """担当者がタグをチェックで確定／却下（AI の提案と事実の区別）"""
    _exec("UPDATE post_tags SET confirmed_by_user = ? WHERE post_id = ? AND tag_id = ?", (1 if confirmed else 0, post_id, tag_id))


def bump_candidate_tag(name, date):
    conn = get_connection()
    row = conn.execute("SELECT id FROM candidate_tags WHERE name = ?", (name,)).fetchone()
    if row:
        conn.execute("UPDATE candidate_tags SET count = count + 1, last_seen = ? WHERE id = ?", (date, row["id"]))
    else:
        conn.execute("INSERT INTO candidate_tags (name, count, first_seen, last_seen) VALUES (?,1,?,?)", (name, date, date))
    conn.commit()
    conn.close()


def count_candidate_records(name, exclude_post_id=None):
    """その候補タグが付いた記録の件数（今回の記録は除く。反応③の「N 回目」に使う）"""
    sql = "SELECT COUNT(DISTINCT post_id) AS n FROM post_tags WHERE tier = 'candidate' AND tag_id = ?"
    params = [name]
    if exclude_post_id:
        sql += " AND post_id != ?"
        params.append(exclude_post_id)
    return _rows(sql, tuple(params))[0]["n"]


def get_candidate_tags():
    return _rows("SELECT * FROM candidate_tags ORDER BY count DESC, name")


def insert_signal(s):
    _exec("INSERT INTO signals (company_id, post_id, fired, reaction, gate_hit, tag_summary, reason_text, lost_values, model) VALUES (?,?,?,?,?,?,?,?,?)",
          (s["company_id"], s["post_id"], 1 if s["fired"] else 0, s.get("reaction"), _join(s["gate"]),
           json.dumps(s["tags"], ensure_ascii=False), s["reason"], json.dumps(s["lost_values"], ensure_ascii=False), s["generated_by"]))


def get_last_signal(company_id):
    """その企業に実際に出た最新の判定（記録をきっかけに出たもの）。まだ無ければ None"""
    rows = _rows("SELECT * FROM signals WHERE company_id = ? ORDER BY id DESC LIMIT 1", (company_id,))
    return rows[0] if rows else None


def get_latest_signals():
    """企業ごとの最新の判定（支店長の「対話の状況」で使う）"""
    return _rows("""SELECT s.*, c.name AS company_name FROM signals s JOIN companies c ON c.id = s.company_id
                    WHERE s.id IN (SELECT MAX(id) FROM signals GROUP BY company_id) ORDER BY c.name""")


def insert_feedback(company_id, staff_id, kind):
    _exec("INSERT INTO feedback (company_id, staff_id, kind) VALUES (?,?,?)", (company_id, staff_id, kind))


def get_latest_feedback():
    rows = _rows("SELECT * FROM feedback WHERE id IN (SELECT MAX(id) FROM feedback GROUP BY company_id)")
    return {r["company_id"]: r for r in rows}


# ── 閲覧範囲（認可。企画書 v4 §12.3「認証は SFA に任せ、認可はツムグが守る」） ──
def visible_company_ids(staff_id):
    """その行員が見てよい企業 ID の集合。staff.access_scope で決める
      assigned_companies＝現在の担当先（前任者の記録を含む）／branch＝自支店の全担当先／
      consulted＝相談を受けた企業／all＝すべて"""
    s = get_staff(staff_id)
    if not s:
        return set()
    scope = s["access_scope"]
    if scope == "all":
        return {c["id"] for c in get_companies()}
    if scope == "branch":
        return {c["id"] for c in _rows("SELECT id FROM companies WHERE branch = ?", (s["branch"],))}
    if scope == "consulted":
        return {r["company_id"] for r in _rows("SELECT DISTINCT company_id FROM consultations WHERE to_staff = ? AND company_id IS NOT NULL", (staff_id,))}
    return {r["company_id"] for r in _rows("SELECT DISTINCT company_id FROM assignments WHERE staff_id = ? AND to_date IS NULL", (staff_id,))}


def current_assignee(company_id):
    rows = _rows("""SELECT a.staff_id, s.name FROM assignments a JOIN staff s ON s.id = a.staff_id
                    WHERE a.company_id = ? AND a.to_date IS NULL ORDER BY a.from_date DESC LIMIT 1""", (company_id,))
    return rows[0] if rows else None


# ── 相談の申し出（「直接相談する／上司に相談する」のワンクリック。v4 §12.3） ──
def insert_consultation(from_staff, to_staff, company_id, theme, via_staff=None, at=None):
    """相談履歴に 1 行足す。via_staff があれば「上司経由の顔つなぎ」。戻り値は新しい ID
    相談を受けた人（consulted スコープ）は、以後この企業の記録を見られるようになる"""
    rows = _rows("SELECT id FROM consultations WHERE id LIKE 'CS-9%' ORDER BY id DESC LIMIT 1")
    new_id = f"CS-{int(rows[0]['id'][3:]) + 1}" if rows else "CS-9001"
    to = get_staff(to_staff) or {}
    theme = theme + (f"（{(get_staff(via_staff) or {}).get('name', via_staff)}さん経由）" if via_staff else "")
    _exec("INSERT INTO consultations (id, at, from_staff, to_staff, to_dept, company_id, case_id, theme) VALUES (?,?,?,?,?,?,?,?)",
          (new_id, at, from_staff, to_staff, to.get("dept"), company_id, None, theme))
    return new_id


def get_consultations_by(from_staff=None, to_staff=None):
    sql = """SELECT c.*, f.name AS from_name, t.name AS to_name, co.name AS company_name FROM consultations c
             LEFT JOIN staff f ON f.id = c.from_staff LEFT JOIN staff t ON t.id = c.to_staff
             LEFT JOIN companies co ON co.id = c.company_id WHERE 1=1"""
    params = []
    if from_staff:
        sql += " AND c.from_staff = ?"
        params.append(from_staff)
    if to_staff:
        sql += " AND c.to_staff = ?"
        params.append(to_staff)
    return _rows(sql + " ORDER BY c.at DESC, c.id DESC", tuple(params))


# ── 候補タグの昇格（AI は提案だけ。承認は人。v4 §9.1） ──────────
def set_candidate_status(name, status):
    """status: candidate | proposed（本部が昇格を承認し、判定基準の改定待ち） | rejected（今回は見送り）"""
    _exec("UPDATE candidate_tags SET status = ? WHERE name = ?", (status, name))


# ── パイロットの効果測定（企業の点数ではなく、仕組みの効果を測る。企画書 v4 §13.4） ──
def get_all_signals():
    return _rows("SELECT * FROM signals ORDER BY id")


def get_all_feedback():
    return _rows("SELECT * FROM feedback ORDER BY id")


def pilot_post_stats(since):
    """パイロット期間（since 以降）の日報の数・正式タグが 1 つ以上付いた数・伝聞（未確認）から拾ったタグを含む数"""
    r = _rows("""SELECT COUNT(*) AS n,
                        SUM(CASE WHEN id IN (SELECT post_id FROM post_tags WHERE tier = 'formal' AND origin = 'hearsay') THEN 1 ELSE 0 END) AS hearsay,
                        SUM(CASE WHEN id IN (SELECT post_id FROM post_tags WHERE tier = 'formal') THEN 1 ELSE 0 END) AS tagged
                 FROM posts WHERE posted_at >= ?""", (since,))[0]
    return {k: r[k] or 0 for k in ("n", "hearsay", "tagged")}


def count_audit(action):
    return _rows("SELECT COUNT(*) AS n FROM audit_logs WHERE action = ?", (action,))[0]["n"]


def get_audit_details(action):
    return [r["detail"] for r in _rows("SELECT detail FROM audit_logs WHERE action = ?", (action,))]


def log_audit(user, action, target, detail=""):
    _exec("INSERT INTO audit_logs (user, action, target, detail) VALUES (?,?,?,?)", (user, action, target, detail))


def get_audit_logs(limit=200):
    return _rows("SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?", (limit,))


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")      # Windows のコンソール対策
    print("取り込み:", ingest(reset="--reset" in sys.argv))
    print("DB:", DB_PATH, "| knowledge public:", count_knowledge("public"))
