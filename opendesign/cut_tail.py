#!/usr/bin/env python3
"""Удаляет чужой блок 'Выбор первого спиннинга' из статей."""
import re

def cut_tail(path, marker):
    txt = open(path, encoding="utf-8").read()
    idx = txt.find(marker)
    if idx == -1:
        return txt, False
    head = txt[:idx].rstrip() + "\n"
    open(path, "w", encoding="utf-8").write(head)
    return head, True

# silikonovye: чужой блок после "Итог и практические рекомендации"
p = "/Users/igor/project/fish-zone/content/silikonovye-primanki-spinninga-vidy-montazh.md"
head, ok = cut_tail(p, "Выбор первого спиннинга.")
print(f"silikonovye: удалён чужой блок = {ok}, размер {len(head)}")

# soma: чужой блок
p = "/Users/igor/project/fish-zone/content/lovit-soma-spinning-snasti-taktika.md"
head, ok = cut_tail(p, "Выбор первого спиннинга похож")
print(f"soma: удалён чужой блок = {ok}, размер {len(head)}")
