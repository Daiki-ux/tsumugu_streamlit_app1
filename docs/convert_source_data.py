# docs/convert_source_data.py — もっちゃんの合成データ（企画書v4準拠）→ data.json / rules.json
#   使い方: python docs/convert_source_data.py
#   入力: ツムグ合成データ（企画書v4準拠）/ の companies / reports / employees / assignments /
#         consultations / case_cards / cases / tags / judgment_criteria.md / demo_inputs
#   出力: data.json（DB に入れる行内データ）と rules.json（判定の設定）を上書き
#
#   ・ID はもっちゃんのデータのまま（C001 / E001 / R0001 / K001）
#   ・reference_tags / reference_candidate は答え合わせ用なので data.json には入れない（tests だけが使う）
#   ・patterns（言い回し辞書）はこのスクリプトの初期値。変換後は rules.json を直接編集してよい（再変換で初期値に戻る）
#   ・sources（クロール先）・forbidden_words・crawl は既存の rules.json をそのまま引き継ぐ
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def find_src():
    """もっちゃんの合成データのフォルダを探す（Mac 由来のフォルダ名は濁点の持ち方が違うので、正規化して比べる）"""
    want = unicodedata.normalize("NFC", "ツムグ合成データ")
    for p in ROOT.iterdir():
        if p.is_dir() and want in unicodedata.normalize("NFC", p.name):
            return p
    raise SystemExit("合成データのフォルダ（ツムグ合成データ…）が見つかりません")


SRC = find_src()

# 正式タグ（tags.json の 予兆タグ）の言い回し辞書。答え合わせ（reference_tags）に合わせてある
PATTERNS = {
    "T01": {  # 後継者未定
        "patterns": [
            "継ぐ気は(ない|ありません)", "継ぐ意思は(不明|ない)", "後継者(が|は)?(いない|未定|決まって|不在)",
            "若い者に任せ", "誰に任せ", "息子.{0,12}(県外|継が|継ぐ)",
            "(承継|後継).{0,20}(本人次第|決まっていな|未定|これから|しづらい|踏み込)",
            "承継の話.{0,12}(後退|止ま|進んで)", "(経営|後)は外から人を招く", "継ぐ人がいな",
        ],
        "counter_examples": ["後継者は専務で決まっている", "子息が入社", "役員承継予定"],
        "questions": ["息子さん（後継者候補）の意向を、直接確認されたことはありますか",
                      "社長ご自身は、いつ頃までを考えていらっしゃいますか"],
    },
    "T02": {  # 技術継承の属人化
        "patterns": [
            "(工場長|職人|熟練|ベテラン|キーパーソン|番頭).{0,25}(退職|引退|辞め|やれるか|続けられる|休んで|痛めて)",
            "手作業の勘", "勘に頼", "(知って|できて?)いるのは.{0,8}(一人|1人|二人|2人)だけ", "属人",
            "(一人|1人|ひとり)で(回して|こなして|やって)", "(職人|工場長|熟練).{0,30}(2人|二人|1人|一人)(で|の)",
            "若手.{0,20}(続かな|定着しな|育たな|来ない)", "技術の継承先(が)?(ない|いない)",
        ],
        "counter_examples": ["定年後も再雇用で継続", "技術は文書化済み", "職人1名を新規採用"],
        "questions": ["その方の技術は、他の方に引き継がれていますか",
                      "退職までに技術継承の時間を確保できそうですか"],
    },
    "T03": {  # 設備投資の停滞
        "patterns": [
            "設備更新.{0,20}(進展|見送|先送|止ま|ありません)", "機械を入れてもな",
            "(投資|更新|導入).{0,12}(見送|先送|止まって|止めて|踏み切れ)", "設備は古いまま",
        ],
        "counter_examples": ["設備更新が完了", "重機導入完了", "新工場の用地取得を検討"],
        "questions": ["設備更新を見送っている理由は、資金・需要・将来の見通しのどれですか"],
    },
    "T04": {  # 品質不具合による社内疲弊
        "patterns": [
            "(不具合|リコール|回収|品質|クレーム).{0,30}(疲弊|手が回ら|苦し|余裕がな|追われ)",
            "(不具合|リコール|回収)(対応|の件).{0,12}(中|継続)", "回収対応",
            "(対応|事故|問題|クレーム).{0,12}(疲弊|手が回ら|参って)",
        ],
        "counter_examples": ["不具合対応は収束した"],
        "questions": ["不具合対応の負担は、今どの程度残っていますか"],
    },
}
# 候補タグ（正式タグではない。判定には使わない。名前は reports.json の reference_candidate に合わせる）
CANDIDATES = {
    "海外展開への関心": {"patterns": ["(海外|東南アジア|アジア|タイ|ベトナム|現地).{0,25}(展示会|拠点|進出|展開|商社|出展|通訳)",
                                      "(展示会|出展).{0,15}(海外|タイ|ベトナム)"], "polarity": "positive"},
    "事業拡大の意欲": {"patterns": ["(新工場|用地取得|事業拡大|県外).{0,25}(検討|構想|引き合い|問い合わせ|話)",
                                    "事業拡大の構想"], "polarity": "positive"},
}
# 失われる地域価値（静的要因と記録の両方から拾う）
VALUES = {
    "V_TECHNOLOGY": {"name": "特殊技術・ノウハウ", "patterns": ["薄板", "社寺", "(特殊|独自|精密)な?(加工|技術|成形)", "代替(先|が)"]},
    "V_CUSTOMERS": {"name": "長年の顧客・取引関係", "patterns": ["(取引|付き合い).{0,8}(\\d+年|長年|長い)"]},
    "V_EMPLOYMENT": {"name": "地域の雇用", "patterns": ["地元採用"]},
    "V_CULTURE_BRAND": {"name": "地域の文化・ブランド", "patterns": ["老舗", "地元では有名", "伝統"]},
}


def load(name):
    return json.loads((SRC / name).read_text(encoding="utf-8"))


def criteria_from_md():
    """judgment_criteria.md の「予兆の考え方」「提示するかどうか」「書き方」を rules.json の criteria にする"""
    md = (SRC / "judgment_criteria.md").read_text(encoding="utf-8")

    def bullets(heading):
        m = re.search(rf"## {heading}\n(.*?)(?=\n##|\Z)", md, re.S)
        return [re.sub(r"^- ", "", x).strip() for x in m.group(1).strip().splitlines() if x.startswith("- ")] if m else []
    think, show, style = bullets("予兆の考え方"), bullets("提示するかどうか"), bullets("書き方")
    return {"sentences": think, "closing": " ".join(show), "style": style,
            "_source": "ツムグ合成データ（企画書v4準拠）/judgment_criteria.md（事業承継支援室が書いた前提）"}


def main():
    companies, reports = load("companies.json"), load("reports.json")
    employees, assignments = load("employees.json"), load("assignments.json")
    consultations, case_cards, cases = load("consultations.json"), load("case_cards.json"), load("cases.json")
    tags = load("tags.json")

    # ── companies / contacts
    out_companies, out_contacts = [], []
    for c in companies:
        out_companies.append({
            "id": c["company_id"], "name": c["name"], "industry": c["industry"], "founded_year": c["established"],
            "employees": c["employees"], "owner_name": c["ceo_name"], "owner_age": c["ceo_age"],
            "key_customers": "、".join(c.get("main_clients") or []), "dependency": c.get("category", ""),
            "region": c.get("location", ""), "branch": c.get("branch", ""),
            # 「技術名／メモ」。技術名が無い企業は空（メモだけを技術として扱わない。変更記録 CH-23）
            "tech_note": ("／".join(x for x in [c.get("key_tech"), c.get("note")] if x) if c.get("key_tech") else ""),
            "successor_status": c.get("successor_status", ""), "support_status": c.get("support_status", ""),
        })
        for i, k in enumerate(c.get("contacts") or [], 1):
            out_contacts.append({"id": f"{c['company_id']}-P{i}", "company_id": c["company_id"],
                                 "name": k["name"], "role": k["title"]})

    # ── staff
    out_staff = [{"id": e["employee_id"], "name": e["name"], "dept": e["branch"], "branch": e["branch"],
                  "role": e["role"], "expertise_tags": e.get("knowledge_areas") or [],
                  "reports_to": e.get("reports_to"), "access_scope": e.get("access_scope", "")}
                 for e in employees]

    # ── assignments（"2025-03" → 月末日）
    def to_day(ym, last=False):
        if not ym:
            return None
        y, m = (int(x) for x in ym.split("-"))
        if not last:
            return f"{y:04d}-{m:02d}-01"
        d = [31, 29 if y % 4 == 0 and (y % 100 or y % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]
        return f"{y:04d}-{m:02d}-{d:02d}"

    out_assign = [{"company_id": a["company_id"], "staff_id": a["employee_id"], "from_date": to_day(a["from"]),
                   "to_date": to_day(a.get("to"), last=True), "role": a.get("role", "")} for a in assignments]

    # ── posts（過去日報は body、パイロット期間は business_report＋insight を 1 つの業務報告にまとめる）
    #    ツムグは新しい入力欄を持たない（変更記録 CH-05）ので、insight も業務報告の一部として扱う
    contact_id_of = {}
    for k in out_contacts:
        contact_id_of.setdefault(k["company_id"], {})[k["name"]] = k["id"]
    out_posts = []
    for r in reports:
        if (r.get("body") or "").strip():
            text = r["body"].strip()
        else:
            text = "".join(x.strip() for x in (r.get("business_report"), r.get("insight")) if x and x.strip())
        cname = re.sub(r"（.*", "", r.get("contact") or "").strip()
        out_posts.append({"id": r["report_id"], "company_id": r["company_id"], "author_id": r["employee_id"],
                          "contact_id": contact_id_of.get(r["company_id"], {}).get(cname),
                          "posted_at": r["date"], "text": text,
                          "source_label": r.get("source", "")})

    # ── knowledge（case_cards＝全行共有可・表示する／cases＝閲覧制限・索引にも表示にも使わない／knowhow＝勘所）
    out_knowledge = []
    # 事例カードには、案件記録（cases.json）の経緯も載せる。事例の中身が行内で共有されている前提（変更記録 CH-15）。
    # 共有するのは経緯・結果・当時の予兆・支援した行員まで。企業名は元データにも無い
    story = {c["case_id"]: c for c in cases}
    for k in case_cards:
        c = story.get(k["case_id"], {})
        out_knowledge.append({
            "id": k["case_id"], "kind": "case", "title": k["title"],
            "industry": k["industry"], "size": f"{k['employee_band']}・{k['succession_type']}", "branch": k["branch"], "year": k["year"],
            "summary": c.get("summary") or k["title"], "signals": k["tags"], "actions": [], "outcome": c.get("outcome") or k["outcome"],
            "questions": [], "handled_by": k["staff"], "source": "internal", "visibility": k["visibility"], "url": "",
            "full_text": " ".join([k["title"], c.get("summary", ""), c.get("outcome") or k["outcome"], k["industry"], k["succession_type"],
                                   " ".join(k["tags"])]),
        })
    for k in cases:
        out_knowledge.append({
            "id": k["case_id"] + "-D", "kind": "case_detail", "title": k["title"], "industry": k["industry"],
            "size": f"従業員{k['employees']}名", "branch": k["branch"], "year": k["year"], "summary": k["summary"],
            "signals": k["tags"], "actions": [], "outcome": k["outcome"], "questions": [], "handled_by": k["staff"],
            "source": "internal", "visibility": k["visibility"], "url": "", "full_text": k["summary"] + " " + k["outcome"],
        })
    out_knowledge += json.loads((ROOT / "docs" / "knowhow.json").read_text(encoding="utf-8"))

    data = {
        "_comment": ("もっちゃんの『ツムグ合成データ（企画書v4準拠）』から docs/convert_source_data.py で生成。すべて架空。"
                     "ID は元データのまま（C001 / E001 / R0001 / K001）。reference_tags は答え合わせ用なのでここには入れない。"
                     "kind=case_detail（cases.json）は閲覧制限ありのため検索索引にも画面にも出さない（企画書 v4 §12.3）。"
                     "kind=knowhow（H-xxx）は ⑦ の確認事項に使う補助データで、もっちゃんのセットには無い（ゆき作成）。"),
        "companies": out_companies, "contacts": out_contacts, "staff": out_staff, "assignments": out_assign,
        "consultations": [{"id": c["consultation_id"], "at": c["date"], "from_staff": c["from_employee"],
                           "to_staff": c["to_employee"], "to_dept": c["to_department"],
                           "company_id": c.get("company_id"), "case_id": c.get("case_id"), "theme": c["theme"]}
                          for c in consultations],
        "posts": out_posts, "knowledge": out_knowledge,
    }
    (ROOT / "data.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── rules.json（patterns はここの初期値、sources などは既存を引き継ぐ）
    rules = json.loads((ROOT / "rules.json").read_text(encoding="utf-8"))
    cat = {"T01": "successor", "T02": "people", "T03": "business", "T04": "business"}
    rules["formal"] = {t["tag_id"]: {"name": t["name"], "category": cat[t["tag_id"]], "definition": t["description"],
                                     "guidance": t["guidance"], **PATTERNS[t["tag_id"]]}
                       for t in tags if t["type"] == "予兆タグ"}
    rules["static"] = {
        "owner_age": {"tag_id": "S01", "name": "経営者の高齢化", "rule": "70歳以上のとき、予兆の重なりに 1 種として数える", "threshold": 70,
                      "guidance": next(t["guidance"] for t in tags if t["tag_id"] == "S01")},
        "years_in_business": {"tag_id": "S02", "name": "長い業歴", "rule": "業歴50年以上のとき、失われる価値の大きさとして理由文に添える（重なりには数えない）",
                              "threshold": 50, "guidance": next(t["guidance"] for t in tags if t["tag_id"] == "S02")},
    }
    rules["candidate"] = {name: {"name": name, **spec} for name, spec in CANDIDATES.items()}
    rules["value"] = VALUES
    rules["criteria"] = criteria_from_md()
    rules["gate"] = {"window_months": 36, "recent_months": 12, "min_distinct": 3, "min_recent_categories": 2,
                     "count_static_owner_age": True,
                     "_note": "種類の異なる予兆が 3 つ以上重なり（静的要因の『経営者の高齢化』も 1 種と数える）、"
                              "うち 2 つ以上の系統が直近 12 ヶ月に観測されたときだけ提示する（judgment_criteria.md「提示するかどうか」）"}
    rules["reaction_labels"] = {"1": "予兆は出ていません（記録は蓄積しています）", "2": "過去に関連する記録があります",
                                "3": "これまでにない変化が続いています", "4": "支援の検討が必要かもしれません"}
    rules["candidate_promote_threshold"] = 3
    # FB 取り込みシート②で挙がった 8 語のうち、もっちゃんの tags.json に入っていない 4 語。
    # 判定には使わない（正式タグは tags.json の 4 語だけ）。候補タグの昇格運用でここから正式タグに上げる候補。
    rules["watchlist"] = ["経営者の高齢化（S01 の静的要因として実装済み）", "経営者の体調変化への言及",
                          "主力取引先からの受注減少", "若手社員の定着不良"]
    rules["_comment"] = ("判定の設定。業務側が書き換える前提。formal / static / candidate / criteria は "
                         "docs/convert_source_data.py がもっちゃんの tags.json・judgment_criteria.md から生成する。"
                         "patterns（言い回し辞書）は変換時の初期値なので、ここを直接直してよい（再変換すると戻る）。"
                         "sources は ⓪ 収集のクロール先（公開ページのみ）。")
    (ROOT / "rules.json").write_text(json.dumps(rules, ensure_ascii=False, indent=2), encoding="utf-8")

    sys.stdout.reconfigure(encoding="utf-8")
    print("data.json :", {k: len(v) for k, v in data.items() if isinstance(v, list)})
    print("rules.json: 正式タグ", list(rules["formal"]), "／候補", list(rules["candidate"]))


if __name__ == "__main__":
    main()
