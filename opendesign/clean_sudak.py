#!/usr/bin/env python3
import re
F = "/Users/igor/project/fish-zone/content/lovit-sudaka-spinning-tehnika-snasti.md"
t = open(F, encoding="utf-8").read()
# Удалить строки вида "NN`Текст" (TOC-дамп из aside)
t = re.sub(r"^\d{2}`\S.*$", "", t, flags=re.M)
# Удалить строки "NN`" (голый номер)
t = re.sub(r"^\d{2}`\s*$", "", t, flags=re.M)
t = re.sub(r"\n{3,}", "\n\n", t)
open(F, "w", encoding="utf-8").write(t)
print("Осталось мусора:", len(re.findall(r"^\d{2}`", t, re.M)))
print("Размер:", len(t))
