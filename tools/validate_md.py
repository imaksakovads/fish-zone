#!/usr/bin/env python3
"""Валидатор markdown-статей для fish-zone.

Проверяет структурные проблемы, которые раньше ловились только на живом сайте:
1. Заголовки-строки без '#' (гуманизатор выдавал их как обычный текст).
2. Пустой '## FAQ' (без :::faq) или отсутствие FAQ.
3. Callout-блоки скучены в конце статьи (>60%).
4. Чужой контент «про выбор спиннинга» в НЕ-спиннинговых темах.

Использование:
    python tools/validate_md.py <файл.md> [<файл.md> ...]
Возвращает 0 если чисто, 1 если есть ошибки (критичные) или предупреждения.
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

# Заголовки, похожие на "заголовок-строку" без # (короткие, без точки, с заглавной)
def _looks_like_plain_heading(line: str) -> bool:
    s = line.strip()
    if not (10 < len(s) < 60):
        return False
    if s.startswith(("#", ":::", "|", "!", "-", "*", ">", "`")):
        return False
    if "|" in s:  # строка таблицы
        return False
    if s.endswith((".", ":", ",", "?", "!", ";", "»")):
        return False
    if "  " in s or s.startswith(("http", "www", "title", "date", "author", "tags", "image")):
        return False
    # Первый символ — заглавная кириллица
    if not re.match(r"^[А-ЯЁA-Z]", s):
        return False
    # Слишком похоже на обычное предложение — содержит союз/предлог в начале
    if re.match(r"^(Но|И|А|Для|С|К|В|На|По|При|Что|Как|Когда|Если|Где|Кто|Это|Он|Она|Они|Мы|Вы)", s, re.I):
        return False
    return True


# Маркеры «чужого» спиннингового контента (вставлялся гуманизатором в НЕ-спиннинговые темы)
# Только явные — про ВЫБОР первого спиннинга, не про снасть для конкретной темы
_SPIN_MARKERS = [
    "выбор первого спиннинга", "первый спиннинг", "спиннинг для новичка",
    "первый комплект", "новинку спиннинг", "собрать первый спиннинг",
    "спиннинг до 3000", "спиннинг за 3000", "новый спиннинг",
]


def validate_md(md: str, *, title: str = "") -> list[str]:
    """Возвращает список ошибок/предупреждений. Пустой список = чисто."""
    issues: list[str] = []
    lines = md.split("\n")

    # 1. Заголовки-строки без #
    plain_heads = [l.strip() for l in lines if _looks_like_plain_heading(l)]
    if plain_heads:
        issues.append(f"Найдены заголовки-строки без '#' ({len(plain_heads)}): "
                      f"{', '.join(plain_heads[:3])}")

    # 2. FAQ: должен быть и не пустой
    has_faq_h2 = any(l.strip() == "## FAQ" for l in lines)
    faq_blocks = len(re.findall(r"^:::faq", md, re.M))
    if not has_faq_h2:
        issues.append("Отсутствует '## FAQ' (нет раздела FAQ)")
    elif faq_blocks == 0:
        issues.append("Раздел '## FAQ' пустой (нет :::faq-блоков)")

    # 3. Callout скучены в конце
    total = len(md)
    callout_positions = [
        m.start() / total
        for m in re.finditer(r"^:::(summary|experience|warning|myth|secret|tip)", md, re.M)
    ]
    if callout_positions and len(callout_positions) >= 2:
        if all(p > 0.55 for p in callout_positions):
            issues.append(
                f"Все callout-блоки ({len(callout_positions)}) скучены в конце "
                f"(мин {min(callout_positions):.0%}) — распределите по разделам")
        if not any(p < 0.5 for p in callout_positions):
            issues.append("Нет callout-блоков в первой половине статьи")

    # 4. Чужой спиннинговый контент (если тема не про спиннинг/снасть)
    low = md.lower()
    spin_hits = [mk for mk in _SPIN_MARKERS if mk in low]
    is_spin_topic = any(k in title.lower() for k in ["спиннинг", "шнур", "плетён", "катушк", "удилищ", "поводок"])
    if spin_hits and not is_spin_topic:
        issues.append(f"Возможен чужой 'спиннинговый' контент: {', '.join(spin_hits[:3])}")

    return issues


def validate_file(path: Path) -> int:
    md = path.read_text(encoding="utf-8")
    # Извлечь title из frontmatter
    title = ""
    m = re.search(r"^title:\s*[\"']?([^\"'\n]+)", md, re.M)
    if m:
        title = m.group(1).strip()
    issues = validate_md(md, title=title)
    if issues:
        print(f"⚠️ {path.name}:")
        for i in issues:
            print(f"   - {i}")
        return 1
    return 0


def main() -> int:
    files = [Path(a) for a in sys.argv[1:]]
    if not files:
        print("Использование: python tools/validate_md.py <файл.md> ...")
        return 2
    bad = 0
    for f in files:
        if f.is_file():
            bad += validate_file(f)
        else:
            print(f"❌ {f}: файл не найден")
            bad += 1
    print(f"\nПроверено файлов: {len(files)}, с проблемами: {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
