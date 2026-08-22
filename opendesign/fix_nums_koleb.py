#!/usr/bin/env python3
"""Убирает ручную нумерацию (1., 2., ...) из заголовков koleblyuschiesya."""
import re
p = "/Users/igor/project/fish-zone/content/koleblyuschiesya-blyosny-vybrat-lovit.md"
txt = open(p, encoding="utf-8").read()

# Убираем "N. " из заголовков ### (но не из ## FAQ)
def clean(m):
    return m.group(1) + re.sub(r"^\d+\.\s+", "", m.group(2))

txt = re.sub(r"^(###\s+)(\d+\.\s+.+)$", clean, txt, flags=re.M)
open(p, "w", encoding="utf-8").write(txt)
print("Готово")
for m in re.finditer(r"^### (.+)$", txt, re.M):
    print("###", m.group(1))
