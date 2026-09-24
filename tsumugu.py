# =============================================================
# tsumugu.py — 処理（反応層 ①〜⑦）。W4 の ranking.py / search.py と同じ「画面を知らない処理」のファイル
#
#   ① new_post      SFA の日報 1 件（業務報告）の dict を作る。ツムグの新しい入力欄は無い
#   ①' draft_from_voice_memo  音声メモから日報の下書き（補助。v4 §4.1。テンプレ → 任意で LLM）
#   ② extract       記録 → タグ（正式 8 語 / 候補 / 価値。原文引用付き）  辞書 → （任意）LLM
#   ③ collate       同一企業の過去の記録 + 静的要因 + 担当履歴 → 企業の輪郭     SQL + pandas（担当者をまたぐ集計）
#   ④ assess        発火ゲート（if 文）→ 発火時のみ理由文。反応の層 1〜4 を決める（v4 §9.3）
#   ⑤ retrieve      ナレッジ検索（TF-IDF = ranking.py）。行内 internal と 公開 public を同じ索引で並べる
#   ⑥ who_to_ask    ナレッジを支援した行員 + 前任担当者（関係の情報だけで選ぶ。v4 §12.3）
#   ⑦ recommend     確認事項・選択肢・次の行動（すべて根拠 ID 付き）＋ 公開の支援メニューの出典
#   run             ①〜⑦ を順に呼ぶ（app.py はこれだけ呼ぶ）
#
# 受け渡しはすべて dict / list（W1〜W4 の pages と同じ）。各関数の docstring に「返す dict のキー」を書く。
# LLM は無くても全部動く（キーがあるときだけ ①' ② ④ ⑦ が LLM に置き換わる）。
# ⓪ 収集は crawler.py（ナレッジ層。日報とは独立に回る）。
# =============================================================
import json
import os
import re
import time
from collections import defaultdict
from datetime import date
from pathlib import Path

import pandas as pd

import database as db
from ranking import get_engine, rebuild_index

BASE_DIR = Path(__file__).resolve().parent
RULES = json.loads((BASE_DIR / "rules.json").read_text(encoding="utf-8"))
LLM_MODEL = "gpt-4o-mini"
REACTION = RULES["reaction_labels"]           # {"1": "そっと蓄積する", ...}


# ── 小道具 ──────────────────────────────────────────────────
def tag_name(tag_id):
    """タグ ID → 日本語名（rules.json に無ければ ID のまま）"""
    for tier in ("formal", "candidate", "value"):
        if tag_id in RULES[tier]:
            return RULES[tier][tag_id]["name"]
    return tag_id


def months_before(d, months):
    """'YYYY-MM-DD' の months ヶ月前（日は 01）"""
    y, m, _ = (int(x) for x in d.split("-"))
    total = y * 12 + (m - 1) - months
    return f"{total // 12:04d}-{total % 12 + 1:02d}-01"


def sentence_around(text, match):
    """正規表現が当たった位置を含む 1 文を返す（引用用）"""
    start = 0
    for s in re.split(r"(?<=[。！？!?])", text):
        end = start + len(s)
        if start <= match.start() < end:
            return s.strip()
        start = end
    return match.group(0)


# ── LLM（09.08 の run_gpt と同じ呼び方。キーが無ければ None を返す） ──
def llm_key():
    key = os.environ.get("OPENAI_API_KEY")
    if key:
        return key
    try:
        import streamlit as st
        return st.secrets.get("OPENAI_API_KEY")
    except Exception:
        return None


def llm_available():
    return os.environ.get("TSUMUGU_NO_LLM") != "1" and bool(llm_key())


def llm_chat(system, user, want_json=False):
    """LLM に聞く。失敗したら None（呼び出し側は必ずフォールバックを持つ）"""
    if not llm_available():
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=llm_key())
        kwargs = {"response_format": {"type": "json_object"}} if want_json else {}
        res = client.chat.completions.create(model=LLM_MODEL, temperature=0.2, **kwargs,
                                             messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
        content = (res.choices[0].message.content or "").strip()
        return json.loads(content) if want_json else content
    except Exception:
        return None


# ── ① 日報の気づき欄 ────────────────────────────────────────
def new_post(company_id, contact_id, author_id, posted_at, text, post_id=None, activity=None):
    """日報の dict を作る。キー: id, company_id, contact_id, author_id, posted_at, text（業務報告）, activity（活動区分）
    ツムグは新しい入力欄を持たない。いつもの業務報告をそのまま読む"""
    return {"id": post_id or db.next_post_id(), "company_id": company_id, "contact_id": contact_id,
            "author_id": author_id, "posted_at": posted_at, "text": text.strip(), "activity": activity}


# ── ①' 業務報告の下書き（v4 §4.1：一言から日報の叩き台。本番は SFA の既製機能） ──
def draft_report(post, use_llm=True):
    """一言 + 直近の記録 → 業務報告の下書き（文字列）。担当者が確認してから登録する前提"""
    c = db.get_company(post["company_id"]) or {}
    contact = next((k for k in db.get_contacts(post["company_id"]) if k["id"] == post.get("contact_id")), None)
    who = f"{contact['name']}（{contact['role']}）" if contact else "先方"
    prev = [p for p in db.get_posts(post["company_id"], until=post["posted_at"]) if p["id"] != post["id"]]
    last = prev[-1]["text"][:30] if prev else ""
    if use_llm and llm_available():
        text = llm_chat("地方銀行の法人担当者の日報の「業務報告」欄を、丁寧語の 2〜3 文で書く。一言にない事実は書かない。融資条件や評価は書かない。",
                        f"企業: {c.get('name')}（{c.get('industry')}）\n面談相手: {who}\n前回の記録: {last or 'なし'}\n今日の一言: {post['text']}")
        if text:
            return text
    lines = [f"{post['posted_at']} {c.get('name', '')}を訪問し、{who}と面談。"]
    if last:
        lines.append(f"前回（{prev[-1]['posted_at']}）の「{last}」の件を確認。")
    lines.append("気づき欄のとおり、雑談の中で先方の状況を伺った。次回訪問時に継続して確認する。")
    return "".join(lines)


# 伝聞・未確認の話らしい言い回し。この文から拾った予兆には「未確認」の印を付ける（重なりには数える）
UNCONFIRMED = re.compile(r"(雑談|小耳|らしい|噂|うわさ|と話していた|と言っていた|世間話|立ち話|帰り際|との話も)")


def is_unconfirmed(sentence):
    return bool(UNCONFIRMED.search(sentence or ""))


def draft_from_voice_memo(post, memo, use_llm=True):
    """①' 訪問後の音声メモ（文字起こし）→ 業務報告の叩き台 {"report", "generated_by"}。
    補助機能。担当者が確認・修正してから登録する前提（AI が書いた日報がそのまま SFA に入ることはない。v4 §9.6）"""
    c = db.get_company(post["company_id"]) or {}
    contact = next((k for k in db.get_contacts(post["company_id"]) if k["id"] == post.get("contact_id")), None)
    who = f"{contact['name']}（{contact['role']}）" if contact else "先方"
    if use_llm and llm_available():
        text = llm_chat("地方銀行の法人担当者の音声メモを、日報の「業務報告」欄の文章に整える。丁寧語で簡潔に。"
                        "メモにない事実は書かない。雑談や噂で聞いた話は「雑談の中で〜と伺った」のように伝聞だと分かる形のまま残す。"
                        "融資条件や企業の評価は書かない。",
                        f"企業: {c.get('name')}（{c.get('industry')}）\n面談相手: {who}\n訪問日: {post['posted_at']}\nメモ: {memo}")
        if text:
            return {"report": text, "generated_by": "llm"}
    sents = [x.strip() for x in re.split(r"(?<=[。！？!?])", memo or "") if x.strip()]
    return {"report": "".join(s if s[-1] in "。！？!?" else s + "。" for s in sents), "generated_by": "template"}


# ── ② 抽出 ─────────────────────────────────────────────────
def _rule_hits(text, tier):
    """辞書抽出。rules.json の patterns を総当たり。当たったタグと引用の dict のリスト
    origin＝引用した文が伝聞（雑談で・らしい 等）なら hearsay（未確認）、そうでなければ report"""
    hits = []
    for tag_id, spec in RULES[tier].items():
        for pat in spec.get("patterns", []):
            m = re.search(pat, text)
            if m:
                ev = sentence_around(text, m)
                hits.append({"tag": tag_id, "tier": tier, "evidence": ev, "confidence": 0.9 if tier == "formal" else 0.7,
                             "method": "rule", "origin": "hearsay" if is_unconfirmed(ev) else "report"})
                break
    return hits


def _llm_hits(text, existing_candidates):
    """LLM 抽出（任意）。正式タグは 8 語の ID に限定し、引用が原文に無いものは捨てる"""
    ids = list(RULES["formal"])
    system = ("地方銀行の法人担当者の日報の気づき欄から事業承継の予兆を抽出する。出力は JSON のみ: "
              '{"formal_tags":[{"tag":"<ID>","evidence":"<原文引用>"}],"candidate_tags":[{"tag":"<短い日本語名>","evidence":"<原文引用>"}]}。'
              f"formal_tags の tag は {', '.join(ids)} のみ。記録に無いことは書かない。evidence は必ず記録の一部をそのまま引用。"
              "正式タグに当てはまらないが変化を示す記述は candidate_tags に短い名前を付ける"
              f"（既存の候補名: {', '.join(existing_candidates) or 'なし'} に近ければ同じ名前）。業務報告や中身のない記録なら両方とも空配列。")
    data = llm_chat(system, text, want_json=True)
    if not data:
        return [], []
    formal = [{"tag": t["tag"], "tier": "formal", "evidence": t["evidence"], "confidence": 0.7, "method": "llm"}
              for t in data.get("formal_tags", []) if t.get("tag") in ids and t.get("evidence", "") in text]   # ← if 文で守る
    cand = [{"tag": t["tag"], "tier": "candidate", "evidence": t.get("evidence", ""), "confidence": 0.5, "method": "llm"}
            for t in data.get("candidate_tags", []) if t.get("tag")]
    return formal, cand


def record_text(post):
    """タグを付ける対象の文字列＝業務報告"""
    return post.get("text", "")


def extract(post, use_llm=True):
    """② 記録 → 抽出結果。
    返す dict のキー: post_id, formal[], candidate[], value[], unclassified
      formal/candidate/value の要素: {tag, tier, evidence, confidence, method, origin（report | hearsay＝伝聞・未確認）}"""
    text = record_text(post)
    formal, cand, value = _rule_hits(text, "formal"), _rule_hits(text, "candidate"), _rule_hits(text, "value")
    if use_llm and llm_available():
        lf, lc = _llm_hits(text, [c["name"] for c in db.get_candidate_tags()])
        for h in lf + lc:
            h["origin"] = "hearsay" if is_unconfirmed(h["evidence"]) else "report"
        formal += [h for h in lf if h["tag"] not in {x["tag"] for x in formal}]
        cand += [h for h in lc if h["tag"] not in {x["tag"] for x in cand}]
    return {"post_id": post["id"], "formal": formal, "candidate": cand, "value": value,
            "unclassified": not (formal or cand or value)}


def all_tags(ext):
    return ext["formal"] + ext["candidate"] + ext["value"]


def retag_all(use_llm=False):
    """タグの無い記録に ② を掛ける（Day 3「意味をつける」。data.json を入れ直した後にも使う）"""
    n = 0
    for p in db.get_posts_without_tags():
        ext = extract(p, use_llm=use_llm)
        db.replace_post_tags(p["id"], all_tags(ext))
        for c in ext["candidate"]:
            db.bump_candidate_tag(c["tag"], p["posted_at"])
        n += 1
    return n


# ── ③ 照合（SQL で読み、pandas で担当者をまたいで集計） ────────
def collate(post, ext):
    """③ 今回の記録 + 抽出 → 企業の輪郭。
    返す dict のキー: company_id, name, industry, as_of, current_post_id,
      static{owner_age, years, employees, key_customers, dependency, tech_note},
      timeline[{post_id, date, author, text, formal[], candidate[], value[], evidence{tag: 文}, origin{tag: report|hearsay}}],
      tag_table[{tag, name, category, first, last, n, authors}]   ← pandas の集計（担当者をまたぐ）
      value_assets[{tag, source, text}], assignments[{staff_id, staff_name, dept, from_date, to_date}]"""
    c = db.get_company(post["company_id"])
    since = months_before(post["posted_at"], RULES["gate"]["window_months"])
    timeline, value_assets = [], []

    # 過去の記録（担当者をまたぐ）。今回の記録は DB を経由せず ext から載せる
    for p in db.get_posts(post["company_id"], since=since, until=post["posted_at"]):
        if p["id"] == post["id"]:
            continue
        item = {"post_id": p["id"], "date": p["posted_at"], "author": p["author_name"] or p["author_id"],
                "text": p["text"], "formal": [], "candidate": [], "value": [],
                "evidence": {}, "origin": {}}
        for t in p["tags"]:
            item[t["tier"]].append(t["tag_id"])
            item["evidence"][t["tag_id"]] = t["evidence"] or ""
            item["origin"][t["tag_id"]] = t.get("origin") or "report"
            if t["tier"] == "value":
                value_assets.append({"tag": t["tag_id"], "source": f"post {p['id']}", "text": t["evidence"] or ""})
        timeline.append(item)
    author = db.get_staff(post["author_id"])
    cur = {"post_id": post["id"], "date": post["posted_at"], "author": author["name"] if author else post["author_id"],
           "text": post["text"], "formal": [t["tag"] for t in ext["formal"]],
           "candidate": [t["tag"] for t in ext["candidate"]], "value": [t["tag"] for t in ext["value"]],
           "evidence": {t["tag"]: t["evidence"] for t in all_tags(ext)},
           "origin": {t["tag"]: t.get("origin", "report") for t in all_tags(ext)}}
    timeline.append(cur)
    value_assets += [{"tag": t["tag"], "source": f"post {post['id']}", "text": t["evidence"]} for t in ext["value"]]

    # pandas：記録×正式タグの表にして、タグごとに 初出・最新・件数・書いた担当者 を集計（★3-1「整理・加工・分析」）
    rows = [{"date": t["date"], "author": t["author"], "tag": tag} for t in timeline for tag in t["formal"]]
    tag_table = []
    if rows:
        df = pd.DataFrame(rows)
        g = df.groupby("tag").agg(first=("date", "min"), last=("date", "max"), n=("date", "size"),
                                  authors=("author", lambda s: "／".join(dict.fromkeys(s))))
        for tag, r in g.iterrows():
            tag_table.append({"tag": tag, "name": tag_name(tag), "category": RULES["formal"][tag]["category"],
                              "first": r["first"], "last": r["last"], "n": int(r["n"]), "authors": r["authors"]})

    # 静的要因（顧客マスタ）。従業員数・取引先・技術は「次の世代につなぎたいもの」にもなる
    static = {"owner_age": c.get("owner_age"), "years": (int(post["posted_at"][:4]) - c["founded_year"]) if c.get("founded_year") else None,
              "employees": c.get("employees"), "key_customers": c.get("key_customers"), "dependency": c.get("dependency"),
              "tech_note": c.get("tech_note")}
    if static["employees"]:
        value_assets.append({"tag": "V_EMPLOYMENT", "source": "static", "text": f"従業員{static['employees']}名の雇用",
                             "head": f"{static['employees']}名", "detail": "従業員の雇用"})
    if static["key_customers"]:
        names = [x.strip() for x in re.split(r"[、,]", static["key_customers"]) if x.strip()]
        value_assets.append({"tag": "V_CUSTOMERS", "source": "static", "text": f"{static['key_customers']}との取引（サプライチェーン）",
                             "head": f"{len(names)}社", "detail": "、".join(names) + "との取引（サプライチェーン）"})
    if static["tech_note"]:
        tech, _, note = static["tech_note"].partition("／")
        if not describes_value(note):                 # 「娘婿が専務として在籍」などの状況メモは価値に入れない
            note = ""
        value_assets.append({"tag": "V_TECHNOLOGY", "source": "static", "text": f"{tech}／{note}" if note else tech,
                             "head": tech, "detail": note})

    return {"company_id": c["id"], "name": c["name"], "industry": c.get("industry") or "", "as_of": post["posted_at"],
            "current_post_id": post["id"], "static": static, "timeline": timeline, "tag_table": tag_table,
            "value_assets": value_assets, "assignments": db.get_assignments(c["id"])}


def pre_visit_summary(company_id, as_of=None, limit=3):
    """訪問前のまとめ（v4 フェーズ 1「読む」）：タグ付きの記録を新しい順に limit 件、出典付きで返す
    → [{date, author, name, text, unconfirmed}]（unconfirmed＝伝聞の文から拾ったもの）"""
    out = []
    for p in reversed(db.get_posts(company_id, until=as_of)):
        formal = [t for t in p["tags"] if t["tier"] == "formal"]
        cand = [t for t in p["tags"] if t["tier"] == "candidate"]
        label = "、".join(tag_name(t["tag_id"]) for t in formal) or "、".join(tag_name(t["tag_id"]) for t in cand)
        if label:
            unconfirmed = bool(formal or cand) and all((t.get("origin") or "report") == "hearsay" for t in (formal or cand))
            out.append({"date": p["posted_at"], "author": p["author_name"], "name": label,
                        "text": p["text"], "unconfirmed": unconfirmed})
        if len(out) >= limit:
            break
    return out


# ── ④ 判定 ─────────────────────────────────────────────────
def summarize_tags(profile):
    """正式タグごとに出典（いつ・誰・引用）をまとめる → [{tag, name, category, sources[{post_id,date,author,evidence,unconfirmed}]}]
    unconfirmed＝雑談などで聞いた伝聞（未確認）。重なりには数えるが、画面と理由文で印を付ける"""
    by_tag = {}
    for t in profile["timeline"]:
        for tag in t["formal"]:
            by_tag.setdefault(tag, []).append({"post_id": t["post_id"], "date": t["date"], "author": t["author"],
                                               "evidence": t["evidence"].get(tag, ""),
                                               "unconfirmed": t.get("origin", {}).get(tag) == "hearsay"})
    return [{"tag": k, "name": tag_name(k), "category": RULES["formal"][k]["category"], "sources": v} for k, v in by_tag.items()]


def gate(profile, summary):
    """発火ゲート（if 文だけ。judgment_criteria.md「提示するかどうか」）。G-03 なら発火

    G-00 今回の記録に正式タグが無い／G-01 重なりが 1 種だけ／G-02 重なるが条件未満／G-03 提示する
    種類の数 ＝ 正式タグの種類数 ＋ 静的要因「経営者の高齢化」（rules.json の gate.count_static_owner_age）
    """
    g = RULES["gate"]
    recent_since = months_before(profile["as_of"], g["recent_months"])
    current = next(t for t in profile["timeline"] if t["post_id"] == profile["current_post_id"])
    if not current["formal"]:
        return "G-00"
    statics = [x for x in static_hits(profile) if x["counts"]] if g.get("count_static_owner_age") else []
    distinct = len(summary) + len(statics)
    if distinct < 2:
        return "G-01"
    recent_cats = {s["category"] for s in summary if any(x["date"] >= recent_since for x in s["sources"])}
    if statics:
        recent_cats.add("static")
    if distinct >= g["min_distinct"] and len(recent_cats) >= g["min_recent_categories"]:
        return "G-03"
    return "G-02"


def static_hits(profile):
    """顧客マスタから立つ静的要因（rules.json の static）→ [{tag_id, name, text, counts}]
    counts=True のものは「種類の異なる予兆」の 1 種として数える（経営者の高齢化）"""
    st, out = RULES["static"], []
    age, years = profile["static"]["owner_age"], profile["static"]["years"]
    if age and age >= st["owner_age"]["threshold"]:
        out.append({"tag_id": st["owner_age"]["tag_id"], "name": st["owner_age"]["name"],
                    "text": f"{st['owner_age']['name']}（{age}歳）", "counts": True})
    if years and years >= st["years_in_business"]["threshold"]:
        out.append({"tag_id": st["years_in_business"]["tag_id"], "name": st["years_in_business"]["name"],
                    "text": f"{st['years_in_business']['name']}（業歴{years}年）", "counts": False})
    return out


def static_facts(profile):
    s = profile["static"]
    facts = []
    if s["owner_age"]:
        facts.append(f"経営者 {s['owner_age']}歳")
    if s["years"]:
        facts.append(f"業歴 {s['years']}年")
    if s["employees"]:
        facts.append(f"従業員 {s['employees']}名")
    return facts


def describes_value(note):
    """顧客マスタのメモが「技術の価値」を説明しているか（例：地域内で代替先が限られる…技術を保有）。
    承継や経営者の状況のメモ（例：娘婿が専務として在籍、技術の継承先なし）は価値ではないので使わない"""
    return bool(note) and bool(re.search(r"(代替|保有|唯一|限られる|強み)", note)) and not re.search(r"(承継|継承|娘婿|高齢|経営者)", note)


VALUE_LABEL = {"V_EMPLOYMENT": "地域の雇用", "V_CUSTOMERS": "長年の取引関係", "V_TECHNOLOGY": "技術・ノウハウ"}


def legacy_items(profile):
    """次の世代につなぎたいもの（タイル表示用）→ [{tag, label, head, detail, source}]
    head＝大きく見せる要点（38名／2社／特殊薄板加工）、detail＝補足。記録から拾った価値（地域の文化・ブランド等）は引用を補足に"""
    seen, out = set(), []
    for v in sorted(profile["value_assets"], key=lambda v: 0 if v["source"] == "static" else 1):
        if v["tag"] in seen:
            continue
        seen.add(v["tag"])
        out.append({"tag": v["tag"], "label": VALUE_LABEL.get(v["tag"], tag_name(v["tag"])),
                    "head": v.get("head") or tag_name(v["tag"]), "detail": v.get("detail", v["text"]),
                    "source": "顧客データ" if v["source"] == "static" else "面談メモ"})
    return out


def lost_values(profile):
    """次の世代につなぎたいもの（この企業が地域で担っていること）。同じ種類はマスタ由来（static）を優先して 1 つ
    画面では前向きな言い方で出す（「失われる」とは言わない。変更記録 CH-18）"""
    seen, out = set(), []
    for v in sorted(profile["value_assets"], key=lambda v: 0 if v["source"] == "static" else 1):
        if v["tag"] not in seen:
            seen.add(v["tag"])
            out.append(v["text"])
    return out


# LLM 無しの理由文で使う言い回し（事実の部分。判定基準＝rules.json の criteria の言葉に沿わせる）
REASON_FACT = {"successor": "後継者が定まっていない様子が、{first}の記録から続いています",
               "people": "技術や業務が特定の人に依存している様子が、{last}に記録されています",
               "business": "{name}が、{last}に記録されています"}


def _who_when(x):
    return f"{x['date'][:4]}年{int(x['date'][5:7])}月・{x['author'].split(' ')[0]}"


def reason_prose(profile, summary):
    """事実（出典つき）→ 推測（〜の可能性があります）の順で 3〜4 文にする。推測は 1 文だけ、断定しない"""
    facts = []
    for s in sorted(summary, key=lambda s: ["successor", "people", "business"].index(s["category"]) if s["category"] in ("successor", "people", "business") else 9):
        src = sorted(s["sources"], key=lambda x: x["date"])
        used = src[0] if s["category"] == "successor" else src[-1]
        facts.append(REASON_FACT.get(s["category"], REASON_FACT["business"]).format(
            first=_who_when(src[0]), last=_who_when(src[-1]), name=s["name"])
            + ("（雑談などで聞いた未確認の話です）" if used.get("unconfirmed") else ""))
    for x in static_hits(profile):
        if x["counts"]:
            facts.append(f"経営者は{profile['static']['owner_age']}歳です（顧客データ）")
    body = "。".join(facts) + "。" if facts else ""
    guess = "それぞれは小さな話ですが、重なることで、承継の準備に使える時間が限られてきている可能性があります。"
    return body + guess


def reason_template(profile, summary):
    """LLM 無しの理由文：事実を出典つきで述べ、推測は 1 文だけ（〜の可能性があります）。箇条書き（- ）は予兆の一覧"""
    lines = [f"{profile['name']}について、支援の検討が必要かもしれません。",
             f"{len({x['author'] for s in summary for x in s['sources']})}人の担当者が残した記録と顧客データから、事業承継の予兆が重なっています。",
             reason_prose(profile, summary)]
    for s in summary:
        src = "／".join(f"{x['date'][:7].replace('-', '年')}月・{x['author']}" + ("（未確認）" if x.get("unconfirmed") else "")
                       for x in s["sources"])
        lines.append(f"- {s['name']}（{src}）")
    for x in static_hits(profile):
        if x["counts"]:
            lines.append(f"- {x['text']}　※顧客データ")
    tail = [x["text"] for x in static_hits(profile) if not x["counts"]]
    if tail:
        lines.append("（" + "、".join(tail) + "。長く地域で続いてきた分、次の世代につなぐ意味も大きい企業です）")
    return "\n".join(lines)


def reason_llm(profile, summary):
    """LLM の理由文（任意）：判定基準の言葉（rules.json の criteria）をそのまま渡す"""
    cr = RULES["criteria"]
    system = ("以下は事業承継支援室のベテランが書いた判定基準です。この言葉に従ってください。\n" +
              "\n".join(f"- {s}" for s in cr["sentences"]) + f"\n\n{cr['closing']}\n\n書き方の約束:\n" +
              "\n".join(f"- {s}" for s in cr["style"]))
    facts = "\n".join(f"- {s['name']}: " + "／".join(f"{x['date']}・{x['author']}「{x['evidence']}」" + ("（雑談で聞いた未確認の話）" if x.get("unconfirmed") else "")
                                                    for x in s["sources"]) for s in summary)
    user = (f"企業: {profile['name']}（{profile['industry']}）\n静的要因（事実）: {'、'.join(static_facts(profile)) or 'なし'}\n"
            f"観測された予兆（出典付き）:\n{facts}\n\n担当者向けの理由文を 3〜4 文で。出典（年月・担当者名）を文中に添えてください。"
            "「未確認の話」と書かれたものは、未確認であることを文中で明示してください。"
            "企業が地域で担っていることは「次の世代につなぎたいもの」として前向きに書き、「失われる」「消える」など不安をあおる言い方はしないでください。")
    return llm_chat(system, user)


def context_posts(profile, ext):
    """反応②「過去の文脈が返る」：今回と同じ正式タグ／候補タグを持つ過去の記録 → [{date, author, text, shared[]}]"""
    mine = {t["tag"] for t in ext["formal"]} | {t["tag"] for t in ext["candidate"]}
    out = []
    for t in profile["timeline"]:
        if t["post_id"] == profile["current_post_id"]:
            continue
        shared = [tag_name(x) for x in (t["formal"] + t["candidate"]) if x in mine]
        if shared:
            out.append({"date": t["date"], "author": t["author"], "text": t["text"], "shared": shared})
    return out


def assess(profile, ext, use_llm=True):
    """④ 輪郭 → 判定。反応の層（v4 §9.3）も決める。
    返す dict のキー: company_id, post_id, fired, reaction(1〜4), reaction_label, gate[], tags[]（summarize_tags）,
      static_facts[], reason, lost_values[], context[]（反応②用）, candidates[]（反応③用 {name, count}）, generated_by"""
    summary = summarize_tags(profile)
    g = gate(profile, summary)
    fired = g == "G-03"
    cands = [{"name": tag_name(t["tag"]),
               "count": db.count_candidate_records(t["tag"], profile["current_post_id"]) + 1}    # 今回を含めて何回目か
              for t in ext["candidate"]]
    threshold = RULES.get("candidate_promote_threshold", 3)
    ctx = context_posts(profile, ext)
    if fired:
        reaction = 4
    elif any(c["count"] >= threshold for c in cands):
        reaction = 3                                              # 既知の定義にない変化が複数回
    elif ctx or ext["formal"]:
        reaction = 2                                              # 判定はしないが、前にも似た話があった
    else:
        reaction = 1                                              # そっと蓄積する（正常動作）
    sig = {"company_id": profile["company_id"], "post_id": profile["current_post_id"], "fired": fired,
           "reaction": reaction, "reaction_label": REACTION[str(reaction)], "gate": [g], "tags": summary,
           "static_facts": static_facts(profile), "statics": static_hits(profile), "reason": "", "lost_values": [],
           "context": ctx, "candidates": cands, "generated_by": "gate"}
    if fired:
        text = reason_llm(profile, summary) if (use_llm and llm_available()) else None
        sig["reason"] = text or reason_template(profile, summary)
        sig["lost_values"] = lost_values(profile)
        sig["generated_by"] = "gate+llm" if text else "gate+template"
    sig["legacy"] = legacy_items(profile)
    return sig


# ── 企業の状態（今日の記録が無くても、蓄積だけから④と同じ条件で見る。取引先の画面用） ──
def days_between(a, b):
    """'YYYY-MM-DD' の日数差（b - a）"""
    from datetime import date as _date
    ay, am, ad = (int(x) for x in a.split("-"))
    by, bm, bd = (int(x) for x in b.split("-"))
    return (_date(by, bm, bd) - _date(ay, am, ad)).days


def company_state(company_id, as_of=None, use_llm=False):
    """訪問前に企業の画面で読む用。今日の記録を入れずに、これまでの蓄積だけで状態を出す。
    返す dict のキー: company, profile, tags[], statics[], candidates[], state(1〜4), state_label, issued, ready,
      last_post, days_since, knowledge, people, next_actions
    state（バッジ）＝この企業に実際に出た最新シグナルの層。まだ無ければ ① 静か。
    ready＝蓄積だけ見れば ④ の条件を満たす（次に正式タグの付く記録が入れば立つ）。画面の注意書きに使う"""
    c = db.get_company(company_id)
    posts = db.get_posts(company_id, until=as_of)
    if not posts:
        return {"company": c, "profile": None, "tags": [], "statics": [], "candidates": [], "state": 1,
                "state_label": REACTION["1"], "last_post": None, "days_since": None,
                "knowledge": {"items": [], "public": []}, "people": None, "next_actions": None}
    last = posts[-1]
    profile = collate(last, extract(last, use_llm=False))
    summary, statics = summarize_tags(profile), static_hits(profile)
    g = RULES["gate"]
    recent_since = months_before(profile["as_of"], g["recent_months"])
    recent_cats = {x["category"] for x in summary if any(y["date"] >= recent_since for y in x["sources"])}
    counted = [x for x in statics if x["counts"]] if g.get("count_static_owner_age") else []
    if counted:
        recent_cats.add("static")
    cands = []
    for t in {t["tag_id"] for p_ in posts for t in p_["tags"] if t["tier"] == "candidate"}:
        cands.append({"name": tag_name(t), "count": db.count_candidate_records(t)})
    # 状態バッジは「これまでに実際に出たシグナル」を出す。判定は記録をきっかけに走るので、
    # 蓄積だけで先に「支援の検討」とは言わない（企画書 v4 §9.3・judgment_criteria.md）
    issued = db.get_last_signal(company_id)
    state = issued["reaction"] if issued and issued["reaction"] else 1
    # 参考：次の記録で条件を満たすか（画面の注意書きに使う。バッジには使わない）
    ready = (len(summary) + len(counted) >= g["min_distinct"] and len(recent_cats) >= g["min_recent_categories"])
    sig = {"company_id": company_id, "post_id": last["id"], "fired": state == 4, "reaction": state,
           "reaction_label": REACTION[str(state)], "gate": [], "tags": summary, "static_facts": static_facts(profile),
           "statics": statics, "reason": "", "lost_values": lost_values(profile), "context": [], "candidates": cands,
           "generated_by": "state"}
    knowledge = retrieve(profile, sig, last["text"])
    people = who_to_ask(knowledge, profile, sig)
    return {"company": c, "profile": profile, "tags": summary, "statics": statics, "candidates": cands,
            "state": state, "state_label": REACTION[str(state)], "issued": issued, "ready": ready, "last_post": last,
            "days_since": days_between(last["posted_at"], as_of) if as_of else None,
            "signal": sig, "knowledge": knowledge, "people": people, "legacy": legacy_items(profile),
            "next_actions": recommend(sig, knowledge, people, use_llm=use_llm) if (summary or cands) else None}


# ── ⑤ ナレッジ検索（W4 の ranking.py。行内 + 公開を同じ索引で） ──
_indexed = False


def ensure_index():
    """ナレッジ全件（internal + public）から TF-IDF インデックスを 1 回だけ作る"""
    global _indexed
    if not _indexed or not get_engine().is_fitted:
        names = {k: v["name"] for tier in ("formal", "candidate", "value") for k, v in RULES[tier].items()}
        rebuild_index(db.get_all_knowledge(shareable_only=True), names)   # 閲覧制限のある案件詳細は索引に入れない
        _indexed = True


def reset_index():
    global _indexed
    _indexed = False


def best_snippet(text, query, width=120):
    """クエリの断片が最も密に出る窓を抜粋（tech0-search の who.py と同じ発想）"""
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= width:
        return text
    terms = re.findall(r"[一-龠ァ-ヶー]{2,}", query)
    best_pos, best_hits = 0, -1
    for pos in range(0, len(text) - width + 1, width // 2):
        hits = sum(text[pos:pos + width].count(t) for t in terms)
        if hits > best_hits:
            best_pos, best_hits = pos, hits
    return ("…" if best_pos else "") + text[best_pos:best_pos + width] + "…"


def retrieve(profile, signal, post_text, top_n=5, public_n=2):
    """⑤ 輪郭 + 判定 → ナレッジ。
    返す dict のキー: query, items[]（行内。knowledge の行 + score, snippet。kind ごとに最低 1 件）, public[]（公開。url 付き、最大 public_n）"""
    ensure_index()
    cur = next(t for t in profile["timeline"] if t["post_id"] == profile["current_post_id"])
    cur_tags = (" ".join(tag_name(x) for x in cur["formal"]) + " ") * 3           # 今日の気づきを重くする
    tags = " ".join(s["name"] for s in signal["tags"])
    size = f"従業員{profile['static']['employees']}名" if profile["static"]["employees"] else ""
    query = f"{cur_tags}{tags} {profile['industry']} {size} {post_text}"
    ranked = get_engine().search(query, top_n=60)
    internal = [r for r in ranked if r.get("source") != "public"]
    # 公開ナレッジ（公的な支援制度・手引き・法律／税制）は、支援制度と法律・税制から 1 件ずつ（無ければ上位から）
    pub_all = [r for r in ranked if r.get("source") == "public"]
    public = [first for kinds in (("option", "knowhow"), ("law",))
              for first in [next((r for r in pub_all if r["kind"] in kinds), None)] if first][:public_n]
    public += [r for r in pub_all if r not in public][:max(public_n - len(public), 0)]
    picked = []
    for kind in ("case", "knowhow", "option"):
        first = next((r for r in internal if r["kind"] == kind), None)
        if first:
            picked.append(first)
    for r in internal:
        if len(picked) >= top_n:
            break
        if r not in picked:
            picked.append(r)
    picked.sort(key=lambda x: x["score"], reverse=True)
    for r in picked + public:
        r["snippet"] = best_snippet(r.get("full_text") or r.get("summary") or "", query)
    return {"query": query, "items": picked[:top_n], "public": public}


# ── ⑥ 人軸検索（tech0-search の who.py の作者集計。関係の情報だけで選ぶ） ─
KIND_WEIGHT = {"case": 1.0, "knowhow": 0.5, "option": 0.0}


def who_to_ask(knowledge, profile, signal, current_author_id=None):
    """⑥ ナレッジ + 担当履歴 → 行員。
    返す dict のキー: targets[{staff_id,name,dept,branch,why,grounded_on[],how[]}], predecessors[同], dept_fallback[], external[{kind, via}]（行員が相談する外部の専門家の種類と、行内の窓口）
    順位は無い（部署順）。how は「直接相談する」「上司に相談する」（v4 §12.3。担当者が選ぶ）"""
    staff = {s["id"]: s for s in db.get_staff_all()}
    grounds, why_extra = defaultdict(list), defaultdict(list)
    for item in knowledge["items"]:
        if KIND_WEIGHT.get(item["kind"], 0) > 0:
            for sid in item["handled_by"]:
                grounds[sid].append(item["id"])
    # 相談履歴（この企業・この事例カードについて誰が誰に相談したか）＝関係の情報だけで選ぶ
    for c in db.get_consultations(profile["company_id"], [k["id"] for k in knowledge["items"]]):
        if c["to_staff"]:
            grounds[c["to_staff"]].append(c["id"])
            why_extra[c["to_staff"]].append(f"「{c['theme'][:20]}」の相談を受けている")
    how = ["直接相談する", "上司に相談する"]

    pred_ids, predecessors = [], []
    for a in profile["assignments"]:
        if a["to_date"] and a["staff_id"] != current_author_id:
            pred_ids.append(a["staff_id"])
            s = staff.get(a["staff_id"], {})
            predecessors.append({"staff_id": a["staff_id"], "name": s.get("name", a["staff_id"]), "dept": s.get("dept", ""),
                                 "branch": s.get("branch", ""), "grounded_on": ["assignment"], "how": how,
                                 "boss": (staff.get(s.get("reports_to")) or {}).get("name", ""),
                                 "why": f"{profile['name']}の前任担当（{a['from_date'][:7]}〜{a['to_date'][:7]}）"})

    targets = []
    for sid, ids in grounds.items():
        s = staff.get(sid)
        if not s:
            continue
        titles = [k["title"].split("（")[0] for k in knowledge["items"] if k["id"] in ids][:2]
        parts = ["、".join(titles) + " を担当"] if titles else []
        parts += why_extra.get(sid, [])
        why, g = "／".join(parts) or "この領域の相談を受けている", list(ids)
        if sid in pred_ids:
            why += f"／{profile['name']}の前任担当"
            g.append("assignment")
        boss = staff.get(s.get("reports_to")) if s.get("reports_to") else None
        targets.append({"staff_id": sid, "name": s["name"], "dept": s["dept"], "branch": s["branch"], "why": why,
                        "grounded_on": g, "how": how, "boss": boss["name"] if boss else ""})
    targets.sort(key=lambda p: (p["dept"], p["name"]))

    cats = {s["category"] for s in signal["tags"]}
    fallback = [] if targets else sorted({RULES["dept_fallback"][c] for c in cats if c in RULES["dept_fallback"]})
    # 外部の専門家＝行員自身が確かめたいときの相談先（お客さまへの紹介ではない）。種類と、相談するときの行内の窓口を返す
    external, seen = [], set()
    for c in sorted(cats, key=lambda c: ["successor", "people", "business"].index(c) if c in ("successor", "people", "business") else 9):
        for e in RULES["external_kinds"].get(c, []):
            if e not in seen:
                seen.add(e)
                external.append({"kind": e, "via": RULES["dept_fallback"].get(c, "本部 事業承継支援室")})
    return {"targets": targets, "predecessors": [p for p in predecessors if p["staff_id"] not in grounds],
            "dept_fallback": fallback, "external": external}


# ── ⑦ 次の一手 ─────────────────────────────────────────────
def _dedupe(xs, limit):
    seen, out = set(), []
    for x in xs:
        x = x.strip()
        if x and x not in seen:
            seen.add(x)
            out.append(x)
        if len(out) >= limit:
            break
    return out


def _clean(xs):
    """禁止語（金利・格付 など）を含む項目は落とす（与信転用の防止）"""
    return [x for x in xs if not any(b in x for b in RULES["forbidden_words"])]


def public_refs(knowledge):
    """公的な支援制度・法律／税制の出典（v4 からの変更 3。外部の事例は出さない：変更記録 CH-14）→ [{id, kind, title, url}]"""
    return [{"id": k["id"], "kind": k["kind"], "title": k["title"], "url": k["url"]} for k in knowledge.get("public", [])]


def verify_questions(signal):
    """伝聞の話（未確認）は、次の訪問で確かめる問いにする（確かめて業務報告に書けば事実になる）"""
    return [f"雑談などで聞いた未確認の話を確かめる：「{x['evidence']}」（{x['date'][:7]}・{x['author']}）"
            for s in signal["tags"] for x in s["sources"] if x.get("unconfirmed")]


def recommend_template(signal, knowledge, people):
    """LLM 無しの次の一手。
      questions＝お客さま（社長・社員の方）に次の訪問で確かめること（未確認の話の確認 → 知恵の問い → 予兆ごとの問い）
      actions  ＝行内での準備（似た事例をまとめて確認 → 前担当で知見のある人 → 前任 → そのほかの相談先）"""
    questions, options, actions, grounded = [], [], [], []
    verify = verify_questions(signal)
    for k in knowledge["items"]:
        if k["kind"] == "knowhow":
            questions += k["questions"]
            grounded.append(k["id"])
    for s in signal["tags"]:
        questions += RULES["formal"][s["tag"]].get("questions", [])
    for k in knowledge["items"]:
        if k["kind"] == "option":
            options.append(k["title"])
            grounded.append(k["id"])
    cases = [k for k in knowledge["items"] if k["kind"] == "case"]
    if cases:                                        # 事例は 1 行にまとめる（同じ文の繰り返しを避ける）
        actions.append("似た事例（" + "・".join(f"{k['branch'] or '過去'} {k['id']}" for k in cases) + "）の進め方を、事例集で確認する")
        grounded += [k["id"] for k in cases]
    titles = {k["id"]: k["title"] for k in cases}
    # 前に担当していて、似た事例も手がけた人を先に（企画書 v4 §5：林さん→大原さんの順につながる）
    for p in sorted(people["targets"], key=lambda p: 0 if "assignment" in p["grounded_on"] else 1):
        did = [f"「{titles[g]}」" for g in p["grounded_on"] if g in titles][:2]
        why = "／".join(x for x in [("この企業を以前担当" if "assignment" in p["grounded_on"] else ""),
                                   ("".join(did) + "を担当" if did else "")] if x)
        actions.append(f"{p['name']}（{p['dept']}）に相談する" + (f"（{why}）" if why else ""))
        grounded.append(p["staff_id"])
        if "assignment" in p["grounded_on"] and people["predecessors"]:
            q = people["predecessors"][0]                 # 前任はその次に（記録に残っていない様子を聞く）
            actions.append(f"前任の{q['name']}（{q['dept']}）に、担当当時の様子を聞く")
            grounded.append(q["staff_id"])
    for q in people["predecessors"]:
        actions.append(f"前任の{q['name']}（{q['dept']}）に、担当当時の様子を聞く")
        grounded.append(q["staff_id"])
    return {"questions": _clean(_dedupe(verify, 2) + _dedupe(questions, 3)), "options": _clean(_dedupe(options, 3)),
            "actions": _clean(_dedupe(actions, 4)), "public_refs": public_refs(knowledge),
            "grounded_on": _dedupe(grounded, 20), "generated_by": "template"}


def recommend_llm(signal, knowledge, people):
    """LLM 版（任意）。渡した ID 以外を書かせず、ID 引用の無い項目は捨てる"""
    system = ('あなたは地方銀行の事業承継支援室のベテランです。若手に「次の一手」を助言します。出力は JSON のみ: '
              '{"questions":[3件以内],"options":[3件以内],"actions":[4件以内]}。'
              "questions は次の訪問でお客さま（社長・社員の方）に確かめること、actions は行内での準備（事例を調べる・行員に相談する）。"
              "渡された理由文・ナレッジ・行員の情報だけを使い、各項目の末尾に根拠の ID を【K-xxx】のように付ける。"
              "融資の可否・金利・融資枠・信用格付け・承継先の具体名は書かない。断定を避け、次回訪問で使える言葉にする。")
    k_lines = "\n".join(f"- {k['id']} [{k['kind']}] {k['title']}: {(k.get('summary') or '')[:120]}"
                        + (f" 行動: {'; '.join(k['actions'][:2])}" if k["actions"] else "") for k in knowledge["items"])
    p_lines = "\n".join(f"- {p['staff_id']} {p['name']}（{p['dept']}）: {p['why']}" for p in people["targets"] + people["predecessors"]) or "なし"
    data = llm_chat(system, f"理由文:\n{signal['reason']}\n\nナレッジ:\n{k_lines}\n\n行員:\n{p_lines}", want_json=True)
    if not data:
        return None
    valid = {k["id"] for k in knowledge["items"]} | {p["staff_id"] for p in people["targets"] + people["predecessors"]}

    def keep(xs):                                   # ← if 文で守る：知らない ID・ID 無しは捨てる
        return _clean([x for x in (xs or []) if re.findall(r"[KHOS]-[0-9A-Za-z-]+", x)
                       and all(i in valid for i in re.findall(r"[KHOS]-[0-9A-Za-z-]+", x))])
    q, o, a = keep(data.get("questions")), keep(data.get("options")), keep(data.get("actions"))
    if not (q or a):
        return None
    grounded = sorted({i for x in q + o + a for i in re.findall(r"[KHOS]-[0-9A-Za-z-]+", x)})
    return {"questions": q[:3], "options": o[:3], "actions": a[:4], "public_refs": public_refs(knowledge),
            "grounded_on": grounded, "generated_by": "llm"}


def recommend(signal, knowledge, people, use_llm=True):
    """⑦ 判定 + ナレッジ + 行員 → 次の一手。返す dict のキー: questions[], options[], actions[], public_refs[], grounded_on[], generated_by"""
    if signal["fired"] and use_llm and llm_available():
        res = recommend_llm(signal, knowledge, people)
        if res:
            res["questions"] = _dedupe(verify_questions(signal), 2) + res["questions"]
            return res
    return recommend_template(signal, knowledge, people)


# ── run：①〜⑦ を順に ─────────────────────────────────────────
def run(post, use_llm=True, persist=True):
    """記録 1 件 → 全工程。返す dict のキー: post, extraction, profile, signal, knowledge, people, next_actions, elapsed_sec
    persist=True なら記録・タグ・判定・監査ログを DB に残す（＝記録が次の誰かの検索対象になる）"""
    t0 = time.time()
    if persist:
        db.insert_post(post)
        db.log_audit(post["author_id"], "post", post["company_id"], post["id"])
    ext = extract(post, use_llm=use_llm)                                   # ②
    if persist:
        db.replace_post_tags(post["id"], all_tags(ext))
        for c in ext["candidate"]:
            db.bump_candidate_tag(c["tag"], post["posted_at"])
    profile = collate(post, ext)                                           # ③
    signal = assess(profile, ext, use_llm=use_llm)                         # ④
    if persist:
        db.insert_signal(signal)
    knowledge = retrieve(profile, signal, post["text"])                    # ⑤
    people = who_to_ask(knowledge, profile, signal, current_author_id=post["author_id"])   # ⑥
    nxt = recommend(signal, knowledge, people, use_llm=use_llm)            # ⑦
    elapsed = round(time.time() - t0, 2)
    if persist:
        db.log_audit(post["author_id"], "search", post["company_id"],
                     f"reaction={signal['reaction']} fired={signal['fired']} items={len(knowledge['items'])} public={len(knowledge['public'])} sec={elapsed}")
    return {"post": post, "extraction": ext, "profile": profile, "signal": signal,
            "knowledge": knowledge, "people": people, "next_actions": nxt, "elapsed_sec": elapsed}


if __name__ == "__main__":
    # 確認用：python tsumugu.py で「今日の 1 件」を流す（DB には残さない）
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    p = new_post("C001", "C001-P1", "E001", "2026-09-15",
                 "定例訪問。受注状況を確認。前年並みとのこと。帰り際の雑談で、斎藤工場長が来春での退職を考えているらしいと伺った。",
                 post_id="P-TEST")
    r = run(p, use_llm=False, persist=False)
    print("③", *[f"{t['name']} {t['first']}〜{t['last']} ×{t['n']} {t['authors']}" for t in r["profile"]["tag_table"]], sep="\n   ")
    print("④", r["signal"]["reaction"], r["signal"]["reaction_label"], r["signal"]["gate"])
    print(r["signal"]["reason"])
    print("⑤", [(k["id"], k["kind"]) for k in r["knowledge"]["items"]], "公開:", [(k["id"], k["url"]) for k in r["knowledge"]["public"]])
    print("⑥", [(x["name"], x["dept"]) for x in r["people"]["targets"]], "前任:", [x["name"] for x in r["people"]["predecessors"]])
    print("⑦", r["next_actions"]["questions"], r["elapsed_sec"], "秒")
