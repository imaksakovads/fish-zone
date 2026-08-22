#!/usr/bin/env python3
"""Koleblyuschiesya: распределяет callout по разделам (вырезает из конца, вставляет по якорям)."""
import re

p = "/Users/igor/project/fish-zone/content/koleblyuschiesya-blyosny-vybrat-lovit.md"
txt = open(p, encoding="utf-8").read()

# Извлекаем callout-блоки из конца (после раздела "Практические советы")
# 1. Вырежем блоки (summary..tip + howto) которые после "### Практические советы"
# Определим позицию раздела "Практические советы"
idx_sovety = txt.find("## Практические советы, которые экономят нервы")
idx_faq = txt.find("## FAQ")

# Всё между "Практические советы" и FAQ содержит callout — вырежем callout-блоки
segment = txt[idx_sovety:idx_faq]
callout_blocks = list(re.finditer(r"(^:::(summary|experience|warning|myth|secret|tip|howto).*?^:::\s*\n?)", segment, re.S|re.M))
print(f"callout-блоков в конце: {len(callout_blocks)}")

# Собираем текст callout отдельно, убираем из segment
blocks_txt = []
for m in callout_blocks:
    blocks_txt.append(m.group(1))
segment_clean = re.sub(r"(^:::(summary|experience|warning|myth|secret|tip|howto).*?^:::\s*\n?)", "", segment, flags=re.S|re.M)

# Восстанавливаем текст с разделами + FAQ
txt = txt[:idx_sovety] + segment_clean + txt[idx_faq:]

# Назначаем блоки по якорям
# summary -> после лида (первый абзац после frontmatter). Найдём первый ## раздел
anchor_summary = txt.find("\n## Хищник смотрит на мир иначе")
# вставим summary перед первым ## (после лида)
txt = txt[:anchor_summary] + "\n\n" + blocks_txt[0].strip() + "\n" + txt[anchor_summary:]

# Остальные по якорям внутри разделов
def insert_after(txt, marker, block):
    """Вставляет block после строки-якоря."""
    idx = txt.find(marker)
    if idx == -1:
        return txt, False
    end = txt.find("\n\n", idx)
    if end == -1:
        return txt, False
    return txt[:end] + "\n\n" + block.strip() + "\n" + txt[end:], True

# experience -> в "Снасть под задачу"
txt, _ = insert_after(txt, "## Снасть под задачу: собираем комплект под колебалку", blocks_txt[1])
# myth -> в "Форма, вес и цвет"
txt, _ = insert_after(txt, "## Форма, вес и цвет: анатомия уловистой колебалки", blocks_txt[3])
# warning -> в "Техника проводки"
txt, _ = insert_after(txt, "## Техника проводки: от равномерки до рывков", blocks_txt[2])
# secret -> в "Сценарии"
txt, _ = insert_after(txt, "## Сценарии: мелководье, глубина, коряжник", blocks_txt[4])
# tip -> в "Практические советы"
txt, _ = insert_after(txt, "## Практические советы, которые экономят нервы", blocks_txt[5])

# howto-блоки (blocks_txt[6:]) -> в "Техника проводки" (4 шага)
howto_all = "\n\n".join(blocks_txt[6:])
txt, _ = insert_after(txt, "## Техника проводки: от равномерки до рывков", howto_all)

# Чистим лишние пустые строки
txt = re.sub(r"\n{3,}", "\n\n", txt)
open(p, "w", encoding="utf-8").write(txt)
print("Koleblyuschiesya: callout распределены")

# Проверка позиций
total = len(txt)
for m in re.finditer(r"^:::(summary|experience|warning|myth|secret|tip|howto)", txt, re.M):
    print(f"  {m.group(1)} на {m.start()/total:.0%}")
