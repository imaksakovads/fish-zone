"""Регенерация sitemap.xml и robots.txt для www.fish-zone.ru (GitHub Pages).

Сканирует собранные .html в output/ (без index) и генерирует sitemap.xml,
а также robots.txt со ссылкой на sitemap. Запускать после build.py.
"""
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output"
BASE_URL = "https://www.fish-zone.ru"
TODAY = date.today().isoformat()

SITEMAP_HEAD = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
SITEMAP_TAIL = '</urlset>'


def build_sitemap() -> str:
    parts = [SITEMAP_HEAD]
    parts.append(f"""  <url>
    <loc>{BASE_URL}/</loc>
    <priority>1.0</priority>
    <changefreq>weekly</changefreq>
    <lastmod>{TODAY}</lastmod>
  </url>""")

    if OUTPUT_DIR.exists():
        articles = sorted(f.stem for f in OUTPUT_DIR.glob("*.html") if f.stem != "index")
        for slug in articles:
            fpath = OUTPUT_DIR / f"{slug}.html"
            mtime = date.fromtimestamp(fpath.stat().st_mtime).isoformat()
            parts.append(f"""  <url>
    <loc>{BASE_URL}/{slug}.html</loc>
    <priority>0.7</priority>
    <changefreq>monthly</changefreq>
    <lastmod>{mtime}</lastmod>
  </url>""")

    parts.append(SITEMAP_TAIL)
    return "\n".join(parts) + "\n"


def main() -> None:
    sitemap = build_sitemap()
    (OUTPUT_DIR / "sitemap.xml").write_text(sitemap, encoding="utf-8")
    print(f"sitemap.xml — {sitemap.count('<loc>')} URLs")

    robots = (
        "User-agent: *\n"
        "Allow: /\n"
        f"Sitemap: {BASE_URL}/sitemap.xml\n"
    )
    (OUTPUT_DIR / "robots.txt").write_text(robots, encoding="utf-8")
    print("robots.txt — записан")


if __name__ == "__main__":
    main()
