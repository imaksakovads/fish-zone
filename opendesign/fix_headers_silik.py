#!/usr/bin/env python3
"""Превращает заголовки-текст в ## в silikonovye."""
p = "/Users/igor/project/fish-zone/content/silikonovye-primanki-spinninga-vidy-montazh.md"
lines = open(p, encoding="utf-8").read().split("\n")

# Заголовки без решётки (по номеру строки из анализа)
headings = {16, 26, 36, 48, 62, 74, 82, 92}
for i in headings:
    if 0 <= i-1 < len(lines):
        lines[i-1] = "## " + lines[i-1].strip()

open(p, "w", encoding="utf-8").write("\n".join(lines))
print("Готово")

# Проверка
import re
txt = open(p, encoding="utf-8").read()
for m in re.finditer(r"^## (.+)$", txt, re.M):
    print("##", m.group(1))
