# docs/build_guide.py — 手順書を生成する（作らなくてよいファイル）
#   docs/guide_template.md の {{file:パス}} を実ファイルの全文に置き換えて tsumugu_sf/4_ツムグ_実装手順書_Salesforce勘案版.md に出す。
#   使い方: python docs/build_guide.py
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LANG = {".py": "python", ".json": "json", ".sql": "sql", ".txt": "text", ".example": "toml", ".gitignore": "text"}


def inline(m):
    rel = m.group(1).strip()
    path = ROOT / rel
    if not path.exists():
        return f"> （ファイルが見つかりません: {rel}）"
    return f"**`{rel}`**\n\n```{LANG.get(path.suffix, 'text')}\n{path.read_text(encoding='utf-8').rstrip()}\n```"


text = re.sub(r"\{\{file:([^}]+)\}\}", inline, (ROOT / "docs" / "guide_template.md").read_text(encoding="utf-8"))
out = ROOT / "4_ツムグ_実装手順書_Salesforce勘案版.md"
out.write_text(text, encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8")
print("wrote:", out, f"({len(text):,} chars)")
