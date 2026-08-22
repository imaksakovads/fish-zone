#!/usr/bin/env python3
"""Убирает дубли: задвоенный лид и сырые FAQ-ответы перед ## FAQ."""
import re
F = "/Users/igor/project/fish-zone/content/lovit-sudaka-spinning-tehnika-snasti.md"
t = open(F, encoding="utf-8").read()

# 1. Убрать задвоенный первый абзац тела (дублирует лид)
# Лид: "Судак — это не щука...специализацией."
# В теле он повторяется целиком + ещё 3 абзаца (ошибка новичка...)
# Уберём первый абзац тела, если он == лиду
lines = t.split("\n")
# найдём лид (после frontmatter)
lead = None
for i, ln in enumerate(lines):
    if ln.startswith("Судак — это не щука") and lead is None:
        lead = ln
        break
# найдём дубль в теле (второе вхождение той же строки после пустой строки)
if lead:
    # удалить дублирующее вхождение лида в теле (не первое)
    first = lines.index(lead)
    # ищем второе вхождение
    dups = [i for i, ln in enumerate(lines) if ln == lead]
    if len(dups) > 1:
        # второй дубль идёт сразу после первого абзаца тела — убрать
        lines[dups[1]] = ""
        print("Убран задвоенный лид (строка", dups[1], ")")

# 2. Убрать сырые FAQ-ответы перед "## FAQ" (строки "Бери 2500...", "Нет. Они весят...", и т.д.)
# Они идут после блока катушки и ДО "## FAQ". Найдём "Q1`..Q4`" уже удалены, но их текст остался.
# Тексты ответов повторяются в FAQ-блоках. Удалим абзацы, которые дословно повторяются в :::faq.
faq_answers = re.findall(r":::faq \*\*[^*]*\*\*\n(.*?)\n:::", t, re.S)
answers = {a.strip() for a in faq_answers}
# Удалить абзацы, равные ответам FAQ, которые НЕ внутри :::faq
out = []
for ln in lines:
    s = ln.strip()
    if s in answers and not re.match(r"^:::", ln):
        # это дубль ответа вне faq — пропускаем
        out.append("")
        continue
    out.append(ln)
t = "\n".join(out)
t = re.sub(r"\n{3,}", "\n\n", t)
open(F, "w", encoding="utf-8").write(t)
print("Готово. Размер:", len(t))
