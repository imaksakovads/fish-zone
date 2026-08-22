#!/usr/bin/env python3
"""Вырезает чужой 'спиннинговый' блок (от 'Тест показывает' до '## FAQ') из 8 статей."""
import re, os

content_dir = "/Users/igor/project/fish-zone/content"
targets = ["dzhig-spinninge-tehnika-lovli-nachinayuschih","lovit-forel-spinning-snasti-primanki",
           "lovit-zhereha-spinning-polnoe-rukovodstvo","otvodnoy-povodok-montazh-tehnika-lovli",
           "vyazat-rybolovnye-uzly-spinninga","vybrat-blesnu-spinninga-kolebalki-vertushki",
           "vybrat-shnur-spinninga-pletyonka-vs-leska","vybrat-vobler-spinninga-polnyy-gid"]

for name in targets:
    p = os.path.join(content_dir, name + ".md")
    txt = open(p, encoding="utf-8").read()
    idx = txt.find("Тест показывает")
    faq = txt.find("## FAQ")
    if idx != -1 and faq != -1 and idx < faq:
        # Обрезаем от начала чужого блока (с начала строки) до FAQ
        line_start = txt.rfind("\n", 0, idx) + 1
        head = txt[:line_start].rstrip() + "\n\n## FAQ\n\n"
        open(p, "w", encoding="utf-8").write(head)
        print(f"{name}: удалён чужой блок ({len(txt)-len(head)} симв), теперь {len(head)}")
    else:
        print(f"{name}: не найден чужой блок (idx={idx}, faq={faq})")
