#!/usr/bin/env python3
"""forel: удаляет остаток чужого блока 'Тест на спиннинге', H3->H2."""
import re
p = "/Users/igor/project/fish-zone/content/lovit-forel-spinning-snasti-primanki.md"
txt = open(p, encoding="utf-8").read()

# 1. Удалить остаток чужого блока (от "Тест на спиннинге" до ## FAQ)
idx = txt.find("Тест на спиннинге это не украшение")
faq = txt.find("## FAQ")
if idx != -1 and faq != -1 and idx < faq:
    line_start = txt.rfind("\n", 0, idx) + 1
    txt = txt[:line_start].rstrip() + "\n\n## FAQ\n\n"
    print("Удалён остаток чужого блока")

# 2. H3 -> H2 (все разделы станут ##)
txt = re.sub(r"^### ", "## ", txt, flags=re.M)
open(p, "w", encoding="utf-8").write(txt)
print("H3->H2 готово")
for m in re.finditer(r"^#{1,3} (.+)$", txt, re.M):
    print(" ", m.group(0))
