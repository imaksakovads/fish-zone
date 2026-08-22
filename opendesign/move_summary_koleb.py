#!/usr/bin/env python3
"""Koleblyuschiesya: перемещает summary в начало (после лида)."""
import re
p = "/Users/igor/project/fish-zone/content/koleblyuschiesya-blyosny-vybrat-lovit.md"
txt = open(p, encoding="utf-8").read()

# Извлекаем summary-блок
m = re.search(r"(:::summary\n.*?^:::)\s*\n?", txt, re.S|re.M)
if not m:
    print("summary не найден")
else:
    summary = m.group(1).strip()
    txt = txt[:m.start()] + txt[m.end():]
    # Вставляем после лида — перед первым "## Хищник"
    anchor = txt.find("## Хищник смотрит на мир иначе")
    if anchor == -1:
        anchor = txt.find("\n## ")
    if anchor != -1:
        txt = txt[:anchor].rstrip() + "\n\n" + summary + "\n\n" + txt[anchor:]
        print("summary перемещён в начало")
    open(p, "w", encoding="utf-8").write(txt)

# проверка
total = len(txt)
for m in re.finditer(r"^:::(summary|experience|warning|myth|secret|tip|howto)", txt, re.M):
    print(f"  {m.group(1)} на {m.start()/total:.0%}")
