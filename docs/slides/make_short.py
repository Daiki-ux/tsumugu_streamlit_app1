# docs/slides/make_short.py — 別案（ストーリー版）を発表時間（7 分・デモ込み）の長さに並べ替える
#   使い方: python make_short.py 別案.pptx 出力.pptx [story|compact]
#     story  ：別案（VARIANT=story・31 枚）を並べ替えるだけ
#     compact：7 分版（VARIANT=short・33 枚）。前段の背景などを 1 枚に作り直した統合スライドを本編に使う
#   ・本編 14 枚に絞り、外したスライドは消さずに「付録」の後ろへ回す（質疑で使う）
#   ・区切りのスライド（システムパート）を「付録」の区切りに書き換える
#   ・本編のノートの先頭に、話す時間の目安と累計を入れる
#   ・ページ番号を振り直す
#   並びは別案（merge_deck.py の出力・31 枚）の番号で指定する
import sys
from pptx import Presentation
from pptx.util import Emu

SRC, OUT = sys.argv[1], sys.argv[2]
MODE = sys.argv[3] if len(sys.argv) > 3 else "story"

# 本編：（別案での番号, 秒）
MAIN = [
    (1, 5),     # 表紙
    (3, 30),    # ツムグのストーリー
    (6, 30),    # 収益の分かれ目は、関係を深められるかどうかに移った（前段）
    (7, 25),    # 「関係の深さ」は担当者個人に依存している（前段）
    (14, 30),   # 3 つの条件に、ツムグはこう応える
    (19, 30),   # 予兆の判断に、現場だからわかる知見を使う
    (20, 30),   # 入力 → 処理 → 出力の流れ
    (21, 100),  # デモ
    (22, 35),   # 当初案からの変化
    (23, 25),   # 貸し続けられる環境を、自ら作る
    (25, 25),   # ROI
    (26, 20),   # 承認してほしい投資
    (27, 15),   # 有用性が証明された後の広がり方
    (28, 10),   # 結論
]
DIVIDER = 13    # 「システムパート」の区切り → 「付録」の区切りにする
APPENDIX = [2, 4, 5, 8, 9, 10, 11, 12, 15, 16, 17, 18, 24, 29, 30, 31, 32]   # 18 はアーキテクチャ
TOTAL = 32
if MODE == "compact":
    MAIN = [
        (1, 5),     # 表紙
        (3, 25),    # ツムグのストーリー
        (4, 30),    # 外部環境（前段 2〜4 枚目＋なぜ事業承継から を 1 枚に）
        (5, 30),    # 内部環境（前段 5〜7 枚目を 1 枚に）
        (16, 30),   # 3 つの条件に応える機能（3 つの条件＋主な機能）
        (20, 25),   # システムの全体構成（アーキテクチャ）
        (21, 25),   # 予兆の判断に、現場だからわかる知見を使う
        (22, 25),   # 入力 → 処理 → 出力（技術を添えて）
        (23, 95),   # デモ
        (24, 35),   # 当初案からの変化
        (25, 25),   # 貸し続けられる環境を、自ら作る（立場ごとの効果を含む）
        (27, 25),   # ROI
        (28, 20),   # 承認してほしい投資
        (29, 15),   # 有用性が証明された後の広がり方
        (30, 10),   # 結論
    ]
    DIVIDER = 15
    APPENDIX = [2, 6, 7, 8, 9, 10, 11, 12, 13, 14, 17, 18, 19, 26, 31, 32, 33, 34]
    TOTAL = 34

p = Presentation(SRC)
slides = list(p.slides)
assert len(slides) == TOTAL, f"{MODE} は {TOTAL} 枚のはず（{len(slides)} 枚）"
order = [n for n, _ in MAIN] + [DIVIDER] + APPENDIX
assert sorted(order) == list(range(1, TOTAL + 1)), "並びに抜けか重なりがある"


def replace_text(slide, old, new):
    for sh in slide.shapes:
        if not sh.has_text_frame:
            continue
        for para in sh.text_frame.paragraphs:
            for r in para.runs:
                if r.text == old:
                    r.text = new
                    return True
    return False


# 区切りを「付録」に
d = slides[DIVIDER - 1]
assert replace_text(d, "システムパート", "付録")
assert replace_text(d, "3 つの条件に、ツムグはどう応えるか", "時間の都合で本編から外したスライド（質疑で使う）")
for sh in d.shapes:
    if sh.has_text_frame and sh.text_frame.text.startswith("条件への答え"):
        sh.text_frame.paragraphs[0].runs[0].text = ("サマリ ／ 背景の元のスライド（前段） ／ なぜ事業承継から ／ 主な機能 ／ 技術 ／ 期待される効果 ／ ROI の前提 ／ 外販 ／ セキュリティ ／ 想定問答" if MODE == "compact" else "サマリ ／ 背景の詳細（前段） ／ なぜ事業承継から ／ 主な機能 ／ 技術 ／ 期待される効果 ／ ROI の前提 ／ 外販 ／ セキュリティ ／ 想定問答")
        for r in sh.text_frame.paragraphs[0].runs[1:]:
            r.text = ""
d.notes_slide.notes_text_frame.text = "ここから付録。質疑で必要になったときに開く。"

# 前段の 3 つの条件を付録に回したので、答えのスライドのリード文を単独で読める形に（compact は生成時に済み）
if MODE == "story":
  assert replace_text(slides[14 - 1], "前段の「残る・引き継がれる・つながる」を、新しい入力を増やさずに満たす",
                    "属人化を解くには、気づきが「残る・引き継がれる・つながる」ことが要る。ツムグは新しい入力を増やさずに満たす")

# 本編のノートに時間の目安
total = 0
for n, sec in MAIN:
    total += sec
    tf = slides[n - 1].notes_slide.notes_text_frame
    if tf is None:          # 前段の表紙はノートの欄が無い
        continue
    tf.text = f"【{sec // 60}:{sec % 60:02d}／累計 {total // 60}:{total % 60:02d}】\n" + tf.text
print(f"本編の合計 {total // 60} 分 {total % 60} 秒")

# 並べ替え
lst = p.slides._sldIdLst
ids = list(lst)
for el in ids:
    lst.remove(el)
for n in order:
    lst.append(ids[n - 1])

# ページ番号
for i, slide in enumerate(p.slides, 1):
    for sh in slide.shapes:
        if sh.has_text_frame and sh.text_frame.text.strip().isdigit() \
                and abs(Emu(sh.left).inches - 11.87) < 0.1 and abs(Emu(sh.top).inches - 6.92) < 0.1:
            runs = [r for para in sh.text_frame.paragraphs for r in para.runs]
            runs[0].text = str(i)
            for r in runs[1:]:
                r.text = ""
p.save(OUT)
print("wrote", OUT, "slides:", len(p.slides), "本編:", len(MAIN))
