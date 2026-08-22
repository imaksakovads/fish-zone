#!/usr/bin/env python3
"""Универсальный распределитель callout: вырезает callout из конца, вставляет по разделам.

Логика:
- Находит разделы (##) статьи.
- Извлекает callout-блоки (:::summary/experience/warning/myth/secret/tip/howto) из конца (после последнего контентного раздела, до FAQ).
- Распределяет: summary -> первый раздел, остальные -> по одному на раздел в порядке появления.
- howto -> в раздел техники (если есть "Техник" в названии), иначе в предпоследний контентный.
"""
import re, sys

def redistribute(path: str) -> None:
    txt = open(path, encoding="utf-8").read()
    total_before = len(txt)

    # Разделы ## и их позиции
    sections = [(m.start(), m.group(1)) for m in re.finditer(r"^## (.+)$", txt, re.M)]
    faq_idx = txt.find("## FAQ")
    if faq_idx == -1:
        faq_idx = len(txt)

    # Извлекаем все callout-блоки (кроме :::faq) — из всей статьи, чтобы пересобрать
    blocks = list(re.finditer(r"(^:::(summary|experience|warning|myth|secret|tip|howto).*?^:::\s*\n?)", txt, re.S|re.M))
    if not blocks:
        print(f"  {path}: нет callout")
        return

    # Типы блоков по порядку
    block_types = [m.group(2) for m in blocks]
    block_texts = [m.group(1).strip() for m in blocks]

    # Убираем все callout из текста (включая блоки в конце)
    txt_clean = re.sub(r"(^:::(summary|experience|warning|myth|secret|tip|howto).*?^:::\s*\n?)", "", txt, flags=re.S|re.M)
    txt_clean = re.sub(r"\n{3,}", "\n\n", txt_clean)

    # Заново находим разделы в очищенном тексте
    sections_clean = [(m.start(), m.group(1)) for m in re.finditer(r"^## (.+)$", txt_clean, re.M)]

    # Распределяем блоки: summary -> первый раздел, остальные -> по одному на раздел
    # Найдём вставку: после первого абзаца каждого раздела
    # Разбиваем: summary идёт первым, потом остальные по порядку
    # Определяем раздел-якорь для каждого блока (по номеру)
    content_sections = [s for s in sections_clean if "FAQ" not in s[1]]

    # Тип -> предпочтительный раздел
    def target_section(bt, n):
        # summary -> 1-й, experience -> 2-й, warning -> 3-й, myth -> 4-й, secret -> 5-й, tip -> последний
        order = {"summary":0, "experience":1, "warning":2, "myth":3, "secret":4}
        if bt in order and order[bt] < len(content_sections):
            return content_sections[order[bt]]
        # howto -> раздел с "Техник" или предпоследний
        if bt == "howto":
            for s in content_sections:
                if "техник" in s[1].lower() or "проводк" in s[1].lower():
                    return s
            return content_sections[-2] if len(content_sections) >= 2 else content_sections[-1]
        return content_sections[-1]

    # Вставляем блоки в обратном порядке (чтобы не ломать индексы)
    # Найдём вставку: после заголовка раздела, перед первым \n\n (концом первого абзаца)
    def insert_pos(anchor_start):
        # вставить после первого абзаца раздела
        end = txt_clean.find("\n\n", anchor_start)
        if end == -1:
            end = anchor_start
        return end

    # Группируем блоки по разделам
    # Проще: вставляем в порядке, идя с конца
    # Сначала назначим каждому блоку позицию вставки
    assignments = []  # (insert_pos, block_text)
    used_positions = set()
    for i, bt in enumerate(block_types):
        sec = target_section(bt, i)
        pos = insert_pos(sec[0])
        # сдвиг чтобы не вставлять дважды в одно место
        while pos in used_positions:
            pos = txt_clean.find("\n\n", pos + 2)
            if pos == -1:
                pos = sec[0] + 50
                break
        used_positions.add(pos)
        assignments.append((pos, block_texts[i]))

    # Вставляем с конца
    for pos, block in sorted(assignments, key=lambda x: -x[0]):
        txt_clean = txt_clean[:pos] + "\n\n" + block + txt_clean[pos:]

    open(path, "w", encoding="utf-8").write(txt_clean)
    print(f"  {path}: распределено {len(blocks)} callout ({total_before}->{len(txt_clean)})")

    # Проверка
    total = len(txt_clean)
    for m in re.finditer(r"^:::(summary|experience|warning|myth|secret|tip|howto)", txt_clean, re.M):
        print(f"    {m.group(1)} на {m.start()/total:.0%}")

if __name__ == "__main__":
    for f in sys.argv[1:]:
        redistribute(f)
