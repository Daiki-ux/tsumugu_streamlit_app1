# =============================================================
# crawler.py — ⓪ 収集（★3-1 の第 1 段「連携／生データ収集」。PROJECT ZERO W2 の crawler.py そのまま ＋ 2 関数）
#   fetch_page / parse_html / crawl_url は W2 の完成版のまま。
#   to_knowledge()  取ってきたページを knowledge の 1 行（dict）にする
#   crawl_all()     rules.json の sources を順に取り、data/raw/ に生 HTML を保存し、knowledge(public) と sources に入れる
#   使い方: python crawler.py          （再実行しても、取得済みのページは data/raw/ から読む＝再取得しない）
#          python crawler.py --refresh （全部取り直す）
#   集めるのは公的な支援制度・手引き・法律／税制の公開ページだけ（外部の事例記事は集めない）。行内データはスクレイピングしない。
# =============================================================
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

import database as db

BASE_DIR = Path(__file__).resolve().parent
RAW_DIR = BASE_DIR / "data" / "raw"
RULES = json.loads((BASE_DIR / "rules.json").read_text(encoding="utf-8"))
CRAWL = RULES["crawl"]


# ── W2 そのまま ─────────────────────────────────────────────
def fetch_page(url: str, timeout: int = 10) -> Optional[str]:
    """指定URLのHTMLを取得する。失敗時は None"""
    try:
        headers = {"User-Agent": CRAWL["user_agent"]}
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding
        return resp.text
    except requests.RequestException as e:
        print(f"❌ 取得エラー: {e}")
        return None


def parse_html(html: str, url: str) -> dict:
    """HTMLを解析してページ情報を抽出する"""
    soup = BeautifulSoup(html, "html.parser")

    # 不要タグを除去
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    # タイトル取得
    title = "No Title"
    if soup.find("title"):
        title = soup.find("title").get_text().strip()
    elif soup.find("h1"):
        title = soup.find("h1").get_text().strip()

    # meta description
    description = ""
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        description = meta["content"][:200]

    # meta keywords
    keywords = []
    meta_kw = soup.find("meta", attrs={"name": "keywords"})
    if meta_kw and meta_kw.get("content"):
        keywords = [kw.strip() for kw in meta_kw["content"].split(",")][:10]

    # 本文テキスト
    elems = soup.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "td"])
    full_text = " ".join(e.get_text().strip() for e in elems)
    full_text = re.sub(r"\s+", " ", full_text).strip()

    # リンク
    links = [
        a["href"]
        for a in soup.find_all("a", href=True)
        if a["href"].startswith("http")
    ][:20]

    return {
        "url": url,
        "title": title,
        "description": description,
        "keywords": keywords,
        "full_text": full_text,
        "links": links,
        "word_count": len(full_text.split()),
        "crawled_at": datetime.now().isoformat(),
        "crawl_status": "success",
    }


def crawl_url(url: str) -> dict:
    """URLをクロールして情報を返す（fetch → parse のワンストップ）"""
    html = fetch_page(url)

    if not html:
        return {
            "url": url,
            "crawl_status": "failed",
            "crawled_at": datetime.now().isoformat(),
            "error": "Failed to fetch page",
        }

    try:
        return parse_html(html, url)
    except Exception as e:
        return {
            "url": url,
            "crawl_status": "error",
            "crawled_at": datetime.now().isoformat(),
            "error": str(e),
        }


# ── ここから 2 関数を足す ────────────────────────────────────
def to_knowledge(page: dict, source: dict) -> dict:
    """W2 の page dict → knowledge の 1 行。id は 'PUB-' + sources.id。要約は本文の先頭 200 字。
    signals には正式タグ語彙のうち本文に語が出るものを入れる（TF-IDF の keywords 相当）"""
    text = page.get("full_text", "")
    signals = [tag_id for tag_id, spec in RULES["formal"].items()
               if any(w in text for w in spec["name"].replace("・", " ").split())]
    title = re.sub(r"\s*[|｜].*$", "", page.get("title", "")).strip() or source["label"]   # 「ページ名 | サイト名」のサイト名を落とす
    return {"id": "PUB-" + source["id"], "kind": source["kind"], "title": title, "industry": "", "size": "", "branch": "",
            "year": None, "summary": (page.get("description") or text[:200]), "signals": signals, "actions": [],
            "outcome": "", "questions": [], "handled_by": [], "full_text": text[:6000], "source": "public",
            "url": page["url"], "crawled_at": page["crawled_at"],
            "license_note": f"公開ページ（{source['label']}）。出典として URL を表示する。本文は検索用の内部利用に限る"}


def crawl_all(refresh: bool = False) -> dict:
    """rules.json の sources を全部取り、knowledge(public) と sources テーブルに入れる。
    戻り値は {success, failed, skipped}（skipped＝data/raw/ の取得済みを使った件数。success に含む）"""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    db.init_db()
    result = {"success": 0, "failed": 0, "skipped": 0}
    for src in RULES["sources"]:
        raw = RAW_DIR / f"{src['id']}.json"
        if raw.exists() and not refresh:
            page = json.loads(raw.read_text(encoding="utf-8"))          # 取得済み → 再取得しない
            result["skipped"] += 1
        else:
            page = crawl_url(src["url"])
            raw.write_text(json.dumps(page, ensure_ascii=False, indent=2), encoding="utf-8")
            time.sleep(CRAWL["delay_seconds"])                          # 相手のサーバーに負担をかけない
        db.upsert_source(src, page["crawl_status"], page["crawled_at"])
        if page["crawl_status"] == "success" and page.get("full_text"):
            db.insert_knowledge(to_knowledge(page, src))
            result["success"] += 1
        else:
            result["failed"] += 1
        print(f"{page['crawl_status']:8s} {src['id']:9s} {src['url']}")
    db.prune_public_sources([src["id"] for src in RULES["sources"]])   # クロール先から外したページは DB からも消す
    return result


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print(crawl_all(refresh="--refresh" in sys.argv))
    print("knowledge public:", db.count_knowledge("public"))
