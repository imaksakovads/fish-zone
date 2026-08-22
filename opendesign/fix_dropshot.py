#!/usr/bin/env python3
"""Удаляет чужой хвост (про выбор спиннинга) из drop-shot, soma, silikonovye."""
import re

def cut_tail(path, stop_marker):
    """Обрезает текст статьи до stop_marker (оставляет маркер и всё до него)."""
    txt = open(path, encoding="utf-8").read()
    # если маркер найден, обрезаем после него
    idx = txt.find(stop_marker)
    if idx == -1:
        return txt, False
    # оставляем до конца строки маркера
    end = txt.find("\n", idx)
    head = txt[:end+1] if end != -1 else txt[:idx+len(stop_marker)]
    return head, True

# drop-shot: чужой блок начинается с "Выбор первого спиннинга." (после Итога)
import shutil
p = "/Users/igor/project/fish-zone/content/drop-shot-osnastka-tehnika-lovli.md"
txt = open(p, encoding="utf-8").read()
# Найдём начало чужого блока
marker = "Выбор первого спиннинга."
idx = txt.find(marker)
if idx != -1:
    # обрезаем до начала чужого блока, но оставляем Итог (он выше)
    head = txt[:idx].rstrip() + "\n"
    open(p, "w", encoding="utf-8").write(head)
    print(f"drop-shot: удалён чужой блок ({len(txt)-len(head)} симв), теперь {len(head)}")
else:
    print("drop-shot: маркер не найден")
