#!/usr/bin/env python3
"""Poppery: удаляет чужой блок про щуку, превращает H1->H2, распределяет callout."""
import re
p = "/Users/igor/project/fish-zone/content/poppery-uokery-tehnika-lovli-poverhnostnymi.md"
txt = open(p, encoding="utf-8").read()

# 1. Извлекаем callout-блоки (сохраняем)
blocks = list(re.finditer(r"(^:::(summary|experience|warning|myth|secret|tip|howto).*?^:::\s*\n?)", txt, re.S|re.M))
block_texts = [m.group(1).strip() for m in blocks]
block_types = [m.group(2) for m in blocks]
print(f"callout: {len(blocks)}")

# 2. Убираем чужой блок про щуку (от "Почему щука сходит" до FAQ) + все callout
# Сначала удалим callout
txt_clean = re.sub(r"(^:::(summary|experience|warning|myth|secret|tip|howto).*?^:::\s*\n?)", "", txt, flags=re.S|re.M)

# Удаляем чужой блок про щуку: от "## Почему щука сходит" до "## FAQ"
chuzh_start = txt_clean.find("## Почему щука сходит именно у травы")
faq = txt_clean.find("## FAQ")
if chuzh_start != -1 and faq != -1 and chuzh_start < faq:
    txt_clean = txt_clean[:chuzh_start].rstrip() + "\n\n" + txt_clean[faq:]
    print("чужой блок про щуку удалён")

# 3. H1 -> H2 (разделы)
txt_clean = re.sub(r"^# (?!#)", "## ", txt_clean, flags=re.M)

# 4. Распределяем callout по H2-разделам
txt_clean = re.sub(r"\n{3,}", "\n\n", txt_clean)
sections = [(m.start(), m.group(1)) for m in re.finditer(r"^## (.+)$", txt_clean, re.M)]
content_sections = [s for s in sections if "FAQ" not in s[1]]
print(f"H2-разделов: {len(content_sections)}")

def target(bt, sections):
    order = {"summary":0, "experience":1, "warning":2, "myth":3, "secret":4}
    if bt in order and order[bt] < len(sections):
        return sections[order[bt]]
    if bt == "howto":
        for s in sections:
            if "техник" in s[1].lower() or "проводк" in s[1].lower():
                return s
        return sections[-2] if len(sections)>=2 else sections[-1]
    return sections[-1]

def insert_pos(anchor_start, used):
    end = txt_clean.find("\n\n", anchor_start)
    if end == -1:
        end = anchor_start
    while end in used:
        nxt = txt_clean.find("\n\n", end+2)
        if nxt == -1:
            end = anchor_start + 60
            break
        end = nxt
    used.add(end)
    return end

used = set()
assignments = []
for i, bt in enumerate(block_types):
    sec = target(bt, content_sections)
    pos = insert_pos(sec[0], used)
    assignments.append((pos, block_texts[i]))

for pos, block in sorted(assignments, key=lambda x: -x[0]):
    txt_clean = txt_clean[:pos] + "\n\n" + block + txt_clean[pos:]

open(p, "w", encoding="utf-8").write(txt_clean)
total = len(txt_clean)
for m in re.finditer(r"^:::(summary|experience|warning|myth|secret|tip|howto)", txt_clean, re.M):
    print(f"  {m.group(1)} на {m.start()/total:.0%}")
