#!/usr/bin/env python3
"""Конвертирует sudak-spinning-guide.html (эталон OpenDesign) в markdown для build.py."""
import re, html as htmllib

SRC = "/Users/igor/project/fish-zone/opendesign/sudak-spinning-guide.html"
DST = "/Users/igor/project/fish-zone/content/lovit-sudaka-spinning-tehnika-snasti.md"

raw = open(SRC, encoding="utf-8").read()

# --- Вспомогательные ---
def txt(tag):
    return re.sub(r"<[^>]+>", "", tag).strip()

def md_inline(block):
    """Грубо: html-параграфы -> markdown текст."""
    # убираем <p> теги, превращаем <strong> в **, <em> в *
    b = block
    b = re.sub(r"<strong>", "**", b); b = re.sub(r"</strong>", "**", b)
    b = re.sub(r"<em>", "*", b); b = re.sub(r"</em>", "*", b)
    b = re.sub(r"<span class=\"val\">", "`", b); b = re.sub(r"</span>", "`", b)
    b = re.sub(r"<[^>]+>", "", b)  # остальные теги убрать
    b = htmllib.unescape(b)
    return b.strip()

# --- Разбивка: hero title + body ---
# Извлекаем H1
m = re.search(r"<h1[^>]*>(.*?)</h1>", raw, re.S)
title = txt(m.group(1)) if m else "Как ловить судака на спиннинг"

# Лид (hero-sub)
m = re.search(r'class="hero-sub">(.*?)</p>', raw, re.S)
lead = txt(m.group(1)) if m else ""

# Основной контент статьи между <article> и </article>
m = re.search(r"<article[^>]*>(.*?)</article>", raw, re.S)
body = m.group(1) if m else raw

# --- Собираем секции ---
# Секции: <section id="..."> ... <header class="sec-row"><span class="sec-num">NN</span><h2>...</h2></header> ... </section>
sections = re.findall(r'<section id="([^"]+)".*?</section>', body, re.S)

out = []
for sec in sections:
    # заголовок
    m = re.search(r'<h2[^>]*>(.*?)</h2>', sec, re.S)
    h2 = txt(m.group(1)) if m else ""
    out.append(f"## {h2}\n")

    # содержимое: разбираем последовательно
    pos = 0
    # figure (картинка)
    for fm in re.finditer(r"<figure.*?<img[^>]*src=\"([^\"]+)\"[^>]*alt=\"([^\"]*)\".*?</figure>", sec, re.S):
        img_src = fm.group(1).replace("../assets/", "").replace("assets/", "")
        img_alt = fm.group(2)
        out.append(f"\n![{img_alt}](/images/{img_src.split('/')[-1]})\n")

    # callout
    for cm in re.finditer(r'<div class="callout-label">(.*?)</div>\s*(.*?)(?=<div class="callout-label">|</aside>)', sec, re.S):
        label = txt(cm.group(1))
        content = md_inline(cm.group(2))
        # маппинг label -> директива
        label_map = {
            "Вывод за 30 секунд": "summary", "Опыт автора": "experience",
            "Частая ошибка": "warning", "Миф и правда": "myth",
            "Секрет": "secret", "Совет": "tip", "Цвет приманки": "tip",
        }
        direct = label_map.get(label, "tip")
        out.append(f"\n:::{direct}\n{content}\n:::\n")

    # абзацы
    for pm in re.finditer(r"<p>(.*?)</p>", sec, re.S):
        p = md_inline(pm.group(1))
        if p:
            out.append(f"{p}\n")

# FAQ
faq_items = re.findall(r'<button class="faq-q"[^>]*>.*?<span class="faq-num">(Q\d)</span>(.*?)<svg.*?</button>.*?<div class="faq-a"><p>(.*?)</p>', body, re.S)
if faq_items:
    out.append("\n## FAQ\n")
    for num, q, a in faq_items:
        q = htmllib.unescape(txt(q))
        a = htmllib.unescape(txt(a))
        out.append(f"\n:::faq **{q}?**\n{a}\n:::\n")

# --- Frontmatter ---
date = "2026-08-22"
fm = f"""---
title: "{title}"
description: "{lead[:155]}"
date: {date}
author: Fish Zone
category: fish
tags: судак, ловля судака, спиннинг, джиг, хищник
image: /images/lovit-sudaka-spinning-tehnika-snasti-hero.webp
image_alt: {title}
---

{lead}

"""
final = fm + "\n".join(out)
open(DST, "w", encoding="utf-8").write(final)
print(f"Записано: {DST}, {len(final)} симв")
print("Секции:", len(sections), "| FAQ:", len(faq_items))
