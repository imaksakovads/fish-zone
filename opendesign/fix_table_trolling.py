#!/usr/bin/env python3
"""Восстанавливает таблицу соответствий в trolling."""
import re
p = "/Users/igor/project/fish-zone/content/trolling-spinninge-snasti-tehnika-lodki.md"
txt = open(p, encoding="utf-8").read()

# Блок строк "Условие:/Снасть:/Приманка:/Скорость:/Стратегия:" 
# Найдём группу из 5 последовательных строк с этими префиксами
lines = txt.split("\n")
out = []
i = 0
table_started = False
while i < len(lines):
    s = lines[i].strip()
    # начало блока таблицы
    if s.startswith("Условие:") and not table_started:
        # собираем группу блоков (каждый блок = 5 строк, разделён пустой строкой)
        blocks = []
        while i < len(lines):
            blk = lines[i:i+5]
            # проверка что это блок таблицы
            prefixes = [b.strip().split(":")[0] for b in blk]
            if all(p in ("Условие","Снасть","Приманка","Скорость","Стратегия") for p in prefixes):
                blocks.append([b.strip() for b in blk])
                i += 6  # пропускаем блок + пустую строку
            else:
                break
        if blocks:
            out.append("\n| Условие | Снасть | Приманка | Скорость | Стратегия |")
            out.append("| --- | --- | --- | --- | --- |")
            for blk in blocks:
                vals = {}
                for b in blk:
                    k, _, v = b.partition(":")
                    vals[k] = v.strip()
                row = "| " + " | ".join([vals.get("Условие",""), vals.get("Снасть",""), vals.get("Приманка",""), vals.get("Скорость",""), vals.get("Стратегия","")]) + " |"
                out.append(row)
            out.append("")
            table_started = True
            continue
    out.append(lines[i])
    i += 1

txt = "\n".join(out)
open(p, "w", encoding="utf-8").write(txt)
print("Готово, таблица восстановлена" if table_started else "Таблица не найдена")
