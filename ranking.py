# =============================================================
# ranking.py — TF-IDF 検索エンジン（PROJECT ZERO W4 の ranking.py をナレッジ用に読み替え）
#   pages → knowledge（title / summary / signals / full_text）
#   日本語なので analyzer="char_wb"（文字 2〜3 gram）。W4 と同じ。
# =============================================================
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class SearchEngine:
    def __init__(self):
        self.vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 3),
                                          max_features=8000, min_df=1, max_df=0.95, sublinear_tf=True)
        self.matrix = None
        self.items: list[dict] = []
        self.is_fitted = False

    def build_index(self, items: list[dict], tag_names: dict[str, str] | None = None) -> None:
        """ナレッジ全件から TF-IDF 行列を作る。タイトル×3、要約×2、タグ名×2、本文×1 の重み"""
        if not items:
            return
        tag_names = tag_names or {}
        self.items = items
        corpus = []
        for k in items:
            sig_words = " ".join(tag_names.get(s, s) for s in k.get("signals", []))
            corpus.append(" ".join([
                (k.get("title", "") + " ") * 3,
                ((k.get("summary") or "") + " ") * 2,
                (sig_words + " ") * 2,
                (k.get("industry") or "") + " " + (k.get("size") or "") + " ",
                (k.get("full_text") or ""),
            ]))
        self.matrix = self.vectorizer.fit_transform(corpus)
        self.is_fitted = True

    def search(self, query: str, top_n: int = 20) -> list[dict]:
        """コサイン類似度で上位 top_n 件。score は 0〜100"""
        if not self.is_fitted or not query.strip():
            return []
        qv = self.vectorizer.transform([query])
        sims = cosine_similarity(qv, self.matrix)[0]
        results = []
        for idx, s in enumerate(sims):
            if s > 0.01:
                item = dict(self.items[idx])
                item["score"] = round(float(s) * 100, 1)
                results.append(item)
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_n]


_engine: SearchEngine | None = None


def get_engine() -> SearchEngine:
    global _engine
    if _engine is None:
        _engine = SearchEngine()
    return _engine


def rebuild_index(items: list[dict], tag_names: dict[str, str] | None = None) -> None:
    get_engine().build_index(items, tag_names)
