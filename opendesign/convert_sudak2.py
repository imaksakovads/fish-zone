#!/usr/bin/env python3
"""Конвертирует sudak-spinning-guide.html в markdown для build.py (через BeautifulSoup)."""
from bs4 import BeautifulSoup
import re

SRC = "/Users/igor/project/fish-zone/opendesign/sudak-spinning-guide.html"
DST = "/Users/igor/project/fish-zone/content/lovit-sudaka-spinning-tehnika-snasti.md"

soup = BeautifulSoup(open(SRC, encoding="utf-8").read(), "html.parser")

title = soup.find("h1").get_text(strip=True) if soup.find("h1") else "Как ловить судака на спиннинг"
lead_el = soup.select_one(".hero-sub")
lead = lead_el.get_text(strip=True) if lead_el else ""

# Маппинг label callout -> директива
LABEL_MAP = {
    "вывод за 30 секунд": "summary", "опыт автора": "experience",
    "частая ошибка": "warning", "миф и правда": "myth",
    "секрет": "secret", "совет": "tip",
}

out = [f"---\ntitle: \"{title}\"\ndescription: \"{lead[:155]}\"\ndate: 2026-08-22\nauthor: Fish Zone\ncategory: fish\ntags: судак, ловля судака, спиннинг, джиг, хищник\nimage: /images/lovit-sudaka-spinning-tehnika-snasti-hero.webp\nimage_alt: {title}\n---\n\n{lead}\n"]

def walk_children(el):
    """Рекурсивно собирает markdown из секции."""
    lines = []
    for child in el.children:
        name = getattr(child, "name", None)
        if name is None:
            continue
        if name == "h2":
            t = child.get_text(" ", strip=True)
            lines.append(f"\n## {t}\n")
        elif name == "h3":
            t = child.get_text(" ", strip=True)
            lines.append(f"\n### {t}\n")
        elif name == "p":
            t = _inline(child)
            if t:
                lines.append(f"{t}\n")
        elif name == "figure":
            img = child.find("img")
            if img:
                src = img.get("src", "").replace("../assets/", "").replace("assets/", "")
                alt = img.get("alt", "")
                lines.append(f"\n![{alt}](/images/{src.split('/')[-1]})\n")
            cap = child.find("figcaption")
            if cap:
                lines.append(f"*{cap.get_text(strip=True)}*\n")
        elif name == "div" and "callout" in " ".join(child.get("class", [])):
            label_el = child.find(class_="callout-label")
            label = label_el.get_text(strip=True).lower() if label_el else "tip"
            direct = LABEL_MAP.get(label, "tip")
            # текст callout = все p внутри
            content = "\n".join(_inline(p) for p in child.find_all("p", recursive=False) if _inline(p))
            # не дублировать label в контенте
            content = content.replace(label_el.get_text(strip=True), "") if label_el else content
            lines.append(f"\n:::{direct}\n{content.strip()}\n:::\n")
        elif name == "div" and "table-wrap" in " ".join(child.get("class", [])):
            table = child.find("table")
            if table:
                lines.append(_table(table))
        elif name == "ul":
            for li in child.find_all("li"):
                t = _inline(li)
                if t:
                    lines.append(f"- {t}\n")
        elif name == "ol":
            for i, li in enumerate(child.find_all("li"), 1):
                t = _inline(li)
                if t:
                    lines.append(f"{i}. {t}\n")
        elif name in ("strong", "em", "span", "a", "br"):
            t = _inline(child)
            if t:
                lines.append(f"{t}\n")
        else:
            # вложенные блоки (div в div) — рекурсия
            inner = walk_children(child)
            if inner.strip():
                lines.append(inner)
    return "\n".join(lines)

def _inline(el):
    """HTML-элемент -> markdown inline (сохраняя ** и `)."""
    t = str(el)
    t = re.sub(r"<strong[^>]*>", "**", t); t = t.replace("</strong>", "**")
    t = re.sub(r"<em[^>]*>", "*", t); t = t.replace("</em>", "*")
    t = re.sub(r'<span class="val"[^>]*>', "`", t); t = t.replace("</span>", "`")
    t = re.sub(r"<[^>]+>", "", t)
    t = t.replace("&nbsp;", " ").replace("&mdash;", "—").replace("&ndash;", "–")
    t = re.sub(r"&[a-z]+;", " ", t)
    return re.sub(r"\s+", " ", t).strip()

def _table(table):
    rows = []
    for tr in table.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
        rows.append("| " + " | ".join(cells) + " |")
    if not rows:
        return ""
    header = rows[0]
    sep = "| " + " | ".join(["---"] * (header.count("|") - 1)) + " |"
    return "\n".join([header, sep] + rows[1:]) + "\n"

# Основная статья
article = soup.find("article")
if article:
    out.append(walk_children(article))

# FAQ
faq_items = soup.select(".faq-item")
if faq_items:
    out.append("\n## FAQ\n")
    for item in faq_items:
        q = item.select_one(".faq-q")
        a = item.select_one(".faq-a")
        if q and a:
            qt = q.get_text(" ", strip=True).replace("Q", "").strip()
            # убрать номер Q1 и шеврон
            qt = re.sub(r"^Q\d+\s*", "", qt)
            at = _inline(a)
            out.append(f"\n:::faq **{qt}**\n{at}\n:::\n")

final = "\n".join(out)
final = re.sub(r"\n{3,}", "\n\n", final)
open(DST, "w", encoding="utf-8").write(final)
print(f"Записано: {DST}, {len(final)} симв")
print("Разделов ## :", final.count("\n## "))
print("Callout ::: :", final.count(":::"))
print("Картинок ![:", final.count("!["))

# Отчёты
import collections
print("Директивы:", collections.Counter(re.findall(r"^:::(summary|experience|warning|myth|secret|tip|faq|howto)", final, re.M)))
