#!/usr/bin/env python3
"""Восстанавливает пустые FAQ-ответы из эталона OpenDesign."""
from bs4 import BeautifulSoup
import re

SRC = "/Users/igor/project/fish-zone/opendesign/sudak-spinning-guide.html"
DST = "/Users/igor/project/fish-zone/content/lovit-sudaka-spinning-tehnika-snasti.md"

soup = BeautifulSoup(open(SRC, encoding="utf-8").read(), "html.parser")
faq_items = soup.select(".faq-item")
answers = []
for item in faq_items:
    q = item.select_one(".faq-q")
    a = item.select_one(".faq-a")
    if q and a:
        qt = q.get_text(" ", strip=True)
        qt = re.sub(r"^Q\d+\s*", "", qt).strip()
        at = a.get_text(" ", strip=True).strip()
        answers.append((qt, at))
print("Найдено ответов в эталоне:", len(answers))

t = open(DST, encoding="utf-8").read()
# Для каждого :::faq **Вопрос** ... ::: — вставить ответ
def fill(m):
    q = m.group(1)
    # найти ответ по совпадению вопроса
    for qt, at in answers:
        if qt[:25].lower() in q.lower() or q[:25].lower() in qt.lower():
            return f":::faq **{q}**\n{at}\n:::"
    return m.group(0)

t = re.sub(r":::faq \*\*(.*?)\*\*\n\n:::", lambda m: f":::faq **{m.group(1)}**\n{next((a for qt,a in answers if m.group(1)[:25].lower() in qt.lower() or qt[:25].lower() in m.group(1).lower()), '')}\n:::", t)
open(DST, "w", encoding="utf-8").write(t)
print("Готово")
# проверка
import subprocess
out = subprocess.run(["grep","-c",":::faq",DST],capture_output=True,text=True)
print("FAQ блоков:", out.stdout.strip())
