#!/usr/bin/env python3
"""Удаляет чужой 'спиннинговый' блок из kastmaster (строки про 'Спиннинг для новичка')."""
import re
p = "/Users/igor/project/fish-zone/content/kastmaster-chto-eto-i-kak-lovit.md"
txt = open(p, encoding="utf-8").read()

# Чужой блок начинается с "Спиннинг для новичка — это всегда лотерея" и заканчивается перед ":summary"
start = txt.find("Спиннинг для новичка — это всегда лотерея")
summary = txt.find(":::summary")
if start != -1 and summary != -1 and start < summary:
    # Удалить от начала строки с чужим текстом до summary
    line_start = txt.rfind("\n", 0, start) + 1
    txt = txt[:line_start] + txt[summary:]
    print("kastmaster: чужой спиннинговый блок удалён")
else:
    print("kastmaster: не найдено")
open(p, "w", encoding="utf-8").write(txt)
