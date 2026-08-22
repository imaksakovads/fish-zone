#!/usr/bin/env python3
"""Удаляет чужой блок про выбор спиннинга из golavl (до ## FAQ)."""
import re
p = "/Users/igor/project/fish-zone/content/lovit-golavlya-spinning-taktika-primanki.md"
txt = open(p, encoding="utf-8").read()

marker = "Тест показывает, приманки какого веса удержит удилище."
idx = txt.find(marker)
faq_idx = txt.find("## FAQ")
if idx != -1 and faq_idx != -1 and idx < faq_idx:
    head = txt[:idx].rstrip() + "\n\n## FAQ\n\n"
    open(p, "w", encoding="utf-8").write(head)
    print(f"golavl: удалён чужой блок, размер {len(head)}")
else:
    print("golavl: маркер не найден")
