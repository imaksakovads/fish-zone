#!/usr/bin/env python3
"""
Статический сборщик блога Fish Zone (fish-zone.ru).
Конвертирует Markdown-статьи → SEO-оптимизированные HTML-страницы.
Один репозиторий: content/ → output/ → GitHub Pages.

Запуск:
    python3 build.py                           # собрать все статьи
    python3 build.py --check                   # только проверка статей
    python3 build.py --new "Заголовок"          # создать новую статью
    python3 build.py --watch                   # следить за изменениями (dev)

Требования:
    pip install markdown

Структура статьи (content/*.md):
    ---
    title: "Как выбрать спиннинг для новичка"
    description: "Мета-описание 140-160 символов с ключами"
    date: 2026-08-18
    author: Fish Zone
    category: tackle          # tackle | fish | technique | lure | rig | season | rating
    tags: спиннинг, выбор, новичок
    image: /images/cover.jpg
    image_alt: Спиннинг для новичка
    ---
    ## Контент статьи в Markdown...
"""

import re
import json
import shutil
import argparse
import os
from pathlib import Path
from datetime import datetime
from html import escape

# ═══════════════════════════════════════════════════════════════════
# КОНФИГУРАЦИЯ
# ═══════════════════════════════════════════════════════════════════

ROOT = Path(__file__).resolve().parent
CONTENT_DIR = ROOT / "content"
TEMPLATES_DIR = ROOT / "templates"
OUTPUT_DIR = ROOT / "output"
STATIC_DIR = ROOT / "static"

SITE_URL = "https://www.fish-zone.ru"
BLOG_URL = SITE_URL
SITE_NAME = "Fish Zone"

AUTHOR_DEFAULT = "Fish Zone"
AUTHOR_DESCRIPTION = (
    "Блог о спиннинговой ловле: выбор снастей, техники проводки, "
    "ловля хищной рыбы. Практические советы для рыболовов."
)

# Категории статей → читаемые рубрики
CATEGORY_NAMES = {
    "tackle": "Снасти",
    "fish": "Виды рыб",
    "technique": "Техники ловли",
    "lure": "Приманки",
    "rig": "Оснастка и узлы",
    "season": "Сезон и места",
    "rating": "Выбор и рейтинги",
}

# Средняя скорость чтения русского текста (слов/мин)
READING_SPEED_WPM = 180

MD_EXTENSIONS = [
    "markdown.extensions.toc",
    "markdown.extensions.fenced_code",
    "markdown.extensions.tables",
    "markdown.extensions.attr_list",
    "markdown.extensions.smarty",
]
MD_EXTENSION_CONFIGS = {
    "markdown.extensions.toc": {
        "permalink": False,
        "baselevel": 2,
        "title": "Содержание",
    },
}


# ═══════════════════════════════════════════════════════════════════
# ИНСТРУМЕНТЫ
# ═══════════════════════════════════════════════════════════════════

def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Разбирает YAML-подобный frontmatter из начала файла."""
    if not text.startswith("---\n"):
        return {}, text
    parts = text.split("---\n", 2)
    if len(parts) < 3:
        return {}, text
    meta = {}
    for line in parts[1].strip().split("\n"):
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        meta[key] = value
    return meta, parts[2]


def validate_frontmatter(meta: dict, filename: str = "") -> list[str]:
    """Проверяет обязательные поля frontmatter. Возвращает список ошибок."""
    errors = []
    required = ["title", "description", "date", "category"]
    for field in required:
        if not meta.get(field):
            errors.append(f"{filename}: отсутствует поле '{field}'")
    if "title" in meta and len(meta["title"]) > 100:
        errors.append(f"{filename}: title слишком длинный ({len(meta['title'])} симв.)")
    if "description" in meta and not (140 <= len(meta["description"]) <= 160):
        errors.append(f"{filename}: description вне диапазона 140-160 (сейчас {len(meta.get('description',''))})")
    cat = meta.get("category", "")
    if cat and cat not in CATEGORY_NAMES:
        errors.append(f"{filename}: неизвестная категория '{cat}' (допустимо: {', '.join(CATEGORY_NAMES)})")
    return errors


_TRANSLIT_TABLE = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e",
    "ё": "yo", "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k",
    "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r",
    "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "",
    "э": "e", "ю": "yu", "я": "ya",
}
_STOP_WORDS: frozenset[str] = frozenset({
    "как", "о", "в", "на", "и", "или", "для", "от", "что", "это",
    "не", "по", "с", "к", "из", "за", "у", "но", "то", "так",
    "бы", "ли", "же", "до", "под", "при", "без", "над", "об",
    "про", "со", "во", "ко", "а", "он", "она", "они", "мы",
    "вы", "его", "её", "их", "всё", "еще", "уже", "только",
    "лишь", "чем", "все", "вся", "весь",
})
_SLUG_MAX_LEN = 60
_SLUG_MIN_WORDS = 3
_WORD_SPLIT = re.compile(r"[^а-яёa-z0-9]+")


def _transliterate_word(word: str) -> str:
    result: list[str] = []
    for ch in word:
        if ch in _TRANSLIT_TABLE:
            tr = _TRANSLIT_TABLE[ch]
            if tr:
                result.append(tr)
        elif ch.isalnum():
            result.append(ch)
    return "".join(result)


def slugify(text: str, max_len: int = _SLUG_MAX_LEN) -> str:
    text = text.lower().strip()
    words = [w for w in _WORD_SPLIT.split(text) if w]
    significant = [w for w in words if w not in _STOP_WORDS]
    if len(significant) < _SLUG_MIN_WORDS:
        significant = words
    latin_words = [w for w in (_transliterate_word(w) for w in significant) if w]
    if not latin_words:
        return "post"
    chosen: list[str] = []
    length = 0
    for w in latin_words:
        added = len(chosen)
        if length + added + len(w) > max_len:
            break
        chosen.append(w)
        length += len(w)
    if not chosen:
        chosen = [latin_words[0][:max_len]]
    slug = "-".join(chosen)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug


def calc_reading_time(text: str) -> int:
    """Время чтения в минутах (русский текст: ~180 слов/мин)."""
    words = len(re.findall(r"[а-яёa-z0-9]+", text.lower(), re.I))
    return max(1, round(words / READING_SPEED_WPM))


def format_date(date_str: str, fmt: str = "%d.%m.%Y") -> str:
    if not date_str:
        return ""
    try:
        return datetime.strptime(str(date_str)[:10], "%Y-%m-%d").strftime(fmt)
    except ValueError:
        return str(date_str)


def to_iso_date(date_str: str) -> str:
    if not date_str:
        return ""
    try:
        return datetime.strptime(str(date_str)[:10], "%Y-%m-%d").date().isoformat()
    except ValueError:
        return str(date_str)


def load_template(name: str) -> str:
    path = TEMPLATES_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Шаблон не найден: {path}")
    return path.read_text(encoding="utf-8")


def render(template: str, **kwargs) -> str:
    """Простая замена {{переменных}} в шаблоне."""
    result = template
    for key, value in kwargs.items():
        placeholder = "{{" + key + "}}"
        result = result.replace(placeholder, str(value) if value is not None else "")
    return result


# ═══════════════════════════════════════════════════════════════════
# ОГЛАВЛЕНИЕ
# ═══════════════════════════════════════════════════════════════════

_H_PATTERN = re.compile(r'<h([23])\s+id="([^"]+)"[^>]*>(.*?)</h[23]>', re.IGNORECASE)
_TAG_STRIP = re.compile(r"<[^>]+>")


def extract_headings(html: str) -> list[dict]:
    headings: list[dict] = []
    for match in _H_PATTERN.finditer(html):
        level = int(match.group(1))
        hid = match.group(2)
        text = _TAG_STRIP.sub("", match.group(3)).strip()
        headings.append({"level": level, "id": hid, "text": text})
    return headings


def build_toc_html(headings: list[dict]) -> str:
    if not headings:
        return ""
    lines = [
        '<nav class="toc mb-12 p-6 border border-gray-200 bg-gray-50/50" '
        'aria-label="Содержание статьи">',
        '<h2 class="font-display text-sm uppercase tracking-widest mb-4">Содержание</h2>',
        '<ul class="space-y-2 text-sm">',
    ]
    for h in headings:
        indent = "ml-4" if h["level"] == 3 else ""
        lines.append(
            f'<li class="{indent}">'
            f'<a href="#{h["id"]}" class="text-gray-600 hover:text-black transition">'
            f'{escape(h["text"])}</a></li>'
        )
    lines.append("</ul></nav>")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
# JSON-LD
# ═══════════════════════════════════════════════════════════════════

def build_jsonld_article(meta: dict, url: str) -> str:
    date_pub = to_iso_date(meta.get("date", ""))
    category = meta.get("category", "")
    ld = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": meta.get("title", ""),
        "description": meta.get("description", ""),
        "image": {"@type": "ImageObject", "url": meta.get("image", "")},
        "datePublished": date_pub,
        "dateModified": date_pub,
        "articleSection": CATEGORY_NAMES.get(category, category),
        "author": {"@type": "Person", "name": meta.get("author", AUTHOR_DEFAULT)},
        "publisher": {
            "@type": "Organization",
            "name": SITE_NAME,
            "url": SITE_URL,
            "logo": {"@type": "ImageObject", "url": f"{SITE_URL}/apple-touch-icon.png"},
        },
        "mainEntityOfPage": {"@type": "WebPage", "@id": url},
    }
    return json.dumps(ld, ensure_ascii=False, indent=2)


def build_jsonld_breadcrumbs(meta: dict, url: str) -> str:
    ld = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Главная", "item": SITE_URL},
            {"@type": "ListItem", "position": 2, "name": "Блог", "item": BLOG_URL},
            {"@type": "ListItem", "position": 3, "name": meta.get("title", ""), "item": url},
        ],
    }
    return json.dumps(ld, ensure_ascii=False, indent=2)


# ═══════════════════════════════════════════════════════════════════
# СБОРКА СТРАНИЦ
# ═══════════════════════════════════════════════════════════════════

_H1_IN_BODY = re.compile(r"^# [^#]", re.MULTILINE)


def preprocess_markdown(body_md: str) -> tuple[str, list[str]]:
    """Автоисправления Markdown перед конвертацией."""
    warnings: list[str] = []
    if _H1_IN_BODY.search(body_md):
        body_md = _H1_IN_BODY.sub("## ", body_md)
        warnings.append("H1 в теле статьи → заменён на H2")
    return body_md, warnings


def build_post(meta: dict, body_md: str, template: str) -> str:
    from markdown import markdown as md_convert

    slug = meta.get("slug") or slugify(meta["title"])
    url = f"{BLOG_URL}/{slug}.html"

    image = meta.get("image", "")
    if image and image.startswith("/"):
        image = SITE_URL + image
        meta = {**meta, "image": image}

    body_md, md_warnings = preprocess_markdown(body_md)
    if md_warnings:
        meta.setdefault("_warnings", []).extend(md_warnings)

    body_html = md_convert(body_md, extensions=MD_EXTENSIONS, extension_configs=MD_EXTENSION_CONFIGS)

    toc_html = build_toc_html(extract_headings(body_html))
    read_min = calc_reading_time(body_md)
    date_fmt = format_date(meta.get("date", ""))
    date_iso = to_iso_date(meta.get("date", ""))
    category = meta.get("category", "")
    category_name = CATEGORY_NAMES.get(category, category)

    tags_raw = meta.get("tags", "")
    tag_list = [t.strip() for t in tags_raw.split(",") if t.strip()]
    tags_html = "".join(
        f'<a href="{BLOG_URL}/?tag={slugify(t)}" '
        f'class="text-xs border border-gray-300 px-3 py-1 rounded-full '
        f'hover:bg-black hover:text-white transition">{escape(t)}</a>'
        for t in tag_list
    )

    jsonld_article = build_jsonld_article(meta, url)
    jsonld_bc = build_jsonld_breadcrumbs(meta, url)

    return render(
        template,
        title=escape(meta.get("title", "")),
        description=escape(meta.get("description", "")),
        canonical=url,
        og_image=meta.get("image", ""),
        og_image_alt=meta.get("image_alt", meta.get("title", "")),
        jsonld_article=jsonld_article,
        jsonld_breadcrumbs=jsonld_bc,
        article_date=date_fmt,
        article_date_iso=date_iso,
        article_author=meta.get("author", AUTHOR_DEFAULT),
        article_category=category_name,
        article_category_slug=category,
        article_tags_html=tags_html,
        article_read_time=str(read_min),
        article_toc=toc_html,
        article_body=body_html,
        site_url=SITE_URL,
        blog_url=BLOG_URL,
        site_name=SITE_NAME,
        author_description=AUTHOR_DESCRIPTION,
        copyright_year=str(datetime.now().year),
    )


def build_index(posts: list[dict], template: str) -> str:
    jsonld_blog = json.dumps({
        "@context": "https://schema.org",
        "@type": "Blog",
        "name": f"Блог {SITE_NAME}",
        "url": BLOG_URL,
        "description": "Блог о спиннинговой ловле: снасти, приманки, техники, виды рыб",
        "publisher": {"@type": "Organization", "name": SITE_NAME, "url": SITE_URL},
    }, ensure_ascii=False, indent=2)

    cards: list[str] = []
    for meta in posts:
        slug = meta.get("slug") or slugify(meta["title"])
        url = f"{BLOG_URL}/{slug}.html"
        img_url = meta.get("image", "")
        if img_url.startswith("/"):
            img_url = SITE_URL + img_url
        date_fmt = format_date(meta.get("date", ""))
        date_iso = to_iso_date(meta.get("date", ""))
        read_min = calc_reading_time(meta.get("_body", ""))
        cat_name = CATEGORY_NAMES.get(meta.get("category", ""), "")

        card = f"""<article class="border border-gray-200 group hover:border-black transition duration-300 flex flex-col">
    <div class="h-56 overflow-hidden border-b border-gray-200">
        <img src="{img_url}" alt="{escape(meta.get('image_alt', meta.get('title', '')))}" class="w-full h-full object-cover group-hover:scale-105 transition duration-700" width="800" height="448" loading="lazy">
    </div>
    <div class="p-6 flex flex-col flex-1">
        <div class="flex items-center gap-3 mb-3">
            <time datetime="{date_iso}" class="font-mono text-xs text-gray-400">{date_fmt}</time>
            <span class="text-gray-300">·</span>
            <span class="font-mono text-xs text-gray-400">{read_min} мин</span>
        </div>
        <h2 class="font-display text-xl uppercase mb-3 leading-tight">
            <a href="{url}" class="hover:text-gray-500 transition">{escape(meta.get('title', ''))}</a>
        </h2>
        <p class="text-gray-600 text-sm leading-relaxed mb-4 flex-1">{escape(meta.get('description', ''))}</p>
        {f'<div class="font-mono text-xs text-gray-400">{escape(cat_name)}</div>' if cat_name else ''}
    </div>
</article>"""
        cards.append(card.strip())

    return render(
        template,
        title=f"Блог {SITE_NAME} — спиннинговая ловля",
        description="Блог о спиннинговой ловле: как выбрать снасти, ловить хищника, освоить техники проводки. Практические руководства для рыболовов.",
        canonical=BLOG_URL,
        og_image=f"{SITE_URL}/images/default-cover.webp",
        og_image_alt=f"Блог {SITE_NAME}",
        jsonld_blog=jsonld_blog,
        article_cards="\n".join(cards) if cards else "",
        article_count=str(len(posts)),
        site_url=SITE_URL,
        blog_url=BLOG_URL,
        site_name=SITE_NAME,
        copyright_year=str(datetime.now().year),
    )


def load_articles() -> list[tuple[dict, str]]:
    """Загружает все .md статьи из content/, сортирует по дате (новые сверху)."""
    articles: list[tuple[dict, str]] = []
    for path in sorted(CONTENT_DIR.glob("*.md")):
        if path.name.startswith("."):
            continue
        text = path.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(text)
        if not meta.get("title"):
            continue
        meta["slug"] = meta.get("slug") or slugify(meta["title"])
        meta["_source_file"] = path
        meta["_body"] = body
        articles.append((meta, body))
    articles.sort(key=lambda m: m[0].get("date", ""), reverse=True)
    return articles


def build_all(incremental: bool = False):
    try:
        import markdown  # noqa: F401
    except ImportError:
        print("❌ Нужен markdown: pip install markdown")
        return

    print("🔨 Fish Zone Blog Builder\n")

    post_tpl = load_template("blog-post.html")
    index_tpl = load_template("blog-index.html")
    print("📄 Шаблоны загружены")

    articles = load_articles()
    if not articles:
        print("\n⚠️  Нет статей в content/.\n")
        return
    print(f"📚 Статей: {len(articles)}")

    if incremental:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    else:
        if OUTPUT_DIR.exists():
            shutil.rmtree(OUTPUT_DIR)
        OUTPUT_DIR.mkdir(parents=True)

    if STATIC_DIR.exists():
        for f in STATIC_DIR.rglob("*"):
            if f.is_file():
                dst = OUTPUT_DIR / f.relative_to(STATIC_DIR)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dst)
        print("📦 Статика скопирована")

    total_warnings = 0
    built_count = 0
    for meta, body in articles:
        slug = meta["slug"]
        output_path = OUTPUT_DIR / f"{slug}.html"
        if incremental and output_path.exists():
            src_md = meta.get("_source_file")
            if src_md and src_md.exists() and src_md.stat().st_mtime <= output_path.stat().st_mtime:
                print(f"  ➖ {slug}.html — без изменений")
                continue
        html = build_post(meta, body, post_tpl)
        output_path.write_text(html, encoding="utf-8")
        print(f"  ✅ {slug}.html — «{meta['title'][:60]}»")
        built_count += 1
        for w in meta.get("_warnings", []):
            print(f"     ⚠️  {w}")
        total_warnings += len(meta.get("_warnings", []))

    posts_meta = [m for m, _ in articles]
    index_html = build_index(posts_meta, index_tpl)
    (OUTPUT_DIR / "index.html").write_text(index_html, encoding="utf-8")
    print("  ✅ index.html — главная блога")

    summary = f"сборка завершена: {built_count} статей"
    if total_warnings:
        summary += f", {total_warnings} предупреждений"
    print(f"\n{summary}")
    print(f"   Файлы в {OUTPUT_DIR}/")


# ═══════════════════════════════════════════════════════════════════
# СОЗДАНИЕ НОВЫХ СТАТЕЙ
# ═══════════════════════════════════════════════════════════════════

DEFAULT_TEMPLATE = """---
title: "{{TITLE}}"
description: "{{DESCRIPTION}}"
date: {{DATE}}
author: Fish Zone
category: tackle
tags: спиннинг, рыбалка
image: /images/cover-{{SLUG}}.webp
image_alt: {{TITLE}}
---

## Введение

_Лид-абзац: ответ на главный вопрос читателя в 2-3 предложениях._

## Основной раздел

Контент статьи...

## Итог

Краткое резюме.
"""


def create_article(title: str, description: str = "", tags: str = "") -> Path:
    today = datetime.now().strftime("%Y-%m-%d")
    slug = slugify(title)
    content = (
        DEFAULT_TEMPLATE
        .replace("{{TITLE}}", title)
        .replace("{{DESCRIPTION}}", description)
        .replace("{{DATE}}", today)
        .replace("{{TAGS}}", tags)
        .replace("{{SLUG}}", slug)
    )
    path = CONTENT_DIR / f"{slug}.md"
    if path.exists():
        raise FileExistsError(f"Статья уже существует: {path}")
    path.write_text(content, encoding="utf-8")
    print(f"✅ Создана статья: {path}")
    return path


# ═══════════════════════════════════════════════════════════════════
# ПРОВЕРКА
# ═══════════════════════════════════════════════════════════════════

def check_all() -> int:
    """Проверяет статьи без сборки. Возвращает кол-во ошибок."""
    articles = load_articles()
    errors = 0
    print("🔍 Проверка статей\n")
    for meta, _ in articles:
        file_errors = validate_frontmatter(meta, meta.get("slug", ""))
        for e in file_errors:
            print(f"  ✗ {e}")
            errors += 1
    if not articles:
        print("  (нет статей)")
    if errors == 0:
        print(f"✅ {len(articles)} статей прошли проверку")
    else:
        print(f"\n❌ {errors} ошибок")
    return errors


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Fish Zone Blog Builder")
    parser.add_argument("--check", action="store_true", help="только проверка статей")
    parser.add_argument("--new", metavar="TITLE", help="создать новую статью")
    parser.add_argument("--watch", action="store_true", help="dev-режим слежения")
    args = parser.parse_args()

    if args.check:
        sys_exit(check_all())
        return

    if args.new:
        create_article(args.new)
        return

    if args.watch:
        import time
        print("👁  Режим слежения (Ctrl+C для выхода)\n")
        try:
            while True:
                build_all(incremental=True)
                time.sleep(2)
        except KeyboardInterrupt:
            print("\nОстановлено.")
            return

    build_all()


def sys_exit(code: int):
    import sys
    sys.exit(code)


if __name__ == "__main__":
    main()
