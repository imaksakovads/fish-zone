#!/usr/bin/env python3
"""Добавляет разделы ## в povodok по смысловым маркерам."""
p = "/Users/igor/project/fish-zone/content/vybrat-privyazat-povodok-spinninga.md"
txt = open(p, encoding="utf-8").read()

# (маркер текста, заголовок раздела) — вставляем ## заголовок перед маркером
sections = [
    ("Самый частый сценарий потери приманки — атака щуки.", "## Биология: почему рыба срезает поводок\n"),
    ("Сезонность диктует свои правила в выборе толщины поводка.", "## Сезонность: как меняется выбор поводка\n"),
    ("Переходим к снастям.", "## Снасти и снаряжение\n"),
    ("Длина поводка зависит от размера приманки и назначения.", "## Длина поводка: какая и зачем\n"),
]

for marker, head in sections:
    idx = txt.find(marker)
    if idx != -1:
        line_start = txt.rfind("\n", 0, idx) + 1
        txt = txt[:line_start] + head + txt[line_start:]

open(p, "w", encoding="utf-8").write(txt)
print("Разделы добавлены")
import re
for m in re.finditer(r"^## (.+)$", txt, re.M):
    print(" ##", m.group(1))
