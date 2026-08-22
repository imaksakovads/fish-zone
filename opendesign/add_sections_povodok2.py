#!/usr/bin/env python3
"""Добавляет разделы ## в povodok (материалы, привязка, сценарии)."""
p = "/Users/igor/project/fish-zone/content/vybrat-privyazat-povodok-spinninga.md"
txt = open(p, encoding="utf-8").read()

sections = [
    ("Теперь о материалах подробнее.", "## Материалы поводка: какой выбрать\n"),
    ("Техника привязывания поводка — отдельная тема.", "## Как правильно привязать поводок\n"),
    ("Теперь о сценариях ловли.", "## Сценарии ловли и тактика\n"),
]
for marker, head in sections:
    idx = txt.find(marker)
    if idx != -1:
        line_start = txt.rfind("\n", 0, idx) + 1
        txt = txt[:line_start] + head + txt[line_start:]

open(p, "w", encoding="utf-8").write(txt)
import re
for m in re.finditer(r"^## (.+)$", txt, re.M):
    print(" ##", m.group(1))
