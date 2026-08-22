#!/usr/bin/env python3
"""Превращает заголовки-текст в ## в kastmaster."""
p = "/Users/igor/project/fish-zone/content/kastmaster-chto-eto-i-kak-lovit.md"
txt = open(p, encoding="utf-8").read()

# Заголовки-текст (по содержимому)
markers = [
    "Биология хищника, или почему он клюет на кусок металла",
    "Сезонность. Тактика по временам года",
    "Снасти под Кастмастер. Подбираем комплект с умом",
    "Приманки. Размеры и цвета",
    "Техника ловли. От простого к сложному",
    "Практические сценарии. Реальные ситуации",
    "Сводная таблица. Условие, снасть, приманка, тактика",
]
import re
changed = 0
for mk in markers:
    # заменяем строку, равную маркеру, на ## маркер (только если не начинается с #)
    pattern = r"^(?!#)" + re.escape(mk) + r"$"
    txt, n = re.subn(pattern, "## " + mk, txt, flags=re.M)
    changed += n

open(p, "w", encoding="utf-8").write(txt)
print(f"Изменено заголовков: {changed}")
for m in re.finditer(r"^## (.+)$", txt, re.M):
    print("##", m.group(1))
