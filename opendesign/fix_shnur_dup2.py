#!/usr/bin/env python3
"""Shnur: удаляет старый чужой summary на 90%."""
import re
p = "/Users/igor/project/fish-zone/content/vybrat-shnur-spinninga-pletyonka-vs-leska.md"
txt = open(p, encoding="utf-8").read()
# Найдём все summary блоки (:::summary ... :::
blocks = list(re.finditer(r":::summary\n.*?^:::", txt, re.S|re.M))
print("Найдено summary:", len(blocks))
for m in blocks:
    pos = m.start()/len(txt)
    print(f"  {pos:.0%}")
    if pos > 0.5:
        txt = txt[:m.start()] + txt[m.end():]
        print("  -> удалён")
        break
open(p, "w", encoding="utf-8").write(txt)
# проверка
for m in re.finditer(r":::summary", txt):
    print(f"summary остался на {m.start()/len(txt):.0%}")
