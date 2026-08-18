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


# ═══════════════════════════════════════════════════════════════════
# CALLOUT-ДИРЕКТИВЫ (:::блок) И FAQ/HowTo
# ═══════════════════════════════════════════════════════════════════

# Типы callout-блоков и их классы/заголовки
_CALLOUT_TYPES = {
    "tip": ("callout-tip", "Совет"),
    "secret": ("callout-secret", "Секрет"),
    "experience": ("callout-experience", "Опыт автора"),
    "warning": ("callout-warning", "Частая ошибка"),
    "myth": ("callout-myth", "Миф и правда"),
    "summary": ("callout-summary", "Вывод за 30 секунд"),
}

# Директива: строки вида ":::tip", ":::tip Заголовок" ... ":::"
_CALLOUT_OPEN = re.compile(r"^:::\s*([a-z]+)(?:\s+(.+))?\s*$")


def render_callouts(body_md: str):
    """Преобразует callout-директивы (:::) в HTML-блоки и собирает FAQ/HowTo данные.

    Возвращает (обработанный_markdown, faq_data, howto_data).
    FAQ-директива: ":::faq Вопрос?" ... ответ ... ":::"
    HowTo-директива: ":::howto Шаг" ... описание ... ":::"
    """
    from markdown import markdown as _md
    lines = body_md.split("\n")
    out: list[str] = []
    i = 0
    faq_data: list[dict] = []
    howto_data: list[dict] = []

    while i < len(lines):
        line = lines[i]
        m = _CALLOUT_OPEN.match(line.strip())
        if m:
            ctype = m.group(1)
            custom_title = m.group(2)
            # собираем содержимое блока до ":::"
            block_lines: list[str] = []
            i += 1
            while i < len(lines) and lines[i].strip() != ":::": 
                block_lines.append(lines[i])
                i += 1
            # i теперь на закрывающей ":::"
            i += 1  # пропускаем ":::"

            inner_md = "\n".join(block_lines).strip()
            if not inner_md:
                continue

            # Преобразуем внутренний markdown
            inner_html = _md(inner_md, extensions=MD_EXTENSIONS, extension_configs=MD_EXTENSION_CONFIGS)

            if ctype == "faq":
                # FAQ: первая строка — вопрос (жирный или обычный), остальное — ответ
                first_line = block_lines[0].strip() if block_lines else ""
                question = re.sub(r"^\*\*(.+)\*\*\s*$", r"\1", first_line)
                answer_md = "\n".join(block_lines[1:]).strip() if len(block_lines) > 1 else ""
                answer_html = _md(answer_md, extensions=MD_EXTENSIONS, extension_configs=MD_EXTENSION_CONFIGS) if answer_md else inner_html
                faq_data.append({"q": question, "a": answer_html})
                out.append(
                    f'<div class="faq-item border border-gray-200 p-5 mb-4">'
                    f'<h3 class="font-display text-lg uppercase mb-2">{escape(question)}</h3>'
                    f'<div class="prose-custom">{answer_html}</div></div>'
                )
            elif ctype == "howto":
                first_line = block_lines[0].strip() if block_lines else ""
                step_title = re.sub(r"^\*\*(.+)\*\*\s*$", r"\1", first_line)
                desc_md = "\n".join(block_lines[1:]).strip() if len(block_lines) > 1 else ""
                desc_html = _md(desc_md, extensions=MD_EXTENSIONS, extension_configs=MD_EXTENSION_CONFIGS) if desc_md else inner_html
                howto_data.append({"name": step_title, "text": desc_html})
                out.append(
                    f'<div class="howto-step border-l-4 border-water pl-5 mb-4">'
                    f'<h3 class="font-display text-lg uppercase mb-1">{escape(step_title)}</h3>'
                    f'<div class="prose-custom">{desc_html}</div></div>'
                )
            else:
                # Обычный callout
                cls, default_title = _CALLOUT_TYPES.get(ctype, ("callout-tip", "Совет"))
                title = custom_title or default_title
                out.append(
                    f'<aside class="callout {cls} border border-gray-200 bg-gray-50/50 p-5 my-5">'
                    f'<p class="font-display text-xs uppercase tracking-widest text-water mb-2">{escape(title)}</p>'
                    f'<div class="prose-custom">{inner_html}</div></aside>'
                )
            continue
        out.append(line)
        i += 1

    return "\n".join(out), faq_data, howto_data


def build_jsonld_faq(faq_data: list[dict]) -> str:
    if not faq_data:
        return ""
    ld = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": item["q"],
                "acceptedAnswer": {"@type": "Answer", "text": re.sub(r"<[^>]+>", " ", item["a"]).strip()},
            }
            for item in faq_data
        ],
    }
    return json.dumps(ld, ensure_ascii=False, indent=2)


def build_jsonld_howto(howto_data: list[dict], meta: dict) -> str:
    if not howto_data:
        return ""
    ld = {
        "@context": "https://schema.org",
        "@type": "HowTo",
        "name": meta.get("title", ""),
        "step": [
            {"@type": "HowToStep", "position": i + 1, "name": item["name"],
             "text": re.sub(r"<[^>]+>", " ", item["text"]).strip()}
            for i, item in enumerate(howto_data)
        ],
    }
    return json.dumps(ld, ensure_ascii=False, indent=2)


def build_post(meta: dict, body_md: str, template: str, related_posts: list[dict] | None = None) -> str:
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

    # Callout-директивы (:::) и FAQ/HowTo → HTML + сбор JSON-LD
    body_md, faq_data, howto_data = render_callouts(body_md)
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
    jsonld_faq = build_jsonld_faq(faq_data)
    jsonld_howto = build_jsonld_howto(howto_data, meta)

    # Related-статьи («С этой статьёй читают»)
    related_html = ""
    if related_posts:
        cards = []
        for rp in related_posts[:4]:
            rslug = rp.get("slug") or slugify(rp["title"])
            rurl = f"{BLOG_URL}/{rslug}.html"
            rimg = rp.get("image", "")
            if rimg.startswith("/"):
                rimg = SITE_URL + rimg
            rdate = format_date(rp.get("date", ""))
            cards.append(
                f'<a href="{rurl}" class="group border border-gray-200 hover:border-water transition flex items-center gap-4 p-3">'
                f'<img src="{rimg}" alt="{escape(rp.get("image_alt", rp.get("title","")))}" class="w-20 h-14 object-cover" loading="lazy" width="80" height="56">'
                f'<div><p class="font-mono text-[10px] text-gray-400 mb-1">{rdate}</p>'
                f'<h3 class="font-display text-sm uppercase leading-tight group-hover:text-water transition">{escape(rp.get("title",""))}</h3></div></a>'
            )
        related_html = '<section class="mt-12"><h2 class="font-display text-2xl uppercase mb-4">С этой статьёй читают</h2><div class="grid grid-cols-1 md:grid-cols-2 gap-4">' + "".join(cards) + '</div></section>'

    return render(
        template,
        title=escape(meta.get("title", "")),
        description=escape(meta.get("description", "")),
        canonical=url,
        og_image=meta.get("image", ""),
        og_image_alt=meta.get("image_alt", meta.get("title", "")),
        jsonld_article=jsonld_article,
        jsonld_breadcrumbs=jsonld_bc,
        jsonld_faq=jsonld_faq,
        jsonld_howto=jsonld_howto,
        article_date=date_fmt,
        article_date_iso=date_iso,
        article_author=meta.get("author", AUTHOR_DEFAULT),
        article_category=category_name,
        article_category_slug=category,
        article_tags_html=tags_html,
        article_read_time=str(read_min),
        article_toc=toc_html,
        article_body=body_html,
        article_related=related_html,
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


def pick_related(current: dict, articles: list[tuple[dict, str]], limit: int = 4) -> list[dict]:
    """Подбирает related-статьи: сначала та же категория, потом другие, но не текущую."""
    cur_cat = current.get("category", "")
    cur_slug = current.get("slug")
    same_cat = [m for m, _ in articles if m.get("category") == cur_cat and m.get("slug") != cur_slug]
    others = [m for m, _ in articles if m.get("category") != cur_cat and m.get("slug") != cur_slug]
    return (same_cat + others)[:limit]


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
        html = build_post(meta, body, post_tpl, related_posts=pick_related(meta, articles))
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


def generate_article(title: str, tags: str = "", category: str = "tackle", prompt: str = "") -> Path:
    """Генерирует статью через гуманизатор (tools/humanize.py) и сохраняет .md.

    Пайплайн:
      1. create_article() — создаёт .md с frontmatter
      2. Отправляет промпт в гуманизатор (CLI, DeepSeek/Gemini fallback)
      3. Гуманизатор применяет фильтры (детокс AI-клише, запрет тире и т.д.)
      4. Вставляет тело статьи, обновляет category/tags

    Аргументы:
        title    — заголовок статьи
        tags     — теги через запятую
        category — категория (tackle/fish/technique/lure/rig/season/rating)
        prompt   — доп. уточнение темы (иначе используется title)
    """
    filepath = create_article(title, tags=tags)
    print(f"   Шаг 1: файл создан")

    # Формируем промпт для генерации под спиннинг-нишу
    if not prompt:
        prompt = (
            f"Напиши статью для спиннинг-блога на тему: {title}. "
            f"Это информационная SEO-статья для рыболовов-спиннингистов. "
            f"Аудитория: от новичков до опытных, мужчины 25-55 лет. "
            f"Структура:\n"
            f"- Лид-абзац без заголовка (сразу с новой строки)\n"
            f"- Разделы с заголовками ## H2\n"
            f"- В конце естественное завершение, без рекламы\n\n"
            f"Обязательно включи в текст эти блоки (используй callout-директивы):\n"
            f"1. :::summary — вывод за 30 секунд (в начале, сразу после лида)\n"
            f"2. :::experience — блок «Опыт автора» (в середине)\n"
            f"3. :::warning — блок «Частая ошибка» (в середине)\n"
            f"4. :::myth — блок «Миф и правда» (в середине)\n"
            f"5. :::secret — блок «Секрет» (в середине)\n"
            f"6. :::tip — блок «Совет» (в середине)\n"
            f"7. :::howto **Название шага** ... описание — минимум 2-3 шага HowTo\n"
            f"8. В конце — раздел ## FAQ с 2-3 блоками :::faq **Вопрос?** ответ...\n\n"
            f"Формат директив: блок открывается строкой :::тип, содержимое, "
            f"закрывается строкой ::: (три двоеточия). Для howto/faq первая строка "
            f"внутри — **жирный заголовок**, остальное — описание.\n\n"
            f"Остальной текст: чистый Markdown, без frontmatter (он уже есть), "
            f"без H1, короткие абзацы по 2-4 предложения, "
            f"конкретика и практическая польза."
        )

    print(f"   Шаг 2: отправляю в гуманизатор...")
    import subprocess
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "humanize.py"), prompt],
        capture_output=True, text=True, timeout=300,
    )
    if result.returncode != 0 or not result.stdout.strip():
        print(f"❌ Гуманизатор не сработал: {result.stderr[-300:]}")
        return filepath
    article_body = result.stdout.strip()
    print(f"   ✅ Гуманизатор ответил ({len(article_body)} симв)")

    # Читаем файл и вставляем тело после frontmatter
    raw = filepath.read_text(encoding="utf-8")
    parts = raw.split("---\n")
    if len(parts) >= 3:
        frontmatter = parts[1].strip()
        # Обновляем category
        if category:
            if re.search(r'^category: .*', frontmatter, re.MULTILINE):
                frontmatter = re.sub(r'^category: .*', f'category: {category}', frontmatter, flags=re.MULTILINE)
            else:
                frontmatter += f'\ncategory: {category}'
        new_content = f"---\n{frontmatter}\n---\n\n{article_body}\n"
        filepath.write_text(new_content, encoding="utf-8")
    else:
        filepath.write_text(raw.rstrip() + "\n\n" + article_body + "\n", encoding="utf-8")

    print(f"\n📝 Статья сгенерирована: {filepath}")
    print(f"   Тема: {title}")
    print(f"   Далее: запусти критик → build → deploy")
    return filepath


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
    parser.add_argument("--generate", metavar="TITLE", help="сгенерировать статью через гуманизатор")
    parser.add_argument("--category", default="tackle", help="категория для --generate (tackle/fish/technique/lure/rig/season/rating)")
    parser.add_argument("--tags", default="", help="теги для --generate через запятую")
    parser.add_argument("--prompt", default="", help="доп. промпт для --generate")
    parser.add_argument("--watch", action="store_true", help="dev-режим слежения")
    args = parser.parse_args()

    if args.check:
        sys_exit(check_all())
        return

    if args.generate:
        generate_article(args.generate, tags=args.tags, category=args.category, prompt=args.prompt)
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
