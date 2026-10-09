# =============================================================
# app.py — 見た目（W4 の app.py と同じ役割）。SFA（Salesforce）の画面を Streamlit で模す（企画書 v4 §14.5）
#   起動:  streamlit run app.py
#   事前:  python docs/convert_source_data.py → python database.py --reset → python crawler.py
#          → python -c "import tsumugu; tsumugu.retag_all()"   （DB が空なら起動時に自動で行う）
#
#   パイロット版の画面（ログイン中の行員の閲覧範囲＝access_scope で出し分ける。v4 §7.1・§12.3）
#     🏢 取引先（訪問前に読む）        … 法人担当・支店長・本部・部長
#     📝 日報（訪問後、登録すると反応） … 法人担当・支店長・部長
#     👀 対話の状況（支店長）           … 支店長・部長
#     🧭 本部（相談・候補タグ・判定基準）… 本部・部長
#     📊 パイロット評価・監査           … 支店長・本部・部長
#
#   「パッと見て分かる」ための約束（この 4 つを崩さない）
#     1. 情報は必ずカード（`card()`）に入れる。文字の羅列を画面に直接置かない
#     2. 取引先・反応の状態と数字は `status_bar()` で 1〜2 行に控えめに（主役は下のカード）。一覧の集計は `tiles()`
#     3. 1 行 ＝ 1 つのこと。見出し（太字）→ 中身 → 出典（小さい灰色）の順で必ず同じ形
#     4. 点数・危険度・ランキングは出さない（企画書 v4 §7.2・§7.3）。バッジは「点数」ではなく「今どの状態か」
#   処理は tsumugu.run() / tsumugu.company_state() に任せ、ここは「結果の dict を並べる」だけ。
# =============================================================
import importlib
import os
import re
from datetime import date
from html import escape

import streamlit as st

import database as db
import ranking
import tsumugu


def _reload_if_updated(*modules):
    """処理のファイル（database.py・ranking.py・tsumugu.py）が更新されていたら読み込み直す。
    Streamlit（特に Streamlit Cloud）は app.py だけを新しくして、import したファイルは古いまま動き続けることがあり、
    マージ後に「関数が無い」（AttributeError）になるため（変更記録 CH-45）。依存の順（database → ranking → tsumugu）に読み直す"""
    changed = False
    for m in modules:
        mtime = os.path.getmtime(m.__file__)
        # まだ記録が無い（古い app.py が読み込んだまま）か、ファイルが新しくなっていたら読み直す
        if changed or getattr(m, "_loaded_mtime", None) != mtime:
            importlib.reload(m)
            changed = True                     # 下の段が上の段を import しているので、1 つ読み直したら後ろも読み直す
        m._loaded_mtime = mtime


_reload_if_updated(db, ranking, tsumugu)

st.set_page_config(page_title="ツムグ｜SFA の中の表示領域", page_icon="🧵", layout="wide")
db.init_db()
if not db.get_companies():                       # DB が空なら合成データを入れ、公開ナレッジを集め、タグを付ける
    db.ingest(reset=True)
    try:
        import crawler
        crawler.crawl_all()
    except Exception:
        pass                                     # ネットが無くても行内ナレッジだけで動く
    tsumugu.retag_all()

TODAY = date(2026, 9, 15)                        # デモの「今日」（合成データの想定）
FB = tsumugu.RULES["feedback_kinds"]             # {"started": "対話を始めた", ...}
THRESHOLD = tsumugu.RULES.get("candidate_promote_threshold", 3)
STAGE = {"fired": "支援の検討が挙がっている", "started": "対話が始まっている", "hq_consulted": "本部に相談中",
         "deal": "案件になった", "quiet": "特段の動きなし", "skipped": "今回は見送り"}
STAGE_ORDER = ["fired", "started", "hq_consulted", "deal", "quiet", "skipped"]
# 反応の 4 層＝状態バッジ（色は状態を表すだけで、危険度の段階ではない）
BADGE = {1: ("予兆は出ていません", "#5B6B7F", "#EEF0F3"), 2: ("過去に関連する記録があります", "#2F5D8A", "#E8EEF6"),
         3: ("これまでにない変化が続いています", "#1F6B5F", "#E2F3EF"), 4: ("支援の検討が必要かもしれません", "#9A6410", "#FCF1DA")}
BADGE_NOTE = {1: "記録は蓄積しています", 2: "判定はしていません", 3: "正式な予兆ではありません", 4: "最終判断は担当者が行います"}
INK, SUB, LINE = "#1E2637", "#5B6B7F", "#E4E6EA"

# ロール（staff.access_scope）→ 呼び名と、開ける画面
P_COMPANY, P_REPORT, P_BRANCH, P_HQ, P_PILOT = "🏢 取引先（訪問前）", "📝 日報（訪問後）", "👀 対話の状況", "🧭 本部", "📊 パイロット評価・監査"
ROLE = {"assigned_companies": ("法人担当者", [P_COMPANY, P_REPORT]),
        "branch": ("支店長・上長", [P_BRANCH, P_COMPANY, P_REPORT, P_PILOT]),
        "consulted": ("本部専門部署", [P_HQ, P_COMPANY, P_PILOT]),
        "all": ("部長（全体）", [P_COMPANY, P_REPORT, P_BRANCH, P_HQ, P_PILOT])}
SCOPE_NOTE = {"assigned_companies": "現在の担当先（前任者の記録を含む）", "branch": "自支店の全担当先",
              "consulted": "相談を受けた企業", "all": "すべて"}

st.markdown(f"""<style>
div[data-testid="stVerticalBlock"] > div {{ margin-bottom: 2px; }}
.zone {{ border-top:2px dashed #2F5D8A; padding-top:10px; margin:22px 0 12px; color:#2F5D8A; font-weight:700; font-size:15px; }}
.sfa {{ background:#F3F3F3; border:1px solid #DDDBDA; border-radius:8px; padding:12px 16px; margin-bottom:6px; }}
.sfa .lb {{ font-size:11px; color:#706E6B; letter-spacing:.03em; }}
.sfa .nm {{ font-size:22px; font-weight:800; color:#181818; margin:2px 0 4px; }}
.sfa .fx {{ display:flex; flex-wrap:wrap; gap:4px 22px; font-size:13px; color:#3E3E3C; }}
.sfa .fx b {{ color:#706E6B; font-weight:600; margin-right:4px; }}


/* タブ：押せる「ボタン」に見えるように（選んでいるものは塗りつぶし、ほかは枠付き）。Streamlit 1.60 の stTabs の作りに合わせる */
.stTabs [role="tablist"] {{ gap:8px !important; flex-wrap:wrap; padding-bottom:4px; }}
.stTabs [role="tablist"]::after {{ display:none !important; }}
.stTabs .react-aria-SelectionIndicator {{ display:none !important; }}
.stTabs [data-testid="stTab"] {{ border:1px solid #C9D6E6 !important; border-radius:999px !important; padding:6px 16px !important;
    background:#fff !important; cursor:pointer; box-shadow:0 1px 2px rgba(30,38,55,.06); }}
.stTabs [data-testid="stTab"] p {{ font-size:13.5px !important; font-weight:700 !important; color:#2F5D8A !important; }}
.stTabs [data-testid="stTab"]:hover {{ background:#EEF3F9 !important; }}
.stTabs [data-testid="stTab"][aria-selected="true"] {{ background:#2F5D8A !important; border-color:#2F5D8A !important; }}
.stTabs [data-testid="stTab"][aria-selected="true"] p {{ color:#fff !important; }}
/* パイロット用の任意アンケート：反応の流れとは別の枠（点線・薄い背景・ラベル） */
.st-key-pilot_survey {{ border:1.5px dashed #B8B2D6; background:#F7F6FC; border-radius:12px; padding:14px 18px 12px; margin-top:28px; }}
.st-key-pilot_survey .sv-hd {{ display:flex; flex-wrap:wrap; align-items:center; gap:6px 10px; }}
.st-key-pilot_survey .sv-tag {{ font-size:11.5px; font-weight:700; color:#5B4FA0; background:#ECE9F8; border-radius:999px; padding:2px 10px; }}
.st-key-pilot_survey .sv-q {{ font-size:15px; font-weight:800; color:{INK}; }}
.st-key-pilot_survey .sv-nt {{ font-size:11.5px; color:{SUB}; margin:4px 0 8px; }}
.st-key-pilot_survey button p {{ font-size:13px; }}
/* 予兆ごとのまとめ（取引先・訪問前） */
:is(.card, .st-key-signal_chips) .dg-st {{ display:flex; flex-wrap:wrap; align-items:center; gap:2px 0; padding:2px 0 0; }}
/* 予兆のチップ（押すと絞り込み）：カードの見た目に揃える */
.st-key-signal_chips {{ border:1px solid {LINE}; border-radius:12px; padding:16px 18px 10px; margin-bottom:14px; background:#fff; }}
.st-key-signal_chips .hd {{ font-size:15px; font-weight:800; color:{INK}; margin-bottom:4px; }}
.st-key-signal_chips .note {{ font-size:11px; color:{SUB}; margin-bottom:6px; }}
.st-key-signal_chips .dg-st {{ display:flex; flex-wrap:wrap; gap:2px 0; }}
.st-key-signal_chips .dg-lg {{ font-size:10.5px; color:{SUB}; padding:2px 0 8px; border-bottom:1px solid #F1F2F4; }}
.st-key-signal_chips [data-testid="stButtonGroup"] button {{ background:#FCF1DA; border:1px solid #F0DDB5; border-radius:999px; cursor:pointer; }}
.st-key-signal_chips [data-testid="stButtonGroup"] button p {{ color:#8A5A12; font-weight:700; font-size:13px; }}
.st-key-signal_chips [data-testid="stButtonGroup"] button:hover {{ background:#F8E6BF; }}
.st-key-signal_chips [data-testid="stButtonGroup"] button[aria-pressed="true"] {{ background:#9A6410 !important; border-color:#9A6410 !important; }}
.st-key-signal_chips [data-testid="stButtonGroup"] button[aria-pressed="true"] p {{ color:#fff !important; }}
:is(.card, .st-key-signal_chips) .dg-flt {{ font-size:12px; font-weight:700; color:#8A5A12; background:#FFF6E3; border-radius:8px; padding:6px 10px; margin-bottom:4px; }}
:is(.card, .st-key-signal_chips) .dg-flt span {{ font-weight:500; color:{SUB}; }}
:is(.card, .st-key-signal_chips) .dg-lg {{ font-size:10.5px; color:{SUB}; padding:4px 0 6px; border-bottom:1px solid #F1F2F4; }}
:is(.card, .st-key-signal_chips) .dg {{ padding:10px 0; border-top:1px solid #F1F2F4; }}
.dg-rec .note + .dg, .dg-rec .dg-flt + .dg {{ border-top:none; }}
.dg-rec .dg-l.dg {{ padding:10px 0; margin-top:0; }}
:is(.card, .st-key-signal_chips) .dg-h {{ display:flex; flex-wrap:wrap; align-items:baseline; gap:2px 10px; }}
:is(.card, .st-key-signal_chips) .dg-n {{ font-size:14.5px; font-weight:800; color:#8A5A12; }}
:is(.card, .st-key-signal_chips) .dg-w {{ font-size:11.5px; color:{SUB}; }}
:is(.card, .st-key-signal_chips) .dg-q {{ font-size:13.5px; color:{INK}; line-height:1.7; }}
:is(.card, .st-key-signal_chips) .dg-l {{ display:grid; grid-template-columns:11em 1fr; gap:0 10px; align-items:baseline; margin-top:6px; padding-left:14px; }}
@media (max-width: 640px) {{ :is(.card, .st-key-signal_chips) .dg-l {{ grid-template-columns:1fr; }} }}
:is(.card, .st-key-signal_chips) .dg-wh {{ font-size:11.5px; color:{SUB}; white-space:nowrap; }}
:is(.card, .st-key-signal_chips) .dg-l .dg-q b {{ color:{INK}; font-weight:700; background:#FFF6E3; }}
:is(.card, .st-key-signal_chips) .dg-l .uc {{ font-size:10.5px; color:#8A5A12; border:1px dashed #9A6410; border-radius:6px; padding:0 6px; margin-left:6px; white-space:nowrap; }}
:is(.card, .st-key-signal_chips) .dg-q .uc {{ font-size:10.5px; color:#8A5A12; border:1px dashed #9A6410; border-radius:6px; padding:0 6px; margin-left:6px; white-space:nowrap; }}
:is(.card, .st-key-signal_chips) .dg-old {{ font-size:11px; color:{SUB}; margin-top:3px; }}
/* AI が考えたヒント：記録（白いカード）と分ける */
.hint {{ background:#EEF1FB; border:1px solid #D5DCF3; border-radius:12px; padding:14px 18px 12px; margin-bottom:14px; }}
.hint-h {{ display:flex; flex-wrap:wrap; align-items:center; gap:4px 10px; }}
.hint-t {{ font-size:15px; font-weight:800; color:#2B3A78; }}
.hint-tag {{ font-size:11px; font-weight:700; color:#fff; background:#5363B8; border-radius:999px; padding:2px 10px; }}
.hint-n {{ font-size:11px; color:#56608C; margin:4px 0 10px; }}
.hq {{ display:flex; gap:8px; align-items:flex-start; background:#fff; border:1px solid #DDE3F6; border-radius:4px 14px 14px 14px;
       padding:8px 12px; margin:0 0 8px; font-size:14px; color:{INK}; line-height:1.6; }}
.hq-i {{ flex:0 0 auto; }}
/* 録音：押す場所が分かるように、マイクのボタンを大きな赤い丸に（変更記録 CH-48） */
.rec-need {{ background:#F4F5F7; border:1px dashed #C9CDD3; border-radius:8px; padding:10px 12px; font-size:13px; color:#55595F; }}
.rec-steps {{ font-size:12.5px; color:{INK}; line-height:1.7; margin:2px 0 8px; }}
.rec-steps b {{ color:#B3261E; }}
.st-key-rec_box [data-testid="stAudioInput"] > div {{ border:2px solid #E3A6A1; background:#FFF6F5; border-radius:12px; min-height:76px; align-items:center; }}
.st-key-rec_box [data-testid="stAudioInputActionButton"] {{ width:54px; height:54px; border-radius:50%; background:#D93025; color:#fff;
       box-shadow:0 2px 6px rgba(217,48,37,.35); }}
.st-key-rec_box [data-testid="stAudioInputActionButton"]:hover {{ background:#B3261E; color:#fff; }}
.st-key-rec_box [data-testid="stAudioInputActionButton"] svg {{ width:28px; height:28px; }}
.st-key-rec_box [data-testid="stAudioInputActionButton"][aria-label*="Stop"] {{ background:#3C4043; box-shadow:none; }}
/* 取り込んだ面談の記録を日報の型に整えた案（変更記録 CH-48） */
.ir {{ display:flex; gap:10px; background:#fff; border:1px solid #DDE3F6; border-radius:8px; padding:7px 12px; margin:0 0 6px;
       font-size:14px; color:{INK}; line-height:1.6; }}
.ir b {{ flex:0 0 9.5em; color:#2B3A78; font-size:12.5px; padding-top:2px; }}
.sv {{ display:flex; flex-direction:column; gap:2px; border-left:3px solid #C9A227; background:#FBF5E0; border-radius:0 6px 6px 0;
       padding:6px 10px; margin:8px 0 4px; }}
.sv-l {{ font-size:12px; font-weight:700; color:#806300; }}
.sv-t {{ font-size:13.5px; color:{INK}; }}
.sv-n {{ font-size:11.5px; color:#6B6B6B; }}
/* 面談メモ履歴：1 件 1 行、押すと全文 */
details.ml {{ border-top:1px solid #F1F2F4; }}
details.ml:first-of-type {{ border-top:none; }}
details.ml summary {{ list-style:none; cursor:pointer; display:flex; flex-wrap:wrap; align-items:center; gap:2px 10px; padding:8px 4px; }}
details.ml summary::-webkit-details-marker {{ display:none; }}
details.ml summary:hover {{ background:#F7F8FA; }}
details.ml summary::before {{ content:"▸"; color:{SUB}; font-size:11px; }}
details.ml[open] summary::before {{ content:"▾"; }}
.ml-d {{ font-size:12.5px; font-weight:700; color:{INK}; white-space:nowrap; }}
.ml-a {{ font-size:12px; color:{SUB}; white-space:nowrap; }}
.ml-t {{ font-size:13.5px; color:{INK}; flex:1 1 200px; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
details.ml[open] .ml-t {{ visibility:hidden; }}
.ml-b {{ font-size:14px; color:{INK}; line-height:1.7; padding:2px 8px 10px 22px; }}
.ml-b .sub {{ font-size:11.5px; color:{SUB}; margin-top:4px; }}
.sec {{ display:flex; flex-wrap:wrap; align-items:center; gap:4px 10px; margin:26px 0 10px; padding-bottom:6px; border-bottom:1px solid {LINE}; }}
.sec .no {{ background:#2F5D8A; color:#fff; border-radius:999px; min-width:22px; height:22px; display:inline-flex; align-items:center;
            justify-content:center; font-size:12px; font-weight:800; }}
.sec .tt {{ font-size:16px; font-weight:800; color:{INK}; }}
.sec .sb {{ font-size:12px; color:{SUB}; }}
.legacy {{ background:#EEF6F1; border:1px solid #CFE6D8; border-left:6px solid #2E7D5B; border-radius:12px; padding:14px 18px 16px; margin:4px 0 16px; }}
.legacy .lh {{ display:flex; flex-wrap:wrap; align-items:baseline; gap:4px 12px; margin-bottom:10px; }}
.legacy .lh .t {{ font-size:17px; font-weight:800; color:#1F5E43; }}
.legacy .lh .n {{ font-size:12px; color:#3F6B57; }}
.legacy .grid {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(190px, 1fr)); gap:10px; }}
.legacy .it {{ background:#fff; border-radius:10px; padding:10px 14px; border:1px solid #DCEDE3; }}
.legacy .it .lb {{ font-size:11.5px; font-weight:700; color:#2E7D5B; }}
.legacy .it .hd2 {{ font-size:22px; font-weight:800; color:{INK}; line-height:1.3; margin:2px 0; }}
.legacy .it .dt {{ font-size:12px; color:{SUB}; line-height:1.5; }}
.legacy .it.wide {{ grid-column:span 2; }}
@media (max-width: 700px) {{ .legacy .it.wide {{ grid-column:auto; }} }}
.legacy .en {{ padding:6px 0; border-top:1px solid #E6F1EA; }}
.legacy .en:first-of-type {{ border-top:none; padding-top:2px; }}
.legacy .en .nm {{ font-size:16px; font-weight:800; color:{INK}; line-height:1.4; }}
.legacy .en .hl {{ font-size:12px; font-weight:700; color:#1F5E43; background:#E2F1E8; border-radius:999px; padding:1px 9px; margin-left:8px; }}
.legacy .en .uc {{ font-size:10.5px; color:#8A5A12; border:1px dashed #9A6410; border-radius:6px; padding:0 6px; margin-left:6px; }}
.legacy .ft {{ font-size:11px; color:#3F6B57; margin-top:8px; }}
.sum {{ border:1px solid {LINE}; border-radius:10px; background:#FAFBFC; padding:10px 16px 8px; margin:0 0 14px; }}
.sum .top {{ display:flex; flex-wrap:wrap; align-items:center; gap:4px 10px; padding-bottom:8px; border-bottom:1px solid #EDEFF2; }}
.sum .st {{ border-radius:999px; padding:3px 12px; font-size:13.5px; font-weight:800; }}
.sum .nt {{ font-size:12px; color:{INK}; }}
.sum .dc {{ font-size:10.5px; color:{SUB}; margin-left:auto; }}
.sum .grid {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(150px, 1fr)); gap:6px 0; padding-top:8px; }}
.sum .c {{ padding:0 14px; border-left:1px solid #EDEFF2; }}
.sum .c:first-child {{ padding-left:0; border-left:none; }}
.sum .c .k {{ font-size:11px; color:{SUB}; }}
.sum .c .v {{ font-size:16px; font-weight:800; color:{INK}; line-height:1.3; }}
.sum .c .s {{ font-size:10.5px; color:{SUB}; line-height:1.4; }}
.tiles {{ display:flex; gap:12px; align-items:stretch; margin:2px 0 6px; flex-wrap:wrap; }}
.tiles .t {{ flex:1 1 0; min-width:130px; background:#F4F6F8; border-radius:12px; padding:14px 16px;
             display:flex; flex-direction:column; justify-content:space-between; }}
.tiles .t .k {{ font-size:12px; font-weight:700; color:{SUB}; line-height:1.4; min-height:2.8em; }}
.tiles .t .v {{ font-size:27px; font-weight:800; color:{INK}; line-height:1.2; margin:6px 0 4px; }}
.tiles .t .s {{ font-size:11px; color:{SUB}; line-height:1.4; min-height:2.4em; }}

.card {{ border:1px solid {LINE}; border-radius:12px; padding:16px 18px; margin-bottom:14px; background:#fff; }}
.card .hd {{ font-size:15px; font-weight:800; color:{INK}; margin-bottom:4px; }}
.card .note {{ font-size:11px; color:{SUB}; margin-bottom:10px; }}
.card .row {{ padding:9px 0; border-top:1px solid #F1F2F4; }}
.card .row:first-of-type {{ border-top:none; padding-top:2px; }}
.card .row .ttl {{ font-size:14px; font-weight:700; color:{INK}; }}
.card .row .sub {{ font-size:11.5px; color:{SUB}; margin-top:3px; line-height:1.6; }}
.card .row .body {{ font-size:14px; color:{INK}; margin-top:3px; line-height:1.7; }}
.card ol {{ margin:0; padding-left:20px; }}
.card ol li {{ font-size:14px; line-height:1.7; margin:7px 0; }}

.chip {{ display:inline-block; border-radius:999px; padding:3px 11px; margin:0 6px 6px 0; font-size:13px; font-weight:700; }}
.chip.s {{ font-size:11px; padding:2px 9px; margin:4px 5px 0 0; }}
.src {{ display:inline-block; background:#F4F6F8; color:{SUB}; border-radius:6px; padding:1px 7px; margin:3px 5px 0 0; font-size:11px; }}
.who {{ font-size:14px; font-weight:700; color:{INK}; }}
.why {{ font-size:11.5px; color:{SUB}; line-height:1.6; }}
</style>""", unsafe_allow_html=True)


# ── 部品 ────────────────────────────────────────────────────
def zone(title):
    st.markdown(f"<div class='zone'>〰 ツムグ　{title}</div>", unsafe_allow_html=True)


def sfa_header(label, name, fields):
    """SFA（Salesforce）のレコードヘッダを模した灰色の帯。ここは「これまで通り」の領域"""
    fx = "".join(f"<span><b>{escape(k)}</b>{escape(str(v))}</span>" for k, v in fields)
    st.markdown(f"<div class='sfa'><div class='lb'>SFA の領域（これまで通り）｜{escape(label)}</div>"
                f"<div class='nm'>{escape(name)}</div><div class='fx'>{fx}</div></div>", unsafe_allow_html=True)


def section(no, title, sub=""):
    """反応の中の「まとまり」の見出し（番号・名前・一行の説明）"""
    st.markdown(f"<div class='sec'><span class='no'>{no}</span><span class='tt'>{escape(title)}</span>"
                f"<span class='sb'>{escape(sub)}</span></div>", unsafe_allow_html=True)


def status_bar(state, items, note=""):
    """状態（反応の 4 層）と数字を 1 枚の薄いパネルに控えめにまとめる（主役は下のカード）
    1 行目＝状態ラベル＋注記、2 行目＝数字を同じ幅の欄に区切って並べる。items = [(見出し, 数字, 補足), ...]"""
    label, fg, bg = BADGE[state]
    note = note or BADGE_NOTE[state]
    cells = "".join(f"<div class='c'><div class='k'>{escape(k)}</div><div class='v'>{escape(str(v))}</div>"
                    f"<div class='s'>{escape(sub) if sub else '&nbsp;'}</div></div>" for k, v, sub in items)
    st.markdown(f"<div class='sum'><div class='top'><span class='st' style='background:{bg};color:{fg}'>{label}</span>"
                f"<span class='nt'>{escape(note)}</span><span class='dc'>支援機会シグナル（危険度の点数ではありません）</span></div>"
                f"<div class='grid'>{cells}</div></div>", unsafe_allow_html=True)


def tiles(items, big=False):
    """items = [(見出し, 数字, 補足), ...] を 1 行の HTML で出す（高さが揃う）。big=True は見出しを大きく太く"""
    ks = "font-size:14px;color:#1E2637" if big else ""
    cells = "".join(f"<div class='t'><div class='k' style='{ks}'>{escape(k)}</div><div class='v'>{escape(str(v))}</div>"
                    f"<div class='s'>{escape(s)}</div></div>" for k, v, s in items)
    st.markdown(f"<div class='tiles'>{cells}</div>", unsafe_allow_html=True)


def card(title, rows_html, note="", accent=""):
    """カード 1 枚。rows_html は row() で作った行の並び"""
    style = f" style='border-left:5px solid {accent}'" if accent else ""
    st.markdown(f"<div class='card'{style}>{('<div class=hd>' + escape(title) + '</div>') if title else ''}"
                f"{('<div class=note>' + escape(note) + '</div>') if note else ''}{rows_html}</div>",
                unsafe_allow_html=True)


def row(title, body="", sub="", chips_html=""):
    """1 行 ＝ 見出し（太字）→ 中身 → 出典（小さい灰色）"""
    return (f"<div class='row'><div class='ttl'>{escape(title)}</div>"
            f"{('<div class=body>' + escape(body) + '</div>') if body else ''}"
            f"{chips_html}"
            f"{('<div class=sub>' + escape(sub) + '</div>') if sub else ''}</div>")


def ym(d):
    return f"{d[:4]}年{int(d[5:7])}月"


def srcs(sources):
    """出典（年月・担当者）を小さな箱で並べる"""
    return "".join(f"<span class='src'>{escape(ym(x['date']))}・{escape(x['author'])}</span>" if not x.get("unconfirmed") else
                   f"<span class='src' style='background:#fff;border:1px dashed #9A6410;color:#8A5A12'>"
                   f"{escape(ym(x['date']))}・{escape(x['author'])}　未確認（雑談などで聞いた話）</span>" for x in sources)


def card_signals(sig):
    """重なった予兆（出典つき）。1 予兆＝1 行"""
    rows = "".join(row(s["name"], chips_html=srcs(s["sources"])) for s in sig["tags"])
    for x in sig["statics"]:
        rows += row(x["text"], chips_html="<span class='src'>顧客データ</span>")
    card("重なった予兆", rows, "それぞれ、どの記録のいつの記述かを示しています")


def legacy_band(items, note="この企業が地域で担っていること。承継の対話で、社長と一緒に大切にしたいものです"):
    """次の世代につなぎたいもの。企画の芯なので、前向きな色（緑）の帯で目立たせる（警告の色は使わない）
    items＝tsumugu.legacy_items のまとまり。雇用・取引は数字を大きく、技術・ノウハウは横長のタイルに複数並べる（名前・担い手・出どころ）"""
    if not items:
        return
    cells, by = "", set()
    for x in items:
        if x.get("entries"):
            rows = ""
            for e in x["entries"]:
                by.add(e.get("by"))
                holder = (f"<span class='hl'>担い手：{escape(e['holder'])}</span>") if e.get("holder") else ""
                unc = "<span class='uc'>未確認</span>" if e.get("unconfirmed") else ""
                rows += (f"<div class='en'><div class='nm'>● {escape(e['name'])}{holder}</div>"
                         f"<div class='dt'>{escape(e['detail'] or '')}{'　' if e['detail'] else ''}"
                         f"<span style='opacity:.75'>（{escape(e['source'])}）</span>{unc}</div></div>")
            cells += (f"<div class='it wide'><div class='lb'>{escape(x['label'])}（{len(x['entries'])}件）</div>{rows}</div>")
        else:
            cells += (f"<div class='it'><div class='lb'>{escape(x['label'])}</div><div class='hd2'>{escape(x['head'])}</div>"
                      f"<div class='dt'>{escape(x['detail'] or '')}{'　' if x['detail'] else ''}"
                      f"<span style='opacity:.75'>（{escape(x['source'])}）</span></div></div>")
    foot = ""
    if "llm-sim" in by:
        foot = "<div class='ft'>技術名と担い手は、AI が日報から取り出したものです（このデモでは、あらかじめ用意した結果で AI の処理を模擬しています）</div>"
    elif "llm" in by:
        foot = "<div class='ft'>技術名と担い手は、AI が日報から取り出したものです。元の記述と出どころで確かめられます</div>"
    st.markdown(f"<div class='legacy'><div class='lh'><span class='t'>🌱 次の世代につなぎたいもの</span>"
                f"<span class='n'>{escape(note)}</span></div><div class='grid'>{cells}</div>{foot}</div>", unsafe_allow_html=True)


def card_questions(questions, title="お客さまとの会話のヒント",
                   note="機会があれば、社長や社員の方に。記録から AI が考えた例です。聞くかどうか、何を聞くかは担当者が決めます"):
    """AI が考えた会話のヒント。記録（白いカード）とは見た目を分ける：藍色の背景・「AI のヒント」の札・吹き出し（変更記録 CH-40）"""
    if not questions:
        return
    items = "".join(f"<div class='hq'><span class='hq-i'>💬</span><span>{escape(q)}</span></div>" for q in questions)
    st.markdown(f"<div class='hint'><div class='hint-h'><span class='hint-t'>{escape(title)}</span>"
                f"<span class='hint-tag'>✨ AI のヒント</span></div><div class='hint-n'>{escape(note)}</div>{items}</div>",
                unsafe_allow_html=True)


PUBLIC_KIND = {"option": "公的な支援制度", "knowhow": "手引き・Q&A", "law": "法律・税制"}


def card_cases(knowledge, current_tags=(), title="社内の支援事例"):
    """社内の支援事例（全行で共有されている事例集）。1 件ずつ、経緯・結果・当時の予兆・支援した行員まで見せる"""
    cases = [k for k in knowledge["items"] if k["kind"] == "case"]
    if not cases:
        return
    now = set(current_tags)
    rows = ""
    for k in cases:
        who = "、".join(staff_by_id[x]["name"] for x in k["handled_by"] if x in staff_by_id)
        meta = (f"<span class='chip s' style='background:#E8EEF6;color:#2F5D8A'>{escape(k['branch'] or '')} {k['year'] or ''}</span>"
                f"<span class='chip s' style='background:#F4F6F8;color:{SUB}'>{escape(k['industry'] or '')}・{escape(k['size'] or '')}</span>"
                f"<span class='chip s' style='background:#F4F6F8;color:{SUB}'>{escape(k['id'])}</span>")
        sig = "".join(f"<span class='chip s' style='background:{'#FCF1DA' if t in now else '#fff'};color:#8A5A12;border:1px solid #F0DDB5'>"
                      f"{escape(t)}{'（今回と共通）' if t in now else ''}</span>" for t in k["signals"])
        rows += (f"<div class='row'><div class='ttl'>{escape(k['title'])}</div><div>{meta}</div>"
                 f"<div class='body'>{escape(k['summary'] or '')}</div>"
                 f"<div class='body' style='font-size:13px'><b>結果</b>　{escape(k['outcome'] or '')}</div>"
                 f"<div class='sub'>当時の予兆　{sig}</div>"
                 f"<div class='sub'>支援した行員：{escape(who)}（相談できる人にも出ています）</div></div>")
    card(title, rows, "行内の事例集（全行で共有）から、似た状況の事例を選んでいます")


def card_knowhow(knowledge, title="現場の知恵"):
    """行員が実際の支援で得た気づき（行内のナレッジ共有。書き手の経験年数は問わない）"""
    items = [k for k in knowledge["items"] if k["kind"] == "knowhow"]
    if items:
        card(title, "".join(row(k["title"], body=k["summary"] or "",
                                sub="、".join(f"{staff_by_id[x]['name']}（{staff_by_id[x]['dept']}）" for x in k["handled_by"] if x in staff_by_id))
                            for k in items), "行員が実際の支援で得た気づき（行内で共有）")


def card_public(refs, title="関連する公的な支援制度・法令"):
    """公的な支援制度・法律／税制（crawler.py で収集した公的機関のページ）"""
    if not refs:
        return
    rows = "".join(f"<div class='row'><span class='chip s' style='background:#F4F6F8;color:{SUB}'>{PUBLIC_KIND.get(k['kind'], k['kind'])}</span>"
                   f"<div class='ttl'><a href='{escape(k['url'])}' target='_blank'>{escape(k['title'])}</a></div>"
                   f"<div class='sub'>{escape(k['url'])}</div></div>" for k in refs)
    card(title, rows,
         "公的機関のページです（crawler.py で収集）。お客さまへの案内や、制度を確かめるときの参考に")


def _by_latest(tags):
    return sorted(tags, key=lambda t: max(x["date"] for x in t["sources"]), reverse=True)


def card_signals_with_records(tags, statics, years, posts, key):
    """「これまでの記録に出てきた予兆」1 枚：上にチップ（ひと目で把握・押すと絞り込み）、下に予兆ごとの記録（変更記録 CH-34・36・37）
    面談メモ由来の予兆は押せるチップ（st.pills）。押すとすぐ下の記録がその予兆だけになる"""
    ordered = _by_latest(tags)
    label = {t["name"]: f"● {t['name']}" for t in ordered}     # 時期は下の記録で見られるので、チップは名前だけ（CH-38）
    with st.container(key="signal_chips"):
        st.markdown(f"<div class='hd'>これまでの記録に出てきた予兆（過去{years}年）</div>"
                    f"<div class='note'>今も続いているとは限りません。判定ではありません。予兆を押すと、その予兆の記録だけに絞り込めます</div>",
                    unsafe_allow_html=True)
        picked = []
        if ordered:
            picked = st.pills("予兆で絞り込む", [t["name"] for t in ordered], selection_mode="multi", key=key,
                              format_func=lambda n: label[n], label_visibility="collapsed") or []
        else:
            st.markdown(f"<div style='color:{SUB};font-size:13px'>これまでの記録に、予兆に関わるものはありません</div>", unsafe_allow_html=True)
        if statics:
            st.markdown("<div class='dg-st'>" + "".join(f"<span class='chip' style='background:#EEF0F3;color:#44506A'>◆ {escape(x['text'])}</span>"
                                                     for x in statics) + "</div>", unsafe_allow_html=True)
        st.markdown("<div class='dg-lg'>● 面談メモから（押すと絞り込み）　◆ 顧客データから</div>",
                    unsafe_allow_html=True)
        st.markdown(signal_records_html(tags, posts, picked), unsafe_allow_html=True)


def _with_bold(text, evs):
    """記録の本文を出し、予兆の根拠になった文を太字にする（一文だけだと前後の文脈が分からないため）。evs は根拠の文のリスト"""
    out = escape(text or "")
    for ev in dict.fromkeys(e for e in evs if e):
        e = escape(ev)
        out = out.replace(e, f"<b>{e}</b>", 1) if e in out else out
    return out or "".join(f"<b>{escape(e)}</b>" for e in evs if e)


def signal_records_html(tags, posts, picked=()):
    """予兆に関わる記録を 1 件ずつ新しい順に（同じ記録は 1 回だけ）。各記録に、その記録から拾った予兆のチップを付ける。
    チップで絞り込むと、選んだ予兆を含む記録だけ残る（予兆ごとの見出しで区切るのはやめた。変更記録 CH-41）"""
    text_of = {p["id"]: p["text"] for p in posts}
    recs = {}
    for t in tags:
        for x in t["sources"]:
            r = recs.setdefault(x["post_id"], {"date": x["date"], "author": x["author"], "tags": [], "ev": [], "unc": False})
            r["tags"].append(t["name"])
            r["ev"].append(x["evidence"])
            r["unc"] = r["unc"] or bool(x.get("unconfirmed"))
    rows = sorted(recs.items(), key=lambda kv: kv[1]["date"], reverse=True)
    shown = [(pid, r) for pid, r in rows if not picked or set(picked) & set(r["tags"])]
    html = ""
    if picked:
        html += (f"<div class='dg-flt'>絞り込み中：{escape('・'.join(picked))}（記録 {len(shown)} / {len(rows)} 件）"
                 f"<span>　上の予兆をもう一度押すと解除</span></div>")
    for pid, r in shown:
        chips = "".join(
            f"<span class='chip s' style='background:{'#9A6410' if n in picked else '#FCF1DA'};color:{'#fff' if n in picked else '#8A5A12'}'>● {escape(n)}</span>"
            for n in r["tags"])
        unc = "<span class='uc'>未確認（雑談などで聞いた話）</span>" if r["unc"] else ""
        html += (f"<div class='dg-l dg'><span class='dg-wh'>{escape(ym(r['date']))}・{escape(r['author'])}</span>"
                 f"<div><div class='dg-q'>{_with_bold(text_of.get(pid, ''), r['ev'])}{unc}</div><div>{chips}</div></div></div>")
    if not rows:
        html = f"<div style='color:{SUB};font-size:13px;padding:6px 0'>これまでの記録に、予兆に関わるものはありません</div>"
    return (f"<div class='dg-rec'><div class='note' style='margin:8px 0 2px'>予兆に関わる記録を新しい順に並べています。"
            f"太字は予兆の根拠になった文、下のチップはその記録から拾った予兆です</div>{html}</div>")


def _next_day(d):
    from datetime import timedelta
    return (date.fromisoformat(d) + timedelta(days=1)).isoformat()


def assignment_periods(assignments):
    """担当の移り変わりを期間に分ける（主担当・副担当が重なる企業もあるので、担当が変わるたびに区切る）
    → [{start, end(None=現在), staff[{name, dept}]}]（古い順）"""
    cuts = sorted({a["from_date"] for a in assignments} | {_next_day(a["to_date"]) for a in assignments if a["to_date"]})
    periods = []
    for i, start in enumerate(cuts):
        end = cuts[i + 1] if i + 1 < len(cuts) else None
        staff = [a for a in assignments if a["from_date"] <= start and (not a["to_date"] or a["to_date"] >= start)]
        if staff:
            periods.append({"start": start, "end": end, "staff": [{"name": a["staff_name"], "dept": a["dept"]} for a in staff]})
    return periods


def memo_line(p):
    """面談メモ 1 件 1 行：日付・書いた人・本文の先頭・予兆のチップ。押すと全文（HTML の details）"""
    tg = "".join(f"<span class='chip s' style='background:#FCF1DA;color:#8A5A12'>{escape(tsumugu.tag_name(t['tag_id']))}</span>"
                 for t in p["tags"] if t["tier"] == "formal")
    if any(t["tier"] == "formal" and t.get("origin") == "hearsay" for t in p["tags"]):
        tg += "<span class='chip s' style='background:#fff;border:1px dashed #9A6410;color:#8A5A12'>未確認の話を含む</span>"
    src = "過去日報（取り込み）" if "過去" in (p["source_label"] or "") else "SFA 日報"
    act = f"{p['activity']}｜" if p.get("activity") else ""
    return (f"<details class='ml'><summary><span class='ml-d'>{escape(p['posted_at'])}</span>"
            f"<span class='ml-a'>{escape(p['author_name'] or '')}</span><span class='ml-t'>{escape(p['text'])}</span>{tg}</summary>"
            f"<div class='ml-b'>{escape(p['text'])}<div class='sub'>{escape(act + src)}</div></div></details>")


def memo_history(posts, assignments, key):
    """面談メモ履歴（タブの中）。担当期間ごとに折りたたみ（今の担当だけ開く）、中は 1 件 1 行・押すと全文（変更記録 CH-42）。
    見出しが担当の移り変わりを兼ねる"""
    periods = assignment_periods(assignments)
    groups = []
    for pr in reversed(periods):
        ps = [p for p in posts if p["posted_at"] >= pr["start"] and (pr["end"] is None or p["posted_at"] < pr["end"])]
        groups.append((pr, ps))
    first = periods[0]["start"] if periods else None
    before = [p for p in posts if first and p["posted_at"] < first] if periods else list(posts)
    st.markdown(f"<div class='note' style='font-size:11px;color:{SUB};margin:2px 0 8px'>全 {len(posts)} 件。担当の移り変わりごとにまとめています。"
                f"行を押すと全文を開きます。担当者が代わっても記録は残ります</div>", unsafe_allow_html=True)
    for i, (pr, ps) in enumerate(groups):
        who = "・".join(f"{x['name']}（{x['dept']}）" for x in pr["staff"])
        span = f"{pr['start'][:7]} 〜 {'現在' if pr['end'] is None else _prev_month(pr['end'])}"
        label = f"{who}　{span}　記録 {len(ps)} 件" + ("　（現在の担当）" if pr["end"] is None else "")
        with st.expander(label, expanded=(i == 0)):
            st.markdown("".join(memo_line(p) for p in reversed(ps)) or f"<div class='sub'>この期間の記録はありません</div>",
                        unsafe_allow_html=True)
    if before:
        with st.expander(f"担当の記録がない期間（〜{first[:7] if first else ''}）　記録 {len(before)} 件"):
            st.markdown("".join(memo_line(p) for p in reversed(before)), unsafe_allow_html=True)


def _prev_month(d):
    """期間の終わり（次の期間の初日）→ その前日の年月"""
    from datetime import timedelta
    return (date.fromisoformat(d) - timedelta(days=1)).isoformat()[:7]


def card_memos(posts, title="面談メモ履歴", note="新しい順。担当者が代わっても記録は残ります"):
    rows, last_author = "", None
    for p in reversed(posts):
        if last_author and p["author_name"] != last_author:
            rows += (f"<div class='row' style='border-top:1px dashed #2F5D8A'><div class='sub' style='color:#2F5D8A;font-weight:700'>"
                     f"— 担当交代：{escape(p['author_name'] or '')} → {escape(last_author)} —</div></div>")
        last_author = p["author_name"]
        tg = "".join(f"<span class='chip s' style='background:#FCF1DA;color:#8A5A12'>{escape(tsumugu.tag_name(t['tag_id']))}</span>"
                     for t in p["tags"] if t["tier"] == "formal")
        src = "過去日報（取り込み）" if "過去" in (p["source_label"] or "") else "SFA 日報"
        if any(t["tier"] == "formal" and t.get("origin") == "hearsay" for t in p["tags"]):
            tg += "<span class='chip s' style='background:#fff;border:1px dashed #9A6410;color:#8A5A12'>未確認の話を含む</span>"
        act = f"{p['activity']}｜" if p.get("activity") else ""
        rows += row(f"{p['posted_at']}　{p['author_name']}", body=p["text"], sub=act + src, chips_html=tg)
    card(title, rows, note)


def people_block(people, company, me):
    """相談できる人。1 人ずつ「直接相談する／上司に相談する」のワンクリック（v4 §12.3）"""
    boss = staff_by_id.get((staff_by_id.get(me) or {}).get("reports_to") or "")
    st.markdown(f"<div class='card' style='margin-bottom:6px'><div class='hd'>相談できる人</div>"
                f"<div class='note'>過去の担当・支援した事例・相談を受けた履歴（関係の情報）だけで選んでいます。おすすめ順ではありません。"
                f"相談の中身は、システムではなく人が自分の権限と判断で伝えます</div></div>", unsafe_allow_html=True)
    persons = [p for p in people["targets"] + people["predecessors"] if p["staff_id"] != me]
    for i in range(0, len(persons), 2):                        # 2 人ずつ横に並べる
        for col, p in zip(st.columns(2, gap="medium"), persons[i:i + 2]):
            with col, st.container(border=True):
                _person(p, company, me, boss)


def _person(p, company, me, boss):
    """相談できる人 1 人分（名前・選んだ理由・ボタン 2 つ）"""
    st.markdown(f"<div class='who'>{escape(p['name'])}（{escape(p['dept'])}）</div><div class='why'>{escape(p['why'])}</div>",
                unsafe_allow_html=True)
    c2, c3 = st.columns(2, gap="small")
    theme = f"{company['name']}の事業承継について"
    if c2.button("直接相談する", key=f"direct_{company['id']}_{p['staff_id']}", width="stretch"):
        db.insert_consultation(me, p["staff_id"], company["id"], theme, at=TODAY.isoformat())
        db.log_audit(me, "consult_request", company["id"], f"to={p['staff_id']} direct")
        st.toast(f"{p['name']}さんへの相談を記録しました。{p['name']}さんは相談を受けた範囲として{company['name']}の記録を読めるようになります")
    if boss and c3.button("上司に相談する", key=f"boss_{company['id']}_{p['staff_id']}", width="stretch",
                          help=f"{boss['name']}さんに、{p['name']}さんへの顔つなぎを頼みます"):
        db.insert_consultation(me, boss["id"], company["id"], f"{p['name']}さん（{p['dept']}）への顔つなぎのお願い：{theme}",
                               at=TODAY.isoformat())
        db.log_audit(me, "consult_request", company["id"], f"to={boss['id']} via_boss target={p['staff_id']}")
        st.toast(f"上司の{boss['name']}さんに、{p['name']}さんへの顔つなぎを相談しました")


def card_other_contacts(people):
    extra = ""
    if people["dept_fallback"]:
        extra += row("相談先（部署）", body="、".join(people["dept_fallback"]))
    if people["external"]:
        extra += ("<div class='row'><div class='ttl'>専門家に確かめたいとき</div>"
                  + "".join(f"<div class='body'>・{escape(e['kind'])}<span style='font-size:11.5px;color:{SUB}'>　窓口：{escape(e['via'])}</span></div>"
                            for e in people["external"])
                  + "<div class='sub'>担当者自身が確かめたいときの相談先です。当行の提携先の専門家には、窓口の部署を通して相談できます"
                    "（特定の事務所はシステムからは出しません）</div></div>")
    if extra:
        card("そのほかの相談先", extra)


# ── サイドバー：ログイン中の行員（SFA のログインを模す）とデモの進め方 ───
staff = db.get_staff_all()
staff_by_id = {s["id"]: s for s in staff}
companies = db.get_companies()
comp_by_id = {c["id"]: c for c in companies}
DEMOS = [  # (ボタン, 行員, 画面, 取引先, 日付, 活動区分, 業務報告) ── demo_inputs.json と企画書 v4 §14.3 の順
    ("① 訪問前に読む（佐々木／カナイ精工）", "E001", P_COMPANY, "C001", "2026-09-15", None, ""),
    ("② 日報 → 予兆が立つ（佐々木／カナイ精工）", "E001", P_REPORT, "C001", "2026-09-15", "定例訪問",
     "定例訪問。受注状況を確認。前年並みとのこと。帰り際の雑談で、斎藤工場長が来春での退職を考えているらしいと伺った。"),
    ("③ 立たない（宮本／太田電装）", "E003", P_REPORT, "C002", "2026-09-16", "決算説明",
     "決算の説明を受けた。社長から、専務には技術を任せ、経営は外から人を招くことも考え始めたと聞いた。"),
    ("④ くり返し出ている話（阿部／ヤマト化成）", "E006", P_REPORT, "C009", "2026-09-17", "定例訪問",
     "定例訪問。社長がベトナムの展示会への出展を決めたとのこと。現地の通訳を探している。"),
    ("⑤ 支店長が対話の状況を見る（土屋）", "E004", P_BRANCH, None, None, None, ""),
    ("⑥ 本部が相談を受ける（林）", "E002", P_HQ, None, None, None, ""),
    ("⑦ 候補タグの昇格を判断する（大原）", "E007", P_HQ, None, None, None, ""),
]


def allowed_pages(staff_id):
    return ROLE.get((staff_by_id.get(staff_id) or {}).get("access_scope"), ROLE["assigned_companies"])[1]


def on_me_change():
    pages = allowed_pages(st.session_state["me"])
    if st.session_state.get("page") not in pages:
        st.session_state["page"] = pages[0]
    st.session_state.pop("result", None)


def run_demo(i):
    _, me, page, cid, day, activity, text = DEMOS[i]
    st.session_state["me"] = me
    st.session_state["page"] = page
    st.session_state.pop("result", None)
    if cid:
        st.session_state["co_company"] = cid
        st.session_state["rp_company"] = cid
    if day:
        st.session_state["rp_date"] = date.fromisoformat(day)
    if activity:
        st.session_state["rp_activity"] = activity
    st.session_state["rp_text"] = text
    st.session_state.pop("intake", None)


def reset_all():
    db.ingest(reset=True)
    tsumugu.retag_all()
    tsumugu.reset_index()
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.session_state["flash"] = "データを初期化しました（合成データの状態に戻りました）"


st.session_state.setdefault("me", "E001")
st.session_state.setdefault("page", P_COMPANY)
st.session_state.setdefault("rp_date", TODAY)
st.session_state.setdefault("rp_text", "")

with st.sidebar:
    st.title("🧵 ツムグ")
    st.warning("個人の習作です（議論のたたき台）。チームで決まった仕様ではありません", icon="✏️")
    st.caption("Salesforce（SFA）の画面の中に置く表示領域を模したものです。灰色の帯が SFA、点線から下がツムグの領域です")
    ids = [s["id"] for s in staff]
    st.selectbox("ログイン中の行員（SFA のログインを模擬）", ids, key="me", on_change=on_me_change,
                 format_func=lambda i: f"{staff_by_id[i]['name']}（{staff_by_id[i]['dept']}・{staff_by_id[i]['role']}）")
    me = st.session_state["me"]
    me_s = staff_by_id[me]
    role_name = ROLE.get(me_s["access_scope"], ROLE["assigned_companies"])[0]
    visible = db.visible_company_ids(me)
    st.markdown(f"**ロール**：{role_name}  \n**見られる範囲**：{SCOPE_NOTE.get(me_s['access_scope'], '')}（{len(visible)} 社）")
    st.caption("閲覧範囲はツムグ側で判定します（認証は SFA、認可はツムグ）")

    with st.expander("▶ デモの進め方（今日＝2026-09-15）", expanded=True):
        for i, d in enumerate(DEMOS):
            st.button(d[0], key=f"demo_{i}", on_click=run_demo, args=(i,), width="stretch")
        st.caption("②〜④ は日報が書かれた状態で開きます。「SFA に登録する」を押してください")

    st.divider()
    st.caption("LLM: " + ("使用（OpenAI）" if tsumugu.llm_available() else "未設定 → 辞書＋テンプレで動作"))
    st.caption(f"公開ナレッジ: {db.count_knowledge('public')} 件（crawler.py）／行内ナレッジ: {db.count_knowledge('internal')} 件")
    st.info("日報の記録とツムグの反応は、人事評価には使いません。\n\n融資判断・信用格付には使いません。\n\nデータはすべて架空（合成）です。")
    st.button("🔄 データを初期化", on_click=reset_all, help="デモで登録した日報・相談・フィードバックを消して、合成データの状態に戻します")

if st.session_state.get("flash"):
    st.success(st.session_state.pop("flash"))

pages = allowed_pages(me)
if st.session_state.get("page") not in pages:
    st.session_state["page"] = pages[0]
page = st.segmented_control("画面", pages, key="page", label_visibility="collapsed") or pages[0]
vis_companies = [c for c in companies if c["id"] in visible]
vis_ids = [c["id"] for c in vis_companies]


def company_select(key, label="取引先"):
    """閲覧できる企業だけを選ばせる（見られない企業は候補にも出さない）"""
    if not vis_ids:
        return None
    if st.session_state.get(key) not in vis_ids:
        st.session_state[key] = vis_ids[0]
    return st.selectbox(label, vis_ids, key=key, format_func=lambda i: comp_by_id[i]["name"])


def log_view_once(action, target, detail=""):
    """同じ画面を開き直すたびに記録しないよう、内容が変わったときだけ監査ログに残す"""
    sig = f"{me}|{action}|{target}"
    if st.session_state.get("_last_view") != sig:
        st.session_state["_last_view"] = sig
        db.log_audit(me, action, target, detail)


def company_header(c):
    sfa_header("取引先", c["name"], [("業種", c["industry"]), ("従業員", f"{c['employees']}名"),
                                     ("代表", f"{c['owner_name']}（{c['owner_age']}歳）"), ("創業", f"{c['founded_year']}年"),
                                     ("後継者", c["successor_status"] or "—"), ("所在地", c["region"]),
                                     ("主担当", (db.current_assignee(c["id"]) or {}).get("name", "—"))])


# ── 画面1：取引先（訪問前に、企業の画面で読む。v4 フェーズ 1「読む」） ────────
def page_company():
    cid = company_select("co_company")
    if not cid:
        st.info("閲覧できる取引先はまだありません。相談を受けると、その企業の記録を読めるようになります（本部専門部署の閲覧範囲）")
        return
    c = comp_by_id[cid]
    company_header(c)
    log_view_once("view_company", cid)

    v = tsumugu.company_state(cid, as_of=TODAY.isoformat())
    posts = db.get_posts(cid)
    zone("この企業の状況（訪問前に読む）")
    note = "記録は蓄積しています。次に予兆が記録されると、支援の検討として提示します" if (v["state"] == 1 and v.get("ready")) else ""
    counted = [x for x in v["statics"] if x["counts"]]
    authors = {p["author_name"] for p in posts}
    status_bar(v["state"], [
        ("気になる予兆", f"{len(v['tags']) + len(counted)}種", f"面談メモ {len(v['tags'])}・顧客データ {len(counted)}"),
        ("最終接点", f"{v['days_since']}日前" if v["days_since"] is not None else "—",
         f"{v['last_post']['posted_at']} {v['last_post']['author_name']}" if v["last_post"] else ""),
        ("似た支援事例", f"{len([k for k in v['knowledge']['items'] if k['kind'] == 'case'])}件", ""),
        ("面談メモ", f"{len(posts)}件", f"{len(authors)}人の担当者")], note)
    legacy_band(v["legacy"], "この企業が地域で担っていること。訪問のときも、ここを大切に話を聞けると良いものです")

    # 相談を受けた人（本部）には、誰から何の相談かを先に見せる
    mine = [x for x in db.get_consultations_by(to_staff=me) if x["company_id"] == cid]
    if mine:
        card("この企業について受けている相談",
             "".join(row(f"{x['at'] or ''}　{x['from_name'] or ''}さんから", body=x["theme"]) for x in mine),
             "相談を受けた範囲として、この企業の記録を読めます", accent="#2F5D8A")

    # 並び（変更記録 CH-37・CH-39）：予兆（チップで絞り込み ＋ 予兆ごとの記録を 1 枚に）→ お客さまとの会話のヒント → ほかの記録（タブ）
    card_signals_with_records(v["tags"], v["statics"], tsumugu.RULES["gate"]["window_months"] // 12, posts, key=f"sig_pick_{cid}")
    if v["next_actions"]:
        card_questions(v["next_actions"]["questions"])

    # 面談メモ履歴（担当期間ごとに折りたたみ）。顧客データは SFA の領域（上のヘッダー）と「次の世代につなぎたいもの」に
    # 出ているので、ツムグ側では並べ直さない（顧客データのタブはやめた。変更記録 CH-43）
    st.markdown(f"<div style='font-size:15px;font-weight:800;color:{INK};margin:14px 0 2px'>面談メモ履歴（{len(posts)} 件）</div>",
                unsafe_allow_html=True)
    memo_history(posts, db.get_assignments(cid), key=cid)

    st.caption("前任者たちの記録を読むことで、着任初日から担当企業の状況を把握できます（書かなくても得られる価値）。")


# ── 画面2：日報（訪問後、登録すると反応が返る。v4 フェーズ 2・3） ───────────
def show_reaction(r):
    """日報への反応。まとまりごとに番号付きの見出しで区切る
      反応④：①判定（理由・重なった予兆・次の世代につなぎたいもの） ②次にすること ③相談する ④参考にする
      反応①〜③：判定（と過去の関連記録）
      反応②〜④の下に、パイロット用の任意アンケート（この後どうしたか）を別枠で
      タグの確定や候補タグの昇格は運営側（本部）の判断なので、担当者の画面には出さない（変更記録 CH-25）"""
    sig, prof, post = r["signal"], r["profile"], r["post"]
    company = comp_by_id[prof["company_id"]]
    lvl = sig["reaction"]
    counted = [x for x in sig["statics"] if x["counts"]]
    no = iter(range(1, 10))
    zone("日報への反応")

    # ── 判定 ──
    if lvl == 4:
        n_unc = len({x["post_id"] for s in sig["tags"] for x in s["sources"] if x.get("unconfirmed")})
        items = [("重なった予兆", f"{len(sig['tags']) + len(counted)}種", f"面談メモ {len(sig['tags'])}・顧客データ {len(counted)}"),
                 ("根拠の記録", f"{len({x['post_id'] for s in sig['tags'] for x in s['sources']})}件",
                  f"{len({x['author'] for s in sig['tags'] for x in s['sources']})}人の担当者" + (f"・うち未確認 {n_unc}件" if n_unc else "")),
                 ("社内の事例", f"{len([k for k in r['knowledge']['items'] if k['kind'] == 'case'])}件",
                  f"現場の知恵 {len([k for k in r['knowledge']['items'] if k['kind'] == 'knowhow'])}件・公的な制度 {len(r['next_actions']['public_refs'])}件")]
        section(next(no), "判定", "なぜ「支援の検討」が挙がったか、この企業が地域で担っているもの。根拠の記録で確かめられます")
    else:
        ctx_authors = {cx["author"] for cx in sig["context"]}
        items = [("関連する過去の記録", f"{len(sig['context'])}件", f"{len(ctx_authors)}人の担当者" if ctx_authors else "今回が最初")]
        if lvl == 3:
            items.append(("くり返し出ている話", f"{len(sig['candidates'])}件", "予兆の判定には使っていません"))
        section(next(no), "判定", {1: "何も出ないのが通常の状態です", 2: "予兆の判定はしていません",
                                    3: "予兆の判定はしていません。くり返し出ている話をお知らせします"}[lvl])
    status_bar(lvl, items)                     # 処理時間は担当者には見せず、監査ログとパイロット評価で見る
    if lvl == 4:
        legacy_band(sig.get("legacy") or [])

    if lvl == 4:
        c1, c2 = st.columns([1.25, 1], gap="medium")
        with c1:
            lead = "  \n".join(x for x in sig["reason"].split("\n") if not x.startswith("- "))
            card("判定の理由", row("", body=lead,
                                   sub=f"AI が書いた文章です。事実かどうかは、右の出典に挙げた記録で確かめられます（生成: {sig['generated_by']}）"),
                 accent="#9A6410")
        with c2:
            card_signals(sig)

        section(next(no), "次にすること", "お客さまとの会話のヒント と、行内での準備（どちらも AI の提案。決めるのは担当者）")
        c1, c2 = st.columns(2, gap="medium")
        with c1:
            card_questions(r["next_actions"]["questions"])
        with c2:
            if r["next_actions"]["actions"]:
                card("行内での準備", "".join(row("・" + a) for a in r["next_actions"]["actions"]),
                     f"事例を調べる・行員に相談する（案）。根拠: {', '.join(r['next_actions']['grounded_on'])}")

        section(next(no), "相談する", "誰につなぐか（関係の情報だけで選んでいます）")
        people_block(r["people"], company, me)      # 相談できる人（2 列）
        card_other_contacts(r["people"])            # そのほかの相談先（その下に 1 枚）

        cases = [k for k in r["knowledge"]["items"] if k["kind"] == "case"]
        tips = [k for k in r["knowledge"]["items"] if k["kind"] == "knowhow"]
        refs = r["next_actions"]["public_refs"]
        section(next(no), "参考にする", "社内の事例・現場の知恵・公的な制度（ボタンで切り替え）")
        t1, t2, t3 = st.tabs([f"社内の支援事例（{len(cases)}）", f"現場の知恵（{len(tips)}）", f"公的な支援制度・法令（{len(refs)}）"])
        with t1:
            card_cases(r["knowledge"], [s["name"] for s in sig["tags"]] + [x["name"] for x in counted], title="")
        with t2:
            card_knowhow(r["knowledge"], title="")
        with t3:
            card_public(refs, title="")
    elif lvl == 3:
        rows = "".join(row(f"{c['name']}（{c['count']} 回目）",
                           body="同じような話が、これまでの記録にも何度か出ています。お客さまの変化を知る手がかりにしてください")
                       for c in sig["candidates"])
        card("くり返し出ている話", rows, "予兆の判定には使っていません", accent="#1F6B5F")
    elif lvl == 1:
        st.caption("この記録は、次に担当する人が読めるように残ります")

    if sig["context"] and lvl in (2, 3):
        card("過去に関連する記録があります",
             "".join(row(f"{ym(cx['date'])}　{cx['author']}", body=cx["text"],
                         chips_html="".join(f"<span class='chip s' style='background:#FCF1DA;color:#8A5A12'>{escape(s)}</span>" for s in cx["shared"]))
                     for cx in sig["context"]),
             "予兆の判定はしていません。同じ企業の、関連する過去の記録です（担当者が代わっても届きます）", accent="#2F5D8A")

    # ── この後どうしたか：パイロット用の任意アンケート。反応の流れ（①〜）とは別の枠にする（変更記録 CH-31） ──
    if lvl >= 2:
        with st.container(key="pilot_survey"):
            st.markdown("<div class='sv-hd'><span class='sv-tag'>パイロット用アンケート（任意）</span>"
                        "<span class='sv-q'>この後どうしましたか？</span></div>"
                        "<div class='sv-nt'>回答は任意です。1 回のクリックで記録され、支店長の「対話の状況」とパイロットの効果測定に使います。"
                        "人事評価には使いません</div>", unsafe_allow_html=True)
            cols = st.columns(4, gap="small")
            for col, (kind, label) in zip(cols, FB.items()):
                if col.button(label, key=f"fb_{kind}_{post['id']}", width="stretch"):
                    db.insert_feedback(prof["company_id"], me, kind)
                    db.log_audit(me, "feedback", prof["company_id"], kind)
                    st.toast(f"記録しました：{label}（ご協力ありがとうございます）")


ACTIVITIES = ["定例訪問", "決算説明", "資金のご相談", "着任・ご挨拶", "支店長同行", "その他"]


BY_LABEL = {"llm": "AI", "llm-sim": "AI（このデモでは用意した結果で模擬）", "rule": "ルールで項目に分けた（AI のキーが無いときの簡易版）"}
SOURCE_LABEL = {"rec": "🎤 録音", "audio": "🎞 音声・動画ファイル", "text": "📄 テキスト", "sample": "🧪 デモ用サンプル", "manual": "✍️ 書いた業務報告"}


# ── 面談の記録を取り込んで、日報の型に整える（変更記録 CH-48） ──────────────
#   どの入口から入っても intake（tsumugu.intake）を通り、確認の画面に出る。業務報告に入れるかは担当者が決める。
#   録音ファイル・書き起こしの全文は保存しない（セッションの中だけで使い、入れた文だけが SFA に登録される）
def _consented(company_id):
    if st.session_state.get(f"consent_{company_id}"):
        return True
    st.session_state["flash_warn"] = "先に「お客さまの了承を得て録音・記録しています」にチェックしてください"
    return False


def _run_intake(company_id, text, source):
    staff_names = [x["name"].split()[0] for x in staff]
    res = tsumugu.intake(text, company_id, staff_names)
    if not res:
        st.session_state["flash_warn"] = "取り込んだ記録に文がありませんでした"
        return
    for x in res["sensitive"]:
        x["decided"] = None
    st.session_state["intake"] = {"company_id": company_id, "source": source, **res}
    kinds = {}
    for x in res["sensitive"]:
        kinds[x["treatment"]] = kinds.get(x["treatment"], 0) + 1
    # 監査ログには「機微情報の印が付いた」事実だけを残し、中身は残さない
    db.log_audit(me, "intake", company_id, f"source={source} by={res['by']} sensitive={kinds or 0} dropped={len(res['dropped'])}")


def on_record(company_id):
    key = f"rp_audio_{company_id}_{st.session_state.get('audio_n', 0)}"
    audio = st.session_state.get(key)
    if not audio or not _consented(company_id):
        return
    res = tsumugu.transcribe(audio.getvalue(), company_id)
    st.session_state["audio_n"] = st.session_state.get("audio_n", 0) + 1       # 録音欄を空に戻す
    if not res:
        st.session_state["flash_warn"] = ("このデモでは、録音の文字起こしはカナイ精工・太田電装・ヤマト化成だけ模擬しています。"
                                          "AI（OpenAI）のキーを設定すると、どの取引先でも実際に文字起こしします")
        return
    _run_intake(company_id, res["text"], "rec")


def on_audio_file(company_id):
    key = f"rp_file_{company_id}_{st.session_state.get('file_n', 0)}"
    f = st.session_state.get(key)
    if not f or not _consented(company_id):
        return
    st.session_state["file_n"] = st.session_state.get("file_n", 0) + 1
    if f.size > tsumugu.AUDIO_LIMIT_MB * 1024 * 1024:
        st.session_state["flash_warn"] = (f"ファイルが大きすぎます（{f.size / 1024 / 1024:.0f}MB）。{tsumugu.AUDIO_LIMIT_MB}MB までです。"
                                          "Zoom・Teams の録画なら、音声だけのファイル（m4a）か、文字起こしのファイル（vtt）を使ってください")
        return
    res = tsumugu.transcribe(f.getvalue(), company_id, filename=f.name, meeting=True)
    if not res:
        st.session_state["flash_warn"] = ("このデモでは、ファイルの文字起こしはカナイ精工だけ模擬しています。"
                                          "AI（OpenAI）のキーを設定すると、実際に文字起こしします")
        return
    _run_intake(company_id, res["text"], "audio")


def on_text_file(company_id):
    key = f"rp_tfile_{company_id}_{st.session_state.get('tfile_n', 0)}"
    f = st.session_state.get(key)
    if not f:
        return
    st.session_state["tfile_n"] = st.session_state.get("tfile_n", 0) + 1
    _run_intake(company_id, tsumugu.read_transcript(f.name, f.getvalue()), "text")


def on_sample(company_id, path):
    _run_intake(company_id, path.read_text(encoding="utf-8"), "sample")


def on_tidy(company_id):
    """✨ AI で整える：書いた業務報告も、取り込みと同じ流れで日報の型に整えた案を出す。置き換えるかは担当者が決める"""
    text = st.session_state.get("rp_text", "").strip()
    if not text:
        st.session_state["flash_warn"] = "業務報告が空です。先に書くか、📥 から取り込んでください"
        return
    _run_intake(company_id, text, "manual")


def _intake_add(section, text):
    it = st.session_state.get("intake")
    if it:
        it["sections"].setdefault(section, []).append(text)
        it["report"] = tsumugu.format_report(it["sections"])


def restore_dropped(i):
    it = st.session_state.get("intake")
    hit = next((d for d in it["dropped"] if d["i"] == i), None) if it else None
    if hit:
        it["dropped"].remove(hit)
        _intake_add("その他", hit["text"])


def decide_sensitive(i, decision):
    """ask の文：include（日報に入れる）／exclude（外す）。route_hq の文：route（本部に直接伝える）"""
    it = st.session_state.get("intake")
    x = next((x for x in it["sensitive"] if x["i"] == i), None) if it else None
    if not x:
        return
    x["decided"] = decision
    if decision == "include":                                 # お客さまの言葉として、言い回しはそのまま残す
        _intake_add("気になった変化", f"「{x['text'].rstrip('。')}」との話があった。")
    if decision == "route":
        hq = tsumugu.SENSITIVE.get("hq_staff", "E007")
        db.insert_consultation(me, hq, it["company_id"], "（日報には残さないご相談）社長から直接伺ったお話について、お時間をいただきたいです",
                               at=TODAY.isoformat())
        db.log_audit(me, "consult_request", it["company_id"], f"to={hq} sensitive_route")      # 中身は残さない
    db.log_audit(me, "sensitive_decided", it["company_id"], f"{x['category']}:{decision}")


def apply_intake():
    it = st.session_state.pop("intake", None)
    if it:
        st.session_state["rp_text"] = it["report"]
        st.session_state["flash_info"] = "整えた案を業務報告に入れました。確認・修正してから登録してください（取り込んだ記録の全文は保存していません）"


def close_intake():
    st.session_state.pop("intake", None)


def intake_panel(company_id):
    it = st.session_state.get("intake")
    if not it or it["company_id"] != company_id:
        return
    with st.container(key="intake_panel"):
        body = "".join(f"<div class='ir'><b>{escape(n)}</b><span>{escape(''.join(it['sections'][n]))}</span></div>"
                       for n in tsumugu.TEMPLATE.get("order", []) if it["sections"].get(n))
        st.markdown(f"<div class='hint'><div class='hint-h'><span class='hint-t'>日報の型に整えた案</span><span class='hint-tag'>✨ AI のヒント</span></div>"
                    f"<div class='hint-n'>{escape(SOURCE_LABEL.get(it['source'], ''))} から。{escape(BY_LABEL[it['by']])}。"
                    f"要約はしていません。元の文を項目に並べ替えています。業務報告に入れるかはあなたが決めます</div>{body}</div>",
                    unsafe_allow_html=True)
        if it["shrink_warn"]:
            st.warning(f"元の記録より大幅に短くなっています（約 {int(it['ratio'] * 100)}%）。下の「外した文」を確かめてください")
        if it["sensitive"]:
            with st.container(border=True):
                st.markdown(f"**🔒 取り扱いに注意する内容（{len(it['sensitive'])} 件）— 日報からは外しています**")
                st.caption("AI と辞書で見つけたものです。見落としもありうるので、最後はあなたが確かめてください")
                for x in it["sensitive"]:
                    how = "辞書で検出" if x["method"] == "rule" else "AI が検出"
                    st.markdown(f"<div class='sv'><span class='sv-l'>{escape(x['label'])}</span>"
                                f"<span class='sv-t'>「{escape(x['text'])}」</span>"
                                f"<span class='sv-n'>{escape(tsumugu.SENSITIVE['treatments'][x['treatment']])}（{how}：{escape(x['reason'])}）</span></div>",
                                unsafe_allow_html=True)
                    if x["treatment"] == "route_hq":
                        if x["decided"] == "route":
                            st.caption("✅ 本部（事業承継支援室）に相談を送りました。内容は日報にもログにも残していません")
                        else:
                            st.button("本部（事業承継支援室）に直接伝える", key=f"sv_route_{x['i']}", on_click=decide_sensitive, args=(x["i"], "route"))
                    elif x["treatment"] == "ask":
                        if x["decided"]:
                            st.caption("✅ 日報に入れました（「気になった変化」）" if x["decided"] == "include" else "✅ 日報から外しました")
                        else:
                            k1, k2, _ = st.columns([1, 1, 3], gap="small")
                            k1.button("日報に入れる", key=f"sv_in_{x['i']}", on_click=decide_sensitive, args=(x["i"], "include"), width="stretch")
                            k2.button("外す", key=f"sv_out_{x['i']}", on_click=decide_sensitive, args=(x["i"], "exclude"), width="stretch")
        if it["dropped"]:
            with st.expander(f"整えるときに外した文（{len(it['dropped'])} 件）— 必要なら戻せます"):
                for d in it["dropped"]:
                    d1, d2 = st.columns([5, 1], gap="small", vertical_alignment="center")
                    d1.caption(d["text"])
                    d2.button("戻す", key=f"dr_{d['i']}", on_click=restore_dropped, args=(d["i"],), width="stretch")
        a1, a2, _ = st.columns([2, 1, 2.5], gap="small")
        a1.button("この内容で業務報告に入れる", on_click=apply_intake, type="primary", width="stretch")
        a2.button("閉じる", on_click=close_intake, width="stretch")


def on_save_draft(company_id):
    text = st.session_state.get("rp_text", "").strip()
    if not text:
        st.session_state["flash_warn"] = "業務報告が空なので、下書きは保存していません"
        return
    at = db.save_draft(company_id, me, text, st.session_state.get("rp_activity"), st.session_state.get(f"rp_contact_{company_id}"))
    st.session_state["flash_info"] = f"💾 下書きを保存しました（{at}）。次にこの取引先の日報を開くと、自動で読み込みます"


def register(company_id):
    """SFA に登録 → 裏でツムグが ②〜⑦ を走らせる。入力欄は空に戻す"""
    text = st.session_state.get("rp_text", "").strip()
    if not text:
        st.session_state["flash_warn"] = "業務報告を入力してください"
        return
    day = st.session_state["rp_date"].isoformat()
    same = db.find_same_post(company_id, me, day, text)
    if same:                                   # 二度押し・登録し直し：新しく記録せず、登録済みの日報への反応をもう一度見せる
        post = tsumugu.new_post(company_id, st.session_state.get(f"rp_contact_{company_id}"), me, day, text,
                                post_id=same, activity=st.session_state.get("rp_activity"))
        st.session_state["result"] = {**tsumugu.run(post, persist=False), "duplicate": True}
    else:
        post = tsumugu.new_post(company_id, st.session_state.get(f"rp_contact_{company_id}"), me, day, text,
                                activity=st.session_state.get("rp_activity"))
        st.session_state["result"] = tsumugu.run(post)
    db.delete_draft(company_id, me)
    st.session_state["rp_text"] = ""
    st.session_state.pop("intake", None)


def page_report():
    company_id = company_select("rp_company")
    if not company_id:
        st.info("日報を書ける取引先がありません")
        return
    c = comp_by_id[company_id]
    company_header(c)
    # 下書きがあれば、この取引先を開いたときに 1 回だけ読み込む（入力中の内容は上書きしない）
    loaded = f"draft_loaded_{company_id}_{me}"
    if not st.session_state.get(loaded):
        st.session_state[loaded] = True
        d = db.get_draft(company_id, me)
        if d and not st.session_state.get("rp_text", "").strip():
            st.session_state["rp_text"] = d["text"] or ""
            if d["activity"] in ACTIVITIES:
                st.session_state["rp_activity"] = d["activity"]
            st.session_state["flash_info"] = f"💾 保存していた下書きを読み込みました（{d['saved_at']}）"
    with st.container(border=True):                                  # SFA の領域：いつもの日報
        st.caption("SFA の領域（これまで通り）— 日報の新規作成")
        contacts = db.get_contacts(company_id)
        c1, c2, c3 = st.columns([2, 1.2, 1.2])
        c1.selectbox("面談相手", [k["id"] for k in contacts], key=f"rp_contact_{company_id}",
                     format_func=lambda i: next(f"{k['name']}（{k['role']}）" for k in contacts if k["id"] == i))
        c2.selectbox("活動区分", ACTIVITIES, key="rp_activity")
        c3.date_input("訪問日", key="rp_date")
        st.text_area("業務報告", key="rp_text", height=150,
                     placeholder="例：定例訪問。受注状況を確認。前年並みとのこと。設備更新の件はその後進展なし。")
        # 入力の補助：📥 取り込む／✨ AI で整える／💾 下書き保存（変更記録 CH-44・CH-48）
        b1, b2, b3, _ = st.columns([1.5, 1.2, 1.1, 1.2], gap="small")
        with b1.popover("📥 面談の記録を取り込む", width="stretch"):
            st.caption("録音・ファイル・文字起こしを取り込み、日報の型に整えた案を出します。録音ファイルと書き起こしの全文は保存しません")
            st.checkbox("お客さまの了承を得て、録音・記録しています", key=f"consent_{company_id}")
            ok = st.session_state.get(f"consent_{company_id}", False)
            t1, t2, t3, t4 = st.tabs(["🎤 録音", "🎞 音声・動画", "📄 テキスト", "🧪 サンプル"])
            need = "<div class='rec-need'>☝️ 上の「お客さまの了承を得て、録音・記録しています」にチェックを入れると使えます</div>"
            with t1:
                if not ok:
                    st.markdown(need, unsafe_allow_html=True)
                else:
                    st.markdown("<div class='rec-steps'><b>① 赤いマイクのボタンを押す</b>と録音が始まります　"
                                "<b>② 話し終えたら、もう一度押して</b>止めます　"
                                "<b>③</b> 止めると文字に起こし、日報の型に整えた案を出します</div>", unsafe_allow_html=True)
                    with st.container(key="rec_box"):
                        st.audio_input("録音", key=f"rp_audio_{company_id}_{st.session_state.get('audio_n', 0)}",
                                       on_change=on_record, args=(company_id,), label_visibility="collapsed")
            with t2:
                st.caption(f"Zoom・Teams などの録音・録画（{'・'.join(tsumugu.AUDIO_TYPES)}、{tsumugu.AUDIO_LIMIT_MB}MB まで）")
                if not ok:
                    st.markdown(need, unsafe_allow_html=True)
                else:
                    st.file_uploader("音声・動画ファイル", type=tsumugu.AUDIO_TYPES, label_visibility="collapsed",
                                     key=f"rp_file_{company_id}_{st.session_state.get('file_n', 0)}", on_change=on_audio_file, args=(company_id,))
            with t3:
                st.caption("文字起こしのファイル（txt・md、Zoom・Teams の vtt）")
                st.file_uploader("テキスト", type=tsumugu.TEXT_TYPES, label_visibility="collapsed",
                                 key=f"rp_tfile_{company_id}_{st.session_state.get('tfile_n', 0)}", on_change=on_text_file, args=(company_id,))
            with t4:
                samples = tsumugu.meeting_samples(company_id)
                st.caption("デモ用に用意した面談の書き起こし（架空）です" if samples else "この取引先のサンプルはありません（カナイ精工にあります）")
                for pth in samples:
                    st.button(f"{pth.suffix[1:]}：{pth.stem.split('_', 1)[1]}", key=f"smp_{pth.name}", on_click=on_sample,
                              args=(company_id, pth), width="stretch")
        b2.button("✨ AI で整える", on_click=on_tidy, args=(company_id,), width="stretch",
                  help="書いた業務報告を、日報の型に整えた案を出します。要約はしません。置き換えるかはあなたが決めます")
        b3.button("💾 下書き保存", on_click=on_save_draft, args=(company_id,), width="stretch")
        intake_panel(company_id)
        for k, fn in (("flash_warn", st.warning), ("flash_info", st.info)):
            if st.session_state.get(k):
                fn(st.session_state.pop(k))
        st.button("SFA に登録する", type="primary", on_click=register, args=(company_id,))
    r = st.session_state.get("result")
    if r and r["post"]["company_id"] == company_id:
        if r.get("duplicate"):
            st.info(f"同じ内容の日報は登録済みです（{r['post']['posted_at']}　{c['name']}）。新しくは登録せず、登録済みの日報への反応を表示しています")
        else:
            st.success(f"SFA に登録しました（模擬）　{r['post']['posted_at']}　{c['name']}")
        show_reaction(r)
    st.caption("多くの日報では何も出ません。ときどき「過去に関連する記録があります」、まれに「支援の検討が必要かもしれません」が出ます"
               "（オオカミ少年にならないための設計です）。")


# ── 画面3：対話の状況（支店長。危険度順に並べず、点数も出さない。v4 §7.2） ─────
def page_branch():
    sfa_header("支店の担当先一覧", f"{me_s['branch']}　担当先一覧", [("担当先", f"{len(vis_companies)}社"), ("基準日", TODAY.isoformat())])
    log_view_once("view_branch", me_s["branch"])
    zone("対話の状況")
    latest = {s["company_id"]: s for s in db.get_latest_signals()}
    fb = db.get_latest_feedback()
    groups = {k: [] for k in STAGE_ORDER}
    for c in vis_companies:
        s, f = latest.get(c["id"]), fb.get(c["id"])
        stage = f["kind"] if f else ("fired" if (s and s["fired"]) else "quiet")
        when = (f["at"] if f else (s["created_at"] if s else "")) or ""
        who = (db.current_assignee(c["id"]) or {}).get("name", "")
        groups[stage].append((when, c, who, s))
    tiles([(STAGE[k], f"{len(groups[k])}社", "") for k in STAGE_ORDER if k != "skipped"], big=True)
    st.caption("支援の進み具合ごとにまとめています。企業を危険度で順位付けしたり、点数を付けたりはしません。並びは更新の新しい順です。")

    asks = db.get_consultations_by(to_staff=me)
    if asks:
        card("部下からの相談（顔つなぎの依頼）",
             "".join(row(f"{x['from_name']}さん　{x['company_name'] or ''}", body=x["theme"], sub=x["at"] or "") for x in asks),
             "誰に、どこまで話すかは支店長が判断します。支店長の役割は「監視」ではなく「人につなぐこと」です", accent="#2F5D8A")

    for stage in STAGE_ORDER:
        rows = sorted(groups[stage], key=lambda x: x[0], reverse=True)
        if not rows:
            continue
        sub = "（記録は積み上がっています。予兆は出ていません）" if stage == "quiet" else ""
        st.markdown(f"<div style='margin-top:18px;font-size:15px;font-weight:800;color:{INK}'>{STAGE[stage]}"
                    f"<span style='font-weight:500;color:{SUB}'>（{len(rows)} 社）</span>"
                    f"<span style='font-weight:500;font-size:12px;color:{SUB}'>　{sub}</span></div>", unsafe_allow_html=True)
        if stage == "quiet":
            cells = "".join(f"<div class='t' style='background:#fff;border:1px solid {LINE};flex:0 1 200px'>"
                            f"<div class='v' style='font-size:15px'>{escape(c['name'])}</div><div class='s'>{escape(who)}</div></div>"
                            for _, c, who, _ in rows)
            st.markdown(f"<div class='tiles'>{cells}</div>", unsafe_allow_html=True)
            continue
        for when, c, who, s in rows:
            with st.expander(f"{c['name']}　｜　担当 {who}"):
                legacy_band(tsumugu.company_state(c["id"], as_of=TODAY.isoformat())["legacy"])
                st.caption("点数ではなく、この企業が地域で担っているものを表示しています。詳しくは取引先の画面で記録を読めます")


# ── 画面4：本部（相談を受ける・候補タグの昇格・判定基準。v4 §9.1・§9.2・§12.3） ────
def page_hq():
    sfa_header("本部", f"{me_s['dept']}　{me_s['name']}", [("役割", me_s["role"]), ("閲覧範囲", SCOPE_NOTE.get(me_s["access_scope"], ""))])
    zone("相談を受けている企業")
    asks = db.get_consultations_by(to_staff=me)
    if asks:
        card("受けている相談", "".join(row(f"{x['at'] or ''}　{x['from_name'] or ''}さんから", body=x["theme"],
                                           sub=(f"企業: {x['company_name']}（取引先の画面で記録を読めます）" if x["company_name"] else "事例についての相談"))
                                       for x in asks),
             "相談を受けた企業の記録は、相談を受けた人も読めます。見られない情報は、見られる人につなぐ（v4 §12.3）")
    else:
        st.caption("まだ相談は届いていません。担当者が日報の反応から「直接相談する」を押すと、ここに届きます")

    zone("候補タグ（新しい予兆パターンの候補）")
    st.caption(f"正式タグに当てはまらない変化に、AI が名前を付けて数えています。{THRESHOLD} 回を超えたものは、昇格するかを人が判断します。"
               "AI がタグ体系を勝手に書き換えることはありません")
    status_label = {"candidate": "判断待ち", "proposed": "昇格を承認（判定基準の改定待ち）", "rejected": "今回は見送り", "formal": "正式タグ"}
    for ctag in db.get_candidate_tags():
        n = db.count_candidate_records(ctag["name"])
        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 1.1, 1.1], vertical_alignment="center")
            ready = n >= THRESHOLD
            c1.markdown(f"<div class='who'>＋ {escape(tsumugu.tag_name(ctag['name']))}　<span style='font-weight:500;color:{SUB}'>{n} 件の記録</span></div>"
                        f"<div class='why'>初出 {ctag['first_seen']}／最新 {ctag['last_seen']}　｜　状態：{status_label.get(ctag['status'], ctag['status'])}"
                        f"{'' if ready else f'　｜　{THRESHOLD} 回に届いていません'}</div>", unsafe_allow_html=True)
            if ready and ctag["status"] == "candidate":
                if c2.button("昇格を承認", key=f"prom_{ctag['name']}", width="stretch"):
                    db.set_candidate_status(ctag["name"], "proposed")
                    db.log_audit(me, "tag_review", ctag["name"], "proposed")
                    st.rerun()
                if c3.button("今回は見送り", key=f"rej_{ctag['name']}", width="stretch"):
                    db.set_candidate_status(ctag["name"], "rejected")
                    db.log_audit(me, "tag_review", ctag["name"], "rejected")
                    st.rerun()
    wl = tsumugu.RULES.get("watchlist") or {}
    if wl:
        names = [v.get("name", k) if isinstance(v, dict) else str(v) for k, v in (wl.items() if isinstance(wl, dict) else enumerate(wl))]
        st.caption("昇格候補の見張りリスト（FB シート②の残りの語）：" + "、".join(names))

    zone("判定基準（事業承継支援室のベテランの言葉）")
    cr = tsumugu.RULES["criteria"]
    card("予兆の重み（数字ではなく言葉で持つ）", "<ol>" + "".join(f"<li>{escape(x)}</li>" for x in cr["sentences"]) + "</ol>",
         "LLM に渡す判定基準そのものです。業務側が日本語のまま書き換えられます（v4 §9.2）")
    card("提示するかどうか", row("", body=cr["closing"]))
    card("書き方の約束", "<ol>" + "".join(f"<li>{escape(x)}</li>" for x in cr["style"]) + "</ol>")


# ── 画面5：パイロット評価・監査（企業の点数ではなく、仕組みの効果を測る。v4 §13.4） ──
def page_pilot():
    zone("パイロットの効果測定")
    st.caption("企業を評価する数字ではありません。ツムグという仕組みが「読まれ」「つながり」「対話につながっているか」を測る指標です"
               "（企画書 v4 §13.4 続ける／直す／やめるの判断材料）")
    sigs = db.get_all_signals()
    fired_cos = {s["company_id"] for s in sigs if s["fired"]}
    fbs = db.get_all_feedback()
    moved = {f["company_id"] for f in fbs if f["kind"] in ("started", "hq_consulted", "deal")}
    connected = fired_cos & moved
    deals = {f["company_id"] for f in fbs if f["kind"] == "deal"}
    secs = [float(m.group(1)) for d in db.get_audit_details("search") for m in [re.search(r"sec=([\d.]+)", d or "")] if m]
    consults = db.count_audit("consult_request")
    tiles([("訪問前の閲覧", f"{db.count_audit('view_company')}回", "取引先の画面を開いた回数（読む価値）"),
           ("登録された日報", f"{len(sigs)}件", "パイロット期間に反応を返した件数"),
           ("支援の検討の提示", f"{len(fired_cos)}社", "予兆が立った企業"),
           ("支援への接続", f"{len(connected)}／{len(fired_cos)}社", "提示後に対話・本部相談・案件に進んだ"),
           ("早期相談（人につないだ）", f"{consults}件", "直接相談・上司経由の顔つなぎ"),
           ("案件化", f"{len(deals)}社", "承継手数料などにつながった"),
           ("反応までの時間", f"{(sum(secs) / len(secs)):.2f}秒" if secs else "—", "登録から反応まで（平均）")])

    ps = db.pilot_post_stats("2026-04-01")
    pct = lambda a, b: f"{round(100 * a / b)}%" if b else "—"
    tiles([("パイロット期間の日報", f"{ps['n']}件", "2026年4月以降（SFA に登録された日報）"),
           ("予兆につながる事実を含む日報", pct(ps["tagged"], ps["n"]), f"{ps['tagged']}件。業務報告に書かれた事実の積み重ねが予兆のもと"),
           ("伝聞（未確認）の話を含む日報", f"{ps['hearsay']}件", "「雑談で」「らしい」などの文から予兆を拾ったもの。次回の訪問で確かめる対象")])
    dist = {i: sum(1 for s in sigs if s["reaction"] == i) for i in (1, 2, 3, 4)}
    tiles([(f"反応 {i}：{BADGE[i][0]}", f"{dist[i]}件", BADGE_NOTE[i]) for i in (1, 2, 3, 4)])
    st.caption("記録の大半が ①（何も出ない）であることが正常な状態です。④ が多すぎる場合は判定基準を見直します")

    zone("監査ログ（誰が・いつ・何を見た／出した）")
    st.caption("目的外利用（融資判断への転用など）を後から確かめられるように、閲覧・検索・出力・相談をすべて記録しています（v4 §7.3）")
    names = {s["id"]: s["name"] for s in staff}
    st.dataframe([{"日時": a["at"], "行員": names.get(a["user"], a["user"]), "操作": a["action"], "対象": a["target"], "詳細": a["detail"]}
                  for a in db.get_audit_logs()], width="stretch", hide_index=True)
    with st.expander("公開ナレッジのクロール先（⓪ 収集）"):
        st.dataframe([{"ID": s["id"], "種類": s["kind"], "名前": s["label"], "URL": s["url"], "状態": s["status"], "取得": (s["last_crawled_at"] or "")[:16]}
                      for s in db.get_sources()], width="stretch", hide_index=True)


{P_COMPANY: page_company, P_REPORT: page_report, P_BRANCH: page_branch, P_HQ: page_hq, P_PILOT: page_pilot}[page]()
