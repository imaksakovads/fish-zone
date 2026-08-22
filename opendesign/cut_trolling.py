#!/usr/bin/env python3
"""Обрезает чужой блок про спиннинг в trolling."""
import re
p = "/Users/igor/project/fish-zone/content/trolling-spinninge-snasti-tehnika-lodki.md"
txt = open(p, encoding="utf-8").read()

# Чужой блок начинается после "# Итог" с "Собрать первый спиннинг проще"
marker = "Собрать первый спиннинг проще, чем кажется."
idx = txt.find(marker)
if idx != -1:
    head = txt[:idx].rstrip() + "\n"
    open(p, "w", encoding="utf-8").write(head)
    print(f"trolling: удалён чужой блок ({len(txt)-len(head)} симв), размер {len(head)}")
else:
    print("trolling: маркер не найден, размер", len(txt))

# Проверка
txt = open(p, encoding="utf-8").read()
print("=== заголовки ===")
for m in re.finditer(r"^(#{1,3}) (.+)$", txt, re.M):
    print(f"  {m.group(1)} {m.group(2)}")
