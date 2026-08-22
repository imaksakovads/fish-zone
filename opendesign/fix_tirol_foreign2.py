#!/usr/bin/env python3
"""Удаляет чужой спиннинговый блок из tirolskaya (после summary до FAQ)."""
p = "/Users/igor/project/fish-zone/content/tirolskaya-palochka-montazh-tehnika-lovli.md"
txt = open(p, encoding="utf-8").read()

start = txt.find("Тест это диапазон веса приманок, которые бланк")
faq = txt.find("## FAQ")
if start != -1 and faq != -1 and start < faq:
    line_start = txt.rfind("\n", 0, start) + 1
    txt = txt[:line_start] + txt[faq:]
    print("tirolskaya: чужой спиннинговый блок (после summary) удалён")
else:
    print("tirolskaya: не найдено (start={}, faq={})".format(start, faq))
open(p, "w", encoding="utf-8").write(txt)
# проверка
print("Остаток 'спиннинг для новичка':", "спиннинг для новичка" in txt.lower())
