#!/usr/bin/env python3
"""Превращает заголовки-текст в заголовки в zhereha и yazya."""
import re

def fix(name, main_heads, sub_heads):
    p = f"/Users/igor/project/fish-zone/content/{name}.md"
    txt = open(p, encoding="utf-8").read()
    def replace(txt, markers, level):
        for mk in markers:
            txt = re.subn(r"^(?!#)" + re.escape(mk) + r"$", level + " " + mk, txt, flags=re.M)[0]
        return txt
    txt = replace(txt, main_heads, "##")
    txt = replace(txt, sub_heads, "###")
    open(p, "w", encoding="utf-8").write(txt)
    print(f"{name}: готово")
    for m in re.finditer(r"^(#{2,3}) (.+)$", txt, re.M):
        print(f"  {m.group(1)} {m.group(2)}")

# zhereha
fix("lovit-zhereha-spinning-polnoe-rukovodstvo",
    ["Биология и поведение объекта","Сезонность: когда и как ловить","Снасти: детальный разбор",
     "Приманки: полный арсенал","Техника ловли пошагово","Практические сценарии: как ловить в разных условиях",
     "Сводная таблица: быстрое решение","Итог и практические рекомендации"],
    ["Воблеры-минноу","Колеблющиеся блёсны","Поверхностные приманки"])

print()
# yazya
fix("lovlya-yazya-spinning-primanki-provodki",
    ["Биология и поведение язя","Сезонность ловли язя","Снасти для ловли язя","Приманки для язя",
     "Техника ловли язя","Практические сценарии ловли язя","Сводная таблица условий ловли язя",
     "Итог и практические рекомендации"],
    [])
