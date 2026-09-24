# =============================================================
# tests/test_tsumugu.py — 「動いた」の証拠（作らなくても動く。作ると安心）
#   実行: pytest -q
#   期待値はもっちゃんの合成データの答え合わせ用データ：
#     reports.json の reference_tags / reference_candidate（79 件すべて）と
#     demo_inputs.json の expected_layer（D1 予兆が立つ／D2 過去の文脈／D3 候補タグ）
#   LLM もネットも使わない。
# =============================================================
import json
import os
import sys
import unicodedata
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["TSUMUGU_NO_LLM"] = "1"

SRC = next(p for p in ROOT.iterdir() if p.is_dir() and "ツムグ合成データ" in unicodedata.normalize("NFC", p.name))
REPORTS = json.loads((SRC / "reports.json").read_text(encoding="utf-8"))
DEMOS = json.loads((SRC / "demo_inputs.json").read_text(encoding="utf-8"))
POSTS = {p["id"]: p for p in json.loads((ROOT / "data.json").read_text(encoding="utf-8"))["posts"]}


@pytest.fixture(scope="session", autouse=True)
def seeded_db(tmp_path_factory):
    import database as db
    db.DB_PATH = tmp_path_factory.mktemp("db") / "test.db"     # 本番の DB を汚さない
    db.ingest(reset=True)
    import crawler                                             # ネットは使わず、公開ナレッジを 1 件だけ手で入れる
    page = {"url": "https://example.test/case", "title": "テスト事例 | サイト名", "description": "",
            "full_text": "後継者不在 の金属加工業で従業員承継を進めた支援事例。技術継承と設備投資の相談。",
            "crawled_at": "2026-09-22T00:00:00", "crawl_status": "success"}
    db.insert_knowledge(crawler.to_knowledge(page, {"id": "TEST", "kind": "option", "label": "テスト"}))
    import tsumugu
    tsumugu.retag_all()
    yield


def _demo(demo_id, persist=False):
    import tsumugu
    d = next(x for x in DEMOS if x["demo_id"] == demo_id)
    post = tsumugu.new_post(d["company_id"], None, d["employee_id"], d["date"], d["one_liner"], post_id="DEMO-" + demo_id)
    return d, tsumugu.run(post, use_llm=False, persist=persist)


# ── ② 抽出：79 件すべてを答え合わせ ─────────────────────────
def test_extract_matches_reference_tags():
    import tsumugu
    name2id = {v["name"]: k for k, v in tsumugu.RULES["formal"].items()}
    wrong = []
    for r in REPORTS:
        ext = tsumugu.extract(POSTS[r["report_id"]], use_llm=False)
        want = {name2id[n] for n in r["reference_tags"] if n in name2id}
        got = {t["tag"] for t in ext["formal"]}
        if want != got:
            wrong.append((r["report_id"], sorted(want), sorted(got)))
        assert all(t["evidence"] in tsumugu.record_text(POSTS[r["report_id"]]) for t in ext["formal"])
    assert wrong == [], f"正式タグが答えと違う記録: {wrong}"


def test_extract_matches_reference_candidates():
    import tsumugu
    wrong = []
    for r in REPORTS:
        got = {t["tag"] for t in tsumugu.extract(POSTS[r["report_id"]], use_llm=False)["candidate"]}
        want = {r["reference_candidate"]} if r.get("reference_candidate") else set()
        if want != got:
            wrong.append((r["report_id"], sorted(want), sorted(got)))
    assert wrong == [], f"候補タグが答えと違う記録: {wrong}"


def test_formal_tags_are_the_four_from_tags_json():
    import tsumugu
    names = {t["name"] for t in json.loads((SRC / "tags.json").read_text(encoding="utf-8")) if t["type"] == "予兆タグ"}
    assert {v["name"] for v in tsumugu.RULES["formal"].values()} == names


# ── ④ 判定：デモ 3 件の反応の層 ─────────────────────────────
def test_demo1_kanai_fires():
    d, r = _demo("D1")
    sig = r["signal"]
    assert (sig["reaction"], sig["fired"], sig["gate"]) == (d["expected_layer"], True, ["G-03"])
    names = {s["name"] for s in sig["tags"]} | {x["name"] for x in sig["statics"] if x["counts"]}
    assert names >= set(d["expected_overlap"]), names                       # 期待された 5 つの予兆が重なる
    authors = {x["author"] for s in sig["tags"] for x in s["sources"]}
    assert {"林 敏行", "宮本 遥", "佐々木 涼太"} <= authors                  # 担当者 3 人をまたぐ
    assert any("薄板" in v for v in sig["lost_values"])


def test_demo2_ota_denso_returns_context_only():
    d, r = _demo("D2")
    sig = r["signal"]
    assert (sig["reaction"], sig["fired"]) == (d["expected_layer"], False)
    assert len(sig["tags"]) == 1 and sig["tags"][0]["name"] == "後継者未定"   # 同じ種類だけでは立たない
    assert not [x for x in sig["statics"] if x["counts"]]                    # 社長68歳・業歴38年 → 静的要因なし
    assert len(sig["context"]) >= 2                                          # 過去の関連記録が返る


def test_demo3_yamato_kasei_candidate_tag():
    d, r = _demo("D3")
    sig = r["signal"]
    assert (sig["reaction"], sig["fired"]) == (d["expected_layer"], False)
    cand = next(c for c in sig["candidates"] if c["name"] == d["expected_candidate"])
    assert cand["count"] >= 4                                                # 4 回目
    import tsumugu
    assert cand["count"] >= tsumugu.RULES["candidate_promote_threshold"]


def test_quiet_record_is_reaction_one():
    import tsumugu
    post = tsumugu.new_post("C007", None, "E005", "2026-09-15", "訪問しました。特になし。", post_id="Q")
    r = tsumugu.run(post, use_llm=False, persist=False)
    assert (r["signal"]["reaction"], r["signal"]["fired"]) == (1, False)      # 何も返さないのが正常動作


def test_borderline_company_does_not_fire():
    """C003 スズキ木工所：技術継承の属人化 ×2 ＋ 社長75歳。種類が 2 つなので立たない（判定基準の調整用）"""
    import tsumugu
    post = tsumugu.new_post("C003", None, "E006", "2026-09-15", "造作は田村さん一人で回している状態が続いている。", post_id="B")
    r = tsumugu.run(post, use_llm=False, persist=False)
    assert r["signal"]["fired"] is False and r["signal"]["reaction"] == 2


# ── ①' 下書き・⑤⑥⑦ ────────────────────────────────────────
def test_draft_report_without_llm():
    import tsumugu
    post = tsumugu.new_post("C001", "C001-P2", "E001", "2026-09-15", "斎藤工場長が来春での退職を考えていると聞きました。", post_id="P-D")
    d = tsumugu.draft_report(post, use_llm=False)
    assert "カナイ精工" in d and "斎藤" in d


def test_cases_shown_are_case_cards_only():
    """表示・検索に使うのは全行共有可の事例カードだけ（企画書 v4 §12.3）。案件詳細（-D）は出さない"""
    d, r = _demo("D1")
    ids = [k["id"] for k in r["knowledge"]["items"]]
    assert set(d["expected_cases"]) <= set(ids), ids
    assert not [i for i in ids if i.endswith("-D")]
    assert all(k["visibility"] == "全行共有可" for k in r["knowledge"]["items"] if k["source"] == "internal")


def test_people_are_chosen_by_relationship():
    d, r = _demo("D1")
    people = r["people"]["targets"] + r["people"]["predecessors"]
    ids = {p["staff_id"] for p in people}
    assert set(d["expected_contacts"]) <= ids, ids                            # 林（E002）と大原（E007）
    assert "E003" in ids                                                      # 前任の宮本
    assert all(p["grounded_on"] and p["how"] == ["直接相談する", "上司に相談する"] for p in people)
    assert any("相談を受けている" in p["why"] for p in people)                 # 相談履歴も根拠になる


def test_next_actions_grounded_and_clean():
    import tsumugu
    d, r = _demo("D1")
    na = r["next_actions"]
    assert na["questions"] and na["actions"] and na["grounded_on"]
    text = " ".join(na["questions"] + na["options"] + na["actions"])
    assert not any(w in text for w in tsumugu.RULES["forbidden_words"])        # 融資条件の語を出さない
    assert r["knowledge"]["public"] and na["public_refs"][0]["url"].startswith("https://")


def test_feedback_four_kinds_and_audit_seconds():
    import database as db
    import tsumugu
    for kind in tsumugu.RULES["feedback_kinds"]:
        db.insert_feedback("C001", "E001", kind)
    assert db.get_latest_feedback()["C001"]["kind"] == "skipped"
    post = tsumugu.new_post("C001", "C001-P1", "E001", "2026-09-15", "特になし。", post_id="P-9999")
    tsumugu.run(post, use_llm=False, persist=True)
    assert any("sec=" in (a["detail"] or "") for a in db.get_audit_logs(5))


def test_result_is_plain_json():
    _, r = _demo("D1")
    assert json.loads(json.dumps(r, ensure_ascii=False))["signal"]["fired"] is True   # dict だけで出来ている


# ── パイロット版で足したもの（一言の振り分け・閲覧範囲・相談・候補タグの昇格） ─────────
def test_voice_memo_becomes_report_draft():
    import tsumugu
    memo = "定例訪問。受注状況を確認。帰り際の雑談で、斎藤工場長が来春での退職を考えているらしいと聞いた"
    post = tsumugu.new_post("C001", "C001-P1", "E001", "2026-09-15", "", post_id="P-VOICE")
    d = tsumugu.draft_from_voice_memo(post, memo, use_llm=False)
    assert d["report"].endswith("聞いた。") and "受注状況" in d["report"]               # 業務報告 1 本の下書き
    assert "hearsay" not in post                                                   # ツムグの入力欄は増やさない


def test_hearsay_wording_counts_toward_overlap_but_is_marked_unconfirmed():
    """業務報告の中の伝聞（雑談で・らしい）から拾った予兆も重なりには数える。ただし出典に印を付け、確かめる問いを出す"""
    import tsumugu
    post = tsumugu.new_post("C001", "C001-P1", "E001", "2026-09-15",
                            "定例訪問。受注状況を確認。前年並みとのこと。帰り際の雑談で、斎藤工場長が来春での退職を考えているらしいと伺った。",
                            post_id="P-HEAR")
    r = tsumugu.run(post, use_llm=False, persist=False)
    sig = r["signal"]
    assert sig["fired"] is True and sig["reaction"] == 4
    skill = next(s for s in sig["tags"] if s["name"] == "技術継承の属人化")
    assert next(x for x in skill["sources"] if x["post_id"] == "P-HEAR")["unconfirmed"] is True
    assert all(not x["unconfirmed"] for s in sig["tags"] for x in s["sources"] if x["post_id"] != "P-HEAR")  # 過去の記録に誤って付かない
    assert "未確認" in sig["reason"]
    assert r["next_actions"]["questions"][0].startswith("雑談などで聞いた未確認の話を確かめる")


def test_plain_fact_is_not_marked_unconfirmed():
    import tsumugu
    post = tsumugu.new_post("C001", None, "E001", "2026-09-15", "工場長の斎藤さんが来春で退職されると社長から伺った。", post_id="P-FACT")
    t = next(x for x in tsumugu.extract(post, use_llm=False)["formal"] if x["tag"] == "T02")
    assert t["origin"] == "report"


def test_access_scope_limits_visible_companies():
    import database as db
    assert db.visible_company_ids("E001") == {"C001"}                            # 法人担当＝現在の担当先だけ
    assert len(db.visible_company_ids("E004")) == 10                             # 支店長＝自支店の全担当先
    assert "C002" in db.visible_company_ids("E007")                              # 本部＝相談を受けた企業


def test_consultation_opens_the_company_to_the_consulted_person():
    import database as db
    assert "C001" not in db.visible_company_ids("E002")
    db.insert_consultation("E001", "E002", "C001", "カナイ精工の事業承継について", at="2026-09-15")
    assert "C001" in db.visible_company_ids("E002")                              # 見られない情報は、見られる人につなぐ
    assert any(c["company_id"] == "C001" for c in db.get_consultations_by(to_staff="E002"))


def test_candidate_tag_promotion_is_decided_by_a_person():
    import database as db
    db.set_candidate_status("海外展開への関心", "proposed")
    row = next(c for c in db.get_candidate_tags() if c["name"] == "海外展開への関心")
    assert row["status"] == "proposed"
    import tsumugu
    assert "海外展開への関心" not in tsumugu.RULES["formal"]                    # 承認しても正式タグは勝手に増えない


def test_same_report_is_not_registered_twice():
    """同じ企業・担当者・訪問日・本文の日報は二重に登録しない（出典が同じ記録で重ならない）"""
    import database as db
    import tsumugu
    text = "定例訪問。二重登録の確認用。"
    assert db.find_same_post("C001", "E001", "2026-09-20", text) is None
    tsumugu.run(tsumugu.new_post("C001", None, "E001", "2026-09-20", text), use_llm=False)
    first = db.find_same_post("C001", "E001", "2026-09-20", text)
    assert first
    assert db.find_same_post("C001", "E001", "2026-09-20", text + "　") == first      # 前後の空白は同じとみなす
    assert db.find_same_post("C001", "E001", "2026-09-21", text) is None               # 別の日は別の日報


def test_post_ids_keep_counting_after_9999():
    import database as db
    import tsumugu
    tsumugu.run(tsumugu.new_post("C004", None, "E005", "2026-09-22", "訪問。", post_id="P-9999"), use_llm=False)
    a = db.next_post_id()
    tsumugu.run(tsumugu.new_post("C004", None, "E005", "2026-09-22", "訪問。別件。", post_id=a), use_llm=False)
    assert int(db.next_post_id()[2:]) == int(a[2:]) + 1                                # 同じ ID を二度出さない（上書きしない）

