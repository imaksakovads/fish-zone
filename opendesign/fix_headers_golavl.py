#!/usr/bin/env python3
"""Превращает заголовки-текст в заголовки с # в golavl (с иерархией)."""
import re
p = "/Users/igor/project/fish-zone/content/lovit-golavlya-spinning-taktika-primanki.md"
txt = open(p, encoding="utf-8").read()

# Основные разделы -> ##
main_heads = [
    "Биология и поведение объекта",
    "Сезонность: весна / лето / осень / зима",
    "Снасти для ловли голавля",
    "Приманки для голавля",
    "Техника ловли",
    "Практические сценарии ловли",
    "Сводная таблица условий и тактики",
    "Итог и практические рекомендации",
]
# Подразделы -> ###
sub_heads = [
    "Вращающиеся блесны",
    "Колеблющиеся блесны",
    "Силиконовые приманки",
    "Естественные приманки",
    "Выбор точки ловли",
    "Проводка вращающейся блесны",
    "Проводка воблера минноу",
    "Техника ловли на поверхностные приманки",
    "Ловля на силиконовые приманки",
    "Ловля на глубине",
    "Заросли и коряжник",
]

def replace_plain(txt, markers, level):
    for mk in markers:
        pattern = r"^(?!#)" + re.escape(mk) + r"$"
        txt = re.subn(pattern, level + " " + mk, txt, flags=re.M)[0]
    return txt

txt = replace_plain(txt, main_heads, "##")
txt = replace_plain(txt, sub_heads, "###")
open(p, "w", encoding="utf-8").write(txt)
print("Готово")
for m in re.finditer(r"^(#{2,3}) (.+)$", txt, re.M):
    print(f"{m.group(1)} {m.group(2)}")
