#!/usr/bin/env python3
"""Превращает сезоны (Весна/Лето/Осень/Зима) в H4 в golavl."""
p = "/Users/igor/project/fish-zone/content/lovit-golavlya-spinning-taktika-primanki.md"
lines = open(p, encoding="utf-8").read().split("\n")
seasons = {"Весна","Лето","Осень","Зима"}
count = 0
for i, l in enumerate(lines):
    s = l.strip()
    if s in seasons and not s.startswith("#"):
        lines[i] = "#### " + s
        count += 1
open(p, "w", encoding="utf-8").write("\n".join(lines))
print(f"Сезонов в H4: {count}")
