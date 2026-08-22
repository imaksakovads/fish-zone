#!/usr/bin/env python3
"""Tviching: распределяет callout по H3-разделам (нет H2, кроме FAQ)."""
import re
p = "/Users/igor/project/fish-zone/content/tviching-spinninge-tehnika-lovli-voblerom.md"
txt = open(p, encoding="utf-8").read()

# Извлекаем callout-блоки
blocks = list(re.finditer(r"(^:::(summary|experience|warning|myth|secret|tip|howto).*?^:::\s*\n?)", txt, re.S|re.M))
block_texts = [m.group(1).strip() for m in blocks]
block_types = [m.group(2) for m in blocks]
print(f"callout: {len(blocks)}")

# Убираем callout из текста
txt_clean = re.sub(r"(^:::(summary|experience|warning|myth|secret|tip|howto).*?^:::\s*\n?)", "", txt, flags=re.S|re.M)
txt_clean = re.sub(r"\n{3,}", "\n\n", txt_clean)

# H3 разделы
sections = [(m.start(), m.group(1)) for m in re.finditer(r"^### (.+)$", txt_clean, re.M)]
print(f"H3-разделов: {len(sections)}")

# Назначение: summary->1-й, experience->2-й, warning->3-й, myth->4-й, secret->5-й, howto->"Техника", tip->последний
def target(bt, sections):
    order = {"summary":0, "experience":1, "warning":2, "myth":3, "secret":4}
    if bt in order and order[bt] < len(sections):
        return sections[order[bt]]
    if bt == "howto":
        for s in sections:
            if "техник" in s[1].lower() or "проводк" in s[1].lower() or "твичинг" in s[1].lower():
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
    sec = target(bt, sections)
    pos = insert_pos(sec[0], used)
    assignments.append((pos, block_texts[i]))

for pos, block in sorted(assignments, key=lambda x: -x[0]):
    txt_clean = txt_clean[:pos] + "\n\n" + block + txt_clean[pos:]

open(p, "w", encoding="utf-8").write(txt_clean)
total = len(txt_clean)
for m in re.finditer(r"^:::(summary|experience|warning|myth|secret|tip|howto)", txt_clean, re.M):
    print(f"  {m.group(1)} на {m.start()/total:.0%}")
