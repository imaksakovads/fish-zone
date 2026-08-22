#!/usr/bin/env python3
"""Удаляет чужой 'спиннинговый' блок из tirolskaya (до summary)."""
p = "/Users/igor/project/fish-zone/content/tirolskaya-palochka-montazh-tehnika-lovli.md"
txt = open(p, encoding="utf-8").read()

start = txt.find("Дело вот в чем. Новичок приходит в магазин, смотрит на витрину")
summary = txt.find(":::summary")
if start != -1 and summary != -1 and start < summary:
    line_start = txt.rfind("\n", 0, start) + 1
    txt = txt[:line_start] + txt[summary:]
    print("tirolskaya: чужой блок до summary удалён")
else:
    print("tirolskaya: маркер не найден")
open(p, "w", encoding="utf-8").write(txt)
