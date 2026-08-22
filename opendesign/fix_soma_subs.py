#!/usr/bin/env python3
"""Soma: подразделы техники и сценариев -> H3."""
import re
p = "/Users/igor/project/fish-zone/content/lovit-soma-spinning-snasti-taktika.md"
txt = open(p, encoding="utf-8").read()

# Подразделы техники (после "Техника ловли сома")
subs_teh = ["Джиг на яме", "Твичинг на мелководье", "Троллинг"]
for s in subs_teh:
    txt = txt.replace(f"## {s}", f"### {s}")

# Подразделы сценариев (после "Практические сценарии")
subs_scen = ["Мелководье", "Глубина", "Коряжник", "Каменистое дно"]
for s in subs_scen:
    txt = txt.replace(f"## {s}", f"### {s}")

open(p, "w", encoding="utf-8").write(txt)
print("Soma: подразделы -> H3")
for m in re.finditer(r"^(#{1,4}) (.+)$", txt, re.M):
    print(f"  {m.group(1)} {m.group(2)}")
