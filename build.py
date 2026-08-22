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
import sys
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

SITE_URL = "https://fish-zone.ru"
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

# Короткое название категории (для hero-крошек статьи)
CATEGORY_SHORT = {
    "tackle": "Снасть",
    "fish": "Рыбы",
    "technique": "Техника",
    "lure": "Приманки",
    "rig": "Оснастка",
    "season": "Сезон",
    "rating": "Рейтинги",
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
        "baselevel": 1,
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

_H1_IN_BODY = re.compile(r"^# (?!#)", re.MULTILINE)


def preprocess_markdown(body_md: str) -> tuple[str, list[str]]:
    """Автоисправления Markdown перед конвертацией."""
    warnings: list[str] = []
    if _H1_IN_BODY.search(body_md):
        body_md = _H1_IN_BODY.sub("## ", body_md)
        warnings.append("H1 в теле статьи → заменён на H2")
    return body_md, warnings


def _add_image_dimensions(body_html: str) -> str:
    """Добавляет width/height к <img> без них (соотношение 16:9) для CLS/PageSpeed."""
    # Картинки 16:9 (1344x756) — добавляем стандартные размеры, если нет
    def add_dim(m):
        tag = m.group(0)
        if "width=" in tag and "height=" in tag:
            return tag
        # вставляем перед закрывающим >
        if tag.rstrip().endswith("/>"):
            return tag[:-2] + ' width="1344" height="756" />'
        return tag[:-1] + ' width="1344" height="756">'
    return re.sub(r"<img[^>]*>", add_dim, body_html)


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
            custom_title = (m.group(2) or "").strip()
            # Убираем markdown-разметку ** жирного из заголовка
            custom_title = re.sub(r"^\*\*(.+)\*\*\s*$", r"\1", custom_title)
            # собираем содержимое блока до ":::" или до новой открывающей директивы :::тип
            block_lines: list[str] = []
            i += 1
            while i < len(lines):
                s = lines[i].strip()
                if s == ":::":
                    i += 1  # съедаем закрывающую ":::"
                    break
                if _CALLOUT_OPEN.match(s):
                    break  # новая директива — закрываем текущий блок без ":::"
                block_lines.append(lines[i])
                i += 1

            inner_md = "\n".join(block_lines).strip()
            if not inner_md:
                continue

            # Преобразуем внутренний markdown
            inner_html = _md(inner_md, extensions=MD_EXTENSIONS, extension_configs=MD_EXTENSION_CONFIGS)

            if ctype == "faq":
                # FAQ: заголовок — в открывающей строке (:::faq Вопрос?), либо первая строка блока
                question = (custom_title or "").strip()
                if not question and block_lines:
                    first_line = block_lines[0].strip()
                    question = re.sub(r"^\*\*(.+)\*\*\s*$", r"\1", first_line)
                    block_lines = block_lines[1:]
                answer_md = "\n".join(block_lines).strip()
                answer_html = _md(answer_md, extensions=MD_EXTENSIONS, extension_configs=MD_EXTENSION_CONFIGS) if answer_md else inner_html
                if not question:
                    question = "Вопрос"
                faq_data.append({"q": question, "a": answer_html})
                qnum = len(faq_data)
                # Аккордеон (JS открывает один пункт)
                out.append(
                    f'<div class="faq-item" data-open="false">'
                    f'<button class="faq-q" aria-expanded="false">'
                    f'<span class="faq-num">Q{qnum}</span>'
                    f'{escape(question)}'
                    f'<svg class="faq-chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>'
                    f'</button>'
                    f'<div class="faq-a"><p>{re.sub(r"</?p>", "", answer_html).strip()}</p></div></div>'
                )
            elif ctype == "howto":
                # HowTo: заголовок — в открывающей строке (:::howto Название), либо первая строка блока
                step_title = (custom_title or "").strip()
                if not step_title and block_lines:
                    first_line = block_lines[0].strip()
                    step_title = re.sub(r"^\*\*(.+)\*\*\s*$", r"\1", first_line)
                    block_lines = block_lines[1:]
                desc_md = "\n".join(block_lines).strip()
                desc_html = _md(desc_md, extensions=MD_EXTENSIONS, extension_configs=MD_EXTENSION_CONFIGS) if desc_md else inner_html
                if not step_title:
                    step_title = "Шаг"
                howto_data.append({"name": step_title, "text": desc_html})
                out.append(
                    f'<h3 class="sub"><span class="h3-num">■</span>{escape(step_title)}</h3>'
                    f'<div class="prose">{desc_html}</div>'
                )
            else:
                # Обычный callout — тёмная «водная» панель с label
                cls, default_title = _CALLOUT_TYPES.get(ctype, ("callout-tip", "Совет"))
                title = custom_title or default_title
                out.append(
                    f'<aside class="callout {cls}">'
                    f'<div class="callout-label">{escape(title)}</div>'
                    f'{inner_html}</aside>'
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


def build_article_sections(body_html: str):
    """Разбивает HTML статьи на разделы, нумерует их и строит оглавление.

    Возвращает (lead_html, sections_html, toc_desktop, toc_mobile, count).
    Определяет уровень секций автоматически: H2, если есть; иначе H3
    (но не подзаголовки howto с class="sub"). Каждая секция получает номер 01, 02…
    """
    # Уровень секций: H2 если их >= 2 (реальные разделы), иначе H3
    # (одиночный H2 типа "## FAQ" не является уровнем секций)
    h2_count = len(re.findall(r'<h2\b', body_html))
    has_h2 = h2_count >= 2
    sec_tag = 'h2' if has_h2 else 'h3'
    # Убираем howto-подзаголовки (class="sub") из рассмотрения, если работаем с H3
    if not has_h2:
        body_html_work = re.sub(r'<h3 class="sub"[^>]*>.*?</h3>', '', body_html, flags=re.S)
    else:
        body_html_work = body_html

    # Разбиваем на куски: текст и заголовки выбранного уровня
    parts = re.split(
        rf'(<{sec_tag}[^>]*id="([^"]+)"[^>]*>.*?</{sec_tag}>)',
        body_html_work, flags=re.S)

    headings = []  # (id, num, text)
    lead_html = ""
    idx = 0
    if parts and parts[0].strip():
        lead_html = parts[0].strip()
        idx = 1

    body_sections_html = []
    while idx + 2 < len(parts):
        h_full = parts[idx]
        h_id = parts[idx + 1]
        text_after = parts[idx + 2]
        num = len(headings) + 1
        h_text = re.sub(r'<[^>]+>', '', h_full).strip()
        headings.append((h_id, num, h_text))
        body_sections_html.append(
            f'<section id="{h_id}">'
            f'<header class="sec-row"><span class="sec-num">{num:02d}</span>{h_full}</header>'
            f'{text_after}</section>'
        )
        idx += 3

    if idx < len(parts) and parts[idx].strip():
        body_sections_html.append(parts[idx])

    sections_html = "\n".join(body_sections_html)

    toc_desktop = "\n".join(
        f'<a class="toc-link" href="#{hid}"><span class="toc-num">{num:02d}</span>{escape(text)}</a>'
        for hid, num, text in headings
    )
    toc_mobile = "\n".join(
        f'<a class="toc-link" href="#{hid}"><span class="toc-num">{num:02d}</span>{escape(text)}</a>'
        for hid, num, text in headings
    )
    return lead_html, sections_html, toc_desktop, toc_mobile, len(headings)


def build_prev_next(current: dict, articles: list[tuple[dict, str]]):
    """Возвращает (prev_html, next_html) по соседним статьям в общем списке."""
    metas = [m for m, _ in articles]
    try:
        i = next(k for k, m in enumerate(metas) if m.get("slug") == current.get("slug"))
    except StopIteration:
        return "", ""
    prev = metas[i - 1] if i > 0 else None
    nxt = metas[i + 1] if i < len(metas) - 1 else None

    def card(art, direction):
        if not art:
            return ""
        slug = art.get("slug") or slugify(art["title"])
        url = f"{BLOG_URL}/{slug}.html"
        cat = CATEGORY_NAMES.get(art.get("category", ""), "")
        mins = calc_reading_time(art.get("_body", ""))
        arrow = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M19 12H5M11 6l-6 6 6 6"/></svg>'
                 if direction == "prev" else
                 '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg>')
        label = "Предыдущее руководство" if direction == "prev" else "Следующее руководство"
        cls = "pn-card" if direction == "prev" else "pn-card next"
        return (f'<a class="{cls}" href="{url}">'
                f'<span class="pn-dir">{arrow if direction=="prev" else ""} {label} {arrow if direction=="next" else ""}</span>'
                f'<span class="pn-title">{escape(art.get("title",""))}</span>'
                f'<span class="pn-meta">{cat} · {mins} мин</span></a>')

    return card(prev, "prev"), card(nxt, "next")


def build_post(meta: dict, body_md: str, template: str, related_posts: list[dict] | None = None, all_articles: list | None = None) -> str:
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

    # Добавляем width/height к inline-картинкам без размеров (для CLS и PageSpeed)
    body_html = _add_image_dimensions(body_html)

    lead_html, sections_html, toc_desktop, toc_mobile, toc_count = build_article_sections(body_html)
    read_min = calc_reading_time(body_md)
    date_fmt = format_date(meta.get("date", ""))
    date_iso = to_iso_date(meta.get("date", ""))
    category = meta.get("category", "")
    category_name = CATEGORY_NAMES.get(category, category)
    category_short = CATEGORY_SHORT.get(category, category_name)

    jsonld_article = build_jsonld_article(meta, url)
    jsonld_bc = build_jsonld_breadcrumbs(meta, url)
    jsonld_faq = build_jsonld_faq(faq_data)
    jsonld_howto = build_jsonld_howto(howto_data, meta)

    prev_html, next_html = build_prev_next(meta, all_articles or [])

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
        article_category_short=category_short,
        article_read_time=str(read_min),
        article_lead_html=lead_html,
        article_body=sections_html,
        article_toc_desktop=toc_desktop,
        article_toc_mobile=toc_mobile,
        article_toc_count=f"{toc_count:02d}",
        article_prev=prev_html,
        article_next=next_html,
        article_count=str(len(all_articles or [])),
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

    # WebSite JSON-LD с SearchAction (для Google Sitelinks Searchbox)
    jsonld_website = json.dumps({
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": f"Блог {SITE_NAME}",
        "url": BLOG_URL,
        "description": "Блог о спиннинговой ловле: снасти, приманки, техники, виды рыб",
        "potentialAction": {
            "@type": "SearchAction",
            "target": f"{BLOG_URL}/?s={{search_term_string}}",
            "query-input": "required name=search_term_string",
        },
    }, ensure_ascii=False, indent=2)

    # Маппинг категории → data-filter + дуотон-класс + короткая подпись для обложки
    CAT_FILTER = {"technique": "tehniki", "fish": "vidy", "tackle": "snasti", "lure": "tehniki",
                  "rig": "tehniki", "season": "vidy", "rating": "snasti"}
    CAT_DUO = {"technique": "d1", "fish": "d3", "tackle": "d4", "lure": "d2",
               "rig": "d2", "season": "d3", "rating": "d4"}
    # Короткая подпись для дуотон-обложки (упрощённое название статьи)
    def duo_label(title: str, cat: str) -> str:
        t = title
        for w in ("Как ловить ", "Как выбрать ", "на спиннинге", " для начинающих",
                  " полный гид", " руководство", " техника ловли", " удилищу", " снасти",
                  ": техника и снасти", " уловистые приёмы и приманки"):
            t = t.replace(w, "")
        t = t.rstrip(":;., ")
        # вернуть первые 3-4 слова
        words = [x for x in t.split() if x]
        return " ".join(words[:4]).upper() or title[:30].upper()

    cards: list[str] = []
    total_min = 0
    cat_counts = {"technique": 0, "fish": 0, "tackle": 0, "lure": 0, "rig": 0, "season": 0, "rating": 0}

    for i, meta in enumerate(posts, 1):
        slug = meta.get("slug") or slugify(meta["title"])
        url = f"{BLOG_URL}/{slug}.html"
        img_url = meta.get("image", "")
        if img_url.startswith("/"):
            img_url = SITE_URL + img_url
        date_fmt = format_date(meta.get("date", ""))
        date_iso = to_iso_date(meta.get("date", ""))
        read_min = calc_reading_time(meta.get("_body", ""))
        total_min += read_min
        cat = meta.get("category", "")
        cat_name = CATEGORY_NAMES.get(cat, cat)
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
        dfilter = CAT_FILTER.get(cat, "tehniki")
        duo = CAT_DUO.get(cat, "d1")
        label = duo_label(meta.get("title", ""), cat)

        # Медиа: фото если есть, иначе дуотон (без надписей на обложке)
        if img_url:
            media = (
                f'<div class="card-media photo">'
                f'<img src="{img_url}" alt="{escape(meta.get("image_alt", meta.get("title", "")))}" loading="lazy" width="1344" height="756">'
                f'</div>'
            )
        else:
            media = (
                f'<div class="card-media duo {duo}">'
                f'<div class="rings" aria-hidden="true"><i></i><i></i><i></i><i></i></div>'
                f'</div>'
            )

        card = (
            f'<article class="card" data-cat="{dfilter}">'
            f'{media}'
            f'<div class="card-body">'
            f'<div class="card-meta"><time datetime="{date_iso}">{date_fmt}</time><span class="dot"></span><span>{read_min} мин</span></div>'
            f'<h3><a href="{url}">{escape(meta.get("title", "") or "")}</a></h3>'
            f'<p>{escape(meta.get("description", ""))}</p>'
            f'<div class="card-foot">'
            f'<a class="card-read" href="{url}">Читать <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg></a>'
            f'<span class="card-tag">{escape((cat_name or "").lower())}</span>'
            f'</div></div></article>'
        )
        cards.append(card)

    return render(
        template,
        title=f"Блог {SITE_NAME} — спиннинговая ловля",
        description="Блог о спиннинговой ловле: как выбрать снасти, ловить хищника, освоить техники проводки. Практические руководства для рыболовов.",
        canonical=BLOG_URL,
        og_image=f"{SITE_URL}/static/fish-zone-preview.png",
        og_image_alt=f"Блог {SITE_NAME}",
        jsonld_blog=jsonld_blog,
        jsonld_website=jsonld_website,
        article_cards="\n".join(cards) if cards else "",
        article_count=str(len(posts)),
        total_minutes=str(total_min),
        cat_technique=str(cat_counts.get("technique", 0) + cat_counts.get("lure", 0) + cat_counts.get("rig", 0)),
        cat_fish=str(cat_counts.get("fish", 0) + cat_counts.get("season", 0)),
        cat_tackle=str(cat_counts.get("tackle", 0) + cat_counts.get("rating", 0)),
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
        html = build_post(meta, body, post_tpl, related_posts=pick_related(meta, articles), all_articles=articles)
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


def _make_description(body: str, title: str, target: tuple[int, int] = (140, 160)) -> str:
    """Формирует meta description 140-160 символов из первого абзаца лида."""
    # Без callout-директив, без markdown-разметки
    clean = re.sub(r"^:::[a-z]+\s*.*$", "", body, flags=re.MULTILINE)
    clean = re.sub(r"^:::\s*$", "", clean, flags=re.MULTILINE)
    clean = re.sub(r"[#*_>`]", "", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    lo, hi = target
    if len(clean) >= lo:
        return clean[:hi].rsplit(" ", 1)[0].rstrip(".,;:") + "."
    # Короткий текст — добиваем заголовком
    while len(clean) < lo:
        clean = clean + " " + title
    return clean[:hi].rsplit(" ", 1)[0].rstrip(".,;:") + "."


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
            f"Напиши исчерпывающую, глубокую SEO-статью для спиннинг-блога на тему: {title}. "
            f"Это информационная статья, которая должна конкурировать в топе Яндекса. "
            f"Аудитория: от новичков до опытных, мужчины 25-55 лет.\n\n"
            f"ТРЕБОВАНИЯ К ОБЪЁМУ И ГЛУБИНЕ (критично):\n"
            f"- Объём: минимум 3000 слов (около 20000-25000 знаков с пробелами). "
            f"Развёрнутый, плотный текст, НЕ короткий и НЕ обзорный.\n"
            f"- Каждый раздел раскрывай детально, с конкретикой, примерами и практическими советами.\n\n"
            f"СТРУКТУРА (минимум 8-10 разделов H2):\n"
            f"0. Лид-абзац без заголовка — вводный, сразу по делу.\n"
            f"1. Биология и поведение объекта (как ведёт себя, где держится, особенности).\n"
            f"2. Сезонность: весна / лето / осень / зима — как меняется активность и тактика в каждый сезон.\n"
            f"3. Снасти: детальный разбор удилища, катушки, шнура/лески, поводка с числами (тест, длина, диаметр, размер).\n"
            f"4. Приманки: виды, размеры, цвета, когда что работает.\n"
            f"5. Техника ловли: пошагово, с подразделами H3.\n"
            f"6. Практические сценарии: отдельно разбери мелководье, глубину, заросли/коряжник.\n"
            f"7. Сводная таблица: markdown-таблица «условие → снасть → приманка → тактика».\n"
            f"8. Итог и практические рекомендации.\n\n"
            f"ОБЯЗАТЕЛЬНО ВКЛЮЧИ БЛОКИ (callout-директивы):\n"
            f"1. :::summary — вывод за 30 секунд (сразу после лида)\n"
            f"2. :::experience — блок «Опыт автора»\n"
            f"3. :::warning — блок «Частая ошибка»\n"
            f"4. :::myth — блок «Миф и правда»\n"
            f"5. :::secret — блок «Секрет»\n"
            f"6. :::tip — блок «Совет»\n"
            f"7. :::howto **Шаг N: название** ... описание — минимум 3-4 шага\n"
            f"8. В конце — раздел ## FAQ с 3-4 блоками :::faq **Вопрос?** ответ...\n\n"
            f"РАСПРЕДЕЛЕНИЕ CALLOUT-БЛОКОВ (критично):\\n"
            f"- НЕ скучивай все callout в конец статьи. Распредели их равномерно:\\n"
            f"  минимум 2 блока должны быть в первой половине статьи.\\n"
            f"- Вставляй :::experience, :::warning, :::myth, :::secret, :::tip в соответствующие разделы по смыслу (не более 1-2 на раздел).\\n"
            f"- :::summary — сразу после лида. :::howto — в разделе техники.\\n"
            f"- ## FAQ — только в самом конце статьи.\\n\\n"
            f"ТЕМА И ЗАПРЕТ УХОДА ОТ ТЕМЫ (критично):\\n"
            f"- Пиши ТОЛЬКО о теме статьи: {title}.\\n"
            f"- КАТЕГОРИЧЕСКИ НЕЛЬЗЯ переключаться на «выбор первого спиннинга», «как выбрать спиннинг для новичка», общие советы по покупке удилища/катушки, если тема — конкретная рыба, приманка или техника.\\n"
            f"- Раздел «Снасти» раскрывай В КОНТЕКСТЕ темы, а не как общий гид по спиннингу.\\n"
            f"- Никаких блоков «Спиннинг для новичка» в статьях о рыбах, приманках и техниках.\\n\\n"

            f"Формат директив: блок открывается строкой :::тип, содержимое, "
            f"закрывается строкой ::: (три двоеточия). Заголовок howto/faq — в открывающей строке "
            f"после типа (:::howto **Название**), в теле только описание.\n\n"
            f"ФОРМАТ:\n"
            f"- Чистый Markdown, без frontmatter (он уже есть), без H1. "
            f"Заголовки разделов — ## H2, подразделы — ### H3.\n"
            f"- Плотные, содержательные абзацы (4-8 предложений), живой разговорный стиль.\n"
            f"- Конкретные числа: тест, длина, диаметр, размер катушки, вес приманки.\n"
            f"- Никакой воды, канцелярита и пересказа. Только практическая польза.\n"
        )

    print(f"   Шаг 2: отправляю в гуманизатор...")
    import subprocess
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "humanize.py"), prompt, "--max-tokens", "10000"],
        capture_output=True, text=True, timeout=600,
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
        # Обновляем tags (если переданы)
        if tags:
            if re.search(r'^tags: .*', frontmatter, re.MULTILINE):
                frontmatter = re.sub(r'^tags: .*', f'tags: {tags}', frontmatter, flags=re.MULTILINE)
            else:
                frontmatter += f'\ntags: {tags}'
        # Генерируем description из первого предложения лида (140-160 симв)
        # Обновляем существующую строку description (даже если она пустая), не дублируем
        desc = _make_description(article_body, title)
        if re.search(r'^description: .*', frontmatter, re.MULTILINE):
            frontmatter = re.sub(r'^description: .*', f'description: "{desc}"', frontmatter, flags=re.MULTILINE)
        else:
            frontmatter += f'\ndescription: "{desc}"'
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
    from tools.validate_md import validate_md
    articles = load_articles()
    errors = 0
    print("🔍 Проверка статей\n")
    for meta, body in articles:
        file_errors = validate_frontmatter(meta, meta.get("slug", ""))
        for e in file_errors:
            print(f"  ✗ {e}")
            errors += 1
        # Структурная валидация markdown (заголовки без #, пустой FAQ, callout в конце, чужой контент)
        md_issues = validate_md(body, title=meta.get("title", ""))
        for e in md_issues:
            print(f"  ✗ [{meta.get('slug')}] {e}")
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
