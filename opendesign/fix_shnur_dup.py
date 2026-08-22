#!/usr/bin/env python3
"""Shnur: удаляет старый чужой summary на 90%."""
import re
p = "/Users/igor/project/fish-zone/content/vybrat-shnur-spinninga-pletyonka-vs-leska.md"
txt = open(p, encoding="utf-8").read()
# Найдём все summary, удалим тот, что после 50%
blocks = list(re.finditer(r"(:::summary\n.*?^:::) ", txt, re.S|re.M))
for m in blocks:
    if m.start()/len(txt) > 0.5:
        txt = txt[:m.start()] + txt[m.end():]
        print(f"Удалён summary на {m.start()/len(txt):.0%}")
        break
open(p, "w", encoding="utf-8").write(txt)
# проверка
for m in re.finditer(r":::summary", txt):
    print(f"summary остался на {m.start()/len(txt):.0%}")
